from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, Rectangle


ROOT = Path("D:/fzyc")
CORE = ROOT / "output" / "paper20_candidate_pool_audit_20260712"
MAJOR = ROOT / "output" / "paper19_major_revision_20260712"
PREV = ROOT / "output" / "paper19_rejection_driven_experiments_20260712"
REV = ROOT / "output" / "paper19_jcheminformatics_revision_20260712"
HARD = ROOT / "output" / "sci1_hardening_20260707"
UQ = ROOT / "output" / "sci1_mechanism_uq_decision_20260707"
FIG = CORE / "main_figures"
KS = [4, 8, 16, 32]

BLUE = "#376FA8"
ORANGE = "#D07A34"
TEAL = "#2D8A7E"
RED = "#B54D4D"
GREY = "#707984"
LIGHT = "#DDE2E7"
INK = "#202832"
COLORS = [BLUE, ORANGE, TEAL, RED, GREY, "#8A6FA8"]
DISPLAY = {
    "bace": "BACE", "bbbp": "BBBP", "clintox": "ClinTox", "esol": "ESOL",
    "freesolv": "FreeSolv", "lipo": "Lipophilicity", "tdc_caco2_wang": "Caco2",
    "tdc_hia_hou": "HIA", "tdc_pgp_broccatelli": "P-gp",
}


def setup() -> None:
    mpl.rcParams.update({
        "font.family": "Arial", "font.size": 8.4, "axes.titlesize": 9.0,
        "axes.labelsize": 8.5, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
        "legend.fontsize": 7.1, "axes.linewidth": 0.8, "axes.spines.top": False,
        "axes.spines.right": False, "svg.fonttype": "none", "pdf.fonttype": 42,
    })


def panel(ax: plt.Axes, label: str, title: str) -> None:
    ax.text(-0.20, 1.08, label, transform=ax.transAxes, fontsize=10.5, fontweight="bold", va="top")
    ax.set_title(title, loc="left", pad=5)


def save(fig: plt.Figure, stem: str) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    for suffix in ["png", "svg", "pdf"]:
        kwargs = {"dpi": 600} if suffix == "png" else {}
        fig.savefig(FIG / f"{stem}.{suffix}", bbox_inches="tight", facecolor="white", **kwargs)
    plt.close(fig)


def figure1() -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.35))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    stages = [
        ("Data and task\nregistration", "Datasets, endpoints,\nmetrics, split manifest", BLUE),
        ("Candidate and\nrepresentation registry", "Eligibility, order,\ncompute exposure", TEAL),
        ("Candidate-pool\nexpansion", "K = 4, 8, 16, 32", ORANGE),
        ("Repeated nested\nselection", "3 outer x 3 inner\nx 5 seeds", BLUE),
        ("Outer auditing", "Candidate utilities and\nvalidation-selected model", TEAL),
        ("Cross-fitted\nreference", "Other four seeds choose;\nheld-out seed evaluates", ORANGE),
        ("Utility-pattern\ndiversity", "Raw, centred, relative\nand rank matrices", BLUE),
        ("Ranking fidelity", "Chance-adjusted recovery\nand rank agreement", TEAL),
        ("Audit-gap\ndecomposition", "Audit-best, selected gain,\nincremental gap", ORANGE),
        ("Matched-size\nmultiview analysis", "Composition effects at\nfixed K", BLUE),
        ("Reliability\nboundaries", "OOD, minority class,\nchemical support", TEAL),
        ("Audit outputs", "Main evidence, SI, source\ndata and limitations", ORANGE),
    ]
    cols, w, h = 6, 0.145, 0.22
    xs = np.linspace(0.02, 0.98 - w, cols)
    ys = [0.64, 0.31]
    for i, (title, detail, color) in enumerate(stages):
        row, col = divmod(i, cols)
        x, y = xs[col], ys[row]
        ax.add_patch(Rectangle((x, y), w, h, facecolor="white", edgecolor=color, linewidth=1.5))
        ax.add_patch(Rectangle((x, y + h - 0.045), w, 0.045, facecolor=color, edgecolor=color))
        ax.text(x + w / 2, y + 0.135, title, ha="center", va="center", fontsize=6.6, fontweight="bold", color=INK)
        ax.text(x + w / 2, y + 0.055, detail, ha="center", va="center", fontsize=6.2, color=GREY)
        if col < cols - 1:
            ax.add_patch(FancyArrowPatch((x + w, y + h / 2), (xs[col + 1], y + h / 2), arrowstyle="-|>", mutation_scale=8, lw=1, color=GREY))
    ax.add_patch(FancyArrowPatch((0.955, 0.64), (0.955, 0.53), connectionstyle="arc3,rad=-0.35", arrowstyle="-|>", mutation_scale=8, lw=1, color=GREY))
    ax.add_patch(FancyArrowPatch((0.955, 0.53), (0.02, 0.53), connectionstyle="arc3,rad=0", arrowstyle="-|>", mutation_scale=8, lw=1, color=GREY))
    labels = ["Data\nRegistration", "Candidate\nConstruction", "Nested\nSelection", "Outer\nAuditing", "Statistical\nDecomposition", "Reliability\nand Reporting"]
    x0 = np.linspace(0.025, 0.975, len(labels) + 1)
    for i, label in enumerate(labels):
        ax.text((x0[i] + x0[i + 1]) / 2, 0.10, label, ha="center", va="center", fontsize=6.2, fontweight="bold", color=INK)
        if i < len(labels) - 1:
            ax.annotate("", xy=(x0[i + 1] + 0.008, 0.10), xytext=(x0[i + 1] - 0.008, 0.10), arrowprops=dict(arrowstyle="-|>", color=GREY, lw=0.9))
    ax.plot([0.025, 0.975], [0.16, 0.16], color=LIGHT, lw=1)
    fig.subplots_adjust(0.01, 0.01, 0.99, 0.99)
    save(fig, "Figure_1_retrospective_nested_audit_architecture")


