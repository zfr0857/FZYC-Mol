from __future__ import annotations

import pandas as pd

from fzyc_mol.reporting.stage_d import build_risk_coverage_outputs, build_tdc_gate_outputs


def test_tdc_gate_reporting_uses_paired_seed_deltas() -> None:
    retained = pd.DataFrame(
        {
            "dataset": ["a", "b"],
            "previous_model": ["base", "base"],
            "primary_direction": ["higher", "lower"],
            "retained_source": ["performance_mode", "previous_table14"],
        }
    )
    performance = pd.DataFrame(
        {"dataset": ["a", "a", "b", "b"], "seed": [1, 2, 1, 2], "primary_value": [0.8, 0.9, 0.5, 0.6]}
    )
    baseline = pd.DataFrame(
        {
            "dataset": ["a", "a", "b", "b"],
            "seed": [1, 2, 1, 2],
            "model": ["base"] * 4,
            "primary_value": [0.7, 0.8, 0.4, 0.5],
        }
    )

    audit, confusion = build_tdc_gate_outputs(retained, performance, baseline, bootstrap_replicates=100, seed=1)

    categories = audit.set_index("endpoint")["gate_category"].to_dict()
    assert categories["a"] == "promoted_and_improved"
    assert categories["b"] == "retained_and_avoided_harm"
    assert confusion["count"].sum() == 2


def test_risk_reporting_preserves_endpoint_seed_units() -> None:
    predictions = pd.DataFrame(
        {
            "source": ["x"] * 4,
            "dataset": ["demo"] * 4,
            "seed": [1] * 4,
            "y_true": [0.0, 0.0, 0.0, 0.0],
            "y_pred_calibrated": [0.0, 1.0, 2.0, 3.0],
            "risk_score": [0.0, 1.0, 2.0, 3.0],
        }
    )

    curve, metrics = build_risk_coverage_outputs(predictions, coverages=(0.5, 1.0))

    assert len(curve) == 2
    assert len(metrics) == 1
    assert metrics.iloc[0]["task_type"] == "regression"
    assert metrics.iloc[0]["e_aurc"] == 0.0
