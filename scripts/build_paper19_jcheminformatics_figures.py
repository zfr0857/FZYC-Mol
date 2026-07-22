from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, Rectangle


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "paper19_jcheminformatics_revision_20260712"
FIG = OUT / "figures"

BLUE = "#356FAE"
ORANGE = "#D77A31"
TEAL = "#2A8C82"
RED = "#B94C4C"
GREY = "#6E7781"
LIGHT = "#E6EAF0"
INK = "#1F2937"


def setup() -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 11,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 8.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.8,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
        }
    )


def panel(ax: plt.Axes, letter: str) -> None:
    ax.text(-0.16, 1.10, letter, transform=ax.transAxes, fontsize=13, fontweight="bold", va="top")


def save(fig: plt.Figure, stem: str) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "svg", "pdf"):
        fig.savefig(FIG / f"{stem}.{suffix}", dpi=400 if suffix == "png" else None, bbox_inches="tight")
    plt.close(fig)


def box(ax: plt.Axes, xy: tuple[float, float], wh: tuple[float, float], text: str, color: str) -> None:
    x, y = xy
    w, h = wh
    ax.add_patch(Rectangle((x, y), w, h, facecolor="white", edgecolor=color, linewidth=1.4))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", color=INK, fontsize=9)


def arrow(ax: plt.Axes, start: tuple[float, float], end: tuple[float, float]) -> None:
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=11, color=GREY, linewidth=1.1))


def figure1() -> None:
    fig, axes = plt.subplots(2, 3, figsize=(12.5, 7.6))
    for ax in axes.flat:
        ax.set_axis_off()

    ax = axes[0, 0]
    panel(ax, "A")
    ax.set_title("Frozen audit architecture", loc="left", pad=10)
    box(ax, (0.02, 0.58), (0.27, 0.22), "Candidate\nregistry", BLUE)
    box(ax, (0.37, 0.58), (0.27, 0.22), "Nested\nselection", TEAL)
    box(ax, (0.72, 0.58), (0.27, 0.22), "Outer\naudit", ORANGE)
    arrow(ax, (0.29, 0.69), (0.37, 0.69))
    arrow(ax, (0.64, 0.69), (0.72, 0.69))
    ax.text(0.50, 0.30, "Retrospective protocol lock", ha="center", fontsize=10, fontweight="bold")
    ax.text(0.50, 0.18, "No audit-set feedback into candidate choice", ha="center", fontsize=8.5, color=GREY)

    ax = axes[0, 1]
    panel(ax, "B")
    ax.set_title("Candidate expansion", loc="left", pad=10)
    labels = ["K = 4", "K = 8", "K = 16", "K = 32"]
    widths = [0.22, 0.38, 0.62, 0.90]
    for i, (label, width) in enumerate(zip(labels, widths)):
        y = 0.77 - i * 0.18
        ax.add_patch(Rectangle((0.05, y), width, 0.10, color=BLUE, alpha=0.75))
        ax.text(0.07, y + 0.05, label, va="center", color="white", fontweight="bold")
    ax.text(0.05, 0.08, "Nominal count increases; effective\ndiversity is audited separately", fontsize=8.2, color=GREY)

    ax = axes[0, 2]
    panel(ax, "C")
    ax.set_title("Repeated nested scaffold splits", loc="left", pad=10)
    for i, (label, color, text) in enumerate(
        [("Outer", ORANGE, "3 folds"), ("Inner", TEAL, "3 folds"), ("Seeds", BLUE, "5 repeats")]
    ):
        y = 0.70 - i * 0.22
        box(ax, (0.08, y), (0.38, 0.14), label, color)
        ax.text(0.58, y + 0.07, text, va="center", fontsize=10, fontweight="bold", color=color)
    ax.text(0.08, 0.10, "15 outer units per endpoint", fontsize=8.5, color=GREY)

    ax = axes[1, 0]
    panel(ax, "D")
    ax.set_title("Primary estimands", loc="left", pad=10)
    items = [
        ("Observed audit upper bound", ORANGE),
        ("Raw-scale selection loss", RED),
        ("Validation-audit rank fidelity", BLUE),
        ("Effective candidate rank", TEAL),
    ]
    for i, (text, color) in enumerate(items):
        y = 0.80 - i * 0.19
        ax.add_patch(Rectangle((0.06, y), 0.05, 0.05, color=color))
        ax.text(0.15, y + 0.025, text, va="center", fontsize=9.5)

    ax = axes[1, 1]
    panel(ax, "E")
    ax.set_title("Claim hierarchy", loc="left", pad=10)
    levels = [
        (0.82, "Primary: nine-endpoint\ncandidate expansion", BLUE),
        (0.82, "Confirmation: shared-split\nmultiview pool", TEAL),
        (0.82, "Stress test: four\nmodern baselines", ORANGE),
        (0.82, "Reliability and\nchemical boundaries", GREY),
    ]
    for width, text, color in levels:
        x = (1 - width) / 2
        y = 0.16 + 0.17 * (3 - levels.index((width, text, color)))
        ax.add_patch(Rectangle((x, y), width, 0.12, facecolor=color, edgecolor="none", alpha=0.78))
        ax.text(0.5, y + 0.06, text, ha="center", va="center", color="white", fontsize=6.2, fontweight="bold")

    ax = axes[1, 2]
    panel(ax, "F")
    ax.set_title("Interpretation boundary", loc="left", pad=10)
    box(ax, (0.07, 0.62), (0.38, 0.16), "Observed\naudit best", ORANGE)
    ax.text(0.53, 0.70, "not", fontsize=11, fontweight="bold", color=RED, va="center")
    box(ax, (0.65, 0.62), (0.28, 0.16), "True\noracle", RED)
    box(ax, (0.07, 0.28), (0.38, 0.16), "Outer\naudit", ORANGE)
    ax.text(0.53, 0.36, "not", fontsize=11, fontweight="bold", color=RED, va="center")
    box(ax, (0.65, 0.28), (0.28, 0.16), "Independent\nconfirmation", RED)

    fig.subplots_adjust(wspace=0.32, hspace=0.32)
    save(fig, "Figure_1_frozen_audit_workflow")


