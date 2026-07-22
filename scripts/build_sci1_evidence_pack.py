from __future__ import annotations

import json
import math
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
STRICT = OUT / "\u5c0f\u8bba\u6587-12_\u4e25\u683c\u8865\u5b9e\u9a8c"
THICK = OUT / "\u5c0f\u8bba\u6587-11_\u52a0\u539a\u5b9e\u9a8c"
SUPP = OUT / "\u5c0f\u8bba\u6587-11_\u8865\u5145\u5206\u6790"
PACK = OUT / "\u5c0f\u8bba\u6587-13_SCI1\u8865\u5f3a\u8bc1\u636e"
RESULTS = ROOT / "results"


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def mean_ci(series: pd.Series) -> tuple[float, float, float]:
    x = pd.to_numeric(series, errors="coerce").dropna()
    if len(x) == 0:
        return (math.nan, math.nan, math.nan)
    mean = float(x.mean())
    if len(x) == 1:
        return (mean, math.nan, math.nan)
    se = float(x.std(ddof=1) / math.sqrt(len(x)))
    return (mean, mean - 1.96 * se, mean + 1.96 * se)


def flatten_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [
        "_".join(str(part) for part in col if str(part))
        if isinstance(col, tuple)
        else str(col)
        for col in df.columns
    ]
    return df


