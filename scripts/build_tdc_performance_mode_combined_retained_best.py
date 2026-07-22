from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TABLE_DIR = ROOT / "reports" / "manuscript_tables"
OUT_DIR = ROOT / "reports" / "tdc_performance_mode_appendix_combined"
PREVIOUS_TABLE = TABLE_DIR / "table14_tdc_full_panel_fast_appendix_benchmark.csv"
TABLE15 = TABLE_DIR / "table15_tdc_performance_mode_retained_best.csv"

SOURCES = [
    ("base", ROOT / "reports" / "tdc_performance_mode_appendix"),
    ("catboost", ROOT / "reports" / "tdc_performance_mode_appendix_catboost"),
]


def positive_delta(old_value: float, new_value: float, direction: str) -> float:
    if direction == "lower":
        return old_value - new_value
    return new_value - old_value


def best_by_validation(summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, group in summary.groupby(["dataset", "official_metric", "primary_direction"], dropna=False):
        direction = str(group["primary_direction"].iloc[0])
        ascending = direction == "lower"
        rows.append(group.sort_values("performance_validation_primary_mean", ascending=ascending).iloc[0])
    return pd.DataFrame(rows).reset_index(drop=True)


def load_sources() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summaries = []
    selected = []
    candidates = []
    for source_name, directory in SOURCES:
        summary_path = directory / "selected_metrics_summary.csv"
        selected_path = directory / "selected_metrics_raw.csv"
        candidate_path = directory / "candidate_metrics_raw.csv"
        if not summary_path.exists():
            raise FileNotFoundError(summary_path)
        summary = pd.read_csv(summary_path)
        summary["performance_run_source"] = source_name
        summaries.append(summary)
        if selected_path.exists():
            frame = pd.read_csv(selected_path)
            frame["performance_run_source"] = source_name
            selected.append(frame)
        if candidate_path.exists():
            frame = pd.read_csv(candidate_path)
            frame["performance_run_source"] = source_name
            candidates.append(frame)
    return pd.concat(summaries, ignore_index=True), pd.concat(selected, ignore_index=True), pd.concat(candidates, ignore_index=True)


def build_combined_outputs() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    summary_all, selected_all, candidate_all = load_sources()
    chosen_summary = best_by_validation(summary_all)
    chosen_summary.to_csv(OUT_DIR / "selected_metrics_summary.csv", index=False)

    keys = chosen_summary[["dataset", "performance_run_source"]].drop_duplicates()
    chosen_selected = selected_all.merge(keys, on=["dataset", "performance_run_source"], how="inner")
    chosen_selected = chosen_selected.drop_duplicates(["dataset", "split_method", "seed"], keep="last")
    chosen_selected.to_csv(OUT_DIR / "selected_metrics_raw.csv", index=False)

    candidate_all = candidate_all.drop_duplicates(
        [
            col
            for col in [
                "dataset",
                "split_method",
                "seed",
                "model",
                "candidate_type",
                "topk_members",
                "performance_run_source",
            ]
            if col in candidate_all.columns
        ],
        keep="last",
    )
    candidate_all.to_csv(OUT_DIR / "candidate_metrics_raw.csv", index=False)

    previous = pd.read_csv(PREVIOUS_TABLE)
    previous = previous[
        [
            "dataset",
            "model",
            "primary_mean",
            "primary_std",
            "primary_direction",
            "official_metric",
        ]
    ].rename(
        columns={
            "model": "previous_model",
            "primary_mean": "previous_primary_mean",
            "primary_std": "previous_primary_std",
        }
    )
    combined = previous.merge(
        chosen_summary,
        on=["dataset", "official_metric", "primary_direction"],
        how="outer",
    )
    combined["performance_delta_vs_previous"] = combined.apply(
        lambda row: positive_delta(
            float(row["previous_primary_mean"]),
            float(row["performance_primary_mean"]),
            str(row["primary_direction"]),
        )
        if pd.notna(row["previous_primary_mean"]) and pd.notna(row["performance_primary_mean"])
        else np.nan,
        axis=1,
    )
    combined["retained_source"] = np.where(
        combined["performance_delta_vs_previous"] > 0.0,
        "performance_mode",
        "previous_table14",
    )
    combined["retained_primary_mean"] = np.where(
        combined["performance_delta_vs_previous"] > 0.0,
        combined["performance_primary_mean"],
        combined["previous_primary_mean"],
    )
    combined["retained_model"] = np.where(
        combined["performance_delta_vs_previous"] > 0.0,
        combined["performance_model_counts"],
        combined["previous_model"],
    )
    combined.sort_values(["family", "dataset"]).to_csv(TABLE15, index=False)

    lines = [
        "# Combined TDC Performance-Mode Appendix",
        "",
        "This directory combines the base and CatBoost-expanded performance-mode runs.",
        "For each endpoint, the run configuration is chosen by validation primary mean,",
        "then compared against the previous fast full-panel baseline for retained-best reporting.",
        "",
        f"- Selected summary: `{(OUT_DIR / 'selected_metrics_summary.csv').relative_to(ROOT)}`",
        f"- Selected raw: `{(OUT_DIR / 'selected_metrics_raw.csv').relative_to(ROOT)}`",
        f"- Candidate raw: `{(OUT_DIR / 'candidate_metrics_raw.csv').relative_to(ROOT)}`",
        "- Manuscript table: `reports/manuscript_tables/table15_tdc_performance_mode_retained_best.csv`",
        "",
        "Endpoint run-source counts:",
    ]
    counts = chosen_summary["performance_run_source"].value_counts().to_dict()
    lines.extend([f"- `{key}`: {value}" for key, value in counts.items()])
    retained = combined["retained_source"].value_counts().to_dict()
    lines.extend(["", "Retained-best counts:"])
    lines.extend([f"- `{key}`: {value}" for key, value in retained.items()])
    (OUT_DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build_combined_outputs()
