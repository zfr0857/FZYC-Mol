from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fzyc_mol.data.standardize import audit_cleaning_frame  # noqa: E402
from fzyc_mol.datasets import DATASETS, _first_existing, load_raw_dataset  # noqa: E402


OUT = ROOT / "output" / "paper19_jcheminformatics_revision_20260712"
SEED = 20260712
BOOTSTRAPS = 10_000


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bootstrap_mean_ci(values: np.ndarray, rng: np.random.Generator) -> tuple[float, float, float]:
    values = np.asarray(values, dtype=float)
    means = np.empty(BOOTSTRAPS, dtype=float)
    for start in range(0, BOOTSTRAPS, 500):
        stop = min(start + 500, BOOTSTRAPS)
        draws = rng.choice(values, size=(stop - start, len(values)), replace=True)
        means[start:stop] = draws.mean(axis=1)
    low, high = np.quantile(means, [0.025, 0.975])
    return float(values.mean()), float(low), float(high)


def dataset_characteristics() -> pd.DataFrame:
    display = {
        "esol": ("ESOL", "log mol/L"),
        "freesolv": ("FreeSolv", "hydration free energy (kcal/mol)"),
        "lipo": ("Lipophilicity", "experimental logD"),
        "bbbp": ("BBBP", "binary label"),
        "bace": ("BACE", "binary label"),
        "clintox": ("ClinTox", "binary label"),
        "tdc_caco2_wang": ("Caco2 Wang", "dataset-provided log-permeability scale"),
        "tdc_hia_hou": ("HIA Hou", "binary label"),
        "tdc_pgp_broccatelli": ("P-gp Broccatelli", "binary label"),
    }
    roles = {
        "esol": "primary candidate-expansion audit; multiview confirmation",
        "freesolv": "primary candidate-expansion audit; multiview confirmation",
        "lipo": "primary candidate-expansion audit; multiview confirmation",
        "bbbp": "primary candidate-expansion audit; multiview confirmation",
        "bace": "primary candidate-expansion audit; multiview confirmation",
        "clintox": "primary audit; minority-class negative control",
        "tdc_caco2_wang": "primary candidate-expansion audit; multiview confirmation",
        "tdc_hia_hou": "primary candidate-expansion audit; multiview confirmation",
        "tdc_pgp_broccatelli": "primary candidate-expansion audit; multiview confirmation",
    }
    rows: list[dict[str, object]] = []
    for endpoint in display:
        spec = DATASETS[endpoint]
        raw = load_raw_dataset(endpoint, ROOT / "data")
        smiles_col = _first_existing(raw.columns, spec.smiles_candidates, "SMILES")
        target_col = _first_existing(raw.columns, spec.target_candidates, "target")
        clean, _, summary = audit_cleaning_frame(
            raw,
            smiles_col=smiles_col,
            target_col=target_col,
            task_type=spec.task_type,
        )
        y = pd.to_numeric(clean["y"], errors="coerce")
        row = {
            "endpoint": endpoint,
            "display_name": display[endpoint][0],
            "task_type": spec.task_type,
            "raw_n": int(summary["input_count"]),
            "analysis_n": int(summary["output_count"]),
            "consistent_duplicates_merged": int(summary["duplicate_consistent_merged"]),
            "conflicting_rows_excluded": int(summary["duplicate_conflict_excluded"]),
            "invalid_smiles_excluded": int(summary["invalid_smiles"]),
            "target_unit": display[endpoint][1],
            "evidence_role": roles[endpoint],
            "positive_n": int(y.sum()) if spec.task_type == "classification" else np.nan,
            "positive_rate": float(y.mean()) if spec.task_type == "classification" else np.nan,
            "target_min": float(y.min()) if spec.task_type == "regression" else np.nan,
            "target_max": float(y.max()) if spec.task_type == "regression" else np.nan,
        }
        rows.append(row)
    return pd.DataFrame(rows)


def multiview_raw_effects(rng: np.random.Generator) -> pd.DataFrame:
    path = ROOT / "results" / "reviewer_core_20260624" / "multiview_nested" / "paired_multiview_effects_long.csv"
    frame = pd.read_csv(path)
    frame = frame.loc[
        frame["comparison"] == "realized multiview validation-best gain vs Morgan-only"
    ].copy()
    rows: list[dict[str, object]] = []
    task_types = DATASETS
    for task, group in frame.groupby("task", sort=True):
        mean, low, high = bootstrap_mean_ci(group["raw_utility_gain"].to_numpy(), rng)
        task_type = task_types[task].task_type
        rows.append(
            {
                "endpoint": task,
                "task_type": task_type,
                "effect_definition": "ROC-AUC gain" if task_type == "classification" else "RMSE reduction",
                "n_paired_outer_units": len(group),
                "mean_raw_gain": mean,
                "bootstrap_ci95_low": low,
                "bootstrap_ci95_high": high,
                "positive_units": int((group["raw_utility_gain"] > 0).sum()),
            }
        )
    return pd.DataFrame(rows)


