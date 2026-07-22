from __future__ import annotations

import argparse
import hashlib
import sys
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRegressor
from rdkit import Chem, RDLogger
from rdkit.Chem import BRICS, Descriptors, Fragments
from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.compose import TransformedTargetRegressor
from sklearn.impute import SimpleImputer
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler, StandardScaler
from xgboost import XGBClassifier, XGBRegressor

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import DATASETS, load_dataset
from fzyc_mol.evaluate import compute_metrics
from fzyc_mol.features import mol_from_smiles, morgan_fingerprint, scaffold_from_smiles
from fzyc_mol.splits import make_split


RDLogger.DisableLog("rdApp.*")

SEEDS = [13, 17, 23, 29, 31]
RDKitDescriptor = tuple[str, object]
DESCRIPTOR_FUNCS: list[RDKitDescriptor] = list(Descriptors._descList)
FRAGMENT_FUNCS: list[RDKitDescriptor] = [
    (name, getattr(Fragments, name))
    for name in dir(Fragments)
    if name.startswith("fr_") and callable(getattr(Fragments, name))
]


def _safe_float(value: object) -> float:
    try:
        out = float(value)
    except Exception:
        return 0.0
    if not np.isfinite(out):
        return 0.0
    return float(np.clip(out, -1.0e12, 1.0e12))


@lru_cache(maxsize=200_000)
def rdkit_descriptor_vector(smiles: str) -> np.ndarray:
    mol = mol_from_smiles(smiles)
    if mol is None:
        return np.zeros(len(DESCRIPTOR_FUNCS), dtype=np.float32)
    values = []
    for _, fn in DESCRIPTOR_FUNCS:
        try:
            values.append(_safe_float(fn(mol)))
        except Exception:
            values.append(0.0)
    return np.asarray(values, dtype=np.float32)


def _hash_token(token: str, n_bits: int) -> int:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, byteorder="little", signed=False) % n_bits


def _hashed_counts(tokens: Iterable[str], n_bits: int) -> np.ndarray:
    out = np.zeros(n_bits, dtype=np.float32)
    for token in tokens:
        out[_hash_token(token, n_bits)] += 1.0
    return out


@lru_cache(maxsize=200_000)
def motif_vector(smiles: str, n_brics: int = 512, n_scaffold: int = 512) -> np.ndarray:
    mol = mol_from_smiles(smiles)
    if mol is None:
        return np.zeros(n_brics + n_scaffold + len(FRAGMENT_FUNCS), dtype=np.float32)
    try:
        brics_tokens = sorted(BRICS.BRICSDecompose(mol))
    except Exception:
        brics_tokens = []
    brics = _hashed_counts(brics_tokens, n_brics)
    scaffold = scaffold_from_smiles(smiles)
    scaffold_fp = morgan_fingerprint(scaffold, n_bits=n_scaffold, radius=2) if scaffold else np.zeros(n_scaffold, dtype=np.float32)
    fragments = []
    for _, fn in FRAGMENT_FUNCS:
        try:
            fragments.append(_safe_float(fn(mol)))
        except Exception:
            fragments.append(0.0)
    return np.hstack([brics, scaffold_fp, np.asarray(fragments, dtype=np.float32)]).astype(np.float32)


def feature_matrix(frame: pd.DataFrame, feature_set: str) -> np.ndarray:
    if feature_set == "descriptor":
        return np.vstack([rdkit_descriptor_vector(smiles) for smiles in frame["smiles"]]).astype(np.float32)
    if feature_set == "motif":
        return np.vstack([motif_vector(smiles) for smiles in frame["smiles"]]).astype(np.float32)
    raise ValueError(f"Unknown feature_set={feature_set}")


class ConstantEstimator:
    def __init__(self, value: float, task_type: str) -> None:
        self.value = float(value)
        self.task_type = task_type

    def fit(self, x, y):
        return self

    def predict(self, x):
        return np.full(len(x), self.value, dtype=np.float64)

    def predict_proba(self, x):
        prob = np.clip(np.full(len(x), self.value, dtype=np.float64), 1e-7, 1 - 1e-7)
        return np.column_stack([1 - prob, prob])


