import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "results" / "reviewer_core_20260624"
MULTI = CORE / "multiview_nested"


def test_paired_expansion_effect_is_endpoint_clustered_and_adjusted():
    data = pd.read_csv(CORE / "paired_pool_effects.csv")
    row = data[
        data["metric"].eq("fixed_normalized_regret")
        & data["comparison"].eq("K=32 vs K=4")
    ].iloc[0]
    assert row["paired_units"] == 135
    assert row["endpoints"] == 9
    assert row["endpoint_cluster_ci95_low"] > 0
    assert row["holm_p_across_9_tests"] < 0.05


def test_signal_recovery_has_correct_null_and_monotonic_positive_control():
    values = json.loads((CORE / "reviewer_core_values.json").read_text(encoding="utf-8"))
    signal = values["signal_recovery"]
    assert signal["null_max_abs_chance_adjusted_hit"] < 0.01
    assert signal["full_signal_max_regret"] == 0.0
    for checks in signal["monotonicity"].values():
        assert all(checks.values())


def test_cross_endpoint_meta_risk_is_complete_and_strictly_held_out():
    predictions = pd.read_csv(CORE / "cross_endpoint_meta_risk_predictions.csv")
    selection = pd.read_csv(CORE / "cross_endpoint_meta_risk_model_selection.csv")
    summary = json.loads((CORE / "cross_endpoint_meta_risk_summary.json").read_text(encoding="utf-8"))
    assert len(predictions) == 540
    assert selection["held_endpoint"].nunique() == 9
    assert len(selection) == 9
    assert summary["loeo_mae"] < summary["constant_baseline_mae"]
    assert summary["risk_gate_endpoint_bootstrap_ci95_high"] < 0
    assert summary["endpoints_with_lower_retained_regret"] >= 8


def test_shared_split_multiview_run_is_complete():
    registry = pd.read_csv(MULTI / "candidate_registry.csv")
    inner = pd.read_csv(MULTI / "inner_scores.csv")
    outer = pd.read_csv(MULTI / "outer_candidate_scores.csv")
    policies = pd.read_csv(MULTI / "policy_detail.csv")
    manifest = json.loads((MULTI / "run_manifest.json").read_text(encoding="utf-8"))
    assert len(registry) == 9 * 5 * 12
    assert len(inner) == 9 * 5 * 3 * 3 * 12
    assert len(outer) == 9 * 5 * 3 * 12
    assert policies[["task", "seed", "outer_fold"]].drop_duplicates().shape[0] == 135
    assert np.isfinite(inner["inner_utility"]).all()
    assert np.isfinite(outer["outer_utility"]).all()
    assert manifest["seeds"] == [11, 23, 37, 53, 71]
    assert manifest["candidate_count"] == 12


def test_multiview_effects_are_paired_across_all_endpoints():
    effects = pd.read_csv(MULTI / "paired_multiview_effects.csv")
    row = effects[
        effects["comparison"].eq("realized multiview validation-best gain vs Morgan-only")
    ].iloc[0]
    assert row["paired_outer_units"] == 135
    assert row["endpoints_positive"] == 9
    assert row["endpoint_cluster_ci95_low"] > 0
    assert row["exact_sign_flip_p"] < 0.01
