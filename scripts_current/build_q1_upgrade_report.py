from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "reports" / "q1_upgrade_method_modules"


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


def mean_std(values: pd.Series) -> str:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if numeric.empty:
        return ""
    if len(numeric) == 1:
        return f"{numeric.iloc[0]:.4f}"
    return f"{numeric.mean():.4f} +/- {numeric.std(ddof=1):.4f}"


def build_structure_report() -> pd.DataFrame:
    path = ROOT / "reports" / "structure_full_selector" / "metrics_raw.csv"
    frame = pd.read_csv(path)
    rows: list[dict] = []
    for dataset, group in frame.groupby("dataset", dropna=False):
        task_type = group["task_type"].iloc[0]
        selected = group["selected_candidate"].iloc[0]
        row = {
            "dataset": dataset,
            "task_type": task_type,
            "selected_candidate": selected,
            "n_seeds": group["seed"].nunique(),
        }
        if task_type == "classification":
            row.update(
                {
                    "primary_metric": "ROC-AUC",
                    "primary_mean": group["test_roc_auc"].mean(),
                    "primary_std": group["test_roc_auc"].std(ddof=1),
                    "test_roc_auc": mean_std(group["test_roc_auc"]),
                    "test_pr_auc": mean_std(group["test_pr_auc"]),
                    "test_brier": mean_std(group["test_brier"]),
                    "test_ef1": mean_std(group["test_ef1"]),
                    "test_bedroc20": mean_std(group["test_bedroc20"]),
                }
            )
        else:
            row.update(
                {
                    "primary_metric": "RMSE",
                    "primary_mean": group["test_rmse"].mean(),
                    "primary_std": group["test_rmse"].std(ddof=1),
                    "test_rmse": mean_std(group["test_rmse"]),
                    "test_mae": mean_std(group["test_mae"]),
                    "test_r2": mean_std(group["test_r2"]),
                }
            )
        rows.append(row)
    summary = pd.DataFrame(rows).sort_values(["task_type", "dataset"])
    summary.to_csv(OUT_DIR / "structure_selector_key_metrics.csv", index=False)
    return summary


