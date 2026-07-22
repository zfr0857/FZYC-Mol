from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import time
import warnings
from pathlib import Path

import lightgbm
import numpy as np
import pandas as pd
import sklearn
from lightgbm import LGBMClassifier, LGBMRegressor
from rdkit import Chem, DataStructs, RDLogger, rdBase
from rdkit.Chem import AllChem, Descriptors, MACCSkeys
from rdkit.Chem.Scaffolds import MurckoScaffold
from scipy.stats import spearmanr
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, mean_squared_error, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = Path(os.environ.get("FZYC_MULTIVIEW_OUT", ROOT / "results" / "reviewer_core_20260624" / "multiview_nested"))
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
SEEDS = [11, 23, 37, 53, 71]
REPRESENTATIONS = ["morgan512", "maccs", "rdkit2d", "multiview"]
MODEL_FAMILIES = ["linear", "random_forest", "lightgbm"]
POLICIES = ["fixed_morgan_rf", "validation_best", "one_se_stable", "risk_adjusted", "test_oracle"]
VARIANTS = {
    "full_multiview": REPRESENTATIONS,
    "morgan_only": ["morgan512"],
    "fingerprints_only": ["morgan512", "maccs"],
    "no_multiview_concat": ["morgan512", "maccs", "rdkit2d"],
}
RDLogger.DisableLog("rdApp.*")
warnings.filterwarnings("ignore", message="X does not have valid feature names, but LGBM.*")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", nargs="*", default=TASKS)
    parser.add_argument("--seeds", nargs="*", type=int, default=SEEDS)
    parser.add_argument("--outer-folds", type=int, default=3)
    parser.add_argument("--inner-folds", type=int, default=3)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def pick_column(df: pd.DataFrame, candidates: list[str]) -> str:
    lower = {c.lower(): c for c in df.columns}
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
        if candidate.lower() in lower:
            return lower[candidate.lower()]
    raise KeyError(f"No column from {candidates}; columns={list(df.columns)[:20]}")


def load_task(task: str, registry: dict[str, object]) -> tuple[pd.DataFrame, str]:
    meta = registry[task]
    path = DATA / "raw" / meta["filename"]
    if not path.exists():
        path = DATA / "tdc" / meta["filename"].replace(".csv", ".tab")
    frame = pd.read_csv(path, sep="\t" if path.suffix == ".tab" else ",")
    smiles_col = pick_column(frame, meta["smiles_candidates"])
    target_col = pick_column(frame, meta["target_candidates"])
    frame = frame[[smiles_col, target_col]].rename(columns={smiles_col: "smiles", target_col: "y"})
    frame["y"] = pd.to_numeric(frame["y"], errors="coerce")
    frame = frame.dropna(subset=["smiles", "y"]).drop_duplicates("smiles").reset_index(drop=True)
    if meta["task_type"] == "classification":
        frame["y"] = frame["y"].astype(int)
    return frame, str(meta["task_type"])


def featurize(smiles: pd.Series) -> tuple[dict[str, np.ndarray], np.ndarray, np.ndarray]:
    descriptor_functions = [(name, function) for name, function in Descriptors.descList if name != "Ipc"]
    morgan_rows: list[np.ndarray] = []
    maccs_rows: list[np.ndarray] = []
    descriptor_rows: list[list[float]] = []
    scaffolds: list[str] = []
    keep: list[bool] = []
    for smi in smiles.astype(str):
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            keep.append(False)
            continue
        morgan = np.zeros(512, dtype=np.float32)
        DataStructs.ConvertToNumpyArray(AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=512), morgan)
        maccs = np.zeros(167, dtype=np.float32)
        DataStructs.ConvertToNumpyArray(MACCSkeys.GenMACCSKeys(mol), maccs)
        descriptors = []
        for _, function in descriptor_functions:
            try:
                value = float(function(mol))
            except Exception:
                value = np.nan
            descriptors.append(value if np.isfinite(value) else np.nan)
        scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False)
        if not scaffold:
            scaffold = Chem.MolToSmiles(mol, canonical=True)
        morgan_rows.append(morgan)
        maccs_rows.append(maccs)
        descriptor_rows.append(descriptors)
        scaffolds.append(scaffold)
        keep.append(True)
    morgan = np.asarray(morgan_rows, dtype=np.float32)
    maccs = np.asarray(maccs_rows, dtype=np.float32)
    rdkit2d = np.asarray(descriptor_rows, dtype=np.float64)
    rdkit2d[~np.isfinite(rdkit2d)] = np.nan
    all_missing = np.all(~np.isfinite(rdkit2d), axis=0)
    rdkit2d[:, all_missing] = 0.0
    multiview = np.concatenate([morgan, maccs, rdkit2d], axis=1)
    return (
        {
            "morgan512": morgan,
            "maccs": maccs,
            "rdkit2d": rdkit2d,
            "multiview": multiview,
        },
        np.asarray(scaffolds),
        np.asarray(keep, dtype=bool),
    )


