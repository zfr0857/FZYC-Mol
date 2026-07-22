from __future__ import annotations

import argparse
import math
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "reports" / "model_module_improvement"
TABLE_DIR = ROOT / "reports" / "manuscript_tables"
TABLE17_PATH = TABLE_DIR / "table17_moleculenet_meta_pool_selector.csv"


DEFAULT_CANDIDATE_REPORTS = {
    "expanded_selector": ROOT / "reports" / "validation_selector_expanded" / "candidate_metrics_raw.csv",
    "ablation_pool": ROOT / "reports" / "validation_selector_ablation" / "candidate_metrics_raw.csv",
    "descriptor_motif_pool": ROOT
    / "reports"
    / "validation_selector_plus_descriptor_motif"
    / "candidate_metrics_raw.csv",
}


def load_candidates(paths: dict[str, Path]) -> pd.DataFrame:
    frames = []
    for pool, path in paths.items():
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        frame["candidate_pool"] = pool
        frames.append(frame)
    if not frames:
        raise FileNotFoundError("No candidate metric files were found.")
    data = pd.concat(frames, ignore_index=True, sort=False)
    data = data.drop_duplicates(["dataset", "seed", "candidate_pool", "model"], keep="last")
    data["selection_value"] = pd.to_numeric(data["selection_value"], errors="coerce")
    return data


def primary_columns(task_type: str) -> tuple[str, str, str]:
    if task_type == "regression":
        return "test_rmse", "valid_rmse", "lower"
    return "test_roc_auc", "valid_roc_auc", "higher"