def build_strong_baseline_tables() -> dict[str, object]:
    outer = read_csv(STRICT / "combined_strong_baseline_outer_scores.csv")
    paired = read_csv(STRICT / "combined_strong_candidate_paired_effect_detail.csv")
    selection = read_csv(STRICT / "combined_strong_selection_detail.csv")
    overlap = read_csv(STRICT / "combined_strong_error_overlap_pairwise_detail.csv")
    overlap_summary = read_csv(STRICT / "combined_strong_error_overlap_pairwise_summary.csv")
    duplicate = read_csv(STRICT / "duplicate_sensitivity_summary.csv")
    runtime = read_csv(STRICT / "combined_strong_runtime_status.csv")

    if not outer.empty:
        endpoint = (
            outer.groupby(["task", "task_type", "candidate"], as_index=False)
            .agg(
                n_outer_units=("outer_utility", "size"),
                mean_outer_utility=("outer_utility", "mean"),
                sd_outer_utility=("outer_utility", "std"),
                mean_roc_auc=("roc_auc", "mean"),
                mean_pr_auc=("pr_auc", "mean"),
                mean_rmse=("rmse", "mean"),
                mean_fit_seconds=("fit_seconds", "mean"),
            )
        )
        rdkit = endpoint[endpoint["candidate"].eq("rdkit_rf")][
            ["task", "mean_outer_utility"]
        ].rename(columns={"mean_outer_utility": "rdkit_mean_outer_utility"})
        endpoint = endpoint.merge(rdkit, on="task", how="left")
        endpoint["delta_vs_rdkit_mean"] = (
            endpoint["mean_outer_utility"] - endpoint["rdkit_mean_outer_utility"]
        )
        endpoint.to_csv(PACK / "sci1_strong_baseline_endpoint_table.csv", index=False)
    else:
        endpoint = pd.DataFrame()

    if not paired.empty:
        rows = []
        for (candidate, task, task_type), sub in paired.groupby(
            ["candidate", "task", "task_type"]
        ):
            mean, lo, hi = mean_ci(sub["delta_vs_rdkit"])
            rows.append(
                {
                    "candidate": candidate,
                    "task": task,
                    "task_type": task_type,
                    "n_units": len(sub),
                    "mean_delta_vs_rdkit": mean,
                    "ci95_low": lo,
                    "ci95_high": hi,
                    "win_rate_vs_rdkit": float(sub["beats_rdkit"].mean()),
                }
            )
        paired_ci = pd.DataFrame(rows)
        paired_ci.to_csv(PACK / "sci1_strong_baseline_paired_ci.csv", index=False)
    else:
        paired_ci = pd.DataFrame()

    if not selection.empty:
        sel_summary = (
            selection.groupby(["task", "task_type"], as_index=False)
            .agg(
                n_units=("selection_loss", "size"),
                top1_hit_rate=("outer_top1_hit", "mean"),
                mean_selection_loss=("selection_loss", "mean"),
                mean_range_normalized_selection_loss=(
                    "range_normalized_selection_loss",
                    "mean",
                ),
                mean_inner_outer_spearman=("inner_outer_spearman", "mean"),
                selected_candidates=("selected_candidate", lambda s: ";".join(sorted(set(s)))),
            )
        )
        overall = pd.DataFrame(
            [
                {
                    "task": "__overall__",
                    "task_type": "mixed",
                    "n_units": len(selection),
                    "top1_hit_rate": float(selection["outer_top1_hit"].mean()),
                    "mean_selection_loss": float(selection["selection_loss"].mean()),
                    "mean_range_normalized_selection_loss": float(
                        selection["range_normalized_selection_loss"].mean()
                    ),
                    "mean_inner_outer_spearman": float(
                        selection["inner_outer_spearman"].mean()
                    ),
                    "selected_candidates": ";".join(
                        sorted(set(selection["selected_candidate"]))
                    ),
                }
            ]
        )
        sel_summary = pd.concat([sel_summary, overall], ignore_index=True)
        sel_summary.to_csv(PACK / "sci1_strong_selection_scorecard.csv", index=False)
    else:
        sel_summary = pd.DataFrame()

    if not overlap.empty:
        overlap_ext = (
            overlap.groupby(["candidate_a", "candidate_b"], as_index=False)
            .agg(
                n_units=("jaccard_error_overlap", "size"),
                mean_jaccard_error_overlap=("jaccard_error_overlap", "mean"),
                median_jaccard_error_overlap=("jaccard_error_overlap", "median"),
                min_jaccard_error_overlap=("jaccard_error_overlap", "min"),
                max_jaccard_error_overlap=("jaccard_error_overlap", "max"),
                mean_error_union=("error_union", "mean"),
                mean_error_intersection=("error_intersection", "mean"),
            )
        )
        overlap_ext.to_csv(PACK / "sci1_error_overlap_extended.csv", index=False)
    else:
        overlap_ext = overlap_summary

    if not duplicate.empty:
        duplicate = duplicate.copy()
        duplicate["abs_delta_vs_global_dedup"] = duplicate[
            "delta_vs_global_dedup"
        ].abs()
        duplicate.to_csv(PACK / "sci1_duplicate_sensitivity_extended.csv", index=False)

    completed = []
    if not runtime.empty:
        completed = runtime["status"].astype(str).tolist()
    return {
        "outer_rows": int(len(outer)),
        "inner_rows": int(len(read_csv(STRICT / "combined_strong_baseline_inner_scores.csv"))),
        "prediction_rows": int(len(read_csv(STRICT / "combined_strong_baseline_outer_predictions.csv"))),
        "paired_rows": int(len(paired)),
        "selection_units": int(len(selection)),
        "error_overlap_units": int(len(overlap)),
        "duplicate_rows": int(len(duplicate)),
        "runtime_completed_count": int(
            sum("completed" in status for status in completed)
        ),
        "runtime_rows": int(len(runtime)),
        "tabpfn_status": (
            runtime.loc[runtime["candidate"].eq("tabpfn_rdkit"), "status"].iloc[0]
            if (not runtime.empty and runtime["candidate"].eq("tabpfn_rdkit").any())
            else "not_present"
        ),
        "endpoint_rows": int(len(endpoint)),
        "paired_ci_rows": int(len(paired_ci)),
        "overlap_pair_rows": int(len(overlap_ext)),
        "selection_overall_top1": (
            float(sel_summary.loc[sel_summary["task"].eq("__overall__"), "top1_hit_rate"].iloc[0])
            if not sel_summary.empty
            else math.nan
        ),
    }