def build_estimator(model_name: str, task_type: str, seed: int, y_train: np.ndarray):
    if model_name == "descriptor_mlp":
        if task_type == "regression":
            estimator = TransformedTargetRegressor(
                regressor=MLPRegressor(
                    hidden_layer_sizes=(128, 64),
                    activation="tanh",
                    alpha=1e-2,
                    learning_rate_init=1e-4,
                    early_stopping=True,
                    n_iter_no_change=20,
                    max_iter=500,
                    random_state=seed,
                ),
                transformer=StandardScaler(),
            )
        else:
            estimator = MLPClassifier(
                hidden_layer_sizes=(128, 64),
                activation="tanh",
                alpha=1e-2,
                learning_rate_init=1e-4,
                early_stopping=True,
                n_iter_no_change=20,
                max_iter=500,
                random_state=seed,
            )
        return Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", RobustScaler()),
                ("model", estimator),
            ]
        )

    if task_type == "regression":
        if model_name == "rf_motif":
            estimator = RandomForestRegressor(n_estimators=360, random_state=seed, n_jobs=-1, max_features="sqrt")
        elif model_name == "extratrees_motif":
            estimator = ExtraTreesRegressor(n_estimators=420, random_state=seed, n_jobs=-1, max_features="sqrt")
        elif model_name == "xgb_motif":
            estimator = XGBRegressor(
                n_estimators=320,
                max_depth=3,
                learning_rate=0.035,
                subsample=0.9,
                colsample_bytree=0.75,
                reg_lambda=2.0,
                objective="reg:squarederror",
                tree_method="hist",
                random_state=seed,
                n_jobs=-1,
            )
        elif model_name == "lgbm_motif":
            estimator = LGBMRegressor(
                n_estimators=340,
                learning_rate=0.03,
                num_leaves=31,
                subsample=0.9,
                colsample_bytree=0.75,
                reg_lambda=2.0,
                random_state=seed,
                n_jobs=-1,
                verbose=-1,
            )
        else:
            raise ValueError(model_name)
    else:
        positives = float((y_train == 1).sum())
        negatives = float((y_train == 0).sum())
        scale_pos_weight = negatives / positives if positives > 0 else 1.0
        if model_name == "rf_motif":
            estimator = RandomForestClassifier(
                n_estimators=360,
                random_state=seed,
                n_jobs=-1,
                max_features="sqrt",
                class_weight="balanced_subsample",
            )
        elif model_name == "extratrees_motif":
            estimator = ExtraTreesClassifier(
                n_estimators=420,
                random_state=seed,
                n_jobs=-1,
                max_features="sqrt",
                class_weight="balanced",
            )
        elif model_name == "xgb_motif":
            estimator = XGBClassifier(
                n_estimators=320,
                max_depth=3,
                learning_rate=0.035,
                subsample=0.9,
                colsample_bytree=0.75,
                reg_lambda=2.0,
                objective="binary:logistic",
                eval_metric="logloss",
                tree_method="hist",
                scale_pos_weight=scale_pos_weight,
                random_state=seed,
                n_jobs=-1,
            )
        elif model_name == "lgbm_motif":
            estimator = LGBMClassifier(
                n_estimators=340,
                learning_rate=0.03,
                num_leaves=31,
                subsample=0.9,
                colsample_bytree=0.75,
                reg_lambda=2.0,
                class_weight="balanced",
                random_state=seed,
                n_jobs=-1,
                verbose=-1,
            )
        else:
            raise ValueError(model_name)
    return Pipeline([("imputer", SimpleImputer(strategy="median")), ("model", estimator)])


def predict(estimator, x: np.ndarray, task_type: str) -> np.ndarray:
    if task_type == "classification" and hasattr(estimator, "predict_proba"):
        return estimator.predict_proba(x)[:, 1]
    return estimator.predict(x)


