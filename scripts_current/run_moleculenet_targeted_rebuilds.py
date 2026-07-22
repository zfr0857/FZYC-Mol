from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRegressor
from rdkit import RDLogger
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

from fzyc_mol.datasets import load_dataset
from fzyc_mol.evaluate import compute_metrics
from fzyc_mol.features import descriptor_vector, morgan_fingerprint
from fzyc_mol.splits import make_split


RDLogger.DisableLog("rdApp.*")

OUT_DIR = ROOT / "reports" / "moleculenet_targeted_rebuilds"
TABLE_DIR = ROOT / "reports" / "manuscript_tables"
FIG_DIR = ROOT / "reports" / "manuscript_figures_polished"
TABLE27_PATH = TABLE_DIR / "table27_moleculenet_targeted_rebuild_retained_best.csv"
TABLE28_PATH = TABLE_DIR / "table28_moleculenet_rebuild_priority_matrix.csv"
CURRENT_TABLE = TABLE_DIR / "table19_moleculenet_rescue_integrated_selector.csv"
DEFAULT_DATASETS = ["freesolv", "lipo", "clintox"]


def optional_dependency_status() -> dict[str, bool]:
    return {
        "xgboost": importlib.util.find_spec("xgboost") is not None,
        "catboost": importlib.util.find_spec("catboost") is not None,
    }


class TargetTransform:
    def __init__(self, name: str, seed: int):
        self.name = name
        self.seed = seed
        self.low_: float | None = None
        self.high_: float | None = None
        self.quantile_: QuantileTransformer | None = None

    def available(self, y: np.ndarray) -> bool:
        y = np.asarray(y, dtype=float).reshape(-1)
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


