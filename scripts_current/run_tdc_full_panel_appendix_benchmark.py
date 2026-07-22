from __future__ import annotations

import argparse
import traceback
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import canonicalize_smiles
from fzyc_mol.evaluate import compute_metrics
from fzyc_mol.features import descriptor_vector, morgan_fingerprint


OUT_DIR = ROOT / "reports" / "tdc_full_panel_appendix_benchmark"
TABLE_DIR = ROOT / "reports" / "manuscript_tables"
TABLE_PATH = TABLE_DIR / "table14_tdc_full_panel_fast_appendix_benchmark.csv"


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


def feature_matrix(frame: pd.DataFrame) -> np.ndarray:
    rows = []
    for smiles in frame["smiles"]:
        rows.append(np.hstack([morgan_fingerprint(smiles), descriptor_vector(smiles, include_3d=False)]))
    return np.vstack(rows).astype(np.float32)


def build_estimator(model: str, task_type: str, seed: int):
    if model == "lgbm_morgan":
        if task_type == "regression":
            estimator = LGBMRegressor(
                n_estimators=320,
                learning_rate=0.035,
                num_leaves=31,
                subsample=0.9,
                colsample_bytree=0.8,
                reg_lambda=2.0,
                random_state=seed,
                n_jobs=-1,
                verbose=-1,
            )
        else:
            estimator = LGBMClassifier(
                n_estimators=320,
                learning_rate=0.035,
                num_leaves=31,
                subsample=0.9,
                colsample_bytree=0.8,
                reg_lambda=2.0,
                class_weight="balanced",
                random_state=seed,
                n_jobs=-1,
                verbose=-1,
            )
        return Pipeline([("imputer", SimpleImputer(strategy="median")), ("model", estimator)])
    if model == "rf_morgan":
        if task_type == "regression":
            estimator = RandomForestRegressor(
                n_estimators=220,
                max_features="sqrt",
                random_state=seed,
                n_jobs=-1,
            )
        else:
            estimator = RandomForestClassifier(
                n_estimators=220,
                max_features="sqrt",
                class_weight="balanced_subsample",
                random_state=seed,
                n_jobs=-1,
            )
        return Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler(with_mean=False)),
                ("model", estimator),
            ]
        )
    raise ValueError(f"Unknown model: {model}")


def predict(estimator, x: np.ndarray, task_type: str) -> np.ndarray:
    if task_type == "classification" and hasattr(estimator[-1], "predict_proba"):
        return estimator.predict_proba(x)[:, 1]
    return estimator.predict(x)


def primary_value(row: dict[str, object]) -> tuple[float, str]:
    metric = str(row["official_metric"])
    if metric == "mae":
        return float(row.get("mae", np.nan)), "lower"
    if metric == "roc-auc":
        return float(row.get("roc_auc", np.nan)), "higher"
    if metric == "pr-auc":
        return float(row.get("pr_auc", np.nan)), "higher"
    if metric == "spearman":
        return float(row.get("spearman", np.nan)), "higher"
    raise ValueError(f"Unsupported official metric: {metric}")


def load_split(family: str, name: str, cache_dir: Path, split_method: str, seed: int):
    from tdc.single_pred import ADME, Tox

    loader = ADME if family == "ADME" else Tox
    data = loader(name=name, path=str(cache_dir))
    return data.get_split(method=split_method, seed=seed)


