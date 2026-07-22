from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "reports" / "experiment_thickening_figures"

COLORS = {
    "random": "#2563eb",
    "scaffold": "#059669",
    "structure": "#dc2626",
    "moleculenet": "#7c3aed",
    "tdc": "#0891b2",
    "hybrid_ad": "#0f766e",
    "ensemble_std": "#d97706",
    "inverse_tanimoto": "#2563eb",
    "scaffold_distance": "#64748b",
    "brier": "#0891b2",
    "ece": "#dc2626",
}

FAMILY_COLORS = {
    "chemprop": "#dc2626",
    "graph_core": "#2563eb",
    "morgan_tree": "#059669",
    "multi_fingerprint": "#d97706",
    "pretrained": "#7c3aed",
}


def setup_style() -> None:
    sns.set_theme(style="whitegrid", context="paper", font_scale=1.05)
    plt.rcParams.update(
        {
            "figure.dpi": 140,
            "savefig.dpi": 320,
            "font.family": "DejaVu Sans",
            "axes.titleweight": "bold",
            "axes.edgecolor": "#cbd5e1",
            "axes.labelcolor": "#0f172a",
            "xtick.color": "#334155",
            "ytick.color": "#334155",
            "grid.color": "#e2e8f0",
            "grid.linewidth": 0.8,
            "legend.frameon": True,
            "legend.framealpha": 0.95,
        }
    )


def short_dataset(name: str) -> str:
    label = (
        str(name)
        .replace("tdc_", "")
        .replace("_wang", "")
        .replace("_hou", "")
        .replace("_broccatelli", "")
        .replace("_martins", "")
        .replace("_veith", "")
        .replace("_ma", "")
        .replace("_", " ")
        .upper()
    )
    return {
        "BIOAVAILABILITY": "BIOAV",
        "CACO2": "CACO2",
        "CLINTOX": "CLINTOX",
        "FREESOLV": "FREESOLV",
    }.get(label, label)


def source_label(name: str) -> str:
    labels = {
        "strict_core_fast": "Core experts",
        "strict_multifp_fast": "Multi-FP",
        "chemprop_baseline": "Chemprop",
        "descriptor_motif_baselines": "Motif/descriptors",
        "tdc_admet_multifp": "TDC Multi-FP",
        "moleculenet_selector": "MoleculeNet selector",
        "tdc_admet_selector": "TDC ADMET selector",
    }
    return labels.get(str(name), str(name))


def save(fig: plt.Figure, name: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / f"{name}.png", bbox_inches="tight")
    fig.savefig(OUT_DIR / f"{name}.svg", bbox_inches="tight")
    plt.close(fig)


def add_panel(ax: plt.Axes, label: str) -> None:
    ax.text(
        -0.08,
        1.08,
        label,
        transform=ax.transAxes,
        fontsize=12,
        fontweight="bold",
        color="#0f172a",
        va="top",
    )


def plot_tdc_split_realism_seed3() -> None:
    slope_path = ROOT / "reports" / "split_realism_tdc_lgbm_seed3" / "split_realism_slope.csv"
    frame = pd.read_csv(slope_path)
    class_df = frame[frame["task_type"].eq("classification")].copy()
    reg_df = frame[frame["task_type"].eq("regression")].copy()

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.6), gridspec_kw={"width_ratios": [3.2, 1.2]})

    class_order = class_df.assign(total_drop=class_df["random_to_scaffold_drop"] + class_df["scaffold_to_structure_drop"])
    class_order = class_order.sort_values("total_drop", ascending=False)["dataset"].tolist()
    x = np.arange(len(class_order))
    width = 0.24
    for offset, split in [(-width, "random"), (0.0, "scaffold"), (width, "structure")]:
        values = class_df.set_index("dataset").loc[class_order, f"{split}_roc_auc"].to_numpy()
        axes[0].bar(
            x + offset,
            values,
            width=width,
            color=COLORS[split],
            edgecolor="white",
            linewidth=0.7,
            label=split.replace("_", "-"),
        )
    for idx, dataset in enumerate(class_order):
        row = class_df[class_df["dataset"].eq(dataset)].iloc[0]
        drop = row["random_roc_auc"] - row["structure_roc_auc"]
        axes[0].text(idx, max(row["random_roc_auc"], row["scaffold_roc_auc"], row["structure_roc_auc"]) + 0.012, f"{drop:+.3f}", ha="center", fontsize=8, color="#334155")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels([short_dataset(d) for d in class_order], rotation=35, ha="right")
    axes[0].set_ylabel("ROC-AUC")
    axes[0].set_ylim(0.55, 1.01)
    axes[0].set_title("TDC ADMET classification under stricter structural splits")
    axes[0].legend(ncol=3, loc="lower left")
    add_panel(axes[0], "A")

    if not reg_df.empty:
        row = reg_df.iloc[0]
        splits = ["random", "scaffold", "structure"]
        values = [row[f"{split}_rmse"] for split in splits]
        axes[1].plot(splits, values, marker="o", linewidth=2.2, color=COLORS["tdc"])
        axes[1].fill_between(splits, values, alpha=0.12, color=COLORS["tdc"])
        for i, value in enumerate(values):
            axes[1].text(i, value + 0.006, f"{value:.3f}", ha="center", fontsize=9, color="#334155")
        axes[1].set_ylabel("RMSE")
        axes[1].set_title(f"{short_dataset(row['dataset'])} regression")
        axes[1].set_ylim(max(0.0, min(values) - 0.04), max(values) + 0.06)
    add_panel(axes[1], "B")

    fig.suptitle("Multi-seed split realism stress test", fontsize=15, fontweight="bold", color="#0f172a")
    fig.subplots_adjust(bottom=0.24, top=0.80, wspace=0.24)
    fig.text(
        0.5,
        0.055,
        "Numbers above classification bars show random-to-structure ROC-AUC change; regression panel reports RMSE, where lower is better.",
        ha="center",
        fontsize=9,
        color="#475569",
    )
    save(fig, "fig_thickening_tdc_split_realism_seed3")


