from __future__ import annotations

import importlib.util
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image
from matplotlib.lines import Line2D
from matplotlib.transforms import ScaledTranslation


ROOT = Path(__file__).resolve().parents[1]
BASE_SCRIPT = ROOT / "paper31_expanded_intervention" / "reproducibility_code" / "build_paper31_figures_20260717.py"
OUT = ROOT / "reproduced_outputs" / "main_figures"


def load_base():
    spec = importlib.util.spec_from_file_location("paper31_figures", BASE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def setup() -> None:
    mpl.rcParams.update({
        "font.family": "Times New Roman",
        "font.size": 9.0,
        "axes.titlesize": 10.0,
        "axes.labelsize": 9.2,
        "xtick.labelsize": 8.5,
        "ytick.labelsize": 8.5,
        "legend.fontsize": 8.5,
        "axes.linewidth": 0.75,
        "svg.fonttype": "path",
        "svg.hashsalt": "fzyc-mol-paper35",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "savefig.facecolor": "white",
    })


def clean(ax: plt.Axes, axis: str = "y") -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis=axis, color="#D9DEE5", linewidth=0.55, alpha=0.85)
    ax.set_axisbelow(True)


def label(ax: plt.Axes, letter: str) -> None:
    title = ax.title
    transform = title.get_transform() + ScaledTranslation(
        -18 / 72, 0, ax.figure.dpi_scale_trans
    )
    ax.text(0, title.get_position()[1], letter, transform=transform, fontsize=11,
            fontweight="bold", ha="left", va=title.get_va(), clip_on=False)


def save(fig: plt.Figure) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for suffix, kwargs in [
        ("svg", {"metadata": {"Date": "2026-07-18"}}),
        ("pdf", {}), ("png", {"dpi": 600}), ("png1200", {"dpi": 1200}),
    ]:
        if suffix == "png":
            name = "Figure7_600dpi.png"
        elif suffix == "png1200":
            name = "Figure7_1200dpi.png"
        else:
            name = f"Figure7.{suffix}"
        target = OUT / name
        fig.savefig(target, facecolor="white", **kwargs)
        if suffix == "svg":
            content = target.read_text(encoding="utf-8")
            target.write_text("\n".join(line.rstrip() for line in content.splitlines()) + "\n", encoding="utf-8")
        if suffix in {"png", "png1200"}:
            dpi = 600 if suffix == "png" else 1200
            with Image.open(target) as rendered:
                rendered.convert("RGB").save(target, dpi=(dpi, dpi), compress_level=6)
    plt.close(fig)


def panel_a(ax: plt.Axes, base, data: dict[str, pd.DataFrame]) -> None:
    summary = data["summary"]
    source = summary.loc[
        summary.design.eq("equal_K")
        & summary.anchor_scheme.eq("shared_morgan_linear")
        & summary.candidate_count.eq(32)
    ]
    offsets = {
        "Homogeneous Morgan": 0.20,
        "Classical multiview": 0.00,
        "Modern-augmented": -0.20,
    }
    for task_index, task in enumerate(base.TASKS[::-1]):
        y0 = task_index
        for pool in base.POOLS:
            row = source.loc[source.task.eq(task) & source.pool.eq(pool)].iloc[0]
            y = y0 + offsets[pool]
            selected = row.homogeneous_normalized_selected_gain_mean
            opportunity = row.homogeneous_normalized_oracle_opportunity_mean
            ax.plot([selected, opportunity], [y, y], color=base.COLORS[pool], lw=1.1, zorder=2)
            ax.errorbar(
                selected, y,
                xerr=[[selected - row.homogeneous_normalized_selected_gain_low],
                      [row.homogeneous_normalized_selected_gain_high - selected]],
                fmt="s", ms=6.3, color=base.COLORS[pool], ecolor=base.COLORS[pool],
                elinewidth=0.7, capsize=1.6, zorder=3,
            )
            ax.errorbar(
                opportunity, y,
                xerr=[[opportunity - row.homogeneous_normalized_oracle_opportunity_low],
                      [row.homogeneous_normalized_oracle_opportunity_high - opportunity]],
                fmt="o", ms=6.3, mfc="white", mec=base.COLORS[pool], mew=1.0,
                ecolor=base.COLORS[pool], elinewidth=0.7, capsize=1.6, zorder=3,
            )
    ax.axvline(1, color="#7A8393", lw=0.8, ls="--")
    ax.axhline(2.5, color="#D7DBE1", lw=0.65)
    ax.set_yticks(range(6), [base.TASK_LABEL[t] for t in base.TASKS[::-1]])
    ax.set_ylim(-0.55, 5.55)
    ax.set_xlim(0.62, 2.78)
    ax.set_xlabel("Normalized gain")
    ax.set_title("Opportunity and realised gain", loc="left", fontweight="bold", pad=30)
    clean(ax, "x")
    outcome = [
        Line2D([0], [0], marker="s", color="#555", mfc="#555", lw=0, label="Selected"),
        Line2D([0], [0], marker="o", color="#555", mfc="white", lw=0, label="Audit-best"),
    ]
    ax.legend(handles=outcome, ncol=2, frameon=False, loc="lower center",
              bbox_to_anchor=(0.50, 1.005), borderaxespad=0,
              columnspacing=0.9, handletextpad=0.35)
    label(ax, "A")


