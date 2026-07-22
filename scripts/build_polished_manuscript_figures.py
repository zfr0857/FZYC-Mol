from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from rdkit import RDLogger

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import DATASETS  # noqa: E402

RDLogger.DisableLog("rdApp.*")

TABLE_DIR = ROOT / "reports" / "manuscript_tables"
FIG_DIR = ROOT / "reports" / "manuscript_figures_polished"

MOLECULENET = ["esol", "freesolv", "lipo", "bbbp", "bace", "clintox"]
TDC_ADMET = [
    "tdc_caco2_wang",
    "tdc_hia_hou",
    "tdc_pgp_broccatelli",
    "tdc_bioavailability_ma",
    "tdc_bbb_martins",
    "tdc_cyp2c9_veith",
    "tdc_cyp2d6_veith",
    "tdc_cyp3a4_veith",
]

COLORS = {
    "blue": "#2563eb",
    "cyan": "#0891b2",
    "green": "#059669",
    "amber": "#d97706",
    "red": "#dc2626",
    "purple": "#7c3aed",
    "slate": "#334155",
    "gray": "#64748b",
    "light": "#f8fafc",
}


def setup_style() -> None:
    sns.set_theme(style="whitegrid", context="paper", font_scale=1.05)
    plt.rcParams.update(
        {
            "figure.dpi": 140,
            "savefig.dpi": 320,
            "font.family": "DejaVu Sans",
            "axes.titleweight": "bold",
            "axes.labelcolor": "#0f172a",
            "axes.edgecolor": "#cbd5e1",
            "xtick.color": "#334155",
            "ytick.color": "#334155",
            "grid.color": "#e2e8f0",
            "grid.linewidth": 0.8,
            "legend.frameon": True,
            "legend.framealpha": 0.95,
        }
    )


def ensure_dir() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)


def save(fig: plt.Figure, name: str) -> None:
    fig.savefig(FIG_DIR / f"{name}.png", bbox_inches="tight")
    fig.savefig(FIG_DIR / f"{name}.svg", bbox_inches="tight")
    plt.close(fig)


def short_dataset(name: str) -> str:
    return (
        name.replace("tdc_", "")
        .replace("_wang", "")
        .replace("_hou", "")
        .replace("_broccatelli", "")
        .replace("_martins", "")
        .replace("_veith", "")
        .replace("_ma", "")
        .replace("_", " ")
        .upper()
    )


def wrap_label(text: str, width: int = 18) -> str:
    return "\n".join(textwrap.wrap(str(text), width=width, break_long_words=False))


def compact_fragment(text: str, max_len: int = 28) -> str:
    text = str(text).replace("BRICS::", "").replace("[", "").replace("]", "")
    text = text.replace("@@", "@").replace("*", "")
    if len(text) <= max_len:
        return text
    return f"{text[: max_len - 1]}..."


def add_panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(
        -0.08,
        1.08,
        label,
        transform=ax.transAxes,
        fontsize=12,
        fontweight="bold",
        color="#0f172a",
        va="top",
    )


def primary_is_lower(dataset: str) -> bool:
    return DATASETS[dataset].task_type == "regression"


