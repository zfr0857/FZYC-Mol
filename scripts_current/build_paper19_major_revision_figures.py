from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, Rectangle


ROOT = Path("D:/fzyc")
MAJOR = ROOT / "output" / "paper19_major_revision_20260712"
PREV = ROOT / "output" / "paper19_rejection_driven_experiments_20260712"
REV = ROOT / "output" / "paper19_jcheminformatics_revision_20260712"
HARD = ROOT / "output" / "sci1_hardening_20260707"
UQ = ROOT / "output" / "sci1_mechanism_uq_decision_20260707"
MULTI = ROOT / "results" / "reviewer_core_20260624" / "multiview_nested"
FIG = MAJOR / "figures"

BLUE = "#356FAE"
ORANGE = "#D77A31"
TEAL = "#2A8C82"
RED = "#B94C4C"
GREY = "#727B86"
LIGHT = "#D9DEE5"
INK = "#202833"


def setup() -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8.2,
            "axes.titlesize": 8.8,
            "axes.labelsize": 8.3,
            "xtick.labelsize": 7.4,
            "ytick.labelsize": 7.4,
            "legend.fontsize": 7.1,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
        }
    )


def letter(ax: plt.Axes, label: str) -> None:
    ax.text(-0.24, 1.08, label, transform=ax.transAxes, fontsize=10.0, fontweight="bold", va="top")


