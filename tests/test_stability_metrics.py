from __future__ import annotations

import pytest

from fzyc_mol.selection.stability_metrics import mean_pairwise_jaccard, selection_stability


def test_complete_stability_has_zero_entropy() -> None:
    result = selection_stability(["a", "a", "a"], {"a": "tree", "b": "linear"}, available_candidates=["a", "b"])

    assert result["normalized_entropy"] == pytest.approx(0.0)
    assert result["modal_selection_rate"] == pytest.approx(1.0)
    assert result["family_stability"] == pytest.approx(1.0)


def test_uniform_selection_has_unit_entropy() -> None:
    result = selection_stability(["a", "b", "c", "d"], {"a": "x", "b": "y", "c": "z", "d": "w"}, available_candidates=["a", "b", "c", "d"])

    assert result["normalized_entropy"] == pytest.approx(1.0)
    assert result["family_stability"] == pytest.approx(0.25)


def test_pairwise_jaccard_measures_top_set_stability() -> None:
    value = mean_pairwise_jaccard([{"a", "b"}, {"a", "c"}, {"a", "b"}])

    assert value == pytest.approx((1 / 3 + 1 + 1 / 3) / 3)