def plot_framework() -> None:
    fig, ax = plt.subplots(figsize=(15, 8))
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    def box(x: float, y: float, w: float, h: float, text: str, color: str, lw: float = 1.6) -> None:
        patch = FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.012,rounding_size=0.018",
            facecolor=color,
            edgecolor="#1e293b",
            linewidth=lw,
        )
        ax.add_patch(patch)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=9.5, color="#0f172a")

    def arrow(x1: float, y1: float, x2: float, y2: float, color: str = "#475569") -> None:
        ax.add_patch(
            FancyArrowPatch(
                (x1, y1),
                (x2, y2),
                arrowstyle="-|>",
                mutation_scale=13,
                linewidth=1.4,
                color=color,
            )
        )

    box(0.03, 0.54, 0.13, 0.18, "Molecular\ninput\nSMILES / graph", "#e0f2fe")
    box(0.22, 0.71, 0.17, 0.13, "Graph view\natoms, bonds,\nscaffold", "#dbeafe")
    box(0.22, 0.52, 0.17, 0.13, "Fingerprint view\nMorgan, MACCS,\natom-pair, torsion", "#dcfce7")
    box(0.22, 0.33, 0.17, 0.13, "Descriptor view\nRDKit 2D\nphyschem", "#fef3c7")
    box(0.22, 0.14, 0.17, 0.13, "Language view\nChemBERTa\nMoLFormer", "#ede9fe")

    box(0.48, 0.74, 0.16, 0.10, "GNN / D-MPNN\nGIN, Chemprop", "#dbeafe")
    box(0.48, 0.59, 0.16, 0.10, "Tree experts\nRF, XGB, LGBM,\nExtraTrees", "#dcfce7")
    box(0.48, 0.44, 0.16, 0.10, "Descriptor MLP\nfastprop-like", "#fef3c7")
    box(0.48, 0.29, 0.16, 0.10, "Motif experts\nBRICS, Murcko,\nfunctional groups", "#fee2e2")
    box(0.48, 0.14, 0.16, 0.10, "Frozen encoders\nembedding heads", "#ede9fe")

    box(0.72, 0.58, 0.19, 0.18, "Validation-only\nstrategy selector\nbest expert / stack /\nadaptive / consensus", "#f1f5f9", lw=2.0)
    box(0.72, 0.31, 0.19, 0.16, "Reliability layer\nuncertainty, AD,\nreconstruction\nunfamiliarity", "#ecfeff", lw=2.0)
    box(0.72, 0.10, 0.19, 0.12, "Outputs\nprediction + risk flag\n+ motif explanation", "#f0fdf4", lw=2.0)

    for y in [0.775, 0.585, 0.395, 0.205]:
        arrow(0.16, 0.63, 0.22, y)
    for y in [0.79, 0.64, 0.49, 0.34, 0.19]:
        arrow(0.39, y, 0.48, y)
        arrow(0.64, y, 0.72, 0.67)
    arrow(0.82, 0.58, 0.82, 0.47)
    arrow(0.82, 0.31, 0.82, 0.22)

    ax.text(
        0.5,
        0.94,
        "FZYC-Mol: validation-selected molecular prediction with reliability diagnostics",
        ha="center",
        fontsize=15,
        fontweight="bold",
        color="#0f172a",
    )
    ax.text(
        0.5,
        0.90,
        "All strategy choices use validation predictions only; test labels are reserved for final reporting.",
        ha="center",
        fontsize=10,
        color="#475569",
    )
    ax.text(
        0.5,
        0.02,
        "Evaluation axes: MoleculeNet | TDC ADMET | official PyTDC splits | random/scaffold/structure-separated splits | "
        "low-similarity subsets | MoleculeACE activity cliffs | calibration and enrichment",
        ha="center",
        fontsize=9,
        color="#334155",
    )
    save(fig, "fig1_framework_overview_polished")


def plot_performance_heatmap() -> None:
    table = pd.read_csv(TABLE_DIR / "table2_moleculenet_main_long.csv")
    table = table[~table["category"].eq("Best observed candidate")].copy()
    rows = []
    for dataset, sub in table.groupby("dataset"):
        ascending = sub["direction"].iloc[0] == "lower"
        sub = sub.copy()
        sub["rank"] = sub["value"].rank(ascending=ascending, method="min")
        rows.append(sub)
    ranked = pd.concat(rows, ignore_index=True)
    order = [
        "Classical Morgan",
        "Graph / D-MPNN core",
        "Chemprop",
        "Frozen pretrained",
        "Multi-fingerprint",
        "Descriptor / motif",
        "FZYC-Mol validation selector",
        "FZYC-Mol targeted rescue selector",
    ]
    pivot = ranked.pivot_table(index="dataset", columns="category", values="rank", aggfunc="min")
    pivot = pivot.reindex(index=["esol", "freesolv", "lipo", "bbbp", "bace", "clintox"], columns=[c for c in order if c in pivot.columns])
    annot = pivot.map(lambda x: "" if pd.isna(x) else f"{int(x)}")

    fig, ax = plt.subplots(figsize=(12.5, 5.8))
    sns.heatmap(
        pivot,
        annot=annot,
        fmt="",
        cmap=sns.color_palette("YlGnBu_r", as_cmap=True),
        linewidths=0.8,
        linecolor="white",
        cbar_kws={"label": "Family rank within endpoint"},
        ax=ax,
    )
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_title("Model-family ranks reveal endpoint-specific winners")
    ax.set_xticklabels([wrap_label(t.get_text(), 16) for t in ax.get_xticklabels()], rotation=0)
    ax.set_yticklabels([t.get_text().upper() for t in ax.get_yticklabels()], rotation=0)
    ax.text(
        0,
        -0.22,
        "Rank 1 is best within each dataset. The selector remains near the top without using test labels for strategy selection.",
        transform=ax.transAxes,
        fontsize=9,
        color="#475569",
    )
    save(fig, "fig2_moleculenet_rank_heatmap_polished")