def feature_matrix(smiles: list[str]) -> np.ndarray:
    rows = []
    for smi in smiles:
        rows.append(np.hstack([morgan_fingerprint(smi), descriptor_vector(smi, include_3d=False)]))
    return np.nan_to_num(np.vstack(rows).astype(np.float32), copy=False)


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
            min_samples_leaf=1,
            random_state=seed,
            n_jobs=-1,
        )
    if name == "extratrees":
        return ExtraTreesRegressor(
            n_estimators=n_estimators,
            max_features="sqrt",
            min_samples_leaf=1,
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
    raise ValueError(name)


def predict_scores(model: Pipeline, x: np.ndarray, task_type: str) -> np.ndarray:
    if task_type == "classification":
        estimator = model[-1]
        if hasattr(estimator, "predict_proba"):
            return model.predict_proba(x)[:, 1]
    return model.predict(x)


def primary_value(task_type: str, metrics: dict[str, float]) -> tuple[float, str, str]:
    if task_type == "regression":
        return float(metrics.get("rmse", np.nan)), "rmse", "lower"
    return float(metrics.get("roc_auc", np.nan)), "roc_auc", "higher"


def score_delta(direction: str, old_value: float, new_value: float) -> float:
    if not np.isfinite(old_value) or not np.isfinite(new_value):
        return float("nan")
    if direction == "lower":
        return old_value - new_value
    return new_value - old_value


def candidate_row(
    dataset: str,
    task_type: str,
    seed: int,
    model: str,
    candidate_type: str,
    valid_y: np.ndarray,
    valid_pred: np.ndarray,
    test_y: np.ndarray,
    test_pred: np.ndarray,
    fit_seconds: float,
) -> dict[str, object]:
    valid_metrics = compute_metrics(task_type, valid_y, valid_pred)
    test_metrics = compute_metrics(task_type, test_y, test_pred)
    valid_primary, primary_metric, direction = primary_value(task_type, valid_metrics)
    test_primary, _, _ = primary_value(task_type, test_metrics)
    return {
        "dataset": dataset,
        "task_type": task_type,
        "seed": seed,
        "split": "scaffold",
        "model": model,
        "candidate_type": candidate_type,
        "primary_metric": primary_metric,
        "primary_direction": direction,
        "validation_primary": valid_primary,
        "primary_value": test_primary,
        "fit_seconds": fit_seconds,
        **{f"valid_{key}": value for key, value in valid_metrics.items()},
        **{f"test_{key}": value for key, value in test_metrics.items()},
    }


def fit_regression_candidate(
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
        raise ValueError(f"transform {transform_name} unavailable")
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


def fit_classification_candidate(
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
    dataset: str,
    task_type: str,
    seed: int,
    base_rows: list[dict[str, object]],
    valid_y: np.ndarray,
    test_y: np.ndarray,
) -> list[dict[str, object]]:
    if not base_rows:
        return []
    direction = str(base_rows[0]["primary_direction"])
    reverse = direction == "higher"
    valid_base = [row for row in base_rows if np.isfinite(float(row["validation_primary"]))]
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
                    dataset,
                    task_type,
                    seed,
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
        if task_type == "classification" and len(np.unique(valid_y)) == 2:
            stacker = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=seed)
            stacker.fit(valid_matrix, valid_y.astype(int))
            valid_stack = stacker.predict_proba(valid_matrix)[:, 1]
            test_stack = stacker.predict_proba(test_matrix)[:, 1]
        elif task_type == "regression":
            stacker = RidgeCV(alphas=np.logspace(-4, 4, 13))
            stacker.fit(valid_matrix, valid_y.astype(float))
            valid_stack = stacker.predict(valid_matrix)
            test_stack = stacker.predict(test_matrix)
        else:
            continue
        rows.append(
            {
                **candidate_row(
                    dataset,
                    task_type,
                    seed,
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


def run_one(dataset: str, seed: int, args: argparse.Namespace, deps: dict[str, bool]) -> tuple[list[dict[str, object]], dict[str, object]]:
    frame, spec = load_dataset(dataset, data_dir=ROOT / "data")
    smiles = frame["smiles"].tolist()
    x = feature_matrix(smiles)
    y = frame["y"].to_numpy()
    split = make_split(frame, "scaffold", seed)
    x_train, x_valid, x_test = x[split.train], x[split.valid], x[split.test]
    y_train, y_valid, y_test = y[split.train], y[split.valid], y[split.test]

    candidate_rows: list[dict[str, object]] = []
    if spec.task_type == "regression":
        model_names = ["lgbm", "lgbm_huber", "rf", "extratrees"]
        if deps["xgboost"]:
            model_names += ["xgb", "xgb_huber"]
        if deps["catboost"] and args.include_catboost:
            model_names += ["catboost"]
        for model_name in model_names:
            for transform in args.regression_transforms:
                name = f"{model_name}_{transform}"
                try:
                    valid_pred, test_pred, fit_seconds = fit_regression_candidate(
                        model_name,
                        transform,
                        x_train,
                        y_train,
                        x_valid,
                        x_test,
                        seed,
                        args.n_estimators,
                    )
                except Exception as exc:
                    print(f"candidate_error dataset={dataset} seed={seed} model={name}: {exc}", flush=True)
                    continue
                row = candidate_row(
                    dataset,
                    spec.task_type,
                    seed,
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
        for model_name in model_names:
            try:
                valid_pred, test_pred, fit_seconds = fit_classification_candidate(
                    model_name,
                    x_train,
                    y_train,
                    x_valid,
                    x_test,
                    seed,
                    args.n_estimators,
                )
            except Exception as exc:
                print(f"candidate_error dataset={dataset} seed={seed} model={model_name}: {exc}", flush=True)
                continue
            row = candidate_row(
                dataset,
                spec.task_type,
                seed,
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
                    print(f"candidate_error dataset={dataset} seed={seed} model={name}: {exc}", flush=True)
                    continue
                row = candidate_row(
                    dataset,
                    spec.task_type,
                    seed,
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

    candidate_rows.extend(add_ensemble_candidates(dataset, spec.task_type, seed, candidate_rows, y_valid, y_test))
    valid_candidates = [row for row in candidate_rows if np.isfinite(float(row["validation_primary"]))]
    if not valid_candidates:
        raise RuntimeError(f"No valid candidates for {dataset} seed={seed}.")
    direction = str(valid_candidates[0]["primary_direction"])
    selected = sorted(
        valid_candidates,
        key=lambda row: float(row["validation_primary"]),
        reverse=(direction == "higher"),
    )[0]
    clean_candidates = [{key: value for key, value in row.items() if not key.startswith("_")} for row in candidate_rows]
    clean_selected = {key: value for key, value in selected.items() if not key.startswith("_")}
    clean_selected["selected_by"] = "validation_primary"
    clean_selected["n_train"] = len(split.train)
    clean_selected["n_valid"] = len(split.valid)
    clean_selected["n_test"] = len(split.test)
    return clean_candidates, clean_selected


def append_rows(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    frame = pd.DataFrame(rows)
    if path.exists():
        old = pd.read_csv(path)
        frame = pd.concat([old, frame], ignore_index=True)
    frame.to_csv(path, index=False)


def summarize(output_dir: Path) -> None:
    selected_path = output_dir / "selected_metrics_raw.csv"
    if not selected_path.exists():
        return
    raw = pd.read_csv(selected_path)
    raw = raw.drop_duplicates(["dataset", "seed"], keep="last")
    raw.to_csv(selected_path, index=False)

    summary_rows = []
    for dataset, group in raw.groupby("dataset", dropna=False):
        counts = Counter(group["model"].astype(str))
        row: dict[str, object] = {
            "dataset": dataset,
            "task_type": str(group["task_type"].iloc[0]),
            "primary_metric": str(group["primary_metric"].iloc[0]),
            "primary_direction": str(group["primary_direction"].iloc[0]),
            "n_seeds": int(group["seed"].nunique()),
            "rebuild_model_counts": "; ".join(f"{key}:{value}" for key, value in counts.most_common()),
            "rebuild_primary_mean": float(group["primary_value"].mean()),
            "rebuild_primary_std": float(group["primary_value"].std(ddof=1)),
            "rebuild_validation_primary_mean": float(group["validation_primary"].mean()),
            "fit_seconds_mean": float(group["fit_seconds"].mean()),
        }
        for metric in ["rmse", "mae", "roc_auc", "pr_auc", "brier", "ece"]:
            col = f"test_{metric}"
            row[f"{metric}_mean"] = float(group[col].mean()) if col in group else np.nan
            row[f"{metric}_std"] = float(group[col].std(ddof=1)) if col in group else np.nan
        summary_rows.append(row)
    summary = pd.DataFrame(summary_rows).sort_values("dataset")
    summary.to_csv(output_dir / "selected_metrics_summary.csv", index=False)

    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    if CURRENT_TABLE.exists():
        current = pd.read_csv(CURRENT_TABLE)
        current["integration_better_flag"] = current["integration_better_than_current"].astype(str).str.lower().eq("true")
        current["current_or_rescue_primary_mean"] = np.where(
            current["integration_better_flag"],
            current["integrated_primary_mean"],
            current["current_primary_mean"],
        )
        current["current_or_rescue_primary_std"] = np.where(
            current["integration_better_flag"],
            current["integrated_primary_std"],
            current["current_primary_std"],
        )
        current["current_or_rescue_model"] = np.where(
            current["integration_better_flag"],
            current["selected_model_counts"],
            current["current_model"],
        )
        current = current[
            [
                "dataset",
                "current_model",
                "current_primary_mean",
                "current_primary_std",
                "current_or_rescue_primary_mean",
                "current_or_rescue_primary_std",
                "current_or_rescue_model",
                "primary_direction",
                "primary_metric",
            ]
        ]
        combined = current.merge(summary, on=["dataset", "primary_metric", "primary_direction"], how="right")
        combined["delta_vs_current_or_rescue"] = combined.apply(
            lambda row: score_delta(
                str(row["primary_direction"]),
                float(row["current_or_rescue_primary_mean"]),
                float(row["rebuild_primary_mean"]),
            ),
            axis=1,
        )
        combined["retained_source"] = np.where(
            combined["delta_vs_current_or_rescue"] > 0.0,
            "targeted_rebuild",
            "current_or_rescue_selector",
        )
        combined["retained_primary_mean"] = np.where(
            combined["delta_vs_current_or_rescue"] > 0.0,
            combined["rebuild_primary_mean"],
            combined["current_or_rescue_primary_mean"],
        )
        combined["retained_primary_std"] = np.where(
            combined["delta_vs_current_or_rescue"] > 0.0,
            combined["rebuild_primary_std"],
            combined["current_or_rescue_primary_std"],
        )
        combined["retained_model"] = np.where(
            combined["delta_vs_current_or_rescue"] > 0.0,
            combined["rebuild_model_counts"],
            combined["current_or_rescue_model"],
        )
        combined.sort_values("dataset").to_csv(TABLE27_PATH, index=False)

        priority = combined.copy()
        priority["rebuild_action"] = np.where(
            priority["delta_vs_current_or_rescue"] > 0.0,
            "promote to appendix retained-best; consider selector pool integration",
            "keep as diagnostic; do not replace current selector",
        )
        priority["interpretation"] = np.select(
            [
                priority["dataset"].eq("freesolv") & (priority["delta_vs_current_or_rescue"] <= 0.0),
                priority["dataset"].eq("lipo") & (priority["delta_vs_current_or_rescue"] > 0.0),
                priority["dataset"].eq("clintox") & priority["task_type"].eq("classification"),
            ],
            [
                "small-data hydration/free-energy remains a limitation; prefer chemprop/better physics features before further tabular tuning",
                "tabular target-transform or validation ensemble still adds useful performance evidence",
                "judge by ROC-AUC plus PR-AUC/Brier/ECE because class imbalance can hide reliability failures",
            ],
            default="use as targeted rebuild evidence only",
        )
        priority[
            [
                "dataset",
                "task_type",
                "primary_metric",
                "current_or_rescue_primary_mean",
                "rebuild_primary_mean",
                "delta_vs_current_or_rescue",
                "retained_source",
                "rebuild_action",
                "interpretation",
            ]
        ].to_csv(TABLE28_PATH, index=False)
        plot_decision_figure(combined)

    readme_lines = [
        "# MoleculeNet Targeted Rebuilds",
        "",
        "This appendix runs low-cost rebuildable models on the low-score or high-sensitivity MoleculeNet modules.",
        "The candidate pool uses Morgan fingerprints plus RDKit descriptors, target transforms for regression,",
        "validation-only Top-K / stacking ensembles, and balanced undersampling ensembles for imbalanced classification.",
        "",
        f"- Candidate metrics: `{(output_dir / 'candidate_metrics_raw.csv').resolve().relative_to(ROOT)}`",
        f"- Selected metrics: `{(output_dir / 'selected_metrics_raw.csv').resolve().relative_to(ROOT)}`",
        f"- Selected summary: `{(output_dir / 'selected_metrics_summary.csv').resolve().relative_to(ROOT)}`",
        "- Retained-best table: `reports/manuscript_tables/table27_moleculenet_targeted_rebuild_retained_best.csv`",
        "- Priority table: `reports/manuscript_tables/table28_moleculenet_rebuild_priority_matrix.csv`",
        "",
    ]
    if TABLE27_PATH.exists():
        retained = pd.read_csv(TABLE27_PATH)
        readme_lines.extend(["## Retained-Best Outcome", ""])
        for row in retained.itertuples(index=False):
            readme_lines.append(
                f"- `{row.dataset}`: current/rescue={row.current_or_rescue_primary_mean:.4f}, "
                f"rebuild={row.rebuild_primary_mean:.4f}, "
                f"delta={row.delta_vs_current_or_rescue:+.4f}, retained=`{row.retained_source}`."
            )
        readme_lines.append("")
    readme_lines.extend(
        [
            "All model selection uses validation primary metrics only. Test labels are used only after the validation choice is fixed.",
        ]
    )
    (output_dir / "README.md").write_text("\n".join(readme_lines), encoding="utf-8")


def plot_decision_figure(combined: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    plot = combined.copy().sort_values("delta_vs_current_or_rescue")
    labels = [
        f"{row.dataset}\n{row.primary_metric.upper()}"
        for row in plot.itertuples(index=False)
    ]
    deltas = plot["delta_vs_current_or_rescue"].astype(float).to_numpy()
    colors = ["#1b8a6b" if value > 0 else "#d7dee8" for value in deltas]

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.edgecolor": "#cbd5e1",
            "axes.labelcolor": "#0f172a",
            "xtick.color": "#334155",
            "ytick.color": "#334155",
            "figure.dpi": 180,
            "savefig.dpi": 320,
        }
    )
    fig, ax = plt.subplots(figsize=(8.8, 4.55))
    y_pos = np.arange(len(plot))
    ax.barh(y_pos, deltas, color=colors, alpha=0.96, height=0.58, edgecolor="white", linewidth=0.8)
    ax.axvline(0, color="#334155", linewidth=0.9)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Validation-normalized gain vs current/rescue selector")
    ax.set_title("Targeted rebuild gate", loc="left", pad=12, fontsize=12.5, fontweight="bold")
    ax.grid(axis="x", color="#e5e7eb", linewidth=0.65, alpha=0.85)
    ax.set_axisbelow(True)
    span = max(0.02, float(np.nanmax(np.abs(deltas))) * 0.15)
    for y, row, delta in zip(y_pos, plot.itertuples(index=False), deltas):
        source = "promote rebuild" if delta > 0 else "keep current"
        text = f"{delta:+.3f} | {source}"
        if delta > 0:
            x = delta + span * 0.25
            ha = "left"
            color = "#14532d"
        else:
            x = delta + span * 0.25
            ha = "left"
            color = "#475569"
        ax.text(x, y, text, va="center", ha=ha, fontsize=8.8, color=color, fontweight="bold")
    max_abs = max(0.08, float(np.nanmax(np.abs(deltas))) + span)
    ax.set_xlim(-max_abs, max_abs)
    fig.text(
        0.125,
        0.03,
        "Green bars are promoted; gray bars keep the previous retained result. Lower RMSE and higher ROC-AUC are both converted to positive-delta gain.",
        fontsize=8.3,
        color="#475569",
        ha="left",
        va="center",
    )
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color("#e2e8f0")
    ax.spines["bottom"].set_color("#e2e8f0")
    fig.tight_layout(rect=[0, 0.06, 1, 1])
    for ext in ["png", "svg"]:
        fig.savefig(FIG_DIR / f"fig17_moleculenet_targeted_rebuild_decision.{ext}", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run targeted rebuilds for low-score MoleculeNet modules.")
    parser.add_argument("--datasets", nargs="*", default=DEFAULT_DATASETS)
    parser.add_argument("--seeds", nargs="*", type=int, default=[13, 17, 23, 29, 31])
    parser.add_argument("--output-dir", default=str(OUT_DIR))
    parser.add_argument("--n-estimators", type=int, default=220)
    parser.add_argument("--undersampling-bags", type=int, default=7)
    parser.add_argument(
        "--regression-transforms",
        nargs="*",
        default=["identity", "log1p", "winsor", "quantile_normal"],
    )
    parser.add_argument("--include-catboost", action="store_true")
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--no-resume", action="store_false", dest="resume")
    args = parser.parse_args()

    deps = optional_dependency_status()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "dependency_status.json").write_text(json.dumps(deps, indent=2), encoding="utf-8")

    selected_path = output_dir / "selected_metrics_raw.csv"
    if args.resume and selected_path.exists():
        existing = pd.read_csv(selected_path)
        done = {(str(row["dataset"]), int(row["seed"])) for row in existing.to_dict("records")}
    else:
        done = set()

    for dataset in args.datasets:
        for seed in args.seeds:
            key = (dataset, int(seed))
            if key in done:
                print(f"skip dataset={dataset} seed={seed}", flush=True)
                continue
            print(f"run dataset={dataset} seed={seed}", flush=True)
            candidates, selected = run_one(dataset, seed, args, deps)
            append_rows(output_dir / "candidate_metrics_raw.csv", candidates)
            append_rows(selected_path, [selected])
            summarize(output_dir)

    summarize(output_dir)
    print(f"wrote {output_dir}", flush=True)


if __name__ == "__main__":
    main()