def valid_splits(splits: list[tuple[np.ndarray, np.ndarray]], y: np.ndarray, task_type: str) -> bool:
    if task_type != "classification":
        return True
    return all(len(np.unique(y[train])) == 2 and len(np.unique(y[test])) == 2 for train, test in splits)


def seeded_scaffold_group_kfold(
    groups: np.ndarray,
    n_splits: int,
    seed: int,
) -> list[tuple[np.ndarray, np.ndarray]]:
    rng = np.random.default_rng(seed)
    group_rows: dict[str, list[int]] = {}
    for index, group in enumerate(groups.astype(str)):
        group_rows.setdefault(group, []).append(index)
    records = list(group_rows.items())
    tie_order = rng.permutation(len(records))
    ordered = sorted((records[i] for i in tie_order), key=lambda item: -len(item[1]))
    fold_rows: list[list[int]] = [[] for _ in range(n_splits)]
    fold_sizes = np.zeros(n_splits, dtype=int)
    for _, indices in ordered:
        smallest = np.flatnonzero(fold_sizes == fold_sizes.min())
        fold = int(rng.choice(smallest))
        fold_rows[fold].extend(indices)
        fold_sizes[fold] += len(indices)
    universe = np.arange(len(groups), dtype=int)
    return [
        (np.setdiff1d(universe, np.asarray(sorted(rows), dtype=int), assume_unique=True), np.asarray(sorted(rows), dtype=int))
        for rows in fold_rows
    ]


def split_hash(train: np.ndarray, valid: np.ndarray, test: np.ndarray) -> str:
    payload = {
        "train": np.sort(train).astype(int).tolist(),
        "validation": np.sort(valid).astype(int).tolist(),
        "test": np.sort(test).astype(int).tolist(),
    }
    return hashlib.sha256(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def make_splits(
    y: np.ndarray,
    groups: np.ndarray,
    task_type: str,
    n_splits: int,
    seed: int,
) -> tuple[list[tuple[np.ndarray, np.ndarray]], str]:
    dummy = np.zeros((len(y), 1))
    if task_type == "classification":
        grouped = list(
            StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed).split(dummy, y, groups)
        )
        if valid_splits(grouped, y, task_type):
            return grouped, "stratified_scaffold_group"
        return (
            list(StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed).split(dummy, y)),
            "stratified_random_fallback",
        )
    return seeded_scaffold_group_kfold(groups, n_splits, seed), "seeded_scaffold_group_balanced"


def make_model(task_type: str, family: str, seed: int):
    if task_type == "classification":
        if family == "linear":
            model = LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced", solver="liblinear")
            return make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True), StandardScaler(), model)
        if family == "random_forest":
            model = RandomForestClassifier(
                n_estimators=80,
                max_features="sqrt",
                min_samples_leaf=2,
                class_weight="balanced_subsample",
                random_state=seed,
                n_jobs=-1,
            )
            return make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True), model)
        model = LGBMClassifier(
            n_estimators=80,
            learning_rate=0.06,
            num_leaves=31,
            min_child_samples=15,
            random_state=seed,
            n_jobs=-1,
            verbosity=-1,
        )
        return make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True), model)
    if family == "linear":
        return make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True), StandardScaler(), Ridge(alpha=1.0))
    if family == "random_forest":
        model = RandomForestRegressor(
            n_estimators=80,
            max_features="sqrt",
            min_samples_leaf=2,
            random_state=seed,
            n_jobs=-1,
        )
        return make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True), model)
    model = LGBMRegressor(
        n_estimators=80,
        learning_rate=0.06,
        num_leaves=31,
        min_child_samples=15,
        random_state=seed,
        n_jobs=-1,
        verbosity=-1,
    )
    return make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True), model)