def plot_validation_calibration() -> None:
    path = ROOT / "reports" / "validation_calibration" / "calibration_improvement_by_dataset.csv"
    frame = pd.read_csv(path)
    frame["label"] = frame["source"].map(source_label) + "\n" + frame["dataset"].map(short_dataset)
    order = frame.sort_values("mean_delta_ece_positive", ascending=False)["label"].tolist()
    frame = frame.set_index("label").loc[order].reset_index()

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 8), sharey=True)
    metrics = [
        ("mean_delta_ece_positive", "ECE improvement", COLORS["ece"]),
        ("mean_delta_brier_positive", "Brier improvement", COLORS["brier"]),
    ]
    for ax, (col, title, color) in zip(axes, metrics):
        values = frame[col].to_numpy()
        bar_colors = [color if value >= 0 else "#94a3b8" for value in values]
        ax.barh(np.arange(len(frame)), values, color=bar_colors, edgecolor="white", linewidth=0.5)
        ax.axvline(0, color="#334155", linewidth=0.9)
        ax.set_yticks(np.arange(len(frame)))
        ax.set_yticklabels(frame["label"], fontsize=8)
        ax.invert_yaxis()
        ax.set_xlabel("Selected calibrator - uncalibrated")
        ax.set_title(title)
        add_panel(ax, "A" if col == "mean_delta_ece_positive" else "B")
    fig.suptitle("Validation-only calibration improves reliability without using test labels", fontsize=15, fontweight="bold", color="#0f172a")
    fig.text(
        0.5,
        0.01,
        "Positive values indicate lower test ECE or Brier score after selecting the calibrator by validation Brier score.",
        ha="center",
        fontsize=9,
        color="#475569",
    )
    save(fig, "fig_thickening_validation_calibration")


def plot_ad_gated_curves() -> None:
    path = ROOT / "reports" / "ad_gated_selector" / "ad_gated_metrics_raw.csv"
    frame = pd.read_csv(path)
    risk_order = ["hybrid_ad", "ensemble_std", "inverse_tanimoto", "scaffold_distance"]

    fig, axes = plt.subplots(2, 2, figsize=(14, 9), sharex=True)
    panels = [
        ("moleculenet_selector", "classification", "roc_auc", "MoleculeNet ROC-AUC"),
        ("moleculenet_selector", "classification", "brier", "MoleculeNet Brier"),
        ("tdc_admet_selector", "classification", "roc_auc", "TDC ADMET ROC-AUC"),
        ("moleculenet_selector", "regression", "rmse", "MoleculeNet regression RMSE"),
    ]

    for ax, (source, task_type, metric, title) in zip(axes.ravel(), panels):
        sub = frame[(frame["source"].eq(source)) & (frame["task_type"].eq(task_type))].copy()
        for risk in risk_order:
            risk_sub = sub[sub["risk_score"].eq(risk)].copy()
            if risk_sub.empty or metric not in risk_sub.columns:
                continue
            grouped = risk_sub.groupby("coverage", as_index=False)[metric].mean().sort_values("coverage")
            ax.plot(
                grouped["coverage"],
                grouped[metric],
                marker="o",
                linewidth=2.0,
                markersize=4.5,
                color=COLORS.get(risk, "#64748b"),
                label=risk.replace("_", " "),
            )
        ax.set_title(title)
        ax.set_xlabel("Retained coverage")
        ax.set_ylabel(metric.upper() if metric != "brier" else "Brier score")
        ax.set_xlim(0.48, 1.02)
        if metric in {"brier", "rmse"}:
            ax.invert_yaxis()
        ax.legend(fontsize=8)
    for ax, label in zip(axes.ravel(), ["A", "B", "C", "D"]):
        add_panel(ax, label)
    fig.suptitle("Applicability-domain gating yields risk-coverage trade-offs", fontsize=15, fontweight="bold", color="#0f172a")
    fig.text(
        0.5,
        0.01,
        "Curves keep the lowest-risk molecules first; inverted panels indicate lower-is-better metrics so upward visual movement remains favorable.",
        ha="center",
        fontsize=9,
        color="#475569",
    )
    save(fig, "fig_thickening_ad_gated_risk_coverage")


