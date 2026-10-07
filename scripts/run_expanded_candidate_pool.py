# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import time
import warnings
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from catboost import CatBoostClassifier, CatBoostRegressor
from lightgbm import LGBMClassifier, LGBMRegressor
from rdkit import Chem, DataStructs, RDLogger, rdBase
from rdkit.Chem import AllChem
from rdkit.Chem.Scaffolds import MurckoScaffold
from scipy.stats import spearmanr
from sklearn.base import clone
from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import ElasticNet, LogisticRegression, Ridge
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold, KFold, StratifiedGroupKFold, StratifiedKFold
from xgboost import XGBClassifier, XGBRegressor


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = Path(os.environ.get("FZYC_NESTED_OUT", ROOT / "reports" / "draft10_core_experiments_20260621" / "expanded_nested"))
TASK_DIR = OUT / "tasks"
TASKS = [
    "bbbp",
    "bace",
    "clintox",
    "esol",
    "freesolv",
    "lipo",
    "tdc_caco2_wang",
    "tdc_hia_hou",
    "tdc_pgp_broccatelli",
]
POOL_SIZES = [4, 8, 16, 32]
POLICIES = ["fixed_single", "validation_best", "one_se_stable", "risk_adjusted", "test_oracle"]

RDLogger.DisableLog("rdApp.*")
warnings.filterwarnings("ignore")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", nargs="*", default=TASKS)
    parser.add_argument("--outer-folds", type=int, default=3)
    parser.add_argument("--inner-folds", type=int, default=3)
    parser.add_argument("--max-candidates", type=int, default=32, choices=[4, 8, 16, 32])
    parser.add_argument("--seed", type=int, default=20260621)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def pick_column(df: pd.DataFrame, candidates: list[str]) -> str:
    lower = {c.lower(): c for c in df.columns}
    for col in candidates:
        if col in df.columns:
            return col
        if col.lower() in lower:
            return lower[col.lower()]
    raise KeyError(f"No column from {candidates}; columns={list(df.columns)[:20]}")


def load_task(task: str, registry: dict) -> tuple[pd.DataFrame, str]:
    meta = registry[task]
    path = DATA / "raw" / meta["filename"]
    if not path.exists():
        path = DATA / "tdc" / meta["filename"].replace(".csv", ".tab")
    sep = "\t" if path.suffix == ".tab" else ","
    df = pd.read_csv(path, sep=sep)
    smiles_col = pick_column(df, meta["smiles_candidates"])
    target_col = pick_column(df, meta["target_candidates"])
    frame = df[[smiles_col, target_col]].rename(columns={smiles_col: "smiles", target_col: "y"})
    frame["y"] = pd.to_numeric(frame["y"], errors="coerce")
    frame = frame.dropna(subset=["smiles", "y"]).drop_duplicates("smiles").reset_index(drop=True)
    if meta["task_type"] == "classification":
        frame["y"] = frame["y"].astype(int)
    return frame, meta["task_type"]


def featurize(smiles: pd.Series, n_bits: int = 512) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    features: list[np.ndarray] = []
    scaffolds: list[str] = []
    keep: list[bool] = []
    for smi in smiles.astype(str):
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            keep.append(False)
            continue
        arr = np.zeros(n_bits, dtype=np.float32)
        fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=n_bits)
        DataStructs.ConvertToNumpyArray(fp, arr)
        scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False)
        if not scaffold:
            scaffold = Chem.MolToSmiles(mol, canonical=True)
        features.append(arr)
        scaffolds.append(scaffold)
        keep.append(True)
    return np.vstack(features), np.asarray(scaffolds), np.asarray(keep, dtype=bool)


