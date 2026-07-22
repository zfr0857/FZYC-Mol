from __future__ import annotations

import json
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BASE = Path(os.environ.get(
    "FZYC_COMPOSITION_OUT", ROOT / "output" / "paper27_equal_size_registry_composition_20260716"
))
OUT = Path(os.environ.get("FZYC_FIG7_OUT", BASE / "figures"))
SOURCE = Path(os.environ.get("FZYC_FIG7_SOURCE", BASE / "figure_source_data"))
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
SIZES = {16: 28, 32: 52}


def style() -> None:
    mpl.rcParams.update({
        "font.family": "Times New Roman",
        "font.serif": ["Times New Roman"],
        "mathtext.fontset": "stix",
        "axes.unicode_minus": False,
        "font.size": 9.0,
        "axes.titlesize": 10.3,
        "axes.titleweight": "bold",
        "axes.labelsize": 9.2,
        "xtick.labelsize": 8.0,
        "ytick.labelsize": 8.0,
        "legend.fontsize": 8.2,
        "axes.linewidth": 0.8,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "savefig.facecolor": "white",
        "figure.facecolor": "white",
    })


def panel_label(ax: plt.Axes, label: str, x: float = -0.15) -> None:
    ax.text(x, 1.10, label, transform=ax.transAxes, fontsize=12.0,
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
        raise ValueError("All endpoint-specific homogeneous-pool normalization denominators must be positive")
    cells["observed_audit_best_gain_normalized"] = (
        cells.oracle_opportunity_gain_mean / cells.homogeneous_observed_audit_best_gain
    )
    cells["validation_selected_gain_normalized"] = (
        cells.selected_model_gain_mean / cells.homogeneous_observed_audit_best_gain
    )
    cells["cross_fitted_gap_normalized"] = (
        cells.cross_fitted_selection_gap_mean / cells.homogeneous_observed_audit_best_gain
    )
    audit = reference.copy()
    audit["positive_denominator"] = audit.homogeneous_observed_audit_best_gain > 0
    audit["minimum_denominator_across_cells"] = audit.homogeneous_observed_audit_best_gain.min()
    return summary, cells, audit


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SOURCE.mkdir(parents=True, exist_ok=True)
    style()
    summary, cells, normalization_audit = prepare_cells()
    pool_order = list(COLORS)

    fig = plt.figure(figsize=(7.25, 5.85))
    outer = fig.add_gridspec(2, 1, left=.155, right=.985, bottom=.19, top=.965, hspace=.48)
    top = outer[0].subgridspec(1, 2, width_ratios=[.53, .47], wspace=.40)
    bottom = outer[1].subgridspec(1, 2, width_ratios=[.55, .45], wspace=.38)
    ax_a = fig.add_subplot(top[0, 0])
    ax_b = fig.add_subplot(top[0, 1])
    ax_c = fig.add_subplot(bottom[0, 0])
    ax_d = fig.add_subplot(bottom[0, 1])

    # A: K=32 opportunity and realised gain, normalized only for cross-endpoint display.
    k32 = cells.loc[cells.candidate_count.eq(32)].copy()
    offsets = {"clintox": -.18, "bace": 0.0, "esol": .18}
    for x, pool in enumerate(pool_order):
        for task in TASKS:
            row = k32.loc[k32.pool.eq(pool) & k32.task.eq(task)].iloc[0]
            xp = x + offsets[task]
            selected = row.validation_selected_gain_normalized
            best = row.observed_audit_best_gain_normalized
            ax_a.plot([xp, xp], [selected, best], color=COLORS[pool], lw=1.0, alpha=.72, zorder=1)
            ax_a.scatter(xp, selected, s=SIZES[32], color=COLORS[pool], marker=MARKERS[task],
                         edgecolor="white", linewidth=.45, zorder=3)
            ax_a.scatter(xp, best, s=SIZES[32], facecolor="white", edgecolor=COLORS[pool],
                         marker=MARKERS[task], linewidth=1.1, zorder=3)
    ax_a.set_xticks(range(3), ["Morgan-\nonly", "Classical\nmultiview", "Modern-\naugmented"])
    ax_a.set_ylabel("Normalized gain")
    ax_a.set_title("Opportunity and realised gain", loc="left", pad=6)
    estimate_handles = [
        Line2D([0], [0], marker="o", ls="", mfc="white", mec="#4B5563", label="Observed audit-best"),
        Line2D([0], [0], marker="o", ls="", mfc="#4B5563", mec="#4B5563", label="Validation-selected"),
    ]
    ax_a.legend(handles=estimate_handles, frameon=False, loc="lower right", ncol=1,
                handletextpad=.35, borderpad=.15)
    panel_label(ax_a, "A", -.18)

    # B: exact x definition is raw entropy effective rank divided by K.
    for pool in pool_order:
        for task in TASKS:
            q = cells.loc[cells.pool.eq(pool) & cells.task.eq(task)].sort_values("candidate_count")
            ax_b.plot(q.relative_entropy_rank, q.cross_fitted_gap_normalized,
                      color=COLORS[pool], lw=.9, alpha=.70, zorder=1)
            for row in q.itertuples(index=False):
                ax_b.scatter(row.relative_entropy_rank, row.cross_fitted_gap_normalized,
                             color=COLORS[pool], edgecolor="white", linewidth=.45,
                             marker=MARKERS[task], s=SIZES[int(row.candidate_count)], zorder=3)
    ax_b.axhline(0, color="#AEB4BB", lw=.9, ls="--", zorder=0)
    ax_b.set_xlabel("Relative entropy rank, r_entropy / K")
    ax_b.set_ylabel("Normalized cross-fitted gap")
    ax_b.set_title("Diversity and cross-fitted gap", loc="left", pad=6)
    panel_label(ax_b, "B", -.19)

    # C: grouped heat map; registry name appears once per three-endpoint group.
    matrix_rows = [(pool, task) for pool in pool_order for task in TASKS]
    heat = np.asarray([
        [summary.loc[
            summary.pool.eq(pool) & summary.task.eq(task) & summary.candidate_count.eq(k),
            "chance_adjusted_hit3_mean",
        ].iloc[0] for k in (16, 32)]
        for pool, task in matrix_rows
    ])
    norm = TwoSlopeNorm(vmin=min(-.4, float(np.nanmin(heat))), vcenter=0.0, vmax=max(1.0, float(np.nanmax(heat))))
    image = ax_c.imshow(heat, cmap="RdBu", norm=norm, aspect="auto")
    ax_c.set_xticks([0, 1], ["K = 16", "K = 32"])
    ax_c.set_yticks(range(9), [TASK_LABEL[t] for _, t in matrix_rows])
    ax_c.tick_params(axis="y", pad=3)
    for sep in (2.5, 5.5):
        ax_c.axhline(sep, color="white", lw=1.5)
        ax_c.axhline(sep, color="#C6CBD1", lw=.55)
    for center, pool in zip((1, 4, 7), pool_order):
        ax_c.text(-.48, center, SHORT[pool], transform=ax_c.get_yaxis_transform(),
                  ha="right", va="center", fontsize=8.5, fontweight="bold", color=COLORS[pool])
    for i in range(heat.shape[0]):
        for j in range(heat.shape[1]):
            rgba = image.cmap(image.norm(heat[i, j]))
            luminance = .2126 * rgba[0] + .7152 * rgba[1] + .0722 * rgba[2]
            ax_c.text(j, i, f"{heat[i, j]:.2f}", ha="center", va="center", fontsize=8.2,
                      color="white" if luminance < .48 else "#26313A")
    cbar = fig.colorbar(image, ax=ax_c, fraction=.040, pad=.025)
    cbar.ax.set_title("CAHit@3", fontsize=8.5, fontweight="bold", pad=4)
    cbar.ax.tick_params(labelsize=8.0)
    ax_c.set_title("Chance-adjusted Hit@3", loc="left", pad=6)
    panel_label(ax_c, "C", -.15)

    # D: downstream nested fitting and prediction cost only.
    for pool in pool_order:
        for task in TASKS:
            q = cells.loc[cells.pool.eq(pool) & cells.task.eq(task)].sort_values("candidate_count")
            hours = q.audit_fit_seconds_mean / 3600
            ax_d.plot(hours, q.validation_selected_gain_normalized, color=COLORS[pool],
                      lw=.9, alpha=.70, ls="--", zorder=1)
            for h, row in zip(hours, q.itertuples(index=False)):
                ax_d.scatter(h, row.validation_selected_gain_normalized,
                             color=COLORS[pool], edgecolor="white", linewidth=.45,
                             marker=MARKERS[task], s=SIZES[int(row.candidate_count)], zorder=3)
    ax_d.axhline(0, color="#AEB4BB", lw=.9, ls="--", zorder=0)
    ax_d.set_xlabel("Mean downstream audit time\nper outer unit (h)")
    ax_d.set_ylabel("Normalized selected gain")
    ax_d.set_title("Downstream cost–benefit", loc="left", pad=6)
    ax_d.text(.98, .97, "Downstream fitting only", transform=ax_d.transAxes,
              ha="right", va="top", fontsize=8.0, fontweight="bold", color="#59616A",
              bbox=dict(fc="white", ec="#D5D9DD", lw=.5, boxstyle="round,pad=.18"))
    panel_label(ax_d, "D", -.18)

    for ax in (ax_a, ax_b, ax_d):
        ax.spines[["top", "right"]].set_visible(False)

    pool_handles = [Line2D([0], [0], marker="o", color=color, lw=1.0,
                           markerfacecolor=color, label=SHORT[pool]) for pool, color in COLORS.items()]
    endpoint_handles = [Line2D([0], [0], marker=MARKERS[t], color="#4B5563", lw=0,
                               markerfacecolor="#4B5563", label=TASK_LABEL[t]) for t in TASKS]
    k_handles = [Line2D([0], [0], marker="o", color="#4B5563", lw=0,
                        markersize=np.sqrt(SIZES[k]), label=f"K = {k}") for k in (16, 32)]
    fig.legend(handles=pool_handles + endpoint_handles + k_handles, frameon=False,
               loc="lower center", bbox_to_anchor=(.52, .03), ncol=8,
               handletextpad=.28, columnspacing=.75)

    stem = OUT / "Figure_7_equal_size_registry_composition"
    fig.savefig(stem.with_suffix(".pdf"), bbox_inches="tight", facecolor="white")
    fig.savefig(stem.with_suffix(".svg"), bbox_inches="tight", facecolor="white")
    fig.savefig(stem.with_name(stem.name + "_600dpi.png"), dpi=600, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    public_cells = cells.rename(columns={
        "oracle_opportunity_gain_mean": "observed_audit_best_opportunity_gain_mean",
        "oracle_opportunity_gain_low": "observed_audit_best_opportunity_gain_low",
        "oracle_opportunity_gain_high": "observed_audit_best_opportunity_gain_high",
    })
    legacy = [column for column in public_cells.columns if "oracle" in column.lower()]
    public_cells = public_cells.drop(columns=legacy)
    public_k32 = public_cells.loc[public_cells.candidate_count.eq(32)].copy()
    public_k32.to_csv(SOURCE / "Figure_7A_gain_source.csv", index=False)
    public_cells.to_csv(SOURCE / "Figure_7B_D_story_cells_source.csv", index=False)
    pd.DataFrame(heat, index=[f"{SHORT[p]}|{TASK_LABEL[t]}" for p, t in matrix_rows],
                 columns=["K = 16", "K = 32"]).to_csv(SOURCE / "Figure_7C_cahit_source.csv")
    normalization_audit.to_csv(SOURCE / "Figure_7_normalization_denominator_audit.csv", index=False)
    encoding = pd.DataFrame([
        {"encoding": "registry colour", "level": SHORT[p], "value": c} for p, c in COLORS.items()
    ] + [
        {"encoding": "endpoint marker", "level": TASK_LABEL[t], "value": MARKERS[t]} for t in TASKS
    ] + [
        {"encoding": "candidate-count marker size", "level": f"K = {k}", "value": SIZES[k]} for k in (16, 32)
    ] + [
        {"encoding": "A estimate fill", "level": "Observed audit-best", "value": "open"},
        {"encoding": "A estimate fill", "level": "Validation-selected", "value": "filled"},
    ])
    encoding.to_csv(SOURCE / "Figure_7_visual_encoding_guide.csv", index=False)
    audit = {
        "normalization": "Endpoint- and K-specific homogeneous-pool observed audit-best opportunity gain",
        "minimum_denominator": float(normalization_audit.homogeneous_observed_audit_best_gain.min()),
        "all_denominators_positive": bool(normalization_audit.positive_denominator.all()),
        "relative_entropy_rank_definition": "raw Ledoit-Wolf entropy effective rank divided by nominal candidate count K",
        "cost_scope": "observed downstream nested fitting and prediction only",
    }
    (SOURCE / "Figure_7_definition_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(stem)


if __name__ == "__main__":
    main()
