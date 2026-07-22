from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from huggingface_hub import hf_hub_download
from scipy.stats import pearsonr, spearmanr
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.features import mol_from_smiles, multi_fingerprint_vector, scaffold_from_smiles


REPO_ID = "openadmet/openadmet-expansionrx-challenge-data"
ENDPOINT_EXCLUDE = {"Molecule Name", "SMILES"}
OUT_DIR = ROOT / "reports" / "openadmet_expansionrx_fast_benchmark"
CACHE_DIR = ROOT / "data" / "processed" / "openadmet_expansionrx"


def canonical_smiles(smiles: str) -> str | None:
    mol = mol_from_smiles(smiles)
    if mol is None:
        return None
    from rdkit import Chem

    return Chem.MolToSmiles(mol, canonical=True)


def load_openadmet() -> tuple[pd.DataFrame, pd.DataFrame]:
    train_path = hf_hub_download(repo_id=REPO_ID, repo_type="dataset", filename="expansion_data_train.csv")
    test_path = hf_hub_download(repo_id=REPO_ID, repo_type="dataset", filename="expansion_data_test.csv")
    train = pd.read_csv(train_path)
    test = pd.read_csv(test_path)
    for frame in [train, test]:
        frame["canonical_smiles"] = frame["SMILES"].map(canonical_smiles)
        for column in frame.columns:
            if column not in ENDPOINT_EXCLUDE and column != "canonical_smiles":
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
    train = train[train["canonical_smiles"].notna()].reset_index(drop=True)
    test = test[test["canonical_smiles"].notna()].reset_index(drop=True)
    return train, test


