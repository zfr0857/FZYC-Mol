from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle
from matplotlib.ticker import PercentFormatter
from scipy.stats import linregress


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "output" / "小论文-3_图表包"
FIG_DIR = PACKAGE / "figures"
SRC_DIR = PACKAGE / "source_data"

COL = {
    "ink": "#182230",
    "muted": "#667085",
    "line": "#98A2B3",
    "blue": "#3568A8",
    "blue2": "#7EA6D8",
    "green": "#4E9A73",
    "orange": "#D98C3F",
    "purple": "#8B75AF",
    "red": "#BF5B5B",
    "teal": "#3C8D93",
    "grey": "#737B86",
    "light": "#D8DEE6",
    "pblue": "#EAF2FB",
    "pgreen": "#EDF7F0",
    "porange": "#FFF3E8",
    "ppurple": "#F3EFF9",
    "pteal": "#EAF6F6",
    "pyellow": "#FFF8DC",
}


def setup() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Microsoft YaHei", "DejaVu Sans", "sans-serif"],
            "font.size": 8.0,
            "axes.titlesize": 9.5,
            "axes.labelsize": 8.5,
            "xtick.labelsize": 7.4,
            "ytick.labelsize": 7.4,
            "legend.fontsize": 7.0,
            "axes.linewidth": 0.85,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "legend.frameon": False,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "savefig.facecolor": "white",
            "figure.facecolor": "white",
        }
    )


def save(fig: plt.Figure, stem: str) -> None:
    fig.savefig(FIG_DIR / f"{stem}.svg", bbox_inches="tight")
    fig.savefig(FIG_DIR / f"{stem}.png", dpi=450, bbox_inches="tight")
    plt.close(fig)


def copy_source(path: Path, name: str | None = None) -> None:
    shutil.copy2(path, SRC_DIR / (name or path.name))


def panel(ax: plt.Axes, label: str, x: float = -0.13, y: float = 1.06) -> None:
    ax.text(x, y, label, transform=ax.transAxes, fontsize=10.2, fontweight="bold", va="top", color=COL["ink"])


def style_axis(ax: plt.Axes, grid: str | None = "y") -> None:
    ax.tick_params(length=3, width=0.7, colors=COL["ink"])
    ax.spines["left"].set_color(COL["ink"])
    ax.spines["bottom"].set_color(COL["ink"])
    if grid:
        ax.grid(axis=grid, color="#E7EAF0", linewidth=0.55, zorder=0)


def box(ax, x, y, w, h, title, body=(), fc="white", ec=None, dashed=False, title_size=7.35, body_size=5.7):
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.006,rounding_size=0.010",
        facecolor=fc, edgecolor=ec or COL["line"], linewidth=0.9,
        linestyle="--" if dashed else "-",
    )
    ax.add_patch(patch)
    ax.text(x + 0.010, y + h - 0.014, title, ha="left", va="top", fontsize=title_size, fontweight="bold", color=COL["ink"])
    if body:
        title_lines = title.count("\n") + 1
        body_top = y + h - 0.042 - (title_lines - 1) * 0.024
        ax.text(x + 0.010, body_top, "\n".join(body), ha="left", va="top", fontsize=body_size, linespacing=1.16, color=COL["muted"])
    return patch


def arrow(ax, x1, y1, x2, y2, color=None, dashed=False, lw=1.0, rad=0.0):
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=8,
            linewidth=lw, color=color or COL["grey"],
            linestyle="--" if dashed else "-", connectionstyle=f"arc3,rad={rad}",
        )
    )


def molecule_icon(ax, cx, cy, scale=1.0, color=None):
    color = color or COL["ink"]
    r = 0.020 * scale
    pts = [(cx + r * math.cos(math.pi / 6 + i * math.pi / 3), cy + r * math.sin(math.pi / 6 + i * math.pi / 3)) for i in range(6)]
    for p, q in zip(pts, pts[1:] + pts[:1]):
        ax.plot([p[0], q[0]], [p[1], q[1]], color=color, lw=1.1)
    ax.plot([pts[0][0], cx + 0.047 * scale], [pts[0][1], cy + 0.009 * scale], color=color, lw=1.1)
    ax.plot([cx + 0.047 * scale, cx + 0.064 * scale], [cy + 0.009 * scale, cy - 0.014 * scale], color=color, lw=1.1)
    ax.text(cx - 0.004, cy + 0.031 * scale, "O", fontsize=6.5, fontweight="bold", color=COL["red"])
    ax.text(cx + 0.067 * scale, cy - 0.015 * scale, "N", fontsize=6.5, fontweight="bold", color=COL["blue"])


def graph_icon(ax, x, y, w, h, accent=None):
    accent = accent or COL["blue"]
    pts = [(0.12, 0.25), (0.28, 0.70), (0.48, 0.48), (0.68, 0.75), (0.84, 0.32), (0.57, 0.18)]
    pts = [(x + px * w, y + py * h) for px, py in pts]
    for i, j in [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0), (2, 5)]:
        ax.plot([pts[i][0], pts[j][0]], [pts[i][1], pts[j][1]], color=COL["grey"], lw=0.7)
    for i, (px, py) in enumerate(pts):
        ax.add_patch(Circle((px, py), 0.006, facecolor=accent if i % 2 == 0 else "white", edgecolor=COL["ink"], lw=0.5))


def mini_bits(ax, x, y, w, h, color=None):
    rng = np.random.default_rng(5)
    for i in range(10):
        fc = color or ([COL["blue2"], COL["orange"], COL["light"]][int(rng.integers(0, 3))])
        ax.add_patch(Rectangle((x + i * w / 10, y), w / 12, h * (0.35 + 0.65 * rng.random()), facecolor=fc, edgecolor="none"))


