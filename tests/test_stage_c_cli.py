from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.run_candidate_pool_audit import build_outputs


def test_stage_c_cli_writes_manifest_and_metrics(tmp_path: Path) -> None:
    source = tmp_path / "reports" / "draft10_core_experiments_20260621" / "expanded_nested"
    source.mkdir(parents=True)
    pd.DataFrame(
        {
            "dataset": ["demo", "demo"],
            "task_type": ["classification", "classification"],
            "candidate_order": [1, 2],
            "candidate": ["a", "b"],
            "family": ["linear", "tree"],
        }
    ).to_csv(source / "candidate_registry.csv", index=False)
    pd.DataFrame(
        {
            "dataset": ["demo"] * 6,
            "task_type": ["classification"] * 6,
            "outer_fold": [1] * 6,
            "inner_fold": [1, 2, 3] * 2,
            "candidate": ["a"] * 3 + ["b"] * 3,
            "inner_utility": [0.8, 0.79, 0.8, 0.7, 0.71, 0.69],
            "fit_seconds": [1.0] * 6,
        }
    ).to_csv(source / "inner_scores.csv", index=False)
    pd.DataFrame(
        {
            "dataset": ["demo", "demo"],
            "task_type": ["classification", "classification"],
            "outer_fold": [1, 1],
            "candidate": ["a", "b"],
            "outer_utility": [0.8, 0.7],
        }
    ).to_csv(source / "outer_candidate_scores.csv", index=False)

    paths = build_outputs(tmp_path, modes=("random_subset",), pool_sizes=(2,), seeds=(11,))

    assert all(path.exists() for path in paths.values())
    assert len(pd.read_csv(paths["manifest"])) == 1
