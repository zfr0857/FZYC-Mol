from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RiskCoverageAudit:
    curve: pd.DataFrame
    aurc: float
    oracle_aurc: float
    e_aurc: float
    random_baseline_risk: float


def _risk(loss: np.ndarray, task_type: str) -> float:
    mean = float(np.mean(loss))
    return float(np.sqrt(mean)) if task_type == "regression" else mean


def risk_coverage_audit(
    y_true: Sequence[float],
    prediction: Sequence[float],
    risk_score: Sequence[float],
    *,
    task_type: str,
    coverages: Sequence[float] | None = None,
) -> RiskCoverageAudit:
    """Compute model and optimal-rejection risk curves (lower is better)."""

    y = np.asarray(y_true)
    pred = np.asarray(prediction, dtype=float)
    score = np.asarray(risk_score, dtype=float)
    if y.ndim != 1 or len(y) == 0 or len(y) != len(pred) or len(y) != len(score):
        raise ValueError("y_true, prediction and risk_score must be equal non-empty vectors")
    if task_type not in {"classification", "regression"}:
        raise ValueError("unsupported task_type")
    coverage = np.asarray(coverages if coverages is not None else np.linspace(0.1, 1.0, 19), dtype=float)
    if coverage.ndim != 1 or len(coverage) == 0 or np.any((coverage <= 0) | (coverage > 1)):
        raise ValueError("coverages must be in (0, 1]")
    coverage = np.unique(np.sort(coverage))

    if task_type == "classification":
        loss = (y.astype(int) != (pred >= 0.5).astype(int)).astype(float)
    else:
        loss = (y.astype(float) - pred) ** 2
    model_order = np.argsort(score, kind="stable")
    oracle_order = np.argsort(loss, kind="stable")
    rows = []
    for value in coverage:
        retained = max(1, int(np.ceil(value * len(y))))
        rows.append(
            {
                "coverage": float(value),
                "n_retained": retained,
                "risk": _risk(loss[model_order[:retained]], task_type),
                "oracle_lower_bound_risk": _risk(loss[oracle_order[:retained]], task_type),
            }
        )
    curve = pd.DataFrame(rows)
    aurc = float(np.trapezoid(curve["risk"], curve["coverage"]))
    oracle = float(np.trapezoid(curve["oracle_lower_bound_risk"], curve["coverage"]))
    return RiskCoverageAudit(curve, aurc, oracle, aurc - oracle, _risk(loss, task_type))