def figure01_overall_workflow() -> None:
    fig, ax = plt.subplots(figsize=(7.2, 5.05))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.text(0.015, 0.975, "FZYC-Mol overall workflow", fontsize=11.0, fontweight="bold", va="top", color=COL["ink"])
    ax.text(0.015, 0.941, "Validation-governed multi-view prediction with frozen outer evaluation", fontsize=7.1, va="top", color=COL["muted"])

    columns = [
        (0.015, 0.17, "a  Task protocol", COL["ppurple"], COL["purple"]),
        (0.195, 0.18, "b  Molecular views", COL["pblue"], COL["blue"]),
        (0.395, 0.215, "c  Expert pool", COL["porange"], COL["orange"]),
        (0.63, 0.17, "d  Governance", COL["pgreen"], COL["green"]),
        (0.82, 0.165, "e  Evidence outputs", COL["pteal"], COL["teal"]),
    ]
    for x, w, title, fc, ec in columns:
        ax.add_patch(FancyBboxPatch((x, 0.235), w, 0.665, boxstyle="round,pad=0.006,rounding_size=0.014", facecolor="white", edgecolor=ec, linewidth=1.0))
        ax.add_patch(FancyBboxPatch((x + 0.006, 0.852), w - 0.012, 0.04, boxstyle="round,pad=0.002,rounding_size=0.008", facecolor=fc, edgecolor="none"))
        heading_size = 6.75 if "Evidence outputs" in title else 7.15
        ax.text(x + 0.012, 0.872, title, va="center", fontsize=heading_size, fontweight="bold", color=COL["ink"])

    box(ax, 0.027, 0.695, 0.145, 0.13, "Benchmarks", ["MoleculeNet · TDC", "MoleculeACE · bRo5"], COL["ppurple"], COL["purple"])
    box(ax, 0.027, 0.535, 0.145, 0.13, "Frozen splits", ["random / scaffold", "outer / inner / repeated"], COL["ppurple"], COL["purple"])
    box(ax, 0.027, 0.375, 0.145, 0.13, "Leakage controls", ["train-only fitting", "test labels locked"], COL["ppurple"], COL["purple"])

    box(ax, 0.207, 0.715, 0.155, 0.10, "Graph & bonds", ["atom/bond topology"], COL["pblue"], COL["blue"]); graph_icon(ax, 0.294, 0.714, 0.055, 0.050)
    box(ax, 0.207, 0.585, 0.160, 0.10, "Fingerprint bank", ["Morgan · MACCS · RDKit"], COL["pblue"], COL["blue"], body_size=5.55); mini_bits(ax, 0.285, 0.600, 0.065, 0.030)
    box(ax, 0.207, 0.455, 0.155, 0.10, "Descriptors", ["physicochemical · motif"], COL["pblue"], COL["blue"]); mini_bits(ax, 0.295, 0.470, 0.055, 0.030, COL["purple"])
    box(ax, 0.207, 0.325, 0.155, 0.10, "Frozen\nembeddings", ["ChemBERTa", "MoLFormer"], COL["pblue"], COL["blue"], title_size=7.0, body_size=5.45)

    box(ax, 0.407, 0.715, 0.19, 0.10, "Graph experts", ["GIN/GAT · Chemprop"], COL["porange"], COL["orange"]); graph_icon(ax, 0.522, 0.714, 0.060, 0.050, COL["orange"])
    box(ax, 0.407, 0.585, 0.19, 0.10, "Tabular experts", ["RF · ET · LGBM · XGB"], COL["porange"], COL["orange"]); mini_bits(ax, 0.528, 0.600, 0.055, 0.030)
    box(ax, 0.407, 0.455, 0.19, 0.10, "Frozen heads", ["linear · MLP · ensemble"], COL["porange"], COL["orange"])
    box(ax, 0.407, 0.325, 0.19, 0.10, "Registered candidates", ["eligible / failed / retained"], "white", COL["orange"], dashed=True, title_size=7.0)

    box(ax, 0.642, 0.715, 0.145, 0.10, "Validation ranking", ["metric direction fixed"], COL["pgreen"], COL["green"])
    box(ax, 0.642, 0.585, 0.145, 0.10, "Selection risk", ["one-SE · frequency", "variability"], COL["pgreen"], COL["green"], body_size=5.55)
    box(ax, 0.642, 0.455, 0.145, 0.10, "AD / UQ gate", ["similarity · spread"], COL["pgreen"], COL["green"])
    box(ax, 0.642, 0.325, 0.145, 0.10, "Decision", ["accept / retain / reject"], COL["pgreen"], COL["green"], body_size=5.5)

    box(ax, 0.832, 0.715, 0.14, 0.10, "Prediction", ["ROC/PR", "RMSE/MAE"], COL["pteal"], COL["teal"])
    box(ax, 0.832, 0.585, 0.14, 0.10, "Reliability", ["risk · conformal"], COL["pteal"], COL["teal"])
    box(ax, 0.832, 0.455, 0.14, 0.10, "Shift", ["OOD · cliffs · bRo5"], COL["pteal"], COL["teal"])
    box(ax, 0.832, 0.325, 0.14, 0.10, "Audit trail", ["source data", "hashes"], COL["pteal"], COL["teal"])

    for x1, x2 in [(0.172, 0.195), (0.362, 0.395), (0.597, 0.63), (0.787, 0.82)]:
        arrow(ax, x1, 0.57, x2, 0.57, COL["blue"], lw=1.1)
    ax.add_patch(FancyBboxPatch((0.07, 0.065), 0.86, 0.12, boxstyle="round,pad=0.006,rounding_size=0.012", facecolor="#F7F8FA", edgecolor=COL["line"], linewidth=0.8))
    ax.text(0.085, 0.162, "f  Experiment-thinking layer", fontsize=7.2, fontweight="bold", color=COL["ink"])
    labels = ["external\nvalidation", "calibration /\nimbalance", "Top-K\nstress", "robustness\naudit", "hard\nsubsets", "negative\nresults"]
    xs = np.linspace(0.18, 0.86, len(labels))
    for i, (x, label) in enumerate(zip(xs, labels)):
        ax.add_patch(Circle((x, 0.127), 0.014, facecolor=[COL["pblue"], COL["pgreen"], COL["porange"]][i % 3], edgecolor=COL["line"], lw=0.6))
        ax.text(x, 0.103, label, ha="center", va="top", fontsize=5.7, linespacing=1.05, color=COL["muted"])
    save(fig, "fig01_overall_workflow")


