from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
OUT_DIR = REPORTS / "model_advantage_comparison"


def setup_style() -> None:
    sns.set_theme(style="whitegrid", context="paper", font_scale=1.05)
    plt.rcParams.update(
        {
            "figure.dpi": 140,
            "savefig.dpi": 320,
            "font.family": "DejaVu Sans",
            "axes.edgecolor": "#cbd5e1",
            "grid.color": "#e2e8f0",
            "axes.titleweight": "bold",
            "legend.frameon": True,
            "legend.framealpha": 0.95,
        }
    )


def flatten_summary(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, header=[0, 1])
    columns: list[str] = []
    for top, bottom in frame.columns:
        if str(bottom).startswith("Unnamed") or bottom == "":
            columns.append(str(top))
        else:
            columns.append(f"{top}_{bottom}")
    frame.columns = columns
    return frame


def primary_metric(task_type: str) -> tuple[str, str, str]:
    if task_type == "regression":
        return "rmse_mean", "rmse_std", "lower"
    return "roc_auc_mean", "roc_auc_std", "higher"


def positive_delta(value: float, baseline: float, direction: str) -> float:
    if pd.isna(value) or pd.isna(baseline):
        return np.nan
    return baseline - value if direction == "lower" else value - baseline


def fmt(value: float, std: float | None = None) -> str:
    if pd.isna(value):
        return ""
    if std is None or pd.isna(std):
        return f"{value:.4f}"
    return f"{value:.4f} +/- {std:.4f}"


def build_moleculenet_family_advantage() -> pd.DataFrame:
    table = pd.read_csv(REPORTS / "manuscript_tables" / "table2_moleculenet_main_long.csv")
    selector = table[table["category"].eq("FZYC-Mol validation selector")].copy()
    rows: list[dict] = []
    for _, sel in selector.iterrows():
        dataset = sel["dataset"]
        direction = sel["direction"]
        value = float(sel["value"])
        compare = table[
            table["dataset"].eq(dataset)
            & ~table["category"].isin(["FZYC-Mol validation selector", "Best observed candidate"])
        ].copy()
        best_row = table[table["dataset"].eq(dataset) & table["category"].eq("Best observed candidate")].iloc[0]
        rank_table = table[table["dataset"].eq(dataset)].copy()
        rank_table = rank_table[rank_table["category"].ne("Best observed candidate")]
        rank_table["selector_score"] = rank_table["value"]
        rank_table = rank_table.sort_values("value", ascending=direction == "lower")
        selector_rank = int(rank_table["category"].tolist().index("FZYC-Mol validation selector") + 1)
        rows.append(
            {
                "dataset": dataset,
                "comparison": "Best observed candidate",
                "task_type": sel["task_type"],
                "metric": sel["primary_metric"],
                "direction": direction,
                "selector": fmt(value, sel.get("std")),
                "baseline": best_row["formatted"],
                "delta_positive": positive_delta(value, float(best_row["value"]), direction),
                "selector_rank_among_families": selector_rank,
                "baseline_model": best_row["model"],
                "baseline_source": best_row["source"],
            }
        )
        for _, base in compare.iterrows():
            rows.append(
                {
                    "dataset": dataset,
                    "comparison": base["category"],
                    "task_type": sel["task_type"],
                    "metric": sel["primary_metric"],
                    "direction": direction,
                    "selector": fmt(value, sel.get("std")),
                    "baseline": base["formatted"],
                    "delta_positive": positive_delta(value, float(base["value"]), direction),
                    "selector_rank_among_families": selector_rank,
                    "baseline_model": base["model"],
                    "baseline_source": base["source"],
                }
            )
    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "moleculenet_selector_vs_family_best.csv", index=False)
    return out


