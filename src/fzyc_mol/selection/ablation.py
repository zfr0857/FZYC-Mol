from __future__ import annotations

import math

import pandas as pd

from .selector_rules import select_one_se


GOVERNANCE_RULES = (
    "frozen_one_se_governance",
    "validation_best",
    "one_se_low_variance",
    "one_se_low_cost",
)


def _one_se_set(summary: pd.DataFrame, n_inner: int) -> pd.DataFrame:
    best = summary.sort_values(
        ["val_utility_mean", "candidate_id"], ascending=[False, True], kind="stable"
    ).iloc[0]
    threshold = float(best["val_utility_mean"] - best["val_utility_sd"] / math.sqrt(n_inner))
    return summary.loc[summary["val_utility_mean"] >= threshold].copy()


def select_ablation_rule(
    summary: pd.DataFrame,
    *,
    rule: str,
    n_inner: int,
    task_type: str,
) -> str:
    """Apply a frozen validation-only governance ablation."""

    if rule not in GOVERNANCE_RULES:
        raise ValueError(f"unknown rule: {rule}")
    if rule == "frozen_one_se_governance":
        return select_one_se(summary, n_inner=n_inner, task_type=task_type).candidate_id
    if rule == "validation_best":
        ordered = summary.sort_values(
            ["val_utility_mean", "candidate_id"], ascending=[False, True], kind="stable"
        )
        return str(ordered.iloc[0]["candidate_id"])
    eligible = _one_se_set(summary, n_inner)
    if rule == "one_se_low_variance":
        ordered = eligible.sort_values(
            ["val_utility_sd", "val_utility_mean", "candidate_id"],
            ascending=[True, False, True],
            kind="stable",
        )
    else:
        ordered = eligible.sort_values(
            ["compute_cost", "val_utility_mean", "candidate_id"],
            ascending=[True, False, True],
            kind="stable",
        )
    return str(ordered.iloc[0]["candidate_id"])