def figure02_model_structure() -> None:
    fig, ax = plt.subplots(figsize=(7.2, 5.15))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.text(0.015, 0.975, "FZYC-Mol model structure", fontsize=11.0, fontweight="bold", va="top", color=COL["ink"])
    ax.text(0.015, 0.941, "Parallel experts are selected by validation evidence and released with uncertainty, AD/OOD and interpretation signals", fontsize=6.9, va="top", color=COL["muted"])

    outer = [(0.02, 0.18, COL["blue"], "a  Molecular views"), (0.22, 0.28, COL["orange"], "b  Expert modules"), (0.53, 0.25, COL["green"], "c  Selector & fusion"), (0.81, 0.17, COL["purple"], "d  Evidence heads")]
    for x, w, ec, title in outer:
        ax.add_patch(FancyBboxPatch((x, 0.205), w, 0.68, boxstyle="round,pad=0.006,rounding_size=0.014", facecolor="white", edgecolor=ec, linewidth=1.0))
        ax.text(x + 0.010, 0.865, title, fontsize=7.3, fontweight="bold", color=COL["ink"], va="top")

    box(ax, 0.033, 0.705, 0.155, 0.115, "Input molecule", ["SMILES + graph"], COL["pblue"], COL["blue"]); molecule_icon(ax, 0.11, 0.727, 0.86)
    box(ax, 0.033, 0.555, 0.155, 0.115, "Structural views", ["graph · bonds · scaffold"], COL["pblue"], COL["blue"]); graph_icon(ax, 0.12, 0.558, 0.055, 0.050)
    box(ax, 0.033, 0.405, 0.155, 0.115, "Vector views", ["fingerprints · descriptors"], COL["pblue"], COL["blue"]); mini_bits(ax, 0.112, 0.423, 0.06, 0.03)
    box(ax, 0.033, 0.255, 0.155, 0.115, "Embedding views", ["frozen language", "encoders"], COL["pblue"], COL["blue"])

    box(ax, 0.233, 0.705, 0.255, 0.115, "I. Graph-message experts", ["GIN / GAT / D-MPNN / Chemprop"], COL["porange"], COL["orange"]); graph_icon(ax, 0.405, 0.706, 0.065, 0.050, COL["orange"])
    box(ax, 0.233, 0.555, 0.255, 0.115, "II. Fingerprint / descriptor trees", ["RF / ET / LGBM / XGB / CatBoost"], COL["porange"], COL["orange"], title_size=7.0); mini_bits(ax, 0.407, 0.575, 0.062, 0.03)
    box(ax, 0.233, 0.405, 0.255, 0.115, "III. Frozen-embedding\nheads", ["ChemBERTa / MoLFormer", "linear / MLP"], COL["ppurple"], COL["purple"], title_size=7.0, body_size=5.45)
    box(ax, 0.233, 0.255, 0.255, 0.115, "IV. Historical candidates\n(optional)", ["not confirmatory unless", "split-compatible"], "white", COL["line"], dashed=True, title_size=6.9, body_size=5.35)

    box(ax, 0.543, 0.705, 0.225, 0.115, "Validation selector", ["mean ± SD · ranking", "one-SE set"], COL["pgreen"], COL["green"])
    box(ax, 0.543, 0.555, 0.225, 0.115, "Selection-risk head", ["ambiguity · frequency · variability"], COL["pgreen"], COL["green"])
    box(ax, 0.543, 0.405, 0.225, 0.115, "Risk-aware fusion", ["ensemble spread · calibration", "AD / OOD"], COL["pgreen"], COL["green"])
    box(ax, 0.543, 0.255, 0.105, 0.115, "Accept", ["retained-best", "supported"], COL["pgreen"], COL["green"], title_size=6.8, body_size=5.3)
    box(ax, 0.66, 0.255, 0.108, 0.115, "Retain / reject", ["negative result", "preserved"], COL["porange"], COL["orange"], title_size=6.5, body_size=5.3)

    box(ax, 0.823, 0.705, 0.145, 0.115, "Property head", ["classification", "regression"], COL["ppurple"], COL["purple"])
    box(ax, 0.823, 0.555, 0.145, 0.115, "Calibration / UQ", ["Brier · ECE", "conformal"], COL["ppurple"], COL["purple"])
    box(ax, 0.823, 0.405, 0.145, 0.115, "AD / OOD head", ["Tanimoto", "low-similarity"], COL["ppurple"], COL["purple"])
    box(ax, 0.823, 0.255, 0.145, 0.115, "Interpretation", ["motif · fragment", "case studies"], COL["ppurple"], COL["purple"])

    for yy in [0.76, 0.61, 0.46, 0.31]:
        arrow(ax, 0.188, yy, 0.22, yy, COL["blue"]); arrow(ax, 0.488, yy, 0.53, yy, COL["orange"])
    for yy in [0.76, 0.61, 0.46, 0.31]:
        arrow(ax, 0.78, 0.61, 0.81, yy, COL["green"], rad=(yy - 0.61) * 0.25)
    ax.add_patch(FancyBboxPatch((0.12, 0.07), 0.76, 0.075, boxstyle="round,pad=0.006,rounding_size=0.010", facecolor="#F7F8FA", edgecolor=COL["blue"], linewidth=0.8))
    ax.text(0.14, 0.112, "e  Frozen test reporting", fontsize=7.1, fontweight="bold", va="center", color=COL["ink"])
    ax.text(0.39, 0.112, "test split\n+ predictions", fontsize=5.8, ha="center", va="center", linespacing=1.08, color=COL["muted"])
    ax.text(0.60, 0.112, "candidate CSVs\n+ decisions", fontsize=5.8, ha="center", va="center", linespacing=1.08, color=COL["muted"])
    ax.text(0.80, 0.112, "source data\n+ hashes", fontsize=5.8, ha="center", va="center", linespacing=1.08, color=COL["muted"])
    save(fig, "fig02_model_structure")


