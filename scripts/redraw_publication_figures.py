from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle


ROOT = Path(__file__).resolve().parents[1]
TABLE_DIR = ROOT / "reports" / "manuscript_tables"
POLISHED_DIR = ROOT / "reports" / "manuscript_figures_polished"
PACKAGE_MAIN_DIR = ROOT / "reports" / "submission_package" / "main_figures"

MAIN_FIGURES = {
    "fig1_framework_overview_polished": "Figure_1_FZYC_Mol_framework",
    "fig2_moleculenet_rank_heatmap_polished": "Figure_2_MoleculeNet_model_family_ranks",
    "fig3_moleculenet_performance_dots": "Figure_3_MoleculeNet_main_performance",
    "fig4_split_realism_polished": "Figure_4_Split_realism_structure_shift",
    "fig5_tdc_official_split_delta": "Figure_5_Official_TDC_ADMET_scaffold_delta",
    "fig6_reliability_summary_polished": "Figure_6_Uncertainty_AD_reliability",
    "fig11_motif_fragment_interpretation": "Figure_7_Motif_fragment_interpretation",
}

COLORS = {
    "ink": "#111827",
    "muted": "#64748b",
    "grid": "#e5e7eb",
    "blue": "#2f6fbb",
    "cyan": "#168aad",
    "green": "#1b8a6b",
    "amber": "#d98c00",
    "rose": "#c43b5d",
    "purple": "#7b61b8",
    "slate": "#334155",
    "paper": "#fbfdff",
    "soft_blue": "#dbeafe",
    "soft_green": "#dcfce7",
    "soft_rose": "#fee2e2",
}


def setup_style() -> None:
    sns.set_theme(style="white", context="paper", font_scale=1.0)
    plt.rcParams.update(
        {
            "figure.dpi": 140,
            "savefig.dpi": 360,
            "font.family": "DejaVu Sans",
            "axes.titleweight": "bold",
            "axes.titlesize": 10.8,
            "axes.labelsize": 9.8,
            "axes.labelcolor": COLORS["ink"],
            "axes.edgecolor": "#d1d5db",
            "axes.facecolor": "white",
            "figure.facecolor": "white",
            "xtick.color": COLORS["slate"],
            "ytick.color": COLORS["slate"],
            "grid.color": COLORS["grid"],
            "grid.linewidth": 0.55,
            "legend.frameon": True,
            "legend.framealpha": 0.96,
            "legend.edgecolor": "#e2e8f0",
            "axes.spines.right": False,
            "axes.spines.top": False,
        }
    )


def ensure_dirs() -> None:
    POLISHED_DIR.mkdir(parents=True, exist_ok=True)
    PACKAGE_MAIN_DIR.mkdir(parents=True, exist_ok=True)


def save_main(fig: plt.Figure, polished_stem: str) -> None:
    fig.savefig(POLISHED_DIR / f"{polished_stem}.png", bbox_inches="tight", facecolor="white")
    fig.savefig(POLISHED_DIR / f"{polished_stem}.svg", bbox_inches="tight", facecolor="white")
    package_stem = MAIN_FIGURES[polished_stem]
    fig.savefig(PACKAGE_MAIN_DIR / f"{package_stem}.png", bbox_inches="tight", facecolor="white")
    fig.savefig(PACKAGE_MAIN_DIR / f"{package_stem}.svg", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def wrap(text: object, width: int = 18) -> str:
    return "\n".join(textwrap.wrap(str(text), width=width, break_long_words=False))


def clean_dataset(name: object) -> str:
    text = str(name)
    for token in ["tdc_", "_wang", "_hou", "_broccatelli", "_martins", "_veith", "_ma"]:
        text = text.replace(token, "")
    return text.replace("_", " ").upper()


def compact_fragment(text: object, max_len: int = 34) -> str:
    out = str(text).replace("BRICS::", "").replace("FG::", "").replace("[", "").replace("]", "")
    out = out.replace("*", "*").replace("@@", "@")
    if len(out) <= max_len:
        return out
    return out[: max_len - 1] + "..."


def panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(
        -0.075,
        1.06,
        label,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=12.5,
        fontweight="bold",
        color=COLORS["ink"],
    )


def draw_box(
    ax: plt.Axes,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    lines: list[str],
    face: str,
    edge: str = "#1f2937",
    title_color: str = COLORS["ink"],
    fontsize: float = 8.2,
    lw: float = 1.25,
) -> None:
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        linewidth=lw,
        edgecolor=edge,
        facecolor=face,
    )
    ax.add_patch(patch)
    ax.text(x + 0.018, y + h - 0.024, title, ha="left", va="top", fontsize=9.2, fontweight="bold", color=title_color)
    body = "\n".join(lines)
    ax.text(x + 0.018, y + h - 0.06, body, ha="left", va="top", fontsize=fontsize, color=COLORS["muted"], linespacing=1.22)


