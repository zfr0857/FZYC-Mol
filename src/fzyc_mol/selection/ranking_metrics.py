from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
from scipy.stats import kendalltau, rankdata, spearmanr


def _as_finite(values: Sequence[float], name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or array.size == 0:
        raise ValueError(f"{name} must be a non-empty one-dimensional sequence")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array


def _ndcg(validation: np.ndarray, test: np.ndarray) -> float:
    k = len(validation)
    test_rank = rankdata(-test, method="average")
    relevance = k - test_rank + 1.0
    validation_order = np.argsort(-validation, kind="stable")
    ideal_order = np.argsort(-test, kind="stable")
    discounts = np.log2(np.arange(2, k + 2, dtype=float))
    dcg = float(np.sum((2.0 ** relevance[validation_order] - 1.0) / discounts))
    ideal = float(np.sum((2.0 ** relevance[ideal_order] - 1.0) / discounts))
    return dcg / ideal if ideal > 0 else math.nan


def ranking_audit(
    validation_utility: Sequence[float],
    test_utility: Sequence[float],
) -> dict[str, float | int]:
    """Evaluate validation ranking against the outer-test oracle.

    Test utilities are consumed only here in the audit namespace; this function
    never returns or selects a candidate for training or deployment.
    """

    validation = _as_finite(validation_utility, "validation_utility")
    test = _as_finite(test_utility, "test_utility")
    if validation.shape != test.shape:
        raise ValueError("validation_utility and test_utility must have equal length")

    k = len(validation)
    oracle_index = int(np.argmax(test))
    validation_order = np.argsort(-validation, kind="stable")
    oracle_rank = int(np.flatnonzero(validation_order == oracle_index)[0] + 1)
    fixed_k = min(3, k)
    fraction_k = max(1, math.ceil(0.25 * k))
    top3_hit = int(oracle_rank <= fixed_k)
    chance = fixed_k / k
    chance_adjusted = (top3_hit - chance) / (1.0 - chance) if chance < 1.0 else 0.0
    percentile = 1.0 - (oracle_rank - 1) / max(k - 1, 1)
    rho = spearmanr(validation, test).statistic if k > 1 else 1.0
    tau = kendalltau(validation, test).statistic if k > 1 else 1.0

    return {
        "candidate_count": k,
        "oracle_validation_rank": oracle_rank,
        "top1_hit": int(oracle_rank == 1),
        "top3_k": fixed_k,
        "top3_hit": top3_hit,
        "top_fraction_k": fraction_k,
        "top_fraction_hit": int(oracle_rank <= fraction_k),
        "chance_hit": chance,
        "chance_adjusted_hit": chance_adjusted,
        "mrr": 1.0 / oracle_rank,
        "rank_percentile": percentile,
        "ndcg": _ndcg(validation, test),
        "spearman": float(rho),
        "kendall": float(tau),
    }