def figure03_candidate_pool_and_null() -> None:
    source = ROOT / "results" / "source_data" / "candidate_pool_summary.csv"
    null_path = ROOT / "results" / "selection_closure" / "null_calibration_summary.csv"
    data = pd.read_csv(source); null = pd.read_csv(null_path)
    copy_source(source, "fig03_candidate_pool_summary.csv"); copy_source(null_path, "fig03_null_calibration_summary.csv")
    modes = ["random_order", "random_subset", "family_balanced"]
    labels = ["Random order", "Random subset", "Family-balanced"]
    colors = [COL["grey"], COL["blue"], COL["orange"]]
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.1))
    for ax, metric, ylabel, lab in [
        (axes[0, 0], "mean", "Fixed-denominator regret", "a"),
        (axes[1, 0], "mrr_mean", "MRR", "c"),
    ]:
        for mode, label, color in zip(modes, labels, colors):
            s = data[data["mode"].eq(mode)].sort_values("pool_size")
            if metric == "mean":
                ax.errorbar(s["pool_size"], s["mean"], yerr=[s["mean"] - s["ci95_low"], s["ci95_high"] - s["mean"]], marker="o", ms=3.5, lw=1.25, capsize=2, color=color, label=label)
            else:
                ax.plot(s["pool_size"], s[metric], marker="o", ms=3.5, lw=1.25, color=color, label=label)
        ax.set(xlabel="Registered candidates, K", ylabel=ylabel, xticks=[4, 8, 16, 32]); style_axis(ax); panel(ax, lab)
    axes[0, 0].legend(ncol=1, loc="upper left")

    ax = axes[0, 1]
    x = null["pool_size"].to_numpy()
    ax.fill_between(x, null["null_chance_adjusted_hit_ci95_low"], null["null_chance_adjusted_hit_ci95_high"], color=COL["light"], alpha=0.7, label="Permutation null 95% interval")
    ax.plot(x, null["null_chance_adjusted_hit_mean"], color=COL["grey"], ls="--", lw=1.1, label="Permutation null")
    ax.plot(x, null["observed_chance_adjusted_hit"], color=COL["blue"], marker="o", lw=1.45, label="Observed nested selection")
    ax.axhline(0, color=COL["ink"], lw=0.7)
    ax.set(xlabel="Registered candidates, K", ylabel="Chance-adjusted Top-3 hit", xticks=[4, 8, 16, 32]); style_axis(ax); panel(ax, "b"); ax.legend(loc="upper right")

    ax = axes[1, 1]
    ax.plot(x, null["null_fixed_regret_mean"], color=COL["grey"], marker="s", ls="--", lw=1.15, label="Permutation null")
    ax.plot(x, null["observed_fixed_regret"], color=COL["blue"], marker="o", lw=1.45, label="Observed nested selection")
    ax.fill_between(x, null["null_fixed_regret_ci95_low"], null["null_fixed_regret_ci95_high"], color=COL["light"], alpha=0.7)
    ax.set(xlabel="Registered candidates, K", ylabel="Fixed-denominator regret", xticks=[4, 8, 16, 32]); style_axis(ax); panel(ax, "d"); ax.legend(loc="best")
    fig.tight_layout(w_pad=2.0, h_pad=1.8)
    save(fig, "fig03_candidate_pool_and_null")


def figure04_nested_selection_risk() -> None:
    boot_path = ROOT / "results" / "source_data" / "repeated_nested_bootstrap.csv"
    risk_path = ROOT / "results" / "selection_closure" / "selection_risk_units.csv"
    curve_path = ROOT / "results" / "selection_closure" / "selection_risk_curve.csv"
    boot = pd.read_csv(boot_path); risk = pd.read_csv(risk_path); curves = pd.read_csv(curve_path)
    copy_source(boot_path, "fig04_repeated_nested_bootstrap.csv"); copy_source(risk_path, "fig04_selection_risk_units.csv"); copy_source(curve_path, "fig04_selection_risk_curve.csv")
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.2))
    specs = [("fixed_normalized_regret", "Fixed-denominator regret", "a", COL["blue"]), ("chance_adjusted_hit", "Chance-adjusted Top-3 hit", "b", COL["green"])]
    for ax, (metric, ylabel, lab, color) in zip(axes[0], specs):
        s = boot[boot["metric"].eq(metric)].sort_values("pool_size")
        ax.errorbar(s["pool_size"], s["mean"], yerr=[s["mean"] - s["ci95_low"], s["ci95_high"] - s["mean"]], color=color, marker="o", lw=1.45, capsize=2.5)
        ax.set(xlabel="Registered candidates, K", ylabel=ylabel, xticks=[4, 8, 16, 32]); style_axis(ax); panel(ax, lab)

    ax = axes[1, 0]
    for k, color in zip([4, 8, 16, 32], [COL["blue2"], COL["green"], COL["orange"], COL["purple"]]):
        s = risk[risk["pool_size"].eq(k)]
        ax.scatter(s["selection_risk"], s["fixed_normalized_regret"], s=10, alpha=0.42, color=color, edgecolor="none", label=f"K={k}")
    slope, intercept, _, _, _ = linregress(risk["selection_risk"], risk["fixed_normalized_regret"])
    xx = np.linspace(risk["selection_risk"].min(), risk["selection_risk"].max(), 100)
    ax.plot(xx, intercept + slope * xx, color=COL["ink"], lw=1.2)
    values = json.loads((ROOT / "results" / "selection_closure" / "selection_closure_values.json").read_text(encoding="utf-8"))
    rho = values["selection_risk"]["overall_spearman"]
    ax.text(0.97, 0.95, f"Spearman ρ = {rho:.3f}", transform=ax.transAxes, va="top", ha="right", fontsize=7.2)
    ax.set(xlabel="Validation-side selection risk", ylabel="Outer fixed regret"); style_axis(ax); panel(ax, "c"); ax.legend(ncol=2, loc="lower right")

    ax = axes[1, 1]
    s = curves[curves["pool_size"].astype(str).eq("all")].sort_values("coverage")
    ax.plot(s["coverage"], s["mean_regret"], color=COL["blue"], marker="o", lw=1.45, label="Low-risk units retained")
    ax.axhline(risk["fixed_normalized_regret"].mean(), color=COL["grey"], ls="--", lw=1.1, label="No rejection")
    ax.set(xlabel="Coverage retained", ylabel="Mean outer regret", xlim=(0.08, 1.02)); style_axis(ax); panel(ax, "d"); ax.legend(loc="best")
    fig.tight_layout(w_pad=2.0, h_pad=1.8)
    save(fig, "fig04_nested_selection_risk")


