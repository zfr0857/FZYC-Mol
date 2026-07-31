from __future__ import annotations

import importlib.util
import os
import re
import shutil
from pathlib import Path
from xml.etree import ElementTree as ET

import fitz
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.ticker import NullFormatter
from PIL import Image


ROOT = Path(r"D:\fzyc")
PACKAGE = ROOT / "output" / "paper43_jcheminform_completion_20260726"
OUT = PACKAGE / "main_figures_submission"
TABLES = PACKAGE / "additional_files" / "tables"
MINOR = ROOT / "output" / "paper25_pre_submission_minor_revision_20260715"
ANALYSIS = ROOT / "output" / "paper21_final_reanalysis_20260713"
ANALYSIS_WITH_COMPOSITION = ROOT / "output" / "paper22_major_revision_20260713"

BLUE, ORANGE, TEAL, PURPLE = "#315E8A", "#D58135", "#2F8B83", "#78689A"
GREY, RED, INK, LIGHT = "#7A7F87", "#B85C5C", "#202830", "#E3E7EA"
DISPLAY = {
    "bace": "BACE", "bbbp": "BBBP", "clintox": "ClinTox", "esol": "ESOL",
    "freesolv": "FreeSolv", "lipo": "Lipophilicity", "tdc_caco2_wang": "Caco2",
    "tdc_hia_hou": "HIA", "tdc_pgp_broccatelli": "P-gp",
}


def setup() -> None:
    mpl.rcParams.update({
        "font.family": "Times New Roman", "font.serif": ["Times New Roman"],
        "font.size": 9.0, "axes.titlesize": 10.3, "axes.titleweight": "bold",
        "axes.labelsize": 9.2, "xtick.labelsize": 8.2, "ytick.labelsize": 8.2,
        "legend.fontsize": 8.2, "axes.linewidth": 0.75,
        "axes.spines.top": False, "axes.spines.right": False,
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
        "mathtext.fontset": "custom", "mathtext.rm": "Times New Roman",
        "mathtext.it": "Times New Roman:italic", "axes.unicode_minus": False,
        "savefig.facecolor": "white", "figure.facecolor": "white",
    })


def save(fig: plt.Figure, number: int, stem: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for item in fig.findobj(match=mpl.text.Text):
        if item.get_text() and item.get_fontsize() < 7.7:
            item.set_fontsize(7.7)
    for suffix, kwargs in [("pdf", {}), ("svg", {}), ("png", {"dpi": 600})]:
        target = OUT / (f"Figure{number}_600dpi.png" if suffix == "png" else f"Figure{number}.{suffix}")
        fig.savefig(target, bbox_inches="tight", facecolor="white", **kwargs)
    fig.savefig(OUT / f"{stem}.pdf", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def clean(ax: plt.Axes, axis: str = "y") -> None:
    ax.grid(axis=axis, color=LIGHT, linewidth=0.6, alpha=0.8)
    ax.set_axisbelow(True)


def header(fig: plt.Figure, spec, label: str, title: str):
    sub = spec.subgridspec(2, 1, height_ratios=[0.15, 0.85], hspace=0)
    h = fig.add_subplot(sub[0]); h.axis("off")
    h.text(-0.10, 0.20, label, fontsize=12, fontweight="bold", va="bottom")
    h.text(0.02, 0.20, title, fontsize=10.3, fontweight="bold", va="bottom")
    return sub[1]


def figure1() -> None:
    fig, ax = plt.subplots(figsize=(6.69, 4.55))
    ax.set_xlim(0, 10); ax.set_ylim(0, 7.2); ax.axis("off")
    blocks = [
        (0.15, 5.05, 1.75, 1.15, "9 endpoints\n32 registered\ncandidates", "#EAF1F7"),
        (2.25, 5.05, 1.80, 1.15, "10 split seeds\n3 × 3 nested folds", "#E7F2EF"),
        (4.42, 5.05, 2.15, 1.15, "K-invariant K = 32\nleave-one-seed-out\nreference", "#FFF2CC"),
        (6.95, 5.05, 2.75, 1.15, "Natural-scale contrasts\nand seed-block intervals", "#FBE9DD"),
        (0.95, 2.75, 2.15, 1.15, "Metric-matched\nselection\nPR-AUC and recall rule", "#EEEAF5"),
        (3.55, 2.75, 2.15, 1.15, "Practical-equivalence\nsets and stability", "#EEEAF5"),
        (6.15, 2.75, 2.55, 1.15, "Dependence controls and\nrecovery simulation", "#EEEAF5"),
        (1.55, 0.60, 3.20, 1.05, "Five-seed secondary composition\nand bounded compute", "#F3F3F3"),
        (5.25, 0.60, 3.20, 1.05, "Chemical support and\nthree-endpoint transfer", "#F3F3F3"),
    ]
    for x, y, w, h, label, color in blocks:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.025,rounding_size=0.08",
                                    facecolor=color, edgecolor=INK, linewidth=0.9))
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center",
                fontsize=7.8, linespacing=1.05)
    arrows = [((1.90, 5.63), (2.25, 5.63)), ((4.05, 5.63), (4.42, 5.63)),
              ((6.57, 5.63), (6.95, 5.63)), ((3.15, 5.05), (2.10, 3.90)),
              ((5.50, 5.05), (4.62, 3.90)), ((8.20, 5.05), (7.42, 3.90)),
              ((4.62, 2.75), (3.55, 1.65)), ((7.42, 2.75), (6.85, 1.65))]
    for start, end in arrows:
        ax.annotate("", xy=end, xytext=start, arrowprops=dict(arrowstyle="->", lw=1.0, color=INK))
    ax.text(0.15, 6.72, "Nested audit and evidence hierarchy", fontsize=12, fontweight="bold")
    ax.text(0.15, 6.37, "Can expanded opportunity be realised reproducibly from finite validation?", fontsize=9.2)
    save(fig, 1, "Figure_1_nested_audit_and_evidence_hierarchy")


