from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from rdkit import Chem, RDLogger
from rdkit.Chem.Scaffolds import MurckoScaffold
from scipy.stats import spearmanr
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, mean_squared_error, roc_auc_score
from sklearn.model_selection import GroupKFold, KFold, StratifiedGroupKFold, StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import DATASETS, load_raw_dataset

sys.path.insert(0, str(ROOT / "scripts"))
import run_shared_split_multiview_nested_20260624 as shared


RDLogger.DisableLog("rdApp.*")
warnings.filterwarnings("ignore", category=UserWarning)

OUT = ROOT / "output" / "小论文-12_严格补实验"
TASKS = ["esol", "bace", "clintox"]
SEEDS = [11, 23, 37, 53, 71]
EMBEDDING_ROOT = ROOT / "data" / "processed" / "pretrained_embeddings"
EMBEDDERS = {
    "chemberta_mtr": "DeepChem_ChemBERTa-77M-MTR",
    "molformer": "ibm_MoLFormer-XL-both-10pct",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", nargs="*", default=TASKS)
    parser.add_argument("--seeds", nargs="*", type=int, default=SEEDS)
    parser.add_argument("--outer-folds", type=int, default=3)
    parser.add_argument("--inner-folds", type=int, default=3)
    parser.add_argument("--gnn-epochs", type=int, default=5)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def canonical_smiles(smiles: str) -> str | None:
    if not isinstance(smiles, str) or not smiles.strip():
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return Chem.MolToSmiles(mol, canonical=True)


def load_task_raw(task: str) -> tuple[pd.DataFrame, str]:
    spec = DATASETS[task]
    raw = load_raw_dataset(task, ROOT / "data")
    smiles_col = shared.pick_column(raw, list(spec.smiles_candidates))
    target_col = shared.pick_column(raw, list(spec.target_candidates))
    frame = raw[[smiles_col, target_col]].rename(columns={smiles_col: "smiles_raw", target_col: "y"})
    frame["smiles"] = frame["smiles_raw"].map(canonical_smiles)
    frame["y"] = pd.to_numeric(frame["y"], errors="coerce")
    frame = frame.dropna(subset=["smiles", "y"]).reset_index(drop=True)
    if spec.task_type == "classification":
        frame["y"] = frame["y"].astype(int)
        frame = frame[frame["y"].isin([0, 1])].reset_index(drop=True)
    return frame, spec.task_type


def global_deduplicate(frame: pd.DataFrame, task_type: str) -> pd.DataFrame:
    rows = []
    for smi, group in frame.groupby("smiles", sort=False):
        if task_type == "regression":
            y = float(group["y"].mean())
            action = "mean_aggregated" if len(group) > 1 else "single"
        else:
            values = sorted(group["y"].unique().tolist())
            if len(values) != 1:
                continue
            y = int(values[0])
            action = "consistent_label_merged" if len(group) > 1 else "single"
        rows.append({"smiles": smi, "y": y, "duplicate_action": action, "raw_count": len(group)})
    return pd.DataFrame(rows).reset_index(drop=True)


def keep_duplicates_grouped(frame: pd.DataFrame, task_type: str) -> pd.DataFrame:
    kept = frame[["smiles", "y"]].copy()
    kept["duplicate_action"] = "kept_duplicate_grouped"
    kept["raw_count"] = 1
    if task_type == "classification":
        kept["y"] = kept["y"].astype(int)
    return kept.reset_index(drop=True)


def scaffold(smiles: str) -> str:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return smiles
    s = MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False)
    return s or smiles


def featurize_frame(frame: pd.DataFrame) -> tuple[dict[str, np.ndarray], np.ndarray, np.ndarray, pd.DataFrame]:
    reps, groups, keep = shared.featurize(frame["smiles"])
    filtered = frame.loc[keep].reset_index(drop=True)
    y = filtered["y"].to_numpy()
    return reps, groups, y, filtered


def make_splits(y: np.ndarray, groups: np.ndarray, task_type: str, n_splits: int, seed: int):
    return shared.make_splits(y, groups, task_type, n_splits, seed)


def metric_utility(task_type: str, y: np.ndarray, pred: np.ndarray) -> float:
    return shared.utility(y, pred, task_type)


