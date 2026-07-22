from __future__ import annotations

import pandas as pd

from fzyc_mol.selection.selector_rules import select_one_se


def candidates() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "candidate_id": ["alpha", "beta", "gamma"],
            "val_utility_mean": [0.80, 0.79, 0.60],
            "val_utility_sd": [0.03, 0.02, 0.01],
            "selection_frequency": [0.4, 0.8, 1.0],
            "calibration_loss": [0.10, 0.12, 0.01],
            "compute_cost": [3.0, 2.0, 1.0],
        }
    )


def test_one_se_set_uses_selection_frequency_before_variance() -> None:
    decision = select_one_se(candidates(), n_inner=3, task_type="classification")

    assert decision.candidate_id == "beta"
    assert decision.one_se_candidates == ("alpha", "beta")
    assert decision.reason_trace[0][0] == "selection_frequency"


def test_variance_calibration_and_cost_are_lexicographic_ties() -> None:
    frame = candidates().iloc[:2].copy()
    frame["selection_frequency"] = 0.5
    decision = select_one_se(frame, n_inner=3, task_type="classification")
    assert decision.candidate_id == "beta"

    frame["val_utility_sd"] = 0.02
    frame.loc[frame.candidate_id.eq("alpha"), "calibration_loss"] = 0.01
    decision = select_one_se(frame, n_inner=3, task_type="classification")
    assert decision.candidate_id == "alpha"

    frame["calibration_loss"] = 0.01
    frame.loc[frame.candidate_id.eq("beta"), "compute_cost"] = 1.0
    decision = select_one_se(frame, n_inner=3, task_type="classification")
    assert decision.candidate_id == "beta"


def test_regression_ignores_not_applicable_calibration() -> None:
    frame = candidates().iloc[:2].copy()
    frame["selection_frequency"] = 0.5
    frame["val_utility_sd"] = 0.02
    frame["calibration_loss"] = [float("nan"), float("nan")]
    frame["compute_cost"] = [2.0, 1.0]

    decision = select_one_se(frame, n_inner=3, task_type="regression")

    assert decision.candidate_id == "beta"


def test_stable_candidate_id_breaks_only_exact_tie() -> None:
    frame = candidates().iloc[:2].copy()
    for column in ["val_utility_mean", "val_utility_sd", "selection_frequency", "calibration_loss", "compute_cost"]:
        frame[column] = frame[column].iloc[0]

    decision = select_one_se(frame, n_inner=3, task_type="classification")

    assert decision.candidate_id == "alpha"