def candidate_specs(task_type: str, seed: int) -> list[dict[str, object]]:
    specs = []
    order = 0
    for representation in REPRESENTATIONS:
        for family in MODEL_FAMILIES:
            order += 1
            specs.append(
                {
                    "candidate_order": order,
                    "candidate": f"{representation}__{family}",
                    "representation": representation,
                    "family": family,
                    "model": make_model(task_type, family, seed),
                }
            )
    return specs


def predict(model, features: np.ndarray, task_type: str) -> np.ndarray:
    if task_type == "classification":
        return np.asarray(model.predict_proba(features))[:, 1]
    return np.asarray(model.predict(features), dtype=float)


def utility(y: np.ndarray, prediction: np.ndarray, task_type: str) -> float:
    if task_type == "classification":
        return float(roc_auc_score(y, prediction)) if len(np.unique(y)) == 2 else np.nan
    return -float(np.sqrt(mean_squared_error(y, prediction)))


def choose(stats: pd.DataFrame, policy: str) -> str:
    ordered = stats.sort_values(["inner_mean", "candidate_order"], ascending=[False, True])
    if policy == "fixed_morgan_rf":
        return "morgan512__random_forest"
    if policy == "validation_best":
        return str(ordered.iloc[0]["candidate"])
    if policy == "risk_adjusted":
        scored = stats.assign(score=stats["inner_mean"] - 0.5 * stats["inner_sd"].fillna(0.0))
        return str(scored.sort_values(["score", "candidate_order"], ascending=[False, True]).iloc[0]["candidate"])
    if policy == "one_se_stable":
        best = ordered.iloc[0]
        threshold = float(best["inner_mean"]) - float(best["inner_sd"]) / math.sqrt(3)
        eligible = stats[stats["inner_mean"] >= threshold]
        return str(eligible.sort_values(["inner_sd", "fit_seconds_mean", "candidate_order"]).iloc[0]["candidate"])
    if policy == "test_oracle":
        return "__test_oracle__"
    raise ValueError(policy)