def compute_metric_columns(task_type: str, y: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    if task_type == "classification":
        return {
            "roc_auc": float(roc_auc_score(y, pred)) if len(np.unique(y)) == 2 else np.nan,
            "pr_auc": float(average_precision_score(y, pred)) if len(np.unique(y)) == 2 else np.nan,
            "rmse": np.nan,
        }
    rmse = float(np.sqrt(mean_squared_error(y, pred)))
    return {"roc_auc": np.nan, "pr_auc": np.nan, "rmse": rmse}


def load_embedding(task: str, smiles: pd.Series, embedder_dir: str) -> np.ndarray | None:
    path = EMBEDDING_ROOT / embedder_dir / f"{task}.npz"
    if not path.exists():
        return None
    payload = np.load(path, allow_pickle=True)
    saved_smiles = [canonical_smiles(str(x)) or str(x) for x in payload["smiles"].tolist()]
    emb = payload["embedding"].astype(np.float32)
    lookup = {smi: emb[i] for i, smi in enumerate(saved_smiles)}
    query = [canonical_smiles(str(smi)) or str(smi) for smi in smiles.tolist()]
    missing = [smi for smi in query if smi not in lookup]
    if missing:
        return None
    return np.vstack([lookup[smi] for smi in query]).astype(np.float32)


def make_tabular_model(task_type: str, kind: str, seed: int):
    if task_type == "classification":
        if kind == "linear":
            return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced", solver="liblinear"))
        return make_pipeline(SimpleImputer(strategy="median"), RandomForestClassifier(n_estimators=120, max_features="sqrt", min_samples_leaf=2, class_weight="balanced_subsample", random_state=seed, n_jobs=-1))
    if kind == "linear":
        return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=1.0))
    return make_pipeline(SimpleImputer(strategy="median"), RandomForestRegressor(n_estimators=120, max_features="sqrt", min_samples_leaf=2, random_state=seed, n_jobs=-1))


def try_tabpfn_status() -> dict[str, object]:
    try:
        from tabpfn import TabPFNClassifier

        x = np.random.default_rng(0).normal(size=(30, 8))
        y = (x[:, 0] > 0).astype(int)
        model = TabPFNClassifier(n_estimators=1, device="cpu", random_state=0, ignore_pretraining_limits=True, show_progress_bar=False)
        model.fit(x, y)
        return {"candidate": "tabpfn_rdkit", "status": "available", "reason": ""}
    except Exception as exc:
        return {"candidate": "tabpfn_rdkit", "status": "runtime_unavailable", "reason": f"{type(exc).__name__}: {str(exc).splitlines()[0]}"}


def graph_data_from_smiles(smiles: str, y: float):
    import torch
    from torch_geometric.data import Data

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        x = torch.zeros((1, 6), dtype=torch.float32)
        edge_index = torch.empty((2, 0), dtype=torch.long)
        return Data(x=x, edge_index=edge_index, y=torch.tensor([float(y)], dtype=torch.float32))
    feats = []
    for atom in mol.GetAtoms():
        feats.append(
            [
                atom.GetAtomicNum() / 100.0,
                atom.GetTotalDegree() / 6.0,
                atom.GetFormalCharge(),
                float(atom.GetIsAromatic()),
                atom.GetTotalNumHs() / 4.0,
                atom.GetMass() / 200.0,
            ]
        )
    edges = []
    for bond in mol.GetBonds():
        a, b = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        edges.extend([(a, b), (b, a)])
    if not edges:
        edges = [(0, 0)]
    return Data(
        x=torch.tensor(feats, dtype=torch.float32),
        edge_index=torch.tensor(edges, dtype=torch.long).t().contiguous(),
        y=torch.tensor([float(y)], dtype=torch.float32),
    )