def draw_arrow(ax: plt.Axes, start: tuple[float, float], end: tuple[float, float], color: str = "#64748b", lw: float = 1.4) -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=13,
            linewidth=lw,
            color=color,
            connectionstyle="arc3,rad=0.0",
        )
    )


def plot_framework() -> None:
    fig, ax = plt.subplots(figsize=(17.0, 9.4))
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    ax.text(
        0.5,
        0.965,
        "FZYC-Mol validation-only multi-expert framework",
        ha="center",
        va="top",
        fontsize=17.5,
        fontweight="bold",
        color=COLORS["ink"],
    )
    ax.text(
        0.5,
        0.928,
        "Endpoint-specific selection is made on validation predictions only; held-out test labels are used once for final reporting.",
        ha="center",
        va="top",
        fontsize=10.3,
        color=COLORS["muted"],
    )

    xs = [0.035, 0.235, 0.435, 0.635, 0.815]
    ws = [0.155, 0.155, 0.155, 0.145, 0.145]
    headers = [
        ("1  Data and splits", "#e0f2fe"),
        ("2  Molecular views", "#dcfce7"),
        ("3  Expert pool", "#fef3c7"),
        ("4  Validation integration", "#ede9fe"),
        ("5  Reliability outputs", "#ffe4e6"),
    ]
    for x, w, (label, color) in zip(xs, ws, headers):
        patch = FancyBboxPatch(
            (x, 0.835),
            w,
            0.055,
            boxstyle="round,pad=0.012,rounding_size=0.018",
            linewidth=0,
            facecolor=color,
        )
        ax.add_patch(patch)
        ax.text(x + w / 2, 0.862, label, ha="center", va="center", fontsize=9.4, fontweight="bold", color=COLORS["ink"])

    draw_box(
        ax,
        xs[0],
        0.67,
        ws[0],
        0.135,
        "Benchmarks",
        ["MoleculeNet main panel", "PyTDC ADMET official splits", "MoleculeACE cliffs", "OpenADMET appendix"],
        "#f0f9ff",
        edge="#0284c7",
    )
    draw_box(
        ax,
        xs[0],
        0.46,
        ws[0],
        0.155,
        "Split protocol",
        ["random / scaffold / structure", "train - validation - test", "seeded repeats", "retained best from validation"],
        "#eff6ff",
        edge="#2563eb",
    )
    draw_box(
        ax,
        xs[0],
        0.25,
        ws[0],
        0.155,
        "Hard subsets",
        ["low-similarity molecules", "local cliffs", "roughness diagnostics", "endpoint imbalance"],
        "#ecfeff",
        edge="#0891b2",
    )

    rep_items = [
        ("Graph", ["atom and bond graph", "scaffold context"], "#eff6ff", "#2563eb", 0.69),
        ("Fingerprints", ["Morgan / MACCS", "atom-pair / torsion"], "#f0fdf4", "#059669", 0.53),
        ("Descriptors", ["RDKit 2D physchem", "fast tabular features"], "#fffbeb", "#d97706", 0.37),
        ("Motifs and encoders", ["BRICS / Murcko / FG", "ChemBERTa / MoLFormer"], "#f5f3ff", "#7c3aed", 0.21),
    ]
    for title, lines, face, edge, y in rep_items:
        draw_box(ax, xs[1], y, ws[1], 0.105, title, lines, face, edge=edge, fontsize=7.8)

    expert_items = [
        ("Graph experts", ["GIN, FZYC graph heads", "Chemprop / D-MPNN"], "#eff6ff", "#2563eb", 0.705),
        ("Tabular experts", ["RF, XGBoost, LightGBM", "ExtraTrees, CatBoost-ready"], "#f0fdf4", "#059669", 0.56),
        ("Descriptor/motif heads", ["descriptor MLP", "named motif models"], "#fffbeb", "#d97706", 0.415),
        ("Rescue heads", ["Top-K / stacking ensembles", "target transform candidates"], "#fdf2f8", "#db2777", 0.27),
        ("Frozen embedding heads", ["ChemBERTa-MTR / MLM", "MoLFormer features"], "#f5f3ff", "#7c3aed", 0.125),
    ]
    for title, lines, face, edge, y in expert_items:
        draw_box(ax, xs[2], y, ws[2], 0.10, title, lines, face, edge=edge, fontsize=7.6)

    draw_box(
        ax,
        xs[3],
        0.66,
        ws[3],
        0.145,
        "Validation leaderboard",
        ["one table per endpoint", "metric direction respected", "uncertainty from seeds"],
        "#f5f3ff",
        edge="#7c3aed",
        lw=1.6,
    )
    draw_box(
        ax,
        xs[3],
        0.46,
        ws[3],
        0.14,
        "Selector actions",
        ["best expert", "Top-K mean", "ridge/logistic stacking", "adaptive consensus"],
        "#faf5ff",
        edge="#9333ea",
        lw=1.6,
    )
    draw_box(
        ax,
        xs[3],
        0.27,
        ws[3],
        0.13,
        "Targeted rescue gate",
        ["only if validation improves", "keeps retained-best result", "records source and delta"],
        "#fff1f2",
        edge="#e11d48",
        lw=1.6,
    )
    draw_box(
        ax,
        xs[3],
        0.105,
        ws[3],
        0.105,
        "Leakage guard",
        ["test labels unavailable", "appendix-only additions", "auditable tables"],
        "#f8fafc",
        edge="#475569",
        lw=1.5,
    )

    reliability_items = [
        ("Prediction report", ["primary metric", "seed mean +/- std"], "#f0fdf4", "#059669", 0.705),
        ("Uncertainty and AD", ["ensemble std / error model", "inverse Tanimoto / recon error"], "#ecfeff", "#0891b2", 0.54),
        ("Calibration layer", ["risk-coverage curves", "conformal diagnostics"], "#eff6ff", "#2563eb", 0.375),
        ("Interpretability", ["motif attribution", "fragment enrichment", "failure-case review"], "#fff7ed", "#ea580c", 0.21),
    ]
    for title, lines, face, edge, y in reliability_items:
        draw_box(ax, xs[4], y, ws[4], 0.11, title, lines, face, edge=edge, fontsize=7.6)

    for y in [0.737, 0.537, 0.327]:
        draw_arrow(ax, (xs[0] + ws[0] + 0.01, y), (xs[1] - 0.012, y), COLORS["slate"])
    for y in [0.742, 0.582, 0.422, 0.262]:
        draw_arrow(ax, (xs[1] + ws[1] + 0.01, y), (xs[2] - 0.012, y), COLORS["slate"])
    for y in [0.755, 0.61, 0.465, 0.32, 0.175]:
        draw_arrow(ax, (xs[2] + ws[2] + 0.01, y), (xs[3] - 0.012, 0.535), "#7c3aed", lw=1.25)
    draw_arrow(ax, (xs[3] + ws[3] + 0.01, 0.735), (xs[4] - 0.012, 0.755), COLORS["green"])
    draw_arrow(ax, (xs[3] + ws[3] + 0.01, 0.535), (xs[4] - 0.012, 0.595), COLORS["cyan"])
    draw_arrow(ax, (xs[3] + ws[3] + 0.01, 0.335), (xs[4] - 0.012, 0.265), COLORS["rose"])
    band = FancyBboxPatch(
        (0.035, 0.025),
        0.925,
        0.055,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        linewidth=1.0,
        edgecolor="#cbd5e1",
        facecolor="#f8fafc",
    )
    ax.add_patch(band)
    ax.text(
        0.497,
        0.053,
        "Appendix expansion: fast external benchmarks, full-panel TDC checks, reliability summary table, roughness and literature-alignment diagnostics",
        ha="center",
        va="center",
        fontsize=9.0,
        color=COLORS["slate"],
    )
    save_main(fig, "fig1_framework_overview_polished")