def plot_main_performance_dots() -> None:
    table = pd.read_csv(TABLE_DIR / "table2_moleculenet_main_long.csv")
    keep = [
        "FZYC-Mol validation selector",
        "FZYC-Mol targeted rescue selector",
        "Classical Morgan",
        "Chemprop",
        "Graph / D-MPNN core",
        "Multi-fingerprint",
        "Frozen pretrained",
    ]
    table = table[table["category"].isin(keep)].copy()
    table["dataset_label"] = table["dataset"].str.upper()
    palette = dict(zip(keep, sns.color_palette("Set2", len(keep))))
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.4), gridspec_kw={"width_ratios": [1, 1]})
    for ax, task_type, title, xlabel in [
        (axes[0], "regression", "Regression endpoints", "RMSE (lower is better)"),
        (axes[1], "classification", "Classification endpoints", "ROC-AUC (higher is better)"),
    ]:
        sub = table[table["task_type"].eq(task_type)].copy()
        y_order = list(reversed(sub["dataset_label"].drop_duplicates().tolist()))
        for cat in keep:
            csub = sub[sub["category"].eq(cat)]
            ax.scatter(
                csub["value"],
                csub["dataset_label"],
                s=70,
                label=cat,
                color=palette[cat],
                edgecolor="white",
                linewidth=0.7,
                alpha=0.95,
            )
            for _, r in csub.iterrows():
                if r["category"] == "FZYC-Mol validation selector":
                    ax.errorbar(
                        r["value"],
                        r["dataset_label"],
                        xerr=r["std"],
                        fmt="none",
                        ecolor="#0f172a",
                        elinewidth=1.2,
                        capsize=3,
                    )
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("")
        ax.set_yticks(y_order)
        ax.grid(True, axis="x", alpha=0.35)
    axes[1].legend(loc="center left", bbox_to_anchor=(1.02, 0.5), title="Model family")
    fig.suptitle("Main MoleculeNet performance by model family", fontsize=14, fontweight="bold")
    save(fig, "fig3_moleculenet_performance_dots")


def plot_split_realism() -> None:
    table = pd.read_csv(TABLE_DIR / "table4_split_realism.csv")
    fig, axes = plt.subplots(2, 2, figsize=(14, 8), sharex=True)
    panels = [
        ("MoleculeNet", "regression", axes[0, 0]),
        ("MoleculeNet", "classification", axes[0, 1]),
        ("TDC ADMET", "regression", axes[1, 0]),
        ("TDC ADMET", "classification", axes[1, 1]),
    ]
    x = np.arange(3)
    xlabels = ["Random", "Scaffold", "Structure"]
    palette = sns.color_palette("tab10", 10)
    for idx, (source, task_type, ax) in enumerate(panels):
        sub = table[(table["source"].eq(source)) & (table["task_type"].eq(task_type))]
        for i, (_, r) in enumerate(sub.iterrows()):
            y = [r["random_value"], r["scaffold_value"], r["structure_value"]]
            label = short_dataset(r["dataset"])
            ax.plot(x, y, marker="o", lw=2.1, ms=6, label=label, color=palette[i % len(palette)])
            drop = r["random_to_scaffold_drop"] + r["scaffold_to_structure_drop"]
            if drop > 0:
                ax.annotate(
                    f"drop {drop:.3f}",
                    xy=(2, y[-1]),
                    xytext=(6, 0),
                    textcoords="offset points",
                    fontsize=7.5,
                    color="#475569",
                )
        metric = "RMSE" if task_type == "regression" else "ROC-AUC"
        ax.set_title(f"{source}: {task_type}")
        ax.set_ylabel(metric)
        ax.set_xticks(x)
        ax.set_xticklabels(xlabels)
        ax.grid(True, alpha=0.30)
        if len(sub) <= 7:
            ax.legend(fontsize=7, loc="best")
        add_panel_label(ax, chr(ord("A") + idx))
    fig.suptitle("Split realism: performance shifts from random to structure-separated splits", fontsize=15, fontweight="bold")
    save(fig, "fig4_split_realism_polished")


