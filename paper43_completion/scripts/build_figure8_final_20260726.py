"""Rebuild final Figure 8 from the checked paper43_completion source tables."""

from pathlib import Path
import argparse

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TABLES = ROOT / "source_data"
KS = [4, 8, 16, 32]
BLUE, ORANGE, GREY, INK, LIGHT = "#315E8A", "#D58135", "#7A7F87", "#202830", "#E3E7EA"
DISPLAY = {"bace": "BACE", "bbbp": "BBBP", "clintox": "ClinTox", "tdc_hia_hou": "HIA", "tdc_pgp_broccatelli": "P-gp"}


def setup():
    mpl.rcParams.update({
        "font.family": "Times New Roman", "font.size": 9.0,
        "axes.titlesize": 10.3, "axes.titleweight": "bold", "axes.labelsize": 9.2,
        "xtick.labelsize": 8.2, "ytick.labelsize": 8.2, "legend.fontsize": 8.2,
        "axes.spines.top": False, "axes.spines.right": False,
        "pdf.fonttype": 42, "svg.fonttype": "none", "axes.unicode_minus": False,
    })


def clean(ax):
    ax.grid(axis="y", color=LIGHT, linewidth=.6, alpha=.8)
    ax.set_axisbelow(True)


def build(output_dir: Path):
    fixed = pd.read_csv(TABLES / "fixed_reference_units.csv")
    eps = pd.read_csv(TABLES / "epsilon_near_equivalence_units.csv")
    comp = pd.read_csv(TABLES / "classification_metric_selector_comparisons.csv")
    working = eps[((eps.task_type == "classification") & (eps.epsilon == .010)) |
                  ((eps.task_type == "regression") & (eps.epsilon == .050))]

    fig = plt.figure(figsize=(6.69, 6.25))  # 170 mm wide
    gs = fig.add_gridspec(2, 2, left=.105, right=.985, bottom=.085, top=.90,
                          hspace=.40, wspace=.34)
    asub = gs[0, 0].subgridspec(2, 1, hspace=.42)
    estimands = [("fixed_k32_gap", "-", "K-invariant"),
                 ("k_dependent_crossfit_gap", "--", "K-dependent"),
                 ("same_fold_opportunity_gap", ":", "Same-fold")]
    a_axes = []
    for index, (task, color, marker, title, ylabel) in enumerate([
        ("classification", BLUE, "o", "Classification", "ROC-AUC gap"),
        ("regression", ORANGE, "s", "Regression", "RMSE gap")]):
        ax = fig.add_subplot(asub[index], sharex=a_axes[0] if a_axes else None); q = fixed[fixed.task_type.eq(task)]
        for col, ls, _ in estimands:
            z = q.groupby("pool_size")[col].mean().reindex(KS)
            ax.plot(z.index, z, color=color, marker=marker, ls=ls, lw=1.25, ms=4.1)
        ax.axhline(0, color=GREY, lw=.8); ax.set(ylabel=ylabel, xticks=KS)
        ax.set_title(title, loc="left", pad=2, fontsize=9.0)
        if index == 0:
            ax.tick_params(axis="x", labelbottom=False)
        else:
            ax.set_xlabel("Candidate count, K")
        clean(ax); a_axes.append(ax)
    fig.text(.105, .972, "A  Reference and opportunity gaps", fontsize=10.3, fontweight="bold", va="top")
    fig.legend(handles=[Line2D([0], [0], color=INK, ls=ls, lw=1.35, label=label) for _, ls, label in estimands],
               loc="upper center", bbox_to_anchor=(.325, .952), ncol=3, frameon=False,
               fontsize=7.8, handlelength=1.8, columnspacing=.9)

    for spec, metric, ylabel, title, legend in [
        (gs[0, 1], "crossfit_epsilon_success", "Cross-fitted ε-success (%)", "B  Practical-equivalence success", True),
        (gs[1, 0], "crossfit_near_equivalent_n", "Mean cross-fitted set size", "C  Near-equivalent candidate sets", False)]:
        ax = fig.add_subplot(spec)
        for task, label, color, marker in [("classification", "Classification, ε = 0.010", BLUE, "o"),
                                            ("regression", "Regression, ε = 0.050", ORANGE, "s")]:
            z = working[working.task_type.eq(task)].groupby("pool_size")[metric].mean().reindex(KS)
            if metric == "crossfit_epsilon_success": z = 100 * z
            ax.plot(z.index, z, marker=marker, color=color, label=label, lw=1.25, ms=4.2)
        ax.set(xlabel="Candidate count, K", ylabel=ylabel, xticks=KS); ax.set_ylim(bottom=0)
        if metric == "crossfit_epsilon_success": ax.set_ylim(0, 100)
        if metric == "crossfit_epsilon_success":
            b_left = gs[0, 1].get_position(fig).x0
            fig.text(b_left, .972, title, fontsize=10.3, fontweight="bold", va="top")
        else:
            ax.set_title(title, loc="left", pad=4)
        clean(ax)
        if legend: ax.legend(frameon=False, fontsize=8.0, loc="lower right", handlelength=2.1)

    endpoint_order = ["bace", "bbbp", "clintox", "tdc_hia_hou", "tdc_pgp_broccatelli"]
    k32 = comp[comp.pool_size.eq(32)].groupby(["alternative_selector", "dataset"]).mean(numeric_only=True)
    switch = np.column_stack([100*k32.loc[("pr_auc",), "candidate_changed_vs_roc"].reindex(endpoint_order),
                              100*k32.loc[("minority_constrained",), "candidate_changed_vs_roc"].reindex(endpoint_order)])
    effect = np.column_stack([k32.loc[("pr_auc",), "delta_outer_pr_auc_vs_roc_selector"].reindex(endpoint_order),
                              k32.loc[("minority_constrained",), "delta_outer_minority_recall_vs_roc_selector"].reindex(endpoint_order)])
    dsub = gs[1, 1].subgridspec(1, 2, wspace=.12); heat_axes = []
    for ax, arr, cols, cmap, lim, fmt, title in [
        (fig.add_subplot(dsub[0]), switch, ["PR-AUC\nrule", "Recall\nrule"], "Blues", (0, 100), "{:.0f}%", "D  Candidate switching"),
        (fig.add_subplot(dsub[1]), effect, ["Δ PR-AUC", "Δ minority\nrecall"], "RdBu_r", (-.04, .04), "{:+.3f}", "Outer change")]:
        mesh = ax.pcolormesh(np.arange(3), np.arange(6), arr, cmap=cmap, vmin=lim[0], vmax=lim[1], shading="flat")
        ax.set(xlim=(0, 2), ylim=(5, 0)); ax.set_xticks([.5, 1.5], cols)
        ax.set_yticks(np.arange(5)+.5, [DISPLAY[x] for x in endpoint_order] if not heat_axes else [])
        for i in range(5):
            for j in range(2):
                rgba = mesh.cmap(mesh.norm(arr[i, j])); lum = .2126*rgba[0] + .7152*rgba[1] + .0722*rgba[2]
                ax.text(j+.5, i+.5, fmt.format(arr[i, j]), ha="center", va="center", fontsize=8.5,
                        color="white" if lum < .50 else "black")
        for spine in ax.spines.values(): spine.set_visible(False)
        ax.tick_params(axis="x", labelsize=8.2); ax.tick_params(axis="y", labelsize=8.2)
        ax.set_title(title, loc="left" if not heat_axes else "center", fontsize=10.3, pad=5); heat_axes.append(ax)

    output_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_dir / "Figure8.pdf", bbox_inches="tight", facecolor="white")
    fig.savefig(output_dir / "Figure8.svg", bbox_inches="tight", facecolor="white")
    fig.savefig(output_dir / "Figure8_600dpi.png", dpi=600, bbox_inches="tight", facecolor="white")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reproduced_outputs" / "main_figures")
    args = parser.parse_args(); setup(); build(args.output_dir)