def figure05_moleculenet_rank_audit() -> None:
    main_path = ROOT / "reports" / "manuscript_tables" / "table2_moleculenet_main_long.csv"
    rank_path = ROOT / "reports" / "supplement_experiment_revision_20260606" / "maintext_table_validation_bias_extended.csv"
    clintox_path = ROOT / "reports" / "reviewer_revision_20260607" / "clintox_fixed_precision_recall_consensus_strict_core_multifp.csv"
    main = pd.read_csv(main_path); rank = pd.read_csv(rank_path); clintox = pd.read_csv(clintox_path)
    copy_source(main_path, "fig05_moleculenet_source.csv"); copy_source(rank_path, "fig05_rank_audit.csv"); copy_source(clintox_path, "fig05_clintox_recall.csv")
    cats = ["Classical Morgan", "Chemprop", "FZYC-Mol final retained-best", "Best observed candidate"]
    cat_labels = ["Morgan", "Chemprop", "FZYC-Mol retained", "Test-oracle bound"]
    cat_colors = [COL["grey"], COL["purple"], COL["blue"], COL["orange"]]
    pretty = {"bbbp": "BBBP", "bace": "BACE", "clintox": "ClinTox", "esol": "ESOL", "freesolv": "FreeSolv", "lipo": "Lipo"}
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.35))
    for ax, task, ylabel, lab in [(axes[0, 0], "classification", "ROC-AUC", "a"), (axes[0, 1], "regression", "RMSE", "b")]:
        sub = main[main["task_type"].eq(task) & main["category"].isin(cats)].copy()
        datasets = list(dict.fromkeys(sub["dataset"]))
        x = np.arange(len(datasets)); width = 0.18
        for j, (cat, label, color) in enumerate(zip(cats, cat_labels, cat_colors)):
            vals = sub[sub["category"].eq(cat)].set_index("dataset").reindex(datasets)
            ax.errorbar(x + (j - 1.5) * width, vals["value"], yerr=vals["std"], fmt="o", ms=3.2, capsize=2, color=color, label=label)
        ax.set_xticks(x, [pretty.get(d, d) for d in datasets]); ax.set_ylabel(ylabel); style_axis(ax); panel(ax, lab)
        if task == "classification":
            ax.set_ylim(0.75, 1.01)
            legend_handles, legend_labels = ax.get_legend_handles_labels()

    ax = axes[1, 0]
    means = [clintox["recall_p80"].mean(), clintox["recall_p90"].mean()]
    sds = [clintox["recall_p80"].std(ddof=1), clintox["recall_p90"].std(ddof=1)]
    ax.bar([0, 1], means, yerr=sds, color=[COL["green"], COL["orange"]], width=0.55, capsize=3, alpha=0.85)
    jitter = np.linspace(-0.08, 0.08, len(clintox))
    ax.scatter(jitter, clintox["recall_p80"], s=13, color=COL["ink"], zorder=3)
    ax.scatter(1 + jitter, clintox["recall_p90"], s=13, color=COL["ink"], zorder=3)
    ax.set_xticks([0, 1], ["Precision ≥ 0.80", "Precision ≥ 0.90"]); ax.set_ylabel("ClinTox recall"); ax.set_ylim(0, 1.03); ax.yaxis.set_major_formatter(PercentFormatter(1.0)); style_axis(ax); panel(ax, "c")

    ax = axes[1, 1]
    audit = rank[~rank["source"].eq("overall")].sort_values("median_spearman")
    y = np.arange(len(audit))
    ax.scatter(audit["median_spearman"], y, s=20, color=COL["blue"])
    ax.set_yticks(y, [s.replace("_", " ") for s in audit["source"]]); ax.set_xlabel("Validation–test rank Spearman"); ax.axvline(0, color=COL["ink"], lw=0.7)
    overall = rank[rank["source"].eq("overall")].iloc[0]
    ax.text(0.03, 0.97, f"Median = {overall['median_spearman']:.3f}\nTop-1 = {overall['top1_match_rate']:.3f}; Top-3 = {overall['test_top_in_valid_top3_rate']:.3f}", transform=ax.transAxes, va="top", fontsize=7.0)
    style_axis(ax, "x"); panel(ax, "d")
    fig.legend(legend_handles, legend_labels, ncol=4, loc="upper center", bbox_to_anchor=(0.5, 0.995), fontsize=7.5)
    fig.tight_layout(rect=(0, 0, 1, 0.94), w_pad=2.0, h_pad=1.8)
    save(fig, "fig05_moleculenet_rank_audit")


def figure06_tdc_gate_audit() -> None:
    path = ROOT / "results" / "source_data" / "tdc_gate_audit.csv"
    data = pd.read_csv(path)
    copy_source(path, "fig06_tdc_gate_audit.csv")
    labels = {
        "promoted_and_improved": "Promoted + improved",
        "retained_and_avoided_harm": "Retained + avoided harm",
        "inconclusive_due_to_wide_ci": "Inconclusive (wide CI)",
        "promoted_but_harmed": "Promoted but harmed",
    }
    counts = data.groupby(["gate_category", "promoted"]).size().rename("count").reset_index()
    counts.to_csv(SRC_DIR / "fig06_gate_counts.csv", index=False)
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 5.15), gridspec_kw={"width_ratios": [0.86, 1.55]})
    ax = axes[0]
    order = [k for k in labels if k in set(data["gate_category"])]
    y = np.arange(len(order))
    promoted = [int(counts[(counts["gate_category"].eq(k)) & counts["promoted"]]["count"].sum()) for k in order]
    retained = [int(counts[(counts["gate_category"].eq(k)) & ~counts["promoted"]]["count"].sum()) for k in order]
    ax.barh(y, retained, color=COL["grey"], alpha=0.8, label="Retained")
    ax.barh(y, promoted, left=retained, color=COL["blue"], alpha=0.9, label="Promoted")
    ax.set_yticks(y, [labels[k] for k in order]); ax.invert_yaxis(); ax.set_xlabel("Endpoints"); ax.set_xticks(range(0, max(np.array(promoted) + np.array(retained)) + 2, 2)); style_axis(ax, "x"); panel(ax, "a"); ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=2)

    ax = axes[1]
    plot = data.sort_values(["promoted", "test_delta"], ascending=[True, True]).reset_index(drop=True)
    y = np.arange(len(plot))
    colors = np.where(plot["promoted"], COL["blue"], COL["grey"])
    ax.hlines(y, plot["ci_low"], plot["ci_high"], color=COL["light"], lw=1.2)
    ax.scatter(plot["test_delta"], y, c=colors, s=18, zorder=3)
    ax.axvline(0, color=COL["ink"], lw=0.75)
    ax.set_yticks(y, plot["endpoint"].str.replace("_", " "))
    ax.tick_params(axis="y", labelsize=6.8)
    ax.set_xlabel("Direction-normalized test delta (seed summary)"); style_axis(ax, "x"); panel(ax, "b")
    handles = [Line2D([], [], marker="o", color="none", markerfacecolor=COL["blue"], markeredgecolor="none", label="Promoted"), Line2D([], [], marker="o", color="none", markerfacecolor=COL["grey"], markeredgecolor="none", label="Retained")]
    ax.legend(handles=handles, loc="lower right")
    fig.tight_layout(w_pad=2.0)
    save(fig, "fig06_tdc_gate_audit")


def _risk_curve(loss: np.ndarray, score: np.ndarray, task: str, coverages: np.ndarray):
    order = np.argsort(score); oracle_order = np.argsort(loss)
    full = float(np.sqrt(np.mean(loss))) if task == "regression" else float(np.mean(loss))
    obs, oracle = [], []
    for coverage in coverages:
        k = max(1, int(round(coverage * len(loss))))
        if task == "regression":
            obs.append(float(np.sqrt(np.mean(loss[order[:k]])))); oracle.append(float(np.sqrt(np.mean(loss[oracle_order[:k]]))))
        else:
            obs.append(float(np.mean(loss[order[:k]]))); oracle.append(float(np.mean(loss[oracle_order[:k]])))
    return np.asarray(obs), np.asarray(oracle), np.repeat(full, len(coverages))