def plot_tdc_official_delta() -> None:
    table = pd.read_csv(TABLE_DIR / "table3_tdc_official_admet.csv")
    rows = []
    for _, r in table.iterrows():
        for model, label in [("lgbm_morgan", "LGBM"), ("rf_morgan", "RF")]:
            rows.append(
                {
                    "dataset": short_dataset(r["dataset"]),
                    "model": label,
                    "drop": r[f"{model}_random_to_scaffold_drop"],
                    "task_type": r["task_type"],
                    "metric": r["primary_metric"].upper(),
                }
            )
    df = pd.DataFrame(rows)
    order = (
        df.groupby("dataset")["drop"].mean().sort_values(ascending=False).index.tolist()
    )
    fig, ax = plt.subplots(figsize=(11.5, 5.6))
    sns.barplot(data=df, y="dataset", x="drop", hue="model", order=order, palette=[COLORS["blue"], COLORS["green"]], ax=ax)
    ax.axvline(0, color="#0f172a", lw=1)
    ax.set_xlabel("Random-to-scaffold degradation\n(positive = scaffold split is harder)")
    ax.set_ylabel("")
    ax.set_title("Official PyTDC ADMET splits expose endpoint-dependent scaffold degradation")
    ax.legend(title="")
    for container in ax.containers:
        ax.bar_label(container, fmt="%.3f", fontsize=7, padding=2)
    save(fig, "fig5_tdc_official_split_delta")


def plot_reliability_summary() -> None:
    table = pd.read_csv(TABLE_DIR / "table6_reliability_ad.csv")
    table = table[table["family"].isin(["reconstruction_unfamiliarity", "unique_style_uq"])].copy()
    table["mean_spearman_abs_error"] = pd.to_numeric(table["mean_spearman_abs_error"], errors="coerce")
    table["mean_top10pct_high_error_enrichment"] = pd.to_numeric(table["mean_top10pct_high_error_enrichment"], errors="coerce")
    table = table.dropna(subset=["mean_spearman_abs_error"])
    table["label"] = table["score"].str.replace("_", " ", regex=False)
    table = table.sort_values("mean_spearman_abs_error", ascending=True)

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 6.2), sharey=True)
    sns.barplot(data=table, y="label", x="mean_spearman_abs_error", hue="family", dodge=False, ax=axes[0])
    axes[0].set_xlabel("Mean Spearman with absolute error")
    axes[0].set_ylabel("")
    axes[0].set_title("Error-risk correlation")
    axes[0].legend_.remove()
    sns.barplot(data=table, y="label", x="mean_top10pct_high_error_enrichment", hue="family", dodge=False, ax=axes[1])
    axes[1].axvline(1, color="#0f172a", lw=1, ls="--")
    axes[1].set_xlabel("Top-10% high-error enrichment")
    axes[1].set_ylabel("")
    axes[1].set_title("High-error enrichment")
    axes[1].legend(title="Score family", loc="lower right")
    fig.suptitle("Reliability signals identify high-risk molecular predictions", fontsize=15, fontweight="bold")
    save(fig, "fig6_reliability_summary_polished")


