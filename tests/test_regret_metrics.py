from __future__ import annotations

import math

import pytest

from fzyc_mol.selection.regret_metrics import regret_decomposition


def test_fixed_denominator_is_shared_across_candidate_subsets() -> None:
    full = {"a": 0.9, "b": 0.7, "c": 0.4, "d": 0.1}
    small = regret_decomposition(
        pool_test_utility={"a": 0.9, "b": 0.7},
        full_test_utility=full,
        selected_id="b",
        baseline_id="b",
    )
    large = regret_decomposition(
        pool_test_utility={"a": 0.9, "b": 0.7, "c": 0.4},
        full_test_utility=full,
        selected_id="b",
        baseline_id="b",
    )

    assert small["full_range"] == pytest.approx(0.8)
    assert large["full_range"] == pytest.approx(0.8)
    assert small["fixed_normalized_regret"] == pytest.approx(0.25)
    assert large["fixed_normalized_regret"] == pytest.approx(0.25)


def test_decomposes_selected_oracle_baseline_and_gain() -> None:
    result = regret_decomposition(
        pool_test_utility={"a": 0.8, "b": 0.6, "c": 0.3},
        full_test_utility={"a": 0.8, "b": 0.6, "c": 0.3, "d": 0.0},
        selected_id="b",
        baseline_id="c",
    )

    assert result["selected_test_utility"] == pytest.approx(0.6)
    assert result["oracle_test_utility"] == pytest.approx(0.8)
    assert result["baseline_test_utility"] == pytest.approx(0.3)
    assert result["raw_regret"] == pytest.approx(0.2)
    assert result["selection_gain_vs_baseline"] == pytest.approx(0.3)
    assert result["dynamic_normalized_regret"] == pytest.approx(0.4)


def test_zero_ranges_return_nan_and_record_reason() -> None:
    result = regret_decomposition(
        pool_test_utility={"a": 0.5, "b": 0.5},
        full_test_utility={"a": 0.5, "b": 0.5},
        selected_id="a",
        baseline_id="b",
    )

    assert math.isnan(result["fixed_normalized_regret"])
    assert math.isnan(result["dynamic_normalized_regret"])
    assert result["normalization_status"] == "zero_full_range"


def test_missing_candidate_is_rejected() -> None:
    with pytest.raises(KeyError):
        regret_decomposition({"a": 1.0}, {"a": 1.0}, "missing", "a")
