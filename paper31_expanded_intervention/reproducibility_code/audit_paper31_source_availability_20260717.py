from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(r"D:\fzyc")
OUT = ROOT / "output" / "paper31_expanded_intervention_20260717"
BASE = ROOT / "output" / "paper27_equal_size_registry_composition_20260716"
EMB = ROOT / "data" / "processed" / "pretrained_embeddings"
TASKS = ["clintox", "bace", "bbbp", "esol", "lipo", "tdc_caco2_wang"]
LABELS = {
    "clintox": "ClinTox", "bace": "BACE", "bbbp": "BBBP", "esol": "ESOL",
    "lipo": "Lipophilicity", "tdc_caco2_wang": "Caco2 Wang",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    outer = pd.read_csv(BASE / "equal_size_outer_candidate_scores.csv.gz")
    existing_equal = set(outer.task)
    repeated = pd.read_csv(ROOT / "results" / "nested_selection" / "repeated_nested" / "seed_11" / "outer_candidate_scores.csv")
    multiview = pd.read_csv(ROOT / "results" / "reviewer_core_20260624" / "multiview_nested" / "outer_candidate_scores.csv")
    repeated_tasks = set(repeated.dataset)
    multiview_tasks = set(multiview.task)
    chemprop = pd.read_csv(ROOT / "output" / "小论文-12_严格补实验" / "chemprop_outer_scores.csv")
    dmpnn_tasks = set(chemprop.task)
    encoders = {
        "ChemBERTa-MTR": "DeepChem_ChemBERTa-77M-MTR",
        "ChemBERTa-MLM": "DeepChem_ChemBERTa-77M-MLM",
        "MoLFormer": "ibm_MoLFormer-XL-both-10pct",
    }
    rows = []
    for task in TASKS:
        cached = [name for name, folder in encoders.items() if (EMB / folder / f"{task}.npz").exists()]
        complete = task in existing_equal
        needs = []
        if len(cached) < 3:
            needs.append("frozen embedding extraction")
        if task not in dmpnn_tasks:
            needs.append("one-epoch D-MPNN nested fitting")
        if not complete:
            needs.append("35 lightweight nested candidates")
        rows.append({
            "endpoint": LABELS[task], "task_id": task,
            "homogeneous_morgan_source": "available" if task in repeated_tasks else "requires source data",
            "classical_multiview_source": "available" if task in multiview_tasks else "requires source data",
            "three_encoder_embeddings": ", ".join(cached) if len(cached) == 3 else "requires new analysis",
            "dmpnn_nested_source": "available" if task in dmpnn_tasks else "requires new analysis",
            "complete_equal_size_source": "available" if complete else "requires new analysis",
            "required_action": "; ".join(needs) if needs else "none",
        })
    rows += [
        {"endpoint": "Composition × split regime", "task_id": "clintox,bace,esol",
         "homogeneous_morgan_source": "available", "classical_multiview_source": "requires new analysis",
         "three_encoder_embeddings": "available for scaffold only", "dmpnn_nested_source": "requires new analysis",
         "complete_equal_size_source": "requires new analysis",
         "required_action": "run classical and modern registries on locked Tanimoto-component folds"},
        {"endpoint": "Requested manuscript", "task_id": "manuscript(6)(2).docx",
         "homogeneous_morgan_source": "requires source data", "classical_multiview_source": "n/a",
         "three_encoder_embeddings": "n/a", "dmpnn_nested_source": "n/a",
         "complete_equal_size_source": "requires source data",
         "required_action": "use Paper30 manuscript(6).docx as latest validated baseline"},
    ]
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "Paper31_source_availability_audit.csv", index=False, encoding="utf-8-sig")
    frozen = {
        "status": "source audit complete",
        "predefined_endpoints": TASKS,
        "endpoint_selection_basis": {
            "clintox": "rare-class classification", "bace": "moderately balanced classification",
            "bbbp": "additional classification", "esol": "small regression",
            "lipo": "large regression", "tdc_caco2_wang": "permeability regression",
        },
        "candidate_counts": [4, 8, 16, 32],
        "seeds": [11, 23, 37, 53, 71],
        "outer_folds": 3,
        "inner_folds": 3,
        "primary_anchor": "shared Morgan linear anchor",
        "sensitivity_anchors": ["fixed Morgan-RF anchor", "registry-order median candidate"],
        "primary_normalization": "homogeneous-audit-best normalized gain",
        "sensitivity_normalizations": ["raw endpoint scale", "endpoint-MAD normalized"],
        "equal_budget_rule": "per endpoint and audit unit, truncate each registry in locked order at the classical-multiview median downstream time for the corresponding K; never use outer performance",
        "statistical_unit": "fold effects averaged within seed; seed-level effects retained; endpoint summaries do not treat endpoint-pool-K cells as independent",
        "requested_manuscript_6_2_found": False,
        "baseline": "paper30_submission_package_20260717/Candidate_pool_expansion_Journal_of_Cheminformatics_manuscript(6).docx",
    }
    (OUT / "Paper31_frozen_analysis_plan.json").write_text(json.dumps(frozen, ensure_ascii=False, indent=2), encoding="utf-8")
    print(frame.to_string(index=False))


if __name__ == "__main__":
    main()
