from __future__ import annotations

import pandas as pd


def summarize_moleculeace_task(task: str, train: pd.DataFrame, test: pd.DataFrame) -> dict[str, int | str]:
    required = {"smiles", "cliff_mol"}
    if not required.issubset(train.columns) or not required.issubset(test.columns):
        raise ValueError("MoleculeACE splits require smiles and cliff_mol")
    combined = pd.concat([train.assign(split="train"), test.assign(split="test")], ignore_index=True)
    cliffs = combined[pd.to_numeric(combined["cliff_mol"], errors="coerce").fillna(0).astype(int).eq(1)]
    return {
        "task": task,
        "status": "included",
        "exclusion_reason": "",
        "n_train": len(train),
        "n_train_unique_molecules": train["smiles"].nunique(),
        "n_test": len(test),
        "n_test_unique_molecules": test["smiles"].nunique(),
        "n_cliff_molecules": cliffs["smiles"].nunique(),
        "n_cliff_train": int(pd.to_numeric(train["cliff_mol"], errors="coerce").fillna(0).sum()),
        "n_cliff_test": int(pd.to_numeric(test["cliff_mol"], errors="coerce").fillna(0).sum()),
    }
