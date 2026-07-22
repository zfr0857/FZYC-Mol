from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "reports" / "manuscript_figures_polished"
PACKAGE_MAIN = ROOT / "reports" / "submission_package" / "main_figures"


COLORS = {
    "ink": "#0f172a",
    "muted": "#64748b",
    "line": "#cbd5e1",
    "blue": "#2563eb",
    "cyan": "#0891b2",
    "green": "#15803d",
    "teal": "#0f766e",
    "amber": "#b45309",
    "purple": "#7c3aed",
    "rose": "#be123c",
    "slate": "#475569",
    "paper": "#ffffff",
    "soft_blue": "#eff6ff",
    "soft_cyan": "#ecfeff",
    "soft_green": "#f0fdf4",
    "soft_amber": "#fffbeb",
    "soft_purple": "#f5f3ff",
    "soft_rose": "#fff1f2",
    "soft_slate": "#f8fafc",
}


def setup_fonts() -> None:
    for font_path in [Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf")]:
        if font_path.exists():
            fm.fontManager.addfont(str(font_path))
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.unicode_minus": False,
            "figure.dpi": 160,
            "savefig.dpi": 360,
        }
    )


def box(
    ax,
    xy: tuple[float, float],
    wh: tuple[float, float],
    title: str,
    lines: list[str],
    face: str,
    edge: str,
    title_size: float = 9.0,
    body_size: float = 7.0,
    radius: float = 0.018,
    lw: float = 1.25,
    title_color: str = COLORS["ink"],
) -> None:
    x, y = xy
    w, h = wh
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.012,rounding_size={radius}",
        facecolor=face,
        edgecolor=edge,
        linewidth=lw,
    )
    ax.add_patch(patch)
    ax.text(x + 0.018, y + h - 0.026, title, ha="left", va="top", fontsize=title_size, fontweight="bold", color=title_color)
    ax.text(
        x + 0.018,
        y + h - 0.063,
        "\n".join(lines),
        ha="left",
        va="top",
        fontsize=body_size,
        color=COLORS["muted"],
        linespacing=1.22,
    )


def small_pill(ax, x: float, y: float, text: str, color: str, width: float = 0.12) -> None:
    height = 0.036
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.006,rounding_size=0.018",
        facecolor=color,
        edgecolor="none",
    )
    ax.add_patch(patch)
    ax.text(x + width / 2, y + height / 2, text, ha="center", va="center", fontsize=6.9, color=COLORS["ink"], fontweight="bold")


def arrow(ax, start: tuple[float, float], end: tuple[float, float], color: str = COLORS["slate"], rad: float = 0.0, lw: float = 1.4) -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=13,
            linewidth=lw,
            color=color,
            connectionstyle=f"arc3,rad={rad}",
        )
    )


def panel_title(ax, x: float, y: float, label: str, color: str) -> None:
    ax.text(x, y, label, ha="left", va="center", fontsize=10.5, fontweight="bold", color=COLORS["ink"])
    ax.plot([x, x + 0.12], [y - 0.018, y - 0.018], color=color, lw=2.5, solid_capstyle="round")


