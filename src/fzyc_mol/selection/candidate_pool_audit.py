from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import pandas as pd

from .ranking_metrics import ranking_audit
from .regret_metrics import regret_decomposition
from .selector_rules import SelectionDecision, select_one_se


@dataclass(frozen=True)
class CandidatePoolAudit:
    status: str
    missing_candidates: tuple[str, ...]
    decision: SelectionDecision | None
    ranking: dict[str, float | int] | None
    regret: dict[str, float | str] | None
    validation_summary: pd.DataFrame | None


@dataclass(frozen=True)
class ValidationCache:
    fold_utilities: pd.DataFrame
    candidate_stats: pd.DataFrame

    def summary(self, candidate_ids: Sequence[str]) -> pd.DataFrame:
        ids = [str(value) for value in candidate_ids]
        fold = self.fold_utilities.loc[:, ids]
        winners = fold.idxmax(axis=1)
        counts = Counter(winners.astype(str))
        summary = self.candidate_stats[self.candidate_stats["candidate_id"].isin(ids)].copy()
        summary["selection_frequency"] = summary["candidate_id"].map(lambda value: counts[str(value)] / len(fold))
        return summary


def summarize_validation_scores(inner_scores: pd.DataFrame, candidate_ids: Sequence[str]) -> ValidationCache:
    required = {"candidate_id", "inner_fold", "val_utility", "fit_seconds"}
    missing = required - set(inner_scores.columns)
    if missing:
        raise ValueError(f"missing inner-score columns: {sorted(missing)}")
    frame = inner_scores[inner_scores["candidate_id"].isin(candidate_ids)].copy()
    aggregation: dict[str, tuple[str, str]] = {
        "val_utility_mean": ("val_utility", "mean"),
        "val_utility_sd": ("val_utility", "std"),
        "compute_cost": ("fit_seconds", "mean"),
    }
    if "calibration_loss" in frame.columns:
        aggregation["calibration_loss"] = ("calibration_loss", "mean")
    summary = frame.groupby("candidate_id", as_index=False).agg(**aggregation)
    if "calibration_loss" not in summary:
        summary["calibration_loss"] = float("nan")
    summary["val_utility_sd"] = summary["val_utility_sd"].fillna(0.0)
    fold = frame.pivot(index="inner_fold", columns="candidate_id", values="val_utility")
    if fold.isna().any().any():
        raise ValueError("each candidate must have one utility for every inner fold")
    return ValidationCache(fold.sort_index(axis=1), summary)


def audit_candidate_pool_summary(
    validation_cache: ValidationCache,
    outer_test_utility: Mapping[str, float],
    *,
    full_test_utility: Mapping[str, float],
    pool_candidate_ids: Sequence[str],
    baseline_id: str,
    task_type: str,
    n_inner: int,
) -> CandidatePoolAudit:
    candidate_ids = tuple(str(value) for value in pool_candidate_ids)
    inner_ids = set(validation_cache.candidate_stats["candidate_id"].astype(str))
    outer_ids = {str(value) for value in outer_test_utility}
    missing = tuple(sorted(set(candidate_ids) - inner_ids | (set(candidate_ids) - outer_ids)))
    if missing:
        return CandidatePoolAudit("missing_data", missing, None, None, None, None)

    summary = validation_cache.summary(candidate_ids)
    decision = select_one_se(summary, n_inner=n_inner, task_type=task_type)
    validation_by_id = summary.set_index("candidate_id")["val_utility_mean"].to_dict()
    validation = [validation_by_id[candidate] for candidate in candidate_ids]
    test = [float(outer_test_utility[candidate]) for candidate in candidate_ids]
    ranking = ranking_audit(validation, test)
    regret = regret_decomposition(
        {candidate: float(outer_test_utility[candidate]) for candidate in candidate_ids},
        full_test_utility,
        decision.candidate_id,
        baseline_id,
    )
    return CandidatePoolAudit("completed", (), decision, ranking, regret, summary)


def audit_candidate_pool(
    inner_scores: pd.DataFrame,
    outer_test_utility: Mapping[str, float],
    *,
    full_test_utility: Mapping[str, float],
    pool_candidate_ids: Sequence[str],
    baseline_id: str,
    task_type: str,
) -> CandidatePoolAudit:
    """Freeze a validation-only decision, then evaluate it in the audit namespace."""

    candidate_ids = tuple(str(value) for value in pool_candidate_ids)
    cache = summarize_validation_scores(inner_scores, candidate_ids)
    n_inner = int(inner_scores["inner_fold"].nunique())
    return audit_candidate_pool_summary(
        cache,
        outer_test_utility,
        full_test_utility=full_test_utility,
        pool_candidate_ids=candidate_ids,
        baseline_id=baseline_id,
        task_type=task_type,
        n_inner=n_inner,
    )
