from __future__ import annotations

from pathlib import Path
from textwrap import wrap

import cairosvg
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "reports" / "manuscript_tables" / "table6_reliability_ad.csv"
OUT = ROOT / "reports" / "manuscript_figures_nature_style"

COLORS = {
    "text": "#272727",
    "mid": "#606060",
    "grid": "#EEF1F4",
    "ad": "#42949E",
    "uq": "#7C6CCF",
    "conformal": "#8F8F8F",
}


def label_score(score: str) -> str:
    names = {
        "hybrid_recon_ad": "hybrid recon AD",
        "inverse_tanimoto": "inverse Tanimoto",
        "reconstruction_error": "reconstruction error",
        "confidence_uncertainty": "confidence uncertainty",
        "ensemble_std": "ensemble std",
        "error_model": "error model",
        "hybrid_error_ad": "hybrid error AD",
        "prediction_deviation": "prediction deviation",
        "scaffold_distance": "scaffold distance",
        "classification_coverage": "classification coverage",
        "regression_coverage": "regression coverage",
    }
    return names.get(str(score), str(score).replace("_", " "))


def family_label(family: str) -> str:
    return {
        "reconstruction_unfamiliarity": "AD / reconstruction",
        "unique_style_uq": "UQ / error model",
        "conformal_prediction": "Conformal coverage",
    }.get(str(family), str(family).replace("_", " "))


def family_color(family: str) -> str:
    return {
        "reconstruction_unfamiliarity": COLORS["ad"],
        "unique_style_uq": COLORS["uq"],
        "conformal_prediction": COLORS["conformal"],
    }.get(str(family), COLORS["mid"])


def compact_labels(scores: list[str]) -> str:
    unique = []
    for score in scores:
        label = label_score(score)
        if label not in unique:
            unique.append(label)
    if len(unique) <= 2:
        return " / ".join(unique)
    return unique[0] + " + " + str(len(unique) - 1) + " related"


def main() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans", "sans-serif"],
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "font.size": 7.5,
            "axes.spines.right": False,
            "axes.spines.top": False,
            "axes.linewidth": 0.8,
            "legend.frameon": False,
        }
    )

    table = pd.read_csv(TABLE)
    table["label"] = table["score"].map(label_score)
    table["family_label"] = table["family"].map(family_label)
    table["color"] = table["family"].map(family_color)

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(14.8, 6.9),
        gridspec_kw={"width_ratios": [1.05, 1.0], "wspace": 0.22},
    )

    ax = axes[0]
    scatter = table.dropna(subset=["mean_spearman_abs_error", "mean_top10pct_high_error_enrichment"]).copy()
    grouped = (
        scatter.groupby(
            [
                "family",
                "family_label",
                "mean_spearman_abs_error",
                "mean_top10pct_high_error_enrichment",
            ],
            as_index=False,
        )
        .agg(score=("score", list), n_rows=("n_rows", "sum"))
        .sort_values("mean_top10pct_high_error_enrichment", ascending=False)
    )
    for _, row in grouped.iterrows():
        ax.scatter(
            row["mean_spearman_abs_error"],
            row["mean_top10pct_high_error_enrichment"],
            s=np.sqrt(row["n_rows"]) * 45,
            color=family_color(row["family"]),
            alpha=0.84,
            edgecolor="white",
            linewidth=1.0,
            label=row["family_label"],
        )

    offsets = [
        (10, 7),
        (10, -12),
        (10, 11),
        (10, -16),
        (10, 12),
        (10, -14),
        (10, 10),
        (10, -12),
    ]
    for idx, (_, row) in enumerate(grouped.iterrows()):
        label = "\n".join(wrap(compact_labels(row["score"]), 21))
        ax.annotate(
            label,
            (row["mean_spearman_abs_error"], row["mean_top10pct_high_error_enrichment"]),
            xytext=offsets[idx % len(offsets)],
            textcoords="offset points",
            fontsize=7.1,
            color=COLORS["text"],
            arrowprops=dict(arrowstyle="-", color="#A8A8A8", lw=0.55, shrinkA=2, shrinkB=2),
        )
    ax.axhline(1.0, color="#A8A8A8", lw=0.9, ls="--")
    ax.set_xlim(0.0, 0.98)
    ax.set_ylim(0.86, 3.88)
    ax.set_xlabel("Spearman correlation with absolute error")
    ax.set_ylabel("Top-10% high-error enrichment")
    ax.set_title("High-risk prediction signals", fontweight="bold", pad=8)
    handles, labels = ax.get_legend_handles_labels()
    unique = dict(zip(labels, handles))
    ax.legend(unique.values(), unique.keys(), loc="upper left", fontsize=7.4)
    ax.grid(True, color=COLORS["grid"], lw=0.65)
    ax.text(-0.08, 1.03, "A", transform=ax.transAxes, fontsize=11, fontweight="bold", color=COLORS["text"])

    ax2 = axes[1]
    bar = table.sort_values("mean_risk_coverage_auc", ascending=True).reset_index(drop=True)
    y = np.arange(len(bar))
    ax2.barh(y, bar["mean_risk_coverage_auc"], color=bar["color"], alpha=0.9, height=0.72)
    ax2.set_yticks(y)
    ax2.set_yticklabels(["\n".join(wrap(v, 24)) for v in bar["label"]], fontsize=7.2)
    ax2.tick_params(axis="y", length=0, pad=7)
    ax2.set_xlabel("Mean risk-coverage AUC (lower is better)")
    ax2.set_title("Selective prediction quality", fontweight="bold", pad=8)
    ax2.grid(True, axis="x", color=COLORS["grid"], lw=0.65)
    ax2.set_xlim(0, max(0.98, float(bar["mean_risk_coverage_auc"].max()) * 1.05))
    ax2.text(-0.08, 1.03, "B", transform=ax2.transAxes, fontsize=11, fontweight="bold", color=COLORS["text"])

    fig.suptitle(
        "Reliability summary: uncertainty and applicability-domain scores",
        fontsize=14.5,
        fontweight="bold",
        color=COLORS["text"],
        y=0.98,
    )
    fig.text(
        0.5,
        0.012,
        "Bubble size denotes the number of endpoint-seed rows; lower risk-coverage AUC indicates better selective prediction.",
        ha="center",
        va="bottom",
        fontsize=7.1,
        color=COLORS["mid"],
    )
    fig.subplots_adjust(left=0.07, right=0.985, top=0.86, bottom=0.12)

    OUT.mkdir(parents=True, exist_ok=True)
    svg = OUT / "fig6_reliability_summary_polished.svg"
    png = OUT / "fig6_reliability_summary_polished.png"
    fig.savefig(svg, bbox_inches="tight")
    plt.close(fig)
    cairosvg.svg2png(url=str(svg), write_to=str(png), output_width=7200, background_color="white")
    image = Image.open(png).convert("RGB")
    image = image.filter(ImageFilter.UnsharpMask(radius=0.65, percent=110, threshold=3))
    image.save(png, format="PNG", optimize=True, compress_level=4, dpi=(600, 600))
    print(f"rewrote {png.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
