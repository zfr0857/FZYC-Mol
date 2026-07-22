from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, roc_auc_score, average_precision_score
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import load_dataset
from fzyc_mol.evaluate import compute_metrics
from fzyc_mol.splits import make_split


OUT = ROOT / "reports" / "pretrained_lightweight_adapter_20260611"
OUT.mkdir(parents=True, exist_ok=True)

DATASETS = ["esol", "freesolv", "lipo", "bbbp", "bace", "clintox"]
ENCODERS = ["DeepChem/ChemBERTa-77M-MTR", "ibm/MoLFormer-XL-both-10pct"]
SEEDS = [13, 17, 23]


def safe_id(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_")


def load_embeddings(encoder: str, dataset: str, smiles: list[str]) -> np.ndarray:
    path = ROOT / "data" / "processed" / "pretrained_embeddings" / safe_id(encoder) / f"{dataset}.npz"
    if not path.exists():
        raise FileNotFoundError(path)
    payload = np.load(path, allow_pickle=True)
    saved = [str(item) for item in payload["smiles"].tolist()]
    emb = payload["embedding"].astype(np.float32)
    lookup = {smi: emb[i] for i, smi in enumerate(saved)}
    missing = [smi for smi in smiles if smi not in lookup]
    if missing:
        raise KeyError(f"{path} missing {len(missing)} smiles")
    return np.vstack([lookup[smi] for smi in smiles]).astype(np.float32)


def make_model(task_type: str, model_type: str, seed: int):
    if task_type == "regression":
        if model_type == "linear_probe":
            return Pipeline([("scale", StandardScaler()), ("model", RidgeCV(alphas=np.logspace(-4, 4, 17)))])
        return Pipeline(
            [
                ("scale", StandardScaler()),
                (
                    "model",
                    MLPRegressor(
                        hidden_layer_sizes=(128,),
                        activation="relu",
                        alpha=1e-3,
                        learning_rate_init=1e-3,
                        max_iter=240,
                        early_stopping=True,
                        random_state=seed,
                    ),
                ),
            ]
        )
    if model_type == "linear_probe":
        return Pipeline(
            [
                ("scale", StandardScaler()),
                ("model", LogisticRegression(max_iter=2500, class_weight="balanced", random_state=seed)),
            ]
        )
    return Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "model",
                MLPClassifier(
                    hidden_layer_sizes=(128,),
                    activation="relu",
                    alpha=1e-3,
                    learning_rate_init=1e-3,
                    max_iter=240,
                    early_stopping=True,
                    random_state=seed,
                ),
            ),
        ]
    )


def predict(task_type: str, model, x: np.ndarray) -> np.ndarray:
    if task_type == "classification":
        return model.predict_proba(x)[:, 1]
    return model.predict(x)


def primary(task_type: str, metrics: dict[str, float]) -> tuple[str, float, str]:
    if task_type == "regression":
        return "rmse", float(metrics["rmse"]), "lower"
    return "roc_auc", float(metrics["roc_auc"]), "higher"


def positive_delta(direction: str, reference: float, value: float) -> float:
    return reference - value if direction == "lower" else value - reference