def candidate_specs(task_type: str, seed: int) -> list[dict[str, object]]:
    if task_type == "classification":
        models = [
            ("logreg_l2_c0.1", LogisticRegression(C=0.1, max_iter=3000, class_weight="balanced", solver="liblinear"), "linear"),
            ("logreg_l2_c1", LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced", solver="liblinear"), "linear"),
            ("logreg_l2_c10", LogisticRegression(C=10.0, max_iter=3000, class_weight="balanced", solver="liblinear"), "linear"),
            ("logreg_l1_c1", LogisticRegression(C=1.0, penalty="l1", max_iter=3000, class_weight="balanced", solver="liblinear"), "linear"),
            ("rf_60_sqrt", RandomForestClassifier(n_estimators=60, max_features="sqrt", class_weight="balanced_subsample", random_state=seed, n_jobs=-1), "bagging"),
            ("rf_90_d12", RandomForestClassifier(n_estimators=90, max_depth=12, max_features="sqrt", class_weight="balanced_subsample", random_state=seed, n_jobs=-1), "bagging"),
            ("rf_90_leaf2", RandomForestClassifier(n_estimators=90, min_samples_leaf=2, max_features="sqrt", class_weight="balanced_subsample", random_state=seed, n_jobs=-1), "bagging"),
            ("rf_120_d20_leaf2", RandomForestClassifier(n_estimators=120, max_depth=20, min_samples_leaf=2, max_features="sqrt", class_weight="balanced_subsample", random_state=seed, n_jobs=-1), "bagging"),
            ("et_60_sqrt", ExtraTreesClassifier(n_estimators=60, max_features="sqrt", class_weight="balanced", random_state=seed, n_jobs=-1), "bagging"),
            ("et_90_d12", ExtraTreesClassifier(n_estimators=90, max_depth=12, max_features="sqrt", class_weight="balanced", random_state=seed, n_jobs=-1), "bagging"),
            ("et_90_leaf2", ExtraTreesClassifier(n_estimators=90, min_samples_leaf=2, max_features="sqrt", class_weight="balanced", random_state=seed, n_jobs=-1), "bagging"),
            ("et_120_d20_leaf2", ExtraTreesClassifier(n_estimators=120, max_depth=20, min_samples_leaf=2, max_features="sqrt", class_weight="balanced", random_state=seed, n_jobs=-1), "bagging"),
            ("histgb_lr0.05", HistGradientBoostingClassifier(max_iter=100, learning_rate=0.05, max_leaf_nodes=15, random_state=seed), "boosting"),
            ("histgb_lr0.1", HistGradientBoostingClassifier(max_iter=80, learning_rate=0.1, max_leaf_nodes=15, random_state=seed), "boosting"),
            ("gb_lr0.05_d2", GradientBoostingClassifier(n_estimators=80, learning_rate=0.05, max_depth=2, random_state=seed), "boosting"),
            ("gb_lr0.1_d3", GradientBoostingClassifier(n_estimators=80, learning_rate=0.1, max_depth=3, random_state=seed), "boosting"),
            ("lgbm_60_l15", LGBMClassifier(n_estimators=60, learning_rate=0.05, num_leaves=15, random_state=seed, n_jobs=-1, verbosity=-1), "boosting"),
            ("lgbm_90_l31", LGBMClassifier(n_estimators=90, learning_rate=0.05, num_leaves=31, random_state=seed, n_jobs=-1, verbosity=-1), "boosting"),
            ("lgbm_60_l63", LGBMClassifier(n_estimators=60, learning_rate=0.08, num_leaves=63, random_state=seed, n_jobs=-1, verbosity=-1), "boosting"),
            ("lgbm_100_leaf10", LGBMClassifier(n_estimators=100, learning_rate=0.05, num_leaves=31, min_child_samples=10, random_state=seed, n_jobs=-1, verbosity=-1), "boosting"),
            ("lgbm_100_leaf30", LGBMClassifier(n_estimators=100, learning_rate=0.05, num_leaves=31, min_child_samples=30, random_state=seed, n_jobs=-1, verbosity=-1), "boosting"),
            ("lgbm_80_ff0.7", LGBMClassifier(n_estimators=80, learning_rate=0.07, num_leaves=31, feature_fraction=0.7, random_state=seed, n_jobs=-1, verbosity=-1), "boosting"),
            ("lgbm_80_bag0.8", LGBMClassifier(n_estimators=80, learning_rate=0.07, num_leaves=31, subsample=0.8, subsample_freq=1, random_state=seed, n_jobs=-1, verbosity=-1), "boosting"),
            ("lgbm_120_l15", LGBMClassifier(n_estimators=120, learning_rate=0.04, num_leaves=15, random_state=seed, n_jobs=-1, verbosity=-1), "boosting"),
            ("xgb_60_d3", XGBClassifier(n_estimators=60, max_depth=3, learning_rate=0.08, subsample=0.9, colsample_bytree=0.8, eval_metric="logloss", random_state=seed, n_jobs=2), "boosting"),
            ("xgb_80_d5", XGBClassifier(n_estimators=80, max_depth=5, learning_rate=0.06, subsample=0.9, colsample_bytree=0.8, eval_metric="logloss", random_state=seed, n_jobs=2), "boosting"),
            ("xgb_100_d3", XGBClassifier(n_estimators=100, max_depth=3, learning_rate=0.05, subsample=0.8, colsample_bytree=1.0, eval_metric="logloss", random_state=seed, n_jobs=2), "boosting"),
            ("xgb_60_d6", XGBClassifier(n_estimators=60, max_depth=6, learning_rate=0.08, subsample=0.8, colsample_bytree=0.7, eval_metric="logloss", random_state=seed, n_jobs=2), "boosting"),
            ("cat_60_d4", CatBoostClassifier(iterations=60, depth=4, learning_rate=0.08, random_seed=seed, verbose=False, thread_count=2), "boosting"),
            ("cat_80_d6", CatBoostClassifier(iterations=80, depth=6, learning_rate=0.06, random_seed=seed, verbose=False, thread_count=2), "boosting"),
            ("cat_100_d4", CatBoostClassifier(iterations=100, depth=4, learning_rate=0.05, random_seed=seed, verbose=False, thread_count=2), "boosting"),
            ("cat_60_d8", CatBoostClassifier(iterations=60, depth=8, learning_rate=0.08, random_seed=seed, verbose=False, thread_count=2), "boosting"),
        ]
    else:
        models = [
            ("ridge_a0.1", Ridge(alpha=0.1), "linear"),
            ("ridge_a1", Ridge(alpha=1.0), "linear"),
            ("ridge_a10", Ridge(alpha=10.0), "linear"),
            ("elasticnet_a0.001", ElasticNet(alpha=0.001, l1_ratio=0.2, max_iter=5000, random_state=seed), "linear"),
            ("rf_60_sqrt", RandomForestRegressor(n_estimators=60, max_features="sqrt", random_state=seed, n_jobs=-1), "bagging"),
            ("rf_90_d12", RandomForestRegressor(n_estimators=90, max_depth=12, max_features="sqrt", random_state=seed, n_jobs=-1), "bagging"),
            ("rf_90_leaf2", RandomForestRegressor(n_estimators=90, min_samples_leaf=2, max_features="sqrt", random_state=seed, n_jobs=-1), "bagging"),
            ("rf_120_d20_leaf2", RandomForestRegressor(n_estimators=120, max_depth=20, min_samples_leaf=2, max_features="sqrt", random_state=seed, n_jobs=-1), "bagging"),
            ("et_60_sqrt", ExtraTreesRegressor(n_estimators=60, max_features="sqrt", random_state=seed, n_jobs=-1), "bagging"),
            ("et_90_d12", ExtraTreesRegressor(n_estimators=90, max_depth=12, max_features="sqrt", random_state=seed, n_jobs=-1), "bagging"),
            ("et_90_leaf2", ExtraTreesRegressor(n_estimators=90, min_samples_leaf=2, max_features="sqrt", random_state=seed, n_jobs=-1), "bagging"),
            ("et_120_d20_leaf2", ExtraTreesRegressor(n_estimators=120, max_depth=20, min_samples_leaf=2, max_features="sqrt", random_state=seed, n_jobs=-1), "bagging"),
            ("histgb_lr0.05", HistGradientBoostingRegressor(max_iter=100, learning_rate=0.05, max_leaf_nodes=15, random_state=seed), "boosting"),
            ("histgb_lr0.1", HistGradientBoostingRegressor(max_iter=80, learning_rate=0.1, max_leaf_nodes=15, random_state=seed), "boosting"),
            ("gb_lr0.05_d2", GradientBoostingRegressor(n_estimators=80, learning_rate=0.05, max_depth=2, random_state=seed), "boosting"),
            ("gb_lr0.1_d3", GradientBoostingRegressor(n_estimators=80, learning_rate=0.1, max_depth=3, random_state=seed), "boosting"),
            ("lgbm_60_l15", LGBMRegressor(n_estimators=60, learning_rate=0.05, num_leaves=15, random_state=seed, n_jobs=-1, verbosity=-1), "boosting"),
            ("lgbm_90_l31", LGBMRegressor(n_estimators=90, learning_rate=0.05, num_leaves=31, random_state=seed, n_jobs=-1, verbosity=-1), "boosting"),
            ("lgbm_60_l63", LGBMRegressor(n_estimators=60, learning_rate=0.08, num_leaves=63, random_state=seed, n_jobs=-1, verbosity=-1), "boosting"),
            ("lgbm_100_leaf10", LGBMRegressor(n_estimators=100, learning_rate=0.05, num_leaves=31, min_child_samples=10, random_state=seed, n_jobs=-1, verbosity=-1), "boosting"),
            ("lgbm_100_leaf30", LGBMRegressor(n_estimators=100, learning_rate=0.05, num_leaves=31, min_child_samples=30, random_state=seed, n_jobs=-1, verbosity=-1), "boosting"),
            ("lgbm_80_ff0.7", LGBMRegressor(n_estimators=80, learning_rate=0.07, num_leaves=31, feature_fraction=0.7, random_state=seed, n_jobs=-1, verbosity=-1), "boosting"),
            ("lgbm_80_bag0.8", LGBMRegressor(n_estimators=80, learning_rate=0.07, num_leaves=31, subsample=0.8, subsample_freq=1, random_state=seed, n_jobs=-1, verbosity=-1), "boosting"),
            ("lgbm_120_l15", LGBMRegressor(n_estimators=120, learning_rate=0.04, num_leaves=15, random_state=seed, n_jobs=-1, verbosity=-1), "boosting"),
            ("xgb_60_d3", XGBRegressor(n_estimators=60, max_depth=3, learning_rate=0.08, subsample=0.9, colsample_bytree=0.8, objective="reg:squarederror", random_state=seed, n_jobs=2), "boosting"),
            ("xgb_80_d5", XGBRegressor(n_estimators=80, max_depth=5, learning_rate=0.06, subsample=0.9, colsample_bytree=0.8, objective="reg:squarederror", random_state=seed, n_jobs=2), "boosting"),
            ("xgb_100_d3", XGBRegressor(n_estimators=100, max_depth=3, learning_rate=0.05, subsample=0.8, colsample_bytree=1.0, objective="reg:squarederror", random_state=seed, n_jobs=2), "boosting"),
            ("xgb_60_d6", XGBRegressor(n_estimators=60, max_depth=6, learning_rate=0.08, subsample=0.8, colsample_bytree=0.7, objective="reg:squarederror", random_state=seed, n_jobs=2), "boosting"),
            ("cat_60_d4", CatBoostRegressor(iterations=60, depth=4, learning_rate=0.08, random_seed=seed, verbose=False, thread_count=2), "boosting"),
            ("cat_80_d6", CatBoostRegressor(iterations=80, depth=6, learning_rate=0.06, random_seed=seed, verbose=False, thread_count=2), "boosting"),
            ("cat_100_d4", CatBoostRegressor(iterations=100, depth=4, learning_rate=0.05, random_seed=seed, verbose=False, thread_count=2), "boosting"),
            ("cat_60_d8", CatBoostRegressor(iterations=60, depth=8, learning_rate=0.08, random_seed=seed, verbose=False, thread_count=2), "boosting"),
        ]
    return [
        {"candidate_order": i + 1, "candidate": name, "family": family, "model": model}
        for i, (name, model, family) in enumerate(models)
    ]


def predict(model, x: np.ndarray, task_type: str) -> np.ndarray:
    if task_type == "classification":
        if hasattr(model, "predict_proba"):
            return np.asarray(model.predict_proba(x))[:, 1]
        raw = np.asarray(model.decision_function(x))
        return 1.0 / (1.0 + np.exp(-raw))
    return np.asarray(model.predict(x), dtype=float)


def utility(y: np.ndarray, pred: np.ndarray, task_type: str) -> float:
    if task_type == "classification":
        if len(np.unique(y)) < 2:
            return np.nan
        return float(roc_auc_score(y, pred))
    return -float(np.sqrt(mean_squared_error(y, pred)))


def performance(y: np.ndarray, pred: np.ndarray, task_type: str) -> dict[str, float]:
    if task_type == "classification":
        return {
            "roc_auc": float(roc_auc_score(y, pred)) if len(np.unique(y)) > 1 else np.nan,
            "pr_auc": float(average_precision_score(y, pred)) if len(np.unique(y)) > 1 else np.nan,
            "brier": float(brier_score_loss(y, pred)),
            "rmse": np.nan,
            "mae": np.nan,
            "r2": np.nan,
            "spearman": np.nan,
        }
    rho = spearmanr(y, pred).correlation
    return {
        "roc_auc": np.nan,
        "pr_auc": np.nan,
        "brier": np.nan,
        "rmse": float(np.sqrt(mean_squared_error(y, pred))),
        "mae": float(mean_absolute_error(y, pred)),
        "r2": float(r2_score(y, pred)),
        "spearman": float(rho) if np.isfinite(rho) else np.nan,
    }


def valid_splits(splits: list[tuple[np.ndarray, np.ndarray]], y: np.ndarray, task_type: str) -> bool:
    if task_type != "classification":
        return True
    return all(len(np.unique(y[tr])) == 2 and len(np.unique(y[te])) == 2 for tr, te in splits)


def make_splits(
    y: np.ndarray,
    groups: np.ndarray,
    task_type: str,
    n_splits: int,
    seed: int,
) -> tuple[list[tuple[np.ndarray, np.ndarray]], str]:
    x_dummy = np.zeros((len(y), 1))
    if task_type == "classification":
        grouped = list(StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed).split(x_dummy, y, groups))
        if valid_splits(grouped, y, task_type):
            return grouped, "stratified_scaffold_group"
        fallback = list(StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed).split(x_dummy, y))
        return fallback, "stratified_random_fallback"
    grouped = list(GroupKFold(n_splits=n_splits).split(x_dummy, y, groups))
    if valid_splits(grouped, y, task_type):
        return grouped, "scaffold_group"
    fallback = list(KFold(n_splits=n_splits, shuffle=True, random_state=seed).split(x_dummy))
    return fallback, "random_fallback"