def figure2_custom() -> None:
    """Ten-seed effective-diversity audit (outer 30 units; inner results in S6-S7)."""
    source = PACKAGE / "source_data"
    d = pd.read_csv(source / "effective_diversity_10seed_units.csv")
    loo = pd.read_csv(source / "effective_diversity_10seed_leave_one_out.csv")
    refs = pd.read_csv(source / "effective_diversity_10seed_reference_sensitivity.csv")
    d = d[(d.matrix_level.eq("outer")) & (d.reference_label.eq("candidate_1"))]
    loo = loo[loo.matrix_level.eq("outer")]
    refs = refs[refs.matrix_level.eq("outer")]

    fig = plt.figure(figsize=(6.69, 5.25))
    gs = fig.add_gridspec(2, 2, left=.12, right=.985, bottom=.10, top=.80,
                          wspace=.42, hspace=.48, width_ratios=[.94, 1.06])
    axes = np.asarray([[fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1])],
                       [fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])]])
    modes = [
        ("raw", BLUE, "o", "Raw"),
        ("row_centred", ORANGE, "s", "Row-centred"),
        ("fixed_reference_relative", TEAL, "^", "Fixed-reference"),
        ("within_unit_rank", PURPLE, "D", "Within-unit rank"),
    ]

    ax = axes[0, 0]
    ax.set_title("A  Effective diversity across K", loc="left", pad=5)
    handles = []
    for mode, color, marker, label in modes:
        q = (d[d.transformation.eq(mode)].groupby("candidate_count")["ledoit_wolf_entropy_rank"]
             .agg(y="median", lo=lambda x: x.quantile(.25), hi=lambda x: x.quantile(.75)).reset_index())
        line, = ax.plot(q.candidate_count, q.y, marker=marker, color=color, label=label,
                        lw=1.35, ms=4.2)
        ax.fill_between(q.candidate_count, q.lo, q.hi, color=color, alpha=.08)
        handles.append(line)
    nominal, = ax.plot([4, 32], [4, 32], ":", color=GREY, label="Nominal K", lw=1.0)
    ax.set(xlabel="Nominal candidate count, K", ylabel="Ledoit–Wolf entropy rank",
           xticks=[4, 8, 16, 32])
    clean(ax)

    ax = axes[0, 1]
    ax.set_title("B  Entropy–participation concordance", loc="left", pad=5)
    q = d[d.candidate_count.eq(32)]
    for mode, color, marker, _ in modes:
        z = q[q.transformation.eq(mode)]
        ax.scatter(z.ledoit_wolf_entropy_rank, z.ledoit_wolf_participation_rank,
                   color=color, marker=marker, s=31, edgecolors="white", linewidths=.5)
    lim = [1, max(q.ledoit_wolf_entropy_rank.max(), q.ledoit_wolf_participation_rank.max()) * 1.04]
    ax.plot(lim, lim, ":", color=GREY, lw=1.0)
    ax.set(xlabel="Entropy rank", ylabel="Participation-ratio rank")
    clean(ax)

    ax = axes[1, 0]
    ax.set_title("C  Correlation after adjustment", loc="left", pad=5)
    for mode, color, marker, _ in modes:
        z = d[d.transformation.eq(mode)].groupby("candidate_count").ledoit_wolf_median_correlation.median()
        ax.plot(z.index, z.values, marker=marker, color=color, ms=4.2, lw=1.25)
    ax.axhline(0, color=GREY, lw=.8)
    ax.set(xlabel="Nominal candidate count, K", ylabel="Median candidate correlation",
           xticks=[4, 8, 16, 32])
    clean(ax)

    ax = axes[1, 1]
    ax.set_title("D  Endpoint and reference sensitivity", loc="left", pad=5)
    q = d[(d.candidate_count.eq(32)) &
          (d.transformation.eq("fixed_reference_relative"))].sort_values("ledoit_wolf_entropy_rank")
    y = np.arange(len(q))
    for i, (_, row) in enumerate(q.iterrows()):
        lv = loo[(loo.task.eq(row.task)) &
                 (loo.transformation.eq("fixed_reference_relative")) &
                 (loo.omission_type.eq("seed"))].ledoit_wolf_entropy_rank
        fv = loo[(loo.task.eq(row.task)) &
                 (loo.transformation.eq("fixed_reference_relative")) &
                 (loo.omission_type.eq("outer_fold"))].ledoit_wolf_entropy_rank
        rv = refs[(refs.task.eq(row.task)) &
                  (refs.reference_label.eq("predefined_linear_baseline"))].ledoit_wolf_entropy_rank
        ax.plot([lv.min(), lv.max()], [i, i], color=GREY, lw=1.5)
        ax.plot([fv.min(), fv.max()], [i + .10, i + .10], color=GREY, lw=1.2, ls="--")
        ax.plot(row.ledoit_wolf_entropy_rank, i, "o", color=TEAL, ms=4.6)
        if len(rv):
            ax.scatter([float(rv.median())], [i], facecolors="white", edgecolors=PURPLE,
                       marker="D", s=27, lw=1.0)
    ax.set(yticks=y, yticklabels=[DISPLAY[x] for x in q.task],
           xlabel="Reference-relative entropy rank")
    ax.tick_params(axis="y", labelsize=7.8)
    clean(ax, "x")

    fig.legend([*handles, nominal], [h.get_label() for h in [*handles, nominal]],
               loc="upper center", bbox_to_anchor=(.52, .985), ncol=5,
               frameon=False, handlelength=1.8, columnspacing=1.0)
    sensitivity = [
        Line2D([0], [0], color=GREY, ls="-", label="Leave-one-seed"),
        Line2D([0], [0], color=GREY, ls="--", label="Leave-one-outer-fold"),
        Line2D([0], [0], marker="D", ls="", mfc="white", mec=PURPLE,
               label="Predefined reference"),
    ]
    fig.legend(handles=sensitivity, loc="upper center", bbox_to_anchor=(.52, .935),
               ncol=3, frameon=False, handlelength=1.8, columnspacing=1.4)
    save(fig, 2, "Figure_2_candidate_diversity_after_adjustment")


