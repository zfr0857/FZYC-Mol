from __future__ import annotations

import argparse
import hashlib
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRegressor
from rdkit import Chem, DataStructs, RDLogger
from rdkit.ML.Cluster import Butina
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.analysis import max_train_similarity
from fzyc_mol.datasets import DATASETS, load_dataset
from fzyc_mol.evaluate import compute_metrics
from fzyc_mol.features import descriptor_vector, mol_from_smiles, morgan_fingerprint, scaffold_from_smiles
from fzyc_mol.splits import SplitIndices, make_split


RDLogger.DisableLog("rdApp.*")


def stable_hash(text: str, seed: int) -> float:
    digest = hashlib.blake2b(f"{seed}:{text}".encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, byteorder="little") / 2**64


def _bitvect(smiles: str):
    arr = morgan_fingerprint(smiles)
    bitvect = DataStructs.ExplicitBitVect(arr.shape[0])
    for bit in np.flatnonzero(arr > 0):
        bitvect.SetBit(int(bit))
    return bitvect


def butina_clusters(smiles: list[str], cutoff: float) -> list[list[int]]:
    fps = [_bitvect(s) for s in smiles]
    distances = []
    for i in range(1, len(fps)):
        sims = DataStructs.BulkTanimotoSimilarity(fps[i], fps[:i])
        distances.extend([1.0 - sim for sim in sims])
    clusters = Butina.ClusterData(distances, len(fps), cutoff, isDistData=True)
    return [list(cluster) for cluster in clusters]


def scaffold_hash_clusters(smiles: list[str], seed: int) -> list[list[int]]:
    groups: dict[str, list[int]] = defaultdict(list)
    for idx, smi in enumerate(smiles):
        groups[scaffold_from_smiles(smi)].append(idx)
    return sorted(groups.values(), key=lambda group: stable_hash(scaffold_from_smiles(smiles[group[0]]), seed))