def figure2() -> None:
    summary = pd.read_csv(CORE / "utility_pattern_diversity_summary.csv")
    endpoint = pd.read_csv(CORE / "utility_pattern_diversity_endpoint.csv")
    sensitivity = pd.read_csv(CORE / "utility_pattern_diversity_sensitivity.csv")
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 5.15))
    modes = ["raw", "row_centred", "fixed_reference_relative"]
    titles = ["Raw utility matrix", "Row-centred matrix", "Reference-relative matrix"]
    for idx, (ax, mode, title, color) in enumerate(zip(axes[0], modes, titles, COLORS)):
        panel(ax, chr(65 + idx), title)
        d = summary.loc[summary["transformation"].eq(mode)].sort_values("candidate_count")
        ycol = "hierarchical_bootstrap_median_entropy_rank" if "hierarchical_bootstrap_median_entropy_rank" in d else "mean_shrinkage_entropy_rank"
        y = d[ycol].to_numpy(float)
        lo = d["hierarchical_ci95_low_entropy_rank"].to_numpy(float)
        hi = d["hierarchical_ci95_high_entropy_rank"].to_numpy(float)
        ax.errorbar(d["candidate_count"], y, yerr=[y-lo, hi-y], marker="o", color=color, capsize=2)
        ax.plot([4, 8, 16, 32], [4, 8, 16, 32], ls=":", color=LIGHT)
        ax.set(xlabel="Nominal candidate count, K", ylabel="Shrinkage entropy rank", xticks=[4, 8, 16, 32])
    ax = axes[1, 0]; panel(ax, "D", "Participation-ratio rank")
    for mode, color in zip(["raw", "row_centred", "fixed_reference_relative", "within_unit_rank"], COLORS):
        d = summary.loc[summary["transformation"].eq(mode)].sort_values("candidate_count")
        col = "hierarchical_bootstrap_median_participation_rank" if "hierarchical_bootstrap_median_participation_rank" in d else "mean_shrinkage_participation_rank"
        ax.plot(d["candidate_count"], d[col], marker="o", color=color, label=mode.replace("_", " "))
    ax.set(xlabel="Nominal candidate count, K", ylabel="Participation-ratio rank", xticks=[4, 8, 16, 32]); ax.legend(frameon=False, fontsize=6.2)
    ax = axes[1, 1]; panel(ax, "E", "Correlation before and after adjustment")
    for mode, color in zip(["raw", "row_centred", "fixed_reference_relative"], COLORS):
        d = summary.loc[summary["transformation"].eq(mode)].sort_values("candidate_count")
        col = "hierarchical_bootstrap_median_median_correlation" if "hierarchical_bootstrap_median_median_correlation" in d else "mean_shrinkage_median_correlation"
        ax.plot(d["candidate_count"], d[col], marker="o", color=color, label=mode.replace("_", " "))
    ax.axhline(0, color=LIGHT, lw=0.8); ax.set(xlabel="Nominal candidate count, K", ylabel="Median candidate correlation", xticks=[4, 8, 16, 32]); ax.legend(frameon=False, fontsize=6.2)
    ax = axes[1, 2]; panel(ax, "F", "Endpoint omission sensitivity")
    d = endpoint.loc[endpoint["candidate_count"].eq(32) & endpoint["transformation"].eq("fixed_reference_relative")].copy()
    s = sensitivity.loc[sensitivity["transformation"].eq("fixed_reference_relative")]
    order = d.sort_values("shrinkage_entropy_rank")["task"].tolist()
    for i, task in enumerate(order):
        vals = s.loc[s["task"].eq(task), "entropy_rank"].to_numpy(float)
        point = d.loc[d["task"].eq(task), "shrinkage_entropy_rank"].iloc[0]
        ax.plot([vals.min(), vals.max()], [i, i], color=GREY, lw=2)
        ax.plot(point, i, "o", color=BLUE, ms=4)
    ax.set(yticks=range(len(order)), yticklabels=[DISPLAY[x] for x in order], xlabel="Reference-relative rank at K = 32", ylabel="")
    fig.tight_layout(w_pad=1.4, h_pad=1.6)
    save(fig, "Figure_2_effective_candidate_diversity")