def panel_b(cell, base, data: dict[str, pd.DataFrame]) -> None:
    sub = cell.subgridspec(2, 1, hspace=0.10)
    axes = [plt.subplot(sub[0]), plt.subplot(sub[1])]
    summary = data["summary"]
    primary = summary.loc[
        summary.design.eq("equal_K") & summary.anchor_scheme.eq("shared_morgan_linear")
    ]
    xpos = {"classification": np.arange(4), "regression": np.arange(4) + 5}
    metrics = [
        ("homogeneous_normalized_selected_gain_mean", "Selected gain"),
        ("homogeneous_normalized_cross_fitted_gap_mean", "Cross-fitted gap"),
    ]
    for ax, (metric, ylabel) in zip(axes, metrics):
        for pool in base.POOLS:
            subset = primary.loc[primary.pool.eq(pool)]
            for task_type, x in xpos.items():
                values = subset.loc[subset.task_type.eq(task_type)].groupby("candidate_count")[metric].mean().reindex(base.KS)
                ax.plot(x, values, color=base.COLORS[pool], marker="o", ms=3.8, lw=1.3)
        ax.axvline(4, color="#D0D5DC", lw=0.70)
        ax.axhline(0, color="#7A8393", lw=0.75)
        ax.set_ylabel(ylabel)
        clean(ax, "y")
    axes[0].set_title("Composition-by-K effects", loc="left", fontweight="bold", pad=30)
    band = dict(facecolor="#EEF1F4", edgecolor="none", boxstyle="round,pad=0.22")
    axes[0].text(1.5, 0.96, "Classification", transform=axes[0].get_xaxis_transform(),
                 ha="center", va="top", fontsize=9.5, fontweight="bold", bbox=band)
    axes[0].text(6.5, 0.96, "Regression", transform=axes[0].get_xaxis_transform(),
                 ha="center", va="top", fontsize=9.5, fontweight="bold", bbox=band)
    axes[0].tick_params(labelbottom=False)
    axes[1].set_xticks(np.r_[xpos["classification"], xpos["regression"]], [str(k) for k in base.KS] * 2)
    axes[1].set_xlabel("Candidate-pool size, K")
    pool_handles = [Line2D([0], [0], color=base.COLORS[pool], marker="o", lw=1.3,
                           ms=4.0, label={"Homogeneous Morgan": "Hom.",
                                          "Classical multiview": "Multiview",
                                          "Modern-augmented": "Modern"}[pool])
                    for pool in base.POOLS]
    axes[0].legend(handles=pool_handles, ncol=3, frameon=False, loc="lower center",
                   bbox_to_anchor=(0.50, 1.005), borderaxespad=0,
                   columnspacing=0.75, handlelength=1.35, handletextpad=0.35)
    label(axes[0], "B")


