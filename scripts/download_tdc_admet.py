from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from rdkit import RDLogger

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import DATASETS, canonicalize_smiles


RDLogger.DisableLog("rdApp.*")

TDC_ADMET_TASKS = {
    "tdc_caco2_wang": ("Caco2_Wang", "regression"),
    "tdc_hia_hou": ("HIA_Hou", "classification"),
    "tdc_pgp_broccatelli": ("Pgp_Broccatelli", "classification"),
    "tdc_bioavailability_ma": ("Bioavailability_Ma", "classification"),
    "tdc_bbb_martins": ("BBB_Martins", "classification"),
    "tdc_cyp2c9_veith": ("CYP2C9_Veith", "classification"),
    "tdc_cyp2d6_veith": ("CYP2D6_Veith", "classification"),
    "tdc_cyp3a4_veith": ("CYP3A4_Veith", "classification"),
}


def normalize_tdc_frame(raw: pd.DataFrame, task_type: str) -> pd.DataFrame:
    smiles_col = "Drug" if "Drug" in raw.columns else "smiles"
    target_col = "Y" if "Y" in raw.columns else "y"
    frame = raw[[smiles_col, target_col]].rename(columns={smiles_col: "smiles", target_col: "y"}).copy()
    frame["smiles"] = frame["smiles"].map(canonicalize_smiles)
    frame["y"] = pd.to_numeric(frame["y"], errors="coerce")
    frame = frame.dropna(subset=["smiles", "y"]).drop_duplicates("smiles").reset_index(drop=True)
    if task_type == "classification":
        frame["y"] = frame["y"].astype(int)
        frame = frame[frame["y"].isin([0, 1])].reset_index(drop=True)
    return frame


def update_registry(path: Path) -> None:
    registry = {}
    if path.exists():
        registry = json.loads(path.read_text(encoding="utf-8"))
    for name in TDC_ADMET_TASKS:
        spec = DATASETS[name]
        registry[name] = {
            "url": spec.url,
            "filename": spec.filename,
            "task_type": spec.task_type,
            "smiles_candidates": list(spec.smiles_candidates),
            "target_candidates": list(spec.target_candidates),
        }
    path.write_text(json.dumps(registry, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and normalize 8 TDC ADMET datasets.")
    parser.add_argument("--datasets", nargs="*", default=list(TDC_ADMET_TASKS))
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--tdc-cache-dir", default=str(ROOT / "data" / "tdc"))
    args = parser.parse_args()

    try:
        from tdc.single_pred import ADME
    except ImportError as exc:
        raise SystemExit("Install PyTDC first: python -m pip install PyTDC") from exc

    data_dir = Path(args.data_dir)
    raw_dir = data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = Path(args.tdc_cache_dir)
    rows = []

    for dataset in args.datasets:
        if dataset not in TDC_ADMET_TASKS:
            raise KeyError(f"Unknown TDC task {dataset}. Available: {sorted(TDC_ADMET_TASKS)}")
        tdc_name, task_type = TDC_ADMET_TASKS[dataset]
        target_path = raw_dir / DATASETS[dataset].filename
        if target_path.exists():
            frame = pd.read_csv(target_path)
        else:
            data = ADME(name=tdc_name, path=str(cache_dir))
            frame = normalize_tdc_frame(data.get_data(), task_type)
            frame.to_csv(target_path, index=False)
        rows.append(
            {
                "dataset": dataset,
                "tdc_name": tdc_name,
                "task_type": task_type,
                "rows": len(frame),
                "positives": int(frame["y"].sum()) if task_type == "classification" else None,
                "path": str(target_path),
            }
        )

    update_registry(data_dir / "dataset_registry.json")
    summary = pd.DataFrame(rows)
    summary.to_csv(data_dir / "tdc_admet_summary.csv", index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
