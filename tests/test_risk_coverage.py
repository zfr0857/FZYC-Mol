from __future__ import annotations

import math

import numpy as np
import pytest

from fzyc_mol.reliability.risk_coverage import risk_coverage_audit


def test_regression_uses_root_mean_squared_error() -> None:
    result = risk_coverage_audit(
        y_true=[0, 0, 0, 0],
        prediction=[0, 1, 2, 3],
        risk_score=[0, 1, 2, 3],
        task_type="regression",
        coverages=[0.5, 1.0],
    )

    assert result.curve.iloc[-1]["risk"] == pytest.approx(math.sqrt(3.5))
    assert result.e_aurc == pytest.approx(0.0)


def test_perfect_classification_risk_ranking_matches_oracle() -> None:
    result = risk_coverage_audit(
        y_true=[0, 1, 0, 1],
        prediction=[0.1, 0.9, 0.8, 0.2],
        risk_score=[0.0, 0.1, 0.9, 0.8],
        task_type="classification",
        coverages=[0.5, 0.75, 1.0],
    )

    assert result.e_aurc == pytest.approx(0.0)
    assert result.curve.iloc[0]["risk"] == pytest.approx(0.0)


def test_invalid_coverage_or_lengths_are_rejected() -> None:
    with pytest.raises(ValueError):
        risk_coverage_audit([0], [0], [0], task_type="regression", coverages=[0])
    with pytest.raises(ValueError):
        risk_coverage_audit([0, 1], [0], [0], task_type="classification")