def valid_candidate_rows(data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in data.iterrows():
        task_type = str(row["task_type"])
        test_col, valid_col, direction = primary_columns(task_type)
        selection = row.get("selection_value", np.nan)
        test_value = row.get(test_col, np.nan)
        valid_value = row.get(valid_col, np.nan)
        if pd.isna(selection) and pd.notna(valid_value):
            selection = valid_value
        if pd.isna(selection) or pd.isna(test_value):
            continue
        clean = row.to_dict()
        clean["primary_value"] = float(test_value)
        clean["primary_direction"] = direction
        clean["selection_value"] = float(selection)
        clean["primary_test_column"] = test_col
        clean["primary_valid_column"] = valid_col
        rows.append(clean)
    if not rows:
        raise RuntimeError("No finite candidate rows after primary metric filtering.")
    return pd.DataFrame(rows)


def choose_dataset_level_candidates(data: pd.DataFrame, min_seeds: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    candidate_rows = []
    selected_seed_rows = []
    for dataset, group in data.groupby("dataset", dropna=False):
        task_type = str(group["task_type"].iloc[0])
        _, _, direction = primary_columns(task_type)
        for (pool, model), candidate in group.groupby(["candidate_pool", "model"], dropna=False):
            n_seeds = int(candidate["seed"].nunique())
            if n_seeds < min_seeds:
                continue
            candidate_rows.append(
                {
                    "dataset": dataset,
                    "candidate_pool": pool,
                    "model": model,
                    "task_type": task_type,
                    "primary_direction": direction,
                    "n_seeds": n_seeds,
                    "validation_primary_mean": float(candidate["selection_value"].mean()),
                    "validation_primary_std": float(candidate["selection_value"].std()),
                    "test_primary_mean": float(candidate["primary_value"].mean()),
                    "test_primary_std": float(candidate["primary_value"].std()),
                }
            )
        dataset_candidates = pd.DataFrame([row for row in candidate_rows if row["dataset"] == dataset])
        if dataset_candidates.empty:
            continue
        ascending = direction == "lower"
        selected = dataset_candidates.sort_values("validation_primary_mean", ascending=ascending).iloc[0]
        chosen_rows = group[
            group["candidate_pool"].astype(str).eq(str(selected["candidate_pool"]))
            & group["model"].astype(str).eq(str(selected["model"]))
        ].copy()
        chosen_rows["selected_by"] = "dataset_mean_validation_primary"
        selected_seed_rows.append(chosen_rows)

    if not selected_seed_rows:
        raise RuntimeError("No selected candidate rows were produced.")
    return pd.DataFrame(candidate_rows), pd.concat(selected_seed_rows, ignore_index=True)


def summarize_selected(selected: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for dataset, group in selected.groupby("dataset", dropna=False):
        first = group.iloc[0]
        pool_counts = Counter(group["candidate_pool"].astype(str))
        model_counts = Counter(group["model"].astype(str))
        rows.append(
            {
                "dataset": dataset,
                "task_type": first["task_type"],
                "primary_direction": first["primary_direction"],
                "n_seeds": int(group["seed"].nunique()),
                "selected_pool_counts": "; ".join(f"{k}:{v}" for k, v in pool_counts.most_common()),
                "selected_model_counts": "; ".join(f"{k}:{v}" for k, v in model_counts.most_common()),
                "validation_primary_mean": float(group["selection_value"].mean()),
                "validation_primary_std": float(group["selection_value"].std()),
                "meta_pool_primary_mean": float(group["primary_value"].mean()),
                "meta_pool_primary_std": float(group["primary_value"].std()),
                "rmse_mean": float(group["test_rmse"].mean()) if "test_rmse" in group else np.nan,
                "roc_auc_mean": float(group["test_roc_auc"].mean()) if "test_roc_auc" in group else np.nan,
                "pr_auc_mean": float(group["test_pr_auc"].mean()) if "test_pr_auc" in group else np.nan,
                "brier_mean": float(group["test_brier"].mean()) if "test_brier" in group else np.nan,
                "ece_mean": float(group["test_ece"].mean()) if "test_ece" in group else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values("dataset").reset_index(drop=True)


def load_current_table() -> pd.DataFrame:
    path = TABLE_DIR / "table2_moleculenet_main_long.csv"
    table = pd.read_csv(path)
    current = table[table["category"].eq("FZYC-Mol validation selector")].copy()
    return current[
        [
            "dataset",
            "task_type",
            "primary_metric",
            "direction",
            "model",
            "source",
            "value",
            "std",
        ]
    ].rename(
        columns={
            "model": "current_model",
            "source": "current_source",
            "value": "current_primary_mean",
            "std": "current_primary_std",
            "direction": "primary_direction",
        }
    )


def compare_to_current(summary: pd.DataFrame) -> pd.DataFrame:
    current = load_current_table()
    merged = current.merge(summary, on=["dataset", "task_type", "primary_direction"], how="outer")
    direction = merged["primary_direction"].astype(str)
    merged["meta_delta_vs_current"] = np.where(
        direction.eq("lower"),
        merged["current_primary_mean"] - merged["meta_pool_primary_mean"],
        merged["meta_pool_primary_mean"] - merged["current_primary_mean"],
    )
    merged["meta_better_than_current"] = merged["meta_delta_vs_current"] > 1e-8
    return merged.sort_values("dataset").reset_index(drop=True)


def family_name(source: str, model: str) -> str:
    source = str(source)
    model = str(model)
    if "validation_selector" in source or "adaptive_stacking" in source or "consensus" in source:
        return "selector_or_ensemble"
    if "strict_multifp" in source or "tdc_admet_multifp" in source:
        return "multi_fingerprint_tree"
    if "strict_core" in source and any(token in model for token in ["rf_morgan", "xgb_morgan", "lgbm_morgan"]):
        return "single_morgan_tree"
    if "chemprop" in source:
        return "chemprop"
    if "pretrained" in source:
        return "frozen_pretrained"
    if "upgrade_graph_transformer" in source or "graph_transformer" in model or "fzyc_mol_gt" in model:
        return "graph_transformer_probe"
    if any(token in model for token in ["gin", "dmpnn", "fzyc_mol"]):
        return "gnn_fzyc_core"
    if "full_moleculenet" in source:
        return "legacy_core_or_ablation"
    return source


def build_family_gap_report() -> tuple[pd.DataFrame, pd.DataFrame]:
    ranking_path = ROOT / "reports" / "combined_primary_ranking.csv"
    ranking = pd.read_csv(ranking_path)
    max_rank = ranking.groupby("dataset")["rank"].transform("max")
    ranking["rank_fraction"] = (ranking["rank"] - 1) / (max_rank - 1)
    ranking["low_rank_flag"] = ranking["rank_fraction"] >= 0.75
    ranking["family"] = ranking.apply(lambda row: family_name(row["source"], row["model"]), axis=1)
    summary = (
        ranking.groupby("family", dropna=False)
        .agg(
            rows=("dataset", "size"),
            datasets=("dataset", "nunique"),
            mean_rank_fraction=("rank_fraction", "mean"),
            bottom_quartile_fraction=("low_rank_flag", "mean"),
            median_rank=("rank", "median"),
        )
        .reset_index()
        .sort_values("mean_rank_fraction", ascending=False)
    )
    low_cases = ranking.sort_values("rank_fraction", ascending=False)[
        ["dataset", "model", "source", "family", "task_type", "value", "std", "rank", "rank_fraction"]
    ].head(40)
    return summary, low_cases


def write_report(
    output_dir: Path,
    comparison: pd.DataFrame,
    family_summary: pd.DataFrame,
    low_cases: pd.DataFrame,
) -> None:
    improved = comparison[comparison["meta_better_than_current"].fillna(False)]
    worsened = comparison[~comparison["meta_better_than_current"].fillna(False)]
    worst_families = family_summary.head(4)
    lines = [
        "# Model Module Improvement Report",
        "",
        "Date: 2026-05-31",
        "",
        "## Question",
        "",
        "Can the model side still be improved, especially for low-performing modules?",
        "",
        "## Short Answer",
        "",
        "Yes. The highest-value improvement is not to restart large neural training, but to make",
        "the selector more conservative around weak modules and to add targeted rescue heads for",
        "specific low-performing families.",
        "",
        "## Current Low-Performing Module Families",
        "",
        "The combined ranking shows the weakest standalone families:",
        "",
    ]
    for _, row in worst_families.iterrows():
        lines.append(
            f"- `{row['family']}`: mean rank fraction {row['mean_rank_fraction']:.3f}, "
            f"bottom-quartile fraction {row['bottom_quartile_fraction']:.3f}."
        )
    lines.extend(
        [
            "",
            "Interpretation:",
            "",
            "- Frozen pretrained linear heads are the weakest standalone family. They should be used only as optional complementary experts unless rescued with stronger nonlinear heads.",
            "- Chemprop is valuable on selected endpoints but unstable as a universal module; it should remain endpoint-gated.",
            "- The Graph Transformer probe is not competitive enough in the current CPU-scale setting; do not spend major compute here unless adding a real pretraining or stronger architecture setup.",
            "- Multi-fingerprint tree models remain strong on many ADMET endpoints, but individual tree families can be endpoint-sensitive.",
            "",
            "## New Validation-Only Meta-Pool Selector",
            "",
            "I combined existing candidate pools without retraining:",
            "",
            "- `validation_selector_expanded`",
            "- `validation_selector_ablation`",
            "- `validation_selector_plus_descriptor_motif`",
            "",
            "For each dataset, the final candidate is chosen by mean validation primary metric across seeds. Test labels are used only after the validation choice is fixed.",
            "",
            "Comparison with the current manuscript Table 2 selector:",
            "",
        ]
    )
    for _, row in comparison.iterrows():
        delta = row.get("meta_delta_vs_current", np.nan)
        direction = "improved" if bool(row.get("meta_better_than_current", False)) else "not improved"
        lines.append(
            f"- `{row['dataset']}`: {direction}; current {row['current_primary_mean']:.4g}, "
            f"meta-pool {row['meta_pool_primary_mean']:.4g}, delta {delta:.4g}."
        )
    lines.extend(
        [
            "",
            f"Improved endpoints: {len(improved)}/{len(comparison)}.",
            f"Non-improved endpoints: {len(worsened)}/{len(comparison)}.",
            "",
            "## Recommendation",
            "",
            "Do not replace the current main Table 2 with this meta-pool result. It is most useful",
            "as a diagnostic: simply adding more candidate pools does not automatically improve",
            "the validation-only selector, and low-performing modules need targeted repair or",
            "stability guardrails rather than indiscriminate expansion.",
            "",
            "Next targeted model experiments, in priority order:",
            "",
            "1. Pretrained-rescue heads: train ExtraTrees/CatBoost/XGBoost heads on frozen embeddings plus RDKit descriptors, replacing the current linear frozen heads.",
            "2. Stability-aware selector: add a validation mean-minus-std criterion or require a candidate to beat the incumbent by a small validation margin before switching.",
            "3. Chemprop guardrail: keep Chemprop only for endpoints where validation and seed stability support it; otherwise route to multi-fingerprint/tree ensembles.",
            "4. Graph module rescue only if compute permits: use graph model as an auxiliary feature/stacking member rather than a standalone performance claim.",
            "",
            "## Outputs",
            "",
            f"- Candidate audit: `{(output_dir / 'meta_pool_candidate_audit.csv').resolve().relative_to(ROOT)}`",
            f"- Selected seed rows: `{(output_dir / 'meta_pool_selected_seed_metrics.csv').resolve().relative_to(ROOT)}`",
            f"- Selected summary: `{(output_dir / 'meta_pool_selected_summary.csv').resolve().relative_to(ROOT)}`",
            "- Manuscript appendix table: `reports/manuscript_tables/table17_moleculenet_meta_pool_selector.csv`",
            f"- Low module cases: `{(output_dir / 'low_module_cases.csv').resolve().relative_to(ROOT)}`",
            "",
        ]
    )
    (output_dir / "model_module_improvement_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a validation-only meta-pool selector and low-module report.")
    parser.add_argument("--output-dir", default=str(OUT_DIR))
    parser.add_argument("--min-seeds", type=int, default=5)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    raw = load_candidates(DEFAULT_CANDIDATE_REPORTS)
    clean = valid_candidate_rows(raw)
    candidate_audit, selected = choose_dataset_level_candidates(clean, min_seeds=args.min_seeds)
    summary = summarize_selected(selected)
    comparison = compare_to_current(summary)
    family_summary, low_cases = build_family_gap_report()

    clean.to_csv(output_dir / "meta_pool_all_candidate_metrics.csv", index=False)
    candidate_audit.to_csv(output_dir / "meta_pool_candidate_audit.csv", index=False)
    selected.to_csv(output_dir / "meta_pool_selected_seed_metrics.csv", index=False)
    summary.to_csv(output_dir / "meta_pool_selected_summary.csv", index=False)
    comparison.to_csv(TABLE17_PATH, index=False)
    family_summary.to_csv(output_dir / "low_module_family_summary.csv", index=False)
    low_cases.to_csv(output_dir / "low_module_cases.csv", index=False)
    write_report(output_dir, comparison, family_summary, low_cases)

    print(f"Wrote {TABLE17_PATH}")
    print(comparison[["dataset", "current_primary_mean", "meta_pool_primary_mean", "meta_delta_vs_current"]].to_string(index=False))


if __name__ == "__main__":
    main()