def train_gnn_predict(task_type: str, train_frame: pd.DataFrame, test_frame: pd.DataFrame, seed: int, epochs: int) -> np.ndarray:
    import torch
    from torch import nn
    from torch_geometric.loader import DataLoader
    from torch_geometric.nn import GCNConv, global_mean_pool

    torch.manual_seed(seed)
    train_data = [graph_data_from_smiles(s, y) for s, y in zip(train_frame["smiles"], train_frame["y"])]
    test_data = [graph_data_from_smiles(s, y) for s, y in zip(test_frame["smiles"], test_frame["y"])]
    loader = DataLoader(train_data, batch_size=64, shuffle=True)

    class GCN(nn.Module):
        def __init__(self):
            super().__init__()
            self.conv1 = GCNConv(6, 32)
            self.conv2 = GCNConv(32, 32)
            self.out = nn.Linear(32, 1)

        def forward(self, data):
            x = torch.relu(self.conv1(data.x, data.edge_index))
            x = torch.relu(self.conv2(x, data.edge_index))
            x = global_mean_pool(x, data.batch)
            return self.out(x).view(-1)

    model = GCN()
    y_train = train_frame["y"].to_numpy()
    if task_type == "classification":
        positives = max(float((y_train == 1).sum()), 1.0)
        negatives = max(float((y_train == 0).sum()), 1.0)
        loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([negatives / positives], dtype=torch.float32))
    else:
        loss_fn = nn.MSELoss()
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    model.train()
    for _ in range(max(1, epochs)):
        for batch in loader:
            opt.zero_grad()
            pred = model(batch)
            target = batch.y.view(-1)
            loss = loss_fn(pred, target)
            loss.backward()
            opt.step()
    model.eval()
    preds = []
    with torch.no_grad():
        for batch in DataLoader(test_data, batch_size=128, shuffle=False):
            raw = model(batch).cpu().numpy()
            if task_type == "classification":
                raw = 1.0 / (1.0 + np.exp(-np.clip(raw, -60, 60)))
            preds.extend(raw.tolist())
    return np.asarray(preds, dtype=float)


def predict_tabular(task_type: str, model, x_train, y_train, x_test) -> np.ndarray:
    model.fit(x_train, y_train)
    if task_type == "classification":
        return model.predict_proba(x_test)[:, 1]
    return model.predict(x_test)


