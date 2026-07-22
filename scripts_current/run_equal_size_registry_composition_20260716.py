from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRegressor
from rdkit import Chem
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor, RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier, XGBRegressor


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_shared_split_multiview_nested_20260624 as shared


OUT = ROOT / "results" / "equal_size_registry_composition_20260716" / "new_candidates"
EMBEDDING_ROOT = ROOT / "data" / "processed" / "pretrained_embeddings"
TASKS = ["clintox", "bace", "esol"]
SEEDS = [11, 23, 37, 53, 71]
CLASSIC_REPRESENTATIONS = ["morgan512", "maccs", "rdkit2d", "multiview"]
EMBEDDINGS = {
    "chemberta_mtr": "DeepChem_ChemBERTa-77M-MTR",
    "chemberta_mlm": "DeepChem_ChemBERTa-77M-MLM",
    "molformer": "ibm_MoLFormer-XL-both-10pct",
}
EXTRA_CLASSIC_FAMILIES = ["extra_trees", "linear_alt", "random_forest_alt", "lightgbm_alt", "xgboost"]
EMBEDDING_FAMILIES = ["linear", "linear_alt", "linear_strong", "linear_sparse", "lightgbm"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", nargs="*", default=TASKS)
    parser.add_argument("--seeds", nargs="*", type=int, default=SEEDS)
    parser.add_argument("--outer-folds", type=int, default=3)
    parser.add_argument("--inner-folds", type=int, default=3)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def pipeline(model, scale: bool = False):
    steps = [SimpleImputer(strategy="median", keep_empty_features=True)]
    if scale:
        steps.append(StandardScaler())
    steps.append(model)
    return make_pipeline(*steps)


def make_model(task_type: str, family: str, seed: int):
    classification = task_type == "classification"
    if family == "linear":
        if classification:
            return pipeline(LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced", solver="liblinear"), True)
        return pipeline(Ridge(alpha=1.0, solver="lsqr"), True)
    if family == "linear_alt":
        if classification:
            return pipeline(LogisticRegression(C=0.1, max_iter=3000, class_weight="balanced", solver="liblinear"), True)
        return pipeline(Ridge(alpha=10.0, solver="lsqr"), True)
    if family == "linear_strong":
        if classification:
            return pipeline(LogisticRegression(C=10.0, max_iter=3000, class_weight="balanced", solver="liblinear"), True)
        return pipeline(Ridge(alpha=0.1, solver="lsqr"), True)
    if family == "linear_sparse":
        if classification:
            return pipeline(LogisticRegression(
                C=1.0, penalty="l1", max_iter=3000, class_weight="balanced", solver="liblinear"
            ), True)
        return pipeline(Ridge(alpha=100.0, solver="lsqr"), True)
    if family in {"random_forest", "random_forest_alt"}:
        n_estimators = 80 if family == "random_forest" else 120
        min_leaf = 2 if family == "random_forest" else 1
        if classification:
            model = RandomForestClassifier(
                n_estimators=n_estimators, max_features="sqrt", min_samples_leaf=min_leaf,
                class_weight="balanced_subsample", random_state=seed, n_jobs=2,
            )
        else:
            model = RandomForestRegressor(
                n_estimators=n_estimators, max_features="sqrt", min_samples_leaf=min_leaf,
                random_state=seed, n_jobs=2,
            )
        return pipeline(model)
    if family == "extra_trees":
        if classification:
            model = ExtraTreesClassifier(
                n_estimators=100, max_features="sqrt", min_samples_leaf=2,
                class_weight="balanced", random_state=seed, n_jobs=2,
            )
        else:
            model = ExtraTreesRegressor(
                n_estimators=100, max_features="sqrt", min_samples_leaf=2,
                random_state=seed, n_jobs=2,
            )
        return pipeline(model)
    if family in {"lightgbm", "lightgbm_alt"}:
        leaves = 31 if family == "lightgbm" else 15
        rate = 0.06 if family == "lightgbm" else 0.04
        estimators = 80 if family == "lightgbm" else 120
        cls = LGBMClassifier if classification else LGBMRegressor
        return pipeline(cls(
            n_estimators=estimators, learning_rate=rate, num_leaves=leaves,
            min_child_samples=15, random_state=seed, n_jobs=2, verbosity=-1,
        ))
    if family == "xgboost":
        if classification:
            model = XGBClassifier(
                n_estimators=80, max_depth=3, learning_rate=0.06, subsample=0.9,
                colsample_bytree=0.8, eval_metric="logloss", random_state=seed, n_jobs=2,
            )
        else:
            model = XGBRegressor(
                n_estimators=80, max_depth=3, learning_rate=0.06, subsample=0.9,
                colsample_bytree=0.8, objective="reg:squarederror", random_state=seed, n_jobs=2,
            )
        return pipeline(model)
    raise ValueError(family)


def load_embedding(task: str, smiles: pd.Series, encoder_dir: str) -> np.ndarray:
    payload = np.load(EMBEDDING_ROOT / encoder_dir / f"{task}.npz", allow_pickle=True)
    source_smiles = payload["smiles"].astype(str)
    vectors = np.asarray(payload["embedding"], dtype=np.float32)
    def canonical(smi: str) -> str:
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            raise ValueError(f"Invalid SMILES during embedding alignment: {smi}")
        return Chem.MolToSmiles(mol, canonical=True)

    source_keys = [canonical(smi) for smi in source_smiles]
    if len(set(source_keys)) != len(source_keys):
        raise ValueError(f"Duplicate canonical SMILES in cached embedding: {encoder_dir}/{task}")
    lookup = {key: i for i, key in enumerate(source_keys)}
    target_keys = [canonical(smi) for smi in smiles.astype(str)]
    missing = [key for key in target_keys if key not in lookup]
    if missing:
        raise ValueError(f"{len(missing)} missing embeddings for {encoder_dir}/{task}")
    return np.vstack([vectors[lookup[key]] for key in target_keys])


def candidate_specs(task_type: str, seed: int) -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    for representation in CLASSIC_REPRESENTATIONS:
        for family in EXTRA_CLASSIC_FAMILIES:
            specs.append({
                "candidate": f"{representation}__{family}",
                "representation": representation,
                "family": family,
                "candidate_group": "classic_extension",
                "model": make_model(task_type, family, seed),
            })
    for representation in EMBEDDINGS:
        for family in EMBEDDING_FAMILIES:
            specs.append({
                "candidate": f"{representation}__{family}",
                "representation": representation,
                "family": family,
                "candidate_group": "frozen_pretrained_embedding",
                "model": make_model(task_type, family, seed),
            })
    return specs


def predict(model, x: np.ndarray, task_type: str) -> np.ndarray:
    if task_type == "classification":
        return np.asarray(model.predict_proba(x), dtype=float)[:, 1]
    return np.asarray(model.predict(x), dtype=float)


def run_task_seed(task: str, seed: int, args: argparse.Namespace, registry: dict[str, object]) -> None:
    target = OUT / task / f"seed_{seed}"
    complete = target / "complete.json"
    if complete.exists() and not args.force:
        print(f"SKIP {task} seed {seed}", flush=True)
        return
    target.mkdir(parents=True, exist_ok=True)
    frame, task_type = shared.load_task(task, registry)
    representations, groups, keep = shared.featurize(frame["smiles"])
    frame = frame.loc[keep].reset_index(drop=True)
    y = frame["y"].to_numpy()
    for short, encoder_dir in EMBEDDINGS.items():
        representations[short] = load_embedding(task, frame["smiles"], encoder_dir)
    specs = candidate_specs(task_type, seed)
    outer_splits, outer_split_type = shared.make_splits(y, groups, task_type, args.outer_folds, seed)

    registry_rows = []
    for order, spec in enumerate(specs, start=1):
        registry_rows.append({
            "task": task, "task_type": task_type, "seed": seed, "candidate_order": order,
            "candidate": spec["candidate"], "representation": spec["representation"],
            "family": spec["family"], "candidate_group": spec["candidate_group"],
            "feature_count": representations[str(spec["representation"])].shape[1],
            "model_class": spec["model"].steps[-1][1].__class__.__name__,
            "params": json.dumps(spec["model"].steps[-1][1].get_params(deep=False), default=str, sort_keys=True),
        })
    pd.DataFrame(registry_rows).to_csv(target / "candidate_registry.csv", index=False)

    inner_rows: list[dict[str, object]] = []
    outer_rows: list[dict[str, object]] = []
    split_rows: list[dict[str, object]] = []
    for outer_fold, (outer_train, outer_test) in enumerate(outer_splits, start=1):
        inner_splits, inner_split_type = shared.make_splits(
            y[outer_train], groups[outer_train], task_type, args.inner_folds, seed + outer_fold
        )
        split_rows.append({
            "task": task, "task_type": task_type, "seed": seed, "outer_fold": outer_fold,
            "outer_split_type": outer_split_type, "inner_split_type": inner_split_type,
            "outer_split_hash": shared.split_hash(outer_train, np.asarray([], dtype=int), outer_test),
            "train_n": len(outer_train), "test_n": len(outer_test),
        })
        for order, spec in enumerate(specs, start=1):
            x = representations[str(spec["representation"])]
            for inner_fold, (train_local, valid_local) in enumerate(inner_splits, start=1):
                train_idx = outer_train[train_local]
                valid_idx = outer_train[valid_local]
                model = clone(spec["model"])
                started = time.perf_counter()
                model.fit(x[train_idx], y[train_idx])
                pred = predict(model, x[valid_idx], task_type)
                seconds = time.perf_counter() - started
                inner_rows.append({
                    "task": task, "task_type": task_type, "seed": seed,
                    "outer_fold": outer_fold, "inner_fold": inner_fold,
                    "outer_split_type": outer_split_type, "inner_split_type": inner_split_type,
                    "candidate_order": order, "candidate": spec["candidate"],
                    "representation": spec["representation"], "family": spec["family"],
                    "candidate_group": spec["candidate_group"],
                    "inner_utility": shared.utility(y[valid_idx], pred, task_type),
                    "fit_seconds": seconds,
                })
            model = clone(spec["model"])
            started = time.perf_counter()
            model.fit(x[outer_train], y[outer_train])
            pred = predict(model, x[outer_test], task_type)
            seconds = time.perf_counter() - started
            outer_rows.append({
                "task": task, "task_type": task_type, "seed": seed,
                "outer_fold": outer_fold, "outer_split_type": outer_split_type,
                "candidate_order": order, "candidate": spec["candidate"],
                "representation": spec["representation"], "family": spec["family"],
                "candidate_group": spec["candidate_group"],
                "outer_utility": shared.utility(y[outer_test], pred, task_type),
                "fit_seconds": seconds,
            })
        pd.DataFrame(inner_rows).to_csv(target / "inner_scores.partial.csv", index=False)
        pd.DataFrame(outer_rows).to_csv(target / "outer_candidate_scores.partial.csv", index=False)
        print(f"{task} seed {seed}: outer {outer_fold}/{args.outer_folds}", flush=True)

    pd.DataFrame(inner_rows).to_csv(target / "inner_scores.csv", index=False)
    pd.DataFrame(outer_rows).to_csv(target / "outer_candidate_scores.csv", index=False)
    pd.DataFrame(split_rows).to_csv(target / "split_manifest.csv", index=False)
    complete.write_text(json.dumps({
        "task": task, "seed": seed, "task_type": task_type,
        "candidate_count": len(specs), "inner_rows": len(inner_rows), "outer_rows": len(outer_rows),
        "cached_pretrained_embeddings": list(EMBEDDINGS),
        "scope": "frozen embeddings plus lightweight nested heads; pretrained encoder cost amortized and excluded",
    }, indent=2), encoding="utf-8")


def consolidate(tasks: list[str], seeds: list[int]) -> None:
    dirs = [OUT / task / f"seed_{seed}" for task in tasks for seed in seeds]
    if not all((directory / "complete.json").exists() for directory in dirs):
        return
    for filename in ("candidate_registry.csv", "inner_scores.csv", "outer_candidate_scores.csv", "split_manifest.csv"):
        pd.concat([pd.read_csv(directory / filename) for directory in dirs], ignore_index=True).to_csv(OUT / filename, index=False)
    (OUT / "run_manifest.json").write_text(json.dumps({
        "tasks": tasks, "seeds": seeds, "outer_folds": 3, "inner_folds": 3,
        "new_candidate_count": 35, "new_model_fits": 35 * len(tasks) * len(seeds) * 3 * 4,
        "classic_representations": CLASSIC_REPRESENTATIONS,
        "pretrained_embeddings": EMBEDDINGS,
        "pretraining_cost_included": False,
    }, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    registry = json.loads((ROOT / "data" / "dataset_registry.json").read_text(encoding="utf-8"))
    for task in args.tasks:
        for seed in args.seeds:
            run_task_seed(task, seed, args, registry)
    consolidate(args.tasks, args.seeds)


if __name__ == "__main__":
    main()
