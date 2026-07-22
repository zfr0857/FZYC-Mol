from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


METHODS = ("consensus", "stack", "adaptive")
FAMILY_ALIASES = {
    "full_q1": "strict_core_q1_all",
    "no_core": "q1_no_core",
    "no_multifp": "q1_no_multifp",
    "no_chemprop": "q1_no_chemprop",
    "no_pretrained": "q1_no_pretrained",
    "core_only": "strict_core",
    "multifp_only": "multifp_only",
    "chemprop_only": "chemprop_only",
    "pretrained_only": "pretrained_only",
}


def split_candidate(name: str) -> tuple[str, str]:
    for method in METHODS:
        prefix = f"{method}_"
        if name.startswith(prefix):
            return method, name[len(prefix) :]
    return "unknown", name


def metric_columns(task_type: str) -> tuple[str, str, bool]:
    if task_type == "regression":
        return "valid_rmse", "test_rmse", True
    return "valid_roc_auc", "test_roc_auc", False


def select_family(group: pd.DataFrame, family: str) -> dict | None:
    subset = group[group["family"] == family].copy()
    if subset.empty:
        return None
    task_type = subset["task_type"].iloc[0]
    valid_col, test_col, ascending = metric_columns(task_type)
    if valid_col not in subset or subset[valid_col].isna().all():
        return None
    ranking = (
        subset.groupby(["model", "method", "family"], dropna=False)
        .agg(
            validation_score=(valid_col, "mean"),
            test_mean=(test_col, "mean"),
            test_std=(test_col, "std"),
            n_seeds=("seed", "nunique"),
        )
        .reset_index()
        .dropna(subset=["validation_score"])
        .sort_values("validation_score", ascending=ascending)
    )
    if ranking.empty:
        return None
    row = ranking.iloc[0].to_dict()
    row["task_type"] = task_type
    row["selection_metric"] = valid_col
    row["test_metric"] = test_col
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize expert-family selector ablations.")
    parser.add_argument("--candidate-metrics", default="reports/validation_selector_ablation/candidate_metrics_raw.csv")
    parser.add_argument("--output-dir", default="reports/selector_ablation")
    args = parser.parse_args()

    metrics = pd.read_csv(args.candidate_metrics)
    parsed = metrics["model"].map(split_candidate)
    metrics["method"] = [item[0] for item in parsed]
    metrics["family"] = [item[1] for item in parsed]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for dataset, group in metrics.groupby("dataset"):
        for label, family in FAMILY_ALIASES.items():
            selected = select_family(group, family)
            if selected is None:
                continue
            selected["dataset"] = dataset
            selected["ablation"] = label
            rows.append(selected)
    family_best = pd.DataFrame(rows)
    family_best.to_csv(output_dir / "family_best_summary.csv", index=False)

    deltas = []
    for dataset, group in family_best.groupby("dataset"):
        full = group[group["ablation"] == "full_q1"]
        if full.empty:
            continue
        full_row = full.iloc[0]
        task_type = full_row["task_type"]
        for _, row in group.iterrows():
            if row["ablation"] == "full_q1":
                continue
            if task_type == "regression":
                positive_delta = float(row["test_mean"] - full_row["test_mean"])
                interpretation = "full_better" if positive_delta > 0 else "ablation_better"
            else:
                positive_delta = float(full_row["test_mean"] - row["test_mean"])
                interpretation = "full_better" if positive_delta > 0 else "ablation_better"
            deltas.append(
                {
                    "dataset": dataset,
                    "task_type": task_type,
                    "ablation": row["ablation"],
                    "full_candidate": full_row["model"],
                    "ablation_candidate": row["model"],
                    "test_metric": row["test_metric"],
                    "full_test_mean": full_row["test_mean"],
                    "ablation_test_mean": row["test_mean"],
                    "positive_delta_full_minus_ablation": positive_delta,
                    "interpretation": interpretation if not np.isclose(positive_delta, 0.0) else "tie",
                }
            )
    delta_df = pd.DataFrame(deltas)
    delta_df.to_csv(output_dir / "family_ablation_delta.csv", index=False)
    if not delta_df.empty:
        aggregate = (
            delta_df.groupby("ablation")
            .agg(
                mean_positive_delta=("positive_delta_full_minus_ablation", "mean"),
                full_better=("interpretation", lambda x: int((x == "full_better").sum())),
                ablation_better=("interpretation", lambda x: int((x == "ablation_better").sum())),
                ties=("interpretation", lambda x: int((x == "tie").sum())),
            )
            .reset_index()
            .sort_values("mean_positive_delta", ascending=False)
        )
        aggregate.to_csv(output_dir / "family_ablation_aggregate.csv", index=False)
        print(aggregate.to_string(index=False))


if __name__ == "__main__":
    main()