def figure3() -> None:
    ranking = pd.read_csv(MINOR / "ranking_metric_main_summary.csv").sort_values("candidate_count")
    null = pd.read_csv(MINOR / "mechanism_permutation_null_summary.csv")
    signal = pd.read_csv(MINOR / "mechanism_signal_recovery_summary.csv")
    controls = pd.read_csv(ANALYSIS_WITH_COMPOSITION / "candidate_composition_controls.csv")
    effects = pd.read_csv(TABLES / "fixed_reference_k32_vs_k4_contrasts.csv")
    effects = effects[effects.estimand.eq("fixed_k32_gap")]

    fig = plt.figure(figsize=(6.69, 5.45))
    gs = fig.add_gridspec(2, 2, left=.105, right=.98, bottom=.08, top=.985, hspace=.40, wspace=.42)
    axes = []
    for spec, label, title in zip(gs, "ABCD", ["Chance-adjusted top-rank recovery", "Signal-recovery calibration",
                                                "K-invariant full-registry effects", "Candidate-composition controls"]):
        axes.append((fig.add_subplot(header(fig, spec, label, title)), spec))

    ax = axes[0][0]
    envelope = null.groupby("candidate_count", as_index=False).agg(lo=("null_q025", "min"), hi=("null_q975", "max"))
    ax.fill_between(envelope.candidate_count, envelope.lo, envelope.hi, color=GREY, alpha=.15, label="Permutation 95% envelope")
    ax.plot(ranking.candidate_count, ranking.chance_adjusted_hit_median, "o-", color=BLUE, label="CAHit@3")
    ax.plot(ranking.candidate_count, ranking.normalized_mrr_gain_median, "s-", color=TEAL, label="Normalized MRR gain")
    ax.axhline(0, color=GREY, lw=.8); ax.set(xlabel="Candidate count, K", ylabel="Chance-adjusted score", xticks=[4, 8, 16, 32])
    ax.legend(frameon=False, fontsize=7.7); clean(ax)

    ax = axes[1][0]
    for k, color, marker in zip([4, 8, 16, 32], [BLUE, TEAL, ORANGE, PURPLE], ["o", "s", "^", "D"]):
        q = signal[signal.candidate_count.eq(k)].sort_values("injected_signal")
        ax.plot(q.injected_signal, q.chance_adjusted_hit_median, marker=marker, color=color, label=f"K = {k}")
    ax.axhline(0, color=GREY, lw=.8); ax.set(xlabel="Injected validation–audit signal", ylabel="Median CAHit@3")
    ax.legend(frameon=False, ncol=2, fontsize=7.7); clean(ax)

    axes[2][0].remove()
    csub = axes[2][1].subgridspec(2, 1, height_ratios=[.15, .85], hspace=0)[1].subgridspec(1, 2, wspace=.62)
    for ax, task_type, color, xlabel, order in [
        (fig.add_subplot(csub[0]), "classification", BLUE, "ROC-AUC contrast", ["tdc_hia_hou", "clintox", "bace", "tdc_pgp_broccatelli", "bbbp"]),
        (fig.add_subplot(csub[1]), "regression", ORANGE, "RMSE contrast", ["lipo", "freesolv", "tdc_caco2_wang", "esol"]),
    ]:
        q = effects[effects.task_type.eq(task_type)].set_index("dataset").loc[order].reset_index()
        y = np.arange(len(q)); x = q.mean_natural_scale_effect.to_numpy(); lo = q.seed_block_interval_low.to_numpy(); hi = q.seed_block_interval_high.to_numpy()
        ax.errorbar(x, y, xerr=[x-lo, hi-x], fmt="none", ecolor=GREY, capsize=2.4, lw=1)
        for xi, yi, li, hii in zip(x, y, lo, hi):
            sig = li > 0 or hii < 0
            ax.scatter(xi, yi, s=30, facecolors=color if sig else "white", edgecolors=color, zorder=3)
        ax.axvline(0, color=INK, lw=.8); ax.set(yticks=y, yticklabels=[DISPLAY[x] for x in q.dataset], xlabel=xlabel)
        ax.tick_params(axis="y", labelsize=7.8); clean(ax, "x")

    ax = axes[3][0]
    modes = sorted(controls["mode"].unique())
    for mode, color, marker in zip(modes, [BLUE, TEAL, ORANGE, PURPLE, GREY, RED], ["o", "s", "^", "D", "P", "X"]):
        q = controls[controls["mode"].eq(mode)].sort_values("pool_size")
        ax.plot(q.pool_size, q.chance_adjusted_hit_mean, marker=marker, color=color, label=mode.replace("_", " "), lw=1.2)
    ax.axhline(0, color=GREY, lw=.8); ax.set(xlabel="Candidate count, K", ylabel="Chance-adjusted hit", xticks=[4, 8, 16, 32])
    ax.legend(frameon=False, fontsize=7.1, ncol=2); clean(ax)
    save(fig, 3, "Figure_3_chance_adjusted_ranking_and_fixed_reference_effects")


