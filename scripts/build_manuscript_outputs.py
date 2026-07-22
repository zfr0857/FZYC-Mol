from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fzyc_mol.reporting.stage_e import build_manuscript_values, build_stage_e_outputs  # noqa: E402


def finite_or_none(value: float) -> float | None:
    return float(value) if math.isfinite(float(value)) else None


def main() -> None:
    candidate_pool = ROOT / "results" / "candidate_pool"
    statistics = ROOT / "results" / "statistics"
    nested = ROOT / "results" / "nested_selection"
    source_data = ROOT / "results" / "source_data"
    for path in (statistics, nested, source_data):
        path.mkdir(parents=True, exist_ok=True)

    regret = pd.read_csv(candidate_pool / "subset_regret_long.csv")
    ranking = pd.read_csv(candidate_pool / "subset_ranking_metrics_long.csv")
    decisions = pd.read_csv(candidate_pool / "subset_selection_reason.csv")
    registry = pd.read_csv(ROOT / "reports" / "draft10_core_experiments_20260621" / "expanded_nested" / "candidate_registry.csv")
    endpoint, bootstrap, stability = build_stage_e_outputs(regret, ranking, decisions, registry)
    endpoint.to_csv(statistics / "endpoint_summary.csv", index=False)
    bootstrap.to_csv(statistics / "hierarchical_bootstrap.csv", index=False)
    stability.to_csv(nested / "stability_metrics.csv", index=False)

    candidate_summary = bootstrap.merge(
        endpoint.groupby(["mode", "pool_size"], as_index=False).agg(
            chance_adjusted_hit_mean=("chance_adjusted_hit_mean", "mean"),
            mrr_mean=("mrr_mean", "mean"),
            rank_percentile_mean=("rank_percentile_mean", "mean"),
            spearman_mean=("spearman_mean", "mean"),
            kendall_mean=("kendall_mean", "mean"),
        ),
        on=["mode", "pool_size"],
        how="left",
    )
    candidate_summary.to_csv(source_data / "candidate_pool_summary.csv", index=False)

    source_files = {
        "tdc_gate_audit.csv": ROOT / "results" / "external_panels" / "tdc_gate_audit.csv",
        "risk_coverage_metrics.csv": ROOT / "results" / "reliability" / "risk_coverage_metrics.csv",
        "conformal_long.csv": ROOT / "results" / "reliability" / "conformal_long.csv",
        "moleculeace_inclusion.csv": ROOT / "results" / "external_panels" / "moleculeace_inclusion.csv",
        "repeated_nested_bootstrap.csv": ROOT / "results" / "statistics" / "repeated_nested_bootstrap.csv",
        "repeated_stability_metrics.csv": ROOT / "results" / "nested_selection" / "repeated_stability_metrics.csv",
        "autogluon_budget.csv": ROOT / "results" / "external_panels" / "autogluon_budget.csv",
        "autogluon_budget_outer_long.csv": ROOT / "results" / "external_panels" / "autogluon_budget_outer_long.csv",
        "governance_ablation.csv": ROOT / "results" / "nested_selection" / "governance_ablation.csv",
        "family_removal.csv": ROOT / "results" / "nested_selection" / "family_removal.csv",
        "ablation_summary.csv": ROOT / "results" / "source_data" / "ablation_summary.csv",
        "data_cleaning_flow.csv": ROOT / "results" / "audits" / "data_cleaning_flow.csv",
        "heterogeneous_pool_results.csv": ROOT / "results" / "nested_selection" / "heterogeneous_pool_results.csv",
    }
    loaded: dict[str, pd.DataFrame] = {}
    for name, path in source_files.items():
        loaded[name] = pd.read_csv(path)
        loaded[name].to_csv(source_data / name, index=False)

    values = build_manuscript_values(endpoint, bootstrap)
    gate = loaded["tdc_gate_audit.csv"]
    risk = loaded["risk_coverage_metrics.csv"]
    conformal = loaded["conformal_long.csv"]
    moleculeace = loaded["moleculeace_inclusion.csv"]
    repeated = loaded["repeated_nested_bootstrap.csv"]
    repeated_stability = loaded["repeated_stability_metrics.csv"]
    autogluon = loaded["autogluon_budget.csv"]
    autogluon_outer = loaded["autogluon_budget_outer_long.csv"]
    ablation_summary = loaded["ablation_summary.csv"]
    cleaning = loaded["data_cleaning_flow.csv"]
    heterogeneous = loaded["heterogeneous_pool_results.csv"]
    repeated_values: dict[str, object] = {}
    for pool_size, group in repeated.groupby("pool_size"):
        repeated_values[str(int(pool_size))] = {
            str(row.metric): {
                "mean": float(row.mean),
                "ci95_low": float(row.ci95_low),
                "ci95_high": float(row.ci95_high),
            }
            for row in group.itertuples(index=False)
        }
    stability_values = {
        str(int(pool_size)): {
            "modal_selection_rate_mean": float(group["modal_selection_rate"].mean()),
            "normalized_entropy_mean": float(group["normalized_entropy"].mean()),
            "family_stability_mean": float(group["family_stability"].mean()),
            "pairwise_jaccard_mean": float(group["pairwise_jaccard"].mean()),
        }
        for pool_size, group in repeated_stability.groupby("pool_size")
    }
    autogluon_values: dict[str, object] = {}
    for budget, group in autogluon.groupby("budget_seconds"):
        outer_group = autogluon_outer.loc[autogluon_outer["budget_seconds"].eq(budget)]
        comparisons = {}
        for policy in ("fixed_single", "validation_best", "one_se_stable", "risk_adjusted"):
            delta = group[f"delta_vs_{policy}"]
            comparisons[policy] = {
                "wins": int((delta > 1e-12).sum()),
                "ties": int((delta.abs() <= 1e-12).sum()),
                "losses": int((delta < -1e-12).sum()),
                "mean_utility_delta": float(delta.mean()),
            }
        autogluon_values[str(int(budget))] = {
            "n_endpoints": int(group["dataset"].nunique()),
            "n_outer_folds": int(len(outer_group)),
            "actual_fit_seconds_total": float(outer_group["fit_seconds"].sum()),
            "model_count_mean": float(outer_group["model_count"].mean()),
            "peak_rss_mb_max": float(outer_group["peak_rss_mb"].max()),
            "comparisons": comparisons,
        }
    values.update(
        {
            "tdc_gate": {
                "promoted": int(gate["promoted"].sum()),
                "retained": int((~gate["promoted"]).sum()),
                "category_counts": gate["gate_category"].value_counts().to_dict(),
            },
            "risk_coverage": {
                task: {
                    "median_aurc": float(group["aurc"].median()),
                    "median_e_aurc": float(group["e_aurc"].median()),
                }
                for task, group in risk.groupby("task_type")
            },
            "conformal": {
                f"{task}_{target:.2f}": {
                    "mean_coverage": float(group["coverage"].mean()),
                    "mean_normalized_width_sd": finite_or_none(group["normalized_width_sd"].mean()) if "normalized_width_sd" in group else None,
                    "mean_class_0_coverage": finite_or_none(group["class_0_coverage"].mean()) if "class_0_coverage" in group else None,
                    "mean_class_1_coverage": finite_or_none(group["class_1_coverage"].mean()) if "class_1_coverage" in group else None,
                    "fallback_count": int(group["fallback_reason"].notna().sum()) if "fallback_reason" in group else 0,
                }
                for (task, target), group in conformal.groupby(["task_type", "target_coverage"])
            },
            "moleculeace": {
                "available_tasks": int(len(moleculeace)),
                "included_tasks": int(moleculeace["status"].eq("included").sum()),
                "failed_tasks": int(moleculeace["status"].eq("failed").sum()),
            },
            "repeated_nested": repeated_values,
            "repeated_stability": stability_values,
            "autogluon_budget": autogluon_values,
            "ablation": {
                ablation_class: {
                    str(row.variant): {
                        "mean_fixed_regret": float(row.mean_fixed_regret),
                        "ci95_low": float(row.ci95_low),
                        "ci95_high": float(row.ci95_high),
                    }
                    for row in group.itertuples(index=False)
                }
                for ablation_class, group in ablation_summary.groupby("ablation_class")
            },
            "data_cleaning": {
                "n_endpoints": int(len(cleaning)),
                "input_count": int(cleaning["input_count"].sum()),
                "output_count": int(cleaning["output_count"].sum()),
                "invalid_smiles": int(cleaning["invalid_smiles"].sum()),
                "duplicate_consistent_merged": int(cleaning["duplicate_consistent_merged"].sum()),
                "duplicate_conflict_excluded": int(cleaning["duplicate_conflict_excluded"].sum()),
            },
            "heterogeneous_pool": {
                "confirmatory_completed": bool(heterogeneous["status"].eq("completed").all()),
                "status_counts": heterogeneous["status"].value_counts().to_dict(),
                "claim_action": str(heterogeneous["claim_action"].dropna().iloc[0]),
            },
        }
    )
    (ROOT / "results" / "manuscript_values.json").write_text(
        json.dumps(values, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(candidate_summary.to_string(index=False))


if __name__ == "__main__":
    main()