def plot_risk_coverage_curves() -> None:
    curves = pd.read_csv(ROOT / "reports" / "unique_uq_plus_descriptor_motif" / "risk_coverage_curves.csv")
    keep_scores = ["error_model", "ensemble_std", "hybrid_error_ad", "inverse_tanimoto"]
    keep_datasets = ["bace", "bbbp", "esol", "lipo"]
    curves = curves[curves["uq_score"].isin(keep_scores) & curves["dataset"].isin(keep_datasets)].copy()
    mean = curves.groupby(["dataset", "uq_score", "coverage"], as_index=False)["risk"].mean()
    score_labels = {
        "error_model": "Error model",
        "ensemble_std": "Ensemble std",
        "hybrid_error_ad": "Hybrid UQ+AD",
        "inverse_tanimoto": "Inverse Tanimoto",
    }
    mean["score_label"] = mean["uq_score"].map(score_labels)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
    for ax, dataset in zip(axes.ravel(), keep_datasets):
        sub = mean[mean["dataset"].eq(dataset)]
        sns.lineplot(data=sub, x="coverage", y="risk", hue="score_label", marker="o", ax=ax)
        ax.set_title(dataset.upper())
        ax.set_xlabel("Coverage retained")
        ax.set_ylabel("Risk")
        ax.grid(True, alpha=0.35)
        if dataset != "lipo":
            ax.legend_.remove()
        else:
            ax.legend(title="", loc="best", fontsize=8)
    fig.suptitle("Risk-coverage curves across representative endpoints", fontsize=15, fontweight="bold")
    save(fig, "fig7_risk_coverage_curves")


def plot_calibration_curves() -> None:
    bins = pd.read_csv(ROOT / "reports" / "uncertainty_ad_expanded" / "calibration_bins.csv")
    datasets = ["bace", "bbbp", "clintox"]
    bins = bins[bins["dataset"].isin(datasets)].copy()
    mean = bins.groupby(["dataset", "bin"], as_index=False).agg(
        confidence=("confidence", "mean"),
        observed_positive_rate=("observed_positive_rate", "mean"),
        n=("n", "sum"),
    )
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.6), sharex=True, sharey=True)
    for ax, dataset in zip(axes, datasets):
        sub = mean[mean["dataset"].eq(dataset)]
        ax.plot([0, 1], [0, 1], color="#94a3b8", ls="--", lw=1.4, label="Perfect calibration")
        ax.scatter(
            sub["confidence"],
            sub["observed_positive_rate"],
            s=np.clip(sub["n"], 20, 180),
            color=COLORS["blue"],
            alpha=0.78,
            edgecolor="white",
            linewidth=0.7,
        )
        ax.plot(sub["confidence"], sub["observed_positive_rate"], color=COLORS["blue"], lw=1.8)
        ax.set_title(dataset.upper())
        ax.set_xlabel("Predicted probability")
        ax.grid(True, alpha=0.3)
    axes[0].set_ylabel("Observed positive rate")
    axes[0].legend(loc="upper left", fontsize=8)
    fig.suptitle("Calibration curves for classification endpoints", fontsize=15, fontweight="bold")
    save(fig, "fig8_calibration_curves")


def plot_ablation_significance() -> None:
    table = pd.read_csv(TABLE_DIR / "table5_ablation_significance.csv")
    fam = table[table["section"].eq("family_ablation")].copy()
    fam = fam.sort_values("mean_positive_delta", ascending=True)
    base = table[table["section"].eq("selector_vs_baseline")].copy().head(12)
    base["comparison_short"] = (
        base["comparison"]
        .str.replace("strict_core_fast::", "", regex=False)
        .str.replace("strict_multifp_fast::", "", regex=False)
        .str.replace("chemprop_baseline::", "", regex=False)
        .str.replace("pretrained_frozen_molformer::", "molformer::", regex=False)
        .str.replace("pretrained_frozen_mlm::", "chemberta_mlm::", regex=False)
        .str.replace("pretrained_frozen::", "chemberta_mtr::", regex=False)
    )
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.4))
    sns.barplot(
        data=fam,
        y="comparison",
        x="mean_positive_delta",
        hue="comparison",
        palette="vlag",
        legend=False,
        ax=axes[0],
    )
    axes[0].axvline(0, color="#0f172a", lw=1)
    axes[0].set_xlabel("Mean positive delta vs ablation")
    axes[0].set_ylabel("")
    axes[0].set_title("Family ablation")

    y = np.arange(len(base))
    left = np.zeros(len(base))
    for col, color, label in [
        ("wins", COLORS["green"], "Wins"),
        ("ties", COLORS["gray"], "Ties"),
        ("losses", COLORS["red"], "Losses"),
    ]:
        axes[1].barh(y, base[col], left=left, color=color, label=label)
        left += base[col].to_numpy()
    axes[1].set_yticks(y)
    axes[1].set_yticklabels([wrap_label(v, 28) for v in base["comparison_short"]], fontsize=8)
    axes[1].invert_yaxis()
    axes[1].set_xlabel("Dataset count")
    axes[1].set_title("Selector vs individual baselines")
    axes[1].legend(loc="lower right")
    fig.suptitle("Ablation and win/tie/loss evidence", fontsize=15, fontweight="bold")
    save(fig, "fig9_ablation_significance")


