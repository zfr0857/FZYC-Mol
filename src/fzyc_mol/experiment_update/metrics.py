from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    balanced_accuracy_score,
    matthews_corrcoef,
    precision_recall_curve,
    precision_score,
    recall_score,
)

from fzyc_mol.evaluate import classification_metrics, regression_metrics


def recall_at_fixed_precision(y_true, scores, threshold: float) -> float:
    y_true = np.asarray(y_true).astype(int)
    scores = np.asarray(scores).astype(float)
    precision, recall, _ = precision_recall_curve(y_true, scores)
    mask = precision >= float(threshold)
    if not np.any(mask):
        return 0.0
    return float(np.max(recall[mask]))


def extended_classification_metrics(y_true, scores) -> dict[str, float]:
    y_true = np.asarray(y_true).astype(int)
    scores = np.asarray(scores).astype(float)
    base = classification_metrics(y_true, scores)
    pred = (scores >= 0.5).astype(int)
    base.update(
        {
            "precision": float(precision_score(y_true, pred, zero_division=0)),
            "recall": float(recall_score(y_true, pred, zero_division=0)),
            "mcc": float(matthews_corrcoef(y_true, pred)) if len(np.unique(pred)) > 1 else 0.0,
            "balanced_accuracy": float(balanced_accuracy_score(y_true, pred)),
            "recall_at_precision_0_8": recall_at_fixed_precision(y_true, scores, 0.8),
            "recall_at_precision_0_9": recall_at_fixed_precision(y_true, scores, 0.9),
        }
    )
    return base


def metrics_for_task(task_type: str, y_true, y_pred) -> dict[str, float]:
    if task_type == "classification":
        return extended_classification_metrics(y_true, y_pred)
    return regression_metrics(y_true, y_pred)
