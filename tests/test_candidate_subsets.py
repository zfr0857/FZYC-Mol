from __future__ import annotations

from collections import Counter

import pandas as pd
import pytest

from fzyc_mol.selection.candidate_subsets import build_subset


@pytest.fixture
def registry() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "candidate_id": [f"c{i}" for i in range(12)],
            "family": ["linear"] * 3 + ["tree"] * 3 + ["boosting"] * 6,
            "registry_order": list(range(1, 13)),
        }
    )


@pytest.mark.parametrize("mode", ["random_order", "random_subset", "family_balanced"])
def test_same_seed_is_exactly_reproducible(registry: pd.DataFrame, mode: str) -> None:
    first = build_subset(registry, 6, mode=mode, seed=17, force_include=("c0",))
    second = build_subset(registry, 6, mode=mode, seed=17, force_include=("c0",))

    assert first == second
    assert len(first.candidate_ids) == 6
    assert len(set(first.candidate_ids)) == 6
    assert "c0" in first.candidate_ids


def test_different_seed_changes_random_subset(registry: pd.DataFrame) -> None:
    first = build_subset(registry, 6, mode="random_subset", seed=17, force_include=("c0",))
    second = build_subset(registry, 6, mode="random_subset", seed=23, force_include=("c0",))

    assert first.candidate_ids != second.candidate_ids


def test_family_balanced_tracks_registry_proportions(registry: pd.DataFrame) -> None:
    subset = build_subset(registry, 6, mode="family_balanced", seed=11)
    counts = Counter(registry.set_index("candidate_id").loc[list(subset.candidate_ids), "family"])

    assert abs(counts["linear"] - 1.5) <= 1
    assert abs(counts["tree"] - 1.5) <= 1
    assert abs(counts["boosting"] - 3.0) <= 1


def test_full_pool_contains_every_candidate(registry: pd.DataFrame) -> None:
    subset = build_subset(registry, 12, mode="random_order", seed=99, force_include=("c0",))

    assert set(subset.candidate_ids) == set(registry["candidate_id"])


def test_invalid_size_or_candidate_is_rejected(registry: pd.DataFrame) -> None:
    with pytest.raises(ValueError):
        build_subset(registry, 13, mode="random_subset", seed=1)
    with pytest.raises(KeyError):
        build_subset(registry, 4, mode="random_subset", seed=1, force_include=("missing",))
