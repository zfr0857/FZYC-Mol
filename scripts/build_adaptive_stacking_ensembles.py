from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from rdkit import RDLogger
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.analysis import max_train_similarity
from fzyc_mol.datasets import DATASETS, load_dataset
from fzyc_mol.evaluate import compute_metrics
from fzyc_mol.splits import make_split


RDLogger.DisableLog("rdApp.*")

SEEDS = [13, 17, 23, 29, 31]
SIMILARITY_CACHE: dict[tuple[str, int], pd.Series] = {}

MEMBER_SETS = {
    "core": [
        ("reports/full_moleculenet", "rf_morgan"),
        ("reports/full_moleculenet", "gin"),
        ("reports/full_moleculenet", "fzyc_mol_static"),
    ],
    "ai": [
        ("reports/full_moleculenet", "gin"),
        ("reports/full_moleculenet", "fzyc_mol_static"),
        ("reports/upgrade_graph_transformer", "fzyc_mol_gt"),
    ],
    "all": [
        ("reports/full_moleculenet", "rf_morgan"),
        ("reports/full_moleculenet", "gin"),
        ("reports/full_moleculenet", "fzyc_mol_static"),
        ("reports/upgrade_graph_transformer", "fzyc_mol_gt"),
    ],
    "chemberta": [
        ("reports/full_moleculenet", "rf_morgan"),
        ("reports/full_moleculenet", "gin"),
        ("reports/full_moleculenet", "fzyc_mol_static"),
        ("reports/upgrade_graph_transformer", "fzyc_mol_gt"),
        ("reports/pretrained_frozen", "DeepChem_ChemBERTa-77M-MTR_frozen_head"),
    ],
    "chemberta_rdkit": [
        ("reports/full_moleculenet", "rf_morgan"),
        ("reports/full_moleculenet", "gin"),
        ("reports/full_moleculenet", "fzyc_mol_static"),
        ("reports/upgrade_graph_transformer", "fzyc_mol_gt"),
        ("reports/pretrained_rdkit", "DeepChem_ChemBERTa-77M-MTR_rdkit_head"),
    ],
}


class ConstantProbability:
    def __init__(self, value: float) -> None:
        self.value = float(np.clip(value, 1e-7, 1.0 - 1e-7))

    def predict_proba(self, x):
        prob = np.full((len(x),), self.value, dtype=np.float64)
        return np.column_stack([1.0 - prob, prob])


def _as_probability(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    if values.min() >= 0.0 and values.max() <= 1.0:
        return values
    return 1.0 / (1.0 + np.exp(-np.clip(values, -60.0, 60.0)))


def _prediction_path(report_dir: Path, dataset: str, model: str, seed: int, split_tag: str) -> Path:
    if split_tag == "valid":
        return report_dir / f"{dataset}_{model}_seed{seed}_valid_predictions.csv"
    return report_dir / f"{dataset}_{model}_seed{seed}_predictions.csv"


def load_member_predictions(
    dataset: str,
    seed: int,
    members: list[tuple[str, str]],
    task_type: str,
    split_tag: str,
) -> tuple[pd.DataFrame, list[str]]:
    merged: pd.DataFrame | None = None
    pred_cols: list[str] = []
    for report_dir, model in members:
        path = _prediction_path(ROOT / report_dir, dataset, model, seed, split_tag)
        if not path.exists():
            raise FileNotFoundError(path)
        frame = pd.read_csv(path)[["smiles", "y_true", "y_pred"]].copy()
        col = f"pred_{model}"
        if task_type == "classification":
            frame["y_pred"] = _as_probability(frame["y_pred"].to_numpy())
        frame = frame.rename(columns={"y_pred": col})
        pred_cols.append(col)
        if merged is None:
            merged = frame
        else:
            merged = merged.merge(frame[["smiles", col]], on="smiles", how="inner")
    if merged is None:
        raise ValueError("No ensemble members were provided.")
    return merged, pred_cols


def add_applicability_features(
    dataset: str,
    table: pd.DataFrame,
    frame: pd.DataFrame,
    seed: int,
    pred_cols: list[str],
) -> pd.DataFrame:
    key = (dataset, seed)
    if key not in SIMILARITY_CACHE:
        split = make_split(frame, "scaffold", seed)
        train_smiles = frame.iloc[split.train]["smiles"].tolist()
        sims = max_train_similarity(train_smiles, frame["smiles"].tolist())
        SIMILARITY_CACHE[key] = pd.Series(sims, index=frame["smiles"].tolist())
    out = table.copy()
    pred_matrix = out[pred_cols].to_numpy(dtype=np.float64)
    out["ensemble_mean"] = pred_matrix.mean(axis=1)
    out["ensemble_std"] = pred_matrix.std(axis=1)
    out["ensemble_range"] = pred_matrix.max(axis=1) - pred_matrix.min(axis=1)
    out["max_train_tanimoto"] = out["smiles"].map(SIMILARITY_CACHE[key]).fillna(0.0).astype(float)
    out["scaffold_distance"] = 1.0 - out["max_train_tanimoto"]
    return out


def build_meta_train_table(
    dataset: str,
    seed: int,
    members: list[tuple[str, str]],
    task_type: str,
    full_frame: pd.DataFrame,
    current_test_smiles: set[str],
) -> tuple[pd.DataFrame, list[str], str]:
    try:
        valid, pred_cols = load_member_predictions(dataset, seed, members, task_type, "valid")
        valid = add_applicability_features(dataset, valid, full_frame, seed, pred_cols)
        if len(valid) >= max(8, len(pred_cols) + 3):
            return valid, pred_cols, "validation"
    except FileNotFoundError:
        pred_cols = []

    parts: list[pd.DataFrame] = []
    for other_seed in SEEDS:
        if other_seed == seed:
            continue
        try:
            heldout, pred_cols = load_member_predictions(dataset, other_seed, members, task_type, "test")
        except FileNotFoundError:
            continue
        heldout = heldout[~heldout["smiles"].isin(current_test_smiles)].copy()
        if heldout.empty:
            continue
        parts.append(add_applicability_features(dataset, heldout, full_frame, other_seed, pred_cols))
    if not parts:
        raise FileNotFoundError(f"No validation or cross-seed predictions for {dataset} seed={seed}")
    return pd.concat(parts, ignore_index=True), pred_cols, "cross_seed_heldout"


def feature_columns(pred_cols: list[str]) -> list[str]:
    return pred_cols + [
        "ensemble_mean",
        "ensemble_std",
        "ensemble_range",
        "max_train_tanimoto",
        "scaffold_distance",
    ]


def fit_stacker(task_type: str, train: pd.DataFrame, pred_cols: list[str]):
    cols = feature_columns(pred_cols)
    x = train[cols].to_numpy(dtype=np.float64)
    y = train["y_true"].to_numpy(dtype=np.float64)
    if task_type == "regression":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                ("model", RidgeCV(alphas=np.logspace(-4, 4, 17))),
            ]
        ).fit(x, y)
    if len(np.unique(y.astype(int))) < 2:
        return ConstantProbability(float(np.mean(y)))
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced",
                    random_state=61453,
                ),
            ),
        ]
    ).fit(x, y.astype(int))