def plot_rank_heatmap() -> None:
    table = pd.read_csv(TABLE_DIR / "table2_moleculenet_main_long.csv")
    table = table[~table["category"].eq("Best observed candidate")].copy()
    ranks = []
    for dataset, sub in table.groupby("dataset", sort=False):
        ascending = sub["direction"].iloc[0] == "lower"
        sub = sub.copy()
        sub["rank"] = sub["value"].rank(method="min", ascending=ascending)
        ranks.append(sub)
    ranked = pd.concat(ranks, ignore_index=True)

    category_order = [
        "Classical Morgan",
        "Graph / D-MPNN core",
        "Chemprop",
        "Frozen pretrained",
        "Multi-fingerprint",
        "FZYC-Mol validation selector",
        "FZYC-Mol targeted rescue selector",
        "FZYC-Mol final retained-best",
    ]
    dataset_order = ["esol", "freesolv", "lipo", "bbbp", "bace", "clintox"]
    pivot = ranked.pivot_table(index="dataset", columns="category", values="rank", aggfunc="min")
    pivot = pivot.reindex(index=dataset_order, columns=category_order)
    annot = pd.DataFrame(index=pivot.index, columns=pivot.columns)
    for col in pivot.columns:
        annot[col] = pivot[col].map(lambda value: "" if pd.isna(value) else f"{int(value)}")
    cmap = LinearSegmentedColormap.from_list("rank_cmap", ["#0f766e", "#fef9c3", "#fee2e2"])

    fig, ax = plt.subplots(figsize=(13.6, 6.2))
    sns.heatmap(
        pivot,
        annot=annot,
        fmt="",
        cmap=cmap,
        vmin=1,
        vmax=max(7, int(np.nanmax(pivot.to_numpy()))),
        linewidths=1.0,
        linecolor="white",
        cbar_kws={"label": "Rank within endpoint"},
        ax=ax,
    )
    ax.set_title("Model-family rank map across MoleculeNet endpoints", fontsize=14, pad=14)
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_xticklabels([wrap(x.get_text(), 14) for x in ax.get_xticklabels()], rotation=0, fontsize=8.5)
    ax.set_yticklabels([x.get_text().upper() for x in ax.get_yticklabels()], rotation=0, fontsize=9.5, fontweight="bold")

    selector_cols = [
        i
        for i, col in enumerate(pivot.columns)
        if col in {
            "FZYC-Mol validation selector",
            "FZYC-Mol targeted rescue selector",
            "FZYC-Mol final retained-best",
        }
    ]
    for col_idx in selector_cols:
        ax.add_patch(Rectangle((col_idx, 0), 1, pivot.shape[0], fill=False, edgecolor="#111827", linewidth=2.0))

    for text in ax.texts:
        try:
            rank = int(text.get_text())
        except ValueError:
            continue
        text.set_fontweight("bold" if rank <= 2 else "normal")
        text.set_color("white" if rank <= 2 else COLORS["ink"])

    ax.text(
        0,
        -0.24,
        "Lower rank is better. Black outlines mark validation-governed FZYC-Mol columns; final retained-best includes Lipo rescue and FreeSolv targeted rebuild.",
        transform=ax.transAxes,
        fontsize=9.2,
        color=COLORS["muted"],
    )
    save_main(fig, "fig2_moleculenet_rank_heatmap_polished")