def draw() -> None:
    setup_fonts()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    PACKAGE_MAIN.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(16.8, 9.8))
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    fig.patch.set_facecolor("white")

    ax.text(0.5, 0.962, "FZYC-Mol: validation-governed molecular property prediction", ha="center", va="top", fontsize=17.8, fontweight="bold", color=COLORS["ink"])
    ax.text(
        0.5,
        0.925,
        "A multi-expert selector that freezes test labels until final reporting, then couples performance with reliability, AD/OOD and interpretability evidence.",
        ha="center",
        va="top",
        fontsize=9.9,
        color=COLORS["muted"],
    )

    panel_title(ax, 0.055, 0.858, "A  Experimental protocol", COLORS["blue"])
    panel_title(ax, 0.345, 0.858, "B  Candidate experts", COLORS["amber"])
    panel_title(ax, 0.630, 0.858, "C  Selector core", COLORS["purple"])
    panel_title(ax, 0.805, 0.858, "D  Evidence outputs", COLORS["green"])

    box(
        ax,
        (0.055, 0.665),
        (0.235, 0.145),
        "Benchmarks and endpoint families",
        ["MoleculeNet main panel", "TDC ADMET official splits", "MoleculeACE activity cliffs", "OpenADMET / full-panel appendix"],
        COLORS["soft_blue"],
        COLORS["cyan"],
    )
    box(
        ax,
        (0.055, 0.465),
        (0.235, 0.145),
        "Split governance",
        ["train -> validation -> test", "random / scaffold / structure splits", "seed-level repeats", "test labels locked until final audit"],
        "#f1f5f9",
        COLORS["blue"],
    )
    box(
        ax,
        (0.055, 0.265),
        (0.235, 0.145),
        "Stress-test subsets",
        ["low-similarity molecules", "roughness and local target jumps", "class imbalance", "external ADMET appendix"],
        COLORS["soft_cyan"],
        COLORS["cyan"],
    )

    expert_boxes = [
        ((0.345, 0.705), (0.215, 0.085), "Graph / message passing", ["GIN, graph heads", "Chemprop / D-MPNN"], COLORS["soft_blue"], COLORS["blue"]),
        ((0.345, 0.592), (0.215, 0.085), "Fingerprint and descriptor trees", ["Morgan, MACCS, atom-pair, torsion", "RF, ExtraTrees, XGBoost, LightGBM"], COLORS["soft_green"], COLORS["green"]),
        ((0.345, 0.479), (0.215, 0.085), "Motif and fragment experts", ["BRICS, Murcko, functional groups", "descriptor/motif neural heads"], COLORS["soft_amber"], COLORS["amber"]),
        ((0.345, 0.366), (0.215, 0.085), "Frozen molecular encoders", ["ChemBERTa / MoLFormer features", "descriptor + embedding rescue heads"], COLORS["soft_purple"], COLORS["purple"]),
        ((0.345, 0.253), (0.215, 0.085), "Targeted rescue candidates", ["Top-K mean and stacking", "target transforms, undersampling"], COLORS["soft_rose"], COLORS["rose"]),
    ]
    for xy, wh, title, lines, face, edge in expert_boxes:
        box(ax, xy, wh, title, lines, face, edge, title_size=8.2, body_size=6.6)

    box(
        ax,
        (0.625, 0.615),
        (0.145, 0.18),
        "Validation leaderboard",
        ["one row per seed", "primary metric direction respected", "mean / std / rank / regret", "calibration metrics when available"],
        COLORS["soft_purple"],
        COLORS["purple"],
        title_size=8.2,
        body_size=6.4,
    )
    box(
        ax,
        (0.605, 0.385),
        (0.185, 0.17),
        "Fixed selector policies",
        ["per-seed validation best", "risk-adjusted mean +/- 0.5 SD", "stability tie-breaker", "no endpoint-wise test-policy selection"],
        "#faf5ff",
        COLORS["purple"],
        title_size=8.2,
        body_size=6.3,
        lw=1.55,
    )
    box(
        ax,
        (0.625, 0.195),
        (0.145, 0.13),
        "Retained-best gate",
        ["promote only after fixed validation rule", "keep current result when worse", "record source, delta and limitation"],
        COLORS["soft_rose"],
        COLORS["rose"],
        title_size=8.0,
        body_size=6.25,
    )

    outputs = [
        ((0.805, 0.695), (0.155, 0.095), "Main performance", ["MoleculeNet / TDC", "mean +/- SD; retained-best"], COLORS["soft_green"], COLORS["green"]),
        ((0.805, 0.570), (0.155, 0.095), "Reliability and AD/OOD", ["risk-coverage; uncertainty", "inverse Tanimoto; recon error"], COLORS["soft_cyan"], COLORS["cyan"]),
        ((0.805, 0.445), (0.155, 0.095), "Calibration and imbalance", ["PR-AUC / Brier / ECE", "undersampling; conformal"], COLORS["soft_blue"], COLORS["blue"]),
        ((0.805, 0.320), (0.155, 0.095), "Interpretability", ["motif and fragment evidence", "case-level review"], COLORS["soft_amber"], COLORS["amber"]),
        ((0.805, 0.195), (0.155, 0.095), "Negative-result audit", ["3D-lite / roughness gate", "oracle-only signals retained"], COLORS["soft_rose"], COLORS["rose"]),
    ]
    for xy, wh, title, lines, face, edge in outputs:
        box(ax, xy, wh, title, lines, face, edge, title_size=7.8, body_size=6.0)

    for y in [0.735, 0.535, 0.335]:
        arrow(ax, (0.302, y), (0.335, y), COLORS["slate"], lw=1.2)
    for y in [0.748, 0.635, 0.522, 0.409, 0.296]:
        arrow(ax, (0.568, y), (0.616, 0.475), COLORS["purple"], rad=-0.04, lw=1.25)
    arrow(ax, (0.695, 0.615), (0.695, 0.555), COLORS["purple"], lw=1.35)
    arrow(ax, (0.695, 0.385), (0.695, 0.325), COLORS["rose"], lw=1.35)
    for y, rad in zip([0.742, 0.617, 0.492, 0.367, 0.242], [0.02, 0.01, 0.0, -0.01, -0.02]):
        arrow(ax, (0.778, 0.47), (0.797, y), COLORS["green"], rad=rad, lw=1.25)

    bottom = FancyBboxPatch(
        (0.055, 0.025),
        0.895,
        0.140,
        boxstyle="round,pad=0.014,rounding_size=0.02",
        facecolor="#f8fafc",
        edgecolor="#cbd5e1",
        linewidth=1.15,
    )
    ax.add_patch(bottom)
    ax.text(0.075, 0.137, "Experiment-thickening layer", ha="left", va="center", fontsize=9.0, fontweight="bold", color=COLORS["ink"])
    pills = [
        ("external benchmark", COLORS["soft_blue"], 0.075, 0.094, 0.145),
        ("performance-mode ensembles", COLORS["soft_green"], 0.235, 0.094, 0.195),
        ("selector audit", COLORS["soft_purple"], 0.448, 0.094, 0.130),
        ("fixed-policy integration", COLORS["soft_rose"], 0.595, 0.094, 0.190),
        ("roughness diagnostics", COLORS["soft_amber"], 0.075, 0.052, 0.165),
        ("calibration / imbalance", COLORS["soft_cyan"], 0.258, 0.052, 0.175),
        ("interpretability cases", COLORS["soft_blue"], 0.450, 0.052, 0.165),
        ("negative-result audit", COLORS["soft_rose"], 0.632, 0.052, 0.155),
    ]
    for text, color, x, y, width in pills:
        small_pill(ax, x, y, text, color, width=width)
    ax.text(
        0.075,
        0.036,
        "All additions remain validation-governed; negative results and unpromoted candidates are retained in the supplementary audit.",
        ha="left",
        va="center",
        fontsize=6.9,
        color=COLORS["muted"],
    )

    for ext in ["png", "svg"]:
        out = FIG_DIR / f"fig1_framework_overview_polished.{ext}"
        fig.savefig(out, bbox_inches="tight", facecolor="white")
        fig.savefig(PACKAGE_MAIN / f"Figure_1_FZYC_Mol_framework.{ext}", bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    draw()
