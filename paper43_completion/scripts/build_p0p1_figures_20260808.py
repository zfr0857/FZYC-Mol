from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from PIL import Image


ROOT = Path(os.environ.get("FZYC_ROOT", Path(__file__).resolve().parents[1]))
OUT = ROOT / "work" / "p0p1p2_revision_20260808" / "figures"
WORK = ROOT / "work" / "r11_method_refinement_20260731"
MINOR = ROOT / "output" / "paper25_pre_submission_minor_revision_20260715"
ANALYSIS = ROOT / "output" / "paper22_major_revision_20260713"
STRUCTURAL = ROOT / "work" / "af4_r12_6_1" / "paper43_completion" / "scripts" / "r11_final" / "build_paper43_r11_structural_figures_20260731.py"

BLUE, ORANGE, TEAL, PURPLE = "#315E8A", "#D58135", "#2F8B83", "#78689A"
GREY, INK, LIGHT = "#7A7F87", "#202830", "#E3E7EA"
DISPLAY = {
    "bace": "BACE", "bbbp": "BBBP", "clintox": "ClinTox", "esol": "ESOL",
    "freesolv": "FreeSolv", "lipo": "Lipophilicity", "tdc_caco2_wang": "Caco2",
    "tdc_hia_hou": "HIA", "tdc_pgp_broccatelli": "P-gp",
}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def setup() -> None:
    mpl.rcParams.update({
        "font.family": "Times New Roman", "font.serif": ["Times New Roman"], "font.size": 9,
        "axes.titlesize": 10.3, "axes.titleweight": "bold", "axes.labelsize": 9.2,
        "xtick.labelsize": 8.2, "ytick.labelsize": 8.2, "legend.fontsize": 8.0,
        "axes.linewidth": 0.75, "axes.spines.top": False, "axes.spines.right": False,
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
        "mathtext.fontset": "stix", "axes.unicode_minus": False,
        "savefig.facecolor": "white", "figure.facecolor": "white",
    })