def build_reliability_boundary_scorecard() -> dict[str, object]:
    rows: list[dict[str, object]] = []

    diversity = read_csv(SUPP / "candidate_effective_diversity.csv")
    staged = read_csv(THICK / "heterogeneous_staged_pool_summary.csv")
    multiview_effects = read_csv(
        RESULTS / "reviewer_core_20260624" / "multiview_nested" / "paired_multiview_effects.csv"
    )
    conformal = read_csv(RESULTS / "reliability" / "conformal_long.csv")
    tdc = read_csv(RESULTS / "source_data" / "tdc_gate_audit.csv")
    molace = read_csv(THICK / "completion_moleculeace_gap_correlation_summary.csv")
    bro5 = read_csv(
        ROOT
        / "reports"
        / "full_missing_experiment_run_20260611"
        / "bro5_cycpept_pampa_compact_summary.csv"
    )
    bro5_bins = read_csv(
        ROOT / "reports" / "bro5_cycpept_pampa_20260611" / "tanimoto_bins_summary.csv"
    )
    lin_bins = read_csv(
        ROOT / "reports" / "bro5_linpept_20260611" / "tanimoto_bins_summary.csv"
    )

    if not diversity.empty:
        for _, r in diversity.iterrows():
            rows.append(
                {
                    "evidence_domain": "candidate-pool effective diversity",
                    "analysis": r["measure"],
                    "n_units": "",
                    "primary_value": float(r["K_eff"]),
                    "secondary_value": float(r["median_corr"]),
                    "interpretation": "The lightweight K=32 pool mostly tests selection pressure among highly correlated candidates.",
                    "residual_gap": "Does not substitute for a fully heterogeneous foundation-model panel.",
                }
            )

    if not staged.empty:
        full = staged[staged["stage_id"].eq("plus_multiview")]
        if not full.empty:
            r = full.iloc[0]
            rows.append(
                {
                    "evidence_domain": "heterogeneous multiview confirmation",
                    "analysis": "full 12-candidate multiview pool vs Morgan-only",
                    "n_units": int(r["n_units"]),
                    "primary_value": float(r["G_realized_mean"]),
                    "secondary_value": float(r["G_attain_mean"]),
                    "interpretation": "The frozen selector realized most of the attainable multiview gain.",
                    "residual_gap": "The result is not a claim that every deep baseline is superior.",
                }
            )

    if not multiview_effects.empty:
        target = multiview_effects[
            multiview_effects["comparison"].eq(
                "realized multiview validation-best gain vs Morgan-only"
            )
        ]
        if not target.empty:
            r = target.iloc[0]
            rows.append(
                {
                    "evidence_domain": "paired multiview inference",
                    "analysis": "endpoint-cluster CI for realized multiview gain",
                    "n_units": int(r["paired_outer_units"]),
                    "primary_value": float(r["mean_normalized_utility_gain"]),
                    "secondary_value": f"{r['endpoint_cluster_ci95_low']:.3f} to {r['endpoint_cluster_ci95_high']:.3f}",
                    "interpretation": "All nine endpoints had positive realized multiview gain under the frozen split.",
                    "residual_gap": "Prospective time-split ADMET validation remains pending.",
                }
            )

    if not conformal.empty:
        conf = (
            conformal.groupby(["task_type", "alpha"], as_index=False)
            .agg(
                n_units=("coverage", "size"),
                mean_coverage=("coverage", "mean"),
                min_coverage=("coverage", "min"),
                mean_target=("target_coverage", "mean"),
                mean_avg_set_size=("avg_set_size", "mean"),
                mean_width=("mean_width", "mean"),
            )
        )
        conf.to_csv(PACK / "sci1_conformal_coverage_by_alpha.csv", index=False)
        for _, r in conf.iterrows():
            rows.append(
                {
                    "evidence_domain": "prediction reliability",
                    "analysis": f"{r['task_type']} split conformal alpha={r['alpha']}",
                    "n_units": int(r["n_units"]),
                    "primary_value": float(r["mean_coverage"]),
                    "secondary_value": float(r["mean_target"]),
                    "interpretation": "Coverage is reported with target coverage rather than as a raw performance score.",
                    "residual_gap": "Not a full benchmark of uncertainty methods under every data shift.",
                }
            )

    if not tdc.empty:
        gate_counts = tdc["gate_category"].value_counts().rename_axis("gate_category").reset_index(name="n")
        gate_counts.to_csv(PACK / "sci1_tdc_gate_category_counts.csv", index=False)
        rows.append(
            {
                "evidence_domain": "external-panel reliability",
                "analysis": "TDC gate audit",
                "n_units": int(len(tdc)),
                "primary_value": int(tdc["promoted"].sum()),
                "secondary_value": float(tdc["test_delta"].mean()),
                "interpretation": "The TDC panel is used as a gate and heterogeneity check, not as a broad leaderboard claim.",
                "residual_gap": "Only three seeds per endpoint; strict prospective validation is still needed.",
            }
        )

    if not molace.empty:
        rows.append(
            {
                "evidence_domain": "activity-cliff boundary",
                "analysis": "MoleculeACE pairwise gap audit",
                "n_units": int(len(molace)),
                "primary_value": float(molace["gap_spearman"].mean()),
                "secondary_value": float(molace["direction_accuracy"].mean()),
                "interpretation": "Direction is more stable than magnitude in high-similarity cliff pairs.",
                "residual_gap": "Activity-cliff evidence remains secondary and should not be overgeneralized.",
            }
        )

    if not bro5.empty:
        bro5.to_csv(PACK / "sci1_bro5_split_summary.csv", index=False)
        random_rmse = bro5.loc[bro5["split"].eq("random"), "test_RMSE"]
        perimeter_rmse = bro5.loc[bro5["split"].eq("perimeter"), "test_RMSE"]
        rows.append(
            {
                "evidence_domain": "bRo5 boundary",
                "analysis": "cyclic peptide PAMPA split contrast",
                "n_units": int(len(bro5)),
                "primary_value": random_rmse.iloc[0] if len(random_rmse) else "",
                "secondary_value": perimeter_rmse.iloc[0] if len(perimeter_rmse) else "",
                "interpretation": "Perimeter/time splits are materially harder than random splits.",
                "residual_gap": "bRo5 results are a chemical-boundary stress test, not the main FZYC-Mol endpoint panel.",
            }
        )

    if not bro5_bins.empty:
        rows.append(
            {
                "evidence_domain": "nearest-neighbour boundary",
                "analysis": "cyclic peptide PAMPA Tanimoto bins",
                "n_units": int(len(bro5_bins)),
                "primary_value": float(bro5_bins["mean_abs_error"].mean()),
                "secondary_value": float(bro5_bins["mean_nn_tanimoto"].mean()),
                "interpretation": "Nearest-neighbour similarity is retained as a boundary descriptor.",
                "residual_gap": "Bins are descriptive and do not replace external validation.",
            }
        )

    if not lin_bins.empty:
        rows.append(
            {
                "evidence_domain": "nearest-neighbour boundary",
                "analysis": "linear peptide permeability Tanimoto bins",
                "n_units": int(len(lin_bins)),
                "primary_value": float(lin_bins["roc_auc"].mean()),
                "secondary_value": float(lin_bins["mean_nn_tanimoto"].mean()),
                "interpretation": "Classification reliability is stratified by chemical neighbourhood.",
                "residual_gap": "Permeability panel remains an auxiliary chemical-boundary analysis.",
            }
        )

    scorecard = pd.DataFrame(rows)
    scorecard.to_csv(PACK / "sci1_reliability_boundary_scorecard.csv", index=False)
    return {"scorecard_rows": int(len(scorecard))}


