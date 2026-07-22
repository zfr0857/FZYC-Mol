from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd


VALIDATION_COLUMNS = (
    "candidate_id",
    "val_utility_mean",
    "val_utility_sd",
    "selection_frequency",
    "calibration_loss",
    "compute_cost",
)


@dataclass(frozen=True)
class SelectionDecision:
    candidate_id: str
    one_se_candidates: tuple[str, ...]
    threshold: float
    columns_read: tuple[str, ...]
    reason_trace: tuple[tuple[str, float | str], ...]


def select_one_se(
    candidates: pd.DataFrame,
    *,
    n_inner: int,
    task_type: str,
) -> SelectionDecision:
    """Select using validation-only one-SE and a frozen lexicographic rule."""

    if n_inner < 1:
        raise ValueError("n_inner must be positive")
    if task_type not in {"classification", "regression"}:
        raise ValueError("task_type must be classification or regression")
    missing = set(VALIDATION_COLUMNS) - set(candidates.columns)
    if missing:
        raise ValueError(f"missing validation columns: {sorted(missing)}")

    frame = candidates.loc[:, VALIDATION_COLUMNS].copy()
    if frame.empty or frame["candidate_id"].duplicated().any():
        raise ValueError("candidate_id must be non-empty and unique")
    numeric = [column for column in VALIDATION_COLUMNS if column != "candidate_id"]
    frame[numeric] = frame[numeric].apply(pd.to_numeric, errors="coerce")
    required_finite = ["val_utility_mean", "val_utility_sd", "selection_frequency", "compute_cost"]
    if frame[required_finite].isna().any().any():
        raise ValueError("selection inputs contain missing required values")

    best = frame.sort_values(["val_utility_mean", "candidate_id"], ascending=[False, True], kind="stable").iloc[0]
    threshold = float(best["val_utility_mean"] - best["val_utility_sd"] / math.sqrt(n_inner))
    eligible = frame[frame["val_utility_mean"] >= threshold].copy()
    eligible["_calibration"] = eligible["calibration_loss"].fillna(math.inf)
    eligible = eligible.sort_values(
        ["selection_frequency", "val_utility_sd", "_calibration", "compute_cost", "candidate_id"],
        ascending=[False, True, True, True, True],
        kind="stable",
    )
    selected = eligible.iloc[0]
    one_se_ids = tuple(sorted(eligible["candidate_id"].astype(str)))
    trace = (
        ("selection_frequency", float(selected["selection_frequency"])),
        ("fold_variability", float(selected["val_utility_sd"])),
        (
            "calibration_loss",
            "not_applicable" if task_type == "regression" and pd.isna(selected["calibration_loss"]) else float(selected["calibration_loss"]),
        ),
        ("compute_cost", float(selected["compute_cost"])),
        ("stable_candidate_id", str(selected["candidate_id"])),
    )
    return SelectionDecision(
        candidate_id=str(selected["candidate_id"]),
        one_se_candidates=one_se_ids,
        threshold=threshold,
        columns_read=VALIDATION_COLUMNS,
        reason_trace=trace,
    )
