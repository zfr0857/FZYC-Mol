from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import DatasetSpec
from fzyc_mol.features import feature_dimensions, morgan_fingerprint, scaffold_from_smiles, smiles_to_graph
from fzyc_mol.splits import make_split
from fzyc_mol.train import run_neural_model, run_sklearn_model


def demo_frame() -> pd.DataFrame:
    smiles = [
        "CCO",
        "CCCO",
        "CCCCO",
        "CC(=O)O",
        "c1ccccc1",
        "c1ccncc1",
        "CCN(CC)CC",
        "CCOC(=O)C",
        "CC(C)O",
        "CC(C)(C)O",
        "CCS",
        "CCCl",
        "CCBr",
        "CC#N",
        "CC(=O)N",
        "CC(C)C(=O)O",
        "COc1ccccc1",
        "CCOc1ccccc1",
        "O=C(O)c1ccccc1",
        "Nc1ccccc1",
    ]
    y = [len(s) / 10.0 for s in smiles]
    return pd.DataFrame({"smiles": smiles, "y": y})


def main() -> None:
    atom_dim, bond_dim, desc_dim = feature_dimensions()
    assert atom_dim > 0 and bond_dim > 0 and desc_dim > 0
    fp = morgan_fingerprint("CCO")
    assert fp.shape[0] == 2048
    assert scaffold_from_smiles("c1ccccc1O")
    graph = smiles_to_graph("CCO", 0.1, "regression")
    assert graph.x.shape[0] == 3
    assert graph.edge_index.shape[0] == 2

    frame = demo_frame()
    spec = DatasetSpec(
        name="demo",
        url="",
        filename="",
        task_type="regression",
        smiles_candidates=("smiles",),
        target_candidates=("y",),
    )
    split = make_split(frame, "scaffold", seed=13)
    assert len(split.train) > 0 and len(split.test) > 0

    out = ROOT / "reports" / "validation"
    result_rf = run_sklearn_model("rf_morgan", frame, spec, "scaffold", seed=13)
    result_gin = run_neural_model(
        model_name="gin",
        frame=frame,
        spec=spec,
        split_name="scaffold",
        seed=13,
        epochs=1,
        batch_size=8,
        hidden_dim=32,
        layers=2,
        lr=1e-3,
        weight_decay=1e-5,
        contrastive_weight=0.0,
        num_workers=0,
        output_dir=out,
    )
    result_fzyc = run_neural_model(
        model_name="fzyc_mol",
        frame=frame,
        spec=spec,
        split_name="scaffold",
        seed=13,
        epochs=1,
        batch_size=8,
        hidden_dim=32,
        layers=2,
        lr=1e-3,
        weight_decay=1e-5,
        contrastive_weight=0.01,
        num_workers=0,
        output_dir=out,
    )
    payload = {
        "feature_dimensions": {"atom": atom_dim, "bond": bond_dim, "descriptor": desc_dim},
        "rf": result_rf.to_dict(),
        "gin": result_gin.to_dict(),
        "fzyc_mol": result_fzyc.to_dict(),
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "validation_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
