from __future__ import annotations

import pandas as pd

from fzyc_mol.reporting.stage_e import build_manuscript_values, build_stage_e_outputs


def test_stage_e_outputs_are_endpoint_clustered() -> None:
    regret = pd.DataFrame(
        {
            "endpoint": ["a", "a", "b", "b"],
            "mode": ["random_subset"] * 4,
            "pool_size": [2] * 4,
            "split_id": ["a1", "a2", "b1", "b2"],
            "subset_seed": [1, 2, 1, 2],
            "fixed_normalized_regret": [0.1, 0.2, 0.3, 0.4],
            "raw_regret": [0.01, 0.02, 0.03, 0.04],
            "selection_gain_vs_baseline": [0.2, 0.2, 0.1, 0.1],
        }
    )
    ranking = regret[["endpoint", "mode", "pool_size", "split_id", "subset_seed"]].copy()
    ranking["chance_adjusted_hit"] = [1, 0, 0, -1]
    ranking["mrr"] = [1, 0.5, 0.5, 0.25]
    ranking["rank_percentile"] = [1, 0.5, 0.5, 0]
    ranking["spearman"] = [1, 0, 0, -1]
    ranking["kendall"] = [1, 0, 0, -1]
    decisions = regret[["endpoint", "mode", "pool_size", "split_id", "subset_seed"]].copy()
    decisions["selected_candidate"] = ["x", "x", "y", "z"]
    decisions["one_se_candidates"] = ["x;y", "x", "y;z", "z"]
    registry = pd.DataFrame({"candidate": ["x", "y", "z"], "family": ["linear", "tree", "tree"]})

    endpoint, bootstrap, stability = build_stage_e_outputs(
        regret, ranking, decisions, registry, bootstrap_replicates=100, seed=1
    )

    assert len(endpoint) == 2
    assert len(bootstrap) == 1
    assert bootstrap.iloc[0]["n_endpoints"] == 2
    assert len(stability) == 2
    assert "pairwise_jaccard" in stability

    values = build_manuscript_values(endpoint, bootstrap)
    assert values["candidate_pool"]["random_subset"]["2"]["fixed_regret_mean"] == bootstrap.iloc[0]["mean"]


def test_randomized_subset_entropy_uses_full_available_registry() -> None:
    base = pd.DataFrame(
        {
            "endpoint": ["a"] * 3,
            "mode": ["random_subset"] * 3,
            "pool_size": [2] * 3,
            "split_id": ["a1", "a2", "a3"],
            "subset_seed": [1, 2, 3],
        }
    )
    regret = base.assign(
        fixed_normalized_regret=0.1,
        raw_regret=0.01,
        selection_gain_vs_baseline=0.0,
    )
    ranking = base.assign(
        chance_adjusted_hit=0.0,
        mrr=0.5,
        rank_percentile=0.5,
        spearman=0.0,
        kendall=0.0,
    )
    decisions = base.assign(
        selected_candidate=["x", "y", "z"],
        one_se_candidates=["x", "y", "z"],
    )
    registry = pd.DataFrame(
        {"dataset": ["a"] * 4, "candidate": ["x", "y", "z", "w"], "family": ["f"] * 4}
    )

    _, _, stability = build_stage_e_outputs(
        regret, ranking, decisions, registry, bootstrap_replicates=10, seed=1
    )

    assert 0.0 <= stability.iloc[0]["normalized_entropy"] <= 1.0