def run_one(dataset: str, model_name: str, seed: int, output_dir: Path) -> dict:
    frame, spec = load_dataset(dataset, data_dir=ROOT / "data")
    split = make_split(frame, "scaffold", seed)
    feature_set = "descriptor" if model_name == "descriptor_mlp" else "motif"
    x = feature_matrix(frame, feature_set)
    y = frame["y"].to_numpy()
    y_train = y[split.train]
    if spec.task_type == "classification" and len(np.unique(y_train)) < 2:
        estimator = ConstantEstimator(float(np.mean(y_train)), spec.task_type)
    elif spec.task_type == "regression" and len(y_train) < 3:
        estimator = ConstantEstimator(float(np.mean(y_train)), spec.task_type)
    else:
        estimator = build_estimator(model_name, spec.task_type, seed, y_train)
    estimator.fit(x[split.train], y_train)
    valid_pred = predict(estimator, x[split.valid], spec.task_type)
    test_pred = predict(estimator, x[split.test], spec.task_type)
    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "smiles": frame.iloc[split.valid]["smiles"].to_numpy(),
            "y_true": y[split.valid],
            "y_pred": valid_pred,
        }
    ).to_csv(output_dir / f"{dataset}_{model_name}_seed{seed}_valid_predictions.csv", index=False)
    pd.DataFrame(
        {
            "smiles": frame.iloc[split.test]["smiles"].to_numpy(),
            "y_true": y[split.test],
            "y_pred": test_pred,
        }
    ).to_csv(output_dir / f"{dataset}_{model_name}_seed{seed}_predictions.csv", index=False)
    metrics = compute_metrics(spec.task_type, y[split.test], test_pred)
    return {
        "dataset": dataset,
        "model": model_name,
        "seed": seed,
        "split": "scaffold",
        "task_type": spec.task_type,
        **metrics,
    }


def summarize(metrics: pd.DataFrame, output_dir: Path) -> None:
    metrics.to_csv(output_dir / "metrics_raw.csv", index=False)
    id_cols = {"dataset", "model", "task_type", "seed", "split"}
    metric_cols = [col for col in metrics.columns if col not in id_cols and pd.api.types.is_numeric_dtype(metrics[col])]
    summary = (
        metrics.groupby(["dataset", "model", "task_type"], dropna=False)[metric_cols]
        .agg(["mean", "std"])
        .reset_index()
    )
    summary.to_csv(output_dir / "metrics_summary.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run descriptor-MLP and motif/scaffold expert baselines.")
    parser.add_argument("--datasets", nargs="*", default=["esol", "freesolv", "lipo", "bbbp", "bace", "clintox"])
    parser.add_argument("--models", nargs="*", default=["descriptor_mlp", "rf_motif", "xgb_motif", "lgbm_motif", "extratrees_motif"])
    parser.add_argument("--seeds", nargs="*", type=int, default=SEEDS)
    parser.add_argument("--output-dir", default=str(ROOT / "reports" / "descriptor_motif_baselines"))
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--no-resume", action="store_false", dest="resume")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "metrics_raw.csv"
    if args.resume and metrics_path.exists():
        metrics = pd.read_csv(metrics_path)
        rows = metrics.to_dict("records")
        completed = {(str(row["dataset"]), str(row["model"]), int(row["seed"])) for row in rows}
    else:
        rows = []
        completed = set()
    for dataset in args.datasets:
        if dataset not in DATASETS:
            raise KeyError(f"Unknown dataset: {dataset}")
        for seed in args.seeds:
            for model in args.models:
                key = (dataset, model, seed)
                if key in completed:
                    print(f"skip dataset={dataset} model={model} seed={seed}", flush=True)
                    continue
                print(f"start dataset={dataset} model={model} seed={seed}", flush=True)
                row = run_one(dataset, model, seed, output_dir)
                rows.append(row)
                completed.add(key)
                summarize(pd.DataFrame(rows), output_dir)
                primary = "rmse" if row["task_type"] == "regression" else "roc_auc"
                print(f"done dataset={dataset} model={model} seed={seed} {primary}={row.get(primary, np.nan):.6g}", flush=True)
    summarize(pd.DataFrame(rows), output_dir)
    print(pd.DataFrame(rows).tail(30).to_string(index=False))


if __name__ == "__main__":
    main()