def select_policy(stats: pd.DataFrame, pool_size: int, policy: str) -> str:
    pool = stats[stats["candidate_order"] <= pool_size].copy()
    if policy == "fixed_single":
        return str(pool.sort_values("candidate_order").iloc[0]["candidate"])
    if policy == "validation_best":
        return str(pool.sort_values(["inner_mean", "candidate_order"], ascending=[False, True]).iloc[0]["candidate"])
    if policy == "risk_adjusted":
        pool["score"] = pool["inner_mean"] - 0.5 * pool["inner_sd"].fillna(0.0)
        return str(pool.sort_values(["score", "candidate_order"], ascending=[False, True]).iloc[0]["candidate"])
    if policy == "one_se_stable":
        best = pool.sort_values(["inner_mean", "candidate_order"], ascending=[False, True]).iloc[0]
        threshold = float(best["inner_mean"]) - float(best["inner_sd"] if np.isfinite(best["inner_sd"]) else 0.0) / math.sqrt(3)
        eligible = pool[pool["inner_mean"] >= threshold].copy()
        return str(eligible.sort_values(["inner_sd", "fit_seconds_mean", "candidate_order"]).iloc[0]["candidate"])
    if policy == "test_oracle":
        return "__test_oracle__"
    raise ValueError(policy)


