from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from rdkit import DataStructs

from fzyc_mol.datasets import load_dataset
from fzyc_mol.features import morgan_fingerprint
from fzyc_mol.splits import SplitIndices, make_split

from .io import ExperimentConfig, write_csv


def _fp_bitvect(smiles: str):
    arr = morgan_fingerprint(smiles)
    bv = DataStructs.ExplicitBitVect(int(arr.shape[0]))
    for bit in np.flatnonzero(arr > 0):
        bv.SetBit(int(bit))
    return bv


def perimeter_split(frame: pd.DataFrame, seed: int, test_fraction: float = 0.10, valid_fraction: float = 0.10) -> SplitIndices:
    """Select the most distant molecules as test set using Morgan Tanimoto distance."""
    rng = np.random.default_rng(seed)
    n = len(frame)
    if n < 10:
        return make_split(frame, "random", seed)
    fps = [_fp_bitvect(s) for s in frame["smiles"].tolist()]
    centroid_idx = int(rng.integers(0, n))
    centroid = fps[centroid_idx]
    similarities = np.asarray(DataStructs.BulkTanimotoSimilarity(centroid, fps), dtype=float)
    # Start from a random anchor, then use farthest-to-anchor ordering as a stable max-distance proxy.
    distance = 1.0 - similarities
    order = np.argsort(-distance)
    n_test = max(1, int(round(test_fraction * n)))
    n_valid = max(1, int(round(valid_fraction * n)))
    test = np.sort(order[:n_test])
    remaining = np.asarray([i for i in order[n_test:] if i not in set(test)], dtype=int)
    rng.shuffle(remaining)
    valid = np.sort(remaining[:n_valid])
    train = np.sort(remaining[n_valid:])
    return SplitIndices(train=train, valid=valid, test=test)


def build_split_frame(frame: pd.DataFrame, split: SplitIndices, dataset: str, split_name: str, seed: int) -> pd.DataFrame:
    rows = []
    for split_part, indices in [("train", split.train), ("valid", split.valid), ("test", split.test)]:
        for idx in indices:
            rows.append(
                {
                    "dataset": dataset,
                    "seed": seed,
                    "split_strategy": split_name,
                    "split": split_part,
                    "row_index": int(idx),
                    "smiles": frame.iloc[int(idx)]["smiles"],
                    "y": frame.iloc[int(idx)]["y"],
                }
            )
    return pd.DataFrame(rows)


def generate_splits(config: ExperimentConfig, datasets: list[str] | None = None) -> pd.DataFrame:
    rows = []
    missing = []
    names = datasets or sorted(set(config.datasets("moleculenet") + config.datasets("tdc_admet")))
    test_fraction = float(config.raw.get("perimeter_test_fraction", 0.10))
    valid_fraction = float(config.raw.get("valid_fraction", 0.10))
    for dataset in names:
        try:
            frame, _ = load_dataset(dataset, config.data_dir)
        except Exception as exc:
            missing.append({"module": "data_splits", "dataset": dataset, "reason": str(exc)})
            continue
        for seed in config.seeds:
            for split_name in config.raw.get("splits", ["random", "scaffold", "perimeter"]):
                if split_name == "perimeter":
                    split = perimeter_split(frame, seed, test_fraction=test_fraction, valid_fraction=valid_fraction)
                else:
                    split = make_split(frame, split_name, seed)
                rows.append(build_split_frame(frame, split, dataset, split_name, seed))
    out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    write_csv(out, config.reports_dir / "split_indices.csv")
    if missing:
        write_csv(pd.DataFrame(missing), config.reports_dir / "missing_data_report.csv")
    return out


def split_indices_for(frame: pd.DataFrame, split_name: str, seed: int, config: ExperimentConfig) -> SplitIndices:
    if split_name == "perimeter":
        return perimeter_split(
            frame,
            seed,
            test_fraction=float(config.raw.get("perimeter_test_fraction", 0.10)),
            valid_fraction=float(config.raw.get("valid_fraction", 0.10)),
        )
    return make_split(frame, split_name, seed)