def build_feature_cache(train: pd.DataFrame, test: pd.DataFrame, force: bool = False) -> tuple[np.ndarray, np.ndarray]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / "multifp_features.npz"
    meta_path = CACHE_DIR / "feature_metadata.json"
    all_smiles = train["canonical_smiles"].tolist() + test["canonical_smiles"].tolist()
    if cache_path.exists() and meta_path.exists() and not force:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("n_train") == len(train) and meta.get("n_test") == len(test):
            data = np.load(cache_path)
            return data["x_train"], data["x_test"]
    rows = []
    for i, smiles in enumerate(all_smiles, start=1):
        if i % 500 == 0:
            print(f"feature_cache progress {i}/{len(all_smiles)}", flush=True)
        rows.append(multi_fingerprint_vector(smiles))
    x_all = np.vstack(rows).astype(np.float32)
    x_train = x_all[: len(train)]
    x_test = x_all[len(train) :]
    np.savez_compressed(cache_path, x_train=x_train, x_test=x_test)
    meta_path.write_text(
        json.dumps(
            {
                "repo_id": REPO_ID,
                "n_train": len(train),
                "n_test": len(test),
                "n_features": int(x_all.shape[1]),
                "feature": "multi_fingerprint_vector",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return x_train, x_test


def scaffold_train_valid_indices(frame: pd.DataFrame, seed: int, frac_train: float = 0.8) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    scaffold_to_indices: dict[str, list[int]] = {}
    for idx, smiles in enumerate(frame["canonical_smiles"].tolist()):
        scaffold_to_indices.setdefault(scaffold_from_smiles(smiles), []).append(idx)
    groups = list(scaffold_to_indices.values())
    rng.shuffle(groups)
    groups = sorted(groups, key=lambda group: (-len(group), float(rng.random())))
    n_train_target = int(frac_train * len(frame))
    train_idx: list[int] = []
    valid_idx: list[int] = []
    for group in groups:
        if len(train_idx) + len(group) <= n_train_target:
            train_idx.extend(group)
        else:
            valid_idx.extend(group)
    if not valid_idx:
        indices = np.arange(len(frame))
        rng.shuffle(indices)
        cut = max(1, int(frac_train * len(indices)))
        train_idx = indices[:cut].tolist()
        valid_idx = indices[cut:].tolist()
    return np.asarray(sorted(train_idx), dtype=int), np.asarray(sorted(valid_idx), dtype=int)


def target_transform_available(y: np.ndarray, name: str) -> bool:
    if name == "identity":
        return True
    if name == "log1p":
        return bool(np.nanmin(y) >= 0)
    raise ValueError(name)


def transform_y(y: np.ndarray, name: str) -> np.ndarray:
    if name == "identity":
        return y.astype(float)
    if name == "log1p":
        return np.log1p(np.clip(y.astype(float), 0.0, None))
    raise ValueError(name)


def inverse_transform_y(y: np.ndarray, name: str) -> np.ndarray:
    if name == "identity":
        return y.astype(float)
    if name == "log1p":
        return np.expm1(y.astype(float))
    raise ValueError(name)


def make_regressor(model_name: str, seed: int, n_estimators: int):
    if model_name == "rf_multifp":
        return RandomForestRegressor(
            n_estimators=n_estimators,
            random_state=seed,
            n_jobs=-1,
            max_features="sqrt",
            min_samples_leaf=1,
        )
    if model_name == "extratrees_multifp":
        return ExtraTreesRegressor(
            n_estimators=n_estimators,
            random_state=seed,
            n_jobs=-1,
            max_features="sqrt",
            min_samples_leaf=1,
        )
    if model_name == "lgbm_multifp":
        try:
            from lightgbm import LGBMRegressor
        except ImportError as exc:  # pragma: no cover
            raise ImportError("Install lightgbm to run lgbm_multifp.") from exc
        return LGBMRegressor(
            n_estimators=n_estimators,
            learning_rate=0.03,
            num_leaves=31,
            subsample=0.9,
            colsample_bytree=0.8,
            reg_lambda=2.0,
            random_state=seed,
            n_jobs=-1,
            verbosity=-1,
        )
    raise ValueError(model_name)


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mask = np.isfinite(y_true) & np.isfinite(y_pred)
    y_true = y_true[mask]
    y_pred = y_pred[mask]
    if len(y_true) == 0:
        return {"rmse": np.nan, "mae": np.nan, "r2": np.nan, "spearman": np.nan, "pearson": np.nan}
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    r2 = float(r2_score(y_true, y_pred)) if len(y_true) > 1 else np.nan
    spearman = float(spearmanr(y_true, y_pred).correlation) if len(y_true) > 2 else np.nan
    pearson = float(pearsonr(y_true, y_pred).statistic) if len(y_true) > 2 else np.nan
    return {"rmse": rmse, "mae": mae, "r2": r2, "spearman": spearman, "pearson": pearson}


def choose_primary(metrics: dict[str, float], primary_metric: str) -> float:
    value = metrics.get(primary_metric, np.nan)
    return float(value)


def fit_base_candidate(
    model_name: str,
    transform: str,
    x_fit: np.ndarray,
    y_fit: np.ndarray,
    x_valid: np.ndarray,
    x_test: np.ndarray,
    seed: int,
    n_estimators: int,
) -> tuple[np.ndarray, np.ndarray]:
    model = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("model", make_regressor(model_name, seed, n_estimators)),
        ]
    )
    model.fit(x_fit, transform_y(y_fit, transform))
    valid_pred = inverse_transform_y(model.predict(x_valid), transform)
    test_pred = inverse_transform_y(model.predict(x_test), transform)
    return valid_pred, test_pred


def run_endpoint(
    endpoint: str,
    train: pd.DataFrame,
    test: pd.DataFrame,
    x_train_all: np.ndarray,
    x_test_all: np.ndarray,
    seeds: list[int],
    models: list[str],
    transforms: list[str],
    n_estimators: int,
    primary_metric: str,
) -> tuple[list[dict[str, object]], list[pd.DataFrame], list[dict[str, object]]]:
    metric_rows: list[dict[str, object]] = []
    prediction_frames: list[pd.DataFrame] = []
    choice_rows: list[dict[str, object]] = []

    train_mask = train[endpoint].notna().to_numpy()
    test_mask = test[endpoint].notna().to_numpy()
    endpoint_train = train.loc[train_mask].reset_index(drop=True)
    endpoint_test = test.loc[test_mask].reset_index(drop=True)
    x_train = x_train_all[train_mask]
    x_test = x_test_all[test_mask]
    y_train_all = endpoint_train[endpoint].to_numpy(dtype=float)
    y_test = endpoint_test[endpoint].to_numpy(dtype=float)

    if len(endpoint_train) < 50 or len(endpoint_test) < 20:
        return metric_rows, prediction_frames, choice_rows

    for seed in seeds:
        fit_idx, valid_idx = scaffold_train_valid_indices(endpoint_train, seed=seed, frac_train=0.8)
        x_fit = x_train[fit_idx]
        y_fit = y_train_all[fit_idx]
        x_valid = x_train[valid_idx]
        y_valid = y_train_all[valid_idx]

        base_valid: dict[str, np.ndarray] = {}
        base_test: dict[str, np.ndarray] = {}
        for model_name in models:
            for transform in transforms:
                if not target_transform_available(y_fit, transform):
                    continue
                candidate = f"{model_name}_{transform}"
                print(f"run endpoint={endpoint} seed={seed} candidate={candidate}", flush=True)
                valid_pred, test_pred = fit_base_candidate(
                    model_name=model_name,
                    transform=transform,
                    x_fit=x_fit,
                    y_fit=y_fit,
                    x_valid=x_valid,
                    x_test=x_test,
                    seed=seed,
                    n_estimators=n_estimators,
                )
                base_valid[candidate] = valid_pred
                base_test[candidate] = test_pred
                valid_metrics = regression_metrics(y_valid, valid_pred)
                test_metrics = regression_metrics(y_test, test_pred)
                metric_rows.append(
                    {
                        "endpoint": endpoint,
                        "seed": seed,
                        "strategy": "base",
                        "candidate": candidate,
                        "model": model_name,
                        "target_transform": transform,
                        "selected": False,
                        "n_train_fit": len(fit_idx),
                        "n_valid": len(valid_idx),
                        "n_test": len(y_test),
                        **{f"valid_{k}": v for k, v in valid_metrics.items()},
                        **{f"test_{k}": v for k, v in test_metrics.items()},
                    }
                )

        if not base_valid:
            continue

        candidate_names = list(base_valid)
        valid_scores = {
            name: choose_primary(regression_metrics(y_valid, base_valid[name]), primary_metric)
            for name in candidate_names
        }
        best_name = min(valid_scores, key=valid_scores.get)
        strategy_valid: dict[str, np.ndarray] = {"best_single": base_valid[best_name]}
        strategy_test: dict[str, np.ndarray] = {"best_single": base_test[best_name]}
        strategy_detail: dict[str, str] = {"best_single": best_name}

        valid_matrix = np.column_stack([base_valid[name] for name in candidate_names])
        test_matrix = np.column_stack([base_test[name] for name in candidate_names])
        strategy_valid["consensus_mean"] = np.mean(valid_matrix, axis=1)
        strategy_test["consensus_mean"] = np.mean(test_matrix, axis=1)
        strategy_detail["consensus_mean"] = "|".join(candidate_names)

        ridge = RidgeCV(alphas=np.logspace(-4, 3, 16))
        ridge.fit(valid_matrix, y_valid)
        strategy_valid["stack_ridge"] = ridge.predict(valid_matrix)
        strategy_test["stack_ridge"] = ridge.predict(test_matrix)
        strategy_detail["stack_ridge"] = "|".join(candidate_names)

        strategy_scores = {
            name: choose_primary(regression_metrics(y_valid, pred), primary_metric)
            for name, pred in strategy_valid.items()
        }
        selected_strategy = min(strategy_scores, key=strategy_scores.get)
        choice_rows.append(
            {
                "endpoint": endpoint,
                "seed": seed,
                "selected_strategy": selected_strategy,
                "selected_detail": strategy_detail[selected_strategy],
                "valid_primary_metric": primary_metric,
                "valid_primary_value": strategy_scores[selected_strategy],
                "n_base_candidates": len(candidate_names),
            }
        )

        for strategy, valid_pred in strategy_valid.items():
            test_pred = strategy_test[strategy]
            valid_metrics = regression_metrics(y_valid, valid_pred)
            test_metrics = regression_metrics(y_test, test_pred)
            is_selected = strategy == selected_strategy
            metric_rows.append(
                {
                    "endpoint": endpoint,
                    "seed": seed,
                    "strategy": strategy,
                    "candidate": strategy_detail[strategy],
                    "model": strategy,
                    "target_transform": "",
                    "selected": is_selected,
                    "n_train_fit": len(fit_idx),
                    "n_valid": len(valid_idx),
                    "n_test": len(y_test),
                    **{f"valid_{k}": v for k, v in valid_metrics.items()},
                    **{f"test_{k}": v for k, v in test_metrics.items()},
                }
            )
            if is_selected:
                prediction_frames.append(
                    pd.DataFrame(
                        {
                            "endpoint": endpoint,
                            "seed": seed,
                            "molecule_name": endpoint_test["Molecule Name"].to_numpy(),
                            "smiles": endpoint_test["canonical_smiles"].to_numpy(),
                            "y_true": y_test,
                            "y_pred": test_pred,
                            "selected_strategy": selected_strategy,
                            "selected_detail": strategy_detail[strategy],
                        }
                    )
                )

    return metric_rows, prediction_frames, choice_rows


def summarize_metrics(metrics: pd.DataFrame) -> pd.DataFrame:
    metric_cols = [column for column in metrics.columns if column.startswith("test_") or column.startswith("valid_")]
    selected = metrics[metrics["selected"].eq(True)].copy()
    summary = (
        selected.groupby(["endpoint", "strategy"], dropna=False)
        .agg(
            n_seeds=("seed", "nunique"),
            n_test=("n_test", "mean"),
            **{f"{col}_mean": (col, "mean") for col in metric_cols},
            **{f"{col}_std": (col, "std") for col in metric_cols},
        )
        .reset_index()
    )
    return summary


def build_readme(summary: pd.DataFrame, choices: pd.DataFrame, args: argparse.Namespace) -> None:
    selected_counts = choices.groupby(["endpoint", "selected_strategy"]).size().reset_index(name="n")
    lines = [
        "# OpenADMET-ExpansionRx fast external appendix benchmark",
        "",
        f"Dataset: `{REPO_ID}`",
        "",
        "Protocol:",
        "",
        "- Use released train/test files.",
        "- For each endpoint, filter non-missing labels.",
        "- Split released train labels into fit/validation by scaffold.",
        "- Train fast multi-fingerprint base models on fit split.",
        "- Select best-single, mean consensus, or ridge stacking using validation MAE only.",
        "- Use released test labels only for final evaluation.",
        "",
        f"Seeds: {args.seeds}",
        f"Base models: {args.models}",
        f"Target transforms: {args.transforms}",
        f"Tree estimators: {args.n_estimators}",
        "",
        "Selected-strategy counts:",
        "",
        selected_counts.to_markdown(index=False),
        "",
        "Selected-strategy test summary:",
        "",
        summary[
            [
                "endpoint",
                "strategy",
                "n_seeds",
                "n_test",
                "test_mae_mean",
                "test_mae_std",
                "test_rmse_mean",
                "test_rmse_std",
                "test_spearman_mean",
                "test_spearman_std",
                "test_pearson_mean",
                "test_pearson_std",
            ]
        ].to_markdown(index=False),
        "",
        "Manuscript use: appendix external benchmark. Do not mix directly into main MoleculeNet/TDC tables unless the text clearly labels it as a released real-project OpenADMET external split.",
        "",
    ]
    (OUT_DIR / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run fast OpenADMET-ExpansionRx appendix benchmark.")
    parser.add_argument("--seeds", nargs="*", type=int, default=[13, 17, 23])
    parser.add_argument("--models", nargs="*", default=["rf_multifp", "extratrees_multifp", "lgbm_multifp"])
    parser.add_argument("--transforms", nargs="*", default=["identity", "log1p"])
    parser.add_argument("--n-estimators", type=int, default=250)
    parser.add_argument("--primary-metric", default="mae", choices=["mae", "rmse"])
    parser.add_argument("--force-features", action="store_true")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    train, test = load_openadmet()
    x_train, x_test = build_feature_cache(train, test, force=args.force_features)
    endpoints = [column for column in train.columns if column not in ENDPOINT_EXCLUDE and column != "canonical_smiles"]

    all_metrics: list[dict[str, object]] = []
    all_predictions: list[pd.DataFrame] = []
    all_choices: list[dict[str, object]] = []
    for endpoint in endpoints:
        if train[endpoint].notna().sum() < 100 or test[endpoint].notna().sum() < 50:
            print(f"skip endpoint={endpoint} insufficient labels", flush=True)
            continue
        metric_rows, prediction_frames, choice_rows = run_endpoint(
            endpoint=endpoint,
            train=train,
            test=test,
            x_train_all=x_train,
            x_test_all=x_test,
            seeds=args.seeds,
            models=args.models,
            transforms=args.transforms,
            n_estimators=args.n_estimators,
            primary_metric=args.primary_metric,
        )
        all_metrics.extend(metric_rows)
        all_predictions.extend(prediction_frames)
        all_choices.extend(choice_rows)
        pd.DataFrame(all_metrics).to_csv(OUT_DIR / "metrics_raw.csv", index=False)
        if all_choices:
            pd.DataFrame(all_choices).to_csv(OUT_DIR / "selector_choices.csv", index=False)

    metrics = pd.DataFrame(all_metrics)
    predictions = pd.concat(all_predictions, ignore_index=True) if all_predictions else pd.DataFrame()
    choices = pd.DataFrame(all_choices)
    summary = summarize_metrics(metrics) if not metrics.empty else pd.DataFrame()

    metrics.to_csv(OUT_DIR / "metrics_raw.csv", index=False)
    predictions.to_csv(OUT_DIR / "selected_predictions.csv", index=False)
    choices.to_csv(OUT_DIR / "selector_choices.csv", index=False)
    summary.to_csv(OUT_DIR / "selected_metrics_summary.csv", index=False)
    if not summary.empty and not choices.empty:
        build_readme(summary, choices, args)
    print(f"Wrote OpenADMET fast benchmark to {OUT_DIR}")


if __name__ == "__main__":
    main()
