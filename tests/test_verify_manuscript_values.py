from __future__ import annotations

from scripts.verify_manuscript_values import compare_values
import math


def test_value_comparison_reports_zero_for_equal_nested_values() -> None:
    expected = {"a": {"b": 1.0}, "c": 2}
    actual = {"a": {"b": 1.0 + 1e-10}, "c": 2}

    assert compare_values(expected, actual, tolerance=1e-8) == []


def test_value_comparison_reports_path_for_difference() -> None:
    differences = compare_values({"a": {"b": 1.0}}, {"a": {"b": 1.2}}, tolerance=1e-8)

    assert differences[0]["path"] == "a.b"


def test_nan_values_compare_equal() -> None:
    assert compare_values({"value": math.nan}, {"value": math.nan}) == []
