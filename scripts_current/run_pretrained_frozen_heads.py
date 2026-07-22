from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from rdkit import RDLogger
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import DATASETS, load_dataset
from fzyc_mol.evaluate import compute_metrics
from fzyc_mol.features import descriptor_vector, morgan_fingerprint
from fzyc_mol.splits import make_split


RDLogger.DisableLog("rdApp.*")


def safe_model_id(model_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", model_name).strip("_")


def load_embedding_matrix(path: Path, smiles: list[str]) -> np.ndarray:
    if not path.exists():
        raise FileNotFoundError(path)
    payload = np.load(path, allow_pickle=True)
    saved_smiles = [str(item) for item in payload["smiles"].tolist()]
    embedding = payload["embedding"].astype(np.float32)
    lookup = {smi: embedding[i] for i, smi in enumerate(saved_smiles)}
    missing = [smi for smi in smiles if smi not in lookup]
    if missing:
        raise KeyError(f"Missing {len(missing)} embeddings in {path}. Example: {missing[:3]}")
    return np.vstack([lookup[smi] for smi in smiles]).astype(np.float32)


def rdkit_matrix(dataset: str, smiles: list[str]) -> np.ndarray:
    cache_path = ROOT / "data" / "processed" / f"{dataset}_all_graphs.pt"
    if cache_path.exists():
        graphs = torch.load(cache_path, weights_only=False)
        if len(graphs) == len(smiles) and all(getattr(graph, "smiles", None) == smi for graph, smi in zip(graphs, smiles)):
            fps = np.vstack([graph.fp.view(-1).numpy() for graph in graphs])
            desc = np.vstack([graph.desc.view(-1).numpy() for graph in graphs])
            return np.hstack([fps, desc]).astype(np.float32)
    fps = np.vstack([morgan_fingerprint(smi) for smi in smiles])
    desc = np.vstack([descriptor_vector(smi) for smi in smiles])
    return np.hstack([fps, desc]).astype(np.float32)


def fit_head(task_type: str, x_train: np.ndarray, y_train: np.ndarray):
    if task_type == "regression":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                ("model", RidgeCV(alphas=np.logspace(-4, 4, 17))),
            ]
        ).fit(x_train, y_train)
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced",
                    random_state=61453,
                ),
            ),
        ]
    ).fit(x_train, y_train.astype(int))


def predict_head(task_type: str, model, x: np.ndarray) -> np.ndarray:
    if task_type == "classification":
        return model.predict_proba(x)[:, 1]
    return model.predict(x)


def summarize(metrics: pd.DataFrame, output_dir: Path) -> None:
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Train frozen heads on pretrained molecular embeddings.")
    parser.add_argument("--model-name", default="DeepChem/ChemBERTa-77M-MTR")
    parser.add_argument("--embedding-root", default=str(ROOT / "data" / "processed" / "pretrained_embeddings"))
    parser.add_argument("--datasets", nargs="*", default=list(DATASETS))
    parser.add_argument("--seeds", nargs="*", type=int, default=[13, 17, 23, 29, 31])
    parser.add_argument("--output-dir", default=str(ROOT / "reports" / "pretrained_frozen"))
    parser.add_argument("--include-rdkit", action="store_true")
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    encoder_id = safe_model_id(args.model_name)
    embedding_dir = Path(args.embedding_root) / encoder_id
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    model_name = f"{encoder_id}_rdkit_head" if args.include_rdkit else f"{encoder_id}_frozen_head"

    for dataset in args.datasets:
        frame, spec = load_dataset(dataset, data_dir=ROOT / "data")
        smiles = frame["smiles"].tolist()
        expected_paths = [
            (
                output_dir / f"{dataset}_{model_name}_seed{seed}_predictions.csv",
                output_dir / f"{dataset}_{model_name}_seed{seed}_valid_predictions.csv",
            )
            for seed in args.seeds
        ]
        if args.resume and expected_paths and all(pred.exists() and valid.exists() for pred, valid in expected_paths):
            for seed, (pred_path, _valid_path) in zip(args.seeds, expected_paths):
                pred_frame = pd.read_csv(pred_path)
                rows.append(
                    {
                        "dataset": dataset,
                        "model": model_name,
                        "seed": seed,
                        "split": "scaffold",
                        "task_type": spec.task_type,
                        **compute_metrics(
                            spec.task_type,
                            pred_frame["y_true"].to_numpy(),
                            pred_frame["y_pred"].to_numpy(),
                        ),
                    }
                )
            continue
        x = load_embedding_matrix(embedding_dir / f"{dataset}.npz", smiles)
        if args.include_rdkit:
            x = np.hstack([x, rdkit_matrix(dataset, smiles)]).astype(np.float32)
        y = frame["y"].to_numpy()
        for seed in args.seeds:
            pred_path = output_dir / f"{dataset}_{model_name}_seed{seed}_predictions.csv"
            valid_path = output_dir / f"{dataset}_{model_name}_seed{seed}_valid_predictions.csv"
            if args.resume and pred_path.exists() and valid_path.exists():
                pred_frame = pd.read_csv(pred_path)
                rows.append(
                    {
                        "dataset": dataset,
                        "model": model_name,
                        "seed": seed,
                        "split": "scaffold",
                        "task_type": spec.task_type,
                        **compute_metrics(
                            spec.task_type,
                            pred_frame["y_true"].to_numpy(),
                            pred_frame["y_pred"].to_numpy(),
                        ),
                    }
                )
                continue
            split = make_split(frame, "scaffold", seed)
            head = fit_head(spec.task_type, x[split.train], y[split.train])
            valid_pred = predict_head(spec.task_type, head, x[split.valid])
            test_pred = predict_head(spec.task_type, head, x[split.test])
            valid_frame = pd.DataFrame(
                {
                    "smiles": frame.iloc[split.valid]["smiles"].to_numpy(),
                    "y_true": y[split.valid],
                    "y_pred": valid_pred,
                }
            )
            valid_frame.to_csv(valid_path, index=False)
            pred_frame = pd.DataFrame(
                {
                    "smiles": frame.iloc[split.test]["smiles"].to_numpy(),
                    "y_true": y[split.test],
                    "y_pred": test_pred,
                }
            )
            pred_frame.to_csv(pred_path, index=False)
            rows.append(
                {
                    "dataset": dataset,
                    "model": model_name,
                    "seed": seed,
                    "split": "scaffold",
                    "task_type": spec.task_type,
                    **compute_metrics(spec.task_type, y[split.test], test_pred),
                }
            )

    metrics = pd.DataFrame(rows)
    summarize(metrics, output_dir)
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