def figure07_prediction_and_selection_risk() -> None:
    raw_path = ROOT / "reports" / "risk_calibrated_selector" / "compound_risk_predictions.csv"
    selection_path = ROOT / "results" / "selection_closure" / "selection_risk_curve.csv"
    raw = pd.read_csv(raw_path); selection = pd.read_csv(selection_path)
    copy_source(raw_path, "fig07_compound_risk_predictions.csv"); copy_source(selection_path, "fig07_selection_risk_curve.csv")
    wanted = [("moleculenet", "bbbp", "BBBP", "classification"), ("moleculenet", "clintox", "ClinTox", "classification"), ("tdc_admet", "tdc_caco2_wang", "Caco2", "regression")]
    coverages = np.arange(0.1, 1.01, 0.1)
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.2))
    curve_rows = []
    for i, (ax, (source, endpoint, title, task)) in enumerate(zip(axes.ravel()[:3], wanted)):
        subset = raw[raw["source"].eq(source) & raw["dataset"].eq(endpoint)]
        observed, oracle, random = [], [], []
        for seed, group in subset.groupby("seed"):
            if task == "classification":
                loss = ((group["y_pred_calibrated"].to_numpy() >= 0.5).astype(int) != group["y_true"].to_numpy().astype(int)).astype(float)
            else:
                loss = (group["y_pred_calibrated"].to_numpy() - group["y_true"].to_numpy()) ** 2
            o, q, r = _risk_curve(loss, group["risk_score"].to_numpy(), task, coverages)
            observed.append(o); oracle.append(q); random.append(r)
            for c, ov, oq, rr in zip(coverages, o, q, r):
                curve_rows.append({"source": source, "endpoint": endpoint, "seed": seed, "coverage": c, "observed_risk": ov, "oracle_risk": oq, "random_risk": rr})
        om = np.mean(observed, axis=0); osd = np.std(observed, axis=0, ddof=1)
        qm = np.mean(oracle, axis=0); rm = np.mean(random, axis=0)
        ax.plot(coverages, om, color=COL["blue"], marker="o", ms=2.5, lw=1.4, label="Risk-ranked")
        ax.fill_between(coverages, np.maximum(0, om - osd), om + osd, color=COL["pblue"], alpha=0.9)
        ax.plot(coverages, qm, color=COL["green"], ls="--", lw=1.15, label="Error-oracle")
        ax.plot(coverages, rm, color=COL["grey"], ls=":", lw=1.15, label="Random rejection")
        ax.set_title(title); ax.set_xlabel("Coverage retained"); ax.set_ylabel("RMSE" if task == "regression" else "Error rate"); style_axis(ax); panel(ax, chr(ord("a") + i))
        if i == 0: ax.legend(loc="center right")
    pd.DataFrame(curve_rows).to_csv(SRC_DIR / "fig07_prediction_risk_curves.csv", index=False)

    ax = axes[1, 1]
    s = selection[selection["pool_size"].astype(str).eq("all")].sort_values("coverage")
    ax.plot(s["coverage"], s["mean_regret"], color=COL["purple"], marker="o", ms=3, lw=1.45, label="Selection-risk ranking")
    ax.axhline(float(s.loc[s["coverage"].idxmax(), "mean_regret"]), color=COL["grey"], ls="--", lw=1.1, label="All outer units")
    ax.set_title("Selector reliability"); ax.set_xlabel("Outer units retained"); ax.set_ylabel("Mean fixed regret"); style_axis(ax); panel(ax, "d"); ax.legend(loc="best")
    fig.tight_layout(w_pad=1.8, h_pad=1.8)
    save(fig, "fig07_prediction_and_selection_risk")


def figure08_conformal_audit() -> None:
    path = ROOT / "results" / "source_data" / "conformal_long.csv"
    data = pd.read_csv(path)
    copy_source(path, "fig08_conformal_long.csv")
    cls = data[data["task_type"].eq("classification")]
    reg = data[data["task_type"].eq("regression")]
    summary_rows = []
    for task, frame in [("classification", cls), ("regression", reg)]:
        for target, group in frame.groupby("target_coverage"):
            row = {"task_type": task, "target_coverage": target, "coverage_mean": group["coverage"].mean(), "coverage_sd": group["coverage"].std(ddof=1)}
            if task == "classification":
                row.update({"class_0_coverage_mean": group["class_0_coverage"].mean(), "class_1_coverage_mean": group["class_1_coverage"].mean(), "avg_set_size_mean": group["avg_set_size"].mean(), "fallback_rate": group["fallback_reason"].notna().mean()})
            else:
                row.update({"mean_width_mean": group["mean_width"].mean(), "normalized_width_sd_mean": group["normalized_width_sd"].mean()})
            summary_rows.append(row)
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(SRC_DIR / "fig08_conformal_summary.csv", index=False)
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.1))

    ax = axes[0, 0]
    c = summary[summary["task_type"].eq("classification")]
    ax.plot(c["target_coverage"], c["coverage_mean"], marker="o", color=COL["blue"], lw=1.4, label="Overall")
    ax.plot(c["target_coverage"], c["class_0_coverage_mean"], marker="s", color=COL["green"], lw=1.15, label="Class 0")
    ax.plot(c["target_coverage"], c["class_1_coverage_mean"], marker="^", color=COL["orange"], lw=1.15, label="Class 1")
    ax.plot([0.78, 0.97], [0.78, 0.97], color=COL["ink"], ls="--", lw=0.8)
    ax.set(xlabel="Nominal coverage", ylabel="Classification coverage", xlim=(0.78, 0.97), ylim=(0.75, 1.0)); style_axis(ax); panel(ax, "a"); ax.legend(loc="lower right")

    ax = axes[0, 1]
    r = summary[summary["task_type"].eq("regression")]
    ax.errorbar(r["target_coverage"], r["coverage_mean"], yerr=r["coverage_sd"], marker="o", color=COL["purple"], lw=1.4, capsize=2)
    ax.plot([0.78, 0.97], [0.78, 0.97], color=COL["ink"], ls="--", lw=0.8)
    ax.set(xlabel="Nominal coverage", ylabel="Regression coverage", xlim=(0.78, 0.97), ylim=(0.72, 1.02)); style_axis(ax); panel(ax, "b")

    ax = axes[1, 0]
    ax.plot(c["target_coverage"], c["avg_set_size_mean"], marker="o", color=COL["blue"], lw=1.4)
    ax.set(xlabel="Nominal coverage", ylabel="Mean prediction-set size"); style_axis(ax); panel(ax, "c")
    ax2 = ax.twinx(); ax2.plot(c["target_coverage"], c["fallback_rate"], marker="s", color=COL["orange"], lw=1.15); ax2.set_ylabel("Pooled fallback rate", color=COL["orange"]); ax2.yaxis.set_major_formatter(PercentFormatter(1.0)); ax2.spines["top"].set_visible(False)

    ax = axes[1, 1]
    ax.plot(r["target_coverage"], r["mean_width_mean"], marker="o", color=COL["purple"], lw=1.4)
    ax.set(xlabel="Nominal coverage", ylabel="Mean interval width"); style_axis(ax); panel(ax, "d")
    ax2 = ax.twinx(); ax2.plot(r["target_coverage"], r["normalized_width_sd_mean"], marker="s", color=COL["teal"], lw=1.15); ax2.set_ylabel("Width / train-label SD", color=COL["teal"]); ax2.spines["top"].set_visible(False)
    fig.tight_layout(w_pad=2.2, h_pad=1.8)
    save(fig, "fig08_conformal_audit")


