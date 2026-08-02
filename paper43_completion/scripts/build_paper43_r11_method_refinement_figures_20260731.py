from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.gridspec import GridSpecFromSubplotSpec
from PIL import Image


ROOT = Path(r"D:\fzyc")
WORK = ROOT / "work" / "r11_method_refinement_20260731"
OUT = WORK / "figures"
MINOR = ROOT / "output" / "paper25_pre_submission_minor_revision_20260715"
ANALYSIS = ROOT / "output" / "paper22_major_revision_20260713"
SOURCE = ROOT / "work" / "cold_start_paper_release_2026-07-r11_20260731_01" / "paper43_completion" / "source_data"
BLUE, ORANGE, TEAL, PURPLE = "#315E8A", "#D58135", "#2F8B83", "#78689A"
GREY, RED, INK, LIGHT = "#7A7F87", "#B85C5C", "#202830", "#E3E7EA"
DISPLAY = {
    "bace": "BACE",
    "bbbp": "BBBP",
    "clintox": "ClinTox",
    "esol": "ESOL",
    "freesolv": "FreeSolv",
    "lipo": "Lipophilicity",
    "tdc_caco2_wang": "Caco2",
    "tdc_hia_hou": "HIA",
    "tdc_pgp_broccatelli": "P-gp",
}


def setup() -> None:
    mpl.rcParams.update(
        {
            "font.family": "Times New Roman",
            "font.serif": ["Times New Roman"],
            "font.size": 9,
            "axes.titlesize": 10.3,
            "axes.titleweight": "bold",
            "axes.labelsize": 9.2,
            "xtick.labelsize": 8.2,
            "ytick.labelsize": 8.2,
            "legend.fontsize": 8.2,
            "axes.linewidth": 0.75,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
            "mathtext.fontset": "stix",
            "axes.unicode_minus": False,
            "savefig.facecolor": "white",
            "figure.facecolor": "white",
        }
    )


