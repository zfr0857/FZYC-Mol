from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.build_stage_b_core_metrics import build_outputs


def test_build_outputs_writes_required_stage_b_files(tmp_path: Path) -> None:
    source = tmp_path / "reports" / "draft10_core_experiments_20260621" / "expanded_nested"
    source.mkdir(parents=True)
    registry = pd.DataFrame(
        {
            "dataset": ["demo", "demo"],
            "task_type": ["classification", "classification"],
            "candidate_order": [1, 2],
            "candidate": ["a", "b"],
            "family": ["linear", "tree"],
        }
    )
    inner = pd.DataFrame(
        {
            "dataset": ["demo"] * 6,
            "task_type": ["classification"] * 6,
            "outer_fold": [1] * 6,
            "inner_fold": [1, 2, 3] * 2,
            "candidate": ["a"] * 3 + ["b"] * 3,
            "inner_utility": [0.8, 0.79, 0.8, 0.7, 0.71, 0.69],
            "fit_seconds": [1.0] * 6,
        }
    )
    outer = pd.DataFrame(
        {
            "dataset": ["demo", "demo"],
            "task_type": ["classification", "classification"],
            "outer_fold": [1, 1],
            "candidate": ["a", "b"],
            "outer_utility": [0.8, 0.7],
        }
    )
    registry.to_csv(source / "candidate_registry.csv", index=False)
    inner.to_csv(source / "inner_scores.csv", index=False)
    outer.to_csv(source / "outer_candidate_scores.csv", index=False)

    paths = build_outputs(tmp_path, pool_sizes=(2,))

    assert paths["ranking"].exists()
    assert paths["regret"].exists()
    assert paths["decisions"].exists()
    assert len(pd.read_csv(paths["ranking"])) == 1