def figure8() -> None:
    fixed = pd.read_csv(TABLES / "fixed_reference_units.csv")
    tau = pd.read_csv(TABLES / "tau_near_equivalence_units.csv")
    comp = pd.read_csv(TABLES / "classification_metric_selector_comparisons.csv")
    working = tau[((tau.task_type == "classification") & (tau.tau == .010)) |
                  ((tau.task_type == "regression") & (tau.tau == .050))]
    # 170 mm wide and comfortably below the journal's requested height ceiling.
    # Panel A is factorised by task so ROC-AUC and RMSE never share a y-axis.
    fig = plt.figure(figsize=(6.69, 6.25))
    gs = fig.add_gridspec(2, 2, left=.105, right=.985, bottom=.085, top=.90,
                          hspace=.40, wspace=.34)
    asub = gs[0, 0].subgridspec(2, 1, hspace=.42)
    estimands = [
        ("fixed_k32_gap", "-", "o", "K-invariant"),
        ("k_dependent_crossfit_gap", "--", "s", "K-dependent"),
        ("same_fold_opportunity_gap", ":", "^", "Same-fold"),
    ]
    a_axes = []
    for index, (task, color, marker, title, ylabel) in enumerate([
        ("classification", BLUE, "o", "Classification", "ROC-AUC gap"),
        ("regression", ORANGE, "s", "Regression", "RMSE gap"),
    ]):
        ax = fig.add_subplot(asub[index], sharex=a_axes[0] if a_axes else None)
        q = fixed[fixed.task_type.eq(task)]
        for col, ls, estimand_marker, _ in estimands:
            z = q.groupby("pool_size")[col].mean().reindex([4, 8, 16, 32])
            ax.plot(z.index, z, color=color, marker=estimand_marker, ls=ls, lw=1.25, ms=4.1)
        ax.axhline(0, color=GREY, lw=.8)
        ax.set(ylabel=ylabel, xticks=[4, 8, 16, 32])
        ax.set_title(title, loc="left", pad=2, fontsize=9.0)
        if index == 0:
            ax.tick_params(axis="x", labelbottom=False)
        else:
            ax.set_xlabel("Candidate count, K")
        clean(ax)
        a_axes.append(ax)
    fig.text(.105, .972, "A  Reference and opportunity gaps", fontsize=10.3, fontweight="bold", va="top")
    fig.legend(
        handles=[Line2D([0], [0], color=INK, marker=mark, ls=ls, lw=1.35,
                        label=label) for _, ls, mark, label in estimands],
        loc="upper center", bbox_to_anchor=(.325, .952), ncol=3, frameon=False,
        fontsize=7.8, handlelength=1.8, columnspacing=.9,
    )

    ax = fig.add_subplot(gs[0, 1])
    for task, label, color, marker in [("classification", "Classification, τ = 0.010", BLUE, "o"), ("regression", "Regression, τ = 0.050", ORANGE, "s")]:
        z = working[working.task_type.eq(task)].groupby("pool_size").crossfit_tau_success.mean().reindex([4, 8, 16, 32])
        ax.plot(z.index, 100*z, marker=marker, color=color, label=label, lw=1.25, ms=4.2)
    ax.set(xlabel="Candidate count, K", ylabel="Cross-fitted τ-success (%)", xticks=[4, 8, 16, 32], ylim=(0, 100))
    b_left = gs[0, 1].get_position(fig).x0
    fig.text(b_left, .972, "B  Practical-equivalence success", fontsize=10.3,
             fontweight="bold", va="top")
    ax.legend(frameon=False, fontsize=8.0, loc="lower right", handlelength=2.1)
    clean(ax)

    ax = fig.add_subplot(gs[1, 0])
    for task, label, color, marker in [("classification", "Classification, τ = 0.010", BLUE, "o"), ("regression", "Regression, τ = 0.050", ORANGE, "s")]:
        z = working[working.task_type.eq(task)].groupby("pool_size").crossfit_near_equivalent_n.mean().reindex([4, 8, 16, 32])
        ax.plot(z.index, z, marker=marker, color=color, label=label, lw=1.25, ms=4.2)
    ax.set(xlabel="Candidate count, K", ylabel="Mean cross-fitted set size", xticks=[4, 8, 16, 32]); ax.set_ylim(bottom=0)
    ax.set_title("C  Near-equivalent candidate sets", loc="left", pad=4)
    clean(ax)

    endpoint_order = ["bace", "bbbp", "clintox", "tdc_hia_hou", "tdc_pgp_broccatelli"]
    k32 = comp[comp.pool_size.eq(32)].groupby(["alternative_selector", "dataset"]).mean(numeric_only=True)
    switch = np.column_stack([
        100*k32.loc[("pr_auc",), "candidate_changed_vs_roc"].reindex(endpoint_order).to_numpy(),
        100*k32.loc[("minority_constrained",), "candidate_changed_vs_roc"].reindex(endpoint_order).to_numpy(),
    ])
    effect = np.column_stack([
        k32.loc[("pr_auc",), "delta_outer_pr_auc_vs_roc_selector"].reindex(endpoint_order).to_numpy(),
        k32.loc[("minority_constrained",), "delta_outer_minority_recall_vs_roc_selector"].reindex(endpoint_order).to_numpy(),
    ])
    dsub = gs[1, 1].subgridspec(1, 2, wspace=.12)
    heat_axes = []
    for ax, arr, cols, cmap, lim, fmt, title in [
        (fig.add_subplot(dsub[0]), switch, ["PR-AUC\nswitch", "Recall-rule\nswitch"], "Blues", (0, 100), "{:.0f}%", "D  Candidate switching"),
        (fig.add_subplot(dsub[1]), effect, ["Δ PR-AUC", "Δ minority\nrecall"], "RdBu_r", (-.04, .04), "{:+.3f}", "Outer change"),
    ]:
        mesh = ax.pcolormesh(np.arange(3), np.arange(6), arr, shading="flat", cmap=cmap, vmin=lim[0], vmax=lim[1])
        ax.set_xlim(0, 2); ax.set_ylim(5, 0); ax.set_xticks([.5, 1.5], cols)
        ax.set_yticks(np.arange(5)+.5, [DISPLAY[x] for x in endpoint_order] if not heat_axes else [])
        for i in range(5):
            for j in range(2):
                rgba = mesh.cmap(mesh.norm(arr[i, j]))
                luminance = .2126*rgba[0] + .7152*rgba[1] + .0722*rgba[2]
                ax.text(j+.5, i+.5, fmt.format(arr[i, j]), ha="center", va="center",
                        fontsize=8.5, color="white" if luminance < .50 else "black")
        for s in ax.spines.values(): s.set_visible(False)
        ax.tick_params(axis="x", labelsize=8.2); ax.tick_params(axis="y", labelsize=8.2)
        ax.set_title(title, loc="left" if not heat_axes else "center", fontsize=10.3, pad=5)
        heat_axes.append(ax)
    save(fig, 8, "Figure_8_practical_equivalence_and_metric_selection")


