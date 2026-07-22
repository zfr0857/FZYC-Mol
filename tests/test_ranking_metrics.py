from __future__ import annotations

import math

import numpy as np
import pytest

from fzyc_mol.selection.ranking_metrics import ranking_audit


def test_perfect_ranking_has_perfect_fidelity() -> None:
    result = ranking_audit([4, 3, 2, 1], [40, 30, 20, 10])

    assert result["oracle_validation_rank"] == 1
    assert result["top1_hit"] == 1
    assert result["top3_hit"] == 1
    assert result["top_fraction_hit"] == 1
    assert result["chance_adjusted_hit"] == pytest.approx(1.0)
    assert result["mrr"] == pytest.approx(1.0)
    assert result["rank_percentile"] == pytest.approx(1.0)
    assert result["ndcg"] == pytest.approx(1.0)
    assert result["spearman"] == pytest.approx(1.0)
    assert result["kendall"] == pytest.approx(1.0)


def test_inverse_ranking_can_be_worse_than_random() -> None:
    result = ranking_audit([4, 3, 2, 1], [10, 20, 30, 40])

    assert result["oracle_validation_rank"] == 4
    assert result["top3_hit"] == 0
    assert result["chance_adjusted_hit"] == pytest.approx(-3.0)
    assert result["mrr"] == pytest.approx(0.25)
    assert result["rank_percentile"] == pytest.approx(0.0)
    assert result["spearman"] == pytest.approx(-1.0)
    assert result["kendall"] == pytest.approx(-1.0)


@pytest.mark.parametrize("k", [1, 2, 3])
def test_small_pools_have_defined_chance_adjustment(k: int) -> None:
    result = ranking_audit(np.arange(k, 0, -1), np.arange(k, 0, -1))

    assert result["top3_hit"] == 1
    assert result["chance_hit"] == pytest.approx(1.0)
    assert result["chance_adjusted_hit"] == pytest.approx(0.0)
    assert math.isfinite(result["rank_percentile"])


def test_k32_random_baseline_is_three_over_thirty_two() -> None:
    validation = np.arange(32, 0, -1)
    test = np.arange(1, 33)
    result = ranking_audit(validation, test)

    assert result["chance_hit"] == pytest.approx(3 / 32)
    assert result["top_fraction_k"] == 8


def test_rejects_non_finite_or_mismatched_inputs() -> None:
    with pytest.raises(ValueError):
        ranking_audit([1, 2], [1])
    with pytest.raises(ValueError):
        ranking_audit([1, np.nan], [1, 2])