def figure2() -> None:
    base = ROOT / "output" / "paper19_rejection_driven_experiments_20260712"
    div = pd.read_csv(base / "paper19_effective_diversity.csv")
    eff = div.groupby("candidate_count", as_index=False).agg(
        effective_rank=("outer_entropy_effective_rank", "mean"),
        correlation=("outer_median_pairwise_correlation", "mean"),
    )
    rank = pd.read_csv(base / "paper19_ranking_fidelity_units.csv")
    rank_k = rank.groupby("candidate_count", as_index=False).agg(spearman=("spearman_validation_vs_audit", "mean"))
    effects = pd.read_csv(base / "paper19_k32_vs_k4_endpoint_effects.csv")
    effects = effects.loc[effects["policy"] == "validation_best"].copy()
    controls = pd.read_csv(OUT / "candidate_composition_controls.csv")
    raw = pd.read_csv(base / "paper19_raw_selection_loss_summary.csv")

    fig, axes = plt.subplots(2, 3, figsize=(13.2, 8.2))
    ax = axes[0, 0]
    panel(ax, "A")
    ax.plot(eff["candidate_count"], eff["effective_rank"], marker="o", color=TEAL, lw=2)
    ax.plot(eff["candidate_count"], eff["candidate_count"], color=GREY, ls="--", lw=1, label="nominal K")
    ax.set(xlabel="Nominal candidate count, K", ylabel="Effective candidate rank", xticks=[4, 8, 16, 32], title="Nominal count vs effective diversity")
    ax.legend(frameon=False)

    ax = axes[0, 1]
    panel(ax, "B")
    ax.plot(eff["candidate_count"], eff["correlation"], marker="o", color=ORANGE, lw=2)
    ax.set(xlabel="Nominal candidate count, K", ylabel="Median pairwise utility correlation", xticks=[4, 8, 16, 32], ylim=(0.45, 1.0), title="Candidate correlation")

    ax = axes[0, 2]
    panel(ax, "C")
    ax.plot(rank_k["candidate_count"], rank_k["spearman"], marker="o", color=BLUE, lw=2)
    ax.axhline(0, color=GREY, lw=0.8)
    ax.set(xlabel="Nominal candidate count, K", ylabel="Validation-audit Spearman", xticks=[4, 8, 16, 32], ylim=(0, 1), title="Ranking fidelity")

    ax = axes[1, 0]
    panel(ax, "D")
    order = effects.sort_values("mean_delta_raw_loss_k32_minus_k4")["task"].tolist()
    plot = effects.set_index("task").loc[order]
    y = np.arange(len(plot))
    colors = [BLUE if t == "classification" else ORANGE for t in plot["task_type"]]
    ax.errorbar(
        plot["mean_delta_raw_loss_k32_minus_k4"], y,
        xerr=np.vstack([
            plot["mean_delta_raw_loss_k32_minus_k4"] - plot["ci95_low"],
            plot["ci95_high"] - plot["mean_delta_raw_loss_k32_minus_k4"],
        ]), fmt="none", ecolor=GREY, capsize=2, lw=1.1,
    )
    ax.scatter(plot["mean_delta_raw_loss_k32_minus_k4"], y, c=colors, s=32, zorder=3)
    ax.axvline(0, color=INK, lw=0.8)
    ax.set_yticks(y, [x.replace("tdc_", "") for x in order])
    ax.set(xlabel="K=32 minus K=4 raw selection loss", title="Endpoint-specific raw-scale effects")
    ax.text(0.01, -0.27, "Blue: ROC-AUC loss; orange: RMSE loss. Scales are not pooled.", transform=ax.transAxes, fontsize=8, color=GREY)

    ax = axes[1, 1]
    panel(ax, "E")
    plot = controls.loc[controls["metric"] == "fixed_normalized_regret"]
    names = {"random_order": "Random order", "random_subset": "Random subset", "family_balanced": "Family balanced"}
    for mode, group in plot.groupby("mode"):
        ax.plot(group["pool_size"], group["mean"], marker="o", lw=1.8, label=names[mode])
    ax.set(xlabel="Candidate count, K", ylabel="Normalized selection loss", xticks=[4, 8, 16, 32], title="Candidate-composition controls")
    ax.legend(frameon=False)

    ax = axes[1, 2]
    panel(ax, "F")
    if "policy" in raw.columns:
        raw = raw.loc[raw["policy"] == "validation_best"]
    raw = raw.groupby(["task_type", "candidate_count"], as_index=False)["mean_raw_selection_loss"].mean()
    classes = raw.loc[raw["task_type"] == "classification"]
    regs = raw.loc[raw["task_type"] == "regression"]
    ax.plot(classes["candidate_count"], classes["mean_raw_selection_loss"], marker="o", color=BLUE, lw=2, label="Classification: AUC loss")
    ax2 = ax.twinx()
    ax2.spines["right"].set_visible(True)
    ax2.plot(regs["candidate_count"], regs["mean_raw_selection_loss"], marker="s", color=ORANGE, lw=2, label="Regression: RMSE loss")
    ax.set(xlabel="Candidate count, K", ylabel="Mean ROC-AUC loss", xticks=[4, 8, 16, 32], title="Task-type selection loss")
    ax2.set_ylabel("Mean RMSE loss", color=ORANGE)
    ax.tick_params(axis="y", colors=BLUE)
    ax2.tick_params(axis="y", colors=ORANGE)

    fig.subplots_adjust(wspace=0.44, hspace=0.45)
    save(fig, "Figure_2_candidate_expansion_selection_loss")


