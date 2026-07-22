from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import DATASETS
from fzyc_mol.evaluate import compute_metrics


ENSEMBLES = {
    "consensus_core": [
        ("reports/full_moleculenet", "rf_morgan"),
        ("reports/full_moleculenet", "gin"),
        ("reports/full_moleculenet", "fzyc_mol_static"),
    ],
    "consensus_ai": [
        ("reports/full_moleculenet", "gin"),
        ("reports/full_moleculenet", "fzyc_mol_static"),
        ("reports/upgrade_graph_transformer", "fzyc_mol_gt"),
    ],
    "consensus_all": [
        ("reports/full_moleculenet", "rf_morgan"),
        ("reports/full_moleculenet", "gin"),
        ("reports/full_moleculenet", "fzyc_mol_static"),
        ("reports/upgrade_graph_transformer", "fzyc_mol_gt"),
    ],
}


def _as_probability(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    if values.min() >= 0.0 and values.max() <= 1.0:
        return values
    values = np.clip(values, -60.0, 60.0)
    return 1.0 / (1.0 + np.exp(-values))


def load_prediction(report_dir: Path, dataset: str, model: str, seed: int) -> pd.DataFrame:
    path = report_dir / f"{dataset}_{model}_seed{seed}_predictions.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path)
    return frame[["smiles", "y_true", "y_pred"]].copy()


def build_one(dataset: str, seed: int, members: list[tuple[str, str]], task_type: str) -> pd.DataFrame:
    merged: pd.DataFrame | None = None
    pred_cols: list[str] = []
    for report_dir, model in members:
        frame = load_prediction(ROOT / report_dir, dataset, model, seed)
        col = f"pred_{model}"
        frame = frame.rename(columns={"y_pred": col})
        pred_cols.append(col)
        if merged is None:
            merged = frame
        else:
            merged = merged.merge(frame[["smiles", col]], on="smiles", how="inner")
    if merged is None:
        raise ValueError("No ensemble members provided.")
    preds = [merged[col].to_numpy() for col in pred_cols]
    if task_type == "classification":
        preds = [_as_probability(pred) for pred in preds]
    merged["y_pred"] = np.vstack(preds).mean(axis=0)
    return merged[["smiles", "y_true", "y_pred"]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build fixed consensus ensembles from saved predictions.")
    parser.add_argument("--output-dir", default=str(ROOT / "reports" / "consensus"))
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for dataset, spec in DATASETS.items():
        for seed in [13, 17, 23, 29, 31]:
            for ensemble_name, members in ENSEMBLES.items():
                try:
                    pred = build_one(dataset, seed, members, spec.task_type)
                except FileNotFoundError:
                    continue
                pred_path = output_dir / f"{dataset}_{ensemble_name}_seed{seed}_predictions.csv"
                pred.to_csv(pred_path, index=False)
                metrics = compute_metrics(spec.task_type, pred["y_true"].to_numpy(), pred["y_pred"].to_numpy())
                rows.append(
                    {
                        "dataset": dataset,
                        "model": ensemble_name,
                        "seed": seed,
                        "split": "scaffold",
                        "task_type": spec.task_type,
                        **metrics,
                    }
                )
    metrics = pd.DataFrame(rows)
    metrics.to_csv(output_dir / "metrics_raw.csv", index=False)
    id_cols = {"dataset", "model", "task_type", "seed", "split"}
    metric_cols = [
        col for col in metrics.columns if col not in id_cols and pd.api.types.is_numeric_dtype(metrics[col])
    ]
    summary = (
        metrics.groupby(["dataset", "model", "task_type"], dropna=False)[metric_cols]
        .agg(["mean", "std"])
        .reset_index()
    )
    summary.to_csv(output_dir / "metrics_summary.csv", index=False)
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
