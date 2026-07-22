from __future__ import annotations

import pandas as pd

from scripts.build_conformal_activity_reports import classification_conformal, regression_conformal


def test_classification_report_exposes_class_conditional_diagnostics() -> None:
    valid = pd.DataFrame({"y_true": [0, 0, 1, 1], "y_pred": [0.1, 0.2, 0.8, 0.9]})
    test = pd.DataFrame({"y_true": [0, 1], "y_pred": [0.2, 0.8]})

    result = classification_conformal(valid, test, alpha=0.2)

    assert "qhat_y0" in result and "qhat_y1" in result
    assert "class_0_coverage" in result and "class_1_coverage" in result
    assert "fallback_reason" in result


def test_regression_report_normalizes_width_and_adds_interval_score() -> None:
    valid = pd.DataFrame({"y_true": [0.0, 1.0, 2.0], "y_pred": [0.0, 1.1, 1.9]})
    test = pd.DataFrame({"y_true": [0.5, 1.5], "y_pred": [0.6, 1.4]})

    result = regression_conformal(valid, test, alpha=0.1, y_train=[0.0, 1.0, 2.0, 3.0])

    assert result["normalized_width_sd"] > 0
    assert result["normalized_width_iqr"] > 0
    assert result["interval_score"] > 0