def plot_main_performance() -> None:
    table = pd.read_csv(TABLE_DIR / "table2_moleculenet_main_long.csv")

    legend_spec = [
        ("Strongest non-FZYC comparator", "o", "white", COLORS["slate"], 68),
        ("Validation selector", "D", COLORS["ink"], "white", 74),
        ("Final retained-best", "P", COLORS["blue"], "white", 110),
        ("Best observed candidate", "*", COLORS["amber"], "white", 170),
    ]

    def gain(direction: str, previous: float, current: float) -> float:
        return previous - current if direction == "lower" else current - previous

    fig, axes = plt.subplots(1, 2, figsize=(14.6, 5.7), gridspec_kw={"width_ratios": [1.0, 1.05]})
    panels = [
        ("regression", "Regression endpoints", "RMSE (lower is better)", axes[0]),
        ("classification", "Classification endpoints", "ROC-AUC (higher is better)", axes[1]),
    ]
    for task_type, title, xlabel, ax in panels:
        sub = table[table["task_type"].eq(task_type)].copy()
        datasets = sub["dataset"].drop_duplicates().tolist()
        y_positions = {dataset: i for i, dataset in enumerate(reversed(datasets))}
        for dataset in datasets:
            dsub = sub[sub["dataset"].eq(dataset)].set_index("category")
            y = y_positions[dataset]
            direction = str(dsub["direction"].iloc[0])
            non_fzyc = dsub[
                ~dsub.index.to_series().str.contains("FZYC-Mol", regex=False)
                & ~dsub.index.to_series().eq("Best observed candidate")
            ].copy()
            non_fzyc = non_fzyc.sort_values("value", ascending=direction == "lower")

            comparator = non_fzyc.iloc[0]
            selector = dsub.loc["FZYC-Mol validation selector"]
            final = dsub.loc["FZYC-Mol final retained-best"]
            observed = dsub.loc["Best observed candidate"]

            all_values = dsub["value"].dropna()
            span_min = min(comparator["value"], selector["value"], final["value"], observed["value"])
            span_max = max(comparator["value"], selector["value"], final["value"], observed["value"])
            ax.hlines(y, float(all_values.min()), float(all_values.max()), color="#e5e7eb", lw=2.0, zorder=0)
            ax.hlines(y, span_min, span_max, color="#cbd5e1", lw=4.2, alpha=0.72, zorder=1)
            ax.plot(
                [selector["value"], final["value"]],
                [y, y],
                color=COLORS["green"] if abs(selector["value"] - final["value"]) > 1e-9 else "#94a3b8",
                lw=2.4,
                solid_capstyle="round",
                zorder=2,
            )
            ax.scatter(
                comparator["value"],
                y + 0.16,
                s=68,
                marker="o",
                facecolor="white",
                edgecolor=COLORS["slate"],
                linewidth=1.45,
                zorder=4,
            )
            ax.scatter(
                selector["value"],
                y,
                s=74,
                marker="D",
                color=COLORS["ink"],
                edgecolor="white",
                linewidth=0.8,
                zorder=5,
            )
            ax.scatter(
                final["value"],
                y,
                s=110,
                marker="P",
                color=COLORS["blue"],
                edgecolor="white",
                linewidth=0.9,
                zorder=6,
            )
            ax.scatter(
                observed["value"],
                y - 0.16,
                s=170,
                marker="*",
                color=COLORS["amber"],
                edgecolor="white",
                linewidth=0.8,
                zorder=4,
            )
            for row, color, offset in [(selector, COLORS["ink"], 0.0), (final, COLORS["blue"], 0.0)]:
                if not pd.isna(row.get("std", np.nan)):
                    ax.errorbar(
                        row["value"],
                        y + offset,
                        xerr=row["std"],
                        color=color,
                        elinewidth=1.0,
                        capsize=2.2,
                        fmt="none",
                        alpha=0.78,
                        zorder=3,
                    )

            delta = gain(direction, float(selector["value"]), float(final["value"]))
            if abs(delta) > 1e-9:
                ax.annotate(
                    f"{delta:+.3f}",
                    xy=(final["value"], y),
                    xytext=(7, 9),
                    textcoords="offset points",
                    fontsize=8.1,
                    color=COLORS["green"],
                    fontweight="bold",
                    arrowprops={"arrowstyle": "->", "color": COLORS["green"], "lw": 0.9},
                )
        ax.set_yticks(list(y_positions.values()))
        ax.set_yticklabels([d.upper() for d in reversed(datasets)], fontsize=9.5, fontweight="bold")
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("")
        ax.grid(True, axis="x", alpha=0.34)
        ax.grid(False, axis="y")
        panel_label(ax, "A" if task_type == "regression" else "B")

        xmin, xmax = ax.get_xlim()
        pad = (xmax - xmin) * 0.05
        ax.set_xlim(xmin - pad, xmax + pad)

    handles = [
        plt.Line2D(
            [0],
            [0],
            marker=marker,
            color="none",
            markerfacecolor=face,
            markeredgecolor=edge,
            markeredgewidth=1.2,
            markersize=np.sqrt(size),
            label=label,
        )
        for label, marker, face, edge, size in legend_spec
    ]
    axes[1].legend(
        handles=handles,
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        fontsize=8.1,
        title="Displayed evidence",
    )
    fig.suptitle("Validation-only retained-best summary on MoleculeNet", fontsize=14.8, fontweight="bold")
    fig.text(
        0.08,
        0.018,
        "Thin gray line shows the full candidate range; thick segment shows strongest comparator, validation selector, final retained-best and best observed candidate. Error bars are seed-level standard deviations.",
        fontsize=8.7,
        color=COLORS["muted"],
    )
    fig.tight_layout(rect=[0, 0.06, 0.89, 0.95])
    save_main(fig, "fig3_moleculenet_performance_dots")


