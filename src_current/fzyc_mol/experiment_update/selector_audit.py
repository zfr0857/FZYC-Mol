from __future__ import annotations

import numpy as np
import pandas as pd

from .io import ExperimentConfig, write_csv


def _metric_cols(task_type: str) -> tuple[str, bool]:
    if task_type == "classification":
        return "roc_auc", False
    return "rmse", True


def build_selector_audit(config: ExperimentConfig) -> pd.DataFrame:
    path = config.reports_dir / "strong_baselines_metrics.csv"
    if not path.exists():
        return pd.DataFrame()
    metrics = pd.read_csv(path)
    if metrics.empty:
        return metrics
    rows = []
    for keys, group in metrics.groupby(["dataset", "seed", "split_strategy", "task_type"], dropna=False):
        dataset, seed, split_strategy, task_type = keys
        metric, ascending = _metric_cols(str(task_type))
        valid = group[group["split"].eq("valid")].dropna(subset=[metric]).copy()
        test = group[group["split"].eq("test")].dropna(subset=[metric]).copy()
        if valid.empty or test.empty:
            continue
        valid["valid_rank"] = valid[metric].rank(method="min", ascending=ascending)
        test["test_rank"] = test[metric].rank(method="min", ascending=ascending)
        merged = valid[["model", metric, "valid_rank"]].rename(columns={metric: "valid_metric"}).merge(
            test[["model", metric, "test_rank"]].rename(columns={metric: "test_metric"}),
            on="model",
            how="inner",
        )
        if merged.empty:
            continue
        chosen = merged.sort_values("valid_rank").iloc[0]
        oracle = merged.sort_values("test_rank").iloc[0]
        regret = float(chosen["test_metric"] - oracle["test_metric"]) if task_type == "regression" else float(oracle["test_metric"] - chosen["test_metric"])
        optimism = float(chosen["valid_metric"] - chosen["test_metric"]) if task_type == "classification" else float(chosen["test_metric"] - chosen["valid_metric"])
        rows.append(
            {
                "dataset": dataset,
                "seed": seed,
                "split_strategy": split_strategy,
                "task_type": task_type,
                "selected_candidate": chosen["model"],
                "test_oracle_candidate": oracle["model"],
                "valid_metric": chosen["valid_metric"],
                "test_metric": chosen["test_metric"],
                "valid_rank": chosen["valid_rank"],
                "test_rank": chosen["test_rank"],
                "top1_match": int(chosen["model"] == oracle["model"]),
                "top3_hit": int(chosen["test_rank"] <= 3),
                "regret": regret,
                "optimism_gap": optimism,
                "candidate_count": len(merged),
            }
        )
    out = pd.DataFrame(rows)
    write_csv(out, config.reports_dir / "selector_audit.csv")
    if not out.empty:
        summary = out.groupby(["split_strategy", "task_type"], dropna=False).agg(
            n=("dataset", "count"),
            top1_match_rate=("top1_match", "mean"),
            top3_hit_rate=("top3_hit", "mean"),
            median_regret=("regret", "median"),
            median_optimism_gap=("optimism_gap", "median"),
            median_candidate_count=("candidate_count", "median"),
        ).reset_index()
        write_csv(summary, config.reports_dir / "selector_audit_summary.csv")
    return out