def plot_selector_family_weights() -> None:
    path = ROOT / "reports" / "selector_stability" / "selector_family_weights_raw.csv"
    frame = pd.read_csv(path)
    family_cols = [col for col in frame.columns if col.startswith("family_weight_")]
    for col in family_cols:
        frame[col] = frame[col].fillna(0.0)
    grouped = frame.groupby(["source", "dataset"], as_index=False)[family_cols].mean()
    grouped["label"] = grouped["source"].map(source_label) + "\n" + grouped["dataset"].map(short_dataset)
    grouped["effective_experts"] = frame.groupby(["source", "dataset"])["mean_effective_experts"].mean().to_numpy()
    grouped = grouped.sort_values(["source", "effective_experts"], ascending=[True, False])

    labels = grouped["dataset"].map(short_dataset).tolist()
    x = np.arange(len(grouped))
    bottom = np.zeros(len(grouped))

    fig, ax = plt.subplots(figsize=(14, 7.2))
    for family, color in FAMILY_COLORS.items():
        col = f"family_weight_{family}"
        if col not in grouped.columns:
            continue
        values = grouped[col].to_numpy()
        ax.bar(x, values, bottom=bottom, color=color, edgecolor="white", linewidth=0.6, label=family.replace("_", " "))
        bottom += values
    ax.set_ylim(0, 1.16)
    ax.set_ylabel("Mean selector weight")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=9)
    ax.set_title("Endpoint-specific expert family contribution selected by validation")
    ax.legend(ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.19))

    source_ranges = []
    for source, sub in grouped.reset_index().groupby("source", sort=False):
        start = int(sub.index.min())
        end = int(sub.index.max())
        source_ranges.append((source, start, end))
        if start > 0:
            ax.axvline(start - 0.5, color="#94a3b8", linewidth=1.0, linestyle="--")
        ax.text((start + end) / 2, 1.105, source_label(source), ha="center", fontsize=9, color="#334155")

    for xpos, row in enumerate(grouped.itertuples(index=False)):
        ax.text(xpos, 1.025, f"Neff {row.effective_experts:.1f}", ha="center", fontsize=8, color="#475569")
    fig.subplots_adjust(bottom=0.31, top=0.82)
    fig.text(
        0.5,
        0.055,
        "Weights are averaged over seeds for selected adaptive/stacking candidates; TDC endpoints converge on multi-fingerprint experts while MoleculeNet uses endpoint-specific mixtures.",
        ha="center",
        fontsize=9,
        color="#475569",
    )
    save(fig, "fig_thickening_selector_family_weights")


def write_readme() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Experiment thickening figures",
        "",
        "Generated from real completed result CSV files on 2026-05-28.",
        "",
        "- `fig_thickening_tdc_split_realism_seed3`: multi-seed TDC random/scaffold/structure-separated stress test.",
        "- `fig_thickening_validation_calibration`: validation-only Platt/isotonic calibration improvements.",
        "- `fig_thickening_ad_gated_risk_coverage`: AD-gated retained-coverage performance curves.",
        "- `fig_thickening_selector_family_weights`: selector expert-family contribution and effective expert count.",
        "",
        "These figures are intended for the supplementary experiment package and can be promoted to the main manuscript if the narrative centers on reliability/OOD generalization.",
        "",
    ]
    (OUT_DIR / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    setup_style()
    plot_tdc_split_realism_seed3()
    plot_validation_calibration()
    plot_ad_gated_curves()
    plot_selector_family_weights()
    write_readme()
    print(f"Wrote figures to {OUT_DIR}")


if __name__ == "__main__":
    main()