def plot_split_realism() -> None:
    table = pd.read_csv(TABLE_DIR / "table4_split_realism.csv")
    fig, axes = plt.subplots(2, 2, figsize=(15.0, 8.4), sharex=True)
    panels = [
        ("MoleculeNet", "regression", axes[0, 0]),
        ("MoleculeNet", "classification", axes[0, 1]),
        ("TDC ADMET", "regression", axes[1, 0]),
        ("TDC ADMET", "classification", axes[1, 1]),
    ]
    x = np.arange(3)
    labels = ["Random", "Scaffold", "Structure"]
    line_colors = sns.color_palette("tab10", 10)
    for idx, (source, task_type, ax) in enumerate(panels):
        sub = table[(table["source"].eq(source)) & (table["task_type"].eq(task_type))].copy()
        ax.axvspan(0.85, 2.15, color="#f8fafc", zorder=0)
        for i, (_, row) in enumerate(sub.iterrows()):
            y = [row["random_value"], row["scaffold_value"], row["structure_value"]]
            color = line_colors[i % len(line_colors)]
            ax.plot(x, y, marker="o", lw=2.15, ms=6.0, color=color, label=clean_dataset(row["dataset"]))
            final_delta = row["random_to_scaffold_drop"] + row["scaffold_to_structure_drop"]
            if abs(final_delta) >= 0.08:
                ax.annotate(
                    f"{final_delta:+.2f}",
                    xy=(2, y[-1]),
                    xytext=(5, 0),
                    textcoords="offset points",
                    fontsize=7.4,
                    color=COLORS["muted"],
                    va="center",
                )
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        metric = "RMSE" if task_type == "regression" else "ROC-AUC"
        ax.set_ylabel(metric)
        ax.set_title(f"{source} - {task_type}")
        ax.grid(True, axis="y", alpha=0.32)
        ax.legend(fontsize=7.0, loc="best", ncol=1)
        panel_label(ax, chr(ord("A") + idx))
    fig.suptitle("Performance stress test from random to scaffold and structure-separated splits", fontsize=15.5, fontweight="bold")
    save_main(fig, "fig4_split_realism_polished")


