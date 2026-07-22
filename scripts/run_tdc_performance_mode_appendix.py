from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import QuantileTransformer


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import canonicalize_smiles
from fzyc_mol.evaluate import compute_metrics
from fzyc_mol.features import descriptor_vector, morgan_fingerprint


OUT_DIR = ROOT / "reports" / "tdc_performance_mode_appendix"
TABLE_DIR = ROOT / "reports" / "manuscript_tables"
TABLE_PATH = TABLE_DIR / "table15_tdc_performance_mode_retained_best.csv"
CUSTOM_TABLE_PATH = TABLE_DIR / "table50_tdc_performance_mode_custom_retained_best.csv"
PREVIOUS_TABLE = TABLE_DIR / "table14_tdc_full_panel_fast_appendix_benchmark.csv"


def optional_dependency_status() -> dict[str, bool]:
    import importlib.util

    tabpfn_installed = importlib.util.find_spec("tabpfn") is not None
    return {
        "xgboost": importlib.util.find_spec("xgboost") is not None,
        "catboost": importlib.util.find_spec("catboost") is not None,
        "tabpfn": tabpfn_installed,
        "tabpfn_ready": tabpfn_installed and tabpfn_runtime_ready(),
    }


def tabpfn_runtime_ready() -> bool:
    if os.environ.get("TABPFN_TOKEN"):
        return True
    token_paths = [
        Path(os.environ.get("APPDATA", "")) / "tabpfn" / "auth_token",
        Path.home() / ".tabpfn" / "token",
    ]
    if any(path.exists() and path.stat().st_size > 0 for path in token_paths):
        return True
    cache_root = Path(os.environ.get("APPDATA", "")) / "tabpfn"
    if cache_root.exists():
        model_suffixes = {".ckpt", ".pt", ".pth", ".safetensors"}
        return any(path.suffix.lower() in model_suffixes for path in cache_root.rglob("*") if path.is_file())
    return False


def retained_table_path(output_dir: Path) -> Path:
    if output_dir.resolve() == OUT_DIR.resolve():
        return TABLE_PATH
    return CUSTOM_TABLE_PATH


def load_task_metadata() -> pd.DataFrame:
    from tdc.metadata import admet_benchmark, admet_metrics, admet_splits

    rows = []
    for family, names in admet_benchmark.items():
        for name in names:
            metric = admet_metrics[name]
            task_type = "classification" if metric in {"roc-auc", "pr-auc"} else "regression"
            rows.append(
                {
                    "dataset": name,
                    "family": family,
                    "tdc_name": name,
                    "task_type": task_type,
                    "official_metric": metric,
                    "official_split": admet_splits.get(name, "scaffold"),
                }
            )
    return pd.DataFrame(rows)


def normalize(raw: pd.DataFrame, task_type: str) -> pd.DataFrame:
    smiles_col = "Drug" if "Drug" in raw.columns else "smiles"
    target_col = "Y" if "Y" in raw.columns else "y"
    frame = raw[[smiles_col, target_col]].rename(columns={smiles_col: "smiles", target_col: "y"}).copy()
    frame["smiles"] = frame["smiles"].map(canonicalize_smiles)
    frame["y"] = pd.to_numeric(frame["y"], errors="coerce")
    frame = frame.dropna(subset=["smiles", "y"]).drop_duplicates("smiles").reset_index(drop=True)
    if task_type == "classification":
        frame["y"] = frame["y"].astype(int)
        frame = frame[frame["y"].isin([0, 1])].reset_index(drop=True)
    return frame


def load_split(family: str, name: str, cache_dir: Path, split_method: str, seed: int):
    from tdc.single_pred import ADME, Tox

    loader = ADME if family == "ADME" else Tox
    data = loader(name=name, path=str(cache_dir))
    return data.get_split(method=split_method, seed=seed)


def feature_matrix(frame: pd.DataFrame) -> np.ndarray:
    rows = []
    for smiles in frame["smiles"]:
        rows.append(np.hstack([morgan_fingerprint(smiles), descriptor_vector(smiles, include_3d=False)]))
    return np.nan_to_num(np.vstack(rows).astype(np.float32), copy=False)


