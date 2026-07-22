from __future__ import annotations

import pandas as pd
import pytest

from fzyc_mol.selection.candidate_pool_audit import (
    audit_candidate_pool,
    audit_candidate_pool_summary,
    summarize_validation_scores,
)


def inner_scores() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "candidate_id": ["a", "a", "a", "b", "b", "b", "c", "c", "c"],
            "inner_fold": [1, 2, 3] * 3,
            "val_utility": [0.80, 0.79, 0.80, 0.81, 0.77, 0.79, 0.50, 0.55, 0.52],
            "fit_seconds": [3.0] * 3 + [2.0] * 3 + [1.0] * 3,
            "calibration_loss": [0.1] * 3 + [0.2] * 3 + [0.1] * 3,
        }
    )


def test_audit_separates_validation_selection_from_test_evaluation() -> None:
    outer = {"a": 0.70, "b": 0.60, "c": 0.90}
    result = audit_candidate_pool(
        inner_scores(),
        outer,
        full_test_utility=outer,
        pool_candidate_ids=["a", "b", "c"],
        baseline_id="a",
        task_type="classification",
    )

    assert result.decision.candidate_id == "a"
    assert result.ranking["oracle_validation_rank"] == 3
    assert result.regret["raw_regret"] == pytest.approx(0.20)


def test_test_utility_permutation_does_not_change_decision() -> None:
    kwargs = {
        "inner_scores": inner_scores(),
        "pool_candidate_ids": ["a", "b", "c"],
        "baseline_id": "a",
        "task_type": "classification",
    }
    first = audit_candidate_pool(outer_test_utility={"a": 0.7, "b": 0.6, "c": 0.9}, full_test_utility={"a": 0.7, "b": 0.6, "c": 0.9}, **kwargs)
    second = audit_candidate_pool(outer_test_utility={"a": 0.1, "b": 0.9, "c": 0.2}, full_test_utility={"a": 0.1, "b": 0.9, "c": 0.2}, **kwargs)

    assert first.decision.candidate_id == second.decision.candidate_id


def test_missing_candidate_is_marked_instead_of_silently_shrinking_pool() -> None:
    result = audit_candidate_pool(
        inner_scores(),
        {"a": 0.7, "b": 0.6},
        full_test_utility={"a": 0.7, "b": 0.6, "c": 0.9},
        pool_candidate_ids=["a", "b", "c"],
        baseline_id="a",
        task_type="classification",
    )

    assert result.status == "missing_data"
    assert result.missing_candidates == ("c",)
    assert result.decision is None


def test_precomputed_validation_summary_is_equivalent() -> None:
    inner = inner_scores()
    outer = {"a": 0.70, "b": 0.60, "c": 0.90}
    raw = audit_candidate_pool(
        inner,
        outer,
        full_test_utility=outer,
        pool_candidate_ids=["a", "b", "c"],
        baseline_id="a",
        task_type="classification",
    )
    summary = summarize_validation_scores(inner, ["a", "b", "c"])
    cached = audit_candidate_pool_summary(
        summary,
        outer,
        full_test_utility=outer,
        pool_candidate_ids=["a", "b", "c"],
        baseline_id="a",
        task_type="classification",
        n_inner=3,
    )

    assert cached.decision == raw.decision
    assert cached.ranking == raw.ranking
    assert cached.regret == raw.regret
