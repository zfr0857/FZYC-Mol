from __future__ import annotations

import argparse
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


TDC_ADMET_TASKS = {
    "tdc_caco2_wang": ("Caco2_Wang", "regression"),
    "tdc_hia_hou": ("HIA_Hou", "classification"),
    "tdc_pgp_broccatelli": ("Pgp_Broccatelli", "classification"),
    "tdc_bioavailability_ma": ("Bioavailability_Ma", "classification"),
    "tdc_bbb_martins": ("BBB_Martins", "classification"),
    "tdc_cyp2c9_veith": ("CYP2C9_Veith", "classification"),
    "tdc_cyp2d6_veith": ("CYP2D6_Veith", "classification"),
    "tdc_cyp3a4_veith": ("CYP3A4_Veith", "classification"),
}


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


def build_estimator(model: str, task_type: str, seed: int, y_train: np.ndarray):
    if model == "lgbm_morgan":
        if task_type == "regression":
            est = LGBMRegressor(
                n_estimators=360,
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
            est = LGBMClassifier(
                n_estimators=360,
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
        return Pipeline([("imputer", SimpleImputer(strategy="median")), ("model", est)])
    if model == "rf_morgan":
        if task_type == "regression":
            est = RandomForestRegressor(
                n_estimators=240,
                max_features="sqrt",
                random_state=seed,
                n_jobs=-1,
            )
        else:
            est = RandomForestClassifier(
                n_estimators=240,
                max_features="sqrt",
                class_weight="balanced_subsample",
                random_state=seed,
                n_jobs=-1,
            )
        return Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler(with_mean=False)),
                ("model", est),
            ]
        )
    raise ValueError(f"Unknown model: {model}")


def predict(estimator, x: np.ndarray, task_type: str) -> np.ndarray:
    if task_type == "classification" and hasattr(estimator[-1], "predict_proba"):
        return estimator.predict_proba(x)[:, 1]
    return estimator.predict(x)


def run_one(dataset_key: str, split_method: str, seed: int, model: str, output_dir: Path, cache_dir: Path) -> dict:
    from tdc.single_pred import ADME

    tdc_name, task_type = TDC_ADMET_TASKS[dataset_key]
    data = ADME(name=tdc_name, path=str(cache_dir))
    split = data.get_split(method=split_method, seed=seed)
    train = normalize(split["train"], task_type)
    valid = normalize(split["valid"], task_type)
    test = normalize(split["test"], task_type)
    train_valid = pd.concat([train, valid], ignore_index=True).drop_duplicates("smiles").reset_index(drop=True)
    x_train = feature_matrix(train_valid)
    y_train = train_valid["y"].to_numpy()
    x_test = feature_matrix(test)
    y_test = test["y"].to_numpy()
    estimator = build_estimator(model, task_type, seed, y_train)
    start = time.perf_counter()
    estimator.fit(x_train, y_train)
    fit_seconds = time.perf_counter() - start
    start = time.perf_counter()
    pred = predict(estimator, x_test, task_type)
    predict_seconds = time.perf_counter() - start
    metrics = compute_metrics(task_type, y_test, pred)
    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"smiles": test["smiles"], "y_true": y_test, "y_pred": pred}).to_csv(
        output_dir / f"{dataset_key}_{model}_{split_method}_seed{seed}_predictions.csv",
        index=False,
    )
    return {
        "dataset": dataset_key,
        "tdc_name": tdc_name,
        "model": model,
        "split_method": split_method,
        "seed": seed,
        "task_type": task_type,
        "n_train_valid": len(train_valid),
        "n_test": len(test),
        "fit_seconds": fit_seconds,
        "predict_seconds": predict_seconds,
        **metrics,
    }


def summarize(rows: list[dict], output_dir: Path) -> None:
    raw = pd.DataFrame(rows)
    raw.to_csv(output_dir / "metrics_raw.csv", index=False)
    id_cols = {"dataset", "tdc_name", "model", "split_method", "seed", "task_type"}
    metric_cols = [c for c in raw.columns if c not in id_cols and pd.api.types.is_numeric_dtype(raw[c])]
    summary = (
        raw.groupby(["dataset", "tdc_name", "model", "split_method", "task_type"], dropna=False)[metric_cols]
        .agg(["mean", "std"])
        .reset_index()
    )
    summary.to_csv(output_dir / "metrics_summary.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run TDC ADMET official random/scaffold splits.")
    parser.add_argument("--datasets", nargs="*", default=list(TDC_ADMET_TASKS))
    parser.add_argument("--split-methods", nargs="*", default=["random", "scaffold"])
    parser.add_argument("--models", nargs="*", default=["lgbm_morgan", "rf_morgan"])
    parser.add_argument("--seeds", nargs="*", type=int, default=[13, 17, 23])
    parser.add_argument("--tdc-cache-dir", default=str(ROOT / "data" / "tdc"))
    parser.add_argument("--output-dir", default=str(ROOT / "reports" / "tdc_official_admet_splits"))
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--no-resume", action="store_false", dest="resume")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "metrics_raw.csv"
    if args.resume and metrics_path.exists():
        rows = pd.read_csv(metrics_path).to_dict("records")
        done = {
            (r["dataset"], r["model"], r["split_method"], int(r["seed"]))
            for r in rows
        }
    else:
        rows = []
        done = set()
    for dataset in args.datasets:
        for split_method in args.split_methods:
            for seed in args.seeds:
                for model in args.models:
                    key = (dataset, model, split_method, seed)
                    if key in done:
                        print(f"skip dataset={dataset} split={split_method} model={model} seed={seed}", flush=True)
                        continue
                    print(f"start dataset={dataset} split={split_method} model={model} seed={seed}", flush=True)
                    row = run_one(dataset, split_method, seed, model, output_dir, Path(args.tdc_cache_dir))
                    rows.append(row)
                    done.add(key)
                    summarize(rows, output_dir)
                    primary = "rmse" if row["task_type"] == "regression" else "roc_auc"
                    print(f"done dataset={dataset} split={split_method} model={model} seed={seed} {primary}={row.get(primary, np.nan):.6g}", flush=True)
    summarize(rows, output_dir)
    print(pd.DataFrame(rows).tail(30).to_string(index=False))


if __name__ == "__main__":
    main()