def run_one(dataset: str, encoder: str, seed: int) -> tuple[list[dict], list[pd.DataFrame]]:
    frame, spec = load_dataset(dataset, data_dir=ROOT / "data")
    x = load_embeddings(encoder, dataset, frame["smiles"].tolist())
    y = frame["y"].to_numpy()
    split = make_split(frame, "scaffold", seed)
    rows = []
    pred_frames = []
    for model_type in ["linear_probe", "mlp_adapter"]:
        model = make_model(spec.task_type, model_type, seed)
        model.fit(x[split.train], y[split.train])
        valid_pred = predict(spec.task_type, model, x[split.valid])
        test_pred = predict(spec.task_type, model, x[split.test])
        valid_metrics = compute_metrics(spec.task_type, y[split.valid], valid_pred)
        test_metrics = compute_metrics(spec.task_type, y[split.test], test_pred)
        metric, valid_primary, direction = primary(spec.task_type, valid_metrics)
        _, test_primary, _ = primary(spec.task_type, test_metrics)
        model_id = f"{safe_id(encoder)}_{model_type}"
        rows.append(
            {
                "dataset": dataset,
                "task_type": spec.task_type,
                "encoder": safe_id(encoder),
                "model": model_id,
                "adapter_type": model_type,
                "seed": seed,
                "split": "scaffold",
                "primary_metric": metric,
                "primary_direction": direction,
                "valid_primary": valid_primary,
                "test_primary": test_primary,
                **{f"valid_{k}": v for k, v in valid_metrics.items()},
                **{f"test_{k}": v for k, v in test_metrics.items()},
            }
        )
        pred_frames.append(
            pd.DataFrame(
                {
                    "dataset": dataset,
                    "encoder": safe_id(encoder),
                    "model": model_id,
                    "seed": seed,
                    "smiles": frame.iloc[split.test]["smiles"].to_numpy(),
                    "y_true": y[split.test],
                    "y_pred": test_pred,
                }
            )
        )
    return rows, pred_frames


def summarize(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    selected_rows = []
    for (dataset, encoder, seed), group in raw.groupby(["dataset", "encoder", "seed"], dropna=False):
        direction = str(group["primary_direction"].iloc[0])
        ascending = direction == "lower"
        best = group.sort_values("valid_primary", ascending=ascending).iloc[0].to_dict()
        linear = group[group["adapter_type"].eq("linear_probe")].iloc[0]
        best["delta_vs_linear_test_positive"] = positive_delta(direction, float(linear["test_primary"]), float(best["test_primary"]))
        selected_rows.append(best)
    selected = pd.DataFrame(selected_rows)
    metric_cols = [
        col
        for col in raw.columns
        if col.startswith("valid_") or col.startswith("test_") or col in {"valid_primary", "test_primary"}
    ]
    summary = (
        selected.groupby(["dataset", "task_type", "encoder", "adapter_type", "model", "primary_metric", "primary_direction"], dropna=False)[
            metric_cols + ["delta_vs_linear_test_positive"]
        ]
        .agg(["mean", "std"])
        .reset_index()
    )
    return selected, summary


def main() -> None:
    rows = []
    pred_frames = []
    for dataset in DATASETS:
        for encoder in ENCODERS:
            for seed in SEEDS:
                print(f"run dataset={dataset} encoder={encoder} seed={seed}", flush=True)
                part, preds = run_one(dataset, encoder, seed)
                rows.extend(part)
                pred_frames.extend(preds)
    raw = pd.DataFrame(rows)
    selected, summary = summarize(raw)
    raw.to_csv(OUT / "adapter_candidate_metrics_raw.csv", index=False)
    selected.to_csv(OUT / "adapter_validation_selected.csv", index=False)
    summary.to_csv(OUT / "adapter_selected_summary.csv", index=False)
    pd.concat(pred_frames, ignore_index=True).to_csv(OUT / "adapter_test_predictions.csv", index=False)
    manifest = {
        "datasets": DATASETS,
        "encoders": ENCODERS,
        "seeds": SEEDS,
        "selection_rule": "within each dataset/encoder/seed, select linear_probe or mlp_adapter by validation primary metric only",
        "outputs": [
            "adapter_candidate_metrics_raw.csv",
            "adapter_validation_selected.csv",
            "adapter_selected_summary.csv",
            "adapter_test_predictions.csv",
        ],
    }
    (OUT / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (OUT / "README.md").write_text(
        "# Lightweight pretrained adapter audit\n\n"
        "This controlled supplement compares frozen-embedding linear probes against one-hidden-layer MLP adapters. "
        "It does not fine-tune the molecular encoder. Selection uses validation-set primary metrics only.\n",
        encoding="utf-8",
    )
    print(f"Wrote lightweight adapter outputs to {OUT}", flush=True)
    print(selected[["dataset", "encoder", "seed", "adapter_type", "test_primary", "delta_vs_linear_test_positive"]].to_string(index=False))


if __name__ == "__main__":
    main()