def save(fig: plt.Figure, stem: str) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{stem}.png", dpi=600, bbox_inches="tight", facecolor="white")
    fig.savefig(FIG / f"{stem}.svg", bbox_inches="tight", facecolor="white")
    fig.savefig(FIG / f"{stem}.pdf", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def box(ax: plt.Axes, x: float, y: float, w: float, h: float, text: str, color: str, fontsize: float = 7.2) -> None:
    ax.add_patch(Rectangle((x, y), w, h, facecolor="white", edgecolor=color, linewidth=1.2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", color=INK, fontsize=fontsize)


def arrow(ax: plt.Axes, x1: float, y1: float, x2: float, y2: float) -> None:
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=9, color=GREY, lw=1.0))


def figure1() -> None:
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 4.8))
    for ax in axes.flat:
        ax.set_axis_off()

    ax = axes[0, 0]
    letter(ax, "A")
    ax.set_title("Retrospective frozen audit", loc="left")
    box(ax, 0.03, 0.56, 0.26, 0.18, "Candidate\nregistry", BLUE, 5.8)
    box(ax, 0.37, 0.56, 0.26, 0.18, "Nested\nselection", TEAL, 5.8)
    box(ax, 0.71, 0.56, 0.26, 0.18, "Outer-\naudit", ORANGE, 5.8)
    arrow(ax, 0.29, 0.65, 0.37, 0.65)
    arrow(ax, 0.63, 0.65, 0.71, 0.65)
    ax.text(0.50, 0.28, "Retrospective analysis lock", ha="center", fontweight="bold")
    ax.text(0.50, 0.16, "No outer-label feedback", ha="center", color=GREY, fontsize=7.0)

    ax = axes[0, 1]
    letter(ax, "B")
    ax.set_title("Registered pool expansion", loc="left")
    for i, (k, width) in enumerate(zip([4, 8, 16, 32], [0.22, 0.38, 0.62, 0.88])):
        y = 0.77 - i * 0.17
        ax.add_patch(Rectangle((0.06, y), width, 0.09, facecolor=BLUE, alpha=0.75))
        ax.text(0.08, y + 0.045, f"K = {k}", va="center", color="white", fontweight="bold")
    ax.text(0.06, 0.08, "Per-candidate opportunity fixed;\ntotal search exposure increased with K", color=GREY, fontsize=6.8)

    ax = axes[0, 2]
    letter(ax, "C")
    ax.set_title("Repeated nested scaffold design", loc="left")
    for i, (label, value, color) in enumerate([("Outer folds", "3", ORANGE), ("Inner folds", "3", TEAL), ("Seeds", "5", BLUE)]):
        y = 0.72 - i * 0.19
        box(ax, 0.08, y, 0.48, 0.12, label, color)
        ax.text(0.70, y + 0.06, value, va="center", fontweight="bold", color=color, fontsize=9)
    ax.text(0.08, 0.10, "15 outer-utility rows per endpoint", color=GREY, fontsize=6.8)

    ax = axes[1, 0]
    letter(ax, "D")
    ax.set_title("Joint reporting targets", loc="left")
    items = [
        ("Nominal K and effective diversity", BLUE),
        ("Chance-adjusted ranking fidelity", TEAL),
        ("Endpoint-specific raw loss", RED),
        ("Compute exposure and failures", ORANGE),
    ]
    for i, (text, color) in enumerate(items):
        y = 0.75 - i * 0.18
        ax.add_patch(Rectangle((0.06, y), 0.045, 0.045, color=color))
        ax.text(0.14, y + 0.022, text, va="center", fontsize=7.2)

    ax = axes[1, 1]
    letter(ax, "E")
    ax.set_title("Evidence hierarchy", loc="left")
    labels = [
        ("Primary: near-duplicate\nexpansion audit", BLUE),
        ("Shared-split multiview\nstress test", TEAL),
        ("Limited representation-\nbaseline stress test", ORANGE),
        ("Reliability and\nchemical boundaries", GREY),
    ]
    for i, (text, color) in enumerate(labels):
        y = 0.73 - i * 0.18
        ax.add_patch(Rectangle((0.10, y), 0.80, 0.12, color=color, alpha=0.78))
        ax.text(0.50, y + 0.06, text, ha="center", va="center", color="white", fontsize=6.5, fontweight="bold")

    ax = axes[1, 2]
    letter(ax, "F")
    ax.set_title("Interpretation boundaries", loc="left")
    box(ax, 0.05, 0.60, 0.38, 0.15, "Observed\nouter best", ORANGE)
    ax.text(0.50, 0.675, r"$\ne$", ha="center", va="center", color=RED, fontweight="bold", fontsize=9)
    box(ax, 0.58, 0.60, 0.35, 0.15, "True\nupper bound", RED)
    box(ax, 0.05, 0.28, 0.38, 0.15, "Outer-\naudit", ORANGE)
    ax.text(0.50, 0.355, r"$\ne$", ha="center", va="center", color=RED, fontweight="bold", fontsize=9)
    box(ax, 0.58, 0.28, 0.35, 0.15, "Independent\nconfirmation", RED, 6.5)
    fig.subplots_adjust(wspace=0.36, hspace=0.35)
    save(fig, "Figure_1_major_revision_workflow")