def figure3() -> None:
    ranking = pd.read_csv(MAJOR / "chance_adjusted_ranking_summary.csv").sort_values("candidate_count")
    effects = pd.read_csv(CORE / "cross_fitted_k32_minus_k4.csv")
    controls = pd.read_csv(REV / "candidate_composition_controls.csv")
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 5.15))
    ax = axes[0, 0]; panel(ax, "A", "Chance-adjusted Hit@3")
    ax.plot(ranking["candidate_count"], ranking["mean_chance_adjusted_top3"], marker="o", color=BLUE)
    ax.axhline(0, color=LIGHT, lw=0.8); ax.set(xlabel="K", ylabel="CAHit@3", xticks=KS)
    ax = axes[0, 1]; panel(ax, "B", "Normalized rank recovery")
    ax.plot(ranking["candidate_count"], ranking["mean_rank_percentile"], marker="o", color=TEAL)
    ax.set(xlabel="K", ylabel="Mean audit-rank percentile", xticks=KS, ylim=(0, 1))
    ax = axes[0, 2]; panel(ax, "C", "Normalized MRR gain")
    ax.plot(ranking["candidate_count"], ranking["mean_normalized_mrr_gain"], marker="o", color=ORANGE)
    ax.axhline(0, color=LIGHT, lw=0.8); ax.set(xlabel="K", ylabel="Normalized MRR gain", xticks=KS)
    ax = axes[1, 0]; panel(ax, "D", "Rank-agreement metrics")
    for col, label, color in [("mean_ndcg", "NDCG", BLUE), ("mean_spearman", "Spearman", TEAL), ("mean_kendall", "Kendall", ORANGE)]:
        ax.plot(ranking["candidate_count"], ranking[col], marker="o", label=label, color=color)
    ax.set(xlabel="K", ylabel="Agreement", xticks=KS, ylim=(0, 1)); ax.legend(frameon=False)
    ax = axes[1, 1]; panel(ax, "E", "Endpoint audit-gap change")
    e = effects.sort_values("k32_minus_k4_same_unit_gap")
    y = np.arange(len(e)); x = e["k32_minus_k4_same_unit_gap"].to_numpy(float)
    lo = e["seed_clustered_ci95_low_same_unit_gap"].to_numpy(float); hi = e["seed_clustered_ci95_high_same_unit_gap"].to_numpy(float)
    colors = [BLUE if t == "classification" else ORANGE for t in e["task_type"]]
    ax.errorbar(x, y, xerr=[x-lo, hi-x], fmt="none", ecolor=GREY, capsize=2)
    ax.scatter(x, y, c=colors, s=20); ax.axvline(0, color=INK, lw=0.8)
    ax.set(yticks=y, yticklabels=[DISPLAY[x] for x in e["task"]], xlabel="K = 32 minus K = 4 gap\n(ROC-AUC or RMSE utility units)")
    ax = axes[1, 2]; panel(ax, "F", "Composition controls")
    for mode, color in zip(sorted(controls["mode"].unique()), COLORS):
        d = controls.loc[controls["mode"].eq(mode)].sort_values("pool_size")
        ax.plot(d["pool_size"], d["chance_adjusted_hit_mean"], marker="o", label=mode.replace("_", " "), color=color)
    ax.axhline(0, color=LIGHT, lw=0.8); ax.set(xlabel="K", ylabel="Chance-adjusted hit", xticks=KS); ax.legend(frameon=False, fontsize=6.2)
    fig.tight_layout(w_pad=1.4, h_pad=1.6)
    save(fig, "Figure_3_ranking_distortion_and_audit_gaps")