def save(fig: mpl.figure.Figure, stem: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for item in fig.findobj(match=mpl.text.Text):
        if item.get_text() and item.get_fontsize() < 8:
            item.set_fontsize(8)
    fig.savefig(OUT / f"{stem}.svg", bbox_inches="tight", facecolor="white")
    fig.savefig(OUT / f"{stem}.pdf", bbox_inches="tight", facecolor="white")
    png = OUT / f"{stem}_600dpi.png"
    fig.savefig(png, dpi=600, bbox_inches="tight", facecolor="white")
    with Image.open(png) as image:
        image.convert("RGB").save(png, dpi=(600, 600), compress_level=6)
    plt.close(fig)


def clean(ax, axis: str = "y") -> None:
    ax.grid(axis=axis, color=LIGHT, lw=0.6, alpha=0.8)
    ax.set_axisbelow(True)


def header(fig, spec, letter: str, title: str):
    sub = spec.subgridspec(2, 1, height_ratios=[0.17, 0.83], hspace=0)
    h = fig.add_subplot(sub[0])
    h.axis("off")
    h.text(-0.10, 0.20, letter, fontsize=12, fontweight="bold", va="bottom")
    h.text(0.02, 0.20, title, fontsize=10.3, fontweight="bold", va="bottom")
    return sub[1]


def forest(ax, frame: pd.DataFrame, value: str, low: str, high: str, color: str, xlabel: str) -> None:
    y = np.arange(len(frame))
    x = frame[value].to_numpy(float)
    lo = frame[low].to_numpy(float)
    hi = frame[high].to_numpy(float)
    ax.errorbar(x, y, xerr=[x - lo, hi - x], fmt="none", ecolor=GREY, capsize=2.4, lw=1)
    for xi, yi, li, hii in zip(x, y, lo, hi, strict=True):
        excludes = li > 0 or hii < 0
        ax.scatter(xi, yi, s=31, facecolors=color if excludes else "white", edgecolors=color, zorder=3)
    ax.axvline(0, color=INK, lw=0.8)
    ax.set(yticks=y, yticklabels=[DISPLAY[x] for x in frame.dataset], xlabel=xlabel)
    ax.invert_yaxis()
    clean(ax, "x")


def figure3() -> None:
    decomp = pd.read_csv(WORK / "completion_gap_decomposition_endpoint_summary.csv")
    ranking = pd.read_csv(MINOR / "ranking_metric_main_summary.csv").sort_values("candidate_count")
    null = pd.read_csv(MINOR / "mechanism_permutation_null_summary.csv")
    signal = pd.read_csv(MINOR / "mechanism_signal_recovery_summary.csv")
    controls = pd.read_csv(ANALYSIS / "candidate_composition_controls.csv")
    fig = plt.figure(figsize=(6.69, 5.62))
    gs = fig.add_gridspec(2, 2, left=0.105, right=0.98, bottom=0.08, top=0.985, hspace=0.38, wspace=0.48)
    titles = [
        "Full-registry gap: Δ_inv = Δ_avail + Δ_dep",
        "Chance-adjusted top-rank recovery",
        "Signal-recovery calibration",
        "Candidate-composition controls",
    ]
    content = [header(fig, spec, letter, title) for spec, letter, title in zip(gs, "ABCD", titles, strict=True)]
    a = content[0].subgridspec(1, 2, wspace=0.82)
    for ax, kind, color, xlabel, order in [
        (fig.add_subplot(a[0]), "classification", BLUE, "ROC-AUC contrast", ["bbbp", "tdc_pgp_broccatelli", "bace", "clintox", "tdc_hia_hou"]),
        (fig.add_subplot(a[1]), "regression", ORANGE, "RMSE contrast", ["lipo", "freesolv", "tdc_caco2_wang", "esol"]),
    ]:
        q = decomp[decomp.task_type.eq(kind)].set_index("dataset").loc[order].reset_index()
        forest(ax, q, "Delta_inv", "Delta_inv_low", "Delta_inv_high", color, xlabel)
    ax = fig.add_subplot(content[1])
    env = null.groupby("candidate_count", as_index=False).agg(lo=("null_q025", "min"), hi=("null_q975", "max"))
    ax.fill_between(env.candidate_count, env.lo, env.hi, color=GREY, alpha=0.15, label="Permutation 95% envelope")
    ax.plot(ranking.candidate_count, ranking.chance_adjusted_hit_median, "o-", color=BLUE, label="CAHit@3")
    ax.plot(ranking.candidate_count, ranking.normalized_mrr_gain_median, "s-", color=TEAL, label="Normalized MRR gain")
    ax.axhline(0, color=GREY, lw=0.8)
    ax.set(xlabel="Candidate count, K", ylabel="Chance-adjusted score", xticks=[4, 8, 16, 32])
    ax.legend(frameon=False, fontsize=8)
    clean(ax)

    ax = fig.add_subplot(content[2])
    for k, color, marker in zip([4, 8, 16, 32], [BLUE, TEAL, ORANGE, PURPLE], ["o", "s", "^", "D"], strict=True):
        q = signal[signal.candidate_count.eq(k)].sort_values("injected_signal")
        ax.plot(q.injected_signal, q.chance_adjusted_hit_median, marker=marker, color=color, label=f"K = {k}")
    ax.axhline(0, color=GREY, lw=0.8)
    ax.set(xlabel="Injected validation–audit signal", ylabel="Median CAHit@3")
    ax.legend(frameon=False, ncol=2)
    clean(ax)

    ax = fig.add_subplot(content[3])
    modes = sorted(controls["mode"].unique())
    for mode, color, marker in zip(modes, [BLUE, TEAL, ORANGE, PURPLE, GREY, RED][: len(modes)], ["o", "s", "^", "D", "P", "X"][: len(modes)], strict=True):
        q = controls[controls["mode"].eq(mode)].sort_values("pool_size")
        ax.plot(q.pool_size, q.chance_adjusted_hit_mean, marker=marker, color=color, label=mode.replace("_", " "), lw=1.2)
    ax.axhline(0, color=GREY, lw=0.8)
    ax.set(xlabel="Candidate count, K", ylabel="Chance-adjusted hit", xticks=[4, 8, 16, 32])
    ax.legend(frameon=False, ncol=2, fontsize=8)
    clean(ax)
    save(fig, "Figure3_method_refinement")


def supplementary_decomposition() -> None:
    data = pd.read_csv(WORK / "completion_gap_decomposition_endpoint_summary.csv")
    fig, axes = plt.subplots(1, 2, figsize=(6.69, 3.45), gridspec_kw={"wspace": 0.65})
    for ax, kind, color, order, xlabel in [
        (axes[0], "classification", BLUE, ["bbbp", "tdc_pgp_broccatelli", "bace", "clintox", "tdc_hia_hou"], "ROC-AUC contrast"),
        (axes[1], "regression", ORANGE, ["lipo", "freesolv", "tdc_caco2_wang", "esol"], "RMSE contrast"),
    ]:
        q = data[data.task_type.eq(kind)].set_index("dataset").loc[order].reset_index()
        y = np.arange(len(q))
        offset = 0.14
        for value, low, high, marker, fill, label, shift in [
            ("Delta_avail", "Delta_avail_low", "Delta_avail_high", "o", color, r"$\Delta_{avail}$", -offset),
            ("Delta_dep", "Delta_dep_low", "Delta_dep_high", "s", "white", r"$\Delta_{dep}$", offset),
        ]:
            x = q[value].to_numpy(float)
            lo = q[low].to_numpy(float)
            hi = q[high].to_numpy(float)
            ax.errorbar(x, y + shift, xerr=[x - lo, hi - x], fmt="none", ecolor=GREY, capsize=2.2, lw=1)
            ax.scatter(x, y + shift, s=31, marker=marker, facecolors=fill, edgecolors=color, label=label, zorder=3)
        ax.axvline(0, color=INK, lw=0.8)
        ax.set(yticks=y, yticklabels=[DISPLAY[x] for x in q.dataset], xlabel=xlabel, title=kind.title())
        ax.invert_yaxis()
        clean(ax, "x")
    axes[0].legend(frameon=False, loc="best")
    fig.suptitle("Availability and within-prefix components of the K=32 minus K=4 completion-gap contrast", fontsize=10.5, fontweight="bold")
    save(fig, "FigureS26_completion_gap_decomposition")


def provisional_figure8d() -> None:
    data = pd.read_csv(WORK / "classification_metric_selector_comparisons_frozen_identity_diagnostic.csv")
    order = ["bace", "bbbp", "clintox", "tdc_hia_hou", "tdc_pgp_broccatelli"]
    k32 = data[data.pool_size.eq(32)].groupby(["alternative_selector", "dataset"]).mean(numeric_only=True)
    selector = "frozen_minority_constrained_diagnostic"
    switch = np.column_stack(
        [
            100 * k32.loc[("pr_auc",), "candidate_changed_vs_roc"].reindex(order),
            100 * k32.loc[(selector,), "candidate_changed_vs_roc"].reindex(order),
        ]
    )
    effect = np.column_stack(
        [
            k32.loc[("pr_auc",), "delta_outer_pr_auc_vs_roc_selector"].reindex(order),
            k32.loc[(selector,), "delta_outer_frozen_target_recall_vs_roc_selector"].reindex(order),
        ]
    )
    fig, axes = plt.subplots(1, 2, figsize=(6.69, 3.20), gridspec_kw={"width_ratios": [0.92, 1.08], "wspace": 0.34})
    for idx, (ax, arr, cols, cmap, lim, fmt, title) in enumerate(
        [
            (axes[0], switch, ["PR-AUC\nswitch", "Frozen-recall\nswitch"], "Blues", (0, 100), "{:.0f}%", "D1  Candidate switching"),
            (axes[1], effect, ["ΔPR-AUC", "Δfrozen-class\nrecall"], "RdBu_r", (-0.04, 0.04), "{:+.3f}", "D2  Outer performance change"),
        ]
    ):
        mesh = ax.pcolormesh(np.arange(3), np.arange(6), arr, shading="flat", cmap=cmap, vmin=lim[0], vmax=lim[1])
        ax.set(xlim=(0, 2), ylim=(5, 0))
        ax.set_xticks([0.5, 1.5], cols)
        ax.set_yticks(np.arange(5) + 0.5, [DISPLAY[x] for x in order] if idx == 0 else [])
        if idx == 1:
            ax.tick_params(axis="y", left=False, labelleft=False)
        for i in range(5):
            for j in range(2):
                rgba = mesh.cmap(mesh.norm(arr[i, j]))
                luminance = 0.2126 * rgba[0] + 0.7152 * rgba[1] + 0.0722 * rgba[2]
                ax.text(j + 0.5, i + 0.5, fmt.format(arr[i, j]), ha="center", va="center", fontsize=8, color="white" if luminance < 0.5 else "black")
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_title(title, loc="left", fontsize=10.2, pad=5)
    fig.suptitle("Provisional frozen-identity re-summary at archived inner thresholds", fontsize=10.8, fontweight="bold")
    save(fig, "Figure8D_frozen_identity_PROVISIONAL")


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
        [("classification", BLUE, "Classification", "ROC-AUC gap"), ("regression", ORANGE, "Regression", "RMSE gap")]
    ):
        ax = fig.add_subplot(asub[index], sharex=shared[0] if shared else None)
        subset = fixed[fixed.task_type.eq(kind)]
        for column, linestyle, marker, _ in estimands:
            values = subset.groupby("pool_size")[column].mean().reindex([4, 8, 16, 32])
            ax.plot(values.index, values, color=color, marker=marker, ls=linestyle, lw=1.25, ms=4.1)
        ax.axhline(0, color=GREY, lw=0.8)
        ax.set(ylabel=ylabel, xticks=[4, 8, 16, 32])
        ax.set_title(title, loc="left", pad=2, fontsize=9)
        if index == 0:
            ax.tick_params(axis="x", labelbottom=False)
        else:
            ax.set_xlabel("Candidate count, K")
        clean(ax)
        shared.append(ax)
    fig.text(0.105, 0.972, "A  Reference and opportunity gaps", fontsize=10.3, fontweight="bold", va="top")
    fig.legend(
        handles=[Line2D([0], [0], color=INK, marker=marker, ls=linestyle, label=label) for _, linestyle, marker, label in estimands],
        loc="upper center",
        bbox_to_anchor=(0.325, 0.952),
        ncol=3,
        frameon=False,
        fontsize=8,
    )

    ax = fig.add_subplot(gs[0, 1])
    for kind, label, color, marker in [
        ("classification", "Classification, tau = 0.010", BLUE, "o"),
        ("regression", "Regression, tau = 0.050", ORANGE, "s"),
    ]:
        values = working[working.task_type.eq(kind)].groupby("pool_size").crossfit_tau_success.mean().reindex([4, 8, 16, 32])
        ax.plot(values.index, 100 * values, marker=marker, color=color, label=label, lw=1.25, ms=4.2)
    ax.set(xlabel="Candidate count, K", ylabel="Cross-fitted tau-success (%)", xticks=[4, 8, 16, 32], ylim=(0, 100))
    ax.set_title("B  Practical-equivalence success", loc="left", pad=5)
    ax.legend(frameon=False, loc="lower right")
    clean(ax)

    ax = fig.add_subplot(gs[1, 0])
    for kind, label, color, marker in [
        ("classification", "Classification, tau = 0.010", BLUE, "o"),
        ("regression", "Regression, tau = 0.050", ORANGE, "s"),
    ]:
        values = working[working.task_type.eq(kind)].groupby("pool_size").crossfit_near_equivalent_n.mean().reindex([4, 8, 16, 32])
        ax.plot(values.index, values, marker=marker, color=color, label=label, lw=1.25, ms=4.2)
    ax.set(xlabel="Candidate count, K", ylabel="Mean cross-fitted set size", xticks=[4, 8, 16, 32])
    ax.set_ylim(bottom=0)
    ax.set_title("C  Near-equivalent candidate sets", loc="left", pad=4)
    ax.legend(frameon=False, loc="best")
    clean(ax)

    order = ["bace", "bbbp", "clintox", "tdc_hia_hou", "tdc_pgp_broccatelli"]
    k32 = comp[comp.pool_size.eq(32)].groupby(["alternative_selector", "dataset"]).mean(numeric_only=True)
    selector = "frozen_minority_constrained_diagnostic"
    switch = np.column_stack(
        [
            100 * k32.loc[("pr_auc",), "candidate_changed_vs_roc"].reindex(order),
            100 * k32.loc[(selector,), "candidate_changed_vs_roc"].reindex(order),
        ]
    )
    effect = np.column_stack(
        [
            k32.loc[("pr_auc",), "delta_outer_pr_auc_vs_roc_selector"].reindex(order),
            k32.loc[(selector,), "delta_outer_frozen_target_recall_vs_roc_selector"].reindex(order),
        ]
    )
    dsub = GridSpecFromSubplotSpec(1, 2, subplot_spec=gs[1, 1], wspace=0.46)
    for index, (array, columns, cmap, limits, fmt, title) in enumerate(
        [
            (switch, ["PR-AUC", "Frozen\nrecall"], "Blues", (0, 100), "{:.0f}%", "D1  Switch frequency*"),
            (effect, ["dPR-AUC", "d recall"], "RdBu_r", (-0.04, 0.04), "{:+.3f}", "D2  Outer change*"),
        ]
    ):
        ax = fig.add_subplot(dsub[index])
        mesh = ax.pcolormesh(np.arange(3), np.arange(6), array, shading="flat", cmap=cmap, vmin=limits[0], vmax=limits[1])
        ax.set(xlim=(0, 2), ylim=(5, 0))
        ax.set_xticks([0.5, 1.5], columns)
        ax.set_yticks(np.arange(5) + 0.5, [DISPLAY[x] for x in order] if index == 0 else [])
        if index == 1:
            ax.tick_params(axis="y", left=False, labelleft=False)
        for row in range(5):
            for column in range(2):
                rgba = mesh.cmap(mesh.norm(array[row, column]))
                luminance = 0.2126 * rgba[0] + 0.7152 * rgba[1] + 0.0722 * rgba[2]
                ax.text(column + 0.5, row + 0.5, fmt.format(array[row, column]), ha="center", va="center", fontsize=8, color="white" if luminance < 0.5 else "black")
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_title(title, loc="left", fontsize=9.2, pad=5)
    save(fig, "Figure8_method_refinement_PROVISIONAL")


def main() -> None:
    setup()
    figure3()
    setup()
    supplementary_decomposition()
    setup()
    provisional_figure8d()
    setup()
    figure8()
    print(OUT)


if __name__ == "__main__":
    main()