def run_task_seed(
    task: str,
    task_type: str,
    representations: dict[str, np.ndarray],
    groups: np.ndarray,
    y: np.ndarray,
    seed: int,
    args: argparse.Namespace,
) -> None:
    destination = OUT / "runs" / task / f"seed_{seed}"
    complete = destination / "complete.json"
    if complete.exists() and not args.force:
        print(f"SKIP {task} seed={seed}", flush=True)
        return
    destination.mkdir(parents=True, exist_ok=True)
    specs = candidate_specs(task_type, seed)
    outer_splits, outer_split_type = make_splits(y, groups, task_type, args.outer_folds, seed)
    registry_rows = [
        {
            "task": task,
            "task_type": task_type,
            "seed": seed,
            "candidate_order": spec["candidate_order"],
            "candidate": spec["candidate"],
            "representation": spec["representation"],
            "family": spec["family"],
            "feature_count": representations[str(spec["representation"])].shape[1],
            "model_class": spec["model"].steps[-1][1].__class__.__name__,
            "params": json.dumps(spec["model"].steps[-1][1].get_params(deep=False), default=str, sort_keys=True),
        }
        for spec in specs
    ]
    pd.DataFrame(registry_rows).to_csv(destination / "candidate_registry.csv", index=False)
    inner_rows: list[dict[str, object]] = []
    outer_rows: list[dict[str, object]] = []
    policy_rows: list[dict[str, object]] = []
    ranking_rows: list[dict[str, object]] = []
    prediction_rows: list[dict[str, object]] = []
    split_rows: list[dict[str, object]] = []
    for outer_fold, (outer_train, outer_test) in enumerate(outer_splits, start=1):
        inner_splits, inner_split_type = make_splits(
            y[outer_train], groups[outer_train], task_type, args.inner_folds, seed + outer_fold
        )
        outer_hash = split_hash(outer_train, np.asarray([], dtype=int), outer_test)
        for inner_fold, (train_local, valid_local) in enumerate(inner_splits, start=1):
            train = outer_train[train_local]
            valid = outer_train[valid_local]
            train_scaffolds = set(groups[train])
            valid_scaffolds = set(groups[valid])
            test_scaffolds = set(groups[outer_test])
            split_rows.append(
                {
                    "endpoint": task,
                    "task_type": task_type,
                    "seed": seed,
                    "outer_fold": outer_fold,
                    "inner_fold": inner_fold,
                    "train_n": len(train),
                    "validation_n": len(valid),
                    "test_n": len(outer_test),
                    "train_scaffold_n": len(train_scaffolds),
                    "validation_scaffold_n": len(valid_scaffolds),
                    "test_scaffold_n": len(test_scaffolds),
                    "target_mean": float(y[outer_test].mean()),
                    "target_sd": float(y[outer_test].std(ddof=1)) if len(outer_test) > 1 else 0.0,
                    "target_range": float(y[outer_test].max() - y[outer_test].min()),
                    "outer_split_hash": outer_hash,
                    "split_hash": split_hash(train, valid, outer_test),
                    "no_scaffold_overlap": not (
                        train_scaffolds & valid_scaffolds
                        or train_scaffolds & test_scaffolds
                        or valid_scaffolds & test_scaffolds
                    ),
                }
            )
        stats_rows = []
        for spec in specs:
            x = representations[str(spec["representation"])]
            fold_scores = []
            fold_times = []
            for inner_fold, (train_local, valid_local) in enumerate(inner_splits, start=1):
                train = outer_train[train_local]
                valid = outer_train[valid_local]
                model = clone(spec["model"])
                start = time.perf_counter()
                model.fit(x[train], y[train])
                elapsed = time.perf_counter() - start
                score = utility(y[valid], predict(model, x[valid], task_type), task_type)
                fold_scores.append(score)
                fold_times.append(elapsed)
                inner_rows.append(
                    {
                        "task": task,
                        "task_type": task_type,
                        "seed": seed,
                        "outer_fold": outer_fold,
                        "inner_fold": inner_fold,
                        "outer_split_type": outer_split_type,
                        "inner_split_type": inner_split_type,
                        "candidate_order": spec["candidate_order"],
                        "candidate": spec["candidate"],
                        "representation": spec["representation"],
                        "family": spec["family"],
                        "inner_utility": score,
                        "fit_seconds": elapsed,
                    }
                )
            stats_rows.append(
                {
                    "candidate_order": spec["candidate_order"],
                    "candidate": spec["candidate"],
                    "representation": spec["representation"],
                    "family": spec["family"],
                    "inner_mean": float(np.nanmean(fold_scores)),
                    "inner_sd": float(np.nanstd(fold_scores, ddof=1)),
                    "fit_seconds_mean": float(np.mean(fold_times)),
                }
            )
        stats = pd.DataFrame(stats_rows)
        outer_fold_rows = []
        for spec in specs:
            x = representations[str(spec["representation"])]
            model = clone(spec["model"])
            start = time.perf_counter()
            model.fit(x[outer_train], y[outer_train])
            elapsed = time.perf_counter() - start
            prediction = predict(model, x[outer_test], task_type)
            score = utility(y[outer_test], prediction, task_type)
            row = {
                "task": task,
                "task_type": task_type,
                "seed": seed,
                "outer_fold": outer_fold,
                "outer_split_type": outer_split_type,
                "candidate_order": spec["candidate_order"],
                "candidate": spec["candidate"],
                "representation": spec["representation"],
                "family": spec["family"],
                "n_train": len(outer_train),
                "n_test": len(outer_test),
                "outer_utility": score,
                "fit_seconds": elapsed,
                "roc_auc": score if task_type == "classification" else np.nan,
                "pr_auc": float(average_precision_score(y[outer_test], prediction)) if task_type == "classification" else np.nan,
                "rmse": -score if task_type == "regression" else np.nan,
            }
            outer_rows.append(row)
            outer_fold_rows.append(row)
            for sample_index, truth, value in zip(outer_test, y[outer_test], prediction):
                prediction_rows.append(
                    {
                        "task": task,
                        "task_type": task_type,
                        "seed": seed,
                        "outer_fold": outer_fold,
                        "outer_split_hash": outer_hash,
                        "candidate_order": spec["candidate_order"],
                        "candidate": spec["candidate"],
                        "representation": spec["representation"],
                        "family": spec["family"],
                        "sample_index": int(sample_index),
                        "y_true": float(truth),
                        "y_pred": float(value),
                        "scaffold": groups[sample_index],
                    }
                )
        outer_frame = pd.DataFrame(outer_fold_rows)
        for variant, allowed_representations in VARIANTS.items():
            variant_stats = stats[stats["representation"].isin(allowed_representations)].copy()
            variant_outer = outer_frame[outer_frame["representation"].isin(allowed_representations)].copy()
            oracle = variant_outer.sort_values(["outer_utility", "candidate_order"], ascending=[False, True]).iloc[0]
            full_range = max(float(variant_outer["outer_utility"].max() - variant_outer["outer_utility"].min()), 1e-12)
            validation_order = variant_stats.sort_values(["inner_mean", "candidate_order"], ascending=[False, True])
            oracle_validation_rank = int(np.where(validation_order["candidate"].to_numpy() == oracle["candidate"])[0][0]) + 1
            k = len(variant_stats)
            top3 = float(oracle_validation_rank <= min(3, k))
            chance = min(3, k) / k
            rho = float(spearmanr(variant_stats["inner_mean"], variant_outer.set_index("candidate").loc[variant_stats["candidate"], "outer_utility"]).statistic)
            ranking_rows.append(
                {
                    "task": task,
                    "task_type": task_type,
                    "seed": seed,
                    "outer_fold": outer_fold,
                    "variant": variant,
                    "candidate_count": k,
                    "oracle_validation_rank": oracle_validation_rank,
                    "top3_hit": top3,
                    "chance_adjusted_hit": (top3 - chance) / max(1.0 - chance, 1e-12),
                    "mrr": 1.0 / oracle_validation_rank,
                    "spearman": rho,
                }
            )
            for policy in POLICIES:
                if policy == "fixed_morgan_rf" and "morgan512" not in allowed_representations:
                    continue
                selected = choose(variant_stats, policy)
                selected_row = oracle if selected == "__test_oracle__" else variant_outer[variant_outer["candidate"].eq(selected)].iloc[0]
                policy_rows.append(
                    {
                        "task": task,
                        "task_type": task_type,
                        "seed": seed,
                        "outer_fold": outer_fold,
                        "variant": variant,
                        "candidate_count": k,
                        "policy": policy,
                        "selected_candidate": selected_row["candidate"],
                        "selected_representation": selected_row["representation"],
                        "selected_family": selected_row["family"],
                        "outer_utility": float(selected_row["outer_utility"]),
                        "oracle_candidate": oracle["candidate"],
                        "oracle_utility": float(oracle["outer_utility"]),
                        "raw_regret": float(oracle["outer_utility"] - selected_row["outer_utility"]),
                        "normalized_regret": float((oracle["outer_utility"] - selected_row["outer_utility"]) / full_range),
                    }
                )
        pd.DataFrame(inner_rows).to_csv(destination / "inner_scores.partial.csv", index=False)
        pd.DataFrame(outer_rows).to_csv(destination / "outer_candidate_scores.partial.csv", index=False)
        pd.DataFrame(policy_rows).to_csv(destination / "policy_detail.partial.csv", index=False)
        pd.DataFrame(split_rows).to_csv(destination / "split_manifest.partial.csv", index=False)
        print(f"{task} seed={seed}: outer {outer_fold}/{args.outer_folds}", flush=True)
    pd.DataFrame(inner_rows).to_csv(destination / "inner_scores.csv", index=False)
    pd.DataFrame(outer_rows).to_csv(destination / "outer_candidate_scores.csv", index=False)
    pd.DataFrame(policy_rows).to_csv(destination / "policy_detail.csv", index=False)
    pd.DataFrame(ranking_rows).to_csv(destination / "ranking_metrics.csv", index=False)
    pd.DataFrame(split_rows).to_csv(destination / "split_manifest.csv", index=False)
    pd.DataFrame(prediction_rows).to_csv(destination / "outer_predictions.csv.gz", index=False, compression="gzip")
    complete.write_text(
        json.dumps(
            {
                "task": task,
                "task_type": task_type,
                "seed": seed,
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


def cluster_ci(frame: pd.DataFrame, value: str, reps: int = 5000) -> tuple[float, float]:
    endpoint_values = {task: group[value].to_numpy(float) for task, group in frame.groupby("task", sort=True)}
    tasks = list(endpoint_values)
    rng = np.random.default_rng(20260624)
    values = []
    for _ in range(reps):
        sampled = rng.choice(tasks, len(tasks), replace=True)
        values.append(np.mean(np.concatenate([endpoint_values[task] for task in sampled])))
    return tuple(np.quantile(values, [0.025, 0.975]).astype(float))


def combine(args: argparse.Namespace) -> None:
    destinations = [OUT / "runs" / task / f"seed_{seed}" for task in args.tasks for seed in args.seeds]
    missing = [str(path) for path in destinations if not (path / "complete.json").exists()]
    if missing:
        raise RuntimeError(f"Incomplete runs: {missing[:5]}")
    registry = pd.concat([pd.read_csv(path / "candidate_registry.csv") for path in destinations], ignore_index=True)
    inner = pd.concat([pd.read_csv(path / "inner_scores.csv") for path in destinations], ignore_index=True)
    outer = pd.concat([pd.read_csv(path / "outer_candidate_scores.csv") for path in destinations], ignore_index=True)
    policies = pd.concat([pd.read_csv(path / "policy_detail.csv") for path in destinations], ignore_index=True)
    ranking = pd.concat([pd.read_csv(path / "ranking_metrics.csv") for path in destinations], ignore_index=True)
    splits = pd.concat([pd.read_csv(path / "split_manifest.csv") for path in destinations], ignore_index=True)
    predictions = pd.concat([pd.read_csv(path / "outer_predictions.csv.gz") for path in destinations], ignore_index=True)
    ranking.loc[ranking["candidate_count"] <= 3, "chance_adjusted_hit"] = np.nan
    registry.to_csv(OUT / "candidate_registry.csv", index=False)
    inner.to_csv(OUT / "inner_scores.csv", index=False)
    outer.to_csv(OUT / "outer_candidate_scores.csv", index=False)
    policies.to_csv(OUT / "policy_detail.csv", index=False)
    ranking.to_csv(OUT / "ranking_metrics.csv", index=False)
    splits.to_csv(OUT / "split_manifest.csv", index=False)
    predictions.to_csv(OUT / "outer_predictions.csv.gz", index=False, compression="gzip")
    summary_rows = []
    for (variant, policy), group in policies.groupby(["variant", "policy"], sort=True):
        low, high = cluster_ci(group, "normalized_regret")
        summary_rows.append(
            {
                "variant": variant,
                "policy": policy,
                "n_outer_units": len(group),
                "n_endpoints": group["task"].nunique(),
                "mean_normalized_regret": float(group["normalized_regret"].mean()),
                "median_normalized_regret": float(group["normalized_regret"].median()),
                "endpoint_cluster_ci95_low": low,
                "endpoint_cluster_ci95_high": high,
                "top_selected_representation": group["selected_representation"].value_counts().index[0],
                "top_selected_representation_rate": float(group["selected_representation"].value_counts(normalize=True).iloc[0]),
            }
        )
    pd.DataFrame(summary_rows).to_csv(OUT / "policy_summary.csv", index=False)
    ranking_summary = ranking.groupby("variant", as_index=False).agg(
        n_outer_units=("mrr", "size"),
        chance_adjusted_hit_mean=("chance_adjusted_hit", "mean"),
        mrr_mean=("mrr", "mean"),
        spearman_mean=("spearman", "mean"),
    )
    ranking_summary.to_csv(OUT / "ranking_summary.csv", index=False)
    selection = policies[policies["policy"].eq("validation_best")]
    selection.groupby(["variant", "selected_representation"], as_index=False).size().to_csv(
        OUT / "validation_best_representation_counts.csv", index=False
    )
    manifest = {
        "tasks": args.tasks,
        "seeds": args.seeds,
        "outer_folds": args.outer_folds,
        "inner_folds": args.inner_folds,
        "representations": REPRESENTATIONS,
        "model_families": MODEL_FAMILIES,
        "candidate_count": len(REPRESENTATIONS) * len(MODEL_FAMILIES),
        "split_compatibility": "same seeded scaffold-group allocation and repeat seeds as the confirmatory Morgan-512 experiment",
        "regression_splitter": "seeded scaffold-group allocation with random tie-breaking and sample-count balancing",
        "scope": "shared-split lightweight representation families; does not include retrained graph neural networks or chemical language models",
        "python": platform.python_version(),
        "sklearn": sklearn.__version__,
        "lightgbm": lightgbm.__version__,
        "rdkit": rdBase.rdkitVersion,
    }
    (OUT / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    invalid = sorted(set(args.tasks) - set(TASKS))
    if invalid:
        raise ValueError(f"Unknown tasks: {invalid}")
    OUT.mkdir(parents=True, exist_ok=True)
    registry = json.loads((DATA / "dataset_registry.json").read_text(encoding="utf-8"))
    for task in args.tasks:
        frame, task_type = load_task(task, registry)
        representations, groups, keep = featurize(frame["smiles"])
        y = frame.loc[keep, "y"].to_numpy()
        for seed in args.seeds:
            run_task_seed(task, task_type, representations, groups, y, seed, args)
    combine(args)
    print(OUT)


if __name__ == "__main__":
    main()
