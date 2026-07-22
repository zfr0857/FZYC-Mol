from __future__ import annotations

import pandas as pd

from fzyc_mol.selection.ablation import select_ablation_rule


def _summary() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "candidate_id": ["best", "stable", "cheap"],
            "val_utility_mean": [0.80, 0.79, 0.78],
            "val_utility_sd": [0.06, 0.01, 0.02],
            "selection_frequency": [1 / 3, 2 / 3, 0.0],
            "calibration_loss": [0.2, 0.1, 0.3],
            "compute_cost": [2.0, 3.0, 0.1],
        }
    )


def test_governance_ablation_changes_only_the_frozen_rule() -> None:
    summary = _summary()

    assert select_ablation_rule(summary, rule="validation_best", n_inner=3, task_type="classification") == "best"
    assert select_ablation_rule(summary, rule="one_se_low_variance", n_inner=3, task_type="classification") == "stable"
    assert select_ablation_rule(summary, rule="one_se_low_cost", n_inner=3, task_type="classification") == "cheap"


def test_unknown_governance_ablation_is_rejected() -> None:
    try:
        select_ablation_rule(_summary(), rule="test_best", n_inner=3, task_type="classification")
    except ValueError as exc:
        assert "unknown rule" in str(exc)
    else:
        raise AssertionError("unknown rule must fail")