def plot_tdc_delta() -> None:
    table = pd.read_csv(TABLE_DIR / "table3_tdc_official_admet.csv")
    rows = []
    for _, row in table.iterrows():
        for model, label in [("lgbm_morgan", "LGBM Morgan"), ("rf_morgan", "RF Morgan")]:
            rows.append(
                {
                    "dataset": clean_dataset(row["dataset"]),
                    "model": label,
                    "drop": row[f"{model}_random_to_scaffold_drop"],
                    "task_type": row["task_type"],
                    "direction": row["direction"],
                }
            )
    df = pd.DataFrame(rows)
    order = df.groupby("dataset")["drop"].mean().sort_values(ascending=True).index.tolist()
    fig, ax = plt.subplots(figsize=(12.2, 6.1))
    sns.barplot(
        data=df,
        y="dataset",
        x="drop",
        hue="model",
        order=order,
        palette=["#2563eb", "#059669"],
        ax=ax,
    )
    ax.axvline(0, color=COLORS["ink"], lw=1.0)
    ax.set_title("Official PyTDC ADMET scaffold penalty by fast tabular baseline", fontsize=14, pad=12)
    ax.set_xlabel("Random-to-scaffold degradation (positive means scaffold split is harder)")
    ax.set_ylabel("")
    ax.legend(title="", loc="lower right")
    for container in ax.containers:
        ax.bar_label(container, fmt="%.3f", fontsize=7.1, padding=2)
    ax.grid(True, axis="x", alpha=0.35)
    ax.text(
        0,
        -0.18,
        "The appendix benchmark is intentionally lightweight: strong tabular baselines expose external-split difficulty without restarting large model training.",
        transform=ax.transAxes,
        fontsize=9.0,
        color=COLORS["muted"],
    )
    save_main(fig, "fig5_tdc_official_split_delta")