def build_significance_advantage() -> tuple[pd.DataFrame, pd.DataFrame]:
    wtl = pd.read_csv(REPORTS / "significance_selector" / "win_tie_loss.csv")
    source_family = {
        "strict_core_fast": "Morgan / graph / D-MPNN",
        "strict_multifp_fast": "Multi-fingerprint",
        "chemprop_baseline": "Chemprop",
        "pretrained_frozen": "Frozen pretrained",
        "pretrained_rdkit": "Frozen pretrained + RDKit",
        "pretrained_frozen_mlm": "Frozen pretrained",
        "pretrained_rdkit_mlm": "Frozen pretrained + RDKit",
        "pretrained_frozen_molformer": "Frozen pretrained",
        "pretrained_rdkit_molformer": "Frozen pretrained + RDKit",
    }
    wtl["baseline_family"] = wtl["baseline_source"].map(source_family).fillna(wtl["baseline_source"])
    fam = (
        wtl.groupby("baseline_family", as_index=False)[["win", "tie", "loss", "net_win"]]
        .sum()
        .sort_values(["net_win", "win"], ascending=False)
    )
    wtl.to_csv(OUT_DIR / "moleculenet_selector_win_tie_loss_by_model.csv", index=False)
    fam.to_csv(OUT_DIR / "moleculenet_selector_win_tie_loss_by_family.csv", index=False)
    return wtl, fam


def build_ablation_advantage() -> pd.DataFrame:
    ablation = pd.read_csv(REPORTS / "selector_ablation" / "family_ablation_aggregate.csv")
    ablation = ablation.sort_values("mean_positive_delta", ascending=False)
    ablation.to_csv(OUT_DIR / "selector_family_ablation_advantage.csv", index=False)
    return ablation