def plot_selector_map() -> None:
    frames = []
    for source, path in [
        ("MoleculeNet", ROOT / "reports" / "validation_selector_expanded" / "selected_candidates.csv"),
        ("TDC ADMET", ROOT / "reports" / "validation_selector_tdc_admet" / "selected_candidates.csv"),
    ]:
        frame = pd.read_csv(path)
        frame["source"] = source
        frames.append(frame)
    selected = pd.concat(frames, ignore_index=True)

    def strategy(candidate: str) -> str:
        if str(candidate).startswith("stack"):
            return "stacking"
        if str(candidate).startswith("adaptive"):
            return "adaptive"
        if str(candidate).startswith("consensus"):
            return "consensus"
        return "best expert"

    def family(candidate: str) -> str:
        c = str(candidate)
        if "multifp" in c:
            return "multi-fingerprint"
        if "chemprop" in c:
            return "Chemprop"
        if "chemberta" in c or "molformer" in c:
            return "pretrained"
        if "q1_all" in c:
            return "all experts"
        return "core"

    selected["strategy"] = selected["selected_candidate"].map(strategy)
    selected["family"] = selected["selected_candidate"].map(family)
    selected["dataset_label"] = selected["dataset"].map(short_dataset)
    strategy_colors = {"adaptive": COLORS["blue"], "stacking": COLORS["purple"], "consensus": COLORS["green"], "best expert": COLORS["gray"]}
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), gridspec_kw={"width_ratios": [1.35, 1]})
    y = np.arange(len(selected))
    axes[0].barh(y, np.ones(len(selected)), color=[strategy_colors[s] for s in selected["strategy"]], edgecolor="white")
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(selected["dataset_label"])
    axes[0].set_xticks([])
    axes[0].invert_yaxis()
    axes[0].set_title("Validation-selected strategy by dataset")
    for i, r in selected.iterrows():
        axes[0].text(0.02, i, f"{r['strategy']} | {r['family']}", va="center", ha="left", fontsize=8.2, color="white")
    counts = selected.groupby(["source", "strategy"]).size().reset_index(name="count")
    sns.barplot(data=counts, x="strategy", y="count", hue="source", ax=axes[1], palette=[COLORS["blue"], COLORS["amber"]])
    axes[1].set_xlabel("")
    axes[1].set_ylabel("Number of datasets")
    axes[1].set_title("Strategy usage")
    axes[1].tick_params(axis="x", rotation=25)
    fig.suptitle("The selector chooses different strategies for different endpoint families", fontsize=15, fontweight="bold")
    save(fig, "fig10_validation_selector_map")