def save(fig: mpl.figure.Figure, number: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for item in fig.findobj(match=mpl.text.Text):
        if item.get_text() and item.get_fontsize() < 8:
            item.set_fontsize(8)
    fig.savefig(OUT / f"Figure{number}.svg", bbox_inches="tight", facecolor="white")
    fig.savefig(OUT / f"Figure{number}.pdf", bbox_inches="tight", facecolor="white")
    png = OUT / f"Figure{number}_600dpi.png"
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
    h.text(-0.10, 0.20, letter, fontsize=12, fontweight="bold", va="bottom", color=BLUE)
    h.text(0.02, 0.20, title, fontsize=10.3, fontweight="bold", va="bottom")
    return sub[1]


def decomposition_header(fig, spec):
    sub = spec.subgridspec(2, 1, height_ratios=[0.28, 0.72], hspace=0)
    h = fig.add_subplot(sub[0])
    h.set_xlim(0, 1)
    h.set_ylim(0, 1)
    h.axis("off")
    h.text(-0.10, 0.62, "A", fontsize=12, fontweight="bold", va="bottom", color=BLUE)
    h.text(0.02, 0.62, r"Full-registry gap: $\Delta_{inv}=\Delta_{avail}+\Delta_{dep}$", fontsize=10.3, fontweight="bold", va="bottom")
    items = [
        (0.03, "o", BLUE, r"$\Delta_{inv}$ + interval"),
        (0.39, "D", TEAL, r"$\Delta_{avail}$ point"),
        (0.72, "^", PURPLE, r"$\Delta_{dep}$ point"),
    ]
    for x, marker, color, label in items:
        h.plot([x], [0.22], marker=marker, ms=5.2, color=color, markerfacecolor=color, clip_on=False)
        h.text(x + 0.035, 0.22, label, fontsize=8.0, va="center")
    return sub[1]


def component_forest(ax, frame: pd.DataFrame, xlabel: str, color: str) -> None:
    y = np.arange(len(frame), dtype=float)
    x = frame["Delta_inv"].to_numpy(float)
    lo = frame["Delta_inv_low"].to_numpy(float)
    hi = frame["Delta_inv_high"].to_numpy(float)
    avail = frame["Delta_avail"].to_numpy(float)
    dep = frame["Delta_dep"].to_numpy(float)
    ax.errorbar(x, y, xerr=[x - lo, hi - x], fmt="none", ecolor=GREY, capsize=2.3, lw=1.0, zorder=1)
    for xi, yi, li, hii in zip(x, y, lo, hi, strict=True):
        excludes = li > 0 or hii < 0
        ax.scatter(xi, yi, s=29, marker="o", facecolors=color if excludes else "white", edgecolors=color, zorder=4)
    ax.scatter(avail, y - 0.18, s=24, marker="D", facecolors=TEAL, edgecolors="white", linewidths=0.35, zorder=3)
    ax.scatter(dep, y + 0.18, s=28, marker="^", facecolors=PURPLE, edgecolors="white", linewidths=0.35, zorder=3)
    ax.axvline(0, color=INK, lw=0.8)
    ax.set(yticks=y, yticklabels=[DISPLAY[x] for x in frame.dataset], xlabel=xlabel)
    ax.invert_yaxis()
    ax.margins(y=0.12)
    clean(ax, "x")


def figure3() -> None:
    decomp = pd.read_csv(WORK / "completion_gap_decomposition_endpoint_summary.csv")
    ranking = pd.read_csv(MINOR / "ranking_metric_main_summary.csv").sort_values("candidate_count")
    null = pd.read_csv(MINOR / "mechanism_permutation_null_summary.csv")
    signal = pd.read_csv(MINOR / "mechanism_signal_recovery_summary.csv")
    controls = pd.read_csv(ANALYSIS / "candidate_composition_controls.csv")
    fig = plt.figure(figsize=(6.69, 5.62))
    # The requested vertical panel spacing is 0.20; titles remain in dedicated header rows.
    gs = fig.add_gridspec(2, 2, left=0.105, right=0.98, bottom=0.08, top=0.985, hspace=0.20, wspace=0.48)
    titles = [
        r"Full-registry gap: $\Delta_{inv}=\Delta_{avail}+\Delta_{dep}$",
        "Chance-adjusted top-rank recovery",
        "Signal-recovery calibration",
        "Candidate-composition controls",
    ]
    content = [decomposition_header(fig, gs[0, 0])]
    content.extend(header(fig, spec, letter, title) for spec, letter, title in zip([gs[0, 1], gs[1, 0], gs[1, 1]], "BCD", titles[1:], strict=True))
    a = content[0].subgridspec(1, 2, wspace=0.82)
    axes_a = []
    for kind, color, xlabel, order in [
        ("classification", BLUE, "ROC-AUC contrast", ["bbbp", "tdc_pgp_broccatelli", "bace", "clintox", "tdc_hia_hou"]),
        ("regression", ORANGE, "RMSE contrast", ["lipo", "freesolv", "tdc_caco2_wang", "esol"]),
    ]:
        ax = fig.add_subplot(a[len(axes_a)])
        q = decomp[decomp.task_type.eq(kind)].set_index("dataset").loc[order].reset_index()
        component_forest(ax, q, xlabel, color)
        axes_a.append(ax)
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
    for k, c, m in zip([4, 8, 16, 32], [BLUE, TEAL, ORANGE, PURPLE], ["o", "s", "^", "D"], strict=True):
        q = signal[signal.candidate_count.eq(k)].sort_values("injected_signal")
        ax.plot(q.injected_signal, q.chance_adjusted_hit_median, marker=m, color=c, label=f"K = {k}")
    ax.axhline(0, color=GREY, lw=0.8)
    ax.set(xlabel="Injected validation-audit signal", ylabel="Median CAHit@3")
    ax.legend(frameon=False, ncol=2)
    clean(ax)

    ax = fig.add_subplot(content[3])
    palette = [BLUE, TEAL, ORANGE, PURPLE, GREY, "#B85C5C"]
    markers = ["o", "s", "^", "D", "P", "X"]
    for mode, c, m in zip(sorted(controls["mode"].unique()), palette, markers, strict=False):
        q = controls[controls["mode"].eq(mode)].sort_values("pool_size")
        ax.plot(q.pool_size, q.chance_adjusted_hit_mean, marker=m, color=c, label=mode.replace("_", " "), lw=1.2)
    ax.axhline(0, color=GREY, lw=0.8)
    ax.set(xlabel="Candidate count, K", ylabel="Chance-adjusted hit", xticks=[4, 8, 16, 32])
    ax.legend(frameon=False, ncol=2, fontsize=8)
    clean(ax)
    save(fig, 3)


def figure7() -> None:
    module = load_module(STRUCTURAL, "structural_r126")
    module.OUT = OUT

    def intercepted_save(fig, number):
        save(fig, number)

    module.save = intercepted_save
    module.setup()
    module.figure7()


if __name__ == "__main__":
    setup()
    figure3()
    setup()
    figure7()
    print(OUT)
