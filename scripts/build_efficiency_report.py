from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


REPORTS = {
    "expanded_selector": ROOT / "reports" / "validation_selector_expanded",
    "descriptor_motif": ROOT / "reports" / "descriptor_motif_baselines",
    "selector_plus_descriptor_motif": ROOT / "reports" / "validation_selector_plus_descriptor_motif",
    "tdc_official_admet": ROOT / "reports" / "tdc_official_admet_splits",
    "split_realism": ROOT / "reports" / "split_realism_lgbm",
    "split_realism_tdc": ROOT / "reports" / "split_realism_tdc_lgbm",
    "moleculeace_cliff_weighted": ROOT / "reports" / "moleculeace_cliff_weighted",
}


MODEL_FAMILY = {
    "validation_selector": ("selector/ensemble", "CPU", "no trainable final deep model; validation meta-model only"),
    "descriptor_mlp": ("descriptor neural baseline", "CPU", "small MLP over RDKit descriptors"),
    "rf_motif": ("motif tree baseline", "CPU", "BRICS/Murcko/functional-group tree ensemble"),
    "xgb_motif": ("motif boosted-tree baseline", "CPU", "BRICS/Murcko/functional-group boosted trees"),
    "lgbm_motif": ("motif boosted-tree baseline", "CPU", "BRICS/Murcko/functional-group boosted trees"),
    "extratrees_motif": ("motif tree baseline", "CPU", "BRICS/Murcko/functional-group tree ensemble"),
    "lgbm_morgan": ("fingerprint boosted-tree baseline", "CPU", "Morgan + RDKit descriptors"),
    "rf_morgan": ("fingerprint tree baseline", "CPU", "Morgan + RDKit descriptors"),
}


def primary_metric(row: pd.Series) -> tuple[str, float, str]:
    task_type = row.get("task_type")
    if task_type == "regression" or ("rmse" in row and pd.notna(row.get("rmse", np.nan))):
        return "rmse", float(row.get("rmse", np.nan)), "lower"
    for metric in ("roc_auc", "pr_auc", "accuracy", "f1"):
        value = row.get(metric, np.nan)
        if pd.notna(value):
            return metric, float(value), "higher"
    return "unknown", np.nan, "higher"


def report_span_seconds(report_dir: Path) -> float:
    files = [path for path in report_dir.rglob("*.csv") if path.is_file()]
    if len(files) < 2:
        return np.nan
    mtimes = [path.stat().st_mtime for path in files]
    return float(max(mtimes) - min(mtimes))


def summarize_report(name: str, report_dir: Path) -> list[dict]:
    metrics_path = report_dir / "metrics_raw.csv"
    if not metrics_path.exists():
        return []
    raw = pd.read_csv(metrics_path)
    rows = []
    span = report_span_seconds(report_dir)
    pred_files = list(report_dir.glob("*_predictions.csv"))
    if "dataset" not in raw.columns and "task" in raw.columns:
        raw["dataset"] = raw["task"]
    if "task_type" not in raw.columns and "rmse" in raw.columns:
        raw["task_type"] = "regression"
    group_cols = [c for c in ["dataset", "model", "split_method", "task_type"] if c in raw.columns]
    if "model" not in group_cols:
        raw["model"] = name
        group_cols.append("model")
    for keys, group in raw.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_cols, keys))
        metric_name, _value, direction = primary_metric(group.iloc[0])
        metric_mean = float(group[metric_name].mean()) if metric_name in group else np.nan
        metric_std = float(group[metric_name].std()) if metric_name in group else np.nan
        fit_seconds = float(group["fit_seconds"].mean()) if "fit_seconds" in group else np.nan
        predict_seconds = float(group["predict_seconds"].mean()) if "predict_seconds" in group else np.nan
        family, hardware, notes = MODEL_FAMILY.get(str(row.get("model")), ("other", "CPU", "see report"))
        rows.append(
            {
                "report": name,
                **row,
                "model_family": family,
                "hardware_class": hardware,
                "primary_metric": metric_name,
                "primary_direction": direction,
                "primary_mean": metric_mean,
                "primary_std": metric_std,
                "mean_fit_seconds": fit_seconds,
                "mean_predict_seconds": predict_seconds,
                "report_span_seconds": span,
                "n_metric_rows": int(len(group)),
                "n_prediction_files_in_report": int(len(pred_files)),
                "notes": notes,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build compute-cost and efficiency summary.")
    parser.add_argument("--output-dir", default=str(ROOT / "reports" / "efficiency"))
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, path in REPORTS.items():
        if path.exists():
            rows.extend(summarize_report(name, path))
    table = pd.DataFrame(rows)
    table.to_csv(output_dir / "efficiency_summary.csv", index=False)
    if not table.empty:
        compact = (
            table.groupby(["report", "model_family", "hardware_class"], dropna=False)
            .agg(
                primary_mean_median=("primary_mean", "median"),
                mean_fit_seconds=("mean_fit_seconds", "mean"),
                mean_predict_seconds=("mean_predict_seconds", "mean"),
                n_metric_rows=("n_metric_rows", "sum"),
            )
            .reset_index()
        )
        compact.to_csv(output_dir / "efficiency_compact.csv", index=False)
    print(table.tail(60).to_string(index=False) if not table.empty else "No metrics found.")


if __name__ == "__main__":
    main()
