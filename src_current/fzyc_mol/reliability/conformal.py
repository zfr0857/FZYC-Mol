from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np


@dataclass(frozen=True)
class LabelConditionalFit:
    thresholds: dict[int, float]
    class_counts: dict[int, int]
    fallback_reason: str | None


def _finite_sample_quantile(scores: np.ndarray, alpha: float) -> float:
    level = min(1.0, math.ceil((len(scores) + 1) * (1.0 - alpha)) / len(scores))
    return float(np.quantile(scores, level, method="higher"))


def fit_label_conditional(
    y_calibration: Sequence[int],
    probabilities: np.ndarray,
    *,
    alpha: float,
    min_class_count: int = 5,
) -> LabelConditionalFit:
    y = np.asarray(y_calibration, dtype=int)
    proba = np.asarray(probabilities, dtype=float)
    if proba.shape != (len(y), 2) or len(y) == 0:
        raise ValueError("probabilities must have shape (n, 2)")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0, 1)")
    scores = 1.0 - proba[np.arange(len(y)), y]
    counts = {label: int(np.sum(y == label)) for label in (0, 1)}
    small = next((label for label in (0, 1) if counts[label] < min_class_count), None)
    if small is not None:
        threshold = _finite_sample_quantile(scores, alpha)
        return LabelConditionalFit(
            {0: threshold, 1: threshold},
            counts,
            f"class_{small}_count_{counts[small]}_below_{min_class_count}",
        )
    thresholds = {
        label: _finite_sample_quantile(scores[y == label], alpha)
        for label in (0, 1)
    }
    return LabelConditionalFit(thresholds, counts, None)


def classification_prediction_sets(
    probabilities: np.ndarray,
    thresholds: Mapping[int, float],
) -> list[tuple[int, ...]]:
    proba = np.asarray(probabilities, dtype=float)
    if proba.ndim != 2 or proba.shape[1] != 2:
        raise ValueError("probabilities must have shape (n, 2)")
    return [
        tuple(label for label in (0, 1) if 1.0 - row[label] <= float(thresholds[label]))
        for row in proba
    ]


def normalized_interval_width(widths: Sequence[float], y_train: Sequence[float]) -> dict[str, np.ndarray]:
    width = np.asarray(widths, dtype=float)
    train = np.asarray(y_train, dtype=float)
    sd = float(np.std(train, ddof=1))
    iqr = float(np.quantile(train, 0.75) - np.quantile(train, 0.25))
    return {
        "width_sd": width / sd if sd > 0 else np.full_like(width, np.nan),
        "width_iqr": width / iqr if iqr > 0 else np.full_like(width, np.nan),
    }
