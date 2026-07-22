from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TABLE_DIR = ROOT / "reports" / "manuscript_tables"
FIG_DIR = ROOT / "reports" / "manuscript_figures"
Q1_DIR = ROOT / "reports" / "q1_upgrade_method_modules"


def ensure_dirs() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)


def copy_q1_artifacts() -> None:
    figure_map = {
        "fig_structure_full_selector": "fig8_structure_full_selector",
        "fig_risk_calibrated_selector": "fig9_risk_calibrated_selector",
        "fig_moleculeace_cliff_objective_selector": "fig10_moleculeace_cliff_objective_selector",
    }
    for src_stem, dst_stem in figure_map.items():
        for suffix in [".png", ".svg"]:
            src = Q1_DIR / f"{src_stem}{suffix}"
            dst = FIG_DIR / f"{dst_stem}{suffix}"
            if src.exists():
                shutil.copyfile(src, dst)

    table_map = {
        "structure_selector_key_metrics.csv": "table8_structure_full_selector.csv",
        "risk_calibrated_coverage_summary.csv": "table9_risk_calibrated_selector.csv",
        "moleculeace_cliff_objective_selector_summary.csv": "table10_moleculeace_cliff_objective_selector.csv",
        "moleculeace_cliff_objective_selector_pairs.csv": "table10_moleculeace_cliff_objective_selector_pairs.csv",
    }
    for src_name, dst_name in table_map.items():
        src = Q1_DIR / src_name
        if src.exists():
            shutil.copyfile(src, TABLE_DIR / dst_name)