def figure4() -> None:
    units = pd.read_csv(CORE / "audit_gap_decomposition_units.csv")
    cross = pd.read_csv(CORE / "cross_fitted_k32_minus_k4.csv")
    simulation = pd.read_csv(PREV / "paper19_oracle_extreme_value_simulation.csv")
    d = units.loc[units["candidate_count"].eq(32)].groupby(["task", "task_type"], as_index=False).agg(
        audit_best=("observed_audit_best_gain", "mean"), selected=("selected_model_gain", "mean"), gap=("incremental_observed_audit_gap", "mean")
    )
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 5.25))
    for idx, (ax, col, label, title) in enumerate(zip(axes[0], ["audit_best", "selected", "gap"], ["Observed audit-best gain", "Selected-model gain", "Incremental observed audit gap"], ["Audit-best gain", "Selected-model gain", "Incremental gap"])):
        panel(ax, chr(65 + idx), title)
        q = d.sort_values(col); y = np.arange(len(q)); colors = [BLUE if x == "classification" else ORANGE for x in q["task_type"]]
        ax.barh(y, q[col], color=colors, alpha=0.85); ax.axvline(0, color=INK, lw=0.7)
        ax.set(yticks=y, yticklabels=[DISPLAY[x] for x in q["task"]], xlabel=f"{label}\n(ROC-AUC or RMSE utility units)")
    ax = axes[1, 0]; panel(ax, "D", "Same-unit versus cross-fitted effects")
    ax.scatter(cross["k32_minus_k4_same_unit_gap"], cross["k32_minus_k4_cross_fitted_gap"], c=[BLUE if x == "classification" else ORANGE for x in cross["task_type"]], s=28)
    lim = [min(cross["k32_minus_k4_cross_fitted_gap"].min(), -0.005), max(cross["k32_minus_k4_same_unit_gap"].max(), 0.10)]
    ax.plot(lim, lim, ls=":", color=GREY); ax.axhline(0, color=LIGHT, lw=0.8); ax.axvline(0, color=LIGHT, lw=0.8)
    ax.set(xlabel="Same-unit K32-K4 gap", ylabel="Cross-fitted K32-K4 gap")
    ax = axes[1, 1]; panel(ax, "E", "Cross-fitted endpoint effects")
    e = cross.sort_values("k32_minus_k4_cross_fitted_gap"); y = np.arange(len(e)); x = e["k32_minus_k4_cross_fitted_gap"].to_numpy(float)
    lo = e["seed_clustered_ci95_low_cross_fitted_gap"].to_numpy(float); hi = e["seed_clustered_ci95_high_cross_fitted_gap"].to_numpy(float)
    ax.errorbar(x, y, xerr=[x-lo, hi-x], fmt="none", ecolor=GREY, capsize=2); ax.scatter(x, y, c=[BLUE if q == "classification" else ORANGE for q in e["task_type"]], s=20)
    ax.axvline(0, color=INK, lw=0.8); ax.set(yticks=y, yticklabels=[DISPLAY[x] for x in e["task"]], xlabel="K = 32 minus K = 4 cross-fitted gap")
    ax = axes[1, 2]; panel(ax, "F", "Finite-audit winner optimism")
    s = simulation.loc[simulation["truth_scenario"].eq("equal_truth") & simulation["pairwise_candidate_correlation"].eq(0.9)]
    grid = s.pivot_table(index="effective_audit_sample_size", columns="candidate_count", values="mean_observed_oracle_optimism").sort_index(ascending=False)
    im = ax.imshow(grid, aspect="auto", cmap="YlOrRd"); ax.set(xticks=np.arange(len(grid.columns)), xticklabels=grid.columns, yticks=np.arange(len(grid.index)), yticklabels=grid.index, xlabel="K", ylabel="Effective audit n")
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]): ax.text(j, i, f"{grid.iloc[i,j]:.2f}", ha="center", va="center", fontsize=6.1)
    fig.colorbar(im, ax=ax, fraction=0.045, pad=0.03, label="Mean optimism")
    fig.tight_layout(w_pad=1.2, h_pad=1.6)
    save(fig, "Figure_4_audit_gap_decomposition")


