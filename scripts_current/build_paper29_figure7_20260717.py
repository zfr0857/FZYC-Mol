from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
BASE = Path(os.environ.get(
    "FZYC_COMPOSITION_OUT", ROOT / "output" / "paper27_equal_size_registry_composition_20260716"
))
TARGET = Path(os.environ.get(
    "FZYC_PAPER29_OUT", ROOT / "output" / "paper29_figure7_table_revision_20260717"
))
OUT = TARGET / "main_figures"
SOURCE = TARGET / "figure_source_data"

COLORS = {
    "Homogeneous Morgan": "#7566A8",
    "Classical multiview": "#2D9187",
    "Modern-augmented": "#D97A2B",
}
SHORT = {
    "Homogeneous Morgan": "Morgan-only",
    "Classical multiview": "Classical multiview",
    "Modern-augmented": "Modern-augmented",
}
TASKS = ["clintox", "bace", "esol"]
TASK_LABEL = {"clintox": "ClinTox", "bace": "BACE", "esol": "ESOL"}
MARKERS = {"clintox": "o", "bace": "s", "esol": "^"}


def style() -> None:
    mpl.rcParams.update({
        "font.family": "Times New Roman",
        "font.serif": ["Times New Roman"],
        "mathtext.fontset": "custom",
        "mathtext.rm": "Times New Roman",
        "mathtext.it": "Times New Roman:italic",
        "mathtext.bf": "Times New Roman:bold",
        "axes.unicode_minus": False,
        "font.size": 9.0,
        "axes.titlesize": 10.3,
        "axes.titleweight": "bold",
        "axes.labelsize": 9.2,
        "xtick.labelsize": 8.0,
        "ytick.labelsize": 8.5,
        "legend.fontsize": 8.0,
        "axes.linewidth": 0.8,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "savefig.facecolor": "white",
        "figure.facecolor": "white",
    })


def panel_label(ax: plt.Axes, label: str, x: float = -0.14) -> None:
    ax.text(x, 1.105, label, transform=ax.transAxes, fontsize=12.0,
            fontweight="bold", va="top", ha="left")


def prepare_cells() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary = pd.read_csv(BASE / "equal_size_endpoint_summary.csv")
    diversity = pd.read_csv(BASE / "equal_size_effective_diversity.csv")
    raw = diversity.loc[diversity.transformation.eq("raw")].copy()
    cells = summary.merge(
        raw[["pool", "task", "candidate_count", "entropy_rank", "relative_entropy_rank"]],
        on=["pool", "task", "candidate_count"], how="left", validate="one_to_one",
    )
    reference = summary.loc[summary.pool.eq("Homogeneous Morgan"), [
        "task", "candidate_count", "oracle_opportunity_gain_mean"
    ]].rename(columns={"oracle_opportunity_gain_mean": "homogeneous_observed_audit_best_gain"})
    cells = cells.merge(reference, on=["task", "candidate_count"], validate="many_to_one")
    if not (cells.homogeneous_observed_audit_best_gain > 0).all():
        raise ValueError("All endpoint- and K-specific normalization denominators must be positive")
    cells["observed_audit_best_gain_normalized"] = (
        cells.oracle_opportunity_gain_mean / cells.homogeneous_observed_audit_best_gain
    )
    cells["validation_selected_gain_normalized"] = (
        cells.selected_model_gain_mean / cells.homogeneous_observed_audit_best_gain
    )
    cells["cross_fitted_gap_normalized"] = (
        cells.cross_fitted_selection_gap_mean / cells.homogeneous_observed_audit_best_gain
    )
    cells["audit_fit_minutes_mean"] = cells.audit_fit_seconds_mean / 60.0
    cells["audit_fit_minutes_low"] = cells.audit_fit_seconds_low / 60.0
    cells["audit_fit_minutes_high"] = cells.audit_fit_seconds_high / 60.0
    audit = reference.copy()
    audit["positive_denominator"] = audit.homogeneous_observed_audit_best_gain > 0
    audit["minimum_denominator_across_cells"] = audit.homogeneous_observed_audit_best_gain.min()
    return summary, cells, audit


