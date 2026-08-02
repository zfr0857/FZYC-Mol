from __future__ import annotations

import importlib.util
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpecFromSubplotSpec
from matplotlib.lines import Line2D


BASE_SCRIPT = Path(r"D:\fzyc\scripts\build_paper43_r11_method_refinement_figures_20260731.py")
PACKAGE = Path(
    r"D:\fzyc\output\paper43_jcheminform_completion_20260726"
    r"\JoC_R12_FORMAT_REFINEMENT_CONFLICT_HOLD_20260801"
)
WORK = Path(r"D:\fzyc\work\r11_method_refinement_20260731")
SOURCE = (
    Path(r"D:\fzyc\work\cold_start_paper_release_2026-07-r11_20260731_01")
    / "paper43_completion"
    / "source_data"
)


spec = importlib.util.spec_from_file_location("r11_figbase", BASE_SCRIPT)
base = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(base)
base.OUT = PACKAGE / "03_Main_Figures"
base.WORK = WORK
base.SOURCE = SOURCE


def figure8() -> None:
    fixed = pd.read_csv(SOURCE / "fixed_reference_units.csv")
    tau = pd.read_csv(SOURCE / "tau_near_equivalence_units.csv")
    comp = pd.read_csv(WORK / "classification_metric_selector_comparisons_frozen_identity_diagnostic.csv")
    working = tau[
        ((tau.task_type == "classification") & (tau.tau == 0.010))
        | ((tau.task_type == "regression") & (tau.tau == 0.050))
    ]
    fig = plt.figure(figsize=(6.69, 6.25))
    gs = fig.add_gridspec(2, 2, left=0.105, right=0.985, bottom=0.085, top=0.90, hspace=0.40, wspace=0.34)
    asub = GridSpecFromSubplotSpec(2, 1, subplot_spec=gs[0, 0], hspace=0.42)
    estimands = [
        ("fixed_k32_gap", "-", "o", "Full-registry"),
        ("k_dependent_crossfit_gap", "--", "s", "Within-prefix"),
        ("same_fold_opportunity_gap", ":", "^", "Same-fold"),
    ]
    shared = []
    for index, (kind, color, title, ylabel) in enumerate(
        [("classification", base.BLUE, "Classification", "ROC-AUC gap"), ("regression", base.ORANGE, "Regression", "RMSE gap")]
    ):
        ax = fig.add_subplot(asub[index], sharex=shared[0] if shared else None)
        subset = fixed[fixed.task_type.eq(kind)]
        for column, linestyle, marker, _ in estimands:
            values = subset.groupby("pool_size")[column].mean().reindex([4, 8, 16, 32])
            ax.plot(values.index, values, color=color, marker=marker, ls=linestyle, lw=1.25, ms=4.1)
        ax.axhline(0, color=base.GREY, lw=0.8)
        ax.set(ylabel=ylabel, xticks=[4, 8, 16, 32])
        ax.set_title(title, loc="left", pad=2, fontsize=9)
        if index == 0:
            ax.tick_params(axis="x", labelbottom=False)
        else:
            ax.set_xlabel("Candidate count, K")
        base.clean(ax)
        shared.append(ax)
    fig.text(0.105, 0.972, "A  Reference and opportunity gaps", fontsize=10.3, fontweight="bold", va="top")
    fig.legend(
        handles=[Line2D([0], [0], color=base.INK, marker=m, ls=ls, label=lab) for _, ls, m, lab in estimands],
        loc="upper center",
        bbox_to_anchor=(0.325, 0.952),
        ncol=3,
        frameon=False,
        fontsize=8,
    )

    ax = fig.add_subplot(gs[0, 1])
    for kind, label, color, marker in [
        ("classification", "Classification, tau = 0.010", base.BLUE, "o"),
        ("regression", "Regression, tau = 0.050", base.ORANGE, "s"),
    ]:
        values = working[working.task_type.eq(kind)].groupby("pool_size").crossfit_tau_success.mean().reindex([4, 8, 16, 32])
        ax.plot(values.index, 100 * values, marker=marker, color=color, label=label, lw=1.25, ms=4.2)
    ax.set(xlabel="Candidate count, K", ylabel="Cross-fitted tau-success (%)", xticks=[4, 8, 16, 32], ylim=(0, 100))
    fig.text(0.57, 0.972, "B  Practical-equivalence success", fontsize=10.3, fontweight="bold", va="top")
    ax.legend(frameon=False, loc="lower right")
    base.clean(ax)

    ax = fig.add_subplot(gs[1, 0])
    for kind, label, color, marker in [
        ("classification", "Classification, tau = 0.010", base.BLUE, "o"),
        ("regression", "Regression, tau = 0.050", base.ORANGE, "s"),
    ]:
        values = working[working.task_type.eq(kind)].groupby("pool_size").crossfit_near_equivalent_n.mean().reindex([4, 8, 16, 32])
        ax.plot(values.index, values, marker=marker, color=color, label=label, lw=1.25, ms=4.2)
    ax.set(xlabel="Candidate count, K", ylabel="Mean cross-fitted set size", xticks=[4, 8, 16, 32])
    ax.set_ylim(bottom=0)
    ax.set_title("C  Near-equivalent candidate sets", loc="left", pad=4)
    ax.legend(frameon=False, loc="best")
    base.clean(ax)

    order = ["bace", "bbbp", "clintox", "tdc_hia_hou", "tdc_pgp_broccatelli"]
    k32 = comp[(comp.pool_size == 32) & (comp.alternative_selector == "pr_auc")].groupby("dataset").mean(numeric_only=True).reindex(order)
    switch = 100 * k32[["candidate_changed_vs_roc"]].to_numpy(float)
    effect = k32[["delta_outer_pr_auc_vs_roc_selector"]].to_numpy(float)
    ax = fig.add_subplot(gs[1, 1])
    switch_mesh = ax.pcolormesh([0, 1], np.arange(6), switch, shading="flat", cmap="Blues", vmin=0, vmax=100)
    effect_mesh = ax.pcolormesh([1, 2], np.arange(6), effect, shading="flat", cmap="RdBu_r", vmin=-0.015, vmax=0.015)
    ax.set(xlim=(0, 2), ylim=(5, 0))
    ax.set_xticks([0.5, 1.5], ["Candidate switch\n(%)", "Outer PR-AUC\nchange"])
    ax.set_yticks(np.arange(5) + 0.5, [base.DISPLAY[x] for x in order])
    for row in range(5):
        for x, value, mesh, fmt in [
            (0.5, switch[row, 0], switch_mesh, "{:.0f}%"),
            (1.5, effect[row, 0], effect_mesh, "{:+.3f}"),
        ]:
            rgba = mesh.cmap(mesh.norm(value))
            luminance = 0.2126 * rgba[0] + 0.7152 * rgba[1] + 0.0722 * rgba[2]
            ax.text(x, row + 0.5, fmt.format(value), ha="center", va="center", fontsize=8.2, color="white" if luminance < 0.5 else "black")
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("D  PR-AUC selector audit", loc="left", fontsize=9.2, pad=5)
    base.save(fig, "Figure8")

    source = pd.DataFrame(
        {
            "dataset": order,
            "display_name": [base.DISPLAY[x] for x in order],
            "k": 32,
            "pr_auc_candidate_switch_rate_vs_roc": switch[:, 0] / 100,
            "delta_outer_pr_auc_vs_roc_selector": effect[:, 0],
            "recall_constrained_effect_included": False,
        }
    )
    source.to_csv(PACKAGE / "05_Source_Data" / "Figure8D_PR_AUC_only_source.csv", index=False)


if __name__ == "__main__":
    base.setup()
    figure8()
    print(PACKAGE / "03_Main_Figures" / "Figure8.pdf")
