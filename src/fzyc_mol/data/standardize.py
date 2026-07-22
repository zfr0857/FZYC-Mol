from __future__ import annotations

import hashlib
from typing import Any

import pandas as pd
from rdkit import Chem
from rdkit.Chem.MolStandardize import rdMolStandardize


_FRAGMENT_CHOOSER = rdMolStandardize.LargestFragmentChooser()
_UNCHARGER = rdMolStandardize.Uncharger()


def standardize_smiles(value: object) -> tuple[str | None, str]:
    """Return a neutral, largest-fragment canonical SMILES and an audit reason."""

    if not isinstance(value, str) or not value.strip():
        return None, "missing_smiles"
    molecule = Chem.MolFromSmiles(value)
    if molecule is None:
        return None, "invalid_smiles"
    molecule = rdMolStandardize.Cleanup(molecule)
    molecule = _FRAGMENT_CHOOSER.choose(molecule)
    molecule = _UNCHARGER.uncharge(molecule)
    return Chem.MolToSmiles(molecule, canonical=True, isomericSmiles=True), "retained"


def _data_hash(frame: pd.DataFrame) -> str:
    payload = frame[["standardized_smiles", "y"]].sort_values("standardized_smiles").to_csv(index=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def audit_cleaning_frame(
    frame: pd.DataFrame,
    *,
    smiles_col: str,
    target_col: str,
    task_type: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Standardize a raw endpoint and retain a reason for every source row."""

    if task_type not in {"classification", "regression"}:
        raise ValueError("task_type must be classification or regression")
    work = frame[[smiles_col, target_col]].copy().reset_index(names="source_row")
    standardized = work[smiles_col].map(standardize_smiles)
    work["standardized_smiles"] = standardized.map(lambda item: item[0])
    work["reason"] = standardized.map(lambda item: item[1])
    work["y"] = pd.to_numeric(work[target_col], errors="coerce")
    missing_target = work[target_col].isna()
    non_numeric_target = work[target_col].notna() & work["y"].isna()
    work.loc[(work["reason"] == "retained") & missing_target, "reason"] = "missing_target"
    work.loc[(work["reason"] == "retained") & non_numeric_target, "reason"] = "non_numeric_target"
    if task_type == "classification":
        invalid_class = (work["reason"] == "retained") & ~work["y"].isin([0, 1])
        work.loc[invalid_class, "reason"] = "invalid_class_label"

    valid = work.loc[work["reason"] == "retained"].copy()
    cleaned_rows: list[dict[str, Any]] = []
    duplicate_consistent_merged = 0
    duplicate_conflict_excluded = 0
    for canonical, group in valid.groupby("standardized_smiles", sort=True):
        indices = group.index.tolist()
        if task_type == "classification" and group["y"].nunique(dropna=False) > 1:
            work.loc[indices, "reason"] = "duplicate_label_conflict"
            duplicate_conflict_excluded += len(group)
            continue
        representative = indices[0]
        if len(group) > 1:
            duplicate_consistent_merged += len(group) - 1
            work.loc[indices[1:], "reason"] = "duplicate_consistent_merged"
        cleaned_rows.append(
            {
                "standardized_smiles": canonical,
                "y": int(group["y"].iloc[0]) if task_type == "classification" else float(group["y"].mean()),
                "replicate_count": int(len(group)),
                "source_row": int(work.loc[representative, "source_row"]),
            }
        )

    cleaned = pd.DataFrame(
        cleaned_rows,
        columns=["standardized_smiles", "y", "replicate_count", "source_row"],
    )
    work["action"] = work["reason"].map(
        lambda reason: "retained" if reason == "retained" else ("merged" if reason == "duplicate_consistent_merged" else "removed")
    )
    events = work[["source_row", smiles_col, target_col, "standardized_smiles", "action", "reason"]].copy()
    reason_counts = work["reason"].value_counts().to_dict()
    summary: dict[str, Any] = {
        "input_count": int(len(work)),
        "output_count": int(len(cleaned)),
        "missing_smiles": int(reason_counts.get("missing_smiles", 0)),
        "invalid_smiles": int(reason_counts.get("invalid_smiles", 0)),
        "missing_target": int(reason_counts.get("missing_target", 0)),
        "non_numeric_target": int(reason_counts.get("non_numeric_target", 0)),
        "invalid_class_label": int(reason_counts.get("invalid_class_label", 0)),
        "duplicate_consistent_merged": int(duplicate_consistent_merged),
        "duplicate_conflict_excluded": int(duplicate_conflict_excluded),
        "data_hash": _data_hash(cleaned) if not cleaned.empty else hashlib.sha256(b"").hexdigest(),
    }
    return cleaned, events, summary
