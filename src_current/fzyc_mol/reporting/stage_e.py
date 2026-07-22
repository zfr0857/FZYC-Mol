from __future__ import annotations

import numpy as np
import pandas as pd

from fzyc_mol.selection.stability_metrics import mean_pairwise_jaccard, selection_stability
from fzyc_mol.statistics.hierarchical_bootstrap import hierarchical_bootstrap


def build_manuscript_values(endpoint_summary: pd.DataFrame, bootstrap_summary: pd.DataFrame) -> dict[str, object]:
    values: dict[str, object] = {"candidate_pool": {}}
    candidate_pool: dict[str, dict[str, dict[str, float | int]]] = values["candidate_pool"]  # type: ignore[assignment]
    for row in bootstrap_summary.itertuples(index=False):
        mode_values = candidate_pool.setdefault(str(row.mode), {})
        endpoint = endpoint_summary[
            endpoint_summary["mode"].eq(row.mode) & endpoint_summary["pool_size"].eq(row.pool_size)
        ]
        mode_values[str(int(row.pool_size))] = {
            "n_endpoints": int(row.n_endpoints),
            "fixed_regret_mean": float(row.mean),
            "fixed_regret_median": float(row.median),
            "fixed_regret_iqr": float(row.iqr),
            "fixed_regret_ci95_low": float(row.ci95_low),
            "fixed_regret_ci95_high": float(row.ci95_high),
            "chance_adjusted_hit_mean": float(endpoint["chance_adjusted_hit_mean"].mean()),
            "mrr_mean": float(endpoint["mrr_mean"].mean()),
            "rank_percentile_mean": float(endpoint["rank_percentile_mean"].mean()),
        }
    return values


def build_stage_e_outputs(
    regret: pd.DataFrame,
    ranking: pd.DataFrame,
    decisions: pd.DataFrame,
    registry: pd.DataFrame,
    *,
    bootstrap_replicates: int = 5000,
    seed: int = 20260622,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build endpoint summaries, hierarchical intervals and stability metrics."""

    regret = regret.copy()
    ranking = ranking.copy()
    regret["_unit"] = regret["split_id"].astype(str) + ":subset" + regret["subset_seed"].astype(str)
    ranking["_unit"] = ranking["split_id"].astype(str) + ":subset" + ranking["subset_seed"].astype(str)
    regret_endpoint = (
        regret.groupby(["endpoint", "mode", "pool_size"], as_index=False)
        .agg(
            n_units=("_unit", "nunique"),
            fixed_regret_mean=("fixed_normalized_regret", "mean"),
            fixed_regret_median=("fixed_normalized_regret", "median"),
            fixed_regret_q1=("fixed_normalized_regret", lambda values: float(np.quantile(values, 0.25))),
            fixed_regret_q3=("fixed_normalized_regret", lambda values: float(np.quantile(values, 0.75))),
            raw_regret_mean=("raw_regret", "mean"),
            selection_gain_mean=("selection_gain_vs_baseline", "mean"),
        )
    )
    rank_endpoint = (
        ranking.groupby(["endpoint", "mode", "pool_size"], as_index=False)
        .agg(
            chance_adjusted_hit_mean=("chance_adjusted_hit", "mean"),
            mrr_mean=("mrr", "mean"),
            rank_percentile_mean=("rank_percentile", "mean"),
            spearman_mean=("spearman", "mean"),
            kendall_mean=("kendall", "mean"),
        )
    )
    endpoint_summary = regret_endpoint.merge(rank_endpoint, on=["endpoint", "mode", "pool_size"], how="outer")

    bootstrap_rows = []
    for (mode, pool_size), group in regret.groupby(["mode", "pool_size"], sort=True):
        result = hierarchical_bootstrap(
            group,
            endpoint_col="endpoint",
            unit_col="_unit",
            value_col="fixed_normalized_regret",
            replicates=bootstrap_replicates,
            seed=seed + int(pool_size),
        )
        bootstrap_rows.append(
            {
                "mode": mode,
                "pool_size": int(pool_size),
                "metric": "fixed_normalized_regret",
                "primary_cluster_unit": "endpoint",
                "n_endpoints": result.n_endpoints,
                "mean": result.estimate,
                "median": result.median,
                "iqr": result.iqr,
                "ci95_low": result.ci_low,
                "ci95_high": result.ci_high,
                "bootstrap_replicates": bootstrap_replicates,
            }
        )

    family = registry.drop_duplicates("candidate").set_index("candidate")["family"].astype(str).to_dict()
    stability_rows = []
    for (endpoint, mode, pool_size), group in decisions.groupby(["endpoint", "mode", "pool_size"], sort=True):
        selected = group["selected_candidate"].dropna().astype(str).tolist()
        if "dataset" in registry.columns:
            available = (
                registry.loc[registry["dataset"].eq(endpoint), "candidate"].drop_duplicates().astype(str).tolist()
            )
        else:
            available = registry["candidate"].drop_duplicates().astype(str).tolist()
        stats = selection_stability(selected, family, available_candidates=available)
        top_sets = [set(str(value).split(";")) - {""} for value in group["one_se_candidates"].fillna("")]
        stability_rows.append(
            {
                "endpoint": endpoint,
                "mode": mode,
                "pool_size": int(pool_size),
                **stats,
                "pairwise_jaccard": mean_pairwise_jaccard(top_sets),
            }
        )
    return endpoint_summary, pd.DataFrame(bootstrap_rows), pd.DataFrame(stability_rows)