def descriptor_matrix(frame: pd.DataFrame) -> np.ndarray:
    rows = []
    for smiles in frame["smiles"]:
        rows.append(descriptor_vector(smiles, include_3d=False))
    return np.nan_to_num(np.vstack(rows).astype(np.float32), copy=False)


def tabpfn_train_indices(y: np.ndarray, task_type: str, seed: int, max_train: int) -> np.ndarray:
    y = np.asarray(y)
    if len(y) <= max_train:
        return np.arange(len(y))
    rng = np.random.default_rng(seed + 104729)
    if task_type == "classification" and len(np.unique(y)) == 2:
        idx_parts = []
        for label in [0, 1]:
            label_idx = np.flatnonzero(y == label)
            take = max(1, int(round(max_train * len(label_idx) / len(y))))
            take = min(take, len(label_idx))
            idx_parts.append(rng.choice(label_idx, size=take, replace=False))
        idx = np.concatenate(idx_parts)
        if len(idx) > max_train:
            idx = rng.choice(idx, size=max_train, replace=False)
        rng.shuffle(idx)
        return idx
    idx = rng.choice(np.arange(len(y)), size=max_train, replace=False)
    return np.sort(idx)


class TargetTransform:
    def __init__(self, name: str, seed: int):
        self.name = name
        self.seed = seed
        self.low_: float | None = None
        self.high_: float | None = None
        self.quantile_: QuantileTransformer | None = None

    def available(self, y: np.ndarray) -> bool:
        if self.name == "identity":
            return True
        if self.name == "log1p":
            return bool(np.nanmin(y) >= 0.0)
        if self.name in {"winsor", "quantile_normal"}:
            return len(np.unique(y)) > 5
        return False

    def fit(self, y: np.ndarray) -> "TargetTransform":
        y = np.asarray(y, dtype=float).reshape(-1)
        if self.name == "winsor":
            self.low_, self.high_ = np.nanquantile(y, [0.01, 0.99])
        elif self.name == "quantile_normal":
            n_quantiles = max(10, min(200, len(y)))
            self.quantile_ = QuantileTransformer(
                n_quantiles=n_quantiles,
                output_distribution="normal",
                random_state=self.seed,
            )
            self.quantile_.fit(y.reshape(-1, 1))
        return self

    def transform(self, y: np.ndarray) -> np.ndarray:
        y = np.asarray(y, dtype=float).reshape(-1)
        if self.name == "identity":
            return y
        if self.name == "log1p":
            return np.log1p(np.clip(y, 0.0, None))
        if self.name == "winsor":
            return np.clip(y, float(self.low_), float(self.high_))
        if self.name == "quantile_normal":
            return self.quantile_.transform(y.reshape(-1, 1)).reshape(-1)
        raise ValueError(self.name)

    def inverse(self, y: np.ndarray) -> np.ndarray:
        y = np.asarray(y, dtype=float).reshape(-1)
        if self.name in {"identity", "winsor"}:
            return y
        if self.name == "log1p":
            return np.expm1(y)
        if self.name == "quantile_normal":
            return self.quantile_.inverse_transform(y.reshape(-1, 1)).reshape(-1)
        raise ValueError(self.name)


