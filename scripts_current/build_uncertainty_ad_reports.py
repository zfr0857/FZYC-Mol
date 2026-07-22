from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import mean_squared_error

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.evaluate import expected_calibration_error


def parse_selector_prediction(path: Path) -> tuple[str, int] | None:
    match = re.match(r"(.+)_validation_selector_seed(\d+)_predictions\.csv$", path.name)
    if not match:
        return None
    return match.group(1), int(match.group(2))


def infer_task_type(predictions: pd.DataFrame) -> str:
    y = predictions["y_true"].to_numpy()
    pred = predictions["y_pred"].to_numpy()
    if set(np.unique(y)).issubset({0, 1}) and np.nanmin(pred) >= 0.0 and np.nanmax(pred) <= 1.0:
        return "classification"
    return "regression"


def reliability_bins(dataset: str, seed: int, table: pd.DataFrame, n_bins: int = 10) -> pd.DataFrame:
    y = table["y_true"].to_numpy(dtype=int)
    p = np.clip(table["y_pred"].to_numpy(dtype=float), 1e-7, 1 - 1e-7)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    rows = []
    for i, (low, high) in enumerate(zip(bins[:-1], bins[1:])):
        mask = (p >= low) & (p <= high) if high == 1.0 else (p >= low) & (p < high)
        if not np.any(mask):
            continue
        rows.append(
            {
                "dataset": dataset,
                "seed": seed,
                "bin": i,
                "low": low,
                "high": high,
                "n": int(mask.sum()),
                "confidence": float(p[mask].mean()),
                "observed_positive_rate": float(y[mask].mean()),
                "abs_gap": float(abs(y[mask].mean() - p[mask].mean())),
            }
        )
    return pd.DataFrame(rows)


def risk_coverage(dataset: str, seed: int, table: pd.DataFrame, task_type: str) -> pd.DataFrame:
    if "ensemble_std" in table:
        uncertainty = table["ensemble_std"].to_numpy(dtype=float)
    elif "scaffold_distance" in table:
        uncertainty = table["scaffold_distance"].to_numpy(dtype=float)
    else:
        uncertainty = np.abs(table["y_pred"].to_numpy(dtype=float) - table["y_pred"].mean())
    order = np.argsort(uncertainty)
    y = table["y_true"].to_numpy(dtype=float)
    pred = table["y_pred"].to_numpy(dtype=float)
    rows = []
    for coverage in np.linspace(0.1, 1.0, 10):
        keep = order[: max(1, int(round(len(order) * coverage)))]
        if task_type == "classification":
            risk = float(((pred[keep] >= 0.5).astype(int) != y[keep].astype(int)).mean())
            score = float(np.mean((y[keep] - pred[keep]) ** 2))
            metric_name = "error_rate"
        else:
            risk = float(np.sqrt(mean_squared_error(y[keep], pred[keep])))
            score = float(np.mean(np.abs(y[keep] - pred[keep])))
            metric_name = "rmse"
        rows.append(
            {
                "dataset": dataset,
                "seed": seed,
                "coverage": float(coverage),
                "risk_metric": metric_name,
                "risk": risk,
                "secondary_error": score,
                "mean_uncertainty": float(uncertainty[keep].mean()),
            }
        )
    return pd.DataFrame(rows)


def ad_bins(dataset: str, seed: int, table: pd.DataFrame, task_type: str) -> pd.DataFrame:
    if "max_train_tanimoto" not in table:
        return pd.DataFrame()
    out = table.copy()
    if task_type == "classification":
        out["error"] = ((out["y_pred"] >= 0.5).astype(int) != out["y_true"].astype(int)).astype(float)
        out["soft_error"] = (out["y_true"].astype(float) - out["y_pred"].astype(float)).abs()
    else:
        out["error"] = (out["y_true"].astype(float) - out["y_pred"].astype(float)).abs()
        out["soft_error"] = out["error"]
    out["similarity_bin"] = pd.cut(
        out["max_train_tanimoto"],
        bins=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
        include_lowest=True,
    )
    grouped = (
        out.groupby("similarity_bin", observed=True)
        .agg(
            n=("error", "size"),
            mean_error=("error", "mean"),
            median_error=("error", "median"),
            mean_soft_error=("soft_error", "mean"),
            mean_uncertainty=("ensemble_std", "mean") if "ensemble_std" in out else ("error", "mean"),
            mean_similarity=("max_train_tanimoto", "mean"),
        )
        .reset_index()
    )
    grouped.insert(0, "seed", seed)
    grouped.insert(0, "dataset", dataset)
    grouped["similarity_bin"] = grouped["similarity_bin"].astype(str)
    return grouped


