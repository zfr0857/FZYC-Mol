from __future__ import annotations

import pandas as pd

from fzyc_mol.data.standardize import audit_cleaning_frame, standardize_smiles


def test_standardize_smiles_keeps_largest_fragment_and_normalizes_charge() -> None:
    standardized, reason = standardize_smiles("C[NH+](C)C.[Cl-]")

    assert reason == "retained"
    assert standardized == "CN(C)C"


def test_classification_duplicate_conflicts_are_excluded_with_reasons() -> None:
    frame = pd.DataFrame(
        {
            "smiles": ["CCO", "OCC", "CC", "not-a-smiles", None],
            "y": [0, 1, 1, 0, 1],
        }
    )

    cleaned, events, summary = audit_cleaning_frame(
        frame,
        smiles_col="smiles",
        target_col="y",
        task_type="classification",
    )

    assert cleaned["standardized_smiles"].tolist() == ["CC"]
    assert summary["duplicate_conflict_excluded"] == 2
    assert summary["invalid_smiles"] == 1
    assert summary["missing_smiles"] == 1
    assert set(events.loc[events["action"] == "removed", "reason"]) == {
        "duplicate_label_conflict",
        "invalid_smiles",
        "missing_smiles",
    }


def test_regression_consistent_duplicates_are_aggregated() -> None:
    frame = pd.DataFrame({"smiles": ["CCO", "OCC", "CC"], "y": [1.0, 3.0, 2.0]})

    cleaned, _, summary = audit_cleaning_frame(
        frame,
        smiles_col="smiles",
        target_col="y",
        task_type="regression",
    )

    ethanol = cleaned.loc[cleaned["standardized_smiles"] == "CCO"].iloc[0]
    assert ethanol["y"] == 2.0
    assert ethanol["replicate_count"] == 2
    assert summary["duplicate_consistent_merged"] == 1
