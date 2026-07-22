from __future__ import annotations

import pandas as pd

from fzyc_mol.benchmarks.moleculeace import summarize_moleculeace_task


def test_moleculeace_inclusion_counts_train_test_and_cliffs() -> None:
    train = pd.DataFrame({"smiles": ["A", "B", "B"], "cliff_mol": [0, 1, 1]})
    test = pd.DataFrame({"smiles": ["C", "D"], "cliff_mol": [1, 0]})

    row = summarize_moleculeace_task("task", train, test)

    assert row["status"] == "included"
    assert row["n_train"] == 3
    assert row["n_train_unique_molecules"] == 2
    assert row["n_test"] == 2
    assert row["n_cliff_molecules"] == 2
