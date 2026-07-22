from __future__ import annotations

import pandas as pd

from fzyc_mol.selection.selector_rules import select_one_se


def test_permuting_test_labels_cannot_change_selection() -> None:
    frame = pd.DataFrame(
        {
            "candidate_id": ["a", "b", "c"],
            "val_utility_mean": [0.70, 0.69, 0.50],
            "val_utility_sd": [0.03, 0.02, 0.01],
            "selection_frequency": [0.5, 0.8, 1.0],
            "calibration_loss": [0.2, 0.2, 0.2],
            "compute_cost": [1.0, 1.0, 1.0],
            "test_utility": [0.1, 0.2, 0.9],
        }
    )
    first = select_one_se(frame, n_inner=3, task_type="classification")
    permuted = frame.copy()
    permuted["test_utility"] = [0.9, 0.1, 0.2]
    second = select_one_se(permuted, n_inner=3, task_type="classification")

    assert first.candidate_id == second.candidate_id
    assert "test_utility" not in first.columns_read
