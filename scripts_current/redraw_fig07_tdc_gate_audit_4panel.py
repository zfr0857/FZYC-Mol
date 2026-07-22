from __future__ import annotations

import shutil
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "fig07_tdc_gate_audit_4panel"
DESKTOP = Path.home() / "Desktop"

COL = {
    "ink": "#182230",
    "muted": "#667085",
    "blue": "#3568A8",
    "blue2": "#7EA6D8",
    "grey": "#737B86",
    "light": "#D8DEE6",
    "red": "#BF5B5B",
    "orange": "#D98C3F",
}

CATEGORY_LABELS = {
    "promoted_and_improved": "Promoted + improved",
    "retained_and_avoided_harm": "Retained + avoided harm",
    "inconclusive_due_to_wide_ci": "Inconclusive (wide CI)",
    "promoted_but_harmed": "Promoted but harmed",
}

CATEGORY_ORDER = [
    "promoted_and_improved",
    "retained_and_avoided_harm",
    "inconclusive_due_to_wide_ci",
    "promoted_but_harmed",
]


def setup() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Microsoft YaHei", "DejaVu Sans", "sans-serif"],
            "font.size": 9.6,
            "axes.titlesize": 10.4,
            "axes.labelsize": 11.0,
            "xtick.labelsize": 9.4,
            "ytick.labelsize": 9.4,
            "legend.fontsize": 8.3,
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


def source_path() -> Path:
    paths = list((ROOT / "output").glob("*/source_data/fig07_source_data.csv"))
    if not paths:
        raise FileNotFoundError("fig07_source_data.csv was not found under output/*/source_data")
    return max(paths, key=lambda p: p.stat().st_mtime)


def style_axis(ax: plt.Axes, grid: str | None = "x") -> None:
    ax.tick_params(length=3, width=0.7, colors=COL["ink"])
    ax.spines["left"].set_color(COL["ink"])
    ax.spines["bottom"].set_color(COL["ink"])
    if grid:
        ax.grid(axis=grid, color="#E7EAF0", linewidth=0.55, zorder=0)


def panel(ax: plt.Axes, label: str, x: float = -0.12, y: float = 1.08) -> None:
    ax.text(x, y, label, transform=ax.transAxes, fontsize=11.6, fontweight="bold", va="top", color=COL["ink"])


def endpoint_label(value: str) -> str:
    return value.replace("_", " ")


def plot_gate_counts(ax: plt.Axes, data: pd.DataFrame) -> None:
    order = [k for k in CATEGORY_ORDER if k in set(data["gate_category"])]
    y = np.arange(len(order))
    promoted = []
    retained = []
    for category in order:
        subset = data[data["gate_category"].eq(category)]
        promoted.append(int(subset["promoted"].sum()))
        retained.append(int((~subset["promoted"]).sum()))
    ax.barh(y, retained, color=COL["grey"], alpha=0.78, label="Retained")
    ax.barh(y, promoted, left=retained, color=COL["blue"], alpha=0.92, label="Promoted")
    totals = np.array(promoted) + np.array(retained)
    for yi, total in zip(y, totals):
        ax.text(total + 0.25, yi, str(int(total)), va="center", fontsize=8.0, color=COL["muted"])
    ax.set_yticks(y, [CATEGORY_LABELS[k] for k in order])
    ax.invert_yaxis()
    ax.set_xlabel("Endpoints")
    ax.set_xlim(0, max(totals) + 1.5)
    ax.set_xticks(range(0, int(max(totals)) + 2, 2))
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=2)
    style_axis(ax, "x")
    panel(ax, "a")


