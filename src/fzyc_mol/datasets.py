from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd
from rdkit import Chem


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    url: str
    filename: str
    task_type: str
    smiles_candidates: tuple[str, ...]
    target_candidates: tuple[str, ...]
    positive_label: int | float | None = None


DATASETS: dict[str, DatasetSpec] = {
    "esol": DatasetSpec(
        name="esol",
        url="https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/delaney-processed.csv",
        filename="delaney-processed.csv",
        task_type="regression",
        smiles_candidates=("smiles", "SMILES", "mol"),
        target_candidates=("measured log solubility in mols per litre", "logS", "y"),
    ),
    "freesolv": DatasetSpec(
        name="freesolv",
        url="https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/SAMPL.csv",
        filename="SAMPL.csv",
        task_type="regression",
        smiles_candidates=("smiles", "SMILES", "mol"),
        target_candidates=("expt", "y"),
    ),
    "lipo": DatasetSpec(
        name="lipo",
        url="https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/Lipophilicity.csv",
        filename="Lipophilicity.csv",
        task_type="regression",
        smiles_candidates=("smiles", "SMILES", "mol"),
        target_candidates=("exp", "y"),
    ),
    "bbbp": DatasetSpec(
        name="bbbp",
        url="https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/BBBP.csv",
        filename="BBBP.csv",
        task_type="classification",
        smiles_candidates=("smiles", "SMILES", "mol"),
        target_candidates=("p_np", "Class", "label", "y"),
    ),
    "bace": DatasetSpec(
        name="bace",
        url="https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/bace.csv",
        filename="bace.csv",
        task_type="classification",
        smiles_candidates=("mol", "smiles", "SMILES"),
        target_candidates=("Class", "class", "label", "y"),
    ),
    "clintox": DatasetSpec(
        name="clintox",
        url="https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/clintox.csv.gz",
        filename="clintox.csv.gz",
        task_type="classification",
        smiles_candidates=("smiles", "SMILES", "mol"),
        target_candidates=("CT_TOX", "FDA_APPROVED", "label", "y"),
    ),
    "tdc_caco2_wang": DatasetSpec(
        name="tdc_caco2_wang",
        url="tdc:ADME/Caco2_Wang",
        filename="tdc_caco2_wang.csv",
        task_type="regression",
        smiles_candidates=("smiles", "Drug", "SMILES", "mol"),
        target_candidates=("y", "Y", "label"),
    ),
    "tdc_hia_hou": DatasetSpec(
        name="tdc_hia_hou",
        url="tdc:ADME/HIA_Hou",
        filename="tdc_hia_hou.csv",
        task_type="classification",
        smiles_candidates=("smiles", "Drug", "SMILES", "mol"),
        target_candidates=("y", "Y", "label"),
    ),
    "tdc_pgp_broccatelli": DatasetSpec(
        name="tdc_pgp_broccatelli",
        url="tdc:ADME/Pgp_Broccatelli",
        filename="tdc_pgp_broccatelli.csv",
        task_type="classification",
        smiles_candidates=("smiles", "Drug", "SMILES", "mol"),
        target_candidates=("y", "Y", "label"),
    ),
    "tdc_bioavailability_ma": DatasetSpec(
        name="tdc_bioavailability_ma",
        url="tdc:ADME/Bioavailability_Ma",
        filename="tdc_bioavailability_ma.csv",
        task_type="classification",
        smiles_candidates=("smiles", "Drug", "SMILES", "mol"),
        target_candidates=("y", "Y", "label"),
    ),
    "tdc_bbb_martins": DatasetSpec(
        name="tdc_bbb_martins",
        url="tdc:ADME/BBB_Martins",
        filename="tdc_bbb_martins.csv",
        task_type="classification",
        smiles_candidates=("smiles", "Drug", "SMILES", "mol"),
        target_candidates=("y", "Y", "label"),
    ),
    "tdc_cyp2c9_veith": DatasetSpec(
        name="tdc_cyp2c9_veith",
        url="tdc:ADME/CYP2C9_Veith",
        filename="tdc_cyp2c9_veith.csv",
        task_type="classification",
        smiles_candidates=("smiles", "Drug", "SMILES", "mol"),
        target_candidates=("y", "Y", "label"),
    ),
    "tdc_cyp2d6_veith": DatasetSpec(
        name="tdc_cyp2d6_veith",
        url="tdc:ADME/CYP2D6_Veith",
        filename="tdc_cyp2d6_veith.csv",
        task_type="classification",
        smiles_candidates=("smiles", "Drug", "SMILES", "mol"),
        target_candidates=("y", "Y", "label"),
    ),
    "tdc_cyp3a4_veith": DatasetSpec(
        name="tdc_cyp3a4_veith",
        url="tdc:ADME/CYP3A4_Veith",
        filename="tdc_cyp3a4_veith.csv",
        task_type="classification",
        smiles_candidates=("smiles", "Drug", "SMILES", "mol"),
        target_candidates=("y", "Y", "label"),
    ),
}


def available_datasets() -> list[str]:
    return sorted(DATASETS)


def raw_path(data_dir: str | Path, name: str) -> Path:
    spec = DATASETS[name]
    return Path(data_dir) / "raw" / spec.filename


def _first_existing(columns: Iterable[str], candidates: Iterable[str], role: str) -> str:
    columns_set = set(columns)
    for candidate in candidates:
        if candidate in columns_set:
            return candidate
    raise KeyError(f"Could not find {role} column. Tried: {list(candidates)}")


def canonicalize_smiles(smiles: str) -> str | None:
    if not isinstance(smiles, str) or not smiles.strip():
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return Chem.MolToSmiles(mol, canonical=True)


def load_raw_dataset(name: str, data_dir: str | Path = "data") -> pd.DataFrame:
    if name not in DATASETS:
        raise KeyError(f"Unknown dataset '{name}'. Available: {available_datasets()}")
    path = raw_path(data_dir, name)
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run: python scripts/download_open_data.py --dataset {name}"
        )
    return pd.read_csv(path)


def load_dataset(
    name: str,
    data_dir: str | Path = "data",
    max_rows: int | None = None,
) -> tuple[pd.DataFrame, DatasetSpec]:
    spec = DATASETS[name]
    raw = load_raw_dataset(name, data_dir)
    smiles_col = _first_existing(raw.columns, spec.smiles_candidates, "SMILES")
    target_col = _first_existing(raw.columns, spec.target_candidates, "target")

    frame = raw[[smiles_col, target_col]].rename(columns={smiles_col: "smiles", target_col: "y"})
    frame["smiles"] = frame["smiles"].map(canonicalize_smiles)
    frame = frame.dropna(subset=["smiles", "y"]).drop_duplicates("smiles")
    frame["y"] = pd.to_numeric(frame["y"], errors="coerce")
    frame = frame.dropna(subset=["y"]).reset_index(drop=True)
    if spec.task_type == "classification":
        frame["y"] = frame["y"].astype(int)
        frame = frame[frame["y"].isin([0, 1])].reset_index(drop=True)
    if max_rows is not None:
        frame = frame.head(int(max_rows)).reset_index(drop=True)
    return frame, spec