def figure2() -> None:
    div = pd.read_csv(MAJOR / "effective_diversity_shrinkage_summary.csv")
    endpoint_div = pd.read_csv(MAJOR / "effective_diversity_shrinkage_endpoint.csv")
    ranking = pd.read_csv(MAJOR / "chance_adjusted_ranking_summary.csv")
    loss = pd.read_csv(MAJOR / "selection_loss_seed_clustered.csv")
    controls = pd.read_csv(REV / "candidate_composition_controls.csv")
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 5.2))

    ax = axes[0, 0]
    letter(ax, "A")
    y = div["mean_shrinkage_entropy_rank"]
    ax.errorbar(div["candidate_count"], y, yerr=[y - div["hierarchical_ci95_low_entropy"], div["hierarchical_ci95_high_entropy"] - y], marker="o", color=TEAL, capsize=2, label="Shrinkage entropy rank")
    empirical = pd.read_csv(PREV / "paper19_effective_diversity.csv").groupby("candidate_count")["outer_entropy_effective_rank"].mean()
    ax.plot(empirical.index, empirical.values, marker="s", color=GREY, ls="--", label="Empirical entropy rank")
    ax.plot([4, 8, 16, 32], [4, 8, 16, 32], color=LIGHT, ls=":", label="Nominal K")
    ax.set(xlabel="Candidate count, K", ylabel="Effective rank", xticks=[4, 8, 16, 32])
    ax.set_title("Effective diversity\nwith uncertainty", loc="left")
    ax.legend(frameon=False, fontsize=5.8)

    ax = axes[0, 1]
    letter(ax, "B")
    y = div["mean_shrinkage_median_correlation"]
    ax.errorbar(div["candidate_count"], y, yerr=[y - div["hierarchical_ci95_low_correlation"], div["hierarchical_ci95_high_correlation"] - y], marker="o", color=ORANGE, capsize=2)
    ax.set(xlabel="Candidate count, K", ylabel="Median utility correlation", xticks=[4, 8, 16, 32], ylim=(0.35, 1.0))
    ax.set_title("Shrinkage candidate\ncorrelation", loc="left")

    ax = axes[0, 2]
    letter(ax, "C")
    ax.plot(ranking["candidate_count"], ranking["mean_chance_adjusted_top3"], marker="o", color=BLUE, label="CAHit@3")
    ax.plot(ranking["candidate_count"], ranking["mean_normalized_mrr_gain"], marker="s", color=TEAL, label="Normalized MRR gain")
    ax.axhline(0, color=GREY, lw=0.7)
    ax.set(xlabel="Candidate count, K", ylabel="Chance-adjusted fidelity", xticks=[4, 8, 16, 32], ylim=(-0.05, 1.0))
    ax.set_title("Chance-adjusted\nranking fidelity", loc="left")
    ax.legend(frameon=False)

    ax = axes[1, 0]
    letter(ax, "D")
    order = loss.sort_values("mean_delta").reset_index(drop=True)
    yy = np.arange(len(order))
    colors = [BLUE if x == "classification" else ORANGE for x in order["task_type"]]
    ax.errorbar(order["mean_delta"], yy, xerr=[order["mean_delta"] - order["seed_clustered_ci95_low"], order["seed_clustered_ci95_high"] - order["mean_delta"]], fmt="none", ecolor=GREY, capsize=2, lw=0.9)
    ax.scatter(order["mean_delta"], yy, c=colors, s=18, zorder=3)
    ax.axvline(0, color=INK, lw=0.8)
    ax.set_yticks(yy, [x.replace("tdc_", "") for x in order["task"]])
    ax.set_xlabel("K = 32 minus K = 4 raw loss")
    ax.set_title("Endpoint-specific\nselection loss", loc="left")

    ax = axes[1, 1]
    letter(ax, "E")
    plot = controls.loc[controls["metric"].eq("fixed_normalized_regret")]
    names = {"random_order": "Random order", "random_subset": "Random subset", "family_balanced": "Family balanced"}
    for mode, group in plot.groupby("mode"):
        ax.plot(group["pool_size"], group["mean"], marker="o", label=names[mode])
    ax.set(xlabel="Candidate count, K", ylabel="Normalized selection loss", xticks=[4, 8, 16, 32])
    ax.set_title("Candidate-composition\ncontrols", loc="left")
    ax.legend(frameon=False, fontsize=6.2)

    ax = axes[1, 2]
    letter(ax, "F")
    k32 = endpoint_div.loc[endpoint_div["candidate_count"].eq(32)]
    ax.scatter(k32["empirical_outer_entropy_effective_rank"], k32["shrinkage_outer_entropy_effective_rank"], color=TEAL, s=22)
    lim = max(k32["empirical_outer_entropy_effective_rank"].max(), k32["shrinkage_outer_entropy_effective_rank"].max()) * 1.05
    ax.plot([1, lim], [1, lim], color=GREY, ls="--", lw=0.8)
    ax.set(xlabel="Empirical entropy rank", ylabel="Shrinkage entropy rank")
    ax.set_title("K = 32 estimator\nsensitivity", loc="left")
    fig.subplots_adjust(wspace=0.55, hspace=0.55)
    save(fig, "Figure_2_major_revision_diversity_ranking_loss")