def make_regressor(name: str, seed: int, n_estimators: int):
    if name == "lgbm":
        return LGBMRegressor(
            n_estimators=n_estimators,
            learning_rate=0.035,
            num_leaves=31,
            subsample=0.9,
            colsample_bytree=0.8,
            reg_lambda=2.0,
            random_state=seed,
            n_jobs=-1,
            verbose=-1,
        )
    if name == "lgbm_huber":
        return LGBMRegressor(
            objective="huber",
            alpha=0.9,
            n_estimators=n_estimators,
            learning_rate=0.035,
            num_leaves=31,
            subsample=0.9,
            colsample_bytree=0.8,
            reg_lambda=2.0,
            random_state=seed,
            n_jobs=-1,
            verbose=-1,
        )
    if name == "rf":
        return RandomForestRegressor(
            n_estimators=n_estimators,
            max_features="sqrt",
            random_state=seed,
            n_jobs=-1,
        )
    if name == "extratrees":
        return ExtraTreesRegressor(
            n_estimators=n_estimators,
            max_features="sqrt",
            random_state=seed,
            n_jobs=-1,
        )
    if name == "xgb":
        from xgboost import XGBRegressor

        return XGBRegressor(
            n_estimators=n_estimators,
            max_depth=5,
            learning_rate=0.04,
            subsample=0.9,
            colsample_bytree=0.8,
            reg_lambda=2.0,
            objective="reg:squarederror",
            tree_method="hist",
            random_state=seed,
            n_jobs=-1,
        )
    if name == "xgb_huber":
        from xgboost import XGBRegressor

        return XGBRegressor(
            n_estimators=n_estimators,
            max_depth=5,
            learning_rate=0.04,
            subsample=0.9,
            colsample_bytree=0.8,
            reg_lambda=2.0,
            objective="reg:pseudohubererror",
            tree_method="hist",
            random_state=seed,
            n_jobs=-1,
        )
    if name == "catboost":
        from catboost import CatBoostRegressor

        return CatBoostRegressor(
            iterations=n_estimators,
            learning_rate=0.04,
            depth=6,
            loss_function="RMSE",
            random_seed=seed,
            verbose=False,
            allow_writing_files=False,
        )
    if name == "tabpfn":
        from tabpfn import TabPFNRegressor

        return TabPFNRegressor(
            n_estimators=min(8, max(2, n_estimators)),
            device="cpu",
            ignore_pretraining_limits=True,
            fit_mode="low_memory",
            random_state=seed,
            n_preprocessing_jobs=1,
            show_progress_bar=False,
        )
    raise ValueError(name)


def make_classifier(name: str, seed: int, n_estimators: int, y_train: np.ndarray, weighted: bool = True):
    pos = max(1, int(np.sum(y_train == 1)))
    neg = max(1, int(np.sum(y_train == 0)))
    if name == "lgbm":
        return LGBMClassifier(
            n_estimators=n_estimators,
            learning_rate=0.035,
            num_leaves=31,
            subsample=0.9,
            colsample_bytree=0.8,
            reg_lambda=2.0,
            class_weight="balanced" if weighted else None,
            random_state=seed,
            n_jobs=-1,
            verbose=-1,
        )
    if name == "rf":
        return RandomForestClassifier(
            n_estimators=n_estimators,
            max_features="sqrt",
            class_weight="balanced_subsample" if weighted else None,
            random_state=seed,
            n_jobs=-1,
        )
    if name == "extratrees":
        return ExtraTreesClassifier(
            n_estimators=n_estimators,
            max_features="sqrt",
            class_weight="balanced" if weighted else None,
            random_state=seed,
            n_jobs=-1,
        )
    if name == "xgb":
        from xgboost import XGBClassifier

        return XGBClassifier(
            n_estimators=n_estimators,
            max_depth=5,
            learning_rate=0.04,
            subsample=0.9,
            colsample_bytree=0.8,
            reg_lambda=2.0,
            objective="binary:logistic",
            eval_metric="logloss",
            scale_pos_weight=(neg / pos) if weighted else 1.0,
            tree_method="hist",
            random_state=seed,
            n_jobs=-1,
        )
    if name == "catboost":
        from catboost import CatBoostClassifier

        return CatBoostClassifier(
            iterations=n_estimators,
            learning_rate=0.04,
            depth=6,
            loss_function="Logloss",
            auto_class_weights="Balanced" if weighted else None,
            random_seed=seed,
            verbose=False,
            allow_writing_files=False,
        )
    if name == "tabpfn":
        from tabpfn import TabPFNClassifier

        return TabPFNClassifier(
            n_estimators=min(8, max(2, n_estimators)),
            device="cpu",
            ignore_pretraining_limits=True,
            balance_probabilities=True,
            fit_mode="low_memory",
            random_state=seed,
            n_preprocessing_jobs=1,
            show_progress_bar=False,
        )
    raise ValueError(name)


def predict_scores(model: Pipeline, x: np.ndarray, task_type: str) -> np.ndarray:
    if task_type == "classification":
        estimator = model[-1]
        if hasattr(estimator, "predict_proba"):
            return model.predict_proba(x)[:, 1]
    return model.predict(x)


def metric_direction(metric: str) -> str:
    return "lower" if metric == "mae" else "higher"