def import_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def figure7_custom(data: dict[str, pd.DataFrame], p31) -> None:
    summary, stability = data["summary"], data["stability"]
    units, budget_units = data["units"], data["budget_units"]
    pools, tasks, ks = p31.POOLS, p31.TASKS, p31.KS
    pool_short, task_label, colors = p31.POOL_SHORT, p31.TASK_LABEL, p31.COLORS
    base = summary[summary.design.eq("equal_K") & summary.anchor_scheme.eq("shared_morgan_linear")]
    fig = plt.figure(figsize=(6.40, 5.88))
    gs = fig.add_gridspec(2, 2, left=.12, right=.985, bottom=.075, top=.895, hspace=.48, wspace=.38)

    asub = gs[0, 0].subgridspec(1, 2, wspace=.12)
    k32 = base[base.candidate_count.eq(32)]
    arrays = [k32.pivot_table(index="task", columns="pool", values=m).reindex(index=tasks, columns=pools).to_numpy(float)
              for m in ["homogeneous_normalized_selected_gain_mean", "homogeneous_normalized_oracle_opportunity_mean"]]
    lim = max(float(np.nanquantile(np.abs(np.concatenate([a.ravel() for a in arrays])), .98)), 1e-6)
    for idx, (arr, title) in enumerate(zip(arrays, ["Selected gain", "Audit-best opportunity"])):
        ax = fig.add_subplot(asub[idx]); ax.pcolormesh(np.arange(4), np.arange(7), arr, cmap="RdBu_r", vmin=-lim, vmax=lim, shading="flat")
        ax.set(xlim=(0, 3), ylim=(6, 0)); ax.set_xticks(np.arange(3)+.5, ["H", "MV", "M"])
        ax.set_yticks(np.arange(6)+.5, [task_label[t] for t in tasks] if idx == 0 else [])
        ax.set_title(title, fontsize=9.2, pad=2)
        for i in range(6):
            for j in range(3): ax.text(j+.5, i+.5, f"{arr[i,j]:.2f}", ha="center", va="center", fontsize=7.7)
        for s in ax.spines.values(): s.set_visible(False)
    a_left = gs[0, 0].get_position(fig).x0
    b_left = gs[0, 1].get_position(fig).x0
    c_left = gs[1, 0].get_position(fig).x0
    d_left = gs[1, 1].get_position(fig).x0
    fig.text(a_left, .975, "A  Endpoint-level opportunity at K = 32",
             fontsize=10.3, fontweight="bold", va="top")
    fig.text(.255, .515, "H: homogeneous; MV: multiview; M: modern", ha="center", fontsize=7.7)

    bsub = gs[0, 1].subgridspec(1, 2, wspace=.28)
    for idx, task_type in enumerate(["classification", "regression"]):
        ax = fig.add_subplot(bsub[idx])
        for pool in pools:
            part = base[(base.pool.eq(pool)) & (base.task_type.eq(task_type))].groupby("candidate_count").agg(
                selected=("homogeneous_normalized_selected_gain_mean", "mean"), gap=("homogeneous_normalized_cross_fitted_gap_mean", "mean")).reindex(ks)
            ax.plot(ks, part.selected, "o-", color=colors[pool], lw=1.25, ms=3.5)
            ax.plot(ks, part.gap, "o--", color=colors[pool], mfc="white", lw=1.0, ms=3.2)
        ax.axhline(0, color=GREY, lw=.7); ax.set_xticks(ks); ax.set_title(task_type.title(), fontsize=9.2); ax.set_xlabel("K"); clean(ax)
        if idx == 0: ax.set_ylabel("Normalized value")
    fig.text(.755, .475, "Blue: H   Green: MV   Orange: M", ha="center", fontsize=7.7)
    fig.text(.755, .458, "Solid: selected gain   Dashed: cross-fitted gap", ha="center", fontsize=7.7)
    fig.text(b_left, .975, "B  Composition-by-K ladder",
             fontsize=10.3, fontweight="bold", va="top")

    row_index = pd.MultiIndex.from_product([tasks, pools], names=["task", "pool"])
    heat = base.pivot_table(index=["task", "pool"], columns="candidate_count", values="chance_adjusted_hit3_mean").reindex(row_index)[ks]
    entropy = stability.set_index(["task", "pool", "candidate_count"])["candidate_selection_entropy_normalized"]
    matrix = np.c_[heat.to_numpy(float), [entropy.get((t, p, 32), np.nan) for t, p in row_index]]
    ax = fig.add_subplot(gs[1, 0]); ax.pcolormesh(np.arange(6), np.arange(19), matrix, cmap="RdYlBu", vmin=-1, vmax=1, shading="flat")
    ax.set(xlim=(0, 5), ylim=(18, 0)); ax.set_xticks(np.arange(5)+.5, ["4", "8", "16", "32", "Entropy"])
    code = {pools[0]: "H", pools[1]: "MV", pools[2]: "M"}
    ax.set_yticks(np.arange(18)+.5, [f"{task_label[t]}–{code[p]}" for t,p in row_index], fontsize=7.7)
    for i in range(18):
        for j in range(5):
            v = matrix[i,j]
            if np.isfinite(v): ax.text(j+.5, i+.5, f"{v:.2f}", ha="center", va="center", fontsize=7.7, color="white" if abs(v)>.65 else INK)
    ax.axvline(4, color="white", lw=1.5); [s.set_visible(False) for s in ax.spines.values()]
    ax.set_xlabel("Candidate count, K; entropy at K = 32")

    equal_k = units[units.design.eq("equal_K") & units.anchor_scheme.eq("shared_morgan_linear")].groupby(["pool", "candidate_count"], as_index=False).agg(time=("audit_fit_seconds", "mean"), gain=("homogeneous_normalized_selected_gain", "mean"))
    equal_b = budget_units.groupby(["pool", "candidate_count"], as_index=False).agg(time=("audit_fit_seconds", "mean"), gain=("homogeneous_normalized_selected_gain", "mean"))
    ax = fig.add_subplot(gs[1, 1])
    for pool in pools:
        for table, marker, ls, prefix in [(equal_k, "o", "-", ""), (equal_b, "D", "--", "B")]:
            q = table[table.pool.eq(pool)].sort_values("candidate_count")
            ax.plot(q.time, q.gain, color=colors[pool], ls=ls, lw=1.15)
            ax.scatter(q.time, q.gain, color=colors[pool], marker=marker, s=14 + 1.1*q.candidate_count, zorder=3)
    ax.set_xscale("log"); lo,hi=ax.get_xlim(); ticks=[x for x in [1,10,100,1000] if lo<=x<=hi]; ax.set_xticks(ticks); ax.set_xticklabels([str(x) for x in ticks]); ax.xaxis.set_minor_formatter(NullFormatter())
    ax.axhline(0,color=GREY,lw=.7); ax.set_xlabel("Downstream audit time (s, log scale)"); ax.set_ylabel("Normalized selected gain"); clean(ax,"both")
    handles = [Line2D([0],[0],color=colors[p],label=pool_short[p]) for p in pools]
    handles += [Line2D([0],[0],color=INK,marker="o",label="Equal K"),Line2D([0],[0],color=INK,marker="D",ls="--",label="Equal budget")]
    ax.legend(handles=handles,frameon=False,ncol=2,fontsize=7.7,loc="best")
    lower_title_y = gs[1, 0].get_position(fig).y1 + .018
    fig.text(c_left, lower_title_y, "C  Ranking fidelity and selection stability",
             fontsize=10.3, fontweight="bold", va="bottom")
    fig.text(d_left, lower_title_y, "D  Downstream budget–benefit frontier",
             fontsize=10.3, fontweight="bold", va="bottom")
    save(fig, 7, "Figure_7_expanded_equal_size_intervention")