def figure3() -> None:
    null = pd.read_csv(ROOT / "results" / "selection_closure" / "null_calibration_summary.csv")
    signal = pd.read_csv(ROOT / "results" / "reviewer_core_20260624" / "signal_recovery_summary.csv")
    sim = pd.read_csv(PREV / "paper19_oracle_extreme_value_simulation.csv")
    mv = pd.read_csv(MAJOR / "multiview_absolute_endpoint_summary.csv")
    counts = pd.read_csv(MULTI / "validation_best_representation_counts.csv")
    fig = plt.figure(figsize=(7.2, 5.2))
    gs = fig.add_gridspec(2, 3, wspace=0.55, hspace=0.55)

    ax = fig.add_subplot(gs[0, 0])
    letter(ax, "A")
    ax.plot(null["pool_size"], null["observed_chance_adjusted_hit"], marker="o", color=BLUE, label="Observed")
    ax.plot(null["pool_size"], null["null_chance_adjusted_hit_mean"], marker="s", color=GREY, label="Permutation null")
    ax.axhline(0, color=INK, lw=0.7)
    ax.set(xlabel="Candidate count, K", ylabel="CAHit@3", xticks=[4, 8, 16, 32])
    ax.set_title("Permutation calibration", loc="left")
    ax.legend(frameon=False, fontsize=6.0)

    ax = fig.add_subplot(gs[0, 1])
    letter(ax, "B")
    grid = signal.pivot(index="pool_size", columns="signal_correlation", values="chance_adjusted_hit_mean")
    im = ax.imshow(grid.to_numpy(), aspect="auto", cmap="viridis", vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(grid.columns)), [f"{v:g}" for v in grid.columns], rotation=30)
    ax.set_yticks(np.arange(len(grid.index)), grid.index)
    ax.set(xlabel="Injected correlation", ylabel="K")
    ax.set_title("Signal-recovery control", loc="left")
    fig.colorbar(im, ax=ax, fraction=0.045, pad=0.03)

    ax = fig.add_subplot(gs[0, 2])
    letter(ax, "C")
    plot = sim.loc[sim["truth_scenario"].eq("equal_truth") & np.isclose(sim["pairwise_candidate_correlation"], 0.9)]
    for n, group in plot.groupby("effective_audit_sample_size"):
        ax.plot(group["candidate_count"], group["mean_observed_oracle_optimism"], marker="o", label=f"n_eff={n}")
    ax.set(xlabel="Candidate count, K", ylabel="Optimism (SD units)", xticks=[4, 8, 16, 32])
    ax.set_title("Finite-audit\nwinner optimism", loc="left")
    ax.legend(frameon=False, ncol=2, fontsize=5.8)

    ax = fig.add_subplot(gs[1, 0])
    letter(ax, "D")
    order = mv.sort_values(["task_type", "mean_raw_paired_gain"]).reset_index(drop=True)
    yy = np.arange(len(order))
    colors = [BLUE if x == "classification" else ORANGE for x in order["task_type"]]
    ax.errorbar(order["mean_raw_paired_gain"], yy, xerr=[order["mean_raw_paired_gain"] - order["seed_clustered_ci95_low"], order["seed_clustered_ci95_high"] - order["mean_raw_paired_gain"]], fmt="none", ecolor=GREY, capsize=2, lw=0.9)
    ax.scatter(order["mean_raw_paired_gain"], yy, c=colors, s=18)
    ax.axvline(0, color=INK, lw=0.7)
    ax.set_yticks(yy, [x.replace("tdc_", "") for x in order["task"]])
    ax.set_xlabel("Raw paired gain")
    ax.set_title("Multiview endpoint\neffects", loc="left")
    ax.text(0, -0.29, "Blue: ROC-AUC gain; orange: RMSE reduction.", transform=ax.transAxes, fontsize=5.8, color=GREY)

    ax = fig.add_subplot(gs[1, 1])
    letter(ax, "E")
    reps = counts.loc[counts["variant"].eq("full_multiview")].sort_values("size")
    colors_e = [GREY if r in {"morgan512", "maccs"} else (TEAL if r == "rdkit2d" else BLUE) for r in reps["selected_representation"]]
    ax.barh(reps["selected_representation"], reps["size"], color=colors_e)
    ax.set_xlabel("Selections among 135 outer units")
    ax.set_title("Selected representations", loc="left")

    holder = fig.add_subplot(gs[1, 2])
    holder.set_axis_off()
    letter(holder, "F")
    holder.set_title("Absolute selected\nperformance", loc="left")
    ax1 = holder.inset_axes([0.00, 0.52, 1.00, 0.38])
    cls = mv.loc[mv["task_type"].eq("classification")]
    x = np.arange(len(cls))
    ax1.plot(x, cls["morgan_only_selected_performance"], marker="o", color=GREY, label="Morgan-only")
    ax1.plot(x, cls["full_multiview_selected_performance"], marker="o", color=BLUE, label="Full pool")
    ax1.set_xticks(x, [t.replace("tdc_", "") for t in cls["task"]], rotation=45, ha="right", fontsize=5.6)
    ax1.set_ylabel("ROC-AUC", fontsize=6.2)
    ax1.legend(frameon=False, fontsize=5.4, ncol=2)
    ax2 = holder.inset_axes([0.00, 0.03, 1.00, 0.36])
    reg = mv.loc[mv["task_type"].eq("regression")]
    x = np.arange(len(reg))
    ax2.plot(x, reg["morgan_only_selected_performance"], marker="o", color=GREY)
    ax2.plot(x, reg["full_multiview_selected_performance"], marker="o", color=ORANGE)
    ax2.set_xticks(x, [t.replace("tdc_", "") for t in reg["task"]], rotation=45, ha="right", fontsize=5.6)
    ax2.set_ylabel("RMSE", fontsize=6.2)
    save(fig, "Figure_3_major_revision_controls_multiview")