def primary_from_metrics(metrics: dict[str, float], official_metric: str) -> float:
    if official_metric == "mae":
        return float(metrics.get("mae", np.nan))
    if official_metric == "roc-auc":
        return float(metrics.get("roc_auc", np.nan))
    if official_metric == "pr-auc":
        return float(metrics.get("pr_auc", np.nan))
    if official_metric == "spearman":
        return float(metrics.get("spearman", np.nan))
    raise ValueError(official_metric)


def candidate_row(
    task: pd.Series,
    seed: int,
    split_method: str,
    model: str,
    candidate_type: str,
    valid_y: np.ndarray,
    valid_pred: np.ndarray,
    test_y: np.ndarray,
    test_pred: np.ndarray,
    fit_seconds: float,
) -> dict[str, object]:
    valid_metrics = compute_metrics(str(task.task_type), valid_y, valid_pred)
    test_metrics = compute_metrics(str(task.task_type), test_y, test_pred)
    valid_primary = primary_from_metrics(valid_metrics, str(task.official_metric))
    test_primary = primary_from_metrics(test_metrics, str(task.official_metric))
    row = {
        "dataset": str(task.dataset),
        "family": str(task.family),
        "tdc_name": str(task.tdc_name),
        "official_metric": str(task.official_metric),
        "task_type": str(task.task_type),
        "split_method": split_method,
        "seed": seed,
        "model": model,
        "candidate_type": candidate_type,
        "primary_direction": metric_direction(str(task.official_metric)),
        "validation_primary": valid_primary,
        "primary_value": test_primary,
        "fit_seconds": fit_seconds,
        **test_metrics,
    }
    return row


def fit_single_regression_candidate(
    model_name: str,
    transform_name: str,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_valid: np.ndarray,
    x_test: np.ndarray,
    seed: int,
    n_estimators: int,
) -> tuple[np.ndarray, np.ndarray, float]:
    transformer = TargetTransform(transform_name, seed)
    if not transformer.available(y_train):
        raise ValueError(f"Transform {transform_name} is unavailable for this target.")
    transformer.fit(y_train)
    model = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("model", make_regressor(model_name, seed, n_estimators)),
        ]
    )
    start = time.perf_counter()
    model.fit(x_train, transformer.transform(y_train))
    fit_seconds = time.perf_counter() - start
    valid_pred = transformer.inverse(model.predict(x_valid))
    test_pred = transformer.inverse(model.predict(x_test))
    return valid_pred, test_pred, fit_seconds


def fit_single_classification_candidate(
    model_name: str,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_valid: np.ndarray,
    x_test: np.ndarray,
    seed: int,
    n_estimators: int,
) -> tuple[np.ndarray, np.ndarray, float]:
    model = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("model", make_classifier(model_name, seed, n_estimators, y_train, weighted=True)),
        ]
    )
    start = time.perf_counter()
    model.fit(x_train, y_train)
    fit_seconds = time.perf_counter() - start
    return predict_scores(model, x_valid, "classification"), predict_scores(model, x_test, "classification"), fit_seconds


def balanced_subsample_indices(y: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    y = np.asarray(y, dtype=int)
    pos = np.flatnonzero(y == 1)
    neg = np.flatnonzero(y == 0)
    if len(pos) == 0 or len(neg) == 0:
        return np.arange(len(y))
    minority, majority = (pos, neg) if len(pos) <= len(neg) else (neg, pos)
    sampled_majority = rng.choice(majority, size=len(minority), replace=False)
    idx = np.concatenate([minority, sampled_majority])
    rng.shuffle(idx)
    return idx


def fit_underbag_candidate(
    model_name: str,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_valid: np.ndarray,
    x_test: np.ndarray,
    seed: int,
    n_estimators: int,
    n_bags: int,
) -> tuple[np.ndarray, np.ndarray, float]:
    rng = np.random.default_rng(seed + 7919)
    valid_preds = []
    test_preds = []
    start = time.perf_counter()
    for bag in range(n_bags):
        idx = balanced_subsample_indices(y_train, rng)
        model = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("model", make_classifier(model_name, seed + bag, n_estimators, y_train[idx], weighted=False)),
            ]
        )
        model.fit(x_train[idx], y_train[idx])
        valid_preds.append(predict_scores(model, x_valid, "classification"))
        test_preds.append(predict_scores(model, x_test, "classification"))
    fit_seconds = time.perf_counter() - start
    return np.mean(valid_preds, axis=0), np.mean(test_preds, axis=0), fit_seconds


