# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import resource
import shutil
import tempfile
import time
from pathlib import Path

import autogluon
import numpy as np
import pandas as pd
from autogluon.tabular import TabularPredictor
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold, KFold, StratifiedGroupKFold, StratifiedKFold
from scipy.stats import spearmanr


ROOT = Path("/mnt/d/fzyc")
FEATURE_DIR = ROOT / "reports" / "draft10_core_experiments_20260621" / "autogluon_features"
OUT = Path(os.environ.get("FZYC_AUTOGLUON_OUT", ROOT / "reports" / "draft10_core_experiments_20260621" / "autogluon_nested"))
TASK_DIR = OUT / "tasks"
TASKS = [
    "bbbp", "bace", "clintox", "esol", "freesolv", "lipo",
    "tdc_caco2_wang", "tdc_hia_hou", "tdc_pgp_broccatelli",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", nargs="*", default=TASKS)
    parser.add_argument("--outer-folds", type=int, default=3)
    parser.add_argument("--inner-folds", type=int, default=3)
    parser.add_argument("--time-limit", type=int, default=60)
    parser.add_argument("--seed", type=int, default=20260621)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


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


def make_frame(x: np.ndarray, y: np.ndarray | None = None) -> pd.DataFrame:
    frame = pd.DataFrame(x, columns=[f"fp_{i:03d}" for i in range(x.shape[1])])
    if y is not None:
        frame["target"] = y
    return frame


def evaluate(y: np.ndarray, pred: np.ndarray, task_type: str) -> dict[str, float]:
    if task_type == "classification":
        return {
            "outer_utility": float(roc_auc_score(y, pred)),
            "roc_auc": float(roc_auc_score(y, pred)),
            "pr_auc": float(average_precision_score(y, pred)),
            "brier": float(brier_score_loss(y, pred)),
            "rmse": np.nan,
            "mae": np.nan,
            "r2": np.nan,
            "spearman": np.nan,
        }
    rmse = float(np.sqrt(mean_squared_error(y, pred)))
    rho = spearmanr(y, pred).correlation
    return {
        "outer_utility": -rmse,
        "roc_auc": np.nan,
        "pr_auc": np.nan,
        "brier": np.nan,
        "rmse": rmse,
        "mae": float(mean_absolute_error(y, pred)),
        "r2": float(r2_score(y, pred)),
        "spearman": float(rho) if np.isfinite(rho) else np.nan,
    }


def run_task(task: str, task_type: str, args: argparse.Namespace) -> None:
    task_out = TASK_DIR / task
    done = task_out / "complete.json"
    if done.exists() and not args.force:
        print(f"SKIP {task}", flush=True)
        return
    task_out.mkdir(parents=True, exist_ok=True)
    data = np.load(FEATURE_DIR / f"{task}.npz")
    x = data["X"].astype(np.float32)
    y = data["y"]
    groups = data["groups"]
    smiles = data["smiles"]
    outer_splits, outer_type = make_splits(y, groups, task_type, args.outer_folds, args.seed)
    rows: list[dict[str, object]] = []
    pred_rows: list[dict[str, object]] = []

    for outer_fold, (outer_train, outer_test) in enumerate(outer_splits, start=1):
        inner_splits, inner_type = make_splits(
            y[outer_train], groups[outer_train], task_type, args.inner_folds, args.seed + outer_fold
        )
        inner_train_local, inner_valid_local = inner_splits[0]
        inner_train = outer_train[inner_train_local]
        inner_valid = outer_train[inner_valid_local]
        train_df = make_frame(x[inner_train], y[inner_train])
        tune_df = make_frame(x[inner_valid], y[inner_valid])
        test_df = make_frame(x[outer_test])
        model_dir = Path(tempfile.mkdtemp(prefix=f"fzyc_ag_{task}_{outer_fold}_"))
        problem_type = "binary" if task_type == "classification" else "regression"
        eval_metric = "roc_auc" if task_type == "classification" else "root_mean_squared_error"
        predictor = TabularPredictor(
            label="target",
            problem_type=problem_type,
            eval_metric=eval_metric,
            path=str(model_dir),
            verbosity=1,
        )
        start = time.perf_counter()
        predictor.fit(
            train_data=train_df,
            tuning_data=tune_df,
            time_limit=args.time_limit,
            hyperparameters={"GBM": {}, "CAT": {}, "RF": {}, "XT": {}},
            fit_strategy="sequential",
        )
        fit_seconds = time.perf_counter() - start
        leaderboard = predictor.leaderboard(tune_df, silent=True)
        leaderboard.insert(0, "dataset", task)
        leaderboard.insert(1, "outer_fold", outer_fold)
        leaderboard.to_csv(task_out / f"leaderboard_fold{outer_fold}.csv", index=False)
        best_model = predictor.model_best
        prediction_model = best_model
        refit_status = "not_attempted"
        try:
            refit_map = predictor.refit_full(model="best")
            prediction_model = refit_map.get(best_model, best_model)
            refit_status = "refit_full"
        except Exception as exc:
            refit_status = f"refit_failed:{type(exc).__name__}"
        if task_type == "classification":
            pred = predictor.predict_proba(test_df, model=prediction_model, as_multiclass=False).to_numpy(dtype=float)
        else:
            pred = predictor.predict(test_df, model=prediction_model).to_numpy(dtype=float)
        metrics = evaluate(y[outer_test], pred, task_type)
        peak_self_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
        peak_children_mb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024.0
        rows.append(
            {
                "dataset": task,
                "task_type": task_type,
                "outer_fold": outer_fold,
                "outer_split_type": outer_type,
                "inner_split_type": inner_type,
                "inner_tuning_fold": 1,
                "n_inner_train": len(inner_train),
                "n_inner_valid": len(inner_valid),
                "n_outer_test": len(outer_test),
                "best_model": best_model,
                "prediction_model": prediction_model,
                "refit_status": refit_status,
                "validation_score": float(leaderboard.iloc[0]["score_test"]),
                "fit_seconds": fit_seconds,
                "model_count": int(len(leaderboard)),
                "peak_rss_mb": float(max(peak_self_mb, peak_children_mb)),
                **metrics,
            }
        )
        for idx, yi, pi, smi in zip(outer_test, y[outer_test], pred, smiles[outer_test]):
            pred_rows.append(
                {
                    "dataset": task,
                    "outer_fold": outer_fold,
                    "row_index": int(idx),
                    "smiles": str(smi),
                    "y_true": float(yi),
                    "prediction": float(pi),
                }
            )
        pd.DataFrame(rows).to_csv(task_out / "outer_results.partial.csv", index=False)
        pd.DataFrame(pred_rows).to_csv(task_out / "outer_predictions.partial.csv", index=False)
        shutil.rmtree(model_dir, ignore_errors=True)
        print(f"{task}: outer fold {outer_fold}/{args.outer_folds} complete", flush=True)

    pd.DataFrame(rows).to_csv(task_out / "outer_results.csv", index=False)
    pd.DataFrame(pred_rows).to_csv(task_out / "outer_predictions.csv", index=False)
    done.write_text(
        json.dumps(
            {
                "dataset": task,
                "task_type": task_type,
                "n": len(y),
                "outer_split_type": outer_type,
                "outer_folds": args.outer_folds,
                "inner_folds": args.inner_folds,
                "time_limit_per_outer_fold": args.time_limit,
                "scope": (
                    "AutoGluon-Tabular CPU tree baseline on Morgan-512; first scaffold-aware inner fold "
                    "used as tuning_data"
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def combine(args: argparse.Namespace, manifest: dict) -> None:
    task_dirs = [TASK_DIR / task for task in args.tasks]
    missing = [p.name for p in task_dirs if not (p / "complete.json").exists()]
    if missing:
        raise RuntimeError(f"Incomplete tasks: {missing}")
    detail = pd.concat([pd.read_csv(p / "outer_results.csv") for p in task_dirs], ignore_index=True)
    predictions = pd.concat([pd.read_csv(p / "outer_predictions.csv") for p in task_dirs], ignore_index=True)
    detail.to_csv(OUT / "outer_results.csv", index=False)
    predictions.to_csv(OUT / "outer_predictions.csv", index=False)
    rows: list[dict[str, object]] = []
    for (dataset, task_type), dfg in detail.groupby(["dataset", "task_type"], sort=False):
        row = {
            "dataset": dataset,
            "task_type": task_type,
            "n_outer": len(dfg),
            "outer_split_type": ";".join(sorted(dfg["outer_split_type"].unique())),
            "selected_models": ";".join(f"{m}:{n}" for m, n in Counter(dfg["best_model"]).items()),
            "fit_seconds_mean": dfg["fit_seconds"].mean(),
        }
        if task_type == "classification":
            row.update(
                {
                    "primary_mean": dfg["roc_auc"].mean(),
                    "primary_sd": dfg["roc_auc"].std(ddof=1),
                    "secondary_mean": dfg["pr_auc"].mean(),
                    "brier_mean": dfg["brier"].mean(),
                }
            )
        else:
            row.update(
                {
                    "primary_mean": dfg["rmse"].mean(),
                    "primary_sd": dfg["rmse"].std(ddof=1),
                    "secondary_mean": dfg["mae"].mean(),
                    "spearman_mean": dfg["spearman"].mean(),
                }
            )
        rows.append(row)
    pd.DataFrame(rows).to_csv(OUT / "summary.csv", index=False)
    run_manifest = {
        "tasks": args.tasks,
        "outer_folds": args.outer_folds,
        "inner_folds": args.inner_folds,
        "time_limit_per_outer_fold": args.time_limit,
        "seed": args.seed,
        "python": platform.python_version(),
        "autogluon_tabular": importlib.metadata.version("autogluon.tabular"),
        "feature_manifest": manifest,
        "scope": (
            "AutoGluon-Tabular CPU tree baseline (LightGBM, CatBoost, random forest, ExtraTrees) "
            "on Morgan-512; not a replacement for the FZYC-Mol governance policy"
        ),
        "memory_measurement": "Linux ru_maxrss maximum of main process and completed child processes; cumulative within run",
    }
    (OUT / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")
    print(pd.DataFrame(rows).to_string(index=False), flush=True)


def main() -> None:
    args = parse_args()
    invalid = sorted(set(args.tasks) - set(TASKS))
    if invalid:
        raise ValueError(invalid)
    OUT.mkdir(parents=True, exist_ok=True)
    TASK_DIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((FEATURE_DIR / "manifest.json").read_text(encoding="utf-8"))
    for task in args.tasks:
        run_task(task, manifest["tasks"][task]["task_type"], args)
    combine(args, manifest)


if __name__ == "__main__":
    from collections import Counter

    main()