def panel_c(ax: plt.Axes, base, data: dict[str, pd.DataFrame]) -> None:
    summary = data["summary"]
    primary = summary.loc[
        summary.design.eq("equal_K") & summary.anchor_scheme.eq("shared_morgan_linear")
    ]
    index = pd.MultiIndex.from_product([base.TASKS, base.POOLS], names=["task", "pool"])
    hit = primary.pivot_table(index=["task", "pool"], columns="candidate_count",
                              values="chance_adjusted_hit3_mean").reindex(index)[base.KS]
    hit_matrix = hit.to_numpy(float)
    display = np.full((19, 4), np.nan)
    rows = list(range(9)) + list(range(10, 19))
    display[rows, :] = hit_matrix
    cmap = mpl.colormaps["RdYlBu"].copy()
    cmap.set_bad("white")
    mesh = ax.pcolormesh(np.arange(5), np.arange(20), np.ma.masked_invalid(display),
                         shading="flat", cmap=cmap, vmin=-1, vmax=1, antialiased=False)
    ax.set_xlim(-0.72, 4)
    ax.set_ylim(19, 0)
    for i, row_pos in enumerate(rows):
        for j in range(4):
            value = hit_matrix[i, j]
            if np.isfinite(value):
                dark = abs(value) > 0.62
                ax.text(j + 0.5, row_pos + 0.5, f"{value:.2f}", ha="center", va="center",
                        fontsize=8.5, color="white" if dark else "#253047")
    centres = [1.5, 4.5, 7.5, 11.5, 14.5, 17.5]
    ax.set_yticks(centres, [base.TASK_LABEL[task] for task in base.TASKS])
    for tick_label in ax.get_yticklabels():
        tick_label.set_fontweight("bold")
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    for i, (_, pool) in enumerate(index):
        row_pos = rows[i]
        ax.plot([-0.63, -0.63], [row_pos + 0.18, row_pos + 0.82],
                color=base.COLORS[pool], lw=2.2, solid_capstyle="butt",
                clip_on=False)
        ax.text(-0.25, row_pos + 0.5,
                {"Homogeneous Morgan": "H", "Classical multiview": "MV", "Modern-augmented": "M"}[pool],
                ha="center", va="center", fontsize=8.5, fontweight="bold",
                color=base.COLORS[pool], clip_on=False)
    for boundary in [3, 6, 13, 16]:
        ax.axhline(boundary, color="white", lw=1.4)
    ax.set_xticks(np.arange(4) + 0.5, ["4", "8", "16", "32"])
    ax.tick_params(axis="x", rotation=0, labelsize=8.5)
    ax.set_xlabel("Candidate-pool size, K", labelpad=4)
    ax.set_title("Ranking fidelity", loc="left", fontweight="bold", pad=30)
    cax = ax.inset_axes([1.045, 0.12, 0.035, 0.76])
    cbar = plt.colorbar(mesh, cax=cax)
    if cbar.solids is not None:
        cbar.solids.set_rasterized(False)
    cbar.ax.tick_params(labelsize=8.5)
    cbar.ax.set_title("CAHit@3", fontsize=7.5, pad=4, loc="left")
    label(ax, "C")


def pareto(points: pd.DataFrame) -> pd.DataFrame:
    ordered = points.dropna(subset=["time", "gain"]).sort_values("time")
    keep, best = [], -np.inf
    for _, row in ordered.iterrows():
        if row.gain > best:
            keep.append(row)
            best = row.gain
    return pd.DataFrame(keep)