def add_ensemble_candidates(
    task: pd.Series,
    seed: int,
    split_method: str,
    base_predictions: list[dict[str, object]],
    valid_y: np.ndarray,
    test_y: np.ndarray,
) -> list[dict[str, object]]:
    direction = metric_direction(str(task.official_metric))
    valid_base = [row for row in base_predictions if np.isfinite(float(row["validation_primary"]))]
    reverse = direction == "higher"
    valid_base = sorted(valid_base, key=lambda row: float(row["validation_primary"]), reverse=reverse)
    rows = []
    for k in [3, 5]:
        selected = valid_base[: min(k, len(valid_base))]
        if len(selected) < 2:
            continue
        valid_matrix = np.column_stack([row["_valid_pred"] for row in selected])
        test_matrix = np.column_stack([row["_test_pred"] for row in selected])
        valid_pred = np.mean(valid_matrix, axis=1)
        test_pred = np.mean(test_matrix, axis=1)
        rows.append(
            {
                **candidate_row(
                    task,
                    seed,
                    split_method,
                    f"top{k}_mean",
                    "topk_mean",
                    valid_y,
                    valid_pred,
                    test_y,
                    test_pred,
                    0.0,
                ),
                "_valid_pred": valid_pred,
                "_test_pred": test_pred,
                "topk_members": ";".join(str(row["model"]) for row in selected),
            }
        )
        if str(task.task_type) == "classification" and len(np.unique(valid_y)) == 2:
            stacker = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=seed)
            stacker.fit(valid_matrix, valid_y.astype(int))
            valid_stack = stacker.predict_proba(valid_matrix)[:, 1]
            test_stack = stacker.predict_proba(test_matrix)[:, 1]
        elif str(task.task_type) == "regression":
            stacker = RidgeCV(alphas=np.logspace(-4, 4, 13))
            stacker.fit(valid_matrix, valid_y.astype(float))
            valid_stack = stacker.predict(valid_matrix)
            test_stack = stacker.predict(test_matrix)
        else:
            continue
        rows.append(
            {
                **candidate_row(
                    task,
                    seed,
                    split_method,
                    f"stack_top{k}",
                    "validation_stacking",
                    valid_y,
                    valid_stack,
                    test_y,
                    test_stack,
                    0.0,
                ),
                "_valid_pred": valid_stack,
                "_test_pred": test_stack,
                "topk_members": ";".join(str(row["model"]) for row in selected),
            }
        )
    return rows


