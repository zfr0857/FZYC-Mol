from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from rdkit import DataStructs

from .datasets import DATASETS, load_dataset
from .features import morgan_fingerprint
from .splits import make_split


def _parse_report_name(filename: str, suffix: str) -> tuple[str, str, int] | None:
    for dataset in sorted(DATASETS, key=len, reverse=True):
        prefix = f"{dataset}_"
        if not filename.startswith(prefix) or not filename.endswith(suffix):
            continue
        middle = filename[len(prefix) : -len(suffix)]
        model, sep, seed_text = middle.rpartition("_seed")
        if sep and seed_text.isdigit():
            return dataset, model, int(seed_text)
    return None


def _bitvect_from_array(arr: np.ndarray):
    bitvect = DataStructs.ExplicitBitVect(arr.shape[0])
    on_bits = np.flatnonzero(arr > 0)
    for bit in on_bits:
        bitvect.SetBit(int(bit))
    return bitvect


def max_train_similarity(train_smiles: list[str], test_smiles: list[str]) -> np.ndarray:
    train_fps = [_bitvect_from_array(morgan_fingerprint(smiles)) for smiles in train_smiles]
    sims: list[float] = []
    for smiles in test_smiles:
        fp = _bitvect_from_array(morgan_fingerprint(smiles))
        sim = max(DataStructs.BulkTanimotoSimilarity(fp, train_fps)) if train_fps else 0.0
        sims.append(float(sim))
    return np.asarray(sims, dtype=np.float32)


def applicability_domain_table(
    predictions: pd.DataFrame,
    train_smiles: list[str],
    dataset: str,
    model: str,
    seed: int,
    bins: tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
) -> pd.DataFrame:
    if "smiles" not in predictions.columns:
        raise ValueError("Prediction file must contain a 'smiles' column.")
    frame = predictions.copy()
    frame["max_train_tanimoto"] = max_train_similarity(train_smiles, frame["smiles"].tolist())
    frame["abs_error"] = (frame["y_true"] - frame["y_pred"]).abs()
    frame["similarity_bin"] = pd.cut(
        frame["max_train_tanimoto"],
        bins=bins,
        include_lowest=True,
        right=True,
    )
    grouped = (
        frame.groupby("similarity_bin", observed=True)
        .agg(
            n=("abs_error", "size"),
            mean_abs_error=("abs_error", "mean"),
            median_abs_error=("abs_error", "median"),
            mean_similarity=("max_train_tanimoto", "mean"),
        )
        .reset_index()
    )
    grouped.insert(0, "dataset", dataset)
    grouped.insert(1, "model", model)
    grouped.insert(2, "seed", seed)
    grouped["similarity_bin"] = grouped["similarity_bin"].astype(str)
    return grouped


def gate_summary_table(gates: pd.DataFrame, dataset: str, model: str, seed: int) -> pd.DataFrame:
    columns = [column for column in gates.columns if column.startswith("gate_")]
    row = {"dataset": dataset, "model": model, "seed": seed}
    for column in columns:
        row[f"{column}_mean"] = float(gates[column].mean())
        row[f"{column}_std"] = float(gates[column].std(ddof=0))
    return pd.DataFrame([row])


def analyze_report_dir(
    report_dir: str | Path,
    data_dir: str | Path = "data",
    split_name: str = "scaffold",
    max_rows: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    report_dir = Path(report_dir)
    applicability: list[pd.DataFrame] = []
    gates: list[pd.DataFrame] = []

    for path in report_dir.glob("*_predictions.csv"):
        parsed = _parse_report_name(path.name, "_predictions.csv")
        if parsed is None:
            continue
        dataset, model, seed = parsed
        frame, _spec = load_dataset(dataset, data_dir=data_dir, max_rows=max_rows)
        split = make_split(frame, split_name, seed)
        train_smiles = frame.iloc[split.train]["smiles"].tolist()
        predictions = pd.read_csv(path)
        if "smiles" in predictions.columns:
            applicability.append(
                applicability_domain_table(predictions, train_smiles, dataset, model, seed)
            )

    for path in report_dir.glob("*_gates.csv"):
        parsed = _parse_report_name(path.name, "_gates.csv")
        if parsed is None:
            continue
        dataset, model, seed = parsed
        gates.append(
            gate_summary_table(
                pd.read_csv(path),
                dataset,
                model,
                seed,
            )
        )

    applicability_df = pd.concat(applicability, ignore_index=True) if applicability else pd.DataFrame()
    gate_df = pd.concat(gates, ignore_index=True) if gates else pd.DataFrame()
    if not applicability_df.empty:
        applicability_df.to_csv(report_dir / "applicability_domain.csv", index=False)
    if not gate_df.empty:
        gate_df.to_csv(report_dir / "gate_summary.csv", index=False)
    return applicability_df, gate_df
