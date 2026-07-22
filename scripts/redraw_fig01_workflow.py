from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.lines import Line2D
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "\u5c0f\u8bba\u6587-13_\u56fe1\u91cd\u7ed8"
OUT.mkdir(parents=True, exist_ok=True)


COLORS = {
    "ink": "#172033",
    "muted": "#5E687C",
    "line": "#C7CDD7",
    "protocol": "#8066A8",
    "registry": "#2E6FAE",
    "selection": "#3D9A6B",
    "audit": "#D88934",
    "boundary": "#2F8D94",
    "stop": "#C53F3F",
    "bg": "#FFFFFF",
    "soft": "#F7F9FC",
}


def box(ax, xy, wh, title, body, color, fill="#FFFFFF", dashed=False, title_size=10.6):
    x, y = xy
    w, h = wh
    rect = patches.FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.018,rounding_size=0.035",
        linewidth=2.0,
        edgecolor=color,
        facecolor=fill,
        linestyle="--" if dashed else "-",
        zorder=2,
    )
    ax.add_patch(rect)
    ax.text(
        x + 0.03,
        y + h - 0.035,
        title,
        ha="left",
        va="top",
        fontsize=title_size,
        fontweight="bold",
        color=COLORS["ink"],
        zorder=3,
    )
    ax.text(
        x + 0.03,
        y + h - 0.082,
        body,
        ha="left",
        va="top",
        fontsize=7.35,
        color=COLORS["muted"],
        linespacing=1.16,
        zorder=3,
    )
    return rect


def header(ax, x, y, letter, title, color):
    ax.text(
        x,
        y,
        letter,
        fontsize=10,
        fontweight="bold",
        color="white",
        ha="center",
        va="center",
        bbox=dict(boxstyle="circle,pad=0.30", facecolor=color, edgecolor=color),
        zorder=5,
    )
    ax.text(
        x + 0.05,
        y,
        title,
        fontsize=13,
        fontweight="bold",
        color=COLORS["ink"],
        ha="left",
        va="center",
        zorder=5,
    )


def arrow(ax, start, end, color="#4F6F9F", lw=2.2, style="-", rad=0.0, text=None, text_offset=(0, 0)):
    arr = patches.FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=14,
        linewidth=lw,
        color=color,
        linestyle=style,
        connectionstyle=f"arc3,rad={rad}",
        zorder=4,
    )
    ax.add_patch(arr)
    if text:
        mx = (start[0] + end[0]) / 2 + text_offset[0]
        my = (start[1] + end[1]) / 2 + text_offset[1]
        ax.text(mx, my, text, fontsize=8.3, color=color, ha="center", va="center", zorder=5)
    return arr


def pill(ax, x, y, text, color):
    ax.text(
        x,
        y,
        text,
        ha="center",
        va="center",
        fontsize=8.2,
        color=COLORS["ink"],
        bbox=dict(
            boxstyle="round,pad=0.30,rounding_size=0.18",
            facecolor="#FFFFFF",
            edgecolor=color,
            linewidth=1.3,
        ),
        zorder=5,
    )


