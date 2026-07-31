from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpecFromSubplotSpec


ROOT = Path(r"D:\fzyc")
OUT = ROOT / "output" / "paper43_jcheminform_completion_20260726"
TABLES = OUT / "additional_files" / "tables"
FIGURES = OUT / "figures"
KS = [4, 8, 16, 32]
COLORS = {"K-invariant K=32": "#0072B2", "K-dependent": "#E69F00", "Same-fold": "#009E73"}


def annotate_heatmap(ax, values, formats, cmap, vmin, vmax, labels, columns):
    image = ax.imshow(values, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)
    ax.set_xticks(range(len(columns)), columns, fontsize=8)
    ax.set_yticks(range(len(labels)), labels, fontsize=8)
    for row in range(values.shape[0]):
        for col in range(values.shape[1]):
            value = values[row, col]
            text = formats[col].format(value)
            midpoint = (vmin + vmax) / 2
            color = "white" if abs(value - midpoint) > 0.35 * (vmax - vmin) else "black"
            ax.text(col, row, text, ha="center", va="center", fontsize=7.2, color=color)
    for spine in ax.spines.values():
        spine.set_visible(False)
    return image


def main():
    fixed = pd.read_csv(TABLES / "fixed_reference_units.csv")
    epsilon = pd.read_csv(TABLES / "epsilon_near_equivalence_units.csv")
    comparisons = pd.read_csv(TABLES / "classification_metric_selector_comparisons.csv")

    working = epsilon[
        ((epsilon.task_type == "classification") & (epsilon.epsilon == 0.010))
        | ((epsilon.task_type == "regression") & (epsilon.epsilon == 0.050))
    ]

    plt.rcParams.update({"font.family": "Arial", "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9})
    fig = plt.figure(figsize=(11.5, 8.2), constrained_layout=True)
    grid = fig.add_gridspec(2, 2, width_ratios=[1.05, 1.2], height_ratios=[1, 1])

    # A: natural-scale gaps; classification and regression never share a numerical axis.
    sub_a = GridSpecFromSubplotSpec(1, 2, subplot_spec=grid[0, 0], wspace=0.24)
    for idx, task in enumerate(["classification", "regression"]):
        ax = fig.add_subplot(sub_a[0, idx])
        subset = fixed[fixed.task_type == task]
        summaries = {
            "K-invariant K=32": subset.groupby("pool_size").fixed_k32_gap.mean(),
            "K-dependent": subset.groupby("pool_size").k_dependent_crossfit_gap.mean(),
            "Same-fold": subset.groupby("pool_size").same_fold_opportunity_gap.mean(),
        }
        for label, series in summaries.items():
            ax.plot(KS, series.reindex(KS), marker="o", linewidth=1.7, markersize=4, color=COLORS[label], label=label)
        ax.axhline(0, color="#777777", linewidth=0.8)
        ax.set_xticks(KS)
        ax.set_xlabel("Candidate count K")
        ax.set_ylabel("ROC-AUC gap" if task == "classification" else "RMSE gap")
        ax.set_title("Classification" if task == "classification" else "Regression")
        ax.grid(axis="y", alpha=0.2)
        if idx == 0:
            ax.legend(frameon=False, fontsize=7.5, loc="best")
    fig.text(0.005, 0.985, "A", fontsize=13, fontweight="bold", va="top")
    fig.text(0.035, 0.985, "Reference and opportunity gaps", fontsize=11, fontweight="bold", va="top")

    # B: epsilon-success at task-appropriate retrospectively locked working thresholds.
    ax_b = fig.add_subplot(grid[0, 1])
    for task, label, color, marker in [
        ("classification", "Classification, ε=0.010 ROC-AUC", "#0072B2", "o"),
        ("regression", "Regression, ε=0.050 RMSE", "#D55E00", "s"),
    ]:
        series = working[working.task_type == task].groupby("pool_size").crossfit_epsilon_success.mean()
        ax_b.plot(KS, 100 * series.reindex(KS), marker=marker, linewidth=1.8, color=color, label=label)
    ax_b.set_xticks(KS)
    ax_b.set_ylim(0, 100)
    ax_b.set_xlabel("Candidate count K")
    ax_b.set_ylabel("Cross-fitted ε-success (%)")
    ax_b.set_title("B  Practical-equivalence success", loc="left", fontweight="bold")
    ax_b.legend(frameon=False, fontsize=8, loc="lower right")
    ax_b.grid(axis="y", alpha=0.2)

    # C: near-equivalent set size, kept separate from success rate (no dual axis).
    ax_c = fig.add_subplot(grid[1, 0])
    for task, label, color, marker in [
        ("classification", "Classification, ε=0.010", "#0072B2", "o"),
        ("regression", "Regression, ε=0.050", "#D55E00", "s"),
    ]:
        series = working[working.task_type == task].groupby("pool_size").crossfit_near_equivalent_n.mean()
        ax_c.plot(KS, series.reindex(KS), marker=marker, linewidth=1.8, color=color, label=label)
    ax_c.set_xticks(KS)
    ax_c.set_ylim(bottom=0)
    ax_c.set_xlabel("Candidate count K")
    ax_c.set_ylabel("Mean cross-fitted set size")
    ax_c.set_title("C  Near-equivalent candidate sets", loc="left", fontweight="bold")
    ax_c.legend(frameon=False, fontsize=8, loc="upper left")
    ax_c.grid(axis="y", alpha=0.2)

    # D: endpoint-level metric-dependent switching and the corresponding outer trade-offs.
    sub_d = GridSpecFromSubplotSpec(1, 2, subplot_spec=grid[1, 1], width_ratios=[0.9, 1.15], wspace=0.18)
    endpoint_order = ["bace", "bbbp", "clintox", "tdc_hia_hou", "tdc_pgp_broccatelli"]
    labels = ["BACE", "BBBP", "ClinTox", "HIA", "P-gp"]
    k32 = comparisons[comparisons.pool_size == 32]
    grouped = k32.groupby(["alternative_selector", "dataset"]).mean(numeric_only=True)
    switch = np.column_stack([
        100 * grouped.loc[("pr_auc",), "candidate_changed_vs_roc"].reindex(endpoint_order).to_numpy(),
        100 * grouped.loc[("minority_constrained",), "candidate_changed_vs_roc"].reindex(endpoint_order).to_numpy(),
    ])
    effects = np.column_stack([
        grouped.loc[("pr_auc",), "delta_outer_pr_auc_vs_roc_selector"].reindex(endpoint_order).to_numpy(),
        grouped.loc[("minority_constrained",), "delta_outer_minority_recall_vs_roc_selector"].reindex(endpoint_order).to_numpy(),
    ])
    ax_d1 = fig.add_subplot(sub_d[0, 0])
    annotate_heatmap(ax_d1, switch, ["{:.0f}%", "{:.0f}%"], "Blues", 0, 100, labels, ["PR switch", "Recall-rule\nswitch"])
    ax_d1.set_title("D  Candidate switching", fontsize=9, loc="left", fontweight="bold")
    ax_d2 = fig.add_subplot(sub_d[0, 1])
    limit = max(0.016, float(np.nanmax(np.abs(effects))))
    annotate_heatmap(ax_d2, effects, ["{:+.3f}", "{:+.3f}"], "RdBu", -limit, limit, labels, ["Δ PR-AUC", "Δ minority\nrecall"])
    ax_d2.set_yticklabels([])
    ax_d2.set_title("Outer-fold change vs ROC-AUC selector", fontsize=9)
    fig.suptitle("Practical equivalence and metric-dependent selection", fontsize=13, fontweight="bold")
    png = FIGURES / "Figure_8_consolidated_practical_equivalence_metric_selection.png"
    pdf = FIGURES / "Figure_8_consolidated_practical_equivalence_metric_selection.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)
    print(png)
    print(pdf)


if __name__ == "__main__":
    main()