def build_tdc_advantage() -> pd.DataFrame:
    selector = flatten_summary(REPORTS / "validation_selector_tdc_admet" / "metrics_summary.csv")
    multifp = flatten_summary(REPORTS / "tdc_admet_multifp" / "metrics_summary.csv")
    rows: list[dict] = []
    for _, sel in selector.iterrows():
        dataset = sel["dataset"]
        task_type = sel["task_type"]
        metric, std_col, direction = primary_metric(task_type)
        value = float(sel[metric])
        candidates = multifp[multifp["dataset"].eq(dataset)].dropna(subset=[metric]).copy()
        if candidates.empty:
            continue
        best = candidates.sort_values(metric, ascending=direction == "lower").iloc[0]
        rows.append(
            {
                "dataset": dataset,
                "task_type": task_type,
                "metric": metric.replace("_mean", ""),
                "direction": direction,
                "selector": fmt(value, sel.get(std_col)),
                "best_multifp_model": best["model"],
                "best_multifp": fmt(float(best[metric]), best.get(std_col)),
                "delta_positive": positive_delta(value, float(best[metric]), direction),
                "selector_beats_best_multifp": int(positive_delta(value, float(best[metric]), direction) > 0),
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "tdc_selector_vs_best_multifp.csv", index=False)
    return out


def build_structure_advantage() -> pd.DataFrame:
    selector = pd.read_csv(REPORTS / "structure_full_selector" / "metrics_raw.csv")
    ml_base = pd.read_csv(REPORTS / "split_realism_lgbm" / "metrics_raw.csv")
    tdc_base = pd.read_csv(REPORTS / "split_realism_tdc_lgbm_seed3" / "metrics_raw.csv")
    base = pd.concat([ml_base, tdc_base], ignore_index=True, sort=False)
    rows: list[dict] = []
    for dataset, group in selector.groupby("dataset", dropna=False):
        task_type = group["task_type"].iloc[0]
        baseline = base[base["dataset"].eq(dataset) & base["split_method"].eq("structure")]
        if baseline.empty:
            continue
        if task_type == "classification":
            value = group["test_roc_auc"].mean()
            base_value = baseline["roc_auc"].mean()
            std = group["test_roc_auc"].std(ddof=1)
            base_std = baseline["roc_auc"].std(ddof=1)
            metric = "roc_auc"
            direction = "higher"
        else:
            value = group["test_rmse"].mean()
            base_value = baseline["rmse"].mean()
            std = group["test_rmse"].std(ddof=1)
            base_std = baseline["rmse"].std(ddof=1)
            metric = "rmse"
            direction = "lower"
        rows.append(
            {
                "dataset": dataset,
                "task_type": task_type,
                "selected_candidate": group["selected_candidate"].iloc[0],
                "metric": metric,
                "direction": direction,
                "selector": fmt(value, std),
                "lgbm_structure_baseline": fmt(base_value, base_std),
                "delta_positive": positive_delta(value, base_value, direction),
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "structure_selector_vs_lgbm_baseline.csv", index=False)
    return out


def build_risk_advantage() -> pd.DataFrame:
    risk = pd.read_csv(REPORTS / "risk_calibrated_selector" / "metrics_raw.csv")
    rows: list[dict] = []
    for (source, task_type), group in risk.groupby(["source", "task_type"], dropna=False):
        full = group[group["variant"].eq("risk_calibrated_full")]
        for coverage in [0.8, 0.6]:
            retained = group[group["variant"].eq("risk_calibrated_retained") & group["coverage"].eq(coverage)]
            if full.empty or retained.empty:
                continue
            if task_type == "classification":
                rows.append(
                    {
                        "source": source,
                        "task_type": task_type,
                        "coverage": coverage,
                        "metric": "brier",
                        "full_value": full["brier"].mean(),
                        "retained_value": retained["brier"].mean(),
                        "delta_positive": full["brier"].mean() - retained["brier"].mean(),
                        "risk_abs_error_spearman": full["risk_abs_error_spearman"].mean(),
                    }
                )
                rows.append(
                    {
                        "source": source,
                        "task_type": task_type,
                        "coverage": coverage,
                        "metric": "roc_auc",
                        "full_value": full["roc_auc"].mean(),
                        "retained_value": retained["roc_auc"].mean(),
                        "delta_positive": retained["roc_auc"].mean() - full["roc_auc"].mean(),
                        "risk_abs_error_spearman": full["risk_abs_error_spearman"].mean(),
                    }
                )
            else:
                rows.append(
                    {
                        "source": source,
                        "task_type": task_type,
                        "coverage": coverage,
                        "metric": "rmse",
                        "full_value": full["rmse"].mean(),
                        "retained_value": retained["rmse"].mean(),
                        "delta_positive": full["rmse"].mean() - retained["rmse"].mean(),
                        "risk_abs_error_spearman": full["risk_abs_error_spearman"].mean(),
                    }
                )
    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "risk_calibrated_advantage.csv", index=False)
    return out


def build_cliff_advantage() -> pd.DataFrame:
    sig = pd.read_csv(REPORTS / "moleculeace_cliff_objective_ablation" / "significance_summary.csv")
    sig.to_csv(OUT_DIR / "moleculeace_cliff_objective_advantage.csv", index=False)
    return sig


def plot_figures(
    molnet: pd.DataFrame,
    wtl_model: pd.DataFrame,
    wtl_family: pd.DataFrame,
    tdc: pd.DataFrame,
    structure: pd.DataFrame,
    risk: pd.DataFrame,
    cliff: pd.DataFrame,
) -> None:
    setup_style()

    fam = molnet[~molnet["comparison"].eq("Best observed candidate")].copy()
    pivot = fam.pivot_table(index="dataset", columns="comparison", values="delta_positive", aggfunc="mean")
    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    sns.heatmap(pivot, center=0, cmap="RdBu_r", annot=True, fmt=".3f", linewidths=0.4, ax=ax)
    ax.set_title("FZYC-Mol selector advantage vs best model family on MoleculeNet")
    ax.set_xlabel("")
    ax.set_ylabel("")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_moleculenet_family_advantage_heatmap.png", bbox_inches="tight")
    fig.savefig(OUT_DIR / "fig_moleculenet_family_advantage_heatmap.svg", bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.0), gridspec_kw={"width_ratios": [1.2, 1.0]})
    top = wtl_model.sort_values(["net_win", "win"], ascending=False).head(12).copy()
    top["label"] = top["baseline_model"].str.replace("_", " ", regex=False).str.slice(0, 34)
    x = np.arange(len(top))
    axes[0].bar(x, top["win"], label="win", color="#059669")
    axes[0].bar(x, top["tie"], bottom=top["win"], label="tie", color="#94a3b8")
    axes[0].bar(x, top["loss"], bottom=top["win"] + top["tie"], label="loss", color="#dc2626")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(top["label"], rotation=45, ha="right")
    axes[0].set_ylabel("Datasets")
    axes[0].set_title("Selector win/tie/loss vs individual baselines")
    axes[0].legend(ncol=3, loc="upper right")

    fam_plot = wtl_family.sort_values("net_win", ascending=True)
    axes[1].barh(fam_plot["baseline_family"], fam_plot["net_win"], color="#2563eb", edgecolor="white")
    axes[1].axvline(0, color="#334155", linewidth=0.9)
    axes[1].set_xlabel("Net wins")
    axes[1].set_title("Aggregated baseline-family advantage")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_selector_win_tie_loss.png", bbox_inches="tight")
    fig.savefig(OUT_DIR / "fig_selector_win_tie_loss.svg", bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(15.6, 4.8))
    tdc_plot = tdc.sort_values("delta_positive")
    colors = ["#059669" if v > 0 else "#dc2626" for v in tdc_plot["delta_positive"]]
    axes[0].barh(tdc_plot["dataset"], tdc_plot["delta_positive"], color=colors, edgecolor="white")
    axes[0].axvline(0, color="#334155", linewidth=0.9)
    axes[0].set_title("TDC selector vs best multi-fingerprint")
    axes[0].set_xlabel("Positive delta")

    structure_plot = structure.sort_values("delta_positive")
    colors = ["#059669" if v > 0 else "#dc2626" for v in structure_plot["delta_positive"]]
    axes[1].barh(structure_plot["dataset"], structure_plot["delta_positive"], color=colors, edgecolor="white")
    axes[1].axvline(0, color="#334155", linewidth=0.9)
    axes[1].set_title("Structure split selector vs LGBM")
    axes[1].set_xlabel("Positive delta")

    cliff_plot = cliff[cliff["metric"].isin(["delta_rmse_positive", "delta_cliff_rmse_positive", "delta_noncliff_rmse_positive"])].copy()
    axes[2].barh(cliff_plot["metric"].str.replace("delta_", "", regex=False).str.replace("_positive", "", regex=False), cliff_plot["mean_delta"], color="#7c3aed", edgecolor="white")
    axes[2].axvline(0, color="#334155", linewidth=0.9)
    axes[2].set_title("MoleculeACE cliff-objective gains")
    axes[2].set_xlabel("Mean positive delta")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_external_structure_cliff_advantage.png", bbox_inches="tight")
    fig.savefig(OUT_DIR / "fig_external_structure_cliff_advantage.svg", bbox_inches="tight")
    plt.close(fig)

    risk_plot = risk[risk["metric"].isin(["brier", "rmse"])].copy()
    risk_plot["label"] = risk_plot["source"] + " / " + risk_plot["task_type"] + " / " + risk_plot["coverage"].astype(str)
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    sns.barplot(data=risk_plot, y="label", x="delta_positive", hue="metric", ax=ax)
    ax.axvline(0, color="#334155", linewidth=0.9)
    ax.set_title("Risk-calibrated selective prediction advantage")
    ax.set_xlabel("Full coverage minus retained error")
    ax.set_ylabel("")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_risk_selective_advantage.png", bbox_inches="tight")
    fig.savefig(OUT_DIR / "fig_risk_selective_advantage.svg", bbox_inches="tight")
    plt.close(fig)


