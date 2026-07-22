# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from rdkit import Chem, DataStructs, RDLogger, rdBase
from rdkit.Chem import AllChem
from rdkit.Chem.Scaffolds import MurckoScaffold


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "reports" / "draft10_core_experiments_20260621" / "autogluon_features"
TASKS = [
    "bbbp", "bace", "clintox", "esol", "freesolv", "lipo",
    "tdc_caco2_wang", "tdc_hia_hou", "tdc_pgp_broccatelli",
]
RDLogger.DisableLog("rdApp.*")


def pick_column(df: pd.DataFrame, candidates: list[str]) -> str:
    lower = {c.lower(): c for c in df.columns}
    for col in candidates:
        if col in df.columns:
            return col
        if col.lower() in lower:
            return lower[col.lower()]
    raise KeyError(candidates)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    registry = json.loads((DATA / "dataset_registry.json").read_text(encoding="utf-8"))
    manifest = {"rdkit": rdBase.rdkitVersion, "n_bits": 512, "tasks": {}}
    for task in TASKS:
        meta = registry[task]
        path = DATA / "raw" / meta["filename"]
        if not path.exists():
            path = DATA / "tdc" / meta["filename"].replace(".csv", ".tab")
        frame = pd.read_csv(path, sep="\t" if path.suffix == ".tab" else ",")
        smiles_col = pick_column(frame, meta["smiles_candidates"])
        target_col = pick_column(frame, meta["target_candidates"])
        frame = frame[[smiles_col, target_col]].rename(columns={smiles_col: "smiles", target_col: "y"})
        frame["y"] = pd.to_numeric(frame["y"], errors="coerce")
        frame = frame.dropna().drop_duplicates("smiles").reset_index(drop=True)
        x_rows: list[np.ndarray] = []
        y_rows: list[float] = []
        groups: list[str] = []
        smiles_out: list[str] = []
        for smi, y in frame[["smiles", "y"]].itertuples(index=False):
            mol = Chem.MolFromSmiles(str(smi))
            if mol is None:
                continue
            arr = np.zeros(512, dtype=np.uint8)
            fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=512)
            DataStructs.ConvertToNumpyArray(fp, arr)
            scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False)
            if not scaffold:
                scaffold = Chem.MolToSmiles(mol, canonical=True)
            x_rows.append(arr)
            y_rows.append(float(y))
            groups.append(scaffold)
            smiles_out.append(Chem.MolToSmiles(mol, canonical=True))
        y_arr = np.asarray(y_rows, dtype=np.int8 if meta["task_type"] == "classification" else np.float32)
        np.savez_compressed(
            OUT / f"{task}.npz",
            X=np.vstack(x_rows),
            y=y_arr,
            groups=np.asarray(groups, dtype=str),
            smiles=np.asarray(smiles_out, dtype=str),
        )
        manifest["tasks"][task] = {
            "task_type": meta["task_type"],
            "n": int(len(y_arr)),
            "positive_rate": float(y_arr.mean()) if meta["task_type"] == "classification" else None,
            "source": str(path.relative_to(ROOT)),
        }
        print(task, manifest["tasks"][task], flush=True)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