def plot_structure(summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 4.8), gridspec_kw={"width_ratios": [3, 2]})

    cls = summary[summary["task_type"].eq("classification")].copy()
    reg = summary[summary["task_type"].eq("regression")].copy()
    colors = ["#2563eb", "#0891b2", "#7c3aed", "#16a34a", "#ea580c"]

    if not cls.empty:
        cls = cls.sort_values("primary_mean", ascending=False)
        axes[0].bar(cls["dataset"], cls["primary_mean"], yerr=cls["primary_std"], color=colors[: len(cls)], edgecolor="white", capsize=3)
        axes[0].set_ylim(max(0.5, cls["primary_mean"].min() - 0.12), min(1.0, cls["primary_mean"].max() + 0.08))
        axes[0].set_ylabel("Test ROC-AUC")
        axes[0].set_title("Structure-separated classification selector")
        axes[0].tick_params(axis="x", rotation=20)
        for idx, (_, row) in enumerate(cls.iterrows()):
            axes[0].text(idx, row["primary_mean"] + 0.01, row["selected_candidate"].replace("_", "\n"), ha="center", va="bottom", fontsize=7, color="#334155")

    if not reg.empty:
        axes[1].bar(reg["dataset"], reg["primary_mean"], yerr=reg["primary_std"], color="#f97316", edgecolor="white", capsize=3)
        axes[1].set_ylabel("Test RMSE")
        axes[1].set_title("Structure-separated regression selector")
        axes[1].tick_params(axis="x", rotation=20)
        for idx, (_, row) in enumerate(reg.iterrows()):
            axes[1].text(idx, row["primary_mean"] + 0.01, row["selected_candidate"].replace("_", "\n"), ha="center", va="bottom", fontsize=7, color="#334155")

    fig.suptitle("Full validation selector under structure-separated split", fontsize=15, fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_structure_full_selector.png", bbox_inches="tight")
    fig.savefig(OUT_DIR / "fig_structure_full_selector.svg", bbox_inches="tight")
    plt.close(fig)


def build_risk_report() -> pd.DataFrame:
    path = ROOT / "reports" / "risk_calibrated_selector" / "metrics_raw.csv"
    frame = pd.read_csv(path)
    rows: list[dict] = []
    for keys, group in frame.groupby(["source", "task_type", "variant", "coverage"], dropna=False):
        source, task_type, variant, coverage = keys
        row = {
            "source": source,
            "task_type": task_type,
            "variant": variant,
            "coverage": coverage,
            "n_runs": len(group),
            "risk_abs_error_spearman": group["risk_abs_error_spearman"].mean(),
        }
        if task_type == "classification":
            row.update(
                {
                    "roc_auc": group["roc_auc"].mean(),
                    "pr_auc": group["pr_auc"].mean(),
                    "brier": group["brier"].mean(),
                    "ece": group["ece"].mean(),
                }
            )
        else:
            row.update(
                {
                    "rmse": group["rmse"].mean(),
                    "mae": group["mae"].mean(),
                    "r2": group["r2"].mean(),
                }
            )
        rows.append(row)
    summary = pd.DataFrame(rows).sort_values(["source", "task_type", "variant", "coverage"])
    summary.to_csv(OUT_DIR / "risk_calibrated_coverage_summary.csv", index=False)
    return summary


def plot_risk(summary: pd.DataFrame) -> None:
    retained = summary[summary["variant"].eq("risk_calibrated_retained")].copy()
    full = summary[summary["variant"].eq("risk_calibrated_full")].copy()

    fig, axes = plt.subplots(2, 2, figsize=(12.8, 8.0))
    class_ret = retained[retained["task_type"].eq("classification")]
    reg_ret = retained[retained["task_type"].eq("regression")]

    if not class_ret.empty:
        sns.lineplot(data=class_ret, x="coverage", y="brier", hue="source", marker="o", ax=axes[0, 0])
        axes[0, 0].invert_xaxis()
        axes[0, 0].set_title("Selective classification reliability")
        axes[0, 0].set_ylabel("Brier score")
        axes[0, 0].set_xlabel("Retained coverage")

        sns.lineplot(data=class_ret, x="coverage", y="roc_auc", hue="source", marker="o", ax=axes[0, 1])
        axes[0, 1].invert_xaxis()
        axes[0, 1].set_title("Discrimination after risk triage")
        axes[0, 1].set_ylabel("ROC-AUC")
        axes[0, 1].set_xlabel("Retained coverage")

    if not reg_ret.empty:
        sns.lineplot(data=reg_ret, x="coverage", y="rmse", hue="source", marker="o", ax=axes[1, 0])
        axes[1, 0].invert_xaxis()
        axes[1, 0].set_title("Selective regression error")
        axes[1, 0].set_ylabel("RMSE")
        axes[1, 0].set_xlabel("Retained coverage")

    if not full.empty:
        full_bar = full.copy()
        full_bar["group"] = full_bar["source"] + " / " + full_bar["task_type"]
        sns.barplot(data=full_bar, y="group", x="risk_abs_error_spearman", color="#0f766e", ax=axes[1, 1])
        axes[1, 1].set_title("Risk score vs absolute error")
        axes[1, 1].set_xlabel("Spearman correlation")
        axes[1, 1].set_ylabel("")
        axes[1, 1].axvline(0, color="#334155", linewidth=0.9)

    fig.suptitle("Risk-calibrated validation selector", fontsize=15, fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_risk_calibrated_selector.png", bbox_inches="tight")
    fig.savefig(OUT_DIR / "fig_risk_calibrated_selector.svg", bbox_inches="tight")
    plt.close(fig)


def build_cliff_report() -> pd.DataFrame:
    base_path = ROOT / "reports" / "moleculeace_multifp" / "metrics_raw.csv"
    cliff_path = ROOT / "reports" / "moleculeace_cliff_objective_selector" / "metrics_raw.csv"
    if not base_path.exists() or not cliff_path.exists():
        return pd.DataFrame()
    base = pd.read_csv(base_path)
    cliff = pd.read_csv(cliff_path)
    base_sel = base[(base["split"].eq("test")) & (base["selected_by_validation"].fillna(0).astype(float).eq(1))].copy()
    cliff_sel = cliff[(cliff["split"].eq("test")) & (cliff["selected_by_validation"].fillna(0).astype(float).eq(1))].copy()
    merged = cliff_sel.merge(base_sel, on=["task", "seed"], suffixes=("_cliff", "_base"))
    if merged.empty:
        return pd.DataFrame()
    out = pd.DataFrame(
        {
            "task": merged["task"],
            "seed": merged["seed"],
            "baseline_model": merged["model_base"],
            "cliff_model": merged["model_cliff"],
            "delta_rmse_positive": merged["rmse_base"] - merged["rmse_cliff"],
            "delta_mae_positive": merged["mae_base"] - merged["mae_cliff"],
            "delta_cliff_rmse_positive": merged["cliff_rmse_base"] - merged["cliff_rmse_cliff"],
            "delta_noncliff_rmse_positive": merged["noncliff_rmse_base"] - merged["noncliff_rmse_cliff"],
            "baseline_rmse": merged["rmse_base"],
            "cliff_rmse": merged["rmse_cliff"],
            "baseline_cliff_rmse": merged["cliff_rmse_base"],
            "cliff_cliff_rmse": merged["cliff_rmse_cliff"],
        }
    )
    out["selected_cliff_weighted"] = out["cliff_model"].str.contains("_cliffw", regex=False).astype(int)
    out.to_csv(OUT_DIR / "moleculeace_cliff_objective_selector_pairs.csv", index=False)
    summary = out[["delta_rmse_positive", "delta_mae_positive", "delta_cliff_rmse_positive", "delta_noncliff_rmse_positive"]].agg(["count", "mean", "median", "std"]).T
    summary["positive_fraction"] = (out[summary.index] > 0).mean().to_numpy()
    summary.to_csv(OUT_DIR / "moleculeace_cliff_objective_selector_summary.csv")
    return out


def plot_cliff(pairs: pd.DataFrame) -> None:
    if pairs.empty:
        return
    task_summary = pairs.groupby("task", as_index=False)[["delta_rmse_positive", "delta_cliff_rmse_positive", "delta_noncliff_rmse_positive"]].mean()
    task_summary = task_summary.sort_values("delta_cliff_rmse_positive", ascending=True)
    selection_counts = pairs["cliff_model"].value_counts().reset_index()
    selection_counts.columns = ["model", "count"]

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.4), gridspec_kw={"width_ratios": [2.4, 1.3, 1.4]})
    colors = ["#059669" if value >= 0 else "#dc2626" for value in task_summary["delta_cliff_rmse_positive"]]
    axes[0].barh(task_summary["task"], task_summary["delta_cliff_rmse_positive"], color=colors, edgecolor="white")
    axes[0].axvline(0, color="#334155", linewidth=0.9)
    axes[0].set_xlabel("Cliff RMSE improvement")
    axes[0].set_title("Task-level activity-cliff gain")

    axes[1].scatter(pairs["delta_rmse_positive"], pairs["delta_cliff_rmse_positive"], c=pairs["selected_cliff_weighted"], cmap="viridis", alpha=0.78)
    axes[1].axhline(0, color="#334155", linewidth=0.9)
    axes[1].axvline(0, color="#334155", linewidth=0.9)
    axes[1].set_xlabel("Overall RMSE improvement")
    axes[1].set_ylabel("Cliff RMSE improvement")
    axes[1].set_title("Overall vs cliff-specific")

    axes[2].barh(selection_counts["model"], selection_counts["count"], color="#2563eb", edgecolor="white")
    axes[2].invert_yaxis()
    axes[2].set_xlabel("Selected task-seed runs")
    axes[2].set_title("Validation-selected cliff models")

    fig.suptitle("MoleculeACE cliff-aware training and selector objective", fontsize=15, fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_moleculeace_cliff_objective_selector.png", bbox_inches="tight")
    fig.savefig(OUT_DIR / "fig_moleculeace_cliff_objective_selector.svg", bbox_inches="tight")
    plt.close(fig)


def write_readme(structure: pd.DataFrame, risk: pd.DataFrame, cliff: pd.DataFrame) -> None:
    structure_table = structure.fillna("")
    risk_table = risk[(risk["variant"].isin(["risk_calibrated_full", "risk_calibrated_retained"])) & (risk["coverage"].isin([1.0, 0.8, 0.6]))].fillna("")
    lines = [
        "# Q1 method upgrade report",
        "",
        "This package consolidates the three new method modules requested for the Q1 manuscript: structure-separated full selector, risk-calibrated validation selector, and MoleculeACE cliff-aware selector.",
        "",
        "## Structure-separated full selector",
        "",
        structure_table.to_markdown(index=False),
        "",
        "## Risk-calibrated selector",
        "",
        risk_table.to_markdown(index=False),
        "",
    ]
    if not cliff.empty:
        numeric_cols = ["delta_rmse_positive", "delta_mae_positive", "delta_cliff_rmse_positive", "delta_noncliff_rmse_positive"]
        cliff_summary = cliff[numeric_cols].agg(["count", "mean", "median", "std"]).T
        cliff_summary["positive_fraction"] = (cliff[numeric_cols] > 0).mean().to_numpy()
        lines.extend(
            [
                "## MoleculeACE cliff objective selector",
                "",
                cliff_summary.to_markdown(),
                "",
                f"The cliff-aware selector chose a cliff-weighted model in {cliff['selected_cliff_weighted'].mean():.1%} of task-seed runs.",
                "",
            ]
        )
    (OUT_DIR / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    setup_style()
    structure = build_structure_report()
    plot_structure(structure)
    risk = build_risk_report()
    plot_risk(risk)
    cliff = build_cliff_report()
    plot_cliff(cliff)
    write_readme(structure, risk, cliff)
    print(f"Wrote Q1 method upgrade report to {OUT_DIR}")


if __name__ == "__main__":
    main()