def run_task(task: str, args: argparse.Namespace, registry: dict) -> None:
    task_out = TASK_DIR / task
    done = task_out / "complete.json"
    if done.exists() and not args.force:
        print(f"SKIP {task}: already complete", flush=True)
        return
    task_out.mkdir(parents=True, exist_ok=True)
    frame, task_type = load_task(task, registry)
    x, groups, keep = featurize(frame["smiles"])
    y = frame.loc[keep, "y"].to_numpy()
    specs = candidate_specs(task_type, args.seed)[: args.max_candidates]
    outer_splits, outer_split_type = make_splits(y, groups, task_type, args.outer_folds, args.seed)

    registry_rows = [
        {
            "dataset": task,
            "task_type": task_type,
            "candidate_order": s["candidate_order"],
            "candidate": s["candidate"],
            "family": s["family"],
            "model_class": s["model"].__class__.__name__,
            "params": json.dumps(s["model"].get_params(deep=False), default=str, sort_keys=True),
        }
        for s in specs
    ]
    pd.DataFrame(registry_rows).to_csv(task_out / "candidate_registry.csv", index=False)

    inner_rows: list[dict[str, object]] = []
    outer_rows: list[dict[str, object]] = []
    policy_rows: list[dict[str, object]] = []
    for outer_fold, (outer_train, outer_test) in enumerate(outer_splits, start=1):
        inner_local, inner_split_type = make_splits(
            y[outer_train], groups[outer_train], task_type, args.inner_folds, args.seed + outer_fold
        )
        fold_inner: list[dict[str, object]] = []
        for spec in specs:
            fold_times: list[float] = []
            fold_scores: list[float] = []
            for inner_fold, (tr_local, va_local) in enumerate(inner_local, start=1):
                tr = outer_train[tr_local]
                va = outer_train[va_local]
                model = clone(spec["model"])
                start = time.perf_counter()
                model.fit(x[tr], y[tr])
                fit_seconds = time.perf_counter() - start
                pred = predict(model, x[va], task_type)
                score = utility(y[va], pred, task_type)
                fold_times.append(fit_seconds)
                fold_scores.append(score)
                inner_rows.append(
                    {
                        "dataset": task,
                        "task_type": task_type,
                        "outer_fold": outer_fold,
                        "inner_fold": inner_fold,
                        "outer_split_type": outer_split_type,
                        "inner_split_type": inner_split_type,
                        "candidate_order": spec["candidate_order"],
                        "candidate": spec["candidate"],
                        "family": spec["family"],
                        "inner_utility": score,
                        "fit_seconds": fit_seconds,
                    }
                )
            fold_inner.append(
                {
                    "candidate_order": spec["candidate_order"],
                    "candidate": spec["candidate"],
                    "family": spec["family"],
                    "inner_mean": float(np.nanmean(fold_scores)),
                    "inner_sd": float(np.nanstd(fold_scores, ddof=1)),
                    "fit_seconds_mean": float(np.mean(fold_times)),
                }
            )

        inner_stats = pd.DataFrame(fold_inner)
        fold_outer: list[dict[str, object]] = []
        for spec in specs:
            model = clone(spec["model"])
            start = time.perf_counter()
            model.fit(x[outer_train], y[outer_train])
            fit_seconds = time.perf_counter() - start
            pred = predict(model, x[outer_test], task_type)
            perf = performance(y[outer_test], pred, task_type)
            row = {
                "dataset": task,
                "task_type": task_type,
                "outer_fold": outer_fold,
                "outer_split_type": outer_split_type,
                "candidate_order": spec["candidate_order"],
                "candidate": spec["candidate"],
                "family": spec["family"],
                "n_train": len(outer_train),
                "n_test": len(outer_test),
                "outer_utility": utility(y[outer_test], pred, task_type),
                "fit_seconds": fit_seconds,
                **perf,
            }
            outer_rows.append(row)
            fold_outer.append(row)
        outer_df = pd.DataFrame(fold_outer)

        for pool_size in [k for k in POOL_SIZES if k <= args.max_candidates]:
            pool_inner = inner_stats[inner_stats["candidate_order"] <= pool_size].copy()
            pool_outer = outer_df[outer_df["candidate_order"] <= pool_size].copy()
            oracle_row = pool_outer.sort_values(["outer_utility", "candidate_order"], ascending=[False, True]).iloc[0]
            worst = float(pool_outer["outer_utility"].min())
            scale = max(float(oracle_row["outer_utility"]) - worst, 1e-12)
            valid_top3 = set(pool_inner.sort_values(["inner_mean", "candidate_order"], ascending=[False, True]).head(3)["candidate"])
            for policy in POLICIES:
                selected = select_policy(inner_stats, pool_size, policy)
                selected_row = oracle_row if selected == "__test_oracle__" else pool_outer[pool_outer["candidate"].eq(selected)].iloc[0]
                inner_row = pool_inner[pool_inner["candidate"].eq(selected)]
                policy_rows.append(
                    {
                        "dataset": task,
                        "task_type": task_type,
                        "outer_fold": outer_fold,
                        "outer_split_type": outer_split_type,
                        "pool_size": pool_size,
                        "policy": policy,
                        "selected_candidate": selected_row["candidate"],
                        "selected_family": selected_row["family"],
                        "inner_mean": float(inner_row["inner_mean"].iloc[0]) if not inner_row.empty else np.nan,
                        "inner_sd": float(inner_row["inner_sd"].iloc[0]) if not inner_row.empty else np.nan,
                        "outer_utility": float(selected_row["outer_utility"]),
                        "test_oracle_candidate": oracle_row["candidate"],
                        "test_oracle_utility": float(oracle_row["outer_utility"]),
                        "test_regret": float(oracle_row["outer_utility"] - selected_row["outer_utility"]),
                        "normalized_test_regret": float((oracle_row["outer_utility"] - selected_row["outer_utility"]) / scale),
                        "top3_hit": int(oracle_row["candidate"] in valid_top3),
                    }
                )
        print(f"{task}: outer fold {outer_fold}/{args.outer_folds} complete", flush=True)
        pd.DataFrame(inner_rows).to_csv(task_out / "inner_scores.partial.csv", index=False)
        pd.DataFrame(outer_rows).to_csv(task_out / "outer_candidate_scores.partial.csv", index=False)
        pd.DataFrame(policy_rows).to_csv(task_out / "policy_detail.partial.csv", index=False)

    pd.DataFrame(inner_rows).to_csv(task_out / "inner_scores.csv", index=False)
    pd.DataFrame(outer_rows).to_csv(task_out / "outer_candidate_scores.csv", index=False)
    pd.DataFrame(policy_rows).to_csv(task_out / "policy_detail.csv", index=False)
    done.write_text(
        json.dumps(
            {
                "dataset": task,
                "task_type": task_type,
                "n": len(y),
                "outer_split_type": outer_split_type,
                "outer_folds": args.outer_folds,
                "inner_folds": args.inner_folds,
                "candidate_count": len(specs),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"DONE {task}", flush=True)


def combine(args: argparse.Namespace) -> None:
    task_dirs = [TASK_DIR / task for task in args.tasks]
    if not all((p / "complete.json").exists() for p in task_dirs):
        missing = [p.name for p in task_dirs if not (p / "complete.json").exists()]
        raise RuntimeError(f"Incomplete tasks: {missing}")
    registry = pd.concat([pd.read_csv(p / "candidate_registry.csv") for p in task_dirs], ignore_index=True)
    inner = pd.concat([pd.read_csv(p / "inner_scores.csv") for p in task_dirs], ignore_index=True)
    outer = pd.concat([pd.read_csv(p / "outer_candidate_scores.csv") for p in task_dirs], ignore_index=True)
    detail = pd.concat([pd.read_csv(p / "policy_detail.csv") for p in task_dirs], ignore_index=True)
    registry.to_csv(OUT / "candidate_registry.csv", index=False)
    inner.to_csv(OUT / "inner_scores.csv", index=False)
    outer.to_csv(OUT / "outer_candidate_scores.csv", index=False)
    detail.to_csv(OUT / "policy_detail.csv", index=False)

    summary = (
        detail.groupby(["pool_size", "policy"], as_index=False)
        .agg(
            n_outer_units=("normalized_test_regret", "size"),
            n_endpoints=("dataset", "nunique"),
            normalized_regret_mean=("normalized_test_regret", "mean"),
            normalized_regret_median=("normalized_test_regret", "median"),
            normalized_regret_sd=("normalized_test_regret", "std"),
            top3_hit_rate=("top3_hit", "mean"),
        )
    )
    summary["regret_sem"] = summary["normalized_regret_sd"] / np.sqrt(summary["n_outer_units"])
    summary["regret_ci95_low"] = summary["normalized_regret_mean"] - 1.96 * summary["regret_sem"]
    summary["regret_ci95_high"] = summary["normalized_regret_mean"] + 1.96 * summary["regret_sem"]
    summary.to_csv(OUT / "policy_summary.csv", index=False)

    stability = (
        detail[detail["policy"].ne("test_oracle")]
        .groupby(["dataset", "pool_size", "policy"], as_index=False)
        .agg(
            n_outer=("outer_fold", "nunique"),
            n_selected_models=("selected_candidate", "nunique"),
            modal_selection_rate=("selected_candidate", lambda s: float(s.value_counts(normalize=True).iloc[0])),
        )
    )
    stability.to_csv(OUT / "selection_stability.csv", index=False)

    manifest = {
        "tasks": args.tasks,
        "pool_sizes": [k for k in POOL_SIZES if k <= args.max_candidates],
        "outer_folds": args.outer_folds,
        "inner_folds": args.inner_folds,
        "candidate_count": args.max_candidates,
        "seed": args.seed,
        "python": platform.python_version(),
        "sklearn": sklearn.__version__,
        "rdkit": rdBase.rdkitVersion,
        "scope": "32 pre-registered lightweight candidates; not a retraining of every historical deep model",
    }
    (OUT / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(summary.to_string(index=False), flush=True)


def main() -> None:
    args = parse_args()
    invalid = sorted(set(args.tasks) - set(TASKS))
    if invalid:
        raise ValueError(f"Unknown tasks: {invalid}")
    OUT.mkdir(parents=True, exist_ok=True)
    TASK_DIR.mkdir(parents=True, exist_ok=True)
    registry = json.loads((DATA / "dataset_registry.json").read_text(encoding="utf-8"))
    for task in args.tasks:
        run_task(task, args, registry)
    combine(args)


if __name__ == "__main__":
    main()