def legacy_figures() -> None:
    os.environ["FZYC_FIG_OUT"] = str(OUT)
    os.environ["FZYC_ANALYSIS_OUT"] = str(ANALYSIS_WITH_COMPOSITION)
    p21 = import_module(ROOT / "scripts" / "build_paper21_final_figures.py", "paper21fig")
    p21.setup(); mpl.rcParams["svg.fonttype"] = "none"
    def journal_save(fig, stem):
        number = int(stem.split("_")[1])
        # Tight bounding boxes for the legacy panels extend beyond the nominal canvas.
        # These canvas widths keep final files at or below the journal's 170-mm width
        # while retaining absolute text sizes of at least 7.7 pt.
        target_width = {4: 6.15, 5: 6.20, 6: 4.94}[number]
        width, height = fig.get_size_inches()
        fig.set_size_inches(target_width, height * target_width / width, forward=True)
        save(fig, number, stem)
    p21.save = journal_save
    for fn in [p21.figure4, p21.figure5, p21.figure6]: fn()
    p31 = import_module(ROOT / "scripts" / "build_paper31_figures_20260717.py", "paper31fig")
    p31.OUT = OUT
    p31.style(); setup(); figure7_custom(p31.load(), p31)


def main() -> None:
    setup(); OUT.mkdir(parents=True, exist_ok=True)
    figure1(); figure2_custom(); legacy_figures(); setup(); figure3(); figure8()
    print(OUT)


if __name__ == "__main__":
    main()
