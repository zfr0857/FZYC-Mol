from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.build_stage_e_figures import build_figures


def test_stage_e_figures_are_built_from_source_tables(tmp_path: Path) -> None:
    candidate = pd.DataFrame(
        {
            "mode": ["random_subset", "random_subset"],
            "pool_size": [4, 8],
            "mean": [0.1, 0.2],
            "ci95_low": [0.05, 0.1],
            "ci95_high": [0.15, 0.3],
            "chance_adjusted_hit_mean": [0.7, 0.5],
            "rank_percentile_mean": [0.8, 0.7],
        }
    )
    tdc = pd.DataFrame({"gate_category": ["promoted_and_improved", "retained_and_avoided_harm"]})
    conformal = pd.DataFrame(
        {"task_type": ["regression", "regression"], "target_coverage": [0.8, 0.9], "coverage": [0.82, 0.91]}
    )

    paths = build_figures(candidate, tdc, conformal, tmp_path)

    assert len(paths) == 3
    assert all(path.exists() and path.stat().st_size > 0 for path in paths.values())