def figure5() -> None:
    summary = pd.read_csv(CORE / "matched_k_multiview_summary.csv")
    units = pd.read_csv(CORE / "matched_k_multiview_units.csv")
    freq = pd.read_csv(CORE / "matched_k_selection_frequency.csv")
    verify = pd.read_csv(CORE / "multiview_zero_width_verification.csv")
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 5.25))
    ax = axes[0, 0]; panel(ax, "A", "Matched K = 3 pools")
    d = summary.loc[summary["analysis_group"].eq("matched_K3")].pivot_table(index="task", columns="pool_name", values="mean_representation_composition_effect")
    d = d.div(d.abs().max(axis=1).replace(0, 1), axis=0)
    im = ax.imshow(d, aspect="auto", cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set(yticks=np.arange(len(d)), yticklabels=[DISPLAY[x] for x in d.index], xticks=np.arange(len(d.columns)), xticklabels=[x.replace("matched_K3_", "") for x in d.columns], xlabel="Fixed three-candidate composition")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right"); fig.colorbar(im, ax=ax, fraction=0.045, pad=0.03)
    ax = axes[0, 1]; panel(ax, "B", "Within-learner representation effects")
    w = summary.loc[summary["analysis_group"].eq("within_learner")].copy()
    scale = w.groupby("task")["mean_representation_composition_effect"].transform(lambda x: max(x.abs().max(), 1e-12))
    w["normalized_effect"] = w["mean_representation_composition_effect"] / scale
    for pool, color in zip(sorted(w["pool_name"].unique()), COLORS):
        q = w.loc[w["pool_name"].eq(pool)].sort_values("task")
        ax.plot(range(len(q)), q["normalized_effect"], marker="o", label=pool.replace("within_", "").replace("_K4", ""), color=color)
    ax.axhline(0, color=INK, lw=0.8); ax.set(xticks=range(len(q)), xticklabels=[DISPLAY[x] for x in q["task"]], ylabel="Within-endpoint normalized effect"); plt.setp(ax.get_xticklabels(), rotation=45, ha="right"); ax.legend(frameon=False)
    ax = axes[0, 2]; panel(ax, "C", "Incremental K ladder")
    ladder = summary.loc[summary["analysis_group"].eq("incremental_ladder")].copy()
    scale = ladder.groupby("task")["mean_gain_vs_morgan_k3"].transform(lambda x: max(x.abs().max(), 1e-12))
    ladder["normalized_ladder_gain"] = ladder["mean_gain_vs_morgan_k3"] / scale
    for task, color in zip(sorted(ladder["task"].unique()), COLORS * 2):
        q = ladder.loc[ladder["task"].eq(task)].sort_values("pool_size")
        ax.plot(q["pool_size"], q["normalized_ladder_gain"], marker="o", label=DISPLAY[task], color=color, alpha=0.85)
    ax.axhline(0, color=INK, lw=0.8); ax.set(xlabel="Pool size", ylabel="Within-endpoint normalized gain", xticks=[3, 6, 9, 12]); ax.legend(frameon=False, fontsize=5.7, ncol=2)
    ax = axes[1, 0]; panel(ax, "D", "Endpoint multiview-pool gains")
    e = verify.sort_values("mean_paired_gain"); y = np.arange(len(e)); x = e["mean_paired_gain"].to_numpy(float); lo=e["seed_clustered_ci95_low"].to_numpy(float); hi=e["seed_clustered_ci95_high"].to_numpy(float)
    ax.errorbar(x, y, xerr=[x-lo, hi-x], fmt="none", ecolor=GREY, capsize=2); ax.scatter(x, y, c=[BLUE if z == "classification" else ORANGE for z in e["task_type"]], s=20); ax.axvline(0, color=INK, lw=0.8)
    ax.set(yticks=y, yticklabels=[DISPLAY[x] for x in e["task"]], xlabel="Full K = 12 minus Morgan K = 3\n(ROC-AUC or RMSE utility units)")
    ax = axes[1, 1]; panel(ax, "E", "Absolute selected performance")
    v = pd.read_csv(MAJOR / "multiview_absolute_endpoint_summary.csv")
    ratio = np.where(v["task_type"].eq("classification"),
        v["full_multiview_selected_performance"] / v["morgan_only_selected_performance"],
        v["morgan_only_selected_performance"] / v["full_multiview_selected_performance"])
    x0=np.arange(len(v)); ax.axhline(1, color=GREY, ls=":", lw=0.9); ax.scatter(x0, ratio, marker="s", color=TEAL)
    ax.set(xticks=x0, xticklabels=[DISPLAY[x] for x in v["task"]], ylabel="Relative performance ratio\n(higher is better)"); plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    ax = axes[1, 2]; panel(ax, "F", "Representation-selection frequency")
    f = freq.loc[freq["analysis_group"].eq("incremental_ladder")].groupby("representation")["selection_count"].sum().sort_values()
    ax.barh(range(len(f)), f, color=[COLORS[i % len(COLORS)] for i in range(len(f))]); ax.set(yticks=range(len(f)), yticklabels=f.index.str.replace("morgan512", "Morgan").str.replace("multiview", "Concatenated"), xlabel="Selections across ladder pools")
    fig.tight_layout(w_pad=1.2, h_pad=1.6)
    save(fig, "Figure_5_matched_size_multiview")


def figure6() -> None:
    perf = pd.read_csv(HARD / "six_task_strong_endpoint_table.csv")
    overlap = pd.read_csv(HARD / "six_task_error_overlap_pairwise_summary.csv")
    overlap_detail = pd.read_csv(HARD / "six_task_error_overlap_pairwise_detail.csv")
    similarity = pd.read_csv(UQ / "calibration_ood_scaffold_summary.csv")
    clintox = pd.read_csv(UQ / "clintox_minority_negative_result.csv").drop_duplicates("candidate")
    boundary = pd.read_csv(UQ / "failure_case_category_summary.csv")
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 5.25))
    ax = axes[0, 0]; panel(ax, "A", "Representation utility")
    p = perf.pivot_table(index="task", columns="candidate", values="delta_vs_rdkit_mean")
    p = p.div(p.abs().max(axis=1).replace(0, 1), axis=0)
    im=ax.imshow(p, aspect="auto", cmap="RdBu_r", vmin=-1, vmax=1); ax.set(yticks=np.arange(len(p)), yticklabels=[DISPLAY.get(x,x) for x in p.index], xticks=np.arange(len(p.columns)), xticklabels=[x.replace("_linear_probe", "").replace("chemberta_mtr", "ChemBERTa").replace("molformer", "MoLFormer").replace("gnn_gcn", "GCN").replace("rdkit_rf", "RDKit-RF") for x in p.columns]); plt.setp(ax.get_xticklabels(), rotation=45, ha="right"); fig.colorbar(im, ax=ax, fraction=0.045, pad=0.03)
    ax = axes[0, 1]; panel(ax, "B", "Error-overlap Jaccard")
    candidates=sorted(set(overlap.candidate_a)|set(overlap.candidate_b)); mat=pd.DataFrame(np.eye(len(candidates)),index=candidates,columns=candidates)
    for _,r in overlap.iterrows(): mat.loc[r.candidate_a,r.candidate_b]=mat.loc[r.candidate_b,r.candidate_a]=r.mean_jaccard_error_overlap
    im=ax.imshow(mat, vmin=0, vmax=1, cmap="Blues"); short=[x.replace("chemberta_mtr_linear_probe","ChemBERTa").replace("molformer_linear_probe","MoLFormer").replace("gnn_gcn","GCN").replace("rdkit_rf","RDKit-RF") for x in candidates]; ax.set(xticks=range(len(short)),xticklabels=short,yticks=range(len(short)),yticklabels=short); plt.setp(ax.get_xticklabels(),rotation=45,ha="right"); fig.colorbar(im,ax=ax,fraction=0.045,pad=0.03)
    ax = axes[0, 2]; panel(ax, "C", "Endpoint error complementarity")
    q=overlap_detail.groupby("task",as_index=False)["jaccard_error_overlap"].mean().sort_values("jaccard_error_overlap"); ax.barh(range(len(q)),q["jaccard_error_overlap"],color=TEAL); ax.set(yticks=range(len(q)),yticklabels=[DISPLAY.get(x,x) for x in q.task],xlabel="Mean pairwise error Jaccard",xlim=(0,1))
    ax = axes[1, 0]; panel(ax, "D", "Tanimoto strata")
    s=similarity.groupby("tanimoto_bin",as_index=False).agg(roc_auc=("mean_roc_auc","mean"),ece=("mean_ece","mean")); order=[x for x in ["<0.5","0.5-0.7",">0.7"] if x in s.tanimoto_bin.values]; s=s.set_index("tanimoto_bin").loc[order].reset_index(); x=np.arange(len(s)); ax.plot(x,s.roc_auc,marker="o",color=BLUE,label="ROC-AUC"); ax.plot(x,1-s.ece,marker="s",color=ORANGE,label="1 - ECE"); ax.set(xticks=x,xticklabels=s.tanimoto_bin,ylabel="Performance / calibration",xlabel="Maximum train-set Tanimoto",ylim=(0,1)); ax.legend(frameon=False)
    ax = axes[1, 1]; panel(ax, "E", "ClinTox minority-class failure")
    c=clintox.sort_values("minority_recall"); y=np.arange(len(c)); ax.barh(y,c.minority_recall,color=BLUE,label="Recall"); ax.barh(y,c.minority_false_negative_rate,left=c.minority_recall,color=RED,alpha=0.75,label="False-negative rate"); ax.set(yticks=y,yticklabels=[x.replace("chemberta_mtr_linear_probe","ChemBERTa").replace("molformer_linear_probe","MoLFormer").replace("gnn_gcn","GCN").replace("rdkit_rf","RDKit-RF") for x in c.candidate],xlabel="Minority-class fraction",xlim=(0,1)); ax.legend(frameon=False)
    ax = axes[1, 2]; panel(ax, "F", "Chemical-boundary categories")
    categories=["activity cliff","bro5 perimeter","false negative","extreme label","low similarity"]
    sources=sorted(boundary.source.unique()); matrix=np.zeros((len(sources),len(categories)))
    for i,src in enumerate(sources):
        text=" ".join(boundary.loc[boundary.source.eq(src),"category"].astype(str)).lower()
        for j,key in enumerate(categories): matrix[i,j]=int(key.replace(" ","_") in text.replace(" ","_") or all(w in text for w in key.split()))
    source_labels=[x.replace("six_task_rdkit_rf","Six-task RDKit-RF") for x in sources]
    category_labels=[x.replace("bro5","bRo5") for x in categories]
    ax.imshow(matrix,aspect="auto",cmap="Greys",vmin=0,vmax=1); ax.set(yticks=range(len(sources)),yticklabels=source_labels,xticks=range(len(categories)),xticklabels=category_labels); plt.setp(ax.get_xticklabels(),rotation=45,ha="right")
    fig.tight_layout(w_pad=1.2,h_pad=1.6)
    save(fig, "Figure_6_representation_errors_and_boundaries")


def main() -> None:
    setup()
    figure1(); figure2(); figure3(); figure4(); figure5(); figure6()
    print(FIG)


if __name__ == "__main__":
    main()