def build_literature_gap_matrix() -> dict[str, object]:
    rows = [
        {
            "challenge": "Standard benchmarks and task comparability",
            "primary_sources": "MoleculeNet; Therapeutics Data Commons",
            "high_impact_expectation": "Use explicit datasets, splits, metrics and public task definitions.",
            "current_evidence": "Nine-endpoint frozen 3x3x5 protocol plus TDC gate audit and source-data tables.",
            "residual_gap": "No claim of full MoleculeNet/TDC leaderboard dominance; time-external prospective validation is pending.",
            "manuscript_action": "Frame FZYC-Mol as validation governance, not a universal predictor.",
        },
        {
            "challenge": "Modern strong baselines and foundation-model era comparisons",
            "primary_sources": "Chemprop/D-MPNN; ChemBERTa; MoLFormer; large empirical MPP studies",
            "high_impact_expectation": "Compare against strong descriptor, graph, message-passing and pretrained language-model baselines under the same split.",
            "current_evidence": "RDKit RF, GNN-GCN, Chemprop/D-MPNN, ChemBERTa and MoLFormer completed on the representative ESOL/BACE/ClinTox 3x3x5 panel.",
            "residual_gap": "Nine-endpoint full deep/foundation-model retraining and TabPFN are not complete; TabPFN remains runtime unavailable.",
            "manuscript_action": "Move strong-baseline claims to a representative boundary test and state the remaining gap explicitly.",
        },
        {
            "challenge": "Model-selection bias and validation reuse",
            "primary_sources": "Cawley and Talbot; Varma and Simon; nested QSAR evaluation literature",
            "high_impact_expectation": "Separate model selection from outer assessment and preserve negative results.",
            "current_evidence": "Nested 3x3x5 selection, K-expansion experiment, random-rank negative control, signal-recovery positive control and frozen decision cards.",
            "residual_gap": "Third-party cold-start rerun and DOI release remain to be completed before submission.",
            "manuscript_action": "Keep the main claim on selection loss rather than algorithmic superiority.",
        },
        {
            "challenge": "Distribution shift, chemical boundaries and activity cliffs",
            "primary_sources": "MoleculeACE; activity-cliff and applicability-domain literature; bRo5 stress tests",
            "high_impact_expectation": "Report where average benchmark performance does not transfer.",
            "current_evidence": "MoleculeACE pairwise gap audit, bRo5 split contrast, Tanimoto-bin summaries and TDC gate categories.",
            "residual_gap": "Boundary analyses are secondary; they should not be described as complete prospective deployment validation.",
            "manuscript_action": "Group these analyses as reliability and chemical-boundary evidence.",
        },
        {
            "challenge": "Prediction reliability and uncertainty under shift",
            "primary_sources": "Conformal prediction; molecular UQ under data shifts",
            "high_impact_expectation": "Quantify reliability at the sample level, not only endpoint means.",
            "current_evidence": "Risk curves, E-AURC, split conformal coverage and label-conditional coverage summaries.",
            "residual_gap": "Not a head-to-head benchmark of all uncertainty estimators.",
            "manuscript_action": "Report reliability as bounded evidence with target coverage and limitations.",
        },
        {
            "challenge": "Reproducibility and transparent reporting",
            "primary_sources": "Cheminformatics reproducibility guidance",
            "high_impact_expectation": "Provide source data, code, audit logs, negative results and release metadata.",
            "current_evidence": "Generated source-data tables, XML audits, claim-evidence mapping and runtime-status logs.",
            "residual_gap": "Formal Zenodo DOI, clean environment lockfile and independent rerun are still open.",
            "manuscript_action": "Add a submission-readiness audit and avoid unsupported completion claims.",
        },
    ]
    df = pd.DataFrame(rows)
    df.to_csv(PACK / "sci1_literature_gap_response_matrix.csv", index=False)
    return {"gap_rows": int(len(df))}