def figure3() -> None:
    null = pd.read_csv(ROOT / "results" / "selection_closure" / "null_calibration_summary.csv")
    signal = pd.read_csv(ROOT / "results" / "reviewer_core_20260624" / "signal_recovery_summary.csv")
    sim = pd.read_csv(ROOT / "output" / "paper19_rejection_driven_experiments_20260712" / "paper19_oracle_extreme_value_simulation.csv")
    mv = pd.read_csv(OUT / "multiview_endpoint_raw_gain.csv")
    counts = pd.read_csv(ROOT / "results" / "reviewer_core_20260624" / "multiview_nested" / "validation_best_representation_counts.csv")
    paired = pd.read_csv(ROOT / "results" / "reviewer_core_20260624" / "multiview_nested" / "paired_multiview_effects_long.csv")

    fig, axes = plt.subplots(2, 3, figsize=(13.2, 8.2))
    ax = axes[0, 0]
    panel(ax, "A")
    ax.plot(null["pool_size"], null["observed_chance_adjusted_hit"], marker="o", color=BLUE, lw=2, label="Observed")
    ax.plot(null["pool_size"], null["null_chance_adjusted_hit_mean"], marker="s", color=GREY, lw=1.5, label="Permutation null")
    ax.axhline(0, color=INK, lw=0.8)
    ax.set(xlabel="Candidate count, K", ylabel="Chance-adjusted top-3 hit", xticks=[4, 8, 16, 32], title="Permutation calibration")
    ax.legend(frameon=False)

    ax = axes[0, 1]
    panel(ax, "B")
    grid = signal.pivot(index="pool_size", columns="signal_correlation", values="chance_adjusted_hit_mean")
    im = ax.imshow(grid.to_numpy(), aspect="auto", cmap="viridis", vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(grid.columns)), [f"{v:g}" for v in grid.columns])
    ax.set_yticks(np.arange(len(grid.index)), grid.index)
    ax.set(xlabel="Injected validation-audit correlation", ylabel="Candidate count, K", title="Signal-recovery control")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03, label="Chance-adjusted hit")

    ax = axes[0, 2]
    panel(ax, "C")
    plot = sim.loc[(sim["truth_scenario"] == "equal_truth") & (np.isclose(sim["pairwise_candidate_correlation"], 0.9))]
    for n, group in plot.groupby("effective_audit_sample_size"):
        ax.plot(group["candidate_count"], group["mean_observed_oracle_optimism"], marker="o", label=f"n_eff={n}")
    ax.set(xlabel="Candidate count, K", ylabel="Winner optimism (SD units)", xticks=[4, 8, 16, 32], title="Finite-audit winner optimism")
    ax.legend(frameon=False, ncol=2)

    ax = axes[1, 0]
    panel(ax, "D")
    mv = mv.sort_values(["task_type", "mean_raw_gain"])
    y = np.arange(len(mv))
    colors = [BLUE if t == "classification" else ORANGE for t in mv["task_type"]]
    ax.errorbar(
        mv["mean_raw_gain"], y,
        xerr=np.vstack([mv["mean_raw_gain"] - mv["bootstrap_ci95_low"], mv["bootstrap_ci95_high"] - mv["mean_raw_gain"]]),
        fmt="none", ecolor=GREY, capsize=2, lw=1,
    )
    ax.scatter(mv["mean_raw_gain"], y, c=colors, s=32)
    ax.axvline(0, color=INK, lw=0.8)
    ax.set_yticks(y, [x.replace("tdc_", "") for x in mv["endpoint"]])
    ax.set(xlabel="Realized raw utility gain", title="Endpoint-specific multiview gains")
    ax.text(0.01, -0.27, "Blue: ROC-AUC gain; orange: RMSE reduction.", transform=ax.transAxes, fontsize=8, color=GREY)

    ax = axes[1, 1]
    panel(ax, "E")
    plot = counts.loc[counts["variant"] == "full_multiview"].sort_values("size")
    ax.barh(plot["selected_representation"], plot["size"], color=[GREY, GREY, TEAL, BLUE])
    ax.set(xlabel="Selections among 135 outer units", title="Selected representations")

    ax = axes[1, 2]
    panel(ax, "F")
    comparisons = {
        "realized multiview validation-best gain vs Morgan-only": "Realized multiview",
        "attainable multiview gain vs Morgan-only oracle": "Attainable multiview",
        "concatenated multiview gain vs separate-view pool": "Concatenation",
    }
    rows = []
    for key, label in comparisons.items():
        vals = paired.loc[paired["comparison"] == key, "normalized_utility_gain"]
        endpoint_means = paired.loc[paired["comparison"] == key].groupby("task")["normalized_utility_gain"].mean()
        rows.append((label, endpoint_means.mean(), endpoint_means.min(), endpoint_means.max(), vals.size))
    labels, means, lows, highs, _ = zip(*rows)
    y = np.arange(len(labels))
    ax.errorbar(means, y, xerr=[np.array(means) - np.array(lows), np.array(highs) - np.array(means)], fmt="o", color=TEAL, ecolor=GREY, capsize=3)
    ax.axvline(0, color=INK, lw=0.8)
    ax.set_yticks(y, labels)
    ax.set(xlabel="Mean normalized utility gain\n(range across endpoints)", title="Frozen-selection gains")

    fig.subplots_adjust(wspace=0.50, hspace=0.45)
    save(fig, "Figure_3_ranking_winner_optimism_multiview")


