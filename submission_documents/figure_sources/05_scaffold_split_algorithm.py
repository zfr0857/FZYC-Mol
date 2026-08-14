from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .features import scaffold_from_smiles


@dataclass(frozen=True)
class SplitIndices:
    train: np.ndarray
    valid: np.ndarray
    test: np.ndarray


def scaffold_split(
    frame: pd.DataFrame,
    seed: int,
    frac_train: float = 0.8,
    frac_valid: float = 0.1,
    frac_test: float = 0.1,
) -> SplitIndices:
    if not np.isclose(frac_train + frac_valid + frac_test, 1.0):
        raise ValueError("Split fractions must sum to 1.")

    rng = random.Random(seed)
    scaffold_to_indices: dict[str, list[int]] = defaultdict(list)
    for idx, smiles in enumerate(frame["smiles"].tolist()):
        scaffold_to_indices[scaffold_from_smiles(smiles)].append(idx)

    groups = list(scaffold_to_indices.values())
    rng.shuffle(groups)
    groups = sorted(groups, key=lambda group: (-len(group), rng.random()))

    n_total = len(frame)
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

    return SplitIndices(
        train=np.asarray(sorted(train), dtype=int),
        valid=np.asarray(sorted(valid), dtype=int),
        test=np.asarray(sorted(test), dtype=int),
    )


def random_split(
    frame: pd.DataFrame,
    seed: int,
    frac_train: float = 0.8,
    frac_valid: float = 0.1,
    frac_test: float = 0.1,
) -> SplitIndices:
    if not np.isclose(frac_train + frac_valid + frac_test, 1.0):
        raise ValueError("Split fractions must sum to 1.")
    rng = np.random.default_rng(seed)
    indices = np.arange(len(frame))
    rng.shuffle(indices)
    n_train = int(frac_train * len(indices))
    n_valid = int(frac_valid * len(indices))
    return SplitIndices(
        train=np.sort(indices[:n_train]),
        valid=np.sort(indices[n_train : n_train + n_valid]),
        test=np.sort(indices[n_train + n_valid :]),
    )


def make_split(frame: pd.DataFrame, split: str, seed: int) -> SplitIndices:
    if split == "scaffold":
        return scaffold_split(frame, seed)
    if split == "random":
        return random_split(frame, seed)
    raise ValueError(f"Unknown split '{split}'. Use 'scaffold' or 'random'.")
