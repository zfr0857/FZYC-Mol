from __future__ import annotations

import pandas as pd

from fzyc_mol.reporting.stage_c import build_stage_c_outputs


def test_builds_reproducible_subset_manifest_and_long_metrics() -> None:
    registry = pd.DataFrame(
        {
            "dataset": ["demo"] * 4,
            "task_type": ["classification"] * 4,
            "candidate_order": [1, 2, 3, 4],
            "candidate": ["a", "b", "c", "d"],
            "family": ["linear", "tree", "boosting", "boosting"],
        }
    )
    inner = pd.DataFrame(
        {
            "dataset": ["demo"] * 12,
            "task_type": ["classification"] * 12,
            "outer_fold": [1] * 12,
            "inner_fold": [1, 2, 3] * 4,
            "candidate": sum(([name] * 3 for name in ["a", "b", "c", "d"]), []),
            "inner_utility": [0.8, 0.79, 0.8, 0.75, 0.74, 0.76, 0.7, 0.69, 0.68, 0.6, 0.61, 0.62],
            "fit_seconds": [1.0] * 12,
        }
    )
    outer = pd.DataFrame(
        {
            "dataset": ["demo"] * 4,
            "task_type": ["classification"] * 4,
            "outer_fold": [1] * 4,
            "candidate": ["a", "b", "c", "d"],
            "outer_utility": [0.7, 0.9, 0.8, 0.6],
        }
    )

    manifest, ranking, regret, decisions = build_stage_c_outputs(
        inner,
        outer,
        registry,
        modes=("random_subset", "family_balanced"),
        pool_sizes=(2, 4),
        seeds=(11, 23),
    )

    assert len(manifest) == 8
    assert len(ranking) == 8
    assert len(regret) == 8
    assert len(decisions) == 8
    assert manifest["subset_id"].nunique() == 8
    assert manifest["candidate_ids"].str.contains("a").all()
    assert set(ranking["mode"]) == {"random_subset", "family_balanced"}
