from __future__ import annotations

import numpy as np
from rdkit.ML.Scoring import Scoring
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
)
from scipy.stats import pearsonr, spearmanr


def _sorted_screening_rows(y_true: np.ndarray, scores: np.ndarray) -> list[list[float | bool]]:
    order = np.argsort(-np.asarray(scores, dtype=float))
    labels = np.asarray(y_true, dtype=int)[order]
    ranked_scores = np.asarray(scores, dtype=float)[order]
    return [[float(score), bool(label)] for score, label in zip(ranked_scores, labels)]


def enrichment_factor(y_true: np.ndarray, scores: np.ndarray, fraction: float) -> float:
    y_true = np.asarray(y_true, dtype=int).reshape(-1)
    scores = np.asarray(scores, dtype=float).reshape(-1)
    if len(y_true) == 0:
        return float("nan")
    n_actives = int(y_true.sum())
    if n_actives == 0:
        return float("nan")
    k = max(1, int(np.ceil(len(y_true) * fraction)))
    top = y_true[np.argsort(-scores)[:k]]
    return float((top.sum() / k) / (n_actives / len(y_true)))


def top_fraction_recall(y_true: np.ndarray, scores: np.ndarray, fraction: float) -> float:
    y_true = np.asarray(y_true, dtype=int).reshape(-1)
    scores = np.asarray(scores, dtype=float).reshape(-1)
    n_actives = int(y_true.sum())
    if n_actives == 0:
        return float("nan")
    k = max(1, int(np.ceil(len(y_true) * fraction)))
    return float(y_true[np.argsort(-scores)[:k]].sum() / n_actives)


def bedroc_score(y_true: np.ndarray, scores: np.ndarray, alpha: float = 20.0) -> float:
    y_true = np.asarray(y_true, dtype=int).reshape(-1)
    if len(y_true) == 0 or y_true.sum() == 0:
        return float("nan")
    rows = _sorted_screening_rows(y_true, np.asarray(scores, dtype=float).reshape(-1))
    return float(Scoring.CalcBEDROC(rows, 1, alpha))


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    y_true = np.asarray(y_true).reshape(-1)
    y_pred = np.asarray(y_pred).reshape(-1)
    mse = mean_squared_error(y_true, y_pred)
    if len(y_true) > 1 and len(np.unique(y_true)) > 1 and len(np.unique(y_pred)) > 1:
        spearman = float(spearmanr(y_true, y_pred).correlation)
        pearson = float(pearsonr(y_true, y_pred)[0])
    else:
        spearman = float("nan")
        pearson = float("nan")
    return {
        "rmse": float(np.sqrt(mse)),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "r2": float(r2_score(y_true, y_pred)),
        "spearman": spearman,
        "pearson": pearson,
    }


def classification_metrics(y_true: np.ndarray, logits_or_prob: np.ndarray) -> dict[str, float]:
    y_true = np.asarray(y_true).reshape(-1).astype(int)
    scores = np.asarray(logits_or_prob).reshape(-1)
    if scores.min() < 0.0 or scores.max() > 1.0:
        scores = 1.0 / (1.0 + np.exp(-np.clip(scores, -60.0, 60.0)))
    scores = np.clip(scores, 1e-7, 1.0 - 1e-7)
    pred = (scores >= 0.5).astype(int)
    metrics = {
        "accuracy": float(accuracy_score(y_true, pred)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "brier": float(brier_score_loss(y_true, scores)),
        "ece": expected_calibration_error(y_true, scores),
    }
    if len(np.unique(y_true)) == 2:
        metrics["roc_auc"] = float(roc_auc_score(y_true, scores))
        metrics["pr_auc"] = float(average_precision_score(y_true, scores))
        metrics["ef1"] = enrichment_factor(y_true, scores, 0.01)
        metrics["ef5"] = enrichment_factor(y_true, scores, 0.05)
        metrics["bedroc20"] = bedroc_score(y_true, scores, alpha=20.0)
        metrics["top1_recall"] = top_fraction_recall(y_true, scores, 0.01)
        metrics["top5_recall"] = top_fraction_recall(y_true, scores, 0.05)
        metrics["top10_recall"] = top_fraction_recall(y_true, scores, 0.10)
    else:
        metrics["roc_auc"] = float("nan")
        metrics["pr_auc"] = float("nan")
        metrics["ef1"] = float("nan")
        metrics["ef5"] = float("nan")
        metrics["bedroc20"] = float("nan")
        metrics["top1_recall"] = float("nan")
        metrics["top5_recall"] = float("nan")
        metrics["top10_recall"] = float("nan")
    return metrics


def expected_calibration_error(y_true: np.ndarray, prob: np.ndarray, n_bins: int = 10) -> float:
    y_true = np.asarray(y_true).reshape(-1).astype(int)
    prob = np.asarray(prob).reshape(-1)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for low, high in zip(bins[:-1], bins[1:]):
        if high == 1.0:
            mask = (prob >= low) & (prob <= high)
        else:
            mask = (prob >= low) & (prob < high)
        if not np.any(mask):
            continue
        confidence = float(prob[mask].mean())
        accuracy = float(y_true[mask].mean())
        ece += float(mask.mean()) * abs(accuracy - confidence)
    return float(ece)


def compute_metrics(task_type: str, y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    if task_type == "regression":
        return regression_metrics(y_true, y_pred)
    if task_type == "classification":
        return classification_metrics(y_true, y_pred)
    raise ValueError(f"Unknown task type '{task_type}'.")