def plot_motif_and_fragments() -> None:
    motif = pd.read_csv(ROOT / "reports" / "motif_attribution" / "motif_feature_importance.csv")
    avg = (
        motif.groupby(["dataset", "feature"], as_index=False)
        .agg(importance=("importance", "mean"), direction=("direction", "mean"))
        .sort_values(["dataset", "importance"], ascending=[True, False])
    )
    datasets = ["bbbp", "bace", "clintox"]
    fig, axes = plt.subplots(2, 3, figsize=(16, 9), gridspec_kw={"height_ratios": [1.15, 0.85]})
    for ax, dataset in zip(axes[0], datasets):
        sub = avg[avg["dataset"].eq(dataset)].head(8).copy()
        sub["label"] = (
            sub["feature"]
            .str.replace("FG::", "", regex=False)
            .str.replace("BRICS::", "", regex=False)
            .map(lambda x: wrap_label(x, 18))
        )
        colors = np.where(sub["direction"] >= 0, COLORS["blue"], COLORS["red"])
        ax.barh(sub["label"], sub["importance"], color=colors)
        ax.invert_yaxis()
        ax.set_title(f"{dataset.upper()} motif importance")
        ax.set_xlabel("Importance")
    frag = pd.read_csv(ROOT / "reports" / "scaffold_fragment_cases" / "scaffold_fragment_label_enrichment.csv")
    for ax, dataset in zip(axes[1], datasets):
        sub = frag[(frag["dataset"].eq(dataset)) & (frag["kind"].str.contains("fragment", na=False))].copy()
        if sub.empty:
            ax.axis("off")
            continue
        pos = sub.sort_values("delta_mean_y", ascending=False).head(4)
        neg = sub.sort_values("delta_mean_y", ascending=True).head(4)
        plot = pd.concat([neg, pos]).drop_duplicates("feature")
        plot["label"] = [
            f"frag {i + 1}: {compact_fragment(feature, 24)}"
            for i, feature in enumerate(plot["feature"].tolist())
        ]
        colors = np.where(plot["delta_mean_y"] >= 0, COLORS["blue"], COLORS["red"])
        ax.barh(plot["label"], plot["delta_mean_y"], color=colors)
        ax.axvline(0, color="#0f172a", lw=1)
        ax.set_title(f"{dataset.upper()} fragment enrichment")
        ax.set_xlabel("Delta label mean")
    fig.suptitle("Motif attribution and fragment-level chemical interpretation", fontsize=15, fontweight="bold")
    save(fig, "fig11_motif_fragment_interpretation")


def plot_conformal_coverage() -> None:
    conformal = pd.read_csv(ROOT / "reports" / "conformal_activity" / "conformal_summary.csv")
    conformal["dataset_label"] = conformal["dataset"].str.upper()
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))
    sns.boxplot(data=conformal, x="dataset_label", y="coverage", hue="task_type", ax=axes[0], palette=[COLORS["green"], COLORS["blue"]])
    sns.stripplot(data=conformal, x="dataset_label", y="coverage", ax=axes[0], color="#0f172a", size=3, alpha=0.45)
    axes[0].axhline(0.9, color=COLORS["red"], ls="--", lw=1.5, label="Nominal 90%")
    axes[0].set_xlabel("")
    axes[0].set_ylabel("Coverage")
    axes[0].set_title("Conformal coverage")
    axes[0].tick_params(axis="x", rotation=35)
    axes[0].legend(loc="lower right", fontsize=8)

    if "mean_width" in conformal.columns:
        reg = conformal[conformal["task_type"].eq("regression")].copy()
        if not reg.empty:
            sns.boxplot(data=reg, x="dataset_label", y="mean_width", ax=axes[1], color=COLORS["amber"])
            sns.stripplot(data=reg, x="dataset_label", y="mean_width", ax=axes[1], color="#0f172a", size=3, alpha=0.45)
    axes[1].set_xlabel("")
    axes[1].set_ylabel("Mean interval width")
    axes[1].set_title("Regression conformal interval width")
    axes[1].tick_params(axis="x", rotation=35)
    fig.suptitle("Conformal diagnostics quantify prediction-set reliability", fontsize=15, fontweight="bold")
    save(fig, "fig12_conformal_diagnostics")