def groups_to_split(groups: list[list[int]], n_total: int, frac_train: float = 0.7, frac_valid: float = 0.1) -> SplitIndices:
    n_train = int(frac_train * n_total)
    n_valid = int(frac_valid * n_total)
    train: list[int] = []
    valid: list[int] = []
    test: list[int] = []
    for group in groups:
        if len(train) + len(group) <= n_train:
            train.extend(group)
        elif len(valid) + len(group) <= n_valid:
            valid.extend(group)
        else:
            test.extend(group)
    if not valid:
        valid, train = train[: max(1, n_total // 10)], train[max(1, n_total // 10) :]
    return SplitIndices(np.asarray(sorted(train), dtype=int), np.asarray(sorted(valid), dtype=int), np.asarray(sorted(test), dtype=int))


def structure_separated_split(frame: pd.DataFrame, seed: int, max_butina_n: int = 3500, cutoff: float = 0.45) -> SplitIndices:
    smiles = frame["smiles"].tolist()
    if len(smiles) <= max_butina_n:
        groups = butina_clusters(smiles, cutoff=cutoff)
        groups = sorted(groups, key=lambda g: (-len(g), stable_hash(str(g[0]), seed)))
    else:
        groups = scaffold_hash_clusters(smiles, seed)
    return groups_to_split(groups, len(frame))


def feature_matrix(frame: pd.DataFrame) -> np.ndarray:
    rows = []
    for smiles in frame["smiles"]:
        rows.append(np.hstack([morgan_fingerprint(smiles), descriptor_vector(smiles, include_3d=False)]))
    return np.vstack(rows).astype(np.float32)


def estimator(task_type: str, seed: int):
    if task_type == "regression":
        model = LGBMRegressor(
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
        model = LGBMClassifier(
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
    return Pipeline([("imputer", SimpleImputer(strategy="median")), ("model", model)])


def split_indices(frame: pd.DataFrame, split_method: str, seed: int) -> SplitIndices:
    if split_method in {"random", "scaffold"}:
        return make_split(frame, split_method, seed)
    if split_method == "structure":
        return structure_separated_split(frame, seed)
    raise ValueError(split_method)


def predict(model, x: np.ndarray, task_type: str) -> np.ndarray:
    if task_type == "classification" and hasattr(model[-1], "predict_proba"):
        return model.predict_proba(x)[:, 1]
    return model.predict(x)


def hard_subset_metrics(task_type: str, y_true: np.ndarray, pred: np.ndarray, similarity: np.ndarray) -> dict[str, float]:
    if len(similarity) < 5:
        return {}
    threshold = float(np.quantile(similarity, 0.25))
    mask = similarity <= threshold
    if mask.sum() < 3:
        return {}
    metrics = compute_metrics(task_type, y_true[mask], pred[mask])
    return {f"hard25_{k}": v for k, v in metrics.items()} | {"hard25_n": int(mask.sum()), "hard25_similarity_max": threshold}


def run_one(dataset: str, split_method: str, seed: int, output_dir: Path) -> dict:
    frame, spec = load_dataset(dataset, data_dir=ROOT / "data")
    split = split_indices(frame, split_method, seed)
    x = feature_matrix(frame)
    y = frame["y"].to_numpy()
    fit_idx = np.sort(np.concatenate([split.train, split.valid]))
    model = estimator(spec.task_type, seed)
    start = time.perf_counter()
    model.fit(x[fit_idx], y[fit_idx])
    fit_seconds = time.perf_counter() - start
    start = time.perf_counter()
    pred = predict(model, x[split.test], spec.task_type)
    predict_seconds = time.perf_counter() - start
    y_test = y[split.test]
    metrics = compute_metrics(spec.task_type, y_test, pred)
    train_smiles = frame.iloc[fit_idx]["smiles"].tolist()
    test_smiles = frame.iloc[split.test]["smiles"].tolist()
    similarity = max_train_similarity(train_smiles, test_smiles)
    metrics.update(hard_subset_metrics(spec.task_type, y_test, pred, similarity))
    pred_frame = pd.DataFrame(
        {
            "smiles": test_smiles,
            "y_true": y_test,
            "y_pred": pred,
            "max_train_tanimoto": similarity,
        }
    )
    pred_frame.to_csv(output_dir / f"{dataset}_lgbm_morgan_{split_method}_seed{seed}_predictions.csv", index=False)
    return {
        "dataset": dataset,
        "model": "lgbm_morgan",
        "split_method": split_method,
        "seed": seed,
        "task_type": spec.task_type,
        "n_train_valid": int(len(fit_idx)),
        "n_test": int(len(split.test)),
        "mean_test_similarity": float(np.mean(similarity)),
        "fit_seconds": fit_seconds,
        "predict_seconds": predict_seconds,
        **metrics,
    }


def split_slope(raw: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (dataset, task_type), group in raw.groupby(["dataset", "task_type"]):
        metric = "rmse" if task_type == "regression" else "roc_auc"
        pivot = group.groupby("split_method")[metric].mean()
        row = {"dataset": dataset, "task_type": task_type, "metric": metric}
        for split in ("random", "scaffold", "structure"):
            row[f"{split}_{metric}"] = float(pivot.get(split, np.nan))
        if task_type == "regression":
            row["random_to_scaffold_drop"] = row[f"scaffold_{metric}"] - row[f"random_{metric}"]
            row["scaffold_to_structure_drop"] = row[f"structure_{metric}"] - row[f"scaffold_{metric}"]
        else:
            row["random_to_scaffold_drop"] = row[f"random_{metric}"] - row[f"scaffold_{metric}"]
            row["scaffold_to_structure_drop"] = row[f"scaffold_{metric}"] - row[f"structure_{metric}"]
        rows.append(row)
    return pd.DataFrame(rows)


def summarize(rows: list[dict], output_dir: Path) -> None:
    raw = pd.DataFrame(rows)
    raw.to_csv(output_dir / "metrics_raw.csv", index=False)
    metric_cols = [c for c in raw.columns if c not in {"dataset", "model", "split_method", "seed", "task_type"} and pd.api.types.is_numeric_dtype(raw[c])]
    summary = (
        raw.groupby(["dataset", "model", "split_method", "task_type"], dropna=False)[metric_cols]
        .agg(["mean", "std"])
        .reset_index()
    )
    summary.to_csv(output_dir / "metrics_summary.csv", index=False)
    split_slope(raw).to_csv(output_dir / "split_realism_slope.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run random/scaffold/structure split-realism benchmark.")
    parser.add_argument("--datasets", nargs="*", default=["esol", "freesolv", "lipo", "bbbp", "bace", "clintox"])
    parser.add_argument("--split-methods", nargs="*", default=["random", "scaffold", "structure"])
    parser.add_argument("--seeds", nargs="*", type=int, default=[13, 17, 23])
    parser.add_argument("--output-dir", default=str(ROOT / "reports" / "split_realism_lgbm"))
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--no-resume", action="store_false", dest="resume")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "metrics_raw.csv"
    if args.resume and metrics_path.exists():
        rows = pd.read_csv(metrics_path).to_dict("records")
        done = {(r["dataset"], r["split_method"], int(r["seed"])) for r in rows}
    else:
        rows = []
        done = set()
    for dataset in args.datasets:
        if dataset not in DATASETS:
            raise KeyError(dataset)
        for split_method in args.split_methods:
            for seed in args.seeds:
                key = (dataset, split_method, seed)
                if key in done:
                    print(f"skip dataset={dataset} split={split_method} seed={seed}", flush=True)
                    continue
                print(f"start dataset={dataset} split={split_method} seed={seed}", flush=True)
                row = run_one(dataset, split_method, seed, output_dir)
                rows.append(row)
                done.add(key)
                summarize(rows, output_dir)
                primary = "rmse" if row["task_type"] == "regression" else "roc_auc"
                print(f"done dataset={dataset} split={split_method} seed={seed} {primary}={row.get(primary, np.nan):.6g}", flush=True)
    summarize(rows, output_dir)
    print(pd.DataFrame(rows).tail(30).to_string(index=False))


if __name__ == "__main__":
    main()