def _mean_sd(value: object) -> tuple[float, float]:
    import re
    values = re.findall(r"[-+]?\d+(?:\.\d+)?", str(value))
    if not values:
        return np.nan, np.nan
    return float(values[0]), float(values[1]) if len(values) > 1 else 0.0


def figure09_chemical_boundaries() -> None:
    gap_path = ROOT / "reports" / "remaining_missing_experiments_20260606" / "moleculeace_gap_correlation_summary.csv"
    cyc_path = ROOT / "reports" / "full_missing_experiment_run_20260611" / "bro5_cycpept_pampa_compact_summary.csv"
    lin_path = ROOT / "reports" / "full_missing_experiment_run_20260611" / "linpept_compact_summary_20260611.csv"
    gap = pd.read_csv(gap_path); cyc = pd.read_csv(cyc_path); lin = pd.read_csv(lin_path)
    copy_source(gap_path, "fig09_moleculeace_gap.csv"); copy_source(cyc_path, "fig09_cycpept.csv"); copy_source(lin_path, "fig09_linpept.csv")
    task = gap.groupby("task", as_index=False).agg(gap_spearman=("gap_spearman", "mean"), gap_sd=("gap_spearman", "std"), direction_accuracy=("direction_accuracy", "mean"), direction_sd=("direction_accuracy", "std"), n_pairs=("n_pairs", "mean")).sort_values("gap_spearman")
    task.to_csv(SRC_DIR / "fig09_moleculeace_task_summary.csv", index=False)
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.75))
    ax = axes[0, 0]; y = np.arange(len(task))
    ax.errorbar(task["gap_spearman"], y, xerr=task["gap_sd"], fmt="o", ms=3, color=COL["blue"], ecolor=COL["light"], capsize=2)
    ax.set_yticks(y, task["task"]); ax.tick_params(axis="y", labelsize=6.8); ax.axvline(0, color=COL["ink"], lw=0.75); ax.set_xlabel("Predicted–true activity-gap Spearman"); style_axis(ax, "x"); panel(ax, "a")

    ax = axes[0, 1]
    ax.scatter(task["gap_spearman"], task["direction_accuracy"], s=14 + np.sqrt(task["n_pairs"]) * 1.5, color=COL["green"], alpha=0.8)
    ax.axhline(0.5, color=COL["ink"], ls="--", lw=0.75); ax.axvline(0, color=COL["ink"], ls=":", lw=0.75)
    ax.set(xlabel="Gap Spearman", ylabel="Cliff-pair direction accuracy", ylim=(0.35, 1.02)); ax.yaxis.set_major_formatter(PercentFormatter(1.0)); style_axis(ax); panel(ax, "b")

    ax = axes[1, 0]
    means, sds = zip(*(_mean_sd(v) for v in cyc["test_RMSE"]))
    x = np.arange(len(cyc)); ax.bar(x, means, yerr=sds, color=[COL["green"], COL["blue"], COL["orange"], COL["purple"]], width=0.65, capsize=3, alpha=0.9)
    ax.set_xticks(x, cyc["split"].str.title()); ax.set_ylabel("CycPept-PAMPA RMSE"); style_axis(ax); panel(ax, "c")

    rows = []
    for _, row in lin.iterrows():
        roc, roc_sd = _mean_sd(row["test_ROC_AUC"]); pr, pr_sd = _mean_sd(row["test_PR_AUC"])
        rows.append({"dataset": row["dataset"], "split": row["split"], "roc": roc, "roc_sd": roc_sd, "pr": pr, "pr_sd": pr_sd})
    lp = pd.DataFrame(rows); lp.to_csv(SRC_DIR / "fig09_linpept_parsed.csv", index=False)
    ax = axes[1, 1]
    markers = {"linpept_cellpen": "o", "linpept_nonfouling": "s"}; colors = {"random": COL["green"], "scaffold": COL["blue"], "perimeter": COL["orange"]}
    for dataset, group in lp.groupby("dataset"):
        for _, row in group.iterrows():
            ax.errorbar(row["roc"], row["pr"], xerr=row["roc_sd"], yerr=row["pr_sd"], fmt=markers[dataset], ms=5, color=colors[row["split"]], capsize=2)
    handles = [Line2D([], [], marker="o", color="none", markerfacecolor=c, label=s.title()) for s, c in colors.items()] + [Line2D([], [], marker="o", color=COL["ink"], label="CellPen", linestyle="none"), Line2D([], [], marker="s", color=COL["ink"], label="NonFouling", linestyle="none")]
    ax.set(xlabel="LinPept ROC-AUC", ylabel="LinPept PR-AUC", xlim=(0.70, 0.98), ylim=(0.62, 0.94)); style_axis(ax); panel(ax, "d"); ax.legend(handles=handles, ncol=2, loc="lower right")
    fig.tight_layout(w_pad=2.0, h_pad=1.8)
    save(fig, "fig09_chemical_boundaries")


