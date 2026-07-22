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
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
BASE = Path(os.environ.get(
    "FZYC_COMPOSITION_OUT", ROOT / "output" / "paper27_equal_size_registry_composition_20260716"
))
TARGET = Path(os.environ.get(
    "FZYC_PAPER30_OUT", ROOT / "output" / "paper30_final_minor_revision_20260717"
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
    "Modern-augmented": "Modern augmented",
}
SHORT_C = {
    "Homogeneous Morgan": "Morgan-only",
    "Classical multiview": "Classical MV",
    "Modern-augmented": "Modern augmented",
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
        "font.size": 9.0,
        "axes.titlesize": 10.0,
        "axes.titleweight": "bold",
        "axes.labelsize": 9.0,
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
        raise ValueError("All normalization denominators must be positive")
    cells["observed_audit_best_gain_normalized"] = (
        cells.oracle_opportunity_gain_mean / cells.homogeneous_observed_audit_best_gain
    )
    cells["validation_selected_gain_normalized"] = (
        cells.selected_model_gain_mean / cells.homogeneous_observed_audit_best_gain
    )
    cells["cross_fitted_gap_normalized"] = (
        cells.cross_fitted_selection_gap_mean / cells.homogeneous_observed_audit_best_gain
    )
    for suffix in ("mean", "low", "high"):
        cells[f"audit_fit_minutes_{suffix}"] = cells[f"audit_fit_seconds_{suffix}"] / 60.0
    audit = reference.copy()
    audit["positive_denominator"] = audit.homogeneous_observed_audit_best_gain > 0
    audit["minimum_denominator_across_cells"] = audit.homogeneous_observed_audit_best_gain.min()
    return summary, cells, audit


def panel_letter(fig: plt.Figure, ax: plt.Axes, label: str, dx: float = -0.030, dy: float = 0.018) -> None:
    box = ax.get_position()
    fig.text(box.x0 + dx, box.y1 + dy, label, fontsize=12.0, fontweight="bold",
             ha="left", va="top")


def draw_arrow(ax: plt.Axes, q: pd.DataFrame, xcol: str, ycol: str,
               pool: str, task: str, *, endpoint_shape: bool = True) -> None:
    q = q.sort_values("candidate_count")
    if q.candidate_count.tolist() != [16, 32]:
        raise ValueError(f"Expected K=16 and K=32 for {pool}, {task}")
    tail, head = q.iloc[0], q.iloc[1]
    colour = COLORS[pool]
    marker = MARKERS[task] if endpoint_shape else "o"
    ax.annotate(
        "", xy=(head[xcol], head[ycol]), xytext=(tail[xcol], tail[ycol]),
        arrowprops=dict(arrowstyle="-|>", color=colour, lw=1.2,
                        mutation_scale=8.5, shrinkA=4.2, shrinkB=4.2, alpha=.92),
        zorder=2,
    )
    ax.scatter([tail[xcol]], [tail[ycol]], marker=marker, s=28, facecolor="white",
               edgecolor=colour, linewidth=1.0, zorder=3)
    ax.scatter([head[xcol]], [head[ycol]], marker=marker, s=30, facecolor=colour,
               edgecolor="white", linewidth=.55, zorder=4)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SOURCE.mkdir(parents=True, exist_ok=True)
    style()
    summary, cells, normalization_audit = prepare_cells()
    pools = list(COLORS)

    width_in = 170.0 / 25.4
    height_in = width_in * (3400.0 / 4500.0)
    dpi = 4500.0 / width_in
    fig = plt.figure(figsize=(width_in, height_in))
    outer = fig.add_gridspec(2, 1, left=.125, right=.982, bottom=.105, top=.810,
                             height_ratios=[1.0, 1.08], hspace=.48)
    top = outer[0].subgridspec(1, 2, width_ratios=[1.0, 1.0], wspace=.30)
    bottom = outer[1].subgridspec(1, 2, width_ratios=[.46, .54], wspace=.39)
    ax_a = fig.add_subplot(top[0, 0])
    b_grid = top[0, 1].subgridspec(1, 3, wspace=.13)
    b_axes = [fig.add_subplot(b_grid[0, i]) for i in range(3)]
    ax_c = fig.add_subplot(bottom[0, 0])
    ax_d = fig.add_subplot(bottom[0, 1])

    pool_handles = [Line2D([0, 1], [0, 0], color=COLORS[p], lw=2.6, label=SHORT[p]) for p in pools]
    endpoint_handles = [
        Line2D([0], [0], marker=MARKERS[t], color="#3E4851", lw=0,
               markerfacecolor="#3E4851", markersize=5.2, label=TASK_LABEL[t]) for t in TASKS
    ]
    endpoint_handles.append(Line2D([0, 1], [0, 0], color="#3E4851", lw=1.0,
                                   marker=">", markevery=[1], markersize=5.0,
                                   label="K = 16 → K = 32"))
    leg1 = fig.legend(handles=pool_handles, frameon=False, ncol=3, loc="upper center",
                      bbox_to_anchor=(.50, .982), handlelength=1.8, columnspacing=1.35,
                      handletextpad=.45, borderaxespad=0)
    fig.add_artist(leg1)
    fig.legend(handles=endpoint_handles, frameon=False, ncol=4, loc="upper right",
               bbox_to_anchor=(.983, .925), handlelength=1.4, columnspacing=.82,
               handletextpad=.35, borderaxespad=0)

    # A — K=32 only, with quiet group headings and an unobstructed estimate legend.
    k32 = cells.loc[cells.candidate_count.eq(32)].copy()
    y_data = [9.0, 8.0, 7.0, 5.3, 4.3, 3.3, 1.6, .6, -.4]
    rows = [(p, t) for p in pools for t in TASKS]
    for y, (pool, task) in zip(y_data, rows):
        row = k32.loc[k32.pool.eq(pool) & k32.task.eq(task)].iloc[0]
        selected = row.validation_selected_gain_normalized
        observed = row.observed_audit_best_gain_normalized
        ax_a.plot([selected, observed], [y, y], color=COLORS[pool], lw=1.25, alpha=.82, zorder=1)
        ax_a.scatter(observed, y, s=33, facecolor="white", edgecolor=COLORS[pool],
                     linewidth=1.25, zorder=3)
        ax_a.scatter(selected, y, s=33, facecolor=COLORS[pool], edgecolor="white",
                     linewidth=.55, zorder=4)
    ax_a.set_yticks(y_data, [TASK_LABEL[t] for _, t in rows])
    ax_a.tick_params(axis="y", pad=3)
    for sep in (6.25, 2.25):
        ax_a.plot([-.02, 1.02], [sep, sep], transform=ax_a.get_yaxis_transform(),
                  color="#D5D9DD", lw=.70, clip_on=False, zorder=0)
    for y, pool in zip((9.78, 6.08, 2.08), pools):
        ax_a.plot([.01, .055], [y, y], transform=ax_a.get_yaxis_transform(),
                  color=COLORS[pool], lw=2.8, solid_capstyle="round", clip_on=False)
        ax_a.text(.070, y, SHORT_C[pool], transform=ax_a.get_yaxis_transform(),
                  ha="left", va="center", fontsize=9.0, fontweight="bold", color="#30373D")
    ax_a.set_ylim(-.85, 10.2)
    xmin = min(k32.validation_selected_gain_normalized.min(), k32.observed_audit_best_gain_normalized.min())
    xmax = max(k32.validation_selected_gain_normalized.max(), k32.observed_audit_best_gain_normalized.max())
    span = xmax - xmin
    ax_a.set_xlim(max(0, xmin - .12 * span), xmax + .12 * span)
    ax_a.set_xlabel("Normalized gain")
    ax_a.set_title("Opportunity and realised gain", loc="left", pad=7)
    estimate = [
        Line2D([0], [0], marker="o", ls="", mfc="white", mec="#4B5563", mew=1.1,
               markersize=5.2, label="Open: observed audit-best"),
        Line2D([0], [0], marker="o", ls="", mfc="#4B5563", mec="white", mew=.5,
               markersize=5.2, label="Filled: validation-selected"),
    ]
    fig.legend(handles=estimate, frameon=False, loc="upper left", bbox_to_anchor=(.122, .930),
               ncol=1, handletextpad=.3, labelspacing=.22, borderaxespad=0)

    # B — one endpoint per facet, so trajectories cannot cross endpoints.
    xlim = (0.04, 0.67)
    ylim = (-0.055, 0.112)
    for i, (ax, task) in enumerate(zip(b_axes, TASKS)):
        for pool in pools:
            q = cells.loc[cells.pool.eq(pool) & cells.task.eq(task)]
            draw_arrow(ax, q, "relative_entropy_rank", "cross_fitted_gap_normalized",
                       pool, task, endpoint_shape=False)
        ax.axhline(0, color="#AEB4BB", lw=.8, ls="--", zorder=0)
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)
        ax.set_title(TASK_LABEL[task], fontsize=9.0, fontweight="bold", pad=5)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(axis="x", labelsize=7.7, pad=2)
        if i:
            ax.tick_params(axis="y", labelleft=False, left=False)
            ax.spines["left"].set_visible(False)
        else:
            ax.set_ylabel("Normalized cross-fitted gap", fontsize=9.0, labelpad=4)
    mid_b = b_axes[1].get_position()
    fig.text((b_axes[0].get_position().x0 + b_axes[-1].get_position().x1) / 2,
             mid_b.y0 - .072, "Relative entropy rank, rₑₙₜᵣₒₚᵧ/K",
             ha="center", va="top", fontsize=9.0)
    fig.text(b_axes[0].get_position().x0, b_axes[0].get_position().y1 + .030,
             "Diversity and cross-fitted gap", fontsize=10.0, fontweight="bold",
             ha="left", va="bottom")

    # C — group headings span both K columns; there is no separate pool-name column.
    norm = TwoSlopeNorm(vmin=-1.0, vcenter=0.0, vmax=1.0)
    cmap = mpl.colormaps["RdBu"]
    heat_rows = []
    for pool in pools:
        values = np.asarray([
            [summary.loc[summary.pool.eq(pool) & summary.task.eq(task) &
                         summary.candidate_count.eq(k), "chance_adjusted_hit3_mean"].iloc[0]
             for k in (16, 32)] for task in TASKS
        ])
        heat_rows.extend([(pool, task, values[j]) for j, task in enumerate(TASKS)])
    for gi, pool in enumerate(pools):
        base_y = gi * 4
        ax_c.plot([.05, .28], [base_y + .36, base_y + .36], color=COLORS[pool], lw=2.8,
                  solid_capstyle="round")
        ax_c.text(.36, base_y + .36, SHORT_C[pool], ha="left", va="center",
                  fontsize=9.0, fontweight="bold", color="#30373D")
        for ti, task in enumerate(TASKS):
            y = base_y + 1 + ti
            row = next(v for p, t, v in heat_rows if p == pool and t == task)
            ax_c.text(-.10, y + .5, TASK_LABEL[task], ha="right", va="center", fontsize=8.5)
            for j, value in enumerate(row):
                rgba = cmap(norm(value))
                ax_c.add_patch(Rectangle((j, y), 1, 1, facecolor=rgba,
                                         edgecolor="white", linewidth=.8))
                lum = .2126 * rgba[0] + .7152 * rgba[1] + .0722 * rgba[2]
                ax_c.text(j + .5, y + .5, f"{value:.2f}", ha="center", va="center",
                          fontsize=8.2, color="white" if lum < .49 else "#26313A")
        if gi < 2:
            ax_c.axhline(base_y + 4, color="#C9CED3", lw=.65)
    ax_c.set_xlim(-.58, 2.0)
    ax_c.set_ylim(12.05, -.15)
    ax_c.set_xticks([.5, 1.5], ["K = 16", "K = 32"])
    ax_c.xaxis.tick_top()
    ax_c.tick_params(axis="x", length=0, pad=4)
    ax_c.set_yticks([])
    ax_c.set_title("Ranking fidelity", loc="left", pad=7)
    for spine in ax_c.spines.values():
        spine.set_visible(False)
    sm = mpl.cm.ScalarMappable(norm=norm, cmap=cmap)
    cbar = fig.colorbar(sm, ax=ax_c, fraction=.050, pad=.028)
    cbar.ax.set_title("CAHit@3", fontsize=8.5, fontweight="bold", pad=4)
    cbar.ax.tick_params(labelsize=8.0)

    # D — extra horizontal allocation and a shortened, fully visible x-axis title.
    for pool in pools:
        for task in TASKS:
            q = cells.loc[cells.pool.eq(pool) & cells.task.eq(task)]
            draw_arrow(ax_d, q, "audit_fit_minutes_mean", "validation_selected_gain_normalized",
                       pool, task, endpoint_shape=True)
    ax_d.axhline(0, color="#AEB4BB", lw=.8, ls="--", zorder=0)
    max_x = cells.audit_fit_minutes_mean.max()
    ax_d.set_xlim(0, max_x * 1.12)
    max_y = cells.validation_selected_gain_normalized.max()
    ax_d.set_ylim(-.04, max_y * 1.13)
    ax_d.set_xlabel("Downstream audit time per outer unit (min)", labelpad=5)
    ax_d.set_ylabel("Normalized selected gain", labelpad=5)
    ax_d.set_title("Cost–benefit", loc="left", pad=7)
    ax_d.text(.99, 1.018, "Downstream fitting only", transform=ax_d.transAxes,
              ha="right", va="bottom", fontsize=8.0, color="#646B72")
    ax_d.spines[["top", "right"]].set_visible(False)
    ax_d.margins(x=.03)

    ax_a.spines[["top", "right"]].set_visible(False)
    panel_letter(fig, ax_a, "A")
    panel_letter(fig, b_axes[0], "B")
    panel_letter(fig, ax_c, "C")
    panel_letter(fig, ax_d, "D")

    stem = OUT / "Figure_7_equal_size_candidate_pool_composition_intervention"
    fig.savefig(stem.with_suffix(".pdf"), bbox_inches=None, facecolor="white")
    fig.savefig(stem.with_suffix(".svg"), bbox_inches=None, facecolor="white")
    png_path = stem.with_name(stem.name + "_600dpi.png")
    fig.savefig(png_path, dpi=dpi, bbox_inches=None, facecolor="white",
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

    public = cells.rename(columns={
        "oracle_opportunity_gain_mean": "observed_audit_best_opportunity_gain_mean",
        "oracle_opportunity_gain_low": "observed_audit_best_opportunity_gain_low",
        "oracle_opportunity_gain_high": "observed_audit_best_opportunity_gain_high",
    })
    public = public.drop(columns=[c for c in public if "oracle" in c.lower()])
    public.loc[public.candidate_count.eq(32)].to_csv(SOURCE / "Figure_7A_K32_dumbbell_source.csv", index=False)
    public.to_csv(SOURCE / "Figure_7B_D_arrow_source.csv", index=False)
    heat = pd.DataFrame(
        [v for _, _, v in heat_rows],
        index=[f"{SHORT[p]}|{TASK_LABEL[t]}" for p, t, _ in heat_rows],
        columns=["K = 16", "K = 32"],
    )
    heat.to_csv(SOURCE / "Figure_7C_grouped_heatmap_source.csv")
    normalization_audit.to_csv(SOURCE / "Figure_7_normalization_denominator_audit.csv", index=False)
    pd.DataFrame([
        *({"encoding": "candidate-pool colour", "level": SHORT[p], "value": c} for p, c in COLORS.items()),
        *({"encoding": "endpoint marker", "level": TASK_LABEL[t], "value": MARKERS[t]} for t in TASKS),
        {"encoding": "candidate count", "level": "K = 16", "value": "open arrow tail"},
        {"encoding": "candidate count", "level": "K = 32", "value": "filled arrow head"},
        {"encoding": "Panel A estimate", "level": "Observed audit-best", "value": "open circle"},
        {"encoding": "Panel A estimate", "level": "Validation-selected", "value": "filled circle"},
    ]).to_csv(SOURCE / "Figure_7_visual_encoding_guide.csv", index=False)
    audit = {
        "layout": {"top": [0.50, 0.50], "bottom": [0.46, 0.54]},
        "panel_b_facets": ["ClinTox", "BACE", "ESOL"],
        "panel_a_candidate_count": 32,
        "normalization": "Endpoint- and K-specific homogeneous-pool observed audit-best opportunity gain",
        "minimum_denominator": float(normalization_audit.homogeneous_observed_audit_best_gain.min()),
        "all_denominators_positive": bool(normalization_audit.positive_denominator.all()),
        "time_conversion": "audit_fit_minutes = audit_fit_seconds / 60",
        "cost_scope": "recorded downstream nested fitting and prediction only; excludes encoder pretraining, model acquisition, and cached embedding extraction",
        "heatmap_colour_range": [-1.0, 1.0],
    }
    (SOURCE / "Figure_7_definition_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(stem)


if __name__ == "__main__":
    main()