def panel_d(ax: plt.Axes, base, data: dict[str, pd.DataFrame]) -> None:
    units = data["units"]
    budget = data["budget_units"]
    equal_k = units.loc[
        units.design.eq("equal_K") & units.anchor_scheme.eq("shared_morgan_linear")
    ].groupby(["pool", "candidate_count"], as_index=False).agg(
        time=("audit_fit_seconds", "mean"), gain=("homogeneous_normalized_selected_gain", "mean")
    )
    equal_budget = budget.groupby(["pool", "candidate_count"], as_index=False).agg(
        time=("audit_fit_seconds", "mean"), gain=("homogeneous_normalized_selected_gain", "mean")
    )
    equal_k["design"] = "Equal K"
    equal_budget["design"] = "Equal budget"
    points = pd.concat([equal_k, equal_budget], ignore_index=True)
    sizes = {4: 24, 8: 34, 16: 46, 32: 60}
    for pool in base.POOLS:
        for design, linestyle, marker, face in [
            ("Equal K", "-", "o", base.COLORS[pool]),
            ("Equal budget", "--", "D", "white"),
        ]:
            group = points.loc[points.pool.eq(pool) & points.design.eq(design)].sort_values("candidate_count")
            ax.plot(group.time, group.gain, color=base.COLORS[pool], ls=linestyle, lw=1.1)
            for _, row in group.iterrows():
                ax.scatter(row.time, row.gain, marker=marker, s=sizes[int(row.candidate_count)],
                           facecolor=face, edgecolor=base.COLORS[pool], linewidth=0.9, zorder=3)
            if design == "Equal K":
                for _, row in group.loc[group.candidate_count.eq(32)].iterrows():
                    modern_k32 = pool == "Modern-augmented"
                    offset = (0, 12) if modern_k32 else (3, 3)
                    ax.annotate(f"K={int(row.candidate_count)}", (row.time, row.gain), xytext=offset,
                                textcoords="offset points", fontsize=8.5, color=base.COLORS[pool],
                                ha="center" if modern_k32 else "left")
    front = pareto(points)
    if len(front):
        ax.step(front.time, front.gain, where="post", color="#202632", lw=1.0, alpha=0.8)
    ax.set_xscale("log")
    ax.set_xlim(points.time.min() * 0.55, points.time.max() * 1.8)
    ax.set_xticks([1, 10, 100], ["1", "10", "100"])
    ax.axhline(0, color="#7A8393", lw=0.7)
    ax.set_ylim(-0.36, 2.15)
    ax.set_xlabel("Downstream audit time per outer unit (s, log scale)")
    ax.set_ylabel("Normalized selected gain")
    ax.set_title("Downstream budget-benefit", loc="left", fontweight="bold", pad=30)
    ax.text(1.0, 1.035, "Downstream fitting only", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=8.0, color="#555D68")
    clean(ax, "both")
    design_handles = [
        Line2D([0], [0], color="#333", marker="o", mfc="#777", lw=1.1, label="Equal K"),
        Line2D([0], [0], color="#333", marker="D", mfc="white", lw=1.1, ls="--", label="Equal budget"),
        Line2D([0], [0], color="#202632", lw=1.0, drawstyle="steps-post", label="Pareto frontier"),
    ]
    k_handles = [Line2D([0], [0], color="#666", marker="o", ms=np.sqrt(sizes[k]),
                        mfc="#888", lw=0, label=f"K={k}") for k in base.KS]
    design_legend = ax.legend(handles=design_handles, ncol=1, frameon=False, loc="upper left",
                              bbox_to_anchor=(1.01, 0.98), handlelength=1.2,
                              labelspacing=0.25, handletextpad=0.3)
    ax.add_artist(design_legend)
    ax.legend(handles=k_handles, ncol=4, frameon=False, mode="expand",
              loc="upper left", bbox_to_anchor=(0.0, -0.24, 1.0, 0.05),
              borderaxespad=0.0, handlelength=0.55,
              columnspacing=0.70, handletextpad=0.18, fontsize=7.0)
    label(ax, "D")


def main() -> None:
    setup()
    base = load_base()
    base.DATA = ROOT / "paper31_expanded_intervention" / "experiment_exports"
    base.COLORS = {
        "Homogeneous Morgan": "#3B5B92",
        "Classical multiview": "#2A9D8F",
        "Modern-augmented": "#E69F00",
    }
    data = base.load()
    fig = plt.figure(figsize=(4016 / 600, 200 / 25.4))
    grid = fig.add_gridspec(2, 2, width_ratios=[1.00, 1.12], height_ratios=[1.0, 1.12])
    panel_a(fig.add_subplot(grid[0, 0]), base, data)
    panel_b(grid[0, 1], base, data)
    panel_c(fig.add_subplot(grid[1, 0]), base, data)
    panel_d(fig.add_subplot(grid[1, 1]), base, data)
    fig.subplots_adjust(left=0.13, right=0.78, top=0.88, bottom=0.11, hspace=0.40, wspace=0.50)
    save(fig)
    print(OUT / "Figure7.svg")


if __name__ == "__main__":
    main()
