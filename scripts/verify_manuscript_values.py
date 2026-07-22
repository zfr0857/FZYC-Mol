from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def compare_values(expected: Any, actual: Any, *, tolerance: float = 1e-8, path: str = "") -> list[dict[str, object]]:
    if isinstance(expected, dict) and isinstance(actual, dict):
        differences = []
        for key in sorted(set(expected) | set(actual)):
            child = f"{path}.{key}" if path else str(key)
            if key not in expected or key not in actual:
                differences.append({"path": child, "expected": expected.get(key), "actual": actual.get(key)})
            else:
                differences.extend(compare_values(expected[key], actual[key], tolerance=tolerance, path=child))
        return differences
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        equal = (math.isnan(float(expected)) and math.isnan(float(actual))) or math.isclose(
            float(expected), float(actual), rel_tol=tolerance, abs_tol=tolerance
        )
    else:
        equal = expected == actual
    return [] if equal else [{"path": path, "expected": expected, "actual": actual}]


def rebuild_values(root: Path = ROOT) -> dict[str, object]:
    candidate = pd.read_csv(root / "results" / "source_data" / "candidate_pool_summary.csv")
    candidate_pool: dict[str, dict[str, dict[str, float | int]]] = {}
    for row in candidate.itertuples(index=False):
        candidate_pool.setdefault(str(row.mode), {})[str(int(row.pool_size))] = {
            "n_endpoints": int(row.n_endpoints),
            "fixed_regret_mean": float(row.mean),
            "fixed_regret_median": float(row.median),
            "fixed_regret_iqr": float(row.iqr),
            "fixed_regret_ci95_low": float(row.ci95_low),
            "fixed_regret_ci95_high": float(row.ci95_high),
            "chance_adjusted_hit_mean": float(row.chance_adjusted_hit_mean),
            "mrr_mean": float(row.mrr_mean),
            "rank_percentile_mean": float(row.rank_percentile_mean),
        }
    gate = pd.read_csv(root / "results" / "source_data" / "tdc_gate_audit.csv")
    risk = pd.read_csv(root / "results" / "source_data" / "risk_coverage_metrics.csv")
    conformal = pd.read_csv(root / "results" / "source_data" / "conformal_long.csv")
    moleculeace = pd.read_csv(root / "results" / "source_data" / "moleculeace_inclusion.csv")
    repeated = pd.read_csv(root / "results" / "source_data" / "repeated_nested_bootstrap.csv")
    repeated_stability = pd.read_csv(root / "results" / "source_data" / "repeated_stability_metrics.csv")
    autogluon = pd.read_csv(root / "results" / "source_data" / "autogluon_budget.csv")
    autogluon_outer = pd.read_csv(root / "results" / "source_data" / "autogluon_budget_outer_long.csv")
    ablation_summary = pd.read_csv(root / "results" / "source_data" / "ablation_summary.csv")
    cleaning = pd.read_csv(root / "results" / "source_data" / "data_cleaning_flow.csv")
    heterogeneous = pd.read_csv(root / "results" / "source_data" / "heterogeneous_pool_results.csv")
    repeated_values: dict[str, object] = {}
    for pool_size, group in repeated.groupby("pool_size"):
        repeated_values[str(int(pool_size))] = {
            str(row.metric): {"mean": float(row.mean), "ci95_low": float(row.ci95_low), "ci95_high": float(row.ci95_high)}
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

    def finite_or_none(value: float) -> float | None:
        return float(value) if math.isfinite(float(value)) else None
    return {
        "candidate_pool": candidate_pool,
        "tdc_gate": {
            "promoted": int(gate["promoted"].sum()),
            "retained": int((~gate["promoted"]).sum()),
            "category_counts": gate["gate_category"].value_counts().to_dict(),
        },
        "risk_coverage": {
            task: {"median_aurc": float(group["aurc"].median()), "median_e_aurc": float(group["e_aurc"].median())}
            for task, group in risk.groupby("task_type")
        },
        "conformal": {
            f"{task}_{target:.2f}": {
                "mean_coverage": float(group["coverage"].mean()),
                "mean_normalized_width_sd": finite_or_none(group["normalized_width_sd"].mean()),
                "mean_class_0_coverage": finite_or_none(group["class_0_coverage"].mean()),
                "mean_class_1_coverage": finite_or_none(group["class_1_coverage"].mean()),
                "fallback_count": int(group["fallback_reason"].notna().sum()),
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


def main() -> None:
    expected = json.loads((ROOT / "results" / "manuscript_values.json").read_text(encoding="utf-8"))
    actual = rebuild_values()
    differences = compare_values(expected, actual)
    output = ROOT / "results" / "audits" / "manuscript_value_verification.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"difference_count": len(differences), "differences": differences}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"differences={len(differences)}")
    if differences:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