def main():
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    fig, ax = plt.subplots(figsize=(16.4, 8.8), dpi=300)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(COLORS["bg"])
    ax.set_facecolor(COLORS["bg"])

    ax.text(
        0.035,
        0.955,
        "FZYC-Mol workflow for frozen model selection and audit",
        fontsize=22,
        fontweight="bold",
        color=COLORS["ink"],
        ha="left",
        va="top",
    )
    ax.text(
        0.035,
        0.915,
        "Registered candidates, nested validation, locked outer labels, reliability and chemical-boundary evidence",
        fontsize=11.5,
        color=COLORS["muted"],
        ha="left",
        va="top",
    )

    # Column positions
    xs = [0.035, 0.225, 0.415, 0.605, 0.795]
    w = 0.165
    col_y = 0.245
    col_h = 0.565
    row_y = [0.615, 0.440, 0.265]
    box_h = 0.145

    # Column containers stay below the title block to keep the workflow readable.
    for x, c in zip(xs, ["protocol", "registry", "selection", "audit", "boundary"]):
        rect = patches.FancyBboxPatch(
            (x - 0.01, col_y - 0.01),
            w + 0.02,
            col_h,
            boxstyle="round,pad=0.02,rounding_size=0.025",
            facecolor="#FFFFFF",
            edgecolor=COLORS[c],
            linewidth=1.9,
            zorder=1,
        )
        ax.add_patch(rect)

    header(ax, xs[0] + 0.005, 0.805, "a", "Task protocol", COLORS["protocol"])
    header(ax, xs[1] + 0.005, 0.805, "b", "Candidate registry", COLORS["registry"])
    header(ax, xs[2] + 0.005, 0.805, "c", "Frozen selection", COLORS["selection"])
    header(ax, xs[3] + 0.005, 0.805, "d", "Outer audit", COLORS["audit"])
    header(ax, xs[4] + 0.005, 0.805, "e", "Evidence outputs", COLORS["boundary"])

    box(
        ax,
        (xs[0] + 0.015, row_y[0]),
        (w - 0.03, box_h),
        "Pre-specified tasks",
        "MoleculeNet main panel\nTDC gate panel\nMoleculeACE and bRo5 boundary",
        COLORS["protocol"],
        fill="#F8F5FC",
    )
    box(
        ax,
        (xs[0] + 0.015, row_y[1]),
        (w - 0.03, box_h),
        "Frozen design",
        "Endpoint, metric, split,\nseed and cleaning rule fixed\nbefore model comparison",
        COLORS["protocol"],
        fill="#F8F5FC",
    )
    box(
        ax,
        (xs[0] + 0.015, row_y[2]),
        (w - 0.03, box_h),
        "Leakage controls",
        "Train-fold fitting only\nouter labels locked\nhashes for data and splits",
        COLORS["protocol"],
        fill="#F8F5FC",
    )

    box(
        ax,
        (xs[1] + 0.015, row_y[0]),
        (w - 0.03, box_h),
        "Registered fields",
        "candidate_id, family,\nrepresentation, status,\nregistry_order, config_hash",
        COLORS["registry"],
        fill="#F4F8FD",
    )
    box(
        ax,
        (xs[1] + 0.015, row_y[1]),
        (w - 0.03, box_h),
        "Confirmatory pools",
        "K=4 to 32 lightweight pool\n12-candidate multiview pool\n3-endpoint strong-baseline panel",
        COLORS["registry"],
        fill="#F4F8FD",
    )
    box(
        ax,
        (xs[1] + 0.015, row_y[2]),
        (w - 0.03, box_h),
        "All states logged",
        "eligible, rejected, failed,\nmissing-data and runtime-unavailable\nnegative results retained",
        COLORS["registry"],
        fill="#F4F8FD",
    )

    box(
        ax,
        (xs[2] + 0.015, row_y[0]),
        (w - 0.03, box_h),
        "Nested validation",
        "5 seeds x 3 outer folds\nx 3 inner folds\ntrain-only preprocessing",
        COLORS["selection"],
        fill="#F4FBF7",
    )
    box(
        ax,
        (xs[2] + 0.015, row_y[1]),
        (w - 0.03, box_h),
        "Inner-fold ranking",
        "validation-best\none-SE stable\nrisk-adjusted ranking",
        COLORS["selection"],
        fill="#F4FBF7",
    )
    box(
        ax,
        (xs[2] + 0.015, row_y[2]),
        (w - 0.03, box_h),
        "Rule freeze",
        "selected candidate and policy\nlocked before outer labels\nare read",
        COLORS["selection"],
        fill="#F4FBF7",
    )

    box(
        ax,
        (xs[3] + 0.015, row_y[0]),
        (w - 0.03, box_h),
        "Outer assessment",
        "test utility and oracle\nselection loss / regret\nranking fidelity",
        COLORS["audit"],
        fill="#FFF7EF",
    )
    box(
        ax,
        (xs[3] + 0.015, row_y[1]),
        (w - 0.03, box_h),
        "Paired inference",
        "endpoint-cluster intervals\nsign tests and Holm control\nrealized vs attainable gain",
        COLORS["audit"],
        fill="#FFF7EF",
    )
    box(
        ax,
        (xs[3] + 0.015, row_y[2]),
        (w - 0.03, box_h),
        "No feedback loop",
        "outer labels audit only\nno candidate replacement\nno threshold revision",
        COLORS["audit"],
        fill="#FFF7EF",
    )

    box(
        ax,
        (xs[4] + 0.015, row_y[0]),
        (w - 0.03, box_h),
        "Endpoint evidence",
        "selection decision card\nsource data and hashes\ncandidate and runtime logs",
        COLORS["boundary"],
        fill="#F2FBFC",
    )
    box(
        ax,
        (xs[4] + 0.015, row_y[1]),
        (w - 0.03, box_h),
        "Sample reliability",
        "risk curves, E-AURC\nsplit conformal sets / intervals\nerror-overlap by candidate",
        COLORS["boundary"],
        fill="#F2FBFC",
    )
    box(
        ax,
        (xs[4] + 0.015, row_y[2]),
        (w - 0.03, box_h),
        "Chemical boundary",
        "TDC gate, duplicate sensitivity\nMoleculeACE activity cliffs\nbRo5 and Tanimoto bins",
        COLORS["boundary"],
        fill="#F2FBFC",
    )

    # Main arrows
    y_main = 0.575
    for i in range(4):
        arrow(ax, (xs[i] + w + 0.005, y_main), (xs[i + 1] - 0.015, y_main), color="#486AA6")

    # Stop feedback loop
    arrow(
        ax,
        (xs[3] + 0.115, 0.858),
        (xs[2] + 0.085, 0.858),
        color=COLORS["stop"],
        lw=2.0,
        style="--",
        rad=0.0,
        text="outer labels do not return to selection",
        text_offset=(0.0, -0.030),
    )
    ax.plot([0.583, 0.597], [0.873, 0.843], color=COLORS["stop"], lw=2.4, zorder=6)
    ax.plot([0.597, 0.583], [0.873, 0.843], color=COLORS["stop"], lw=2.4, zorder=6)

    # Evidence tier band
    band = patches.FancyBboxPatch(
        (0.08, 0.07),
        0.84,
        0.13,
        boxstyle="round,pad=0.02,rounding_size=0.025",
        facecolor="#FAFBFD",
        edgecolor="#AEB7C5",
        linewidth=1.4,
        zorder=1,
    )
    ax.add_patch(band)
    ax.text(
        0.105,
        0.175,
        "Evidence hierarchy",
        fontsize=12,
        fontweight="bold",
        color=COLORS["ink"],
        ha="left",
        va="center",
    )
    pill(ax, 0.235, 0.120, "Confirmatory\nK-expansion", COLORS["selection"])
    pill(ax, 0.365, 0.120, "Confirmatory\nmultiview gain", COLORS["selection"])
    pill(ax, 0.510, 0.120, "Representative\nstrong baselines", COLORS["registry"])
    pill(ax, 0.655, 0.120, "Reliability and\nchemical boundary", COLORS["boundary"])
    pill(ax, 0.800, 0.120, "Negative results\nand audit trail", COLORS["audit"])

    # Small legend
    legend_items = [
        Line2D([0], [0], color="#486AA6", lw=2.2, label="allowed information flow"),
        Line2D([0], [0], color=COLORS["stop"], lw=2.2, linestyle="--", label="blocked test feedback"),
    ]
    ax.legend(
        handles=legend_items,
        loc="upper right",
        bbox_to_anchor=(0.965, 0.875),
        frameon=False,
        fontsize=8.5,
        handlelength=2.8,
    )

    fig.tight_layout(pad=0.2)
    for ext in ["png", "svg", "pdf", "tiff"]:
        fig.savefig(OUT / f"fig01_fzyc_mol_redrawn.{ext}", dpi=600 if ext in {"png", "tiff"} else None)
    plt.close(fig)

    nodes = [
        ("a", "Task protocol", "Pre-specified tasks; frozen design; leakage controls"),
        ("b", "Candidate registry", "Registered fields; confirmatory pools; all states logged"),
        ("c", "Frozen selection", "Nested validation; inner-fold ranking; rule freeze"),
        ("d", "Outer audit", "Outer assessment; paired inference; no feedback loop"),
        ("e", "Evidence outputs", "Endpoint evidence; sample reliability; chemical boundary"),
        ("f", "Evidence hierarchy", "Confirmatory core, representative baselines, boundary evidence and negative results"),
    ]
    pd.DataFrame(nodes, columns=["panel", "module", "content"]).to_csv(
        OUT / "fig01_redrawn_nodes.csv", index=False
    )
    edges = [
        ("Task protocol", "Candidate registry", "feeds"),
        ("Candidate registry", "Frozen selection", "feeds"),
        ("Frozen selection", "Outer audit", "freezes before"),
        ("Outer audit", "Evidence outputs", "emits"),
        ("Outer audit", "Frozen selection", "blocked feedback"),
    ]
    pd.DataFrame(edges, columns=["source", "target", "relationship"]).to_csv(
        OUT / "fig01_redrawn_edges.csv", index=False
    )
    print(OUT)


if __name__ == "__main__":
    main()
