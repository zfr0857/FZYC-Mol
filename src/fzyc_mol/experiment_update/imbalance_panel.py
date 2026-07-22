from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.utils import resample
from xgboost import XGBClassifier

from fzyc_mol.datasets import load_dataset
from fzyc_mol.features import morgan_fingerprint

from .data_splits import split_indices_for
from .io import ExperimentConfig, write_csv
from .metrics import extended_classification_metrics


def _x(frame: pd.DataFrame) -> np.ndarray:
    return np.vstack([morgan_fingerprint(s) for s in frame["smiles"]]).astype(np.float32)


def _fit_predict(strategy: str, x_train, y_train, x_eval, seed: int) -> np.ndarray:
    y_train = np.asarray(y_train).astype(int)
    if strategy == "class_weight":
        pos = max(1, int(y_train.sum()))
        neg = max(1, int((1 - y_train).sum()))
        model = XGBClassifier(n_estimators=250, max_depth=3, learning_rate=0.04, subsample=0.85, colsample_bytree=0.8, scale_pos_weight=neg / pos, eval_metric="logloss", random_state=seed, n_jobs=4)
        model.fit(x_train, y_train)
        return model.predict_proba(x_eval)[:, 1]
    if strategy in {"oversampling", "downsampling"}:
        idx_pos = np.where(y_train == 1)[0]
        idx_neg = np.where(y_train == 0)[0]
        if len(idx_pos) == 0 or len(idx_neg) == 0:
            idx = np.arange(len(y_train))
        elif strategy == "oversampling":
            idx_pos_new = resample(idx_pos, replace=True, n_samples=len(idx_neg), random_state=seed)
            idx = np.concatenate([idx_neg, idx_pos_new])
        else:
            idx_neg_new = resample(idx_neg, replace=False, n_samples=len(idx_pos), random_state=seed)
            idx = np.concatenate([idx_neg_new, idx_pos])
        model = XGBClassifier(n_estimators=250, max_depth=3, learning_rate=0.04, subsample=0.85, colsample_bytree=0.8, eval_metric="logloss", random_state=seed, n_jobs=4)
        model.fit(x_train[idx], y_train[idx])
        return model.predict_proba(x_eval)[:, 1]
    if strategy == "downsampling_ensemble":
        idx_pos = np.where(y_train == 1)[0]
        idx_neg = np.where(y_train == 0)[0]
        preds = []
        for k in range(7):
            if len(idx_pos) and len(idx_neg):
                idx_neg_new = resample(idx_neg, replace=False, n_samples=min(len(idx_neg), max(1, len(idx_pos))), random_state=seed + k)
                idx = np.concatenate([idx_neg_new, idx_pos])
            else:
                idx = np.arange(len(y_train))
            model = RandomForestClassifier(n_estimators=180, random_state=seed + k, n_jobs=-1, class_weight=None)
            model.fit(x_train[idx], y_train[idx])
            preds.append(model.predict_proba(x_eval)[:, 1])
        return np.mean(preds, axis=0)
    if strategy == "threshold_moving":
        model = XGBClassifier(n_estimators=250, max_depth=3, learning_rate=0.04, subsample=0.85, colsample_bytree=0.8, eval_metric="logloss", random_state=seed, n_jobs=4)
        model.fit(x_train, y_train)
        return model.predict_proba(x_eval)[:, 1]
    raise ValueError(strategy)


def run_imbalance_panel(config: ExperimentConfig, datasets: list[str] | None = None) -> pd.DataFrame:
    names = datasets or config.datasets("imbalance")
    strategies = list(config.raw.get("imbalance_strategies", []))
    rows = []
    missing = []
    for dataset in names:
        try:
            frame, spec = load_dataset(dataset, config.data_dir)
        except Exception as exc:
            missing.append({"module": "imbalance_panel", "dataset": dataset, "status": "missing_data", "reason": str(exc)})
            continue
        if spec.task_type != "classification" or frame["y"].nunique() != 2:
            continue
        x = _x(frame)
        for seed in config.seeds:
            split = split_indices_for(frame, "scaffold", seed, config)
            for strategy in strategies:
                for part, idx in [("valid", split.valid), ("test", split.test)]:
                    scores = _fit_predict(strategy, x[split.train], frame.iloc[split.train]["y"].to_numpy(), x[idx], seed)
                    metrics = extended_classification_metrics(frame.iloc[idx]["y"].to_numpy(), scores)
                    rows.append(
                        {
                            "dataset": dataset,
                            "seed": seed,
                            "split_strategy": "scaffold",
                            "split": part,
                            "strategy": strategy,
                            "n_train": len(split.train),
                            "positive_rate_train": float(frame.iloc[split.train]["y"].mean()),
                            **metrics,
                        }
                    )
    out = pd.DataFrame(rows)
    write_csv(out, config.reports_dir / "imbalance_panel_metrics.csv")
    if missing:
        write_csv(pd.DataFrame(missing), config.reports_dir / "missing_data_report.csv")
    return out
