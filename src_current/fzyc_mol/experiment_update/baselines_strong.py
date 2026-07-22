from __future__ import annotations

from time import perf_counter
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor, RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier, XGBRegressor

from fzyc_mol.datasets import load_dataset
from fzyc_mol.features import descriptor_vector, morgan_fingerprint

from .data_splits import split_indices_for
from .io import ExperimentConfig, write_csv
from .metrics import metrics_for_task


def _feature_matrix(frame: pd.DataFrame, view: str) -> np.ndarray:
    if view == "rdkit":
        return np.vstack([descriptor_vector(s, include_3d=False) for s in frame["smiles"]]).astype(np.float32)
    if view == "morgan":
        return np.vstack([morgan_fingerprint(s) for s in frame["smiles"]]).astype(np.float32)
    if view == "morgancount":
        # Count-like proxy: binary Morgan bits plus descriptor tail, stable without extra dependencies.
        return np.hstack(
            [
                np.vstack([morgan_fingerprint(s) for s in frame["smiles"]]),
                np.vstack([descriptor_vector(s, include_3d=False) for s in frame["smiles"]]),
            ]
        ).astype(np.float32)
    raise ValueError(view)


def _available_model_factories(task_type: str, seed: int, n_estimators: int) -> dict[str, tuple[str, Callable[[], object]]]:
    if task_type == "classification":
        return {
            "xgboost_rdkit": ("rdkit", lambda: XGBClassifier(n_estimators=n_estimators, max_depth=3, learning_rate=0.04, subsample=0.85, colsample_bytree=0.8, eval_metric="logloss", random_state=seed, n_jobs=4)),
            "xgboost_morgan": ("morgan", lambda: XGBClassifier(n_estimators=n_estimators, max_depth=3, learning_rate=0.04, subsample=0.85, colsample_bytree=0.8, eval_metric="logloss", random_state=seed, n_jobs=4)),
            "xgboost_morgancount": ("morgancount", lambda: XGBClassifier(n_estimators=n_estimators, max_depth=3, learning_rate=0.04, subsample=0.85, colsample_bytree=0.8, eval_metric="logloss", random_state=seed, n_jobs=4)),
            "randomforest_morgan": ("morgan", lambda: RandomForestClassifier(n_estimators=n_estimators, random_state=seed, n_jobs=-1, class_weight="balanced_subsample")),
            "extratrees_morgan": ("morgan", lambda: ExtraTreesClassifier(n_estimators=n_estimators, random_state=seed, n_jobs=-1, class_weight="balanced")),
        }
    return {
        "xgboost_rdkit": ("rdkit", lambda: XGBRegressor(n_estimators=n_estimators, max_depth=3, learning_rate=0.04, subsample=0.85, colsample_bytree=0.8, objective="reg:squarederror", random_state=seed, n_jobs=4)),
        "xgboost_morgan": ("morgan", lambda: XGBRegressor(n_estimators=n_estimators, max_depth=3, learning_rate=0.04, subsample=0.85, colsample_bytree=0.8, objective="reg:squarederror", random_state=seed, n_jobs=4)),
        "xgboost_morgancount": ("morgancount", lambda: XGBRegressor(n_estimators=n_estimators, max_depth=3, learning_rate=0.04, subsample=0.85, colsample_bytree=0.8, objective="reg:squarederror", random_state=seed, n_jobs=4)),
        "randomforest_morgan": ("morgan", lambda: RandomForestRegressor(n_estimators=n_estimators, random_state=seed, n_jobs=-1, max_features="sqrt")),
        "extratrees_morgan": ("morgan", lambda: ExtraTreesRegressor(n_estimators=n_estimators, random_state=seed, n_jobs=-1, max_features="sqrt")),
    }


def _predict(model, task_type: str, x: np.ndarray) -> np.ndarray:
    if task_type == "classification" and hasattr(model, "predict_proba"):
        return model.predict_proba(x)[:, 1]
    return np.asarray(model.predict(x), dtype=float)


def optional_dependency_rows(requested: list[str]) -> list[dict[str, object]]:
    optional = {
        "catboost_morgan": "catboost",
        "lightgbm_morgan": "lightgbm",
        "chemprop": "chemprop CLI",
        "tabpfn_rdkit": "tabpfn",
        "autogluon_rdkit": "autogluon.tabular",
        "kpgt_representation": "precomputed KPGT representation",
    }
    rows = []
    for model, dep in optional.items():
        if model in requested:
            rows.append({"module": "strong_baselines", "candidate": model, "status": "optional_not_run_by_default", "reason": f"Requires {dep} or a dedicated runner/precomputed features."})
    return rows


def run_strong_baselines(config: ExperimentConfig, datasets: list[str] | None = None, splits: list[str] | None = None) -> pd.DataFrame:
    requested = list(config.raw.get("strong_baselines", []))
    names = datasets or sorted(set(config.datasets("moleculenet") + config.datasets("tdc_admet")))
    split_names = splits or list(config.raw.get("splits", ["random", "scaffold", "perimeter"]))
    n_estimators = int(config.raw.get("n_estimators", 300))
    rows = []
    missing = optional_dependency_rows(requested)
    for dataset in names:
        try:
            frame, spec = load_dataset(dataset, config.data_dir)
        except Exception as exc:
            missing.append({"module": "strong_baselines", "dataset": dataset, "status": "missing_data", "reason": str(exc)})
            continue
        features_cache = {}
        for seed in config.seeds:
            for split_name in split_names:
                split = split_indices_for(frame, split_name, seed, config)
                factories = _available_model_factories(spec.task_type, seed, n_estimators)
                for model_name, (view, factory) in factories.items():
                    if requested and model_name not in requested:
                        continue
                    if view not in features_cache:
                        features_cache[view] = _feature_matrix(frame, view)
                    x = features_cache[view]
                    model = Pipeline([("scale", StandardScaler(with_mean=False)), ("model", factory())]) if view == "rdkit" else factory()
                    start = perf_counter()
                    model.fit(x[split.train], frame.iloc[split.train]["y"].to_numpy())
                    train_seconds = perf_counter() - start
                    for part, idx in [("valid", split.valid), ("test", split.test)]:
                        pred = _predict(model, spec.task_type, x[idx])
                        metrics = metrics_for_task(spec.task_type, frame.iloc[idx]["y"].to_numpy(), pred)
                        rows.append(
                            {
                                "dataset": dataset,
                                "seed": seed,
                                "split_strategy": split_name,
                                "split": part,
                                "task_type": spec.task_type,
                                "model": model_name,
                                "feature_view": view,
                                "n_train": len(split.train),
                                "n_valid": len(split.valid),
                                "n_test": len(split.test),
                                "train_seconds": train_seconds,
                                **metrics,
                            }
                        )
    out = pd.DataFrame(rows)
    write_csv(out, config.reports_dir / "strong_baselines_metrics.csv")
    if missing:
        write_csv(pd.DataFrame(missing), config.reports_dir / "missing_dependency_report.csv")
    return out
