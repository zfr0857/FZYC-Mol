from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def build_figure(root: Path = ROOT) -> Path:
    bootstrap = pd.read_csv(root / "results" / "statistics" / "repeated_nested_bootstrap.csv")
    stability = pd.read_csv(root / "results" / "nested_selection" / "repeated_stability_metrics.csv")
    colors = {"regret": "#B4473A", "chance": "#1F6F8B", "mrr": "#4C956C", "stability": "#6C5B7B", "entropy": "#D08C60"}
    fig, axes = plt.subplots(1, 3, figsize=(12.6, 3.7), constrained_layout=True)

    regret = bootstrap.loc[bootstrap["metric"].eq("fixed_normalized_regret")].sort_values("pool_size")
    axes[0].errorbar(
        regret["pool_size"],
        regret["mean"],
        yerr=[regret["mean"] - regret["ci95_low"], regret["ci95_high"] - regret["mean"]],
        color=colors["regret"],
        marker="o",
        capsize=3,
        linewidth=2,
    )
    axes[0].set_title("a  Fixed-denominator regret")
    axes[0].set_ylabel("Normalized outer-test regret")

    for metric, label, color in [
        ("chance_adjusted_hit", "Chance-adjusted hit", colors["chance"]),
        ("mrr", "MRR", colors["mrr"]),
    ]:
        values = bootstrap.loc[bootstrap["metric"].eq(metric)].sort_values("pool_size")
        axes[1].errorbar(
            values["pool_size"],
            values["mean"],
            yerr=[values["mean"] - values["ci95_low"], values["ci95_high"] - values["mean"]],
            marker="o",
            capsize=3,
            linewidth=2,
            label=label,
            color=color,
        )
    axes[1].set_title("b  Ranking quality")
    axes[1].set_ylabel("Metric value")
    axes[1].legend(frameon=False, fontsize=8)

    stable = stability.groupby("pool_size", as_index=False).agg(
        modal_selection_rate=("modal_selection_rate", "mean"),
        normalized_entropy=("normalized_entropy", "mean"),
    )
    axes[2].plot(stable["pool_size"], stable["modal_selection_rate"], marker="o", linewidth=2, label="Modal selection rate", color=colors["stability"])
    axes[2].plot(stable["pool_size"], stable["normalized_entropy"], marker="o", linewidth=2, label="Normalized entropy", color=colors["entropy"])
    axes[2].set_title("c  Selection stability")
    axes[2].set_ylabel("Endpoint mean")
    axes[2].legend(frameon=False, fontsize=8)

    for axis in axes:
        axis.set_xlabel("Candidate-pool size")
        axis.set_xticks([4, 8, 16, 32])
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(axis="y", color="#D9D9D9", linewidth=0.6, alpha=0.7)
    output = root / "results" / "figures" / "repeated_nested_control.png"
    fig.savefig(output, dpi=450, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output


if __name__ == "__main__":
    print(build_figure())