def xml_errors(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"missing: {path}"]
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if name.endswith(".xml"):
                try:
                    ElementTree.fromstring(zf.read(name))
                except Exception as exc:
                    errors.append(f"{name}: {exc}")
    return errors


def main() -> None:
    PACK.mkdir(parents=True, exist_ok=True)
    strong = build_strong_baseline_tables()
    reliability = build_reliability_boundary_scorecard()
    gap = build_literature_gap_matrix()

    audit = {
        "output_dir": str(PACK),
        "strong_baseline": strong,
        "reliability_boundary": reliability,
        "literature_gap_matrix": gap,
        "required_outputs": [
            "sci1_literature_gap_response_matrix.csv",
            "sci1_reliability_boundary_scorecard.csv",
            "sci1_strong_baseline_endpoint_table.csv",
            "sci1_strong_baseline_paired_ci.csv",
            "sci1_error_overlap_extended.csv",
            "sci1_duplicate_sensitivity_extended.csv",
            "sci1_conformal_coverage_by_alpha.csv",
            "sci1_tdc_gate_category_counts.csv",
            "sci1_bro5_split_summary.csv",
        ],
    }
    missing = [name for name in audit["required_outputs"] if not (PACK / name).exists()]
    audit["missing_outputs"] = missing
    audit["passed"] = not missing and strong["runtime_completed_count"] >= 5
    (PACK / "sci1_submission_readiness_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