def run_one(
    task: pd.Series,
    model: str,
    split_method: str,
    seed: int,
    cache_dir: Path,
    output_dir: Path,
) -> dict[str, object]:
    split = load_split(str(task.family), str(task.tdc_name), cache_dir, split_method, seed)
    train = normalize(split["train"], str(task.task_type))
    valid = normalize(split["valid"], str(task.task_type))
    test = normalize(split["test"], str(task.task_type))
    train_valid = pd.concat([train, valid], ignore_index=True).drop_duplicates("smiles").reset_index(drop=True)
    x_train = feature_matrix(train_valid)
    y_train = train_valid["y"].to_numpy()
    x_test = feature_matrix(test)
    y_test = test["y"].to_numpy()
    estimator = build_estimator(model, str(task.task_type), seed)
    start = time.perf_counter()
    estimator.fit(x_train, y_train)
    fit_seconds = time.perf_counter() - start
    start = time.perf_counter()
    pred = predict(estimator, x_test, str(task.task_type))
    predict_seconds = time.perf_counter() - start
    metrics = compute_metrics(str(task.task_type), y_test, pred)
    row = {
        "dataset": str(task.dataset),
        "family": str(task.family),
        "tdc_name": str(task.tdc_name),
        "official_metric": str(task.official_metric),
        "model": model,
        "split_method": split_method,
        "seed": seed,
        "task_type": str(task.task_type),
        "n_train_valid": len(train_valid),
        "n_test": len(test),
        "fit_seconds": fit_seconds,
        "predict_seconds": predict_seconds,
        **metrics,
    }
    value, direction = primary_value(row)
    row["primary_value"] = value
    row["primary_direction"] = direction
    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"smiles": test["smiles"], "y_true": y_test, "y_pred": pred}).to_csv(
        output_dir / f"{task.dataset}_{model}_{split_method}_seed{seed}_predictions.csv",
        index=False,
    )
    return row