def plot_efficiency_tradeoff() -> None:
    table = pd.read_csv(TABLE_DIR / "table7_efficiency.csv")
    table["mean_fit_seconds"] = pd.to_numeric(table["mean_fit_seconds"], errors="coerce")
    table["mean_predict_seconds"] = pd.to_numeric(table["mean_predict_seconds"], errors="coerce")
    table["primary_mean_median"] = pd.to_numeric(table["primary_mean_median"], errors="coerce")
    plot = table.dropna(subset=["mean_fit_seconds", "mean_predict_seconds", "primary_mean_median"]).copy()
    plot["label"] = plot["report"] + "\n" + plot["model_family"].str.replace(" baseline", "", regex=False)
    fig, ax = plt.subplots(figsize=(10, 6))
    sizes = np.clip(plot["n_metric_rows"].astype(float), 20, 260)
    scatter = ax.scatter(
        plot["mean_fit_seconds"],
        plot["primary_mean_median"],
        s=sizes,
        c=plot["mean_predict_seconds"],
        cmap="viridis",
        edgecolor="white",
        linewidth=0.9,
    )
    for _, r in plot.iterrows():
        ax.annotate(wrap_label(r["report"], 16), (r["mean_fit_seconds"], r["primary_mean_median"]), xytext=(5, 3), textcoords="offset points", fontsize=8)
    ax.set_xlabel("Mean fit time (seconds)")
    ax.set_ylabel("Median primary performance summary")
    ax.set_title("Efficiency-performance tradeoff for practical CPU baselines")
    cbar = fig.colorbar(scatter, ax=ax)
    cbar.set_label("Mean prediction time (seconds)")
    ax.grid(True, alpha=0.35)
    save(fig, "fig13_efficiency_tradeoff")


def plot_enrichment_and_cliffs() -> None:
    enrich = pd.read_csv(ROOT / "reports" / "classification_enrichment" / "classification_enrichment_raw.csv")
    selector = enrich[enrich["source"].eq("validation_selector_expanded")].copy()
    enrich_summary = selector.groupby("dataset", as_index=False).agg(
        ef1=("ef1", "mean"),
        ef5=("ef5", "mean"),
        bedroc20=("bedroc20", "mean"),
        pr_auc=("pr_auc", "mean"),
    )
    cliff = pd.read_csv(ROOT / "reports" / "conformal_activity" / "activity_cliff_summary.csv")
    cliff_summary = cliff.groupby("dataset", as_index=False).agg(
        direction_accuracy=("direction_accuracy", "mean"),
        n_cliffs=("n_cliffs", "sum"),
    )
    cliff_summary = cliff_summary[cliff_summary["n_cliffs"] > 0]

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.4))
    enrich_plot = enrich_summary.melt(id_vars="dataset", value_vars=["ef1", "ef5"], var_name="metric", value_name="value")
    sns.barplot(data=enrich_plot, x="dataset", y="value", hue="metric", ax=axes[0], palette=[COLORS["purple"], COLORS["cyan"]])
    axes[0].set_xlabel("")
    axes[0].set_ylabel("Enrichment factor")
    axes[0].set_title("Early enrichment for selector predictions")
    axes[0].tick_params(axis="x", rotation=35)
    axes[0].legend(title="")

    if not cliff_summary.empty:
        sns.barplot(data=cliff_summary, x="dataset", y="direction_accuracy", ax=axes[1], color=COLORS["green"])
        axes[1].set_ylim(0, 1.05)
        axes[1].set_xlabel("")
        axes[1].set_ylabel("Direction accuracy")
        axes[1].set_title("Activity-cliff direction accuracy")
        axes[1].tick_params(axis="x", rotation=35)
        for container in axes[1].containers:
            axes[1].bar_label(container, fmt="%.2f", fontsize=8)
    fig.suptitle("Screening-relevant enrichment and activity-cliff behavior", fontsize=15, fontweight="bold")
    save(fig, "fig14_enrichment_activity_cliffs")


def write_index() -> None:
    lines = ["# Polished Manuscript Figure Index", ""]
    for path in sorted(FIG_DIR.glob("*.png")):
        lines.append(f"- `{path.name}`")
    (FIG_DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    setup_style()
    ensure_dir()
    plot_framework()
    plot_performance_heatmap()
    plot_main_performance_dots()
    plot_split_realism()
    plot_tdc_official_delta()
    plot_reliability_summary()
    plot_risk_coverage_curves()
    plot_calibration_curves()
    plot_ablation_significance()
    plot_selector_map()
    plot_motif_and_fragments()
    plot_conformal_coverage()
    plot_efficiency_tradeoff()
    plot_enrichment_and_cliffs()
    write_index()
    print(f"Generated polished manuscript figures in {FIG_DIR}")


if __name__ == "__main__":
    main()