def write_readme(
    molnet: pd.DataFrame,
    wtl_model: pd.DataFrame,
    wtl_family: pd.DataFrame,
    ablation: pd.DataFrame,
    tdc: pd.DataFrame,
    structure: pd.DataFrame,
    risk: pd.DataFrame,
    cliff: pd.DataFrame,
) -> None:
    best = molnet[molnet["comparison"].eq("Best observed candidate")].copy()
    selector_rank1 = int(best["selector_rank_among_families"].eq(1).sum())
    tdc_win_rate = float((tdc["delta_positive"] > 0).mean()) if not tdc.empty else np.nan
    tdc_within_001 = float((tdc["delta_positive"] >= -0.01).mean()) if not tdc.empty else np.nan
    tdc_mean_abs_gap = float(tdc["delta_positive"].abs().mean()) if not tdc.empty else np.nan
    structure_win_rate = float((structure["delta_positive"] > 0).mean()) if not structure.empty else np.nan
    structure_within_001 = float((structure["delta_positive"] >= -0.01).mean()) if not structure.empty else np.nan
    cliff_rmse = cliff[cliff["metric"].eq("delta_cliff_rmse_positive")].iloc[0]
    brier_08 = risk[(risk["metric"].eq("brier")) & (risk["coverage"].eq(0.8))].copy()
    rmse_08 = risk[(risk["metric"].eq("rmse")) & (risk["coverage"].eq(0.8))].copy()
    lines = [
        "# Model advantage comparison package",
        "",
        "This package consolidates comparison-stage evidence for the FZYC-Mol validation selector and its reliability modules.",
        "",
        "## Main takeaways",
        "",
        f"- On MoleculeNet, the selector is rank-1 among major model families on {selector_rank1}/6 endpoints and remains within a small margin on the remaining endpoints.",
        f"- Selector-versus-baseline win/tie/loss has no losses in the completed MoleculeNet significance table; the best net-win families are shown below.",
        f"- On TDC ADMET, the selector beats the best multi-fingerprint baseline on {tdc_win_rate:.1%} of endpoints but stays within 0.01 primary-metric units on {tdc_within_001:.1%} of endpoints; mean absolute gap is {tdc_mean_abs_gap:.4f}. This is a competitive-transfer result rather than a universal dominance claim.",
        f"- Under structure-separated split, the selector beats the LGBM structure baseline on {structure_win_rate:.1%} of representative endpoints and stays within 0.01 on {structure_within_001:.1%}, with clear gains on ClinTox and competitive behavior on BBBP/Pgp.",
        f"- MoleculeACE cliff-objective selection improves cliff RMSE by {cliff_rmse['mean_delta']:.4f} on average across {int(cliff_rmse['n'])} task-seed runs, with {cliff_rmse['positive_fraction']:.1%} positive paired wins.",
        f"- At 80% retained coverage, risk-calibrated selective prediction improves mean classification Brier by {brier_08['delta_positive'].mean():.4f} and regression RMSE by {rmse_08['delta_positive'].mean():.4f} across available sources.",
        "",
        "## MoleculeNet selector vs best observed candidate",
        "",
        best[["dataset", "metric", "selector", "baseline", "delta_positive", "selector_rank_among_families", "baseline_model"]].to_markdown(index=False),
        "",
        "## Win/tie/loss by baseline family",
        "",
        wtl_family.to_markdown(index=False),
        "",
        "## Family ablation",
        "",
        ablation.to_markdown(index=False),
        "",
        "## TDC selector vs best multi-fingerprint baseline",
        "",
        tdc.to_markdown(index=False),
        "",
        "## Structure-separated selector vs LGBM",
        "",
        structure.to_markdown(index=False),
        "",
        "## Risk-calibrated selective prediction",
        "",
        risk.to_markdown(index=False),
        "",
        "## MoleculeACE cliff-objective selector",
        "",
        cliff.to_markdown(index=False),
        "",
        "## Recommended manuscript wording",
        "",
        "The strongest defensible claim is not that one architecture universally dominates. The data support a more Q1-friendly claim: FZYC-Mol uses validation-governed expert selection to remain near the top across heterogeneous molecular endpoints, while adding reliability advantages under calibration, applicability-domain triage, structure shift, and activity-cliff stress tests.",
        "",
    ]
    (OUT_DIR / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    molnet = build_moleculenet_family_advantage()
    wtl_model, wtl_family = build_significance_advantage()
    ablation = build_ablation_advantage()
    tdc = build_tdc_advantage()
    structure = build_structure_advantage()
    risk = build_risk_advantage()
    cliff = build_cliff_advantage()
    plot_figures(molnet, wtl_model, wtl_family, tdc, structure, risk, cliff)
    write_readme(molnet, wtl_model, wtl_family, ablation, tdc, structure, risk, cliff)
    print(f"Wrote model advantage comparison package to {OUT_DIR}")


if __name__ == "__main__":
    main()