def composition_controls() -> pd.DataFrame:
    source = ROOT / "results" / "source_data" / "candidate_pool_summary.csv"
    frame = pd.read_csv(source)
    keep = frame["metric"].isin(["fixed_normalized_regret", "chance_adjusted_oracle_top3_hit"])
    return frame.loc[keep].sort_values(["metric", "mode", "pool_size"]).reset_index(drop=True)


def strong_baseline_settings() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "candidate": "RDKit-RF",
                "representation": "Morgan fingerprint",
                "learner_or_probe": "random forest; 120 trees; sqrt features; leaf size 2",
                "status": "completed on six MoleculeNet tasks",
            },
            {
                "candidate": "GNN-GCN",
                "representation": "six atom features; two 32-unit GCN layers",
                "learner_or_probe": "global mean pooling; Adam; five fixed epochs",
                "status": "completed on six MoleculeNet tasks",
            },
            {
                "candidate": "ChemBERTa",
                "representation": "DeepChem/ChemBERTa-77M-MTR frozen embedding",
                "learner_or_probe": "logistic or ridge linear probe",
                "status": "completed on six MoleculeNet tasks",
            },
            {
                "candidate": "MoLFormer",
                "representation": "IBM MoLFormer-XL-both-10pct frozen embedding",
                "learner_or_probe": "logistic or ridge linear probe",
                "status": "completed on six MoleculeNet tasks",
            },
            {
                "candidate": "Chemprop/D-MPNN",
                "representation": "message-passing molecular graph",
                "learner_or_probe": "historical three-endpoint boundary panel only",
                "status": "needs new analysis for the full frozen audit",
            },
            {
                "candidate": "TabPFN",
                "representation": "tabular molecular descriptors",
                "learner_or_probe": "runtime unavailable in the frozen environment",
                "status": "needs new analysis",
            },
        ]
    )


def reliability_summary() -> pd.DataFrame:
    base = ROOT / "output" / "sci1_mechanism_uq_decision_20260707"
    conformal = pd.read_csv(base / "conformal_crossfold_summary.csv")
    cqr = pd.read_csv(base / "cqr_regression_summary.csv")
    ensemble = pd.read_csv(base / "ensemble_uncertainty_summary.csv")
    rows: list[dict[str, object]] = []
    c90 = conformal.loc[np.isclose(conformal["target_coverage"], 0.9)]
    for method, group in c90.groupby("method"):
        group = group.dropna(subset=["mean_class_1_coverage", "mean_set_size"])
        if group.empty:
            continue
        rows.append(
            {
                "analysis": "classification conformal",
                "method_or_stratum": method,
                "estimate": float(group["mean_class_1_coverage"].mean()),
                "secondary_estimate": float(group["mean_set_size"].mean()),
                "interpretation": "minority-class coverage; secondary estimate is set size",
            }
        )
    q90 = cqr.loc[np.isclose(cqr["target_coverage"], 0.9)]
    rows.append(
        {
            "analysis": "conformalized quantile regression",
            "method_or_stratum": "CQR at 90% target coverage",
            "estimate": float(q90["mean_coverage"].mean()),
            "secondary_estimate": float(q90["mean_interval_width"].mean()),
            "interpretation": "mean marginal coverage; secondary estimate is raw interval width",
        }
    )
    rows.append(
        {
            "analysis": "ensemble uncertainty",
            "method_or_stratum": "top-10% high-error enrichment",
            "estimate": float(ensemble["mean_top10_high_error_enrichment"].mean()),
            "secondary_estimate": float(ensemble["mean_uncertainty_error_spearman"].mean()),
            "interpretation": "error enrichment; secondary estimate is uncertainty-error Spearman",
        }
    )
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    outputs = {
        "dataset_characteristics.csv": dataset_characteristics(),
        "multiview_endpoint_raw_gain.csv": multiview_raw_effects(rng),
        "candidate_composition_controls.csv": composition_controls(),
        "strong_baseline_settings.csv": strong_baseline_settings(),
        "reliability_summary.csv": reliability_summary(),
    }
    for name, frame in outputs.items():
        frame.to_csv(OUT / name, index=False)

    source_files = [
        ROOT / "results" / "reviewer_core_20260624" / "multiview_nested" / "paired_multiview_effects_long.csv",
        ROOT / "results" / "source_data" / "candidate_pool_summary.csv",
        ROOT / "output" / "sci1_hardening_20260707" / "six_task_strong_baseline_outer_predictions.csv",
        ROOT / "output" / "sci1_mechanism_uq_decision_20260707" / "conformal_crossfold_summary.csv",
    ]
    audit = {
        "analysis_type": "post-lock derived summaries from existing frozen outputs",
        "seed": SEED,
        "bootstrap_resamples": BOOTSTRAPS,
        "created_outputs": {name: len(frame) for name, frame in outputs.items()},
        "source_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in source_files},
        "claim_limits": [
            "No new model fitting was performed by this script.",
            "The outer audit is not an independent confirmation set.",
            "Regression outcomes remain endpoint-specific on their original scales.",
            "Chemprop/D-MPNN full-audit training and TabPFN training need new analysis.",
        ],
    }
    (OUT / "derived_analysis_audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(audit["created_outputs"], indent=2))


if __name__ == "__main__":
    main()
