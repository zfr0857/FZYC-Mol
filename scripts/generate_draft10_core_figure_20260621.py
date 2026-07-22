# -*- coding: utf-8 -*-
from __future__ import annotations

import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
EXPANDED = ROOT / "reports" / "draft10_core_experiments_20260621" / "expanded_nested"
RETRO = ROOT / "reports" / "draft8_14k_revision"
BUNDLE = ROOT / "output" / "初稿-10_图表与源数据"
FIG = BUNDLE / "figures"
SRC = BUNDLE / "source_data"


COLORS = {
    "validation_best": "#1F77B4",
    "one_se_stable": "#2A9D8F",
    "risk_adjusted": "#E76F51",
    "fixed_single": "#6C757D",
}
LABELS = {
    "validation_best": "Validation-best",
    "one_se_stable": "One-SE + stability",
    "risk_adjusted": "Risk-adjusted",
    "fixed_single": "Fixed single",
}


def save_all(fig: plt.Figure, stem: str) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    png = FIG / f"{stem}.png"
    fig.savefig(png, dpi=450, bbox_inches="tight", facecolor="white")
    fig.savefig(FIG / f"{stem}.svg", bbox_inches="tight", facecolor="white")
    fig.savefig(FIG / f"{stem}.pdf", bbox_inches="tight", facecolor="white")
    fig.savefig(FIG / f"{stem}.tiff", dpi=600, bbox_inches="tight", facecolor="white", pil_kwargs={"compression": "tiff_lzw"})
    with Image.open(png) as image:
        if image.width < 2400:
            raise ValueError(f"Figure too narrow: {image.size}")


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    SRC.mkdir(parents=True, exist_ok=True)
    summary = pd.read_csv(EXPANDED / "policy_summary.csv")
    stability = pd.read_csv(EXPANDED / "selection_stability.csv")
    detail = pd.read_csv(EXPANDED / "policy_detail.csv")
    retro = pd.read_csv(RETRO / "candidate_pool_stress_summary.csv")
    summary.to_csv(SRC / "fig04_expanded_nested_policy_summary.csv", index=False)
    stability.to_csv(SRC / "fig04_expanded_nested_selection_stability.csv", index=False)
    detail.to_csv(SRC / "fig04_expanded_nested_policy_detail.csv", index=False)

    policies = ["validation_best", "one_se_stable", "risk_adjusted", "fixed_single"]
    ks = [4, 8, 16, 32]
    stability_mean = stability.groupby(["pool_size", "policy"], as_index=False)["modal_selection_rate"].mean()
    endpoint = (
        detail[(detail["pool_size"].eq(32)) & detail["policy"].isin(policies[:3])]
        .groupby(["dataset", "policy"], as_index=False)["normalized_test_regret"]
        .mean()
    )
    hit_expanded = summary[summary["policy"].eq("validation_best")][["pool_size", "top3_hit_rate"]].copy()
    hit_expanded["analysis"] = "Prospective nested"
    hit_retro = retro[retro["policy"].eq("validation_best")][["pool_size", "top3_hit_rate"]].copy()
    hit_retro["analysis"] = "Retrospective audit"
    hit = pd.concat([hit_retro, hit_expanded], ignore_index=True)
    hit.to_csv(SRC / "fig04_retrospective_prospective_top3.csv", index=False)
    endpoint.to_csv(SRC / "fig04_k32_endpoint_regret.csv", index=False)

    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.8,
        "xtick.major.width": 0.8,
        "ytick.major.width": 0.8,
    })
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 8.6), constrained_layout=True)

    ax = axes[0, 0]
    for policy in policies:
        sub = summary[summary["policy"].eq(policy)].sort_values("pool_size")
        ax.errorbar(
            sub["pool_size"], sub["normalized_regret_mean"],
            yerr=1.96 * sub["regret_sem"], marker="o", lw=2, capsize=3,
            color=COLORS[policy], label=LABELS[policy],
        )
    ax.set_xticks(ks)
    ax.set_xlabel("Candidate-pool size")
    ax.set_ylabel("Normalized outer-test regret")
    ax.set_title("a  Prospective nested selection loss", loc="left", fontweight="bold")
    ax.legend(frameon=False, fontsize=8, ncol=2)

    ax = axes[0, 1]
    for analysis, color, marker in [
        ("Retrospective audit", "#6C757D", "s"),
        ("Prospective nested", "#8E44AD", "o"),
    ]:
        sub = hit[hit["analysis"].eq(analysis)].sort_values("pool_size")
        ax.plot(sub["pool_size"], sub["top3_hit_rate"], marker=marker, lw=2.2, color=color, label=analysis)
    ax.set_xticks(ks)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Candidate-pool size")
    ax.set_ylabel("Validation Top-3 hit rate")
    ax.set_title("b  Ranking fidelity across two audits", loc="left", fontweight="bold")
    ax.legend(frameon=False, fontsize=8)

    ax = axes[1, 0]
    for policy in policies[:3]:
        sub = stability_mean[stability_mean["policy"].eq(policy)].sort_values("pool_size")
        ax.plot(sub["pool_size"], sub["modal_selection_rate"], marker="o", lw=2, color=COLORS[policy], label=LABELS[policy])
    ax.set_xticks(ks)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Candidate-pool size")
    ax.set_ylabel("Modal selection rate")
    ax.set_title("c  Selection stability", loc="left", fontweight="bold")
    ax.legend(frameon=False, fontsize=8)

    ax = axes[1, 1]
    pivot = endpoint.pivot(index="dataset", columns="policy", values="normalized_test_regret")
    order = pivot["validation_best"].sort_values(ascending=False).index
    pivot = pivot.loc[order]
    x = np.arange(len(pivot))
    width = 0.25
    for offset, policy in zip([-width, 0, width], policies[:3]):
        ax.bar(x + offset, pivot[policy], width=width, color=COLORS[policy], label=LABELS[policy])
    ax.set_xticks(x)
    ax.set_xticklabels([name.replace("tdc_", "").replace("_broccatelli", "").replace("_wang", "").replace("_hou", "") for name in pivot.index], rotation=32, ha="right")
    ax.set_ylabel("Normalized outer-test regret")
    ax.set_title("d  Endpoint heterogeneity at K=32", loc="left", fontweight="bold")
    ax.legend(frameon=False, fontsize=8)

    fig.suptitle("Candidate-pool expansion weakens ranking fidelity without a universally superior selector", fontsize=14, fontweight="bold")
    save_all(fig, "fig04_expanded_nested_candidate_pool")
    plt.close(fig)
    print(FIG / "fig04_expanded_nested_candidate_pool.png")


if __name__ == "__main__":
    main()
