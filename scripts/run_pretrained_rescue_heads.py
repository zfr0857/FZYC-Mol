from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRegressor
from rdkit import RDLogger
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import DATASETS, load_dataset
from fzyc_mol.evaluate import compute_metrics
from fzyc_mol.features import descriptor_vector
from fzyc_mol.splits import make_split


RDLogger.DisableLog("rdApp.*")

OUT_DIR = ROOT / "reports" / "pretrained_rescue_heads"
TABLE_DIR = ROOT / "reports" / "manuscript_tables"
TABLE18_PATH = TABLE_DIR / "table18_pretrained_rescue_heads.csv"
DEFAULT_ENCODERS = [
    "DeepChem/ChemBERTa-77M-MTR",
    "DeepChem/ChemBERTa-77M-MLM",
    "ibm/MoLFormer-XL-both-10pct",
]
DEFAULT_DATASETS = ["esol", "freesolv", "lipo", "bbbp", "bace", "clintox"]


def safe_model_id(model_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", model_name).strip("_")


def load_embedding_matrix(path: Path, smiles: list[str]) -> np.ndarray:
    if not path.exists():
        raise FileNotFoundError(path)
    payload = np.load(path, allow_pickle=True)
    saved_smiles = [str(item) for item in payload["smiles"].tolist()]
    embedding = payload["embedding"].astype(np.float32)
    lookup = {smi: embedding[i] for i, smi in enumerate(saved_smiles)}
    missing = [smi for smi in smiles if smi not in lookup]
    if missing:
        raise KeyError(f"Missing {len(missing)} embeddings in {path}. Example: {missing[:3]}")
    return np.vstack([lookup[smi] for smi in smiles]).astype(np.float32)


def descriptor_matrix(smiles: list[str]) -> np.ndarray:
    return np.vstack([descriptor_vector(smi, include_3d=False) for smi in smiles]).astype(np.float32)


def feature_matrix(embedding_dir: Path, dataset: str, smiles: list[str], include_desc: bool) -> np.ndarray:
    emb = load_embedding_matrix(embedding_dir / f"{dataset}.npz", smiles)
    if not include_desc:
        return np.nan_to_num(emb, copy=False)
    desc = descriptor_matrix(smiles)
    return np.nan_to_num(np.hstack([emb, desc]).astype(np.float32), copy=False)


def make_estimator(model: str, task_type: str, seed: int, n_estimators: int):
    if model == "extratrees":
        if task_type == "regression":
            estimator = ExtraTreesRegressor(
                n_estimators=n_estimators,
                max_features="sqrt",
                min_samples_leaf=1,
                random_state=seed,
                n_jobs=-1,
            )
        else:
            estimator = ExtraTreesClassifier(
                n_estimators=n_estimators,
                max_features="sqrt",
                min_samples_leaf=1,
                class_weight="balanced",
                random_state=seed,
                n_jobs=-1,
            )
        return Pipeline([("imputer", SimpleImputer(strategy="median")), ("model", estimator)])
    if model == "lgbm":
        if task_type == "regression":
            estimator = LGBMRegressor(
                n_estimators=n_estimators,
                learning_rate=0.035,
                num_leaves=31,
                subsample=0.9,
                colsample_bytree=0.85,
                reg_lambda=2.0,
                random_state=seed,
                n_jobs=-1,
                verbose=-1,
            )
        else:
            estimator = LGBMClassifier(
                n_estimators=n_estimators,
                learning_rate=0.035,
                num_leaves=31,
                subsample=0.9,
                colsample_bytree=0.85,
                reg_lambda=2.0,
                class_weight="balanced",
                random_state=seed,
                n_jobs=-1,
                verbose=-1,
            )
        return Pipeline([("imputer", SimpleImputer(strategy="median")), ("model", estimator)])
    raise ValueError(f"Unknown rescue model: {model}")


def predict(estimator, task_type: str, x: np.ndarray) -> np.ndarray:
    if task_type == "classification" and hasattr(estimator[-1], "predict_proba"):
        return estimator.predict_proba(x)[:, 1]
    return estimator.predict(x)


def primary_value(task_type: str, metrics: dict[str, float]) -> tuple[float, str, str]:
    if task_type == "regression":
        return float(metrics["rmse"]), "rmse", "lower"
    return float(metrics["roc_auc"]), "roc_auc", "higher"


def run_one(
    dataset: str,
    encoder_name: str,
    model: str,
    seed: int,
    n_estimators: int,
    include_desc: bool,
    embedding_root: Path,
    output_dir: Path,
    resume: bool,
) -> dict[str, object]:
    frame, spec = load_dataset(dataset, data_dir=ROOT / "data")
    encoder_id = safe_model_id(encoder_name)
    feature_tag = "emb_desc" if include_desc else "emb"
    model_id = f"{encoder_id}_{feature_tag}_{model}_rescue"
    pred_path = output_dir / f"{dataset}_{model_id}_seed{seed}_predictions.csv"
    valid_path = output_dir / f"{dataset}_{model_id}_seed{seed}_valid_predictions.csv"
    if resume and pred_path.exists() and valid_path.exists():
        valid_frame = pd.read_csv(valid_path)
        pred_frame = pd.read_csv(pred_path)
        valid_metrics = compute_metrics(spec.task_type, valid_frame["y_true"].to_numpy(), valid_frame["y_pred"].to_numpy())
        test_metrics = compute_metrics(spec.task_type, pred_frame["y_true"].to_numpy(), pred_frame["y_pred"].to_numpy())
        valid_primary, primary_metric, direction = primary_value(spec.task_type, valid_metrics)
        test_primary, _, _ = primary_value(spec.task_type, test_metrics)
        return {
            "dataset": dataset,
            "task_type": spec.task_type,
            "encoder": encoder_id,
            "model": model_id,
            "base_model": model,
            "feature_tag": feature_tag,
            "seed": seed,
            "split": "scaffold",
            "primary_metric": primary_metric,
            "primary_direction": direction,
            "validation_primary": valid_primary,
            "primary_value": test_primary,
            "fit_seconds": np.nan,
            **{f"valid_{k}": v for k, v in valid_metrics.items()},
            **{f"test_{k}": v for k, v in test_metrics.items()},
        }

    smiles = frame["smiles"].tolist()
    x = feature_matrix(embedding_root / encoder_id, dataset, smiles, include_desc=include_desc)
    y = frame["y"].to_numpy()
    split = make_split(frame, "scaffold", seed)
    estimator = make_estimator(model, spec.task_type, seed, n_estimators)
    start = time.perf_counter()
    estimator.fit(x[split.train], y[split.train])
    fit_seconds = time.perf_counter() - start
    valid_pred = predict(estimator, spec.task_type, x[split.valid])
    test_pred = predict(estimator, spec.task_type, x[split.test])
    valid_frame = pd.DataFrame(
        {
            "smiles": frame.iloc[split.valid]["smiles"].to_numpy(),
            "y_true": y[split.valid],
            "y_pred": valid_pred,
        }
    )
    pred_frame = pd.DataFrame(
        {
            "smiles": frame.iloc[split.test]["smiles"].to_numpy(),
            "y_true": y[split.test],
            "y_pred": test_pred,
        }
    )
    valid_frame.to_csv(valid_path, index=False)
    pred_frame.to_csv(pred_path, index=False)
    valid_metrics = compute_metrics(spec.task_type, y[split.valid], valid_pred)
    test_metrics = compute_metrics(spec.task_type, y[split.test], test_pred)
    valid_primary, primary_metric, direction = primary_value(spec.task_type, valid_metrics)
    test_primary, _, _ = primary_value(spec.task_type, test_metrics)
    return {
        "dataset": dataset,
        "task_type": spec.task_type,
        "encoder": encoder_id,
        "model": model_id,
        "base_model": model,
        "feature_tag": feature_tag,
        "seed": seed,
        "split": "scaffold",
        "primary_metric": primary_metric,
        "primary_direction": direction,
        "validation_primary": valid_primary,
        "primary_value": test_primary,
        "fit_seconds": fit_seconds,
        **{f"valid_{k}": v for k, v in valid_metrics.items()},
        **{f"test_{k}": v for k, v in test_metrics.items()},
    }


def summarize(raw: pd.DataFrame, output_dir: Path) -> pd.DataFrame:
    raw.to_csv(output_dir / "metrics_raw.csv", index=False)
    candidate_rows = []
    selected_rows = []
    for dataset, group in raw.groupby("dataset", dropna=False):
        direction = str(group["primary_direction"].iloc[0])
        for model, candidate in group.groupby("model", dropna=False):
            if candidate["seed"].nunique() < 2:
                continue
            candidate_rows.append(
                {
                    "dataset": dataset,
                    "task_type": candidate["task_type"].iloc[0],
                    "model": model,
                    "encoder": candidate["encoder"].iloc[0],
                    "base_model": candidate["base_model"].iloc[0],
                    "feature_tag": candidate["feature_tag"].iloc[0],
                    "primary_metric": candidate["primary_metric"].iloc[0],
                    "primary_direction": direction,
                    "n_seeds": int(candidate["seed"].nunique()),
                    "validation_primary_mean": float(candidate["validation_primary"].mean()),
                    "validation_primary_std": float(candidate["validation_primary"].std()),
                    "primary_mean": float(candidate["primary_value"].mean()),
                    "primary_std": float(candidate["primary_value"].std()),
                    "fit_seconds_mean": float(candidate["fit_seconds"].mean()),
                }
            )
        candidates = pd.DataFrame([row for row in candidate_rows if row["dataset"] == dataset])
        if candidates.empty:
            continue
        ascending = direction == "lower"
        selected = candidates.sort_values("validation_primary_mean", ascending=ascending).iloc[0]
        selected_rows.append(selected.to_dict())
    candidate_summary = pd.DataFrame(candidate_rows).sort_values(["dataset", "validation_primary_mean"])
    selected_summary = pd.DataFrame(selected_rows).sort_values("dataset")
    candidate_summary.to_csv(output_dir / "candidate_summary.csv", index=False)
    selected_summary.to_csv(output_dir / "selected_summary.csv", index=False)
    return selected_summary


def compare_to_frozen(selected: pd.DataFrame) -> pd.DataFrame:
    ranking_path = ROOT / "reports" / "combined_primary_ranking.csv"
    ranking = pd.read_csv(ranking_path)
    frozen = ranking[ranking["source"].astype(str).str.contains("pretrained", case=False, na=False)].copy()
    rows = []
    for dataset, group in frozen.groupby("dataset", dropna=False):
        if dataset not in set(selected["dataset"]):
            continue
        direction = str(group["direction"].iloc[0])
        ascending = direction == "lower"
        best_frozen = group.sort_values("value", ascending=ascending).iloc[0]
        rescue = selected[selected["dataset"].eq(dataset)].iloc[0]
        delta = (
            float(best_frozen["value"]) - float(rescue["primary_mean"])
            if direction == "lower"
            else float(rescue["primary_mean"]) - float(best_frozen["value"])
        )
        rows.append(
            {
                "dataset": dataset,
                "task_type": rescue["task_type"],
                "primary_metric": rescue["primary_metric"],
                "primary_direction": direction,
                "best_frozen_linear_model": best_frozen["model"],
                "best_frozen_linear_value": best_frozen["value"],
                "rescue_model": rescue["model"],
                "rescue_value": rescue["primary_mean"],
                "rescue_std": rescue["primary_std"],
                "delta_vs_best_frozen_linear": delta,
                "rescue_better": delta > 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values("dataset")


def write_report(output_dir: Path, comparison: pd.DataFrame, selected: pd.DataFrame) -> None:
    improved = comparison[comparison["rescue_better"]]
    lines = [
        "# Pretrained Rescue Heads",
        "",
        "Date: 2026-05-31",
        "",
        "This lightweight run targets the weakest standalone module family: frozen pretrained linear heads.",
        "It keeps the pretrained encoders frozen, concatenates low-cost RDKit descriptors, and trains",
        "ExtraTrees/LightGBM rescue heads selected by validation primary metric.",
        "",
        f"Improved over the best existing frozen-linear pretrained head on {len(improved)}/{len(comparison)} datasets.",
        "",
        "## Selected Rescue Models",
        "",
    ]
    for _, row in selected.iterrows():
        lines.append(
            f"- `{row['dataset']}`: `{row['model']}`, validation {row['validation_primary_mean']:.4g}, "
            f"test {row['primary_mean']:.4g} +/- {row['primary_std']:.4g}."
        )
    lines.extend(["", "## Comparison To Best Frozen Linear Head", ""])
    for _, row in comparison.iterrows():
        verdict = "better" if row["rescue_better"] else "not better"
        lines.append(
            f"- `{row['dataset']}`: {verdict}; frozen {row['best_frozen_linear_value']:.4g}, "
            f"rescue {row['rescue_value']:.4g}, delta {row['delta_vs_best_frozen_linear']:.4g}."
        )
    lines.extend(
        [
            "",
            "## Manuscript Use",
            "",
            "Use this as a targeted low-module rescue appendix. It should not replace the main selector",
            "unless the rescued heads are added into a future full validation selector pool.",
            "",
        ]
    )
    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train nonlinear rescue heads for frozen pretrained embeddings.")
    parser.add_argument("--datasets", nargs="*", default=DEFAULT_DATASETS)
    parser.add_argument("--encoders", nargs="*", default=DEFAULT_ENCODERS)
    parser.add_argument("--models", nargs="*", default=["extratrees", "lgbm"])
    parser.add_argument("--seeds", nargs="*", type=int, default=[13, 17, 23, 29, 31])
    parser.add_argument("--n-estimators", type=int, default=120)
    parser.add_argument("--embedding-root", default=str(ROOT / "data" / "processed" / "pretrained_embeddings"))
    parser.add_argument("--output-dir", default=str(OUT_DIR))
    parser.add_argument("--no-desc", action="store_true")
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    for dataset in args.datasets:
        for encoder in args.encoders:
            for model in args.models:
                for seed in args.seeds:
                    row = run_one(
                        dataset=dataset,
                        encoder_name=encoder,
                        model=model,
                        seed=seed,
                        n_estimators=args.n_estimators,
                        include_desc=not args.no_desc,
                        embedding_root=Path(args.embedding_root),
                        output_dir=output_dir,
                        resume=args.resume,
                    )
                    rows.append(row)
                    print(
                        f"[ok] {dataset} {row['model']} seed={seed} "
                        f"valid={row['validation_primary']:.4g} test={row['primary_value']:.4g}"
                    )
    raw = pd.DataFrame(rows)
    selected = summarize(raw, output_dir)
    comparison = compare_to_frozen(selected)
    comparison.to_csv(output_dir / "comparison_to_frozen_linear.csv", index=False)
    selected.merge(comparison, on=["dataset", "task_type", "primary_metric", "primary_direction"], how="left").to_csv(
        TABLE18_PATH, index=False
    )
    write_report(output_dir, comparison, selected)
    print(f"Wrote {TABLE18_PATH}")
    print(comparison[["dataset", "delta_vs_best_frozen_linear", "rescue_better"]].to_string(index=False))


if __name__ == "__main__":
    main()
