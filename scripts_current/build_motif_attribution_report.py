from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from rdkit.Chem import BRICS, Fragments
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import load_dataset
from fzyc_mol.evaluate import compute_metrics
from fzyc_mol.features import mol_from_smiles, scaffold_from_smiles
from fzyc_mol.splits import make_split


FRAGMENT_FUNCS = [
    (name, getattr(Fragments, name))
    for name in dir(Fragments)
    if name.startswith("fr_") and callable(getattr(Fragments, name))
]


def brics_tokens(smiles: str) -> list[str]:
    mol = mol_from_smiles(smiles)
    if mol is None:
        return []
    try:
        return sorted(BRICS.BRICSDecompose(mol))
    except Exception:
        return []


def build_vocab(train_smiles: list[str], top_brics: int, top_scaffolds: int) -> tuple[list[str], list[str]]:
    brics = Counter()
    scaffolds = Counter()
    for smiles in train_smiles:
        brics.update(brics_tokens(smiles))
        scaffolds.update([scaffold_from_smiles(smiles)])
    brics_vocab = [token for token, _count in brics.most_common(top_brics)]
    scaffold_vocab = [token for token, _count in scaffolds.most_common(top_scaffolds) if token]
    return brics_vocab, scaffold_vocab


def named_motif_matrix(smiles_list: list[str], brics_vocab: list[str], scaffold_vocab: list[str]) -> tuple[np.ndarray, list[str]]:
    names = [f"BRICS::{token}" for token in brics_vocab]
    names += [f"Murcko::{token}" for token in scaffold_vocab]
    names += [f"FG::{name}" for name, _fn in FRAGMENT_FUNCS]
    rows = []
    brics_set = [set([token]) for token in brics_vocab]
    for smiles in smiles_list:
        mol = mol_from_smiles(smiles)
        tokens = Counter(brics_tokens(smiles))
        scaffold = scaffold_from_smiles(smiles)
        values = [float(tokens.get(token, 0)) for token in brics_vocab]
        values += [float(scaffold == token) for token in scaffold_vocab]
        for _name, fn in FRAGMENT_FUNCS:
            if mol is None:
                values.append(0.0)
            else:
                try:
                    value = float(fn(mol))
                except Exception:
                    value = 0.0
                values.append(value if np.isfinite(value) else 0.0)
        rows.append(values)
    return np.asarray(rows, dtype=np.float32), names


def fit_model(task_type: str, seed: int):
    if task_type == "classification":
        model = ExtraTreesClassifier(
            n_estimators=600,
            max_features="sqrt",
            class_weight="balanced",
            random_state=seed,
            n_jobs=-1,
        )
    else:
        model = ExtraTreesRegressor(
            n_estimators=600,
            max_features="sqrt",
            random_state=seed,
            n_jobs=-1,
        )
    return Pipeline([("imputer", SimpleImputer(strategy="median")), ("model", model)])


def predict(model, x: np.ndarray, task_type: str) -> np.ndarray:
    if task_type == "classification":
        return model.predict_proba(x)[:, 1]
    return model.predict(x)


def feature_direction(x: np.ndarray, y: np.ndarray, task_type: str) -> np.ndarray:
    directions = []
    for col in range(x.shape[1]):
        values = x[:, col]
        if np.all(values == values[0]):
            directions.append(0.0)
            continue
        if task_type == "classification":
            pos = values[y.astype(int) == 1]
            neg = values[y.astype(int) == 0]
            directions.append(float(np.nanmean(pos) - np.nanmean(neg)) if len(pos) and len(neg) else 0.0)
        else:
            corr = np.corrcoef(values, y)[0, 1]
            directions.append(float(corr) if np.isfinite(corr) else 0.0)
    return np.asarray(directions, dtype=float)


def parse_selector_path(path: Path) -> tuple[str, int] | None:
    match = re.match(r"(.+)_validation_selector_seed(\d+)_predictions\.csv$", path.name)
    if not match:
        return None
    return match.group(1), int(match.group(2))


def scaffold_performance(dataset: str, seed: int, selector_dir: Path, min_n: int) -> pd.DataFrame:
    path = selector_dir / f"{dataset}_validation_selector_seed{seed}_predictions.csv"
    if not path.exists():
        return pd.DataFrame()
    pred = pd.read_csv(path)
    pred["scaffold"] = pred["smiles"].map(scaffold_from_smiles)
    rows = []
    task_type = "classification" if set(np.unique(pred["y_true"])).issubset({0, 1}) else "regression"
    for scaffold, group in pred.groupby("scaffold"):
        if len(group) < min_n:
            continue
        metrics = compute_metrics(task_type, group["y_true"].to_numpy(), group["y_pred"].to_numpy())
        rows.append({"dataset": dataset, "seed": seed, "scaffold": scaffold, "n": len(group), "task_type": task_type, **metrics})
    return pd.DataFrame(rows)


