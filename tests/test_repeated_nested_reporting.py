from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.build_repeated_nested_outputs import build_outputs


def write_repeat(root: Path, seed: int) -> None:
    folder = root / "results" / "nested_selection" / "repeated_nested" / f"seed_{seed}"
    folder.mkdir(parents=True)
    pd.DataFrame(
        {
            "dataset": ["demo", "demo"],
            "task_type": ["classification", "classification"],
            "candidate_order": [1, 2],
            "candidate": ["a", "b"],
            "family": ["linear", "tree"],
        }
    ).to_csv(folder / "candidate_registry.csv", index=False)
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
    ).to_csv(folder / "inner_scores.csv", index=False)
    pd.DataFrame(
        {
            "dataset": ["demo", "demo"],
            "task_type": ["classification", "classification"],
            "outer_fold": [1, 1],
            "candidate": ["a", "b"],
            "outer_utility": [0.8, 0.7],
        }
    ).to_csv(folder / "outer_candidate_scores.csv", index=False)


def test_combines_isolated_repeat_outputs(tmp_path: Path) -> None:
    write_repeat(tmp_path, 11)
    write_repeat(tmp_path, 23)

    paths = build_outputs(tmp_path, seeds=(11, 23), pool_sizes=(2,))

    regret = pd.read_csv(paths["regret"])
    assert set(regret["repeat_seed"]) == {11, 23}
    assert len(regret) == 2
    stability = pd.read_csv(paths["stability"])
    assert stability.iloc[0]["n_selections"] == 2
    assert 0.0 <= stability.iloc[0]["normalized_entropy"] <= 1.0
    assert all(path.exists() for path in paths.values())