def plot_seed_support(ax: plt.Axes, data: pd.DataFrame) -> None:
    order = [k for k in CATEGORY_ORDER if k in set(data["gate_category"])]
    y = np.arange(len(order))
    win = np.array([data.loc[data["gate_category"].eq(k), "seed_win_count"].sum() for k in order], dtype=float)
    tie = np.array([data.loc[data["gate_category"].eq(k), "seed_tie_count"].sum() for k in order], dtype=float)
    loss = np.array([data.loc[data["gate_category"].eq(k), "seed_loss_count"].sum() for k in order], dtype=float)
    total = np.maximum(win + tie + loss, 1.0)
    win_p, tie_p, loss_p = win / total, tie / total, loss / total
    ax.barh(y, win_p, color=COL["blue"], alpha=0.92, label="Improved seed")
    ax.barh(y, tie_p, left=win_p, color=COL["light"], label="Tie")
    ax.barh(y, loss_p, left=win_p + tie_p, color=COL["red"], alpha=0.86, label="Worse seed")
    for yi, w, l, t in zip(y, win.astype(int), loss.astype(int), total.astype(int)):
        ax.text(1.02, yi, f"{w}/{t} improved; {l}/{t} worse", va="center", fontsize=7.4, color=COL["muted"])
    ax.set_yticks(y, [CATEGORY_LABELS[k] for k in order])
    ax.invert_yaxis()
    ax.set_xlabel("Fraction of paired seed summaries")
    ax.set_xlim(0, 1.62)
    ax.set_xticks([0, 0.5, 1.0])
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=3)
    style_axis(ax, "x")
    panel(ax, "b")


def plot_delta_forest(ax: plt.Axes, data: pd.DataFrame, promoted: bool, label: str) -> None:
    plot = data[data["promoted"].eq(promoted)].copy()
    plot = plot.sort_values("test_delta", ascending=True).reset_index(drop=True)
    y = np.arange(len(plot))
    color = COL["blue"] if promoted else COL["grey"]
    ax.hlines(y, plot["ci_low"], plot["ci_high"], color=COL["light"], lw=1.15, zorder=1)
    ax.scatter(plot["test_delta"], y, s=18, color=color, zorder=3)
    ax.axvline(0, color=COL["ink"], lw=0.75)
    ax.set_yticks(y, [endpoint_label(v) for v in plot["endpoint"]])
    ax.tick_params(axis="y", labelsize=9.0 if promoted else 8.0)
    ax.set_xlabel("Direction-normalized test delta")
    if promoted:
        ax.set_xlim(-0.08, 1.30)
        ax.set_xticks([0, 0.25, 0.50, 0.75, 1.00, 1.25])
    else:
        ax.set_xlim(-0.08, 0.04)
        ax.set_xticks([-0.08, -0.04, 0, 0.04])
    ax.set_title(label, loc="left", pad=5)
    style_axis(ax, "x")


def main() -> None:
    setup()
    src = source_path()
    raw = pd.read_csv(src)
    data = raw[raw["endpoint"].notna()].copy()
    bool_map = {"True": True, "False": False, True: True, False: False}
    data["promoted"] = data["promoted"].map(bool_map).astype(bool)
    for col in ["test_delta", "ci_low", "ci_high", "seed_win_count", "seed_tie_count", "seed_loss_count"]:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    fig, axes = plt.subplots(
        2,
        2,
        figsize=(9.7, 7.9),
        gridspec_kw={"width_ratios": [1.02, 1.38], "height_ratios": [0.94, 1.24]},
    )

    plot_gate_counts(axes[0, 0], data)
    plot_seed_support(axes[0, 1], data)
    plot_delta_forest(axes[1, 0], data, True, "Promoted endpoint effects")
    panel(axes[1, 0], "c")
    plot_delta_forest(axes[1, 1], data, False, "Retained endpoint effects")
    panel(axes[1, 1], "d")

    handles = [
        Line2D([], [], marker="o", color="none", markerfacecolor=COL["blue"], markeredgecolor="none", label="Promoted"),
        Line2D([], [], marker="o", color="none", markerfacecolor=COL["grey"], markeredgecolor="none", label="Retained"),
        Patch(facecolor=COL["light"], edgecolor="none", label="Seed-summary CI"),
    ]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.55, -0.005), ncol=3)
    fig.tight_layout(rect=(0, 0.035, 1, 1), w_pad=2.25, h_pad=2.05)

    png = OUT / "fig07_tdc_gate_audit_4panel.png"
    svg = OUT / "fig07_tdc_gate_audit_4panel.svg"
    fig.savefig(svg, bbox_inches="tight")
    fig.savefig(png, dpi=450, bbox_inches="tight")
    plt.close(fig)
    data.to_csv(OUT / "fig07_tdc_gate_audit_4panel_source.csv", index=False)

    for path in (png, svg):
        shutil.copy2(path, DESKTOP / path.name)
    print(png)
    print(svg)


if __name__ == "__main__":
    main()