def run_dataset(dataset: str, seeds: list[int], selector_dir: Path, output_dir: Path, top_brics: int, top_scaffolds: int, min_scaffold_n: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    frame, spec = load_dataset(dataset, data_dir=ROOT / "data")
    importance_rows = []
    metric_rows = []
    scaffold_rows = []
    for seed in seeds:
        split = make_split(frame, "scaffold", seed)
        train_smiles = frame.iloc[split.train]["smiles"].tolist()
        brics_vocab, scaffold_vocab = build_vocab(train_smiles, top_brics, top_scaffolds)
        x, names = named_motif_matrix(frame["smiles"].tolist(), brics_vocab, scaffold_vocab)
        y = frame["y"].to_numpy()
        model = fit_model(spec.task_type, seed)
        model.fit(x[split.train], y[split.train])
        pred = predict(model, x[split.test], spec.task_type)
        metrics = compute_metrics(spec.task_type, y[split.test], pred)
        metric_rows.append({"dataset": dataset, "seed": seed, "model": "named_motif_extratrees", "task_type": spec.task_type, **metrics})
        importances = model[-1].feature_importances_
        directions = feature_direction(x[split.train], y[split.train], spec.task_type)
        top_idx = np.argsort(-importances)[:50]
        for rank, idx in enumerate(top_idx, start=1):
            name = names[idx]
            importance_rows.append(
                {
                    "dataset": dataset,
                    "seed": seed,
                    "rank": rank,
                    "feature": name,
                    "feature_family": name.split("::", 1)[0],
                    "importance": float(importances[idx]),
                    "direction": float(directions[idx]),
                }
            )
        scaf = scaffold_performance(dataset, seed, selector_dir, min_scaffold_n)
        if not scaf.empty:
            scaffold_rows.append(scaf)
    return pd.DataFrame(importance_rows), pd.DataFrame(metric_rows), pd.concat(scaffold_rows, ignore_index=True) if scaffold_rows else pd.DataFrame()


def plot_importance(importance: pd.DataFrame, output_dir: Path) -> None:
    fig_dir = output_dir / "figures"
    fig_dir.mkdir(exist_ok=True)
    if importance.empty:
        return
    for dataset, group in importance.groupby("dataset"):
        agg = group.groupby("feature", as_index=False)["importance"].mean().sort_values("importance", ascending=False).head(15)
        plt.figure(figsize=(7.0, 4.8))
        plt.barh(agg["feature"][::-1], agg["importance"][::-1])
        plt.xlabel("Mean feature importance")
        plt.title(f"{dataset} motif attribution")
        plt.tight_layout()
        plt.savefig(fig_dir / f"{dataset}_motif_importance.png", dpi=220)
        plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build BRICS/Murcko/functional-group attribution reports.")
    parser.add_argument("--datasets", nargs="*", default=["bbbp", "bace", "clintox"])
    parser.add_argument("--seeds", nargs="*", type=int, default=[13, 17, 23, 29, 31])
    parser.add_argument("--selector-dir", default=str(ROOT / "reports" / "validation_selector_plus_descriptor_motif"))
    parser.add_argument("--output-dir", default=str(ROOT / "reports" / "motif_attribution"))
    parser.add_argument("--top-brics", type=int, default=128)
    parser.add_argument("--top-scaffolds", type=int, default=64)
    parser.add_argument("--min-scaffold-n", type=int, default=5)
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    importances = []
    metrics = []
    scaffolds = []
    for dataset in args.datasets:
        print(f"start dataset={dataset}", flush=True)
        imp, met, scaf = run_dataset(
            dataset,
            args.seeds,
            Path(args.selector_dir),
            output_dir,
            args.top_brics,
            args.top_scaffolds,
            args.min_scaffold_n,
        )
        importances.append(imp)
        metrics.append(met)
        scaffolds.append(scaf)
    importance = pd.concat(importances, ignore_index=True) if importances else pd.DataFrame()
    metric = pd.concat(metrics, ignore_index=True) if metrics else pd.DataFrame()
    scaffold = pd.concat(scaffolds, ignore_index=True) if scaffolds else pd.DataFrame()
    importance.to_csv(output_dir / "motif_feature_importance.csv", index=False)
    metric.to_csv(output_dir / "named_motif_model_metrics.csv", index=False)
    scaffold.to_csv(output_dir / "scaffold_level_performance.csv", index=False)
    if not metric.empty:
        metric_cols = [c for c in metric.columns if c not in {"dataset", "seed", "model", "task_type"} and pd.api.types.is_numeric_dtype(metric[c])]
        metric.groupby(["dataset", "model", "task_type"], dropna=False)[metric_cols].agg(["mean", "std"]).reset_index().to_csv(
            output_dir / "named_motif_model_summary.csv",
            index=False,
        )
    plot_importance(importance, output_dir)
    print(importance.head(60).to_string(index=False) if not importance.empty else "No importance rows.")


if __name__ == "__main__":
    main()
