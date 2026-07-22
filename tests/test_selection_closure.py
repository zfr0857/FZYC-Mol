import numpy as np
import pandas as pd

from fzyc_mol.selection.selection_closure import (
    build_selection_risk_frame,
    leave_one_endpoint_out_policy,
    permutation_null_for_unit,
    selection_risk_curve,
)


def test_selection_risk_uses_validation_diagnostics_and_orders_ambiguity():
    nested = pd.DataFrame(
        {
            "endpoint": ["a", "a"],
            "repeat": [1, 1],
            "outer_fold": [1, 2],
            "repeat_seed": [11, 11],
            "split_id": ["a:1", "a:2"],
            "pool_size": [8, 8],
            "one_se_candidates": ["m1", "m1;m2;m3;m4"],
            "selection_reason": [
                '[["selection_frequency", 1.0], ["fold_variability", 0.01]]',
                '[["selection_frequency", 0.33], ["fold_variability", 0.20]]',
            ],
        }
    )
    regret = pd.DataFrame(
        {
            "endpoint": ["a", "a"],
            "repeat": [1, 1],
            "outer_fold": [1, 2],
            "repeat_seed": [11, 11],
            "split_id": ["a:1", "a:2"],
            "pool_size": [8, 8],
            "fixed_normalized_regret": [0.02, 0.40],
        }
    )

    out = build_selection_risk_frame(nested, regret)

    assert out["selection_risk"].between(0, 1).all()
    assert out.loc[out["split_id"] == "a:2", "selection_risk"].item() > out.loc[
        out["split_id"] == "a:1", "selection_risk"
    ].item()
    assert out.loc[out["split_id"] == "a:1", "one_se_size"].item() == 1
    assert out.loc[out["split_id"] == "a:2", "one_se_size"].item() == 4


def test_selection_risk_curve_prefers_low_risk_units():
    frame = pd.DataFrame(
        {
            "selection_risk": [0.1, 0.2, 0.8, 0.9],
            "fixed_normalized_regret": [0.01, 0.02, 0.30, 0.40],
        }
    )
    curve = selection_risk_curve(frame, coverages=[0.5, 1.0])
    assert curve.loc[curve["coverage"] == 0.5, "mean_regret"].item() == 0.015
    assert curve.loc[curve["coverage"] == 1.0, "mean_regret"].item() == 0.1825


def test_permutation_null_is_deterministic_and_chance_adjusted():
    validation = np.array([4.0, 3.0, 2.0, 1.0])
    outer = np.array([4.0, 3.0, 2.0, 1.0])
    a = permutation_null_for_unit(validation, outer, n_permutations=4000, seed=7)
    b = permutation_null_for_unit(validation, outer, n_permutations=4000, seed=7)
    pd.testing.assert_frame_equal(a, b)
    assert abs(a["chance_adjusted_top3_hit"].mean()) < 0.03
    assert a["fixed_normalized_regret"].between(0, 1).all()


def test_leave_one_endpoint_out_policy_never_uses_held_endpoint_for_choice():
    rows = []
    for endpoint, losses in {
        "a": {"rule_1": 0.1, "rule_2": 0.3},
        "b": {"rule_1": 0.1, "rule_2": 0.3},
        "held": {"rule_1": 0.9, "rule_2": 0.0},
    }.items():
        for variant, loss in losses.items():
            rows.append(
                {
                    "endpoint": endpoint,
                    "variant": variant,
                    "full32_fixed_normalized_regret": loss,
                }
            )
    out = leave_one_endpoint_out_policy(pd.DataFrame(rows))
    held = out.loc[out["held_endpoint"] == "held"].iloc[0]
    assert held["selected_variant"] == "rule_1"
    assert held["heldout_regret"] == 0.9
    assert held["heldout_oracle_variant"] == "rule_2"