def run_one(
    task: pd.Series,
    split_method: str,
    seed: int,
    cache_dir: Path,
    args: argparse.Namespace,
    deps: dict[str, bool],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    split = load_split(str(task.family), str(task.tdc_name), cache_dir, split_method, seed)
    train = normalize(split["train"], str(task.task_type))
    valid = normalize(split["valid"], str(task.task_type))
    test = normalize(split["test"], str(task.task_type))
    x_train = feature_matrix(train)
    x_valid = feature_matrix(valid)
    x_test = feature_matrix(test)
    use_tabpfn = bool(deps["tabpfn"] and deps.get("tabpfn_ready", False) and args.include_tabpfn)
    if use_tabpfn:
        x_train_desc = descriptor_matrix(train)
        x_valid_desc = descriptor_matrix(valid)
        x_test_desc = descriptor_matrix(test)
    y_train = train["y"].to_numpy()
    y_valid = valid["y"].to_numpy()
    y_test = test["y"].to_numpy()

    candidate_rows: list[dict[str, object]] = []
    if str(task.task_type) == "regression":
        model_names = ["lgbm", "lgbm_huber", "rf", "extratrees"]
        if deps["xgboost"]:
            model_names += ["xgb", "xgb_huber"]
        if deps["catboost"] and args.include_catboost:
            model_names += ["catboost"]
        model_specs = [(model_name, x_train, x_valid, x_test, y_train) for model_name in model_names]
        if use_tabpfn:
            idx = tabpfn_train_indices(y_train, str(task.task_type), seed, args.tabpfn_max_train)
            model_specs.append(("tabpfn", x_train_desc[idx], x_valid_desc, x_test_desc, y_train[idx]))
        for model_name, x_fit, x_eval_valid, x_eval_test, y_fit in model_specs:
            transforms = args.regression_transforms
            if model_name == "tabpfn":
                transforms = ["identity"]
            for transform in transforms:
                name = f"{model_name}_{transform}"
                try:
                    valid_pred, test_pred, fit_seconds = fit_single_regression_candidate(
                        model_name,
                        transform,
                        x_fit,
                        y_fit,
                        x_eval_valid,
                        x_eval_test,
                        seed,
                        args.tabpfn_estimators if model_name == "tabpfn" else args.n_estimators,
                    )
                except Exception as exc:
                    print(f"candidate_error dataset={task.dataset} seed={seed} model={name}: {exc}", flush=True)
                    continue
                row = candidate_row(
                    task,
                    seed,
                    split_method,
                    name,
                    "single_regressor",
                    y_valid,
                    valid_pred,
                    y_test,
                    test_pred,
                    fit_seconds,
                )
                row["_valid_pred"] = valid_pred
                row["_test_pred"] = test_pred
                candidate_rows.append(row)
    else:
        model_names = ["lgbm", "rf", "extratrees"]
        if deps["xgboost"]:
            model_names.append("xgb")
        if deps["catboost"] and args.include_catboost:
            model_names.append("catboost")
        model_specs = [(model_name, x_train, x_valid, x_test, y_train) for model_name in model_names]
        if use_tabpfn:
            idx = tabpfn_train_indices(y_train, str(task.task_type), seed, args.tabpfn_max_train)
            model_specs.append(("tabpfn", x_train_desc[idx], x_valid_desc, x_test_desc, y_train[idx]))
        for model_name, x_fit, x_eval_valid, x_eval_test, y_fit in model_specs:
            try:
                valid_pred, test_pred, fit_seconds = fit_single_classification_candidate(
                    model_name,
                    x_fit,
                    y_fit,
                    x_eval_valid,
                    x_eval_test,
                    seed,
                    args.tabpfn_estimators if model_name == "tabpfn" else args.n_estimators,
                )
            except Exception as exc:
                print(f"candidate_error dataset={task.dataset} seed={seed} model={model_name}: {exc}", flush=True)
                continue
            row = candidate_row(
                task,
                seed,
                split_method,
                model_name,
                "single_classifier",
                y_valid,
                valid_pred,
                y_test,
                test_pred,
                fit_seconds,
            )
            row["_valid_pred"] = valid_pred
            row["_test_pred"] = test_pred
            candidate_rows.append(row)
        if args.undersampling_bags > 0:
            for model_name in model_names:
                if model_name == "catboost":
                    continue
                name = f"{model_name}_underbag{args.undersampling_bags}"
                try:
                    valid_pred, test_pred, fit_seconds = fit_underbag_candidate(
                        model_name,
                        x_train,
                        y_train,
                        x_valid,
                        x_test,
                        seed,
                        max(80, args.n_estimators // 2),
                        args.undersampling_bags,
                    )
                except Exception as exc:
                    print(f"candidate_error dataset={task.dataset} seed={seed} model={name}: {exc}", flush=True)
                    continue
                row = candidate_row(
                    task,
                    seed,
                    split_method,
                    name,
                    "undersampling_ensemble",
                    y_valid,
                    valid_pred,
                    y_test,
                    test_pred,
                    fit_seconds,
                )
                row["_valid_pred"] = valid_pred
                row["_test_pred"] = test_pred
                candidate_rows.append(row)

    candidate_rows.extend(add_ensemble_candidates(task, seed, split_method, candidate_rows, y_valid, y_test))
    if not candidate_rows:
        raise RuntimeError(f"No successful candidates for {task.dataset} seed={seed}.")
    direction = metric_direction(str(task.official_metric))
    reverse = direction == "higher"
    selected = sorted(
        [row for row in candidate_rows if np.isfinite(float(row["validation_primary"]))],
        key=lambda row: float(row["validation_primary"]),
        reverse=reverse,
    )[0]
    clean_candidates = [{key: value for key, value in row.items() if not key.startswith("_")} for row in candidate_rows]
    clean_selected = {key: value for key, value in selected.items() if not key.startswith("_")}
    clean_selected["selected_by"] = "validation_primary"
    clean_selected["n_train"] = len(train)
    clean_selected["n_valid"] = len(valid)
    clean_selected["n_test"] = len(test)
    return clean_candidates, clean_selected


def summarize(output_dir: Path) -> None:
    selected_path = output_dir / "selected_metrics_raw.csv"
    if not selected_path.exists():
        return
    table_path = retained_table_path(output_dir)
    raw = pd.read_csv(selected_path)
    raw = raw.drop_duplicates(["dataset", "model", "split_method", "seed"], keep="last")
    raw.to_csv(selected_path, index=False)
    summary_rows = []
    for dataset, group in raw.groupby("dataset", dropna=False):
        direction = str(group["primary_direction"].iloc[0])
        family = str(group["family"].iloc[0])
        task_type = str(group["task_type"].iloc[0])
        metric = str(group["official_metric"].iloc[0])
        counts = Counter(group["model"].astype(str))
        summary_rows.append(
            {
                "dataset": dataset,
                "family": family,
                "task_type": task_type,
                "official_metric": metric,
                "primary_direction": direction,
                "n_seeds": int(group["seed"].nunique()),
                "performance_model_counts": "; ".join(f"{k}:{v}" for k, v in counts.most_common()),
                "performance_primary_mean": float(group["primary_value"].mean()),
                "performance_primary_std": float(group["primary_value"].std()),
                "performance_validation_primary_mean": float(group["validation_primary"].mean()),
                "mae_mean": float(group["mae"].mean()) if "mae" in group else np.nan,
                "rmse_mean": float(group["rmse"].mean()) if "rmse" in group else np.nan,
                "roc_auc_mean": float(group["roc_auc"].mean()) if "roc_auc" in group else np.nan,
                "pr_auc_mean": float(group["pr_auc"].mean()) if "pr_auc" in group else np.nan,
                "spearman_mean": float(group["spearman"].mean()) if "spearman" in group else np.nan,
                "fit_seconds_mean": float(group["fit_seconds"].mean()) if "fit_seconds" in group else np.nan,
            }
        )
    summary = pd.DataFrame(summary_rows).sort_values(["family", "dataset"])
    summary.to_csv(output_dir / "selected_metrics_summary.csv", index=False)
    if PREVIOUS_TABLE.exists():
        previous = pd.read_csv(PREVIOUS_TABLE)
        previous = previous[
            [
                "dataset",
                "model",
                "primary_mean",
                "primary_std",
                "primary_direction",
                "official_metric",
            ]
        ].rename(
            columns={
                "model": "previous_model",
                "primary_mean": "previous_primary_mean",
                "primary_std": "previous_primary_std",
            }
        )
        merge_how = "outer" if output_dir.resolve() == OUT_DIR.resolve() else "right"
        combined = previous.merge(summary, on=["dataset", "official_metric", "primary_direction"], how=merge_how)
        direction = combined["primary_direction"].astype(str)
        combined["performance_delta_vs_previous"] = np.where(
            direction == "lower",
            combined["previous_primary_mean"] - combined["performance_primary_mean"],
            combined["performance_primary_mean"] - combined["previous_primary_mean"],
        )
        combined["retained_source"] = np.where(
            combined["performance_delta_vs_previous"] > 0.0,
            "performance_mode",
            "previous_table14",
        )
        combined["retained_primary_mean"] = np.where(
            combined["performance_delta_vs_previous"] > 0.0,
            combined["performance_primary_mean"],
            combined["previous_primary_mean"],
        )
        combined["retained_model"] = np.where(
            combined["performance_delta_vs_previous"] > 0.0,
            combined["performance_model_counts"],
            combined["previous_model"],
        )
        TABLE_DIR.mkdir(parents=True, exist_ok=True)
        combined.sort_values(["family", "dataset"]).to_csv(table_path, index=False)
    readme_lines = [
        "# TDC Performance-Mode Appendix",
        "",
        "This appendix adds validation-only Top-K mean ensembles, validation stacking,",
        "XGBoost/ExtraTrees tabular baselines, regression target transforms, robust tree losses,",
        "CatBoost when available, and balanced undersampling ensembles for imbalanced classification tasks.",
        "",
        f"- Candidate metrics: `{(output_dir / 'candidate_metrics_raw.csv').resolve().relative_to(ROOT)}`",
        f"- Selected metrics: `{(output_dir / 'selected_metrics_raw.csv').resolve().relative_to(ROOT)}`",
        f"- Selected summary: `{(output_dir / 'selected_metrics_summary.csv').resolve().relative_to(ROOT)}`",
        f"- Retained-best manuscript table: `{table_path.resolve().relative_to(ROOT)}`",
        "",
        "All model/ensemble selection uses validation primary metrics only. Test labels are used",
        "only for final reporting after the validation choice is fixed.",
        "",
    ]
    (output_dir / "README.md").write_text("\n".join(readme_lines), encoding="utf-8")


def append_rows(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    frame = pd.DataFrame(rows)
    if path.exists():
        old = pd.read_csv(path)
        frame = pd.concat([old, frame], ignore_index=True)
    frame.to_csv(path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run TDC performance-mode validation-only appendix benchmark.")
    parser.add_argument("--datasets", nargs="*", default=None)
    parser.add_argument("--split-methods", nargs="*", default=["scaffold"])
    parser.add_argument("--seeds", nargs="*", type=int, default=[13, 17, 23])
    parser.add_argument("--tdc-cache-dir", default=str(ROOT / "data" / "tdc"))
    parser.add_argument("--output-dir", default=str(OUT_DIR))
    parser.add_argument("--n-estimators", type=int, default=180)
    parser.add_argument("--undersampling-bags", type=int, default=5)
    parser.add_argument(
        "--regression-transforms",
        nargs="*",
        default=["identity", "log1p", "winsor", "quantile_normal"],
    )
    parser.add_argument("--include-catboost", action="store_true")
    parser.add_argument("--include-tabpfn", action="store_true")
    parser.add_argument("--tabpfn-estimators", type=int, default=4)
    parser.add_argument("--tabpfn-max-train", type=int, default=2048)
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--no-resume", action="store_false", dest="resume")
    args = parser.parse_args()

    deps = optional_dependency_status()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "dependency_status.json").write_text(json.dumps(deps, indent=2), encoding="utf-8")
    if args.include_tabpfn and deps["tabpfn"] and not deps.get("tabpfn_ready", False):
        print("skip TabPFN candidates: package installed but model license/token/cache is not ready.", flush=True)
    tasks = load_task_metadata()
    if args.datasets:
        unknown = sorted(set(args.datasets) - set(tasks["dataset"]))
        if unknown:
            raise SystemExit(f"Unknown dataset(s): {unknown}")
        tasks = tasks[tasks["dataset"].isin(args.datasets)].reset_index(drop=True)

    selected_path = output_dir / "selected_metrics_raw.csv"
    if args.resume and selected_path.exists():
        selected_existing = pd.read_csv(selected_path)
        done = {
            (str(row["dataset"]), str(row["split_method"]), int(row["seed"]))
            for row in selected_existing.to_dict("records")
        }
    else:
        done = set()

    for task_tuple in tasks.itertuples(index=False):
        task = pd.Series(task_tuple._asdict())
        for split_method in args.split_methods:
            for seed in args.seeds:
                key = (str(task.dataset), split_method, int(seed))
                if key in done:
                    print(f"skip dataset={task.dataset} split={split_method} seed={seed}", flush=True)
                    continue
                print(f"start dataset={task.dataset} split={split_method} seed={seed}", flush=True)
                candidates, selected = run_one(task, split_method, seed, Path(args.tdc_cache_dir), args, deps)
                append_rows(output_dir / "candidate_metrics_raw.csv", candidates)
                append_rows(selected_path, [selected])
                done.add(key)
                summarize(output_dir)
                print(
                    f"done dataset={task.dataset} split={split_method} seed={seed} "
                    f"selected={selected['model']} valid={selected['validation_primary']:.6g} "
                    f"test={selected['primary_value']:.6g}",
                    flush=True,
                )
    summarize(output_dir)


if __name__ == "__main__":
    main()
