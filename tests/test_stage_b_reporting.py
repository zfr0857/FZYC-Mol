from __future__ import annotations

import pandas as pd

from fzyc_mol.reporting.stage_b import build_stage_b_outputs


def test_builds_long_form_ranking_regret_and_decision_outputs() -> None:
    registry = pd.DataFrame(
        {
            "dataset": ["demo"] * 3,
            "task_type": ["classification"] * 3,
            "candidate_order": [1, 2, 3],
            "candidate": ["a", "b", "c"],
            "family": ["linear", "tree", "boosting"],
        }
    )
    inner = pd.DataFrame(
        {
            "dataset": ["demo"] * 9,
            "task_type": ["classification"] * 9,
            "outer_fold": [1] * 9,
            "inner_fold": [1, 2, 3] * 3,
            "candidate": ["a"] * 3 + ["b"] * 3 + ["c"] * 3,
            "inner_utility": [0.8, 0.79, 0.8, 0.81, 0.77, 0.79, 0.5, 0.55, 0.52],
            "fit_seconds": [3.0] * 3 + [2.0] * 3 + [1.0] * 3,
        }
    )
    outer = pd.DataFrame(
        {
            "dataset": ["demo"] * 3,
            "task_type": ["classification"] * 3,
            "outer_fold": [1] * 3,
            "candidate": ["a", "b", "c"],
            "outer_utility": [0.7, 0.6, 0.9],
        }
    )

    ranking, regret, decisions = build_stage_b_outputs(inner, outer, registry, pool_sizes=(2, 3))

    assert list(ranking["pool_size"]) == [2, 3]
    assert set(ranking["subset_id"]) == {"fixed_prefix_k2", "fixed_prefix_k3"}
    assert list(regret["selected_candidate"]) == ["a", "a"]
    assert regret["full_range"].nunique() == 1
    assert list(decisions["status"]) == ["completed", "completed"]
    assert "selection_frequency" in decisions.iloc[0]["selection_reason"]