def draw_arrow(ax: plt.Axes, q: pd.DataFrame, xcol: str, ycol: str, pool: str, task: str) -> None:
    q = q.sort_values("candidate_count")
    if q.candidate_count.tolist() != [16, 32]:
        raise ValueError(f"Expected K=16 and K=32 for {pool}, {task}")
    tail, head = q.iloc[0], q.iloc[1]
    colour = COLORS[pool]
    marker = MARKERS[task]
    ax.annotate(
        "", xy=(head[xcol], head[ycol]), xytext=(tail[xcol], tail[ycol]),
        arrowprops=dict(arrowstyle="-|>", color=colour, lw=1.15,
                        mutation_scale=9.0, shrinkA=4.5, shrinkB=4.5, alpha=.86),
        zorder=2,
    )
    ax.scatter([tail[xcol], head[xcol]], [tail[ycol], head[ycol]], marker=marker,
               s=30, facecolor=colour, edgecolor="white", linewidth=.55, zorder=3)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SOURCE.mkdir(parents=True, exist_ok=True)
    style()
    summary, cells, normalization_audit = prepare_cells()
    pool_order = list(COLORS)

    final_width_in = 170.0 / 25.4
    final_height_in = final_width_in * (3330.0 / 4500.0)
    output_dpi = 4500.0 / final_width_in
    fig = plt.figure(figsize=(final_width_in, final_height_in))
    grid = fig.add_gridspec(
        2, 2, width_ratios=[1.15, 1.0], height_ratios=[1.0, 1.05],
        left=.145, right=.985, bottom=.115, top=.94, wspace=.34, hspace=.46,
    )
    ax_a = fig.add_subplot(grid[0, 0])
    ax_b = fig.add_subplot(grid[0, 1])
    ax_c = fig.add_subplot(grid[1, 0])
    ax_d = fig.add_subplot(grid[1, 1])

    # A: K=32 grouped horizontal dumbbells.
    k32 = cells.loc[cells.candidate_count.eq(32)].copy()
    y_positions = [8.0, 7.0, 6.0, 4.4, 3.4, 2.4, .8, -.2, -1.2]
    rows = [(pool, task) for pool in pool_order for task in TASKS]
    for y, (pool, task) in zip(y_positions, rows):
        row = k32.loc[k32.pool.eq(pool) & k32.task.eq(task)].iloc[0]
        selected = row.validation_selected_gain_normalized
        best = row.observed_audit_best_gain_normalized
        ax_a.plot([selected, best], [y, y], color=COLORS[pool], lw=1.25, alpha=.78, zorder=1)
        ax_a.scatter(best, y, s=35, facecolor="white", edgecolor=COLORS[pool],
                     marker="o", linewidth=1.25, zorder=3)
        ax_a.scatter(selected, y, s=35, facecolor=COLORS[pool], edgecolor="white",
                     marker="o", linewidth=.55, zorder=3)
    ax_a.set_yticks(y_positions, [TASK_LABEL[task] for _, task in rows])
    ax_a.tick_params(axis="y", pad=4)
    for sep in (5.2, 1.6):
        ax_a.axhline(sep, color="#D5D9DD", lw=.75, zorder=0)
    for y, pool in zip((8.72, 5.12, 1.52), pool_order):
        ax_a.text(.01, y, SHORT[pool], transform=ax_a.get_yaxis_transform(),
                  ha="left", va="bottom", fontsize=9.0, fontweight="bold", color=COLORS[pool])
    ax_a.set_ylim(-1.65, 9.25)
    ax_a.set_xlabel("Normalized gain")
    ax_a.set_title("Observed opportunity and realised gain", loc="left", pad=7)
    estimate_handles = [
        Line2D([0], [0], marker="o", ls="", mfc="white", mec="#4B5563",
               mew=1.1, label="Observed audit-best"),
        Line2D([0], [0], marker="o", ls="", mfc="#4B5563", mec="white",
               mew=.5, label="Validation-selected"),
    ]
    ax_a.legend(handles=estimate_handles, frameon=False, loc="lower right", ncol=1,
                handletextpad=.35, borderpad=.15, labelspacing=.25)
    panel_label(ax_a, "A")

    # B: direction arrows from K=16 to K=32.
    for pool in pool_order:
        for task in TASKS:
            q = cells.loc[cells.pool.eq(pool) & cells.task.eq(task)]
            draw_arrow(ax_b, q, "relative_entropy_rank", "cross_fitted_gap_normalized", pool, task)
    ax_b.axhline(0, color="#AEB4BB", lw=.9, ls="--", zorder=0)
    ax_b.set_xlabel(r"Relative entropy rank, $r_{\mathrm{entropy}}/K$", fontsize=10.8)
    ax_b.set_ylabel("Normalized cross-fitted gap")
    ax_b.set_title("Diversity and cross-fitted gap", loc="left", pad=7)
    compact_handles = [
        Line2D([0], [0], marker=MARKERS[t], color="#4B5563", lw=0,
               markerfacecolor="#4B5563", markersize=5.3, label=TASK_LABEL[t]) for t in TASKS
    ] + [
        Line2D([0, 1], [0, 0], color="#4B5563", lw=1.0, marker=">",
               markevery=[1], markersize=5.5, label="Arrow: K = 16 → 32")
    ]
    panel_label(ax_b, "B")

    # C: one compact axis with a narrow in-panel registry strip.
    matrix_rows = [(pool, task) for pool in pool_order for task in TASKS]
    heat = np.asarray([
        [summary.loc[
            summary.pool.eq(pool) & summary.task.eq(task) & summary.candidate_count.eq(k),
            "chance_adjusted_hit3_mean",
        ].iloc[0] for k in (16, 32)]
        for pool, task in matrix_rows
    ])
    norm = TwoSlopeNorm(vmin=-1.0, vcenter=0.0, vmax=1.0)
    image = ax_c.imshow(heat, cmap="RdBu", norm=norm, aspect="auto", extent=(.75, 2.65, 8.5, -.5))
    ax_c.set_xlim(-.55, 2.68)
    ax_c.set_ylim(8.5, -.5)
    ax_c.set_xticks([1.225, 2.175], ["K = 16", "K = 32"])
    ax_c.set_yticks([])
    c_group_labels = {
        "Homogeneous Morgan": "Morgan-\nonly",
        "Classical multiview": "Classical\nmultiview",
        "Modern-augmented": "Modern-\naugmented",
    }
    for start, pool in zip((-.5, 2.5, 5.5), pool_order):
        ax_c.add_patch(plt.Rectangle((-.53, start), .58, 3.0,
                       facecolor=mpl.colors.to_rgba(COLORS[pool], .10),
                       edgecolor="#D5D9DD", linewidth=.55, clip_on=False))
        ax_c.text(-.24, start + 1.5, c_group_labels[pool], ha="center", va="center",
                  fontsize=8.2, fontweight="bold", color="#30373D", linespacing=.90)
    for i, (_, task) in enumerate(matrix_rows):
        ax_c.text(.70, i, TASK_LABEL[task], ha="right", va="center", fontsize=8.5, color="#30373D")
    for sep in (2.5, 5.5):
        ax_c.axhline(sep, color="white", lw=1.45)
        ax_c.axhline(sep, color="#BFC5CA", lw=.55)
    for i in range(heat.shape[0]):
        for j in range(heat.shape[1]):
            rgba = image.cmap(image.norm(heat[i, j]))
            luminance = .2126 * rgba[0] + .7152 * rgba[1] + .0722 * rgba[2]
            ax_c.text(1.225 + j * .95, i, f"{heat[i, j]:.2f}", ha="center", va="center", fontsize=8.2,
                      color="white" if luminance < .50 else "#26313A")
    cbar = fig.colorbar(image, ax=ax_c, fraction=.050, pad=.025)
    cbar.ax.set_title("CAHit@3", fontsize=8.5, fontweight="bold", pad=4)
    cbar.ax.tick_params(labelsize=8.0)
    ax_c.set_title("Chance-adjusted Hit@3", loc="left", pad=7)
    panel_label(ax_c, "C")

    # D: minutes and the same directional encoding as B.
    for pool in pool_order:
        for task in TASKS:
            q = cells.loc[cells.pool.eq(pool) & cells.task.eq(task)]
            draw_arrow(ax_d, q, "audit_fit_minutes_mean", "validation_selected_gain_normalized", pool, task)
    ax_d.axhline(0, color="#AEB4BB", lw=.9, ls="--", zorder=0)
    ax_d.set_xlabel("Mean downstream audit time per outer unit (min)")
    ax_d.set_ylabel("Normalized selected gain")
    ax_d.set_title("Downstream cost–benefit", loc="left", pad=16)
    ax_d.text(1.0, 1.015, "Downstream fitting only", transform=ax_d.transAxes,
              ha="right", va="bottom", fontsize=8.0, fontweight="bold", color="#59616A")
    ax_d.legend(handles=compact_handles, frameon=False, loc="lower left", ncol=1,
                fontsize=7.5, handletextpad=.35, borderpad=.1, labelspacing=.18)
    panel_label(ax_d, "D")

    for ax in (ax_a, ax_b, ax_d):
        ax.spines[["top", "right"]].set_visible(False)
        ax.margins(x=.08)

    stem = OUT / "Figure_7_equal_size_candidate_pool_composition_intervention"
    fig.savefig(stem.with_suffix(".pdf"), bbox_inches=None, facecolor="white")
    fig.savefig(stem.with_suffix(".svg"), bbox_inches=None, facecolor="white")
    png_path = stem.with_name(stem.name + "_600dpi.png")
    fig.savefig(png_path, dpi=output_dpi, bbox_inches=None, facecolor="white",
                pil_kwargs={"compress_level": 9})
    plt.close(fig)
    with Image.open(png_path) as image:
        if image.mode != "RGB":
            rgb = Image.new("RGB", image.size, "white")
            if image.mode == "RGBA":
                rgb.paste(image, mask=image.getchannel("A"))
            else:
                rgb.paste(image.convert("RGB"))
            rgb.save(png_path, format="PNG", compress_level=9)

    for suffix in (".pdf", ".svg"):
        shutil.copy2(stem.with_suffix(suffix), OUT / f"Figure7{suffix}")
    shutil.copy2(png_path, OUT / "Figure7_600dpi.png")

    public_cells = cells.rename(columns={
        "oracle_opportunity_gain_mean": "observed_audit_best_opportunity_gain_mean",
        "oracle_opportunity_gain_low": "observed_audit_best_opportunity_gain_low",
        "oracle_opportunity_gain_high": "observed_audit_best_opportunity_gain_high",
    })
    public_cells = public_cells.drop(columns=[c for c in public_cells if "oracle" in c.lower()])
    public_cells.loc[public_cells.candidate_count.eq(32)].to_csv(
        SOURCE / "Figure_7A_K32_dumbbell_source.csv", index=False
    )
    public_cells.to_csv(SOURCE / "Figure_7B_D_arrow_source.csv", index=False)
    pd.DataFrame(
        heat,
        index=[f"{SHORT[p]}|{TASK_LABEL[t]}" for p, t in matrix_rows],
        columns=["K = 16", "K = 32"],
    ).to_csv(SOURCE / "Figure_7C_grouped_heatmap_source.csv")
    normalization_audit.to_csv(SOURCE / "Figure_7_normalization_denominator_audit.csv", index=False)
    pd.DataFrame([
        *({"encoding": "registry colour", "level": SHORT[p], "value": c} for p, c in COLORS.items()),
        *({"encoding": "endpoint marker", "level": TASK_LABEL[t], "value": MARKERS[t]} for t in TASKS),
        {"encoding": "candidate count", "level": "K = 16", "value": "arrow tail"},
        {"encoding": "candidate count", "level": "K = 32", "value": "arrow head"},
        {"encoding": "Panel A estimate", "level": "Observed audit-best", "value": "open circle"},
        {"encoding": "Panel A estimate", "level": "Validation-selected", "value": "filled circle"},
    ]).to_csv(SOURCE / "Figure_7_visual_encoding_guide.csv", index=False)
    audit = {
        "panel_a_candidate_count": 32,
        "normalization": "Endpoint- and K-specific homogeneous-pool observed audit-best opportunity gain",
        "minimum_denominator": float(normalization_audit.homogeneous_observed_audit_best_gain.min()),
        "all_denominators_positive": bool(normalization_audit.positive_denominator.all()),
        "relative_entropy_rank_definition": "raw Ledoit-Wolf entropy effective rank divided by nominal K",
        "direction_encoding": "arrow tail K=16 to arrow head K=32 in panels B and D",
        "time_conversion": "audit_fit_minutes_mean = audit_fit_seconds_mean / 60",
        "cost_scope": "observed downstream nested fitting and prediction only; excludes encoder pretraining, model acquisition, and cached embedding extraction",
        "heatmap_colour_range": [-1.0, 1.0],
    }
    (SOURCE / "Figure_7_definition_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(stem)


if __name__ == "__main__":
    main()