def plot_reliability() -> None:
    table = pd.read_csv(TABLE_DIR / "table6_reliability_ad.csv")
    table = table.copy()
    table["label"] = table["score"].str.replace("_", " ", regex=False).str.replace("hybrid", "hybrid ", regex=False)
    family_palette = {
        "reconstruction_unfamiliarity": COLORS["cyan"],
        "unique_style_uq": COLORS["purple"],
    }
    table["family_label"] = table["family"].map(
        {
            "reconstruction_unfamiliarity": "AD / reconstruction",
            "unique_style_uq": "UQ / error model",
        }
    )

    fig, axes = plt.subplots(1, 2, figsize=(14.6, 6.2), gridspec_kw={"width_ratios": [1.05, 1.0]})
    ax = axes[0]
    for family, sub in table.groupby("family"):
        ax.scatter(
            sub["mean_spearman_abs_error"],
            sub["mean_top10pct_high_error_enrichment"],
            s=np.sqrt(sub["n_rows"]) * 42,
            color=family_palette.get(family, "#64748b"),
            alpha=0.82,
            edgecolor="white",
            linewidth=1.0,
            label=sub["family_label"].iloc[0],
        )
        for _, row in sub.iterrows():
            ax.annotate(
                wrap(row["label"], 18),
                (row["mean_spearman_abs_error"], row["mean_top10pct_high_error_enrichment"]),
                xytext=(6, 4),
                textcoords="offset points",
                fontsize=7.6,
                color=COLORS["slate"],
            )
    ax.axhline(1.0, color="#94a3b8", lw=1.0, ls="--")
    ax.set_xlabel("Spearman correlation with absolute error")
    ax.set_ylabel("Top-10% high-error enrichment")
    ax.set_title("High-risk prediction signals")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.32)
    panel_label(ax, "A")

    bar = table.sort_values("mean_risk_coverage_auc", ascending=True)
    y = np.arange(len(bar))
    axes[1].barh(
        y,
        bar["mean_risk_coverage_auc"],
        color=[family_palette.get(f, "#64748b") for f in bar["family"]],
        alpha=0.88,
    )
    axes[1].set_yticks(y)
    axes[1].set_yticklabels([wrap(v, 23) for v in bar["label"]], fontsize=8.3)
    axes[1].set_xlabel("Mean risk-coverage AUC (lower is better)")
    axes[1].set_title("Selective prediction quality")
    axes[1].grid(True, axis="x", alpha=0.32)
    panel_label(axes[1], "B")
    fig.suptitle("Reliability summary: uncertainty and applicability-domain scores", fontsize=15.5, fontweight="bold")
    save_main(fig, "fig6_reliability_summary_polished")


