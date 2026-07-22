from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from huggingface_hub import hf_hub_download, list_repo_files
from rdkit import Chem
from rdkit.Chem.Scaffolds import MurckoScaffold


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "reports" / "openadmet_expansionrx_feasibility"
REPO_ID = "openadmet/openadmet-expansionrx-challenge-data"
ENDPOINT_EXCLUDE = {"Molecule Name", "SMILES"}


def canonical_smiles(smiles: str) -> str | None:
    if not isinstance(smiles, str) or not smiles.strip():
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return Chem.MolToSmiles(mol, canonical=True)


def murcko_scaffold(smiles: str) -> str:
    mol = Chem.MolFromSmiles(smiles) if isinstance(smiles, str) else None
    if mol is None:
        return ""
    scaffold = MurckoScaffold.GetScaffoldForMol(mol)
    return Chem.MolToSmiles(scaffold, canonical=True) if scaffold is not None else ""


def numeric_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for column in out.columns:
        if column not in ENDPOINT_EXCLUDE:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    return out


def endpoint_summary(train: pd.DataFrame, test: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    rows = []
    endpoints = [column for column in train.columns if column not in ENDPOINT_EXCLUDE]
    for endpoint in endpoints:
        train_values = pd.to_numeric(train[endpoint], errors="coerce")
        test_values = pd.to_numeric(test[endpoint], errors="coerce") if endpoint in test.columns else pd.Series(dtype=float)
        raw_values = pd.to_numeric(raw[endpoint], errors="coerce") if endpoint in raw.columns else pd.Series(dtype=float)
        train_nonmissing = int(train_values.notna().sum())
        test_nonmissing = int(test_values.notna().sum())
        raw_nonmissing = int(raw_values.notna().sum())
        train_std = float(train_values.std()) if train_nonmissing > 1 else np.nan
        test_std = float(test_values.std()) if test_nonmissing > 1 else np.nan
        rows.append(
            {
                "endpoint": endpoint,
                "task_type": "regression",
                "train_nonmissing": train_nonmissing,
                "test_nonmissing": test_nonmissing,
                "raw_nonmissing": raw_nonmissing,
                "train_missing_fraction": float(train_values.isna().mean()),
                "test_missing_fraction": float(test_values.isna().mean()) if len(test_values) else np.nan,
                "test_labels_available": bool(test_nonmissing > 0),
                "train_mean": float(train_values.mean()) if train_nonmissing else np.nan,
                "train_std": train_std,
                "test_mean": float(test_values.mean()) if test_nonmissing else np.nan,
                "test_std": test_std,
                "train_min": float(train_values.min()) if train_nonmissing else np.nan,
                "train_max": float(train_values.max()) if train_nonmissing else np.nan,
            }
        )
    return pd.DataFrame(rows)


def split_summary(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    train = train.copy()
    test = test.copy()
    train["canonical_smiles"] = train["SMILES"].map(canonical_smiles)
    test["canonical_smiles"] = test["SMILES"].map(canonical_smiles)
    train_valid = train[train["canonical_smiles"].notna()].copy()
    test_valid = test[test["canonical_smiles"].notna()].copy()
    train_valid["scaffold"] = train_valid["canonical_smiles"].map(murcko_scaffold)
    test_valid["scaffold"] = test_valid["canonical_smiles"].map(murcko_scaffold)

    train_smiles = set(train_valid["canonical_smiles"])
    test_smiles = set(test_valid["canonical_smiles"])
    train_scaffolds = set(train_valid["scaffold"]) - {""}
    test_scaffolds = set(test_valid["scaffold"]) - {""}
    overlap_smiles = train_smiles & test_smiles
    overlap_scaffolds = train_scaffolds & test_scaffolds

    rows = [
        {
            "split": "train",
            "n_rows": len(train),
            "valid_smiles": len(train_valid),
            "unique_smiles": len(train_smiles),
            "unique_scaffolds": len(train_scaffolds),
            "exact_smiles_overlap_with_other_split": len(overlap_smiles),
            "scaffold_overlap_with_other_split": len(overlap_scaffolds),
            "scaffold_overlap_fraction": len(overlap_scaffolds) / max(1, len(train_scaffolds)),
        },
        {
            "split": "test",
            "n_rows": len(test),
            "valid_smiles": len(test_valid),
            "unique_smiles": len(test_smiles),
            "unique_scaffolds": len(test_scaffolds),
            "exact_smiles_overlap_with_other_split": len(overlap_smiles),
            "scaffold_overlap_with_other_split": len(overlap_scaffolds),
            "scaffold_overlap_fraction": len(overlap_scaffolds) / max(1, len(test_scaffolds)),
        },
    ]
    return pd.DataFrame(rows)


def write_readme(files: list[str], endpoints: pd.DataFrame, splits: pd.DataFrame) -> None:
    label_ready = endpoints[endpoints["test_labels_available"]]
    enough_train = endpoints[endpoints["train_nonmissing"] >= 100]
    lines = [
        "# OpenADMET-ExpansionRx feasibility check",
        "",
        f"Dataset repo: `{REPO_ID}`",
        "",
        "## Files",
        "",
        *[f"- `{file}`" for file in files],
        "",
        "## Split summary",
        "",
        splits.to_markdown(index=False),
        "",
        "## Endpoint summary",
        "",
        endpoints.to_markdown(index=False),
        "",
        "## Feasibility decision",
        "",
        f"- Endpoints with >=100 training labels: {len(enough_train)} / {len(endpoints)}.",
        f"- Endpoints with test labels available in the released full package: {len(label_ready)} / {len(endpoints)}.",
        "- All endpoints are naturally regression-style ADMET endpoints.",
        "- This is feasible as an external appendix benchmark, but should be added after the manuscript tables/figures are updated because it introduces a new benchmark family and endpoint-specific preprocessing choices.",
        "",
        "Recommended first pass: run fast multi-fingerprint RF/LGBM/ExtraTrees and validation-only stacking on endpoints with >=100 train and >=50 test labels; report MAE/RMSE/Spearman and scaffold-overlap diagnostics.",
        "",
    ]
    (OUT_DIR / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = list_repo_files(REPO_ID, repo_type="dataset")
    train_path = hf_hub_download(repo_id=REPO_ID, repo_type="dataset", filename="expansion_data_train.csv")
    test_path = hf_hub_download(repo_id=REPO_ID, repo_type="dataset", filename="expansion_data_test.csv")
    raw_path = hf_hub_download(repo_id=REPO_ID, repo_type="dataset", filename="expansion_data_raw.csv")

    train = numeric_frame(pd.read_csv(train_path))
    test = numeric_frame(pd.read_csv(test_path))
    raw = numeric_frame(pd.read_csv(raw_path))

    endpoints = endpoint_summary(train, test, raw)
    splits = split_summary(train, test)
    endpoints.to_csv(OUT_DIR / "endpoint_feasibility.csv", index=False)
    splits.to_csv(OUT_DIR / "split_feasibility.csv", index=False)
    pd.DataFrame({"file": files}).to_csv(OUT_DIR / "repo_files.csv", index=False)
    write_readme(files, endpoints, splits)
    print(f"Wrote OpenADMET feasibility report to {OUT_DIR}")


if __name__ == "__main__":
    main()