def summarize(rows: list[dict[str, object]], output_dir: Path) -> None:
    output_dir = output_dir.resolve()
    if not rows:
        return
    raw = pd.DataFrame(rows)
    for column in ["mae", "rmse", "roc_auc", "pr_auc", "spearman", "fit_seconds"]:
        if column not in raw.columns:
            raw[column] = np.nan
    raw.to_csv(output_dir / "metrics_raw.csv", index=False)
    id_cols = {
        "dataset",
        "family",
        "tdc_name",
        "official_metric",
        "model",
        "split_method",
        "seed",
        "task_type",
        "primary_direction",
    }
    metric_cols = [column for column in raw.columns if column not in id_cols and pd.api.types.is_numeric_dtype(raw[column])]
    summary = (
        raw.groupby(
            ["dataset", "family", "official_metric", "model", "split_method", "task_type", "primary_direction"],
            dropna=False,
        )[metric_cols]
        .agg(["mean", "std"])
        .reset_index()
    )
    summary.to_csv(output_dir / "metrics_summary.csv", index=False)
    best_rows = []
    for (dataset, split_method), group in raw.groupby(["dataset", "split_method"], dropna=False):
        direction = str(group["primary_direction"].iloc[0])
        model_summary = (
            group.groupby(["family", "official_metric", "task_type", "model"], dropna=False)
            .agg(
                n_seeds=("seed", "nunique"),
                n_test=("n_test", "median"),
                primary_mean=("primary_value", "mean"),
                primary_std=("primary_value", "std"),
                mae_mean=("mae", "mean"),
                rmse_mean=("rmse", "mean"),
                roc_auc_mean=("roc_auc", "mean"),
                pr_auc_mean=("pr_auc", "mean"),
                spearman_mean=("spearman", "mean"),
                fit_seconds_mean=("fit_seconds", "mean"),
            )
            .reset_index()
        )
        ascending = direction == "lower"
        model_summary = model_summary.sort_values("primary_mean", ascending=ascending)
        best = model_summary.iloc[0].to_dict()
        best["dataset"] = dataset
        best["split_method"] = split_method
        best["primary_direction"] = direction
        best_rows.append(best)
    appendix = pd.DataFrame(best_rows).sort_values(["family", "dataset"])
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    appendix.to_csv(TABLE_PATH, index=False)
    lines = [
        "# TDC Full-Panel Fast Appendix Benchmark",
        "",
        "This appendix benchmark expands the external comparison to the full PyTDC ADMET benchmark group: 18 ADME tasks and 4 toxicity tasks.",
        "The protocol uses official scaffold splits, fast Morgan+descriptor RF/LGBM baselines, and TDC's endpoint-specific primary metric.",
        "",
        f"- Raw metrics: `{(output_dir / 'metrics_raw.csv').relative_to(ROOT)}`",
        f"- Summary: `{(output_dir / 'metrics_summary.csv').relative_to(ROOT)}`",
        f"- Manuscript table: `{TABLE_PATH.relative_to(ROOT)}`",
        "",
        appendix.to_markdown(index=False),
        "",
        "Manuscript placement: supplementary external benchmark / appendix. Do not merge directly into the main MoleculeNet/TDC eight-task table.",
        "",
    ]
    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a fast full-panel PyTDC ADMET/Tox appendix benchmark.")
    parser.add_argument("--datasets", nargs="*", default=None, help="TDC metadata names; default uses all ADMET benchmark tasks.")
    parser.add_argument("--models", nargs="*", default=["lgbm_morgan", "rf_morgan"])
    parser.add_argument("--split-methods", nargs="*", default=["scaffold"])
    parser.add_argument("--seeds", nargs="*", type=int, default=[13, 17, 23])
    parser.add_argument("--tdc-cache-dir", default=str(ROOT / "data" / "tdc"))
    parser.add_argument("--output-dir", default=str(OUT_DIR))
    parser.add_argument(
        "--skip-download-errors",
        action="store_true",
        help="Record dataset load/download failures and continue with remaining tasks.",
    )
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--no-resume", action="store_false", dest="resume")
    args = parser.parse_args()

    tasks = load_task_metadata()
    if args.datasets:
        unknown = sorted(set(args.datasets) - set(tasks["dataset"]))
        if unknown:
            raise SystemExit(f"Unknown TDC task(s): {unknown}")
        tasks = tasks[tasks["dataset"].isin(args.datasets)].reset_index(drop=True)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "metrics_raw.csv"
    if args.resume and metrics_path.exists():
        rows = pd.read_csv(metrics_path).to_dict("records")
        done = {
            (str(row["dataset"]), str(row["model"]), str(row["split_method"]), int(row["seed"]))
            for row in rows
        }
    else:
        rows = []
        done = set()

    errors: list[dict[str, object]] = []
    failed_datasets: set[str] = set()
    error_path = output_dir / "download_errors.csv"
    error_columns = [
        "dataset",
        "family",
        "tdc_name",
        "official_metric",
        "model",
        "split_method",
        "seed",
        "error_type",
        "error",
        "traceback_tail",
    ]

    for task in tasks.itertuples(index=False):
        for split_method in args.split_methods:
            for seed in args.seeds:
                for model in args.models:
                    key = (str(task.dataset), model, split_method, int(seed))
                    if key in done:
                        print(f"skip dataset={task.dataset} split={split_method} model={model} seed={seed}", flush=True)
                        continue
                    if str(task.dataset) in failed_datasets:
                        print(
                            f"skip_failed_dataset dataset={task.dataset} split={split_method} model={model} seed={seed}",
                            flush=True,
                        )
                        continue
                    print(f"start dataset={task.dataset} split={split_method} model={model} seed={seed}", flush=True)
                    try:
                        row = run_one(
                            pd.Series(task._asdict()),
                            model,
                            split_method,
                            seed,
                            Path(args.tdc_cache_dir),
                            output_dir,
                        )
                    except Exception as exc:
                        if not args.skip_download_errors:
                            raise
                        failed_datasets.add(str(task.dataset))
                        err_row = {
                            "dataset": str(task.dataset),
                            "family": str(task.family),
                            "tdc_name": str(task.tdc_name),
                            "official_metric": str(task.official_metric),
                            "model": model,
                            "split_method": split_method,
                            "seed": seed,
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                            "traceback_tail": "".join(traceback.format_exception_only(type(exc), exc)).strip(),
                        }
                        errors.append(err_row)
                        pd.DataFrame(errors).to_csv(error_path, index=False)
                        print(
                            f"download_or_load_error dataset={task.dataset} split={split_method} "
                            f"model={model} seed={seed} error={type(exc).__name__}: {exc}",
                            flush=True,
                        )
                        continue
                    rows.append(row)
                    done.add(key)
                    summarize(rows, output_dir)
                    print(
                        f"done dataset={task.dataset} split={split_method} model={model} seed={seed} "
                        f"{row['official_metric']}={row['primary_value']:.6g}",
                        flush=True,
                    )
    summarize(rows, output_dir)
    if errors:
        pd.DataFrame(errors).to_csv(error_path, index=False)
        print(f"recorded_errors={len(errors)} path={error_path}", flush=True)
    elif args.skip_download_errors:
        pd.DataFrame(columns=error_columns).to_csv(error_path, index=False)
    if rows:
        print(pd.DataFrame(rows).tail(30).to_string(index=False))


if __name__ == "__main__":
    main()