def plot_dataset(report_dir: Path, dataset: str, task_type: str, reliability: pd.DataFrame, risk: pd.DataFrame, ad: pd.DataFrame) -> None:
    fig_dir = report_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    if task_type == "classification" and not reliability.empty:
        rel = reliability.groupby("bin", as_index=False)[["confidence", "observed_positive_rate"]].mean()
        plt.figure(figsize=(4.5, 4.0))
        plt.plot([0, 1], [0, 1], color="black", linewidth=1, linestyle="--")
        plt.plot(rel["confidence"], rel["observed_positive_rate"], marker="o")
        plt.xlabel("Predicted probability")
        plt.ylabel("Observed positive rate")
        plt.title(f"{dataset} reliability")
        plt.tight_layout()
        plt.savefig(fig_dir / f"{dataset}_reliability.png", dpi=220)
        plt.close()
    if not risk.empty:
        curve = risk.groupby("coverage", as_index=False)["risk"].mean()
        plt.figure(figsize=(4.8, 3.8))
        plt.plot(curve["coverage"], curve["risk"], marker="o")
        plt.xlabel("Coverage")
        plt.ylabel(risk["risk_metric"].iloc[0])
        plt.title(f"{dataset} risk-coverage")
        plt.tight_layout()
        plt.savefig(fig_dir / f"{dataset}_risk_coverage.png", dpi=220)
        plt.close()
    if not ad.empty:
        curve = ad.groupby("similarity_bin", as_index=False)["mean_error"].mean()
        plt.figure(figsize=(5.2, 3.8))
        plt.bar(curve["similarity_bin"].astype(str), curve["mean_error"])
        plt.xlabel("Max train Tanimoto bin")
        plt.ylabel("Mean error")
        plt.title(f"{dataset} applicability domain")
        plt.xticks(rotation=30, ha="right")
        plt.tight_layout()
        plt.savefig(fig_dir / f"{dataset}_ad_bins.png", dpi=220)
        plt.close()


def process_selector_dir(selector_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    reliability_rows = []
    risk_rows = []
    ad_rows = []
    summary_rows = []

    for pred_path in selector_dir.glob("*_validation_selector_seed*_predictions.csv"):
        parsed = parse_selector_prediction(pred_path)
        if parsed is None:
            continue
        dataset, seed = parsed
        predictions = pd.read_csv(pred_path)
        weight_path = selector_dir / f"{dataset}_validation_selector_seed{seed}_weights.csv"
        table = predictions.copy()
        if weight_path.exists():
            weights = pd.read_csv(weight_path)
            keep_cols = [col for col in ["smiles", "max_train_tanimoto", "scaffold_distance", "ensemble_std"] if col in weights]
            table = table.merge(weights[keep_cols], on="smiles", how="left")
        task_type = infer_task_type(table)
        if task_type == "classification":
            reliability_rows.append(reliability_bins(dataset, seed, table))
            ece = expected_calibration_error(table["y_true"].to_numpy(), table["y_pred"].to_numpy())
            error = ((table["y_pred"] >= 0.5).astype(int) != table["y_true"].astype(int)).astype(float)
        else:
            ece = np.nan
            error = (table["y_true"].astype(float) - table["y_pred"].astype(float)).abs().to_numpy()
        risk_rows.append(risk_coverage(dataset, seed, table, task_type))
        ad = ad_bins(dataset, seed, table, task_type)
        if not ad.empty:
            ad_rows.append(ad)
        uncertainty = table["ensemble_std"].to_numpy(dtype=float) if "ensemble_std" in table else np.full(len(table), np.nan)
        rho = spearmanr(uncertainty, error, nan_policy="omit").statistic if np.isfinite(uncertainty).any() else np.nan
        summary_rows.append(
            {
                "dataset": dataset,
                "seed": seed,
                "task_type": task_type,
                "n": len(table),
                "ece": float(ece) if np.isfinite(ece) else np.nan,
                "mean_error": float(np.mean(error)),
                "mean_uncertainty": float(np.nanmean(uncertainty)) if np.isfinite(uncertainty).any() else np.nan,
                "spearman_uncertainty_error": float(rho) if np.isfinite(rho) else np.nan,
                "source": selector_dir.name,
            }
        )

    reliability = pd.concat(reliability_rows, ignore_index=True) if reliability_rows else pd.DataFrame()
    risk = pd.concat(risk_rows, ignore_index=True) if risk_rows else pd.DataFrame()
    ad = pd.concat(ad_rows, ignore_index=True) if ad_rows else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)
    reliability.to_csv(output_dir / "calibration_bins.csv", index=False)
    risk.to_csv(output_dir / "risk_coverage.csv", index=False)
    ad.to_csv(output_dir / "applicability_domain_bins.csv", index=False)
    summary.to_csv(output_dir / "uncertainty_summary.csv", index=False)

    for dataset, group in summary.groupby("dataset"):
        plot_dataset(
            output_dir,
            dataset,
            group["task_type"].iloc[0],
            reliability[reliability["dataset"] == dataset] if not reliability.empty else pd.DataFrame(),
            risk[risk["dataset"] == dataset] if not risk.empty else pd.DataFrame(),
            ad[ad["dataset"] == dataset] if not ad.empty else pd.DataFrame(),
        )
    print(summary.to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build uncertainty, calibration, and applicability-domain reports.")
    parser.add_argument("--selector-dir", default=str(ROOT / "reports" / "validation_selector"))
    parser.add_argument("--output-dir", default=str(ROOT / "reports" / "uncertainty_ad"))
    args = parser.parse_args()
    process_selector_dir(Path(args.selector_dir), Path(args.output_dir))


if __name__ == "__main__":
    main()