def strong_baseline_panel(args: argparse.Namespace) -> dict[str, object]:
    status_rows = [try_tabpfn_status()]
    registry_rows: list[dict[str, object]] = []
    inner_rows: list[dict[str, object]] = []
    outer_rows: list[dict[str, object]] = []
    pred_rows: list[dict[str, object]] = []

    dataset_registry = json.loads((ROOT / "data" / "dataset_registry.json").read_text(encoding="utf-8"))
    for task in args.tasks:
        frame, task_type = shared.load_task(task, dataset_registry)
        reps, groups, keep = shared.featurize(frame["smiles"])
        frame = frame.loc[keep].reset_index(drop=True)
        y = frame["y"].to_numpy()
        emb_mats = {name: load_embedding(task, frame["smiles"], dirname) for name, dirname in EMBEDDERS.items()}
        for seed in args.seeds:
            outer_splits, outer_split_type = make_splits(y, groups, task_type, args.outer_folds, seed)
            base_specs: list[dict[str, object]] = [
                {"candidate": "gnn_gcn", "family": "GNN", "representation": "molecular_graph", "status": "completed"},
                {"candidate": "rdkit_rf", "family": "strong_tree", "representation": "rdkit2d", "status": "completed"},
            ]
            for emb_name, emb in emb_mats.items():
                base_specs.append(
                    {
                        "candidate": f"{emb_name}_linear_probe",
                        "family": "frozen_pretrained_adapter",
                        "representation": emb_name,
                        "status": "completed" if emb is not None else "missing_embedding",
                    }
                )
            base_specs.append({"candidate": "tabpfn_rdkit", "family": "tabular_foundation_model", "representation": "rdkit2d", "status": status_rows[0]["status"]})
            for order, spec in enumerate(base_specs, start=1):
                registry_rows.append({"task": task, "task_type": task_type, "seed": seed, "candidate_order": order, **spec})
            for outer_fold, (outer_train, outer_test) in enumerate(outer_splits, start=1):
                inner_splits, inner_split_type = make_splits(y[outer_train], groups[outer_train], task_type, args.inner_folds, seed + outer_fold)
                for order, spec in enumerate(base_specs, start=1):
                    if spec["status"] != "completed":
                        continue
                    candidate = str(spec["candidate"])
                    fold_scores = []
                    for inner_fold, (tr_local, va_local) in enumerate(inner_splits, start=1):
                        tr = outer_train[tr_local]
                        va = outer_train[va_local]
                        start = time.perf_counter()
                        if candidate == "gnn_gcn":
                            pred = train_gnn_predict(task_type, frame.iloc[tr], frame.iloc[va], seed + inner_fold, args.gnn_epochs)
                        elif candidate == "rdkit_rf":
                            model = make_tabular_model(task_type, "rf", seed)
                            pred = predict_tabular(task_type, model, reps["rdkit2d"][tr], y[tr], reps["rdkit2d"][va])
                        else:
                            emb_name = candidate.replace("_linear_probe", "")
                            model = make_tabular_model(task_type, "linear", seed)
                            pred = predict_tabular(task_type, model, emb_mats[emb_name][tr], y[tr], emb_mats[emb_name][va])
                        elapsed = time.perf_counter() - start
                        score = metric_utility(task_type, y[va], pred)
                        fold_scores.append(score)
                        inner_rows.append(
                            {
                                "task": task,
                                "task_type": task_type,
                                "seed": seed,
                                "outer_fold": outer_fold,
                                "inner_fold": inner_fold,
                                "outer_split_type": outer_split_type,
                                "inner_split_type": inner_split_type,
                                "candidate_order": order,
                                "candidate": candidate,
                                "family": spec["family"],
                                "inner_utility": score,
                                "fit_seconds": elapsed,
                            }
                        )
                    start = time.perf_counter()
                    if candidate == "gnn_gcn":
                        outer_pred = train_gnn_predict(task_type, frame.iloc[outer_train], frame.iloc[outer_test], seed, args.gnn_epochs)
                    elif candidate == "rdkit_rf":
                        model = make_tabular_model(task_type, "rf", seed)
                        outer_pred = predict_tabular(task_type, model, reps["rdkit2d"][outer_train], y[outer_train], reps["rdkit2d"][outer_test])
                    else:
                        emb_name = candidate.replace("_linear_probe", "")
                        model = make_tabular_model(task_type, "linear", seed)
                        outer_pred = predict_tabular(task_type, model, emb_mats[emb_name][outer_train], y[outer_train], emb_mats[emb_name][outer_test])
                    elapsed = time.perf_counter() - start
                    score = metric_utility(task_type, y[outer_test], outer_pred)
                    metric_cols = compute_metric_columns(task_type, y[outer_test], outer_pred)
                    outer_rows.append(
                        {
                            "task": task,
                            "task_type": task_type,
                            "seed": seed,
                            "outer_fold": outer_fold,
                            "outer_split_type": outer_split_type,
                            "candidate_order": order,
                            "candidate": candidate,
                            "family": spec["family"],
                            "outer_utility": score,
                            "inner_mean": float(np.nanmean(fold_scores)),
                            "inner_sd": float(np.nanstd(fold_scores, ddof=1)),
                            "fit_seconds": elapsed,
                            **metric_cols,
                        }
                    )
                    for local_i, idx in enumerate(outer_test):
                        pred_rows.append(
                            {
                                "task": task,
                                "task_type": task_type,
                                "seed": seed,
                                "outer_fold": outer_fold,
                                "sample_index": int(idx),
                                "smiles": frame.iloc[idx]["smiles"],
                                "y_true": float(y[idx]),
                                "candidate": candidate,
                                "family": spec["family"],
                                "y_pred": float(outer_pred[local_i]),
                            }
                        )
                print(f"strong-panel {task} seed={seed} outer={outer_fold}/{args.outer_folds}", flush=True)

    registry = pd.DataFrame(registry_rows)
    inner = pd.DataFrame(inner_rows)
    outer = pd.DataFrame(outer_rows)
    preds = pd.DataFrame(pred_rows)
    status = pd.DataFrame(status_rows + [{"candidate": "chemprop_dmpnn", "status": "not_run_in_this_script", "reason": "Chemprop CLI smoke test passed, but full 3x3x5 inner-loop training is managed separately because each fold launches an external training process."}])
    registry.to_csv(OUT / "strong_baseline_registry.csv", index=False)
    inner.to_csv(OUT / "strong_baseline_inner_scores.csv", index=False)
    outer.to_csv(OUT / "strong_baseline_outer_scores.csv", index=False)
    preds.to_csv(OUT / "strong_baseline_outer_predictions.csv", index=False)
    status.to_csv(OUT / "strong_baseline_runtime_status.csv", index=False)

    summary = (
        outer.groupby(["candidate", "family", "task_type"], dropna=False)
        .agg(
            n_outer_units=("outer_utility", "size"),
            n_tasks=("task", "nunique"),
            outer_utility_mean=("outer_utility", "mean"),
            outer_utility_median=("outer_utility", "median"),
            inner_mean_mean=("inner_mean", "mean"),
            fit_seconds_median=("fit_seconds", "median"),
            roc_auc_mean=("roc_auc", "mean"),
            pr_auc_mean=("pr_auc", "mean"),
            rmse_mean=("rmse", "mean"),
        )
        .reset_index()
    )
    summary.to_csv(OUT / "strong_baseline_summary.csv", index=False)
    return {
        "strong_registry_rows": int(len(registry)),
        "strong_inner_rows": int(len(inner)),
        "strong_outer_rows": int(len(outer)),
        "strong_prediction_rows": int(len(preds)),
        "strong_completed_candidates": sorted(outer["candidate"].unique().tolist()),
        "tabpfn_status": str(status_rows[0]["status"]),
    }