def figure10_governance_transfer() -> None:
    summary_path = ROOT / "results" / "source_data" / "ablation_summary.csv"
    governance_path = ROOT / "results" / "nested_selection" / "governance_ablation.csv"
    transfer_path = ROOT / "results" / "selection_closure" / "leave_one_endpoint_out_policy.csv"
    summary = pd.read_csv(summary_path); governance = pd.read_csv(governance_path); transfer = pd.read_csv(transfer_path)
    copy_source(summary_path, "fig10_ablation_summary.csv"); copy_source(governance_path, "fig10_governance_ablation.csv"); copy_source(transfer_path, "fig10_policy_transfer.csv")
    fig = plt.figure(figsize=(7.2, 5.75)); gs = fig.add_gridspec(2, 2, width_ratios=[0.92, 1.35], hspace=0.54, wspace=0.46)
    for pos, ablation_class, lab, title in [((0, 0), "governance_rule", "a", "Governance rule"), ((1, 0), "candidate_family_removal", "b", "Candidate composition")]:
        ax = fig.add_subplot(gs[pos])
        s = summary[summary["ablation_class"].eq(ablation_class)].sort_values("mean_fixed_regret")
        y = np.arange(len(s))
        labels = [v.replace("frozen_one_se_governance", "frozen one-SE").replace("one_se_", "one-SE ").replace("validation_best", "validation-best").replace("full_pool", "full pool").replace("remove_", "remove ").replace("_", " ") for v in s["variant"]]
        ax.errorbar(s["mean_fixed_regret"], y, xerr=[s["mean_fixed_regret"] - s["ci95_low"], s["ci95_high"] - s["mean_fixed_regret"]], fmt="o", ms=4, color=COL["blue"] if ablation_class == "governance_rule" else COL["orange"], ecolor=COL["light"], capsize=2)
        ax.set_yticks(y, labels); ax.tick_params(axis="y", labelsize=6.9); ax.set_xlabel("Mean fixed regret"); ax.set_title(title, loc="left", fontsize=8.5); style_axis(ax, "x"); panel(ax, lab, -0.20, 1.10)

    ax = fig.add_subplot(gs[0, 1])
    endpoint_rule = governance.groupby(["endpoint", "variant"])["full32_fixed_normalized_regret"].mean().unstack()
    variants = list(endpoint_rule.columns); endpoints = list(endpoint_rule.index)
    image = ax.imshow(endpoint_rule.to_numpy(), aspect="auto", cmap="Blues", vmin=0, vmax=max(0.35, float(endpoint_rule.max().max())))
    ax.set_xticks(np.arange(len(variants)), [v.replace("frozen_one_se_governance", "frozen one-SE").replace("one_se_", "one-SE ").replace("validation_best", "validation-best").replace("_", " ") for v in variants], rotation=32, ha="right")
    ax.set_yticks(np.arange(len(endpoints)), [e.replace("tdc_", "").replace("_", " ") for e in endpoints]); ax.tick_params(axis="both", labelsize=6.8)
    for i in range(len(endpoints)):
        j = int(np.argmin(endpoint_rule.iloc[i].to_numpy()))
        ax.text(j, i, "●", ha="center", va="center", color=COL["orange"], fontsize=6)
    ax.set_title("Endpoint-wise regret (dot = endpoint oracle)", loc="left", fontsize=8.5); panel(ax, "c", -0.12, 1.10)
    cbar = fig.colorbar(image, ax=ax, fraction=0.035, pad=0.02); cbar.ax.tick_params(labelsize=6.5)

    ax = fig.add_subplot(gs[1, 1])
    plot = transfer.sort_values("heldout_regret"); y = np.arange(len(plot))
    ax.hlines(y, plot["heldout_oracle_regret"], plot["heldout_regret"], color=COL["light"], lw=2)
    ax.scatter(plot["heldout_regret"], y, color=COL["blue"], s=20, label="LOEO-selected rule")
    ax.scatter(plot["heldout_oracle_regret"], y, color=COL["orange"], marker="D", s=18, label="Endpoint oracle rule")
    ax.set_yticks(y, plot["held_endpoint"].str.replace("tdc_", "").str.replace("_", " "))
    ax.tick_params(axis="y", labelsize=6.8)
    ax.set_xlabel("Held-out endpoint fixed regret"); style_axis(ax, "x"); panel(ax, "d", -0.12, 1.10); ax.legend(loc="lower right")
    save(fig, "fig10_governance_transfer")


def write_contracts() -> None:
    text = """# Figure contracts and QA notes\n\nBackend: Python/matplotlib exclusively. Target: double-column journal figures, editable SVG text and 450-dpi PNG previews.\n\n| Figure | Core conclusion | Archetype | Source-data focus |\n|---|---|---|---|\n| 1 | The workflow freezes protocol, candidates and selection before outer test evidence. | schematic-led composite | conceptual; implemented modules only |\n| 2 | Parallel molecular experts feed a validation selector, selection-risk layer and evidence heads. | schematic-led composite | conceptual; historical split-incompatible candidates explicitly dashed |\n| 3 | Candidate expansion weakens ranking but remains above a permutation-null selector. | quantitative grid | randomized pools + 1,000 permutations |\n| 4 | Repeated nested validation exposes regret growth, while validation-side risk triages high-regret units. | quantitative grid | 9 endpoints × 3 outer × 3 inner × 5 repeats |\n| 5 | Predictive scores and validation-test ranking quality must be interpreted jointly. | quantitative grid | MoleculeNet, ClinTox, ranking audit |\n| 6 | The TDC gate promotes only supported endpoints and preserves inconclusive outcomes. | asymmetric quantitative | 22 endpoints |\n| 7 | Prediction risk and selector risk both support selective retention, at different statistical units. | quantitative grid | compound-level and outer-unit risk curves |\n| 8 | Conformal coverage must be reported with class-conditional and efficiency diagnostics. | quantitative grid | 80/90/95% targets |\n| 9 | Activity cliffs and bRo5 splits define chemical boundary conditions. | quantitative grid | MoleculeACE, CycPept, LinPept |\n| 10 | No governance rule is endpoint-universal; leave-one-endpoint-out transfer misses two endpoint-specific optima. | asymmetric quantitative | governance, family removal, LOEO transfer |\n\nQA: all quantitative panels trace to CSV files in source_data; test-oracle values are labelled only as retrospective bounds; colors are redundant with marker/line encodings where comparisons matter; SVG text remains editable.\n"""
    (PACKAGE / "figure_contracts_and_qa.md").write_text(text, encoding="utf-8")


def main() -> None:
    setup()
    figure01_overall_workflow()
    figure02_model_structure()
    figure03_candidate_pool_and_null()
    figure04_nested_selection_risk()
    figure05_moleculenet_rank_audit()
    figure06_tdc_gate_audit()
    figure07_prediction_and_selection_risk()
    figure08_conformal_audit()
    figure09_chemical_boundaries()
    figure10_governance_transfer()
    write_contracts()
    print(f"Generated {len(list(FIG_DIR.glob('*.svg')))} SVG and {len(list(FIG_DIR.glob('*.png')))} PNG files")


if __name__ == "__main__":
    main()
