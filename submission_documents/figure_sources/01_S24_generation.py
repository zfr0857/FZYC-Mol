"""Regenerate the submission-facing PR-AUC-only Supplementary Figure S24.

This script intentionally refuses any selector other than PR-AUC. The archived
minority-class audit is a definition and provenance audit, not a performance
comparison, because inner-validation probabilities were not retained.
"""

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "source_data" / "main_figures" / "classification_metric_selector_comparisons_final.csv"
OUT = ROOT / "reproduced_outputs" / "supplementary_figures"
OUT.mkdir(parents=True, exist_ok=True)

DISPLAY = {
    "bace": "BACE",
    "bbbp": "BBBP",
    "clintox": "ClinTox",
    "tdc_hia_hou": "HIA",
    "tdc_pgp_broccatelli": "P-gp",
}
COLORS = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#6A5ACD"]


def main() -> None:
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman"],
            "font.size": 9,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )
    data = pd.read_csv(SOURCE)
    selectors = set(data["alternative_selector"].dropna().unique())
    if selectors != {"pr_auc"}:
        raise RuntimeError(f"Expected PR-AUC-only source, found {sorted(selectors)}")
    grouped = (
        data.groupby(["dataset", "pool_size"], as_index=False)
        .agg(
            switch_frequency=("candidate_changed_vs_roc", "mean"),
            delta_outer_pr_auc=("delta_outer_pr_auc_vs_roc_selector", "mean"),
        )
    )

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.15), gridspec_kw={"wspace": 0.30})
    for color, endpoint in zip(COLORS, DISPLAY):
        part = grouped[grouped["dataset"].eq(endpoint)].sort_values("pool_size")
        axes[0].plot(part["pool_size"], 100 * part["switch_frequency"], marker="o", ms=4.1, lw=1.25, color=color, label=DISPLAY[endpoint])
        axes[1].plot(part["pool_size"], part["delta_outer_pr_auc"], marker="o", ms=4.1, lw=1.25, color=color)
    axes[0].set_title("A  Candidate switching", loc="left", fontweight="bold")
    axes[0].set(xlabel="Candidate count, K", ylabel="Switch frequency versus ROC-AUC (%)", xticks=[4, 8, 16, 32], ylim=(-2, 102))
    axes[0].legend(frameon=False, ncol=2, loc="upper left")
    axes[1].set_title("B  Outer PR-AUC change", loc="left", fontweight="bold")
    axes[1].set(xlabel="Candidate count, K", ylabel="PR-AUC selector minus ROC-AUC selector", xticks=[4, 8, 16, 32])
    axes[1].axhline(0, color="#555555", lw=0.8, ls="--")
    for ax in axes:
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", color="#D9D9D9", lw=0.5, alpha=0.65)
    fig.suptitle("Supplementary Figure S24. Metric-dependent classification selection (PR-AUC only)", x=0.07, y=0.995, ha="left", fontsize=10.5, fontweight="bold")
    fig.text(0.07, 0.015, "Recall-constrained effects are excluded because frozen-identity inner-validation probabilities were not retained.", ha="left", va="bottom", fontsize=8.2)
    fig.subplots_adjust(left=0.10, right=0.985, top=0.84, bottom=0.23)
    for suffix, kwargs in [("pdf", {}), ("svg", {}), ("png", {"dpi": 600})]:
        fig.savefig(OUT / f"Supplementary_Figure_S24_PR_AUC_only.{suffix}", bbox_inches="tight", **kwargs)
    plt.close(fig)


if __name__ == "__main__":
    main()