def figure4() -> None:
    hard = ROOT / "output" / "sci1_hardening_20260707"
    uq = ROOT / "output" / "sci1_mechanism_uq_decision_20260707"
    perf = pd.read_csv(hard / "six_task_strong_endpoint_table.csv")
    overlap = pd.read_csv(hard / "six_task_error_overlap_pairwise_summary.csv")
    conformal = pd.read_csv(uq / "conformal_crossfold_summary.csv")
    cqr = pd.read_csv(uq / "cqr_regression_summary.csv")
    ood = pd.read_csv(uq / "calibration_ood_scaffold_summary.csv")
    failures = pd.read_csv(uq / "failure_case_category_summary.csv")

    names = {
        "chemberta_mtr_linear_probe": "ChemBERTa",
        "gnn_gcn": "GCN",
        "molformer_linear_probe": "MoLFormer",
        "rdkit_rf": "RDKit-RF",
    }
    perf["label"] = perf["candidate"].map(names)
    perf["normalized_utility"] = perf.groupby("task")["mean_outer_utility"].transform(
        lambda x: (x - x.min()) / max(x.max() - x.min(), 1e-12)
    )
    heat = perf.pivot(index="label", columns="task", values="normalized_utility").reindex(list(names.values()))

    fig, axes = plt.subplots(2, 3, figsize=(13.4, 8.4))
    ax = axes[0, 0]
    panel(ax, "A")
    im = ax.imshow(heat.to_numpy(), cmap="YlGnBu", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(np.arange(len(heat.columns)), heat.columns, rotation=35, ha="right")
    ax.set_yticks(np.arange(len(heat.index)), heat.index)
    ax.set_title("Endpoint-dependent baseline utility")
    fig.colorbar(im, ax=ax, fraction=0.038, pad=0.02, label="Normalized utility")

    ax = axes[0, 1]
    panel(ax, "B")
    labels = list(names.values())
    mat = np.eye(len(labels))
    for _, row in overlap.iterrows():
        a, b = names[row["candidate_a"]], names[row["candidate_b"]]
        i, j = labels.index(a), labels.index(b)
        mat[i, j] = mat[j, i] = row["mean_jaccard_error_overlap"]
    im = ax.imshow(mat, cmap="Oranges", vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(labels)), labels, rotation=35, ha="right")
    ax.set_yticks(np.arange(len(labels)), labels)
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, f"{mat[i, j]:.2f}", ha="center", va="center", fontsize=8)
    ax.set_title("Pairwise error overlap")

    ax = axes[0, 2]
    panel(ax, "C")
    c90 = conformal.loc[np.isclose(conformal["target_coverage"], 0.9)]
    c90 = c90.dropna(subset=["mean_class_1_coverage"])
    summary = c90.groupby("method")["mean_class_1_coverage"].mean().reindex(
        ["split_conformal", "label_conditional_conformal", "mondrian_label_similarity_conformal"]
    )
    labels_c = ["Split", "Label-conditional", "Mondrian"]
    ax.bar(labels_c, summary.to_numpy(), color=[GREY, BLUE, TEAL])
    ax.axhline(0.9, color=RED, ls="--", lw=1, label="90% target")
    ax.set(ylim=(0.55, 0.95), ylabel="Minority-class coverage", title="Conditional conformal coverage")
    ax.tick_params(axis="x", rotation=20)
    ax.legend(frameon=False)

    ax = axes[1, 0]
    panel(ax, "D")
    q90 = cqr.loc[np.isclose(cqr["target_coverage"], 0.9)].copy()
    ax.bar(q90["task"], q90["mean_coverage"], color=ORANGE)
    ax.axhline(0.9, color=RED, ls="--", lw=1)
    ax.set(ylim=(0.65, 1.0), ylabel="Empirical coverage", title="CQR by endpoint")
    ax.tick_params(axis="x", rotation=25)

    ax = axes[1, 1]
    panel(ax, "E")
    bins = ["<0.5", "0.5-0.7", ">0.7"]
    auc = ood.loc[ood["task"].isin(["bace", "bbbp", "clintox"])].groupby("tanimoto_bin")["mean_roc_auc"].mean().reindex(bins)
    ece = ood.loc[ood["task"].isin(["bace", "bbbp", "clintox"])].groupby("tanimoto_bin")["mean_ece"].mean().reindex(bins)
    ax.plot(bins, auc, marker="o", color=BLUE, lw=2, label="ROC-AUC")
    ax.plot(bins, ece, marker="s", color=RED, lw=2, label="ECE")
    ax.set(xlabel="Maximum train-set Tanimoto", ylabel="ROC-AUC", title="Similarity-stratified reliability")
    ax.legend(frameon=False, loc="lower right")
    ax.set_ylim(0, 1.0)

    ax = axes[1, 2]
    panel(ax, "F")
    plot = failures.sort_values("median_abs_error", ascending=True)
    shorten = {
        "novel_scaffold_high_error": "Novel scaffold: high error",
        "extreme_label_high_error": "Extreme label: high error",
        "low_tanimoto_high_error": "Low similarity: high error",
        "bRo5_perimeter_high_error": "bRo5 perimeter: high error",
        "activity_cliff_pair_failure": "Activity-cliff pair",
        "novel_scaffold_misclassification": "Novel scaffold: misclass.",
        "low_tanimoto_misclassification": "Low similarity: misclass.",
        "classification_false_negative": "False negative",
        "bRo5_perimeter_misclassification": "bRo5 perimeter: misclass.",
    }
    labels_f = [shorten.get(x, x.replace("_", " ")) for x in plot["category"]]
    ax.barh(labels_f, plot["median_abs_error"], color=[RED if "minority" in x or "cliff" in x else GREY for x in plot["category"]])
    ax.set(xlabel="Median absolute error or error score", title="Chemical-boundary failure modes")
    ax.tick_params(axis="y", labelsize=7.2)

    fig.subplots_adjust(wspace=0.58, hspace=0.45)
    save(fig, "Figure_4_modern_baselines_reliability_boundaries")


def main() -> None:
    setup()
    figure1()
    figure2()
    figure3()
    figure4()
    print(f"Figures written to {FIG}")


if __name__ == "__main__":
    main()