def figure4() -> None:
    perf = pd.read_csv(HARD / "six_task_strong_endpoint_table.csv")
    overlap = pd.read_csv(HARD / "six_task_error_overlap_pairwise_summary.csv")
    conformal = pd.read_csv(UQ / "conformal_crossfold_summary.csv")
    cqr = pd.read_csv(UQ / "cqr_regression_summary.csv")
    ood = pd.read_csv(UQ / "calibration_ood_scaffold_summary.csv")
    failures = pd.read_csv(UQ / "failure_case_category_summary.csv")
    names = {"chemberta_mtr_linear_probe": "ChemBERTa", "gnn_gcn": "GCN", "molformer_linear_probe": "MoLFormer", "rdkit_rf": "RDKit-RF"}
    perf["label"] = perf["candidate"].map(names)
    perf["normalized"] = perf.groupby("task")["mean_outer_utility"].transform(lambda x: (x - x.min()) / max(x.max() - x.min(), 1e-12))
    heat = perf.pivot(index="label", columns="task", values="normalized").reindex(list(names.values()))
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 5.2))

    ax = axes[0, 0]
    letter(ax, "A")
    im = ax.imshow(heat, cmap="YlGnBu", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(np.arange(len(heat.columns)), heat.columns, rotation=40, ha="right")
    ax.set_yticks(np.arange(len(heat.index)), heat.index)
    ax.set_title("Within-endpoint\nnormalized utility", loc="left")

    ax = axes[0, 1]
    letter(ax, "B")
    labels = list(names.values())
    mat = np.eye(4)
    for _, r in overlap.iterrows():
        i, j = labels.index(names[r.candidate_a]), labels.index(names[r.candidate_b])
        mat[i, j] = mat[j, i] = r.mean_jaccard_error_overlap
    ax.imshow(mat, cmap="Oranges", vmin=0, vmax=1)
    ax.set_xticks(np.arange(4), labels, rotation=40, ha="right")
    ax.set_yticks(np.arange(4), labels)
    for i in range(4):
        for j in range(4):
            ax.text(j, i, f"{mat[i,j]:.2f}", ha="center", va="center", fontsize=6.3)
    ax.set_title("Pairwise error overlap", loc="left")

    ax = axes[0, 2]
    letter(ax, "C")
    c90 = conformal.loc[np.isclose(conformal["target_coverage"], 0.9)].dropna(subset=["mean_class_1_coverage"])
    summary = c90.groupby("method")["mean_class_1_coverage"].mean().reindex(["split_conformal", "label_conditional_conformal", "mondrian_label_similarity_conformal"])
    ax.bar(["Split", "Label-\nconditional", "Mondrian"], summary, color=[GREY, BLUE, TEAL])
    ax.axhline(0.9, color=RED, ls="--", lw=0.9)
    ax.set(ylim=(0.55, 0.95), ylabel="Minority coverage")
    ax.set_title("Conditional conformal\ncoverage", loc="left")

    ax = axes[1, 0]
    letter(ax, "D")
    q90 = cqr.loc[np.isclose(cqr["target_coverage"], 0.9)]
    ax.bar(q90["task"], q90["mean_coverage"], color=ORANGE)
    ax.axhline(0.9, color=RED, ls="--", lw=0.9)
    ax.set(ylim=(0.65, 1.0), ylabel="Empirical coverage")
    ax.set_title("Endpoint-specific CQR", loc="left")
    ax.tick_params(axis="x", rotation=30)

    ax = axes[1, 1]
    letter(ax, "E")
    bins = ["<0.5", "0.5-0.7", ">0.7"]
    subset = ood.loc[ood["task"].isin(["bace", "bbbp", "clintox"])]
    auc = subset.groupby("tanimoto_bin")["mean_roc_auc"].mean().reindex(bins)
    ece = subset.groupby("tanimoto_bin")["mean_ece"].mean().reindex(bins)
    ax.plot(bins, auc, marker="o", color=BLUE, label="ROC-AUC")
    ax.plot(bins, ece, marker="s", color=RED, label="ECE")
    ax.set(ylim=(0, 1), xlabel="Maximum train Tanimoto")
    ax.set_title("Similarity-stratified\nreliability", loc="left")
    ax.legend(frameon=False)

    ax = axes[1, 2]
    letter(ax, "F")
    categories = failures["category"].tolist()
    columns = ["High error", "Misclassification", "False negative", "Pair failure"]
    source_rows: dict[str, list[int]] = {}
    for category in categories:
        low = category.lower()
        values = [int("high_error" in low), int("misclassification" in low), int("false_negative" in low), int("pair_failure" in low)]
        source = category.replace("_high_error", "").replace("_misclassification", "").replace("classification_false_negative", "classification").replace("activity_cliff_pair_failure", "activity_cliff")
        source = source.replace("_", " ")
        if source not in source_rows:
            source_rows[source] = values
        else:
            source_rows[source] = [max(a, b) for a, b in zip(source_rows[source], values)]
    short = list(source_rows)
    matrix = np.asarray([source_rows[x] for x in short])
    ax.imshow(matrix, cmap=mpl.colors.ListedColormap(["#F2F4F6", RED]), vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(np.arange(4), columns, rotation=40, ha="right", fontsize=6.2)
    ax.set_yticks(np.arange(len(short)), short, fontsize=5.8)
    ax.set_title("Failure-category\npresence map", loc="left")
    fig.subplots_adjust(wspace=0.62, hspace=0.58)
    save(fig, "Figure_4_major_revision_reliability_boundaries")


def main() -> None:
    setup()
    figure1()
    figure2()
    figure3()
    figure4()
    print(FIG)


if __name__ == "__main__":
    main()
