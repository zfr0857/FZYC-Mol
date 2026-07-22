from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CORE_PATH = ROOT / "scripts" / "analyze_paper31_expanded_intervention_20260717.py"
CORE_OUT = ROOT / "output" / "paper31_expanded_intervention_20260717"
SIM_ROOT = ROOT / "results" / "paper31_expanded_intervention_20260717" / "similarity_composition"
HOM_SIM = ROOT / "results" / "split_regime_transfer_20260716" / "similarity_cluster"
OUT = CORE_OUT / "composition_split_loop"
TASKS = ["clintox", "bace", "esol"]
SEEDS = [11, 23, 37, 53, 71]


def load_core_module():
    spec = importlib.util.spec_from_file_location("paper31_core_analysis", CORE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load Paper31 core analysis module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.TASKS = TASKS
    return module


def load_similarity_sources(core):
    hom_i, hom_o, split_parts = [], [], []
    for seed in SEEDS:
        root = HOM_SIM / f"seed_{seed}"
        i = pd.read_csv(root / "inner_scores.csv")
        o = pd.read_csv(root / "outer_candidate_scores.csv")
        i["seed"] = seed
        o["seed"] = seed
        hom_i.append(i)
        hom_o.append(o)
        split = pd.read_csv(root / "split_manifest.csv")
        split["seed"] = seed
        split_parts.append(split)
    hom_i = core.normalize(pd.concat(hom_i, ignore_index=True), "inner", "similarity_homogeneous")
    hom_o = core.normalize(pd.concat(hom_o, ignore_index=True), "outer", "similarity_homogeneous")
    hom_i["representation"] = "morgan512"
    hom_o["representation"] = "morgan512"

    base_i = core.normalize(pd.read_csv(SIM_ROOT / "base" / "inner_scores.csv"), "inner", "similarity_base")
    base_o = core.normalize(pd.read_csv(SIM_ROOT / "base" / "outer_candidate_scores.csv"), "outer", "similarity_base")
    new_i = core.normalize(pd.read_csv(SIM_ROOT / "new_candidates" / "inner_scores.csv"), "inner", "similarity_new")
    new_o = core.normalize(pd.read_csv(SIM_ROOT / "new_candidates" / "outer_candidate_scores.csv"), "outer", "similarity_new")
    dmp_i = core.load_chemprop(SIM_ROOT / "chemprop", "inner")
    dmp_o = core.load_chemprop(SIM_ROOT / "chemprop", "outer")
    for frame in (dmp_i, dmp_o):
        frame["representation"] = "dmpnn_graph"
        frame["family"] = "chemprop_dmpnn"
    return (
        {"hom": hom_i, "base": base_i, "new": new_i, "dmpnn": dmp_i},
        {"hom": hom_o, "base": base_o, "new": new_o, "dmpnn": dmp_o},
        pd.concat(split_parts, ignore_index=True),
    )


def summarize_regime(core, inner, outer, anchors, regime):
    units = core.selection_units(inner, outer, anchors, "shared_morgan_linear")
    units = core.add_cross_fitted_gap(units, outer)
    units = core.add_paired_homogeneous_normalization(units)
    units.insert(0, "split_regime", regime)
    summary = core.bootstrap_summary(units.drop(columns="split_regime"))
    summary.insert(0, "split_regime", regime)
    diversity = core.effective_diversity(outer, anchors)
    diversity.insert(0, "split_regime", regime)
    stability = core.selection_stability(units.drop(columns="split_regime"))
    stability.insert(0, "split_regime", regime)
    return units, summary, diversity, stability


def direction_concordance(summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    metrics = [
        "oracle_opportunity_gain_mean", "selected_model_gain_mean",
        "chance_adjusted_hit3_mean", "cross_fitted_selection_gap_mean",
    ]
    for (pool, task), group in summary.groupby(["pool", "task"]):
        for metric in metrics:
            for low, high in [(4, 32), (16, 32)]:
                wide = group.loc[group.candidate_count.isin([low, high])].pivot_table(
                    index="split_regime", columns="candidate_count", values=metric
                )
                if set([low, high]).issubset(wide.columns) and set(["scaffold", "similarity_cluster"]).issubset(wide.index):
                    scaffold_change = float(wide.loc["scaffold", high] - wide.loc["scaffold", low])
                    similarity_change = float(wide.loc["similarity_cluster", high] - wide.loc["similarity_cluster", low])
                    rows.append({
                        "pool": pool, "task": task, "metric": metric, "contrast": f"K{high}-K{low}",
                        "scaffold_change": scaffold_change, "similarity_cluster_change": similarity_change,
                        "same_direction": bool(np.sign(scaffold_change) == np.sign(similarity_change)),
                    })
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    core = load_core_module()

    scaffold_i = pd.read_csv(CORE_OUT / "Paper31_inner_scores.csv.gz")
    scaffold_o = pd.read_csv(CORE_OUT / "Paper31_outer_candidate_scores.csv.gz")
    scaffold_i = scaffold_i.loc[scaffold_i.task.isin(TASKS)].copy()
    scaffold_o = scaffold_o.loc[scaffold_o.task.isin(TASKS)].copy()
    scaffold_anchor = scaffold_o.loc[
        scaffold_o.candidate.isin([core.PRIMARY_ANCHOR, core.SECONDARY_ANCHOR])
    ].drop_duplicates(["task", "seed", "outer_fold", "candidate"])

    sim_i_sources, sim_o_sources, split_manifest = load_similarity_sources(core)
    sim_i, sim_o, sim_registry = core.assemble_pools(sim_i_sources, sim_o_sources)
    checks = core.verify_balance(sim_i, sim_o)
    if not all(checks.values()):
        raise RuntimeError([key for key, value in checks.items() if not value])
    sim_anchor = core.external_anchor_table(sim_o_sources)

    pieces = []
    for args in [
        (scaffold_i, scaffold_o, scaffold_anchor, "scaffold"),
        (sim_i, sim_o, sim_anchor, "similarity_cluster"),
    ]:
        pieces.append(summarize_regime(core, *args))
    units = pd.concat([piece[0] for piece in pieces], ignore_index=True)
    summary = pd.concat([piece[1] for piece in pieces], ignore_index=True)
    diversity = pd.concat([piece[2] for piece in pieces], ignore_index=True)
    stability = pd.concat([piece[3] for piece in pieces], ignore_index=True)
    concordance = direction_concordance(summary)

    split_integrity = {
        "manifest_rows": int(len(split_manifest)),
        "all_no_group_overlap": bool(split_manifest["no_group_overlap"].all()),
        "max_cross_fold_tanimoto": float(split_manifest[[
            "max_train_validation_tanimoto", "max_train_test_tanimoto", "max_validation_test_tanimoto"
        ]].max().max()),
        "threshold": 0.70,
    }
    exports = {
        "Paper31_composition_split_units.csv": units,
        "Paper31_composition_split_summary.csv": summary,
        "Paper31_composition_split_diversity.csv": diversity,
        "Paper31_composition_split_stability.csv": stability,
        "Paper31_composition_split_direction_concordance.csv": concordance,
        "Paper31_similarity_candidate_registry.csv": sim_registry,
        "Paper31_similarity_split_manifest.csv": split_manifest,
    }
    for filename, frame in exports.items():
        frame.to_csv(OUT / filename, index=False)
    audit = {
        "status": "complete", "tasks": TASKS, "seeds": SEEDS,
        "regimes": ["scaffold", "similarity_cluster"], "candidate_counts": core.KS,
        "pools": core.POOL_NAMES, "similarity_split_integrity": split_integrity,
        "balance_checks": checks,
        "inference_unit": "outer folds averaged within seed; seed is the bootstrap block",
        "rows": {filename: int(len(frame)) for filename, frame in exports.items()},
    }
    (OUT / "Paper31_composition_split_audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(audit, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
