from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import DATASETS  # noqa: E402
from fzyc_mol.evaluate import compute_metrics  # noqa: E402

SOURCES = {
    "moleculenet_selector": ROOT / "reports" / "validation_selector_expanded",
    "tdc_admet_selector": ROOT / "reports" / "validation_selector_tdc_admet",
}
OUTPUT_DIR = ROOT / "reports" / "ad_gated_selector"
COVERAGES = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5]
DATASET_ORDER = sorted(DATASETS, key=len, reverse=True)


def parse_prediction_name(path: Path) -> tuple[str, int] | None:
    name = path.name
    if not name.endswith("_validation_selector_seed13_predictions.csv") and "_validation_selector_seed" not in name:
        return None
    match = re.match(r"(.+)_validation_selector_seed(\d+)_predictions\.csv$", name)
    if not match:
        return None
    dataset, seed = match.groups()
    if dataset not in DATASETS:
        return None
    return dataset, int(seed)


def normalize(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        return values
    lo = np.nanmin(values)
    hi = np.nanmax(values)
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return np.zeros_like(values, dtype=float)
    return (values - lo) / (hi - lo)


def risk_scores(weights: pd.DataFrame) -> dict[str, np.ndarray]:
    inv_tanimoto = 1.0 - weights["max_train_tanimoto"].to_numpy(dtype=float)
    scaffold = weights["scaffold_distance"].to_numpy(dtype=float)
    ensemble = weights["ensemble_std"].to_numpy(dtype=float)
    hybrid = (normalize(inv_tanimoto) + normalize(scaffold) + normalize(ensemble)) / 3.0
    return {
        "inverse_tanimoto": inv_tanimoto,
        "scaffold_distance": scaffold,
        "ensemble_std": ensemble,
        "hybrid_ad": hybrid,
    }


def retained_indices(risk: np.ndarray, coverage: float) -> np.ndarray:
    n = len(risk)
    k = max(1, int(np.ceil(n * coverage)))
    return np.argsort(risk)[:k]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, float | str | int]] = []
    for source, directory in SOURCES.items():
        if not directory.exists():
            continue
        for pred_path in directory.glob("*_validation_selector_seed*_predictions.csv"):
            parsed = parse_prediction_name(pred_path)
            if parsed is None:
                continue
            dataset, seed = parsed
            weight_path = directory / f"{dataset}_validation_selector_seed{seed}_weights.csv"
            if not weight_path.exists():
                continue
            pred = pd.read_csv(pred_path)
            weights = pd.read_csv(weight_path)
            if len(pred) != len(weights):
                merged = pred.merge(weights, on="smiles", how="inner")
                pred = merged[["smiles", "y_true", "y_pred"]]
                weights = merged.drop(columns=["y_true", "y_pred"])
            y_true = pred["y_true"].to_numpy()
            y_pred = pred["y_pred"].to_numpy()
            task_type = DATASETS[dataset].task_type
            for score_name, risk in risk_scores(weights).items():
                for coverage in COVERAGES:
                    idx = retained_indices(risk, coverage)
                    metrics = compute_metrics(task_type, y_true[idx], y_pred[idx])
                    row: dict[str, float | str | int] = {
                        "source": source,
                        "dataset": dataset,
                        "seed": seed,
                        "task_type": task_type,
                        "risk_score": score_name,
                        "coverage": coverage,
                        "retained_n": len(idx),
                        "mean_risk": float(np.mean(risk[idx])),
                        "full_n": len(risk),
                    }
                    row.update(metrics)
                    rows.append(row)
    raw = pd.DataFrame(rows)
    raw.to_csv(OUTPUT_DIR / "ad_gated_metrics_raw.csv", index=False)
    metric_cols = [
        col
        for col in raw.columns
        if col
        not in {
            "source",
            "dataset",
            "seed",
            "task_type",
            "risk_score",
            "coverage",
        }
    ]
    summary = (
        raw.groupby(["source", "dataset", "task_type", "risk_score", "coverage"], dropna=False)[metric_cols]
        .agg(["mean", "std"])
        .reset_index()
    )
    summary.to_csv(OUTPUT_DIR / "ad_gated_metrics_summary.csv", index=False)

    full = raw[raw["coverage"].eq(1.0)]
    focused = raw[raw["coverage"].isin([0.8, 0.6])]
    comparisons = focused.merge(
        full[
            [
                "source",
                "dataset",
                "seed",
                "risk_score",
                "rmse",
                "roc_auc",
                "pr_auc",
                "brier",
                "ece",
            ]
        ],
        on=["source", "dataset", "seed", "risk_score"],
        how="left",
        suffixes=("", "_full"),
    )
    comparisons["delta_rmse_positive"] = comparisons["rmse_full"] - comparisons["rmse"]
    comparisons["delta_roc_auc_positive"] = comparisons["roc_auc"] - comparisons["roc_auc_full"]
    comparisons["delta_pr_auc_positive"] = comparisons["pr_auc"] - comparisons["pr_auc_full"]
    comparisons["delta_brier_positive"] = comparisons["brier_full"] - comparisons["brier"]
    comparisons["delta_ece_positive"] = comparisons["ece_full"] - comparisons["ece"]
    comparisons.to_csv(OUTPUT_DIR / "ad_gated_vs_full.csv", index=False)
    agg = (
        comparisons.groupby(["source", "task_type", "risk_score", "coverage"], dropna=False)
        .agg(
            n_runs=("seed", "count"),
            mean_delta_rmse_positive=("delta_rmse_positive", "mean"),
            mean_delta_roc_auc_positive=("delta_roc_auc_positive", "mean"),
            mean_delta_pr_auc_positive=("delta_pr_auc_positive", "mean"),
            mean_delta_brier_positive=("delta_brier_positive", "mean"),
            mean_delta_ece_positive=("delta_ece_positive", "mean"),
        )
        .reset_index()
    )
    agg.to_csv(OUTPUT_DIR / "ad_gated_improvement_summary.csv", index=False)
    print(f"wrote AD-gated selector report to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