def compute_error_overlap() -> dict[str, object]:
    preds = pd.read_csv(OUT / "strong_baseline_outer_predictions.csv")
    rows = []
    unit_cols = ["task", "task_type", "seed", "outer_fold"]
    for unit, group in preds.groupby(unit_cols, sort=True):
        task, task_type, seed, outer_fold = unit
        if task_type == "classification":
            group = group.assign(error_flag=(group["y_pred"] >= 0.5).astype(int) != group["y_true"].astype(int))
        else:
            abs_err = (group["y_pred"] - group["y_true"]).abs()
            threshold = float(abs_err.quantile(0.75))
            group = group.assign(error_flag=abs_err >= threshold)
        pivot = group.pivot_table(index="sample_index", columns="candidate", values="error_flag", aggfunc="max").fillna(False).astype(bool)
        candidates = list(pivot.columns)
        for i, a in enumerate(candidates):
            for b in candidates[i + 1 :]:
                aa = pivot[a].to_numpy(bool)
                bb = pivot[b].to_numpy(bool)
                union = np.logical_or(aa, bb).sum()
                inter = np.logical_and(aa, bb).sum()
                rows.append(
                    {
                        "task": task,
                        "task_type": task_type,
                        "seed": seed,
                        "outer_fold": outer_fold,
                        "candidate_a": a,
                        "candidate_b": b,
                        "n_samples": len(pivot),
                        "errors_a": int(aa.sum()),
                        "errors_b": int(bb.sum()),
                        "error_intersection": int(inter),
                        "error_union": int(union),
                        "jaccard_error_overlap": float(inter / union) if union else np.nan,
                    }
                )
    detail = pd.DataFrame(rows)
    detail.to_csv(OUT / "error_overlap_pairwise_detail.csv", index=False)
    summary = (
        detail.groupby(["candidate_a", "candidate_b"], dropna=False)
        .agg(
            n_units=("jaccard_error_overlap", "size"),
            mean_jaccard_error_overlap=("jaccard_error_overlap", "mean"),
            median_jaccard_error_overlap=("jaccard_error_overlap", "median"),
        )
        .reset_index()
    )
    summary.to_csv(OUT / "error_overlap_pairwise_summary.csv", index=False)
    return {
        "error_overlap_pairs": int(len(detail)),
        "error_overlap_candidate_pairs": int(len(summary)),
        "error_overlap_mean": float(detail["jaccard_error_overlap"].mean()),
    }


def duplicate_policy_frame(task: str, policy: str) -> tuple[pd.DataFrame, str]:
    raw, task_type = load_task_raw(task)
    if policy == "global_dedup":
        frame = global_deduplicate(raw, task_type)
    elif policy == "keep_duplicates_grouped":
        frame = keep_duplicates_grouped(raw, task_type)
    elif policy == "train_fold_only_aggregate":
        frame = keep_duplicates_grouped(raw, task_type)
    else:
        raise ValueError(policy)
    return frame, task_type


def aggregate_train_fold(frame: pd.DataFrame, train_idx: np.ndarray, task_type: str) -> pd.DataFrame:
    train = frame.iloc[train_idx].copy()
    if task_type == "regression":
        return train.groupby("smiles", as_index=False)["y"].mean()
    rows = []
    for smi, group in train.groupby("smiles", sort=False):
        values = group["y"].unique().tolist()
        if len(values) == 1:
            rows.append({"smiles": smi, "y": int(values[0])})
    return pd.DataFrame(rows)