def predict_stacker(model, task_type: str, table: pd.DataFrame, pred_cols: list[str]) -> np.ndarray:
    x = table[feature_columns(pred_cols)].to_numpy(dtype=np.float64)
    if task_type == "classification":
        return model.predict_proba(x)[:, 1]
    return model.predict(x)


def fit_error_models(task_type: str, train: pd.DataFrame, pred_cols: list[str]) -> list[RandomForestRegressor]:
    cols = feature_columns(pred_cols)
    x = train[cols].to_numpy(dtype=np.float64)
    y = train["y_true"].to_numpy(dtype=np.float64)
    models: list[RandomForestRegressor] = []
    for i, col in enumerate(pred_cols):
        pred = train[col].to_numpy(dtype=np.float64)
        if task_type == "classification":
            target = np.abs(y - np.clip(pred, 1e-7, 1.0 - 1e-7))
        else:
            target = np.abs(y - pred)
        model = RandomForestRegressor(
            n_estimators=80,
            min_samples_leaf=max(2, min(10, len(train) // 40)),
            random_state=1009 + i,
            n_jobs=-1,
        )
        model.fit(x, target)
        models.append(model)
    return models


def adaptive_predict(
    task_type: str,
    train: pd.DataFrame,
    test: pd.DataFrame,
    pred_cols: list[str],
) -> tuple[np.ndarray, pd.DataFrame]:
    error_models = fit_error_models(task_type, train, pred_cols)
    cols = feature_columns(pred_cols)
    x_test = test[cols].to_numpy(dtype=np.float64)
    expected_errors = np.column_stack(
        [np.clip(model.predict(x_test), 1e-6, None) for model in error_models]
    )
    raw_weights = 1.0 / expected_errors
    weights = raw_weights / raw_weights.sum(axis=1, keepdims=True)
    preds = test[pred_cols].to_numpy(dtype=np.float64)
    y_pred = (weights * preds).sum(axis=1)

    if task_type == "classification" and len(np.unique(train["y_true"].astype(int))) == 2:
        train_errors = np.column_stack(
            [
                np.clip(model.predict(train[cols].to_numpy(dtype=np.float64)), 1e-6, None)
                for model in error_models
            ]
        )
        train_weights = (1.0 / train_errors)
        train_weights = train_weights / train_weights.sum(axis=1, keepdims=True)
        train_raw = (train_weights * train[pred_cols].to_numpy(dtype=np.float64)).sum(axis=1)
        calibrator = LogisticRegression(max_iter=2000, random_state=2718)
        calibrator.fit(train_raw.reshape(-1, 1), train["y_true"].astype(int).to_numpy())
        y_pred = calibrator.predict_proba(y_pred.reshape(-1, 1))[:, 1]

    diagnostics = test[["smiles", "max_train_tanimoto", "scaffold_distance", "ensemble_std"]].copy()
    for col, values in zip(pred_cols, weights.T):
        diagnostics[f"weight_{col.replace('pred_', '')}"] = values
    for col, values in zip(pred_cols, expected_errors.T):
        diagnostics[f"expected_error_{col.replace('pred_', '')}"] = values
    return y_pred, diagnostics


def summarize(metrics: pd.DataFrame, output_dir: Path) -> None:
    metrics.to_csv(output_dir / "metrics_raw.csv", index=False)
    id_cols = {
        "dataset",
        "model",
        "task_type",
        "seed",
        "split",
        "meta_train_source",
        "meta_train_rows",
    }
    metric_cols = [
        col for col in metrics.columns if col not in id_cols and pd.api.types.is_numeric_dtype(metrics[col])
    ]
    summary = (
        metrics.groupby(["dataset", "model", "task_type"], dropna=False)[metric_cols]
        .agg(["mean", "std"])
        .reset_index()
    )
    summary.to_csv(output_dir / "metrics_summary.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build validation stacking and scaffold-aware adaptive ensembles from saved predictions."
    )
    parser.add_argument("--output-dir", default=str(ROOT / "reports" / "adaptive_stacking"))
    parser.add_argument("--datasets", nargs="*", default=list(DATASETS))
    parser.add_argument("--seeds", nargs="*", type=int, default=SEEDS)
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    for dataset in args.datasets:
        frame, spec = load_dataset(dataset, data_dir=ROOT / "data")
        for seed in args.seeds:
            for family, members in MEMBER_SETS.items():
                try:
                    test, pred_cols = load_member_predictions(dataset, seed, members, spec.task_type, "test")
                except FileNotFoundError:
                    continue
                current_test_smiles = set(test["smiles"].tolist())
                test = add_applicability_features(dataset, test, frame, seed, pred_cols)
                meta_train, pred_cols, source = build_meta_train_table(
                    dataset,
                    seed,
                    members,
                    spec.task_type,
                    frame,
                    current_test_smiles,
                )
                for method in ("stack", "adaptive"):
                    model_name = f"{method}_{family}"
                    pred_path = output_dir / f"{dataset}_{model_name}_seed{seed}_predictions.csv"
                    diag_path = output_dir / f"{dataset}_{model_name}_seed{seed}_weights.csv"
                    if args.resume and pred_path.exists() and diag_path.exists():
                        pred = pd.read_csv(pred_path)
                        metric_values = compute_metrics(
                            spec.task_type,
                            pred["y_true"].to_numpy(),
                            pred["y_pred"].to_numpy(),
                        )
                        rows.append(
                            {
                                "dataset": dataset,
                                "model": model_name,
                                "seed": seed,
                                "split": "scaffold",
                                "task_type": spec.task_type,
                                "meta_train_source": str(pred.get("meta_train_source", source).iloc[0])
                                if "meta_train_source" in pred
                                else source,
                                "meta_train_rows": len(meta_train),
                                **metric_values,
                            }
                        )
                        continue
                    if method == "stack":
                        stacker = fit_stacker(spec.task_type, meta_train, pred_cols)
                        y_pred = predict_stacker(stacker, spec.task_type, test, pred_cols)
                        diagnostics = test[
                            ["smiles", "max_train_tanimoto", "scaffold_distance", "ensemble_std"]
                        ].copy()
                    else:
                        y_pred, diagnostics = adaptive_predict(spec.task_type, meta_train, test, pred_cols)

                    pred = pd.DataFrame(
                        {
                            "smiles": test["smiles"].to_numpy(),
                            "y_true": test["y_true"].to_numpy(),
                            "y_pred": y_pred,
                            "max_train_tanimoto": test["max_train_tanimoto"].to_numpy(),
                            "ensemble_std": test["ensemble_std"].to_numpy(),
                            "meta_train_source": source,
                        }
                    )
                    pred.to_csv(pred_path, index=False)
                    diagnostics.to_csv(diag_path, index=False)
                    metric_values = compute_metrics(
                        spec.task_type,
                        pred["y_true"].to_numpy(),
                        pred["y_pred"].to_numpy(),
                    )
                    rows.append(
                        {
                            "dataset": dataset,
                            "model": model_name,
                            "seed": seed,
                            "split": "scaffold",
                            "task_type": spec.task_type,
                            "meta_train_source": source,
                            "meta_train_rows": len(meta_train),
                            **metric_values,
                        }
                    )

    metrics = pd.DataFrame(rows)
    summarize(metrics, output_dir)
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
