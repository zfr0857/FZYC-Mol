from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
SUMMARY_PATHS = [
    REPORTS / "full_moleculenet" / "metrics_summary.csv",
    REPORTS / "upgrade_graph_transformer" / "metrics_summary.csv",
    REPORTS / "consensus" / "metrics_summary.csv",
    REPORTS / "adaptive_stacking" / "metrics_summary.csv",
    REPORTS / "strict_core" / "metrics_summary.csv",
    REPORTS / "strict_core_fast" / "metrics_summary.csv",
    REPORTS / "strict_multifp_fast" / "metrics_summary.csv",
    REPORTS / "chemprop_baseline" / "metrics_summary.csv",
    REPORTS / "validation_selector" / "metrics_summary.csv",
    REPORTS / "validation_selector_expanded" / "metrics_summary.csv",
    REPORTS / "tdc_admet_multifp" / "metrics_summary.csv",
    REPORTS / "validation_selector_tdc_admet" / "metrics_summary.csv",
    REPORTS / "pretrained_frozen" / "metrics_summary.csv",
    REPORTS / "pretrained_rdkit" / "metrics_summary.csv",
    REPORTS / "pretrained_frozen_mlm" / "metrics_summary.csv",
    REPORTS / "pretrained_rdkit_mlm" / "metrics_summary.csv",
    REPORTS / "pretrained_frozen_molformer" / "metrics_summary.csv",
    REPORTS / "pretrained_rdkit_molformer" / "metrics_summary.csv",
]


def flatten_summary(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, header=[0, 1])
    columns = []
    for top, bottom in frame.columns:
        if str(bottom).startswith("Unnamed") or bottom == "":
            columns.append(top)
        else:
            columns.append(f"{top}_{bottom}")
    frame.columns = columns
    frame["source"] = path.parent.name
    return frame


def main() -> None:
    summaries = [flatten_summary(path) for path in SUMMARY_PATHS if path.exists()]
    merged = pd.concat(summaries, ignore_index=True, sort=False)
    merged.to_csv(REPORTS / "combined_model_summary.csv", index=False)

    rows = []
    for _, row in merged.iterrows():
        task = row["task_type"]
        if task == "regression":
            metric = "rmse_mean"
            direction = "lower"
        else:
            metric = "roc_auc_mean"
            direction = "higher"
        value = row.get(metric)
        if pd.isna(value):
            continue
        rows.append(
            {
                "dataset": row["dataset"],
                "model": row["model"],
                "source": row["source"],
                "task_type": task,
                "primary_metric": metric,
                "direction": direction,
                "value": value,
                "std": row.get(metric.replace("_mean", "_std")),
            }
        )

    ranked = pd.DataFrame(rows)
    parts = []
    for dataset, group in ranked.groupby("dataset"):
        ascending = group["direction"].iloc[0] == "lower"
        table = group.sort_values("value", ascending=ascending).copy()
        table["rank"] = range(1, len(table) + 1)
        parts.append(table)
    ranked = pd.concat(parts, ignore_index=True)
    ranked.to_csv(REPORTS / "combined_primary_ranking.csv", index=False)

    best = ranked[ranked["rank"] == 1].copy()
    best.to_csv(REPORTS / "best_model_by_dataset.csv", index=False)
    print(ranked.to_string(index=False))


if __name__ == "__main__":
    main()