def duplicate_sensitivity(args: argparse.Namespace) -> dict[str, object]:
    policies = ["global_dedup", "train_fold_only_aggregate", "keep_duplicates_grouped"]
    detail_rows = []
    for task in args.tasks:
        for policy in policies:
            frame, task_type = duplicate_policy_frame(task, policy)
            reps, groups, y, filtered = featurize_frame(frame)
            for seed in args.seeds:
                outer_splits, split_type = make_splits(y, groups, task_type, args.outer_folds, seed)
                for outer_fold, (outer_train, outer_test) in enumerate(outer_splits, start=1):
                    if policy == "train_fold_only_aggregate":
                        train_frame = aggregate_train_fold(filtered, outer_train, task_type)
                        train_reps, _, train_y, train_filtered = featurize_frame(train_frame)
                        x_train = train_reps["morgan512"]
                        y_train = train_y
                        x_test = reps["morgan512"][outer_test]
                    else:
                        x_train = reps["morgan512"][outer_train]
                        y_train = y[outer_train]
                        x_test = reps["morgan512"][outer_test]
                    model = make_tabular_model(task_type, "rf", seed)
                    pred = predict_tabular(task_type, model, x_train, y_train, x_test)
                    utility = metric_utility(task_type, y[outer_test], pred)
                    detail_rows.append(
                        {
                            "task": task,
                            "task_type": task_type,
                            "policy": policy,
                            "seed": seed,
                            "outer_fold": outer_fold,
                            "split_type": split_type,
                            "n_total_after_policy": len(filtered),
                            "n_train": len(y_train),
                            "n_test": len(outer_test),
                            "outer_utility": utility,
                            **compute_metric_columns(task_type, y[outer_test], pred),
                        }
                    )
                print(f"duplicate {task} policy={policy} seed={seed}", flush=True)
    detail = pd.DataFrame(detail_rows)
    detail.to_csv(OUT / "duplicate_sensitivity_detail.csv", index=False)
    summary = (
        detail.groupby(["task", "task_type", "policy"], dropna=False)
        .agg(
            n_outer_units=("outer_utility", "size"),
            n_total_after_policy=("n_total_after_policy", "median"),
            outer_utility_mean=("outer_utility", "mean"),
            outer_utility_sd=("outer_utility", "std"),
            roc_auc_mean=("roc_auc", "mean"),
            rmse_mean=("rmse", "mean"),
        )
        .reset_index()
    )
    base = summary[summary["policy"].eq("global_dedup")][["task", "outer_utility_mean"]].rename(columns={"outer_utility_mean": "global_dedup_outer_utility_mean"})
    summary = summary.merge(base, on="task", how="left")
    summary["delta_vs_global_dedup"] = summary["outer_utility_mean"] - summary["global_dedup_outer_utility_mean"]
    summary.to_csv(OUT / "duplicate_sensitivity_summary.csv", index=False)
    return {
        "duplicate_sensitivity_rows": int(len(detail)),
        "duplicate_policies": policies,
        "duplicate_max_abs_delta_vs_global": float(summary["delta_vs_global_dedup"].abs().max()),
    }


def main() -> None:
    args = parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    audit = {
        "tasks": args.tasks,
        "seeds": args.seeds,
        "outer_folds": args.outer_folds,
        "inner_folds": args.inner_folds,
        "scope": "Representative strict 3x3x5 panel: one regression endpoint, one standard classification endpoint, and one imbalanced toxicity endpoint.",
    }
    audit.update(strong_baseline_panel(args))
    audit.update(compute_error_overlap())
    audit.update(duplicate_sensitivity(args))
    required = [
        "strong_baseline_registry.csv",
        "strong_baseline_inner_scores.csv",
        "strong_baseline_outer_scores.csv",
        "strong_baseline_outer_predictions.csv",
        "strong_baseline_summary.csv",
        "strong_baseline_runtime_status.csv",
        "error_overlap_pairwise_detail.csv",
        "error_overlap_pairwise_summary.csv",
        "duplicate_sensitivity_detail.csv",
        "duplicate_sensitivity_summary.csv",
    ]
    missing = [name for name in required if not (OUT / name).exists()]
    audit["required_outputs_missing"] = missing
    audit["passed"] = not missing and audit["strong_prediction_rows"] > 0 and audit["error_overlap_pairs"] > 0
    (OUT / "paper12_strict_gap_experiments_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    if not audit["passed"]:
        raise SystemExit(json.dumps(audit, ensure_ascii=False, indent=2))
    print(OUT)


if __name__ == "__main__":
    main()