def safe_mean(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns:
        return np.nan
    values = pd.to_numeric(frame[column], errors="coerce")
    return float(values.mean()) if values.notna().any() else np.nan


def positive_fraction(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns:
        return np.nan
    values = pd.to_numeric(frame[column], errors="coerce").dropna()
    return float((values > 0).mean()) if len(values) else np.nan


def add_row(rows: list[dict[str, object]], **kwargs: object) -> None:
    defaults = {
        "module": "",
        "source": "",
        "task_type": "",
        "setting": "",
        "n": "",
        "primary_reliability_signal": "",
        "effect_size": "",
        "secondary_signal": "",
        "literature_link": "",
        "manuscript_use": "",
    }
    defaults.update(kwargs)
    rows.append(defaults)


def build_reliability_summary() -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    calibration = pd.read_csv(ROOT / "reports" / "validation_calibration" / "calibration_improvement_by_dataset.csv")
    add_row(
        rows,
        module="validation-only calibration",
        source="all classification sources",
        task_type="classification",
        setting="uncalibrated vs validation-selected Platt/isotonic",
        n=int(calibration["n_runs"].sum()),
        primary_reliability_signal="ECE improvement",
        effect_size=f"{safe_mean(calibration, 'mean_delta_ece_positive'):.4f}",
        secondary_signal=(
            f"Brier improvement {safe_mean(calibration, 'mean_delta_brier_positive'):.4f}; "
            f"positive ECE fraction {positive_fraction(calibration, 'mean_delta_ece_positive'):.2f}; "
            f"mean ROC-AUC tradeoff {safe_mean(calibration, 'mean_delta_roc_auc'):.4f}"
        ),
        literature_link="ADMET reliability; AD/UQ under nonrandom splits",
        manuscript_use="Table 11 / reliability section",
    )

    ad_gated = pd.read_csv(ROOT / "reports" / "ad_gated_selector" / "ad_gated_improvement_summary.csv")
    key_specs = [
        ("moleculenet_selector", "classification", "hybrid_ad", 0.6, "ROC-AUC / Brier"),
        ("moleculenet_selector", "regression", "ensemble_std", 0.6, "RMSE"),
        ("tdc_admet_selector", "classification", "hybrid_ad", 0.6, "ROC-AUC / Brier"),
        ("tdc_admet_selector", "regression", "ensemble_std", 0.6, "RMSE"),
    ]
    for source, task_type, risk_score, coverage, signal in key_specs:
        sub = ad_gated[
            ad_gated["source"].eq(source)
            & ad_gated["task_type"].eq(task_type)
            & ad_gated["risk_score"].eq(risk_score)
            & np.isclose(ad_gated["coverage"].astype(float), coverage)
        ]
        if sub.empty:
            continue
        row = sub.iloc[0]
        if task_type == "classification":
            effect = (
                f"ROC-AUC +{row['mean_delta_roc_auc_positive']:.4f}; "
                f"Brier +{row['mean_delta_brier_positive']:.4f}"
            )
            secondary = f"PR-AUC +{row['mean_delta_pr_auc_positive']:.4f}; ECE +{row['mean_delta_ece_positive']:.4f}"
        else:
            effect = f"RMSE improvement +{row['mean_delta_rmse_positive']:.4f}"
            secondary = "low-risk retained subset improves error"
        add_row(
            rows,
            module="AD-gated selective prediction",
            source=source,
            task_type=task_type,
            setting=f"{risk_score}, retained coverage={coverage:.1f}",
            n=int(row["n_runs"]),
            primary_reliability_signal=signal,
            effect_size=effect,
            secondary_signal=secondary,
            literature_link="applicability domain; embedding/hybrid AD; edge of chemical space",
            manuscript_use="Figure 9 / Table 11",
        )

    risk_cal = pd.read_csv(Q1_DIR / "risk_calibrated_coverage_summary.csv")
    for source, task_type in [
        ("moleculenet", "classification"),
        ("moleculenet", "regression"),
        ("tdc_admet", "classification"),
        ("tdc_admet", "regression"),
        ("structure", "classification"),
        ("structure", "regression"),
    ]:
        full = risk_cal[
            risk_cal["source"].eq(source)
            & risk_cal["task_type"].eq(task_type)
            & risk_cal["variant"].eq("risk_calibrated_full")
            & np.isclose(risk_cal["coverage"].astype(float), 1.0)
        ]
        retained = risk_cal[
            risk_cal["source"].eq(source)
            & risk_cal["task_type"].eq(task_type)
            & risk_cal["variant"].eq("risk_calibrated_retained")
            & np.isclose(risk_cal["coverage"].astype(float), 0.6)
        ]
        if full.empty or retained.empty:
            continue
        frow = full.iloc[0]
        rrow = retained.iloc[0]
        if task_type == "classification":
            primary = "Brier / risk-error Spearman"
            effect = f"Brier {frow['brier']:.4f} -> {rrow['brier']:.4f}"
            secondary = (
                f"Spearman {frow['risk_abs_error_spearman']:.4f}; "
                f"ROC-AUC {frow['roc_auc']:.4f} -> {rrow['roc_auc']:.4f}"
            )
        else:
            primary = "RMSE / risk-error Spearman"
            effect = f"RMSE {frow['rmse']:.4f} -> {rrow['rmse']:.4f}"
            secondary = f"Spearman {frow['risk_abs_error_spearman']:.4f}"
        add_row(
            rows,
            module="risk-calibrated validation selector",
            source=source,
            task_type=task_type,
            setting="full coverage vs 60% retained low-risk subset",
            n=int(frow["n_runs"]),
            primary_reliability_signal=primary,
            effect_size=effect,
            secondary_signal=secondary,
            literature_link="ADMET reliability; conformal/AD reliability under shifts",
            manuscript_use="Figure 9 / Table 11",
        )

    recon = pd.read_csv(ROOT / "reports" / "reconstruction_ood" / "reconstruction_ood_metrics.csv")
    recon_summary = (
        recon.groupby(["score", "task_type"], as_index=False)
        .agg(
            n=("score", "size"),
            spearman=("spearman_abs_error", "mean"),
            risk_coverage_auc=("risk_coverage_auc", "mean"),
            enrichment=("top10pct_high_error_enrichment", "mean"),
        )
        .sort_values("spearman", ascending=False)
    )
    for _, row in recon_summary.iterrows():
        add_row(
            rows,
            module="reconstruction-based unfamiliarity",
            source="validation selector predictions",
            task_type=row["task_type"],
            setting=row["score"],
            n=int(row["n"]),
            primary_reliability_signal="Spearman with absolute error",
            effect_size=f"{row['spearman']:.4f}",
            secondary_signal=f"risk-coverage AUC {row['risk_coverage_auc']:.4f}; top-10% enrichment {row['enrichment']:.4f}",
            literature_link="Molecular deep learning at the edge of chemical space",
            manuscript_use="Table 11 / reliability narrative",
        )

    conformal = pd.read_csv(ROOT / "reports" / "conformal_activity" / "conformal_summary.csv")
    for task_type, sub in conformal.groupby("task_type"):
        if task_type == "classification":
            secondary = f"avg set size {safe_mean(sub, 'avg_set_size'):.4f}; singleton rate {safe_mean(sub, 'singleton_rate'):.4f}"
        else:
            secondary = f"mean width {safe_mean(sub, 'mean_width'):.4f}; median abs error {safe_mean(sub, 'median_abs_error'):.4f}"
        add_row(
            rows,
            module="split conformal prediction",
            source="MoleculeNet selector",
            task_type=task_type,
            setting="alpha-controlled prediction sets/intervals",
            n=len(sub),
            primary_reliability_signal="empirical coverage",
            effect_size=f"{safe_mean(sub, 'coverage'):.4f}",
            secondary_signal=secondary,
            literature_link="conformal prediction + explicit applicability domain",
            manuscript_use="Table 11 / supplementary reliability",
        )

    table = pd.DataFrame(rows)
    table.to_csv(TABLE_DIR / "table11_reliability_summary.csv", index=False)
    return table


def build_negative_boundary_table() -> pd.DataFrame:
    structure = pd.read_csv(Q1_DIR / "structure_selector_key_metrics.csv")
    baseline_values = {
        "bace": 0.7853,
        "bbbp": 0.8975,
        "clintox": 0.8818,
        "tdc_pgp_broccatelli": 0.8524,
        "tdc_caco2_wang": 0.4520,
    }
    rows: list[dict[str, object]] = []
    for _, row in structure.iterrows():
        dataset = row["dataset"]
        selector = float(row["primary_mean"])
        baseline = baseline_values.get(dataset, np.nan)
        if row["task_type"] == "regression":
            delta = baseline - selector
            direction = "positive means lower selector RMSE"
        else:
            delta = selector - baseline
            direction = "positive means higher selector ROC-AUC"
        rows.append(
            {
                "dataset": dataset,
                "task_type": row["task_type"],
                "selected_candidate": row["selected_candidate"],
                "selector_primary_metric": row["primary_metric"],
                "selector_value": selector,
                "lgbm_structure_baseline": baseline,
                "delta_positive": delta,
                "direction": direction,
                "manuscript_interpretation": "honest boundary case" if delta < 0 else "selector competitive or better",
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(TABLE_DIR / "table12_structure_selector_boundary_cases.csv", index=False)
    return out


def write_update_note(reliability: pd.DataFrame, boundary: pd.DataFrame) -> None:
    lines = [
        "# Literature-driven manuscript update manifest",
        "",
        "This update integrates the 2026-05-28 Q1 method-upgrade artifacts into the manuscript-facing package.",
        "",
        "## Added figures",
        "",
        "- `fig8_structure_full_selector.png/svg`",
        "- `fig9_risk_calibrated_selector.png/svg`",
        "- `fig10_moleculeace_cliff_objective_selector.png/svg`",
        "",
        "## Added tables",
        "",
        "- `table8_structure_full_selector.csv`",
        "- `table9_risk_calibrated_selector.csv`",
        "- `table10_moleculeace_cliff_objective_selector.csv`",
        "- `table10_moleculeace_cliff_objective_selector_pairs.csv`",
        "- `table11_reliability_summary.csv`",
        "- `table12_structure_selector_boundary_cases.csv`",
        "",
        "## Reliability summary",
        "",
        f"- Rows: {len(reliability)}",
        "- Main literature links: reconstruction unfamiliarity, AD/UQ under nonrandom splits, ADMET reliability, AD-gated selective prediction.",
        "",
        "## Boundary cases",
        "",
        f"- Rows: {len(boundary)}",
        "- Negative deltas are retained deliberately to frame the method as endpoint-adaptive reliability selection, not universal SOTA.",
        "",
    ]
    (ROOT / "reports" / "literature_driven_manuscript_update_20260529.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> None:
    ensure_dirs()
    copy_q1_artifacts()
    reliability = build_reliability_summary()
    boundary = build_negative_boundary_table()
    write_update_note(reliability, boundary)
    print(f"Updated manuscript figures in {FIG_DIR}")
    print(f"Updated manuscript tables in {TABLE_DIR}")
    print(f"Wrote reliability rows: {len(reliability)}")


if __name__ == "__main__":
    main()
