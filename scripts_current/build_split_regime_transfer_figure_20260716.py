from __future__ import annotations

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[1]
BASE = Path(os.environ.get("FZYC_TRANSFER_OUT", ROOT / "output" / "paper26_split_regime_transfer_20260716"))
OUT = BASE / "supplementary"
SOURCE = BASE / "figure_source_data"
BLUE = "#356D9E"
ORANGE = "#D57A2A"
TEAL = "#2A8C82"
PURPLE = "#7461A8"
GREY = "#6B7280"
DISPLAY = {"clintox": "ClinTox", "bace": "BACE", "esol": "ESOL"}
TRANSFORM = {
    "raw": "Raw", "row_centred": "Row-centred",
    "fixed_reference_relative": "Fixed-reference", "within_unit_rank": "Within-rank",
}


def style() -> None:
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 8.2,
        "axes.labelsize": 8.5, "axes.titlesize": 9.0,
        "xtick.labelsize": 7.7, "ytick.labelsize": 7.7,
        "legend.fontsize": 7.5, "axes.linewidth": 0.8,
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
    })


def panel_label(ax, label: str) -> None:
    ax.text(-0.14, 1.11, label, transform=ax.transAxes, fontsize=11, fontweight="bold", va="top")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SOURCE.mkdir(parents=True, exist_ok=True)
    style()
    ranking = pd.read_csv(BASE / "split_regime_ranking_endpoint_summary.csv")
    effects = pd.read_csv(BASE / "split_regime_cross_fitted_effects.csv")
    diversity = pd.read_csv(BASE / "split_regime_effective_diversity.csv")
    units = pd.read_csv(BASE / "split_regime_ranking_units.csv")
    split_rows = []
    cluster_root = ROOT / "results" / "split_regime_transfer_20260716" / "similarity_cluster"
    for seed in (11, 23, 37, 53, 71):
        frame = pd.read_csv(cluster_root / f"seed_{seed}" / "split_manifest.csv").rename(columns={"endpoint": "task"})
        frame["seed"] = seed
        split_rows.append(frame)
    splits = pd.concat(split_rows, ignore_index=True)

    fig, axes = plt.subplots(2, 2, figsize=(7.15, 5.45), constrained_layout=True)
    ax = axes[0, 0]
    summary = ranking.groupby(["split_regime", "candidate_count"])["chance_adjusted_hit"].agg(
        median="median", low="min", high="max"
    ).reset_index()
    for regime, color, label in [("scaffold", BLUE, "Scaffold"), ("similarity_cluster", ORANGE, "Similarity-cluster")]:
        q = summary.loc[summary.split_regime.eq(regime)]
        ax.fill_between(q.candidate_count, q.low, q.high, color=color, alpha=0.12, linewidth=0)
        ax.plot(q.candidate_count, q["median"], "o-", color=color, lw=1.6, ms=4.2, label=label)
    ax.axhline(0, color="#B9BEC5", lw=0.8, ls="--")
    ax.set(xlabel="Candidate count K", ylabel="Endpoint-median CAHit@3", xticks=[4, 8, 16, 32])
    ax.legend(frameon=False, ncol=2, loc="lower left", handlelength=1.8, columnspacing=1.1)
    ax.spines[["top", "right"]].set_visible(False)
    panel_label(ax, "A")

    ax = axes[0, 1]
    order = ["clintox", "bace", "esol"]
    ybase = np.arange(len(order))[::-1]
    for offset, regime, color, label in [(.11, "scaffold", BLUE, "Scaffold"), (-.11, "similarity_cluster", ORANGE, "Similarity-cluster")]:
        q = effects.set_index(["split_regime", "task"]).loc[[(regime, task) for task in order]].reset_index()
        y = ybase + offset
        ax.errorbar(q.cross_fitted_k32_minus_k4, y,
                    xerr=[q.cross_fitted_k32_minus_k4 - q.bootstrap95_low,
                          q.bootstrap95_high - q.cross_fitted_k32_minus_k4],
                    fmt="o", color=color, ms=4.2, lw=1.2, capsize=2, label=label)
    ax.axvline(0, color="#8D949D", lw=0.9, ls="--")
    ax.set_yticks(ybase, [DISPLAY[x] for x in order])
    ax.set_xlabel("Cross-fitted K32 - K4 selection gap")
    ax.set_ylabel("Endpoint")
    ax.legend(frameon=False, ncol=2, loc="upper right", handletextpad=.3, columnspacing=.8)
    ax.spines[["top", "right"]].set_visible(False)
    panel_label(ax, "B")

    ax = axes[1, 0]
    integrity = splits[["task", "seed", "outer_fold", "inner_fold", "max_train_validation_tanimoto", "max_train_test_tanimoto"]].copy()
    long = integrity.melt(id_vars=["task", "seed", "outer_fold", "inner_fold"], var_name="boundary", value_name="maximum_tanimoto")
    rng = np.random.default_rng(20260716)
    for i, task in enumerate(order):
        q = long.loc[long.task.eq(task)]
        jitter = rng.uniform(-.16, .16, len(q))
        colors = np.where(q.boundary.eq("max_train_test_tanimoto"), TEAL, PURPLE)
        ax.scatter(np.full(len(q), i) + jitter, q.maximum_tanimoto, c=colors, s=12, alpha=.72, edgecolors="none")
    ax.axhline(.70, color="#A34F4F", lw=1.0, ls="--", label="Prespecified threshold")
    ax.set_xticks(range(3), [DISPLAY[x] for x in order])
    ax.set(ylabel="Maximum cross-fold Tanimoto", ylim=(0.66, .705))
    ax.legend(frameon=False, loc="lower left")
    ax.spines[["top", "right"]].set_visible(False)
    panel_label(ax, "C")

    ax = axes[1, 1]
    paired = diversity.pivot_table(index=["task", "candidate_count", "transformation"], columns="split_regime", values="entropy_rank").reset_index()
    for mode, color, marker in [
        ("raw", BLUE, "o"), ("row_centred", ORANGE, "s"),
        ("fixed_reference_relative", TEAL, "^"), ("within_unit_rank", PURPLE, "D"),
    ]:
        q = paired.loc[paired.transformation.eq(mode)]
        ax.scatter(q.scaffold, q.similarity_cluster, color=color, marker=marker, s=24, alpha=.78, label=TRANSFORM[mode])
    lo = float(min(paired.scaffold.min(), paired.similarity_cluster.min()))
    hi = float(max(paired.scaffold.max(), paired.similarity_cluster.max()))
    ax.plot([lo, hi], [lo, hi], color="#9CA3AF", lw=.9, ls="--")
    rho = spearmanr(paired.scaffold, paired.similarity_cluster).statistic
    ax.text(.04, .96, f"Spearman rho = {rho:.2f}", transform=ax.transAxes, ha="left", va="top", color=GREY)
    ax.set(xlabel="Entropy rank: scaffold", ylabel="Entropy rank: similarity-cluster")
    ax.legend(frameon=False, ncol=2, loc="lower right", handletextpad=.25, columnspacing=.7)
    ax.spines[["top", "right"]].set_visible(False)
    panel_label(ax, "D")

    fig.suptitle("Split-regime transfer audit", fontsize=10.5, fontweight="bold")
    stem = OUT / "Supplementary_Figure_S18_split_regime_transfer"
    fig.savefig(stem.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(stem.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(stem.with_name(stem.name + "_600dpi.png"), dpi=600, bbox_inches="tight")
    plt.close(fig)
    summary.to_csv(SOURCE / "Figure_S18A_cahit_source.csv", index=False)
    effects.to_csv(SOURCE / "Figure_S18B_cross_fitted_source.csv", index=False)
    long.to_csv(SOURCE / "Figure_S18C_split_integrity_source.csv", index=False)
    paired.to_csv(SOURCE / "Figure_S18D_effective_rank_source.csv", index=False)
    print(stem)


if __name__ == "__main__":
    main()