def plot_motif_fragment() -> None:
    motif_path = ROOT / "reports" / "motif_attribution" / "motif_feature_importance.csv"
    frag_path = ROOT / "reports" / "scaffold_fragment_cases" / "scaffold_fragment_label_enrichment.csv"
    motif = pd.read_csv(motif_path)
    frag = pd.read_csv(frag_path)
    datasets = ["bbbp", "bace", "clintox"]

    avg = (
        motif.groupby(["dataset", "feature"], as_index=False)
        .agg(importance=("importance", "mean"), direction=("direction", "mean"), family=("feature_family", "first"))
        .sort_values(["dataset", "importance"], ascending=[True, False])
    )

    fig, axes = plt.subplots(2, 3, figsize=(16.8, 9.0), gridspec_kw={"height_ratios": [1.08, 0.92]})
    for col, dataset in enumerate(datasets):
        ax = axes[0, col]
        sub = avg[avg["dataset"].eq(dataset)].head(9).copy()
        sub["label"] = sub["feature"].map(lambda value: wrap(compact_fragment(value, 30), 18))
        sub = sub.iloc[::-1]
        colors = np.where(sub["direction"] >= 0, COLORS["blue"], COLORS["rose"])
        ax.barh(sub["label"], sub["importance"], color=colors, alpha=0.9)
        ax.set_title(f"{dataset.upper()} motif attribution")
        ax.set_xlabel("Mean importance")
        ax.set_ylabel("")
        ax.grid(True, axis="x", alpha=0.28)
        if col == 0:
            panel_label(ax, "A")

        ax2 = axes[1, col]
        fsub = frag[(frag["dataset"].eq(dataset)) & (frag["kind"].astype(str).str.contains("fragment", na=False))].copy()
        if fsub.empty:
            ax2.axis("off")
            continue
        pos = fsub.sort_values("delta_mean_y", ascending=False).head(4)
        neg = fsub.sort_values("delta_mean_y", ascending=True).head(4)
        plot = pd.concat([neg, pos], ignore_index=True).drop_duplicates("feature")
        plot = plot.sort_values("delta_mean_y")
        plot["label"] = plot["feature"].map(lambda value: wrap(compact_fragment(value, 24), 14))
        colors = np.where(plot["delta_mean_y"] >= 0, COLORS["blue"], COLORS["rose"])
        ax2.barh(plot["label"], plot["delta_mean_y"], color=colors, alpha=0.88)
        ax2.axvline(0, color=COLORS["ink"], lw=0.9)
        ax2.set_title(f"{dataset.upper()} fragment enrichment")
        ax2.set_xlabel("Delta label mean")
        ax2.set_ylabel("")
        ax2.tick_params(axis="y", labelsize=7.0)
        ax2.grid(True, axis="x", alpha=0.28)
        if col == 0:
            panel_label(ax2, "B")

    handles = [
        Rectangle((0, 0), 1, 1, color=COLORS["blue"]),
        Rectangle((0, 0), 1, 1, color=COLORS["rose"]),
    ]
    fig.subplots_adjust(wspace=0.28, hspace=0.30, bottom=0.12, top=0.88)
    fig.legend(handles, ["Positive model direction / enriched label", "Negative model direction / depleted label"], loc="lower center", ncol=2, frameon=False)
    fig.suptitle("Chemical interpretation from motif attribution and fragment-level enrichment", fontsize=15.5, fontweight="bold")
    save_main(fig, "fig11_motif_fragment_interpretation")


def write_index() -> None:
    lines = [
        "# Redrawn Publication Figures",
        "",
        "These files were generated by `scripts/redraw_publication_figures.py` and overwrite the main manuscript figure stems.",
        "",
    ]
    for stem, package_stem in MAIN_FIGURES.items():
        lines.append(f"- `{stem}.png` / `{package_stem}.png`")
    (POLISHED_DIR / "REDRAW_INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    setup_style()
    ensure_dirs()
    plot_framework()
    plot_rank_heatmap()
    plot_main_performance()
    plot_split_realism()
    plot_tdc_delta()
    plot_reliability()
    plot_motif_fragment()
    write_index()
    print(f"Redrawn main figures in {POLISHED_DIR}")
    print(f"Updated stable package figures in {PACKAGE_MAIN_DIR}")


if __name__ == "__main__":
    main()
