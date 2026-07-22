from __future__ import annotations

import numpy as np
import pytest

from fzyc_mol.reliability.conformal import (
    classification_prediction_sets,
    fit_label_conditional,
    normalized_interval_width,
)


def test_label_conditional_thresholds_are_fitted_per_class() -> None:
    y = np.array([0, 0, 0, 1, 1, 1])
    proba = np.array([[0.9, 0.1], [0.8, 0.2], [0.7, 0.3], [0.4, 0.6], [0.3, 0.7], [0.2, 0.8]])
    fit = fit_label_conditional(y, proba, alpha=0.2, min_class_count=3)

    assert set(fit.thresholds) == {0, 1}
    assert fit.class_counts == {0: 3, 1: 3}
    assert fit.fallback_reason is None
    sets = classification_prediction_sets(np.array([[0.75, 0.25]]), fit.thresholds)
    assert sets == [(0,)]


def test_small_class_falls_back_to_pooled_with_reason() -> None:
    y = np.array([0, 0, 0, 1])
    proba = np.array([[0.9, 0.1], [0.8, 0.2], [0.7, 0.3], [0.4, 0.6]])
    fit = fit_label_conditional(y, proba, alpha=0.1, min_class_count=2)

    assert fit.fallback_reason == "class_1_count_1_below_2"
    assert fit.thresholds[0] == fit.thresholds[1]


def test_regression_width_is_normalized_per_endpoint() -> None:
    widths = np.array([2.0, 4.0])
    train = np.array([0.0, 1.0, 2.0, 3.0])

    result = normalized_interval_width(widths, train)

    assert result["width_sd"].shape == (2,)
    assert result["width_iqr"].tolist() == pytest.approx([4 / 3, 8 / 3])
