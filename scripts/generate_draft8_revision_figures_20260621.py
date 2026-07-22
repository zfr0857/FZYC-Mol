# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import shutil
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import PercentFormatter


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "draft8_14k_revision"
OUT = ROOT / "output" / "初稿-8_图表与源数据"
FIG = OUT / "figures"
SRC = OUT / "source_data"
FIG.mkdir(parents=True, exist_ok=True)
SRC.mkdir(parents=True, exist_ok=True)

COLORS = {
    "blue": "#4C78A8",
    "orange": "#E39C4A",
    "green": "#5A9C76",
    "red": "#C65F5F",
    "purple": "#8A78A8",
    "grey": "#7A7F87",
    "light": "#D9DDE2",
    "dark": "#2B2F33",
}

mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Microsoft YaHei", "DejaVu Sans", "sans-serif"],
        "font.size": 7,
        "axes.titlesize": 8.5,
        "axes.labelsize": 7.5,
        "xtick.labelsize": 6.5,
        "ytick.labelsize": 6.5,
        "legend.fontsize": 6.5,
        "axes.linewidth": 0.7,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "savefig.facecolor": "white",
        "figure.facecolor": "white",
    }
)


def panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(-0.14, 1.06, label, transform=ax.transAxes, fontsize=9, fontweight="bold", va="top")


def save_bundle(fig: plt.Figure, stem: str) -> Path:
    base = FIG / stem
    fig.savefig(base.with_suffix(".png"), dpi=450, bbox_inches="tight")
    fig.savefig(base.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(base.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(
        base.with_suffix(".tiff"),
        dpi=600,
        bbox_inches="tight",
        pil_kwargs={"compression": "tiff_lzw"},
    )
    return base.with_suffix(".png")


def copy_source(path: Path, name: str | None = None) -> Path:
    dest = SRC / (name or path.name)
    shutil.copy2(path, dest)
    return dest


def parse_mean_sd(value: object) -> tuple[float, float]:
    nums = re.findall(r"[-+]?\d+(?:\.\d+)?", str(value))
    if not nums:
        return np.nan, np.nan
    return float(nums[0]), float(nums[1]) if len(nums) > 1 else 0.0


def retain_conceptual_figures() -> list[Path]:
    source = ROOT / "reports" / "reviewer_revision_20260607" / "figures"
    outputs: list[Path] = []
    for idx, old_stem in [
        (1, "fig1_workflow_only"),
        (2, "fig2_selector_gate_output_evidence"),
    ]:
        new_stem = f"fig{idx:02d}_{'workflow' if idx == 1 else 'strict_protocol'}"
        for ext in [".png", ".svg", ".pdf", ".tiff"]:
            src = source / f"{old_stem}{ext}"
            dst = FIG / f"{new_stem}{ext}"
            shutil.copy2(src, dst)
        outputs.append(FIG / f"{new_stem}.png")
    return outputs


def figure_candidate_pool() -> Path:
    summary_path = REPORT / "candidate_pool_stress_summary.csv"
    stability_path = REPORT / "candidate_pool_selection_stability.csv"
    detail_path = REPORT / "candidate_pool_stress_detail.csv"
    summary = pd.read_csv(summary_path)
    stability = pd.read_csv(stability_path)
    detail = pd.read_csv(detail_path)
    copy_source(summary_path)
    copy_source(stability_path)
    copy_source(detail_path)

    labels = {
        "fixed_single": "Fixed single",
        "validation_best": "Validation-best",
        "one_se_stable": "One-SE + stability",
        "risk_adjusted": "Risk-adjusted",
        "random_expected": "Random expectation",
    }
    colors = {
        "fixed_single": COLORS["grey"],
        "validation_best": COLORS["orange"],
        "one_se_stable": COLORS["blue"],
        "risk_adjusted": COLORS["green"],
        "random_expected": COLORS["purple"],
    }
    policies = list(labels)

    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.25))
    ax = axes[0, 0]
    for policy in policies:
        s = summary[summary["policy"].eq(policy)].sort_values("pool_size")
        ax.plot(s["pool_size"], s["normalized_regret_mean"], marker="o", ms=3.5, lw=1.4, color=colors[policy], label=labels[policy])
        ax.fill_between(s["pool_size"], s["regret_ci95_low"], s["regret_ci95_high"], color=colors[policy], alpha=0.10, linewidth=0)
    ax.axhline(0, color=COLORS["dark"], lw=0.8, ls="--", label="Test-oracle upper bound")
    ax.set(xlabel="Registered candidates", ylabel="Normalized held-out test regret", xticks=[4, 8, 16, 32])
    ax.legend(ncol=2, loc="upper right")
    panel_label(ax, "a")

    ax = axes[0, 1]
    for policy in ["validation_best", "one_se_stable", "risk_adjusted"]:
        s = summary[summary["policy"].eq(policy)].sort_values("pool_size")
        ax.plot(s["pool_size"], s["optimism_gap_mean"], marker="o", ms=3.5, lw=1.4, color=colors[policy], label=labels[policy])
    ax.axhline(0, color=COLORS["dark"], lw=0.8, ls="--")
    ax.set(xlabel="Registered candidates", ylabel="Normalized optimism gap", xticks=[4, 8, 16, 32])
    ax.legend(loc="upper right")
    panel_label(ax, "b")

    ax = axes[1, 0]
    hit = summary[summary["policy"].eq("validation_best")].sort_values("pool_size")
    ax.plot(hit["pool_size"], hit["top3_hit_rate"], marker="o", ms=4, lw=1.6, color=COLORS["red"])
    ax.set(xlabel="Registered candidates", ylabel="Test-oracle candidate in validation Top-3", xticks=[4, 8, 16, 32], ylim=(0, 1.02))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    for _, row in hit.iterrows():
        ax.text(row["pool_size"], row["top3_hit_rate"] + 0.04, f"{row['top3_hit_rate']:.2f}", ha="center", fontsize=6)
    panel_label(ax, "c")

    ax = axes[1, 1]
    stab = (
        stability[stability["policy"].eq("validation_best")]
        .groupby("pool_size", as_index=False)["modal_selection_rate"]
        .mean()
        .sort_values("pool_size")
    )
    ax.plot(stab["pool_size"], stab["modal_selection_rate"], marker="o", ms=4, lw=1.6, color=COLORS["blue"])
    ax.set(xlabel="Registered candidates", ylabel="Modal selection rate across seeds", xticks=[4, 8, 16, 32], ylim=(0, 1.02))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    for _, row in stab.iterrows():
        ax.text(row["pool_size"], row["modal_selection_rate"] + 0.04, f"{row['modal_selection_rate']:.2f}", ha="center", fontsize=6)
    panel_label(ax, "d")

    for ax in axes.ravel():
        ax.grid(axis="y", color="#E7E9EC", lw=0.6)
    fig.tight_layout(w_pad=2.0, h_pad=2.0)
    return save_bundle(fig, "fig03_candidate_pool_stress")


def figure_nested_validation() -> Path:
    summary_path = ROOT / "reports" / "remaining_missing_experiments_20260606" / "true_nested_validation" / "true_nested_validation_summary.csv"
    inner_path = ROOT / "reports" / "remaining_missing_experiments_20260606" / "true_nested_validation" / "true_nested_validation_inner_scores.csv"
    seed_path = ROOT / "reports" / "remaining_missing_experiments_20260606" / "nested_seed_validation_summary.csv"
    summary = pd.read_csv(summary_path)
    inner = pd.read_csv(inner_path)
    seed = pd.read_csv(seed_path)
    candidate_col = "model" if "model" in inner else "candidate"
    counts = inner.groupby("dataset")[candidate_col].nunique().rename("candidate_count").reset_index()
    summary = summary.merge(counts, on="dataset", how="left")
    summary.to_csv(SRC / "fig04_true_nested_summary_with_candidate_counts.csv", index=False)
    copy_source(seed_path, "fig04_seed_nested_audit.csv")

    pretty = {
        "bbbp": "BBBP", "bace": "BACE", "clintox": "ClinTox", "esol": "ESOL",
        "freesolv": "FreeSolv", "lipo": "Lipo", "tdc_caco2_wang": "Caco2",
        "tdc_hia_hou": "HIA", "tdc_pgp_broccatelli": "Pgp",
    }
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.6))
    cls = summary[summary["task_type"].eq("classification")].copy()
    reg = summary[summary["task_type"].eq("regression")].copy()
    tcrit = 4.303

    ax = axes[0, 0]
    x = np.arange(len(cls))
    ci = tcrit * cls["roc_auc_sd"].fillna(0) / np.sqrt(cls["n_outer"])
    ax.errorbar(x, cls["roc_auc_mean"], yerr=ci, fmt="o", color=COLORS["blue"], ecolor=COLORS["light"], capsize=2.5)
    ax.set_xticks(x, [pretty.get(v, v) for v in cls["dataset"]], rotation=25, ha="right")
    ax.set_ylabel("Outer ROC-AUC (mean and 95% CI)")
    for xi, (_, row) in enumerate(cls.iterrows()):
        ax.text(xi, row["roc_auc_mean"] + ci.iloc[xi] + 0.015, f"K={int(row['candidate_count']) if pd.notna(row['candidate_count']) else 'NA'}", ha="center", fontsize=5.5)
    panel_label(ax, "a")

    ax = axes[0, 1]
    x = np.arange(len(reg))
    ci = tcrit * reg["rmse_sd"].fillna(0) / np.sqrt(reg["n_outer"])
    ax.errorbar(x, reg["rmse_mean"], yerr=ci, fmt="o", color=COLORS["orange"], ecolor=COLORS["light"], capsize=2.5)
    ax.set_xticks(x, [pretty.get(v, v) for v in reg["dataset"]], rotation=25, ha="right")
    ax.set_ylabel("Outer RMSE (mean and 95% CI)")
    for xi, (_, row) in enumerate(reg.iterrows()):
        ax.text(xi, row["rmse_mean"] + ci.iloc[xi] + 0.08, f"K={int(row['candidate_count']) if pd.notna(row['candidate_count']) else 'NA'}", ha="center", fontsize=5.5)
    panel_label(ax, "b")

    ax = axes[1, 0]
    plot = seed.sort_values("median_regret_vs_test_oracle", ascending=True).copy()
    labels = [f"{pretty.get(d, d)} | {s.replace('_', ' ')}" for d, s in zip(plot["dataset"], plot["source"])]
    y = np.arange(len(plot))
    ax.scatter(plot["median_regret_vs_test_oracle"], y, s=18, color=np.where(plot["task_type"].eq("classification"), COLORS["blue"], COLORS["orange"]))
    ax.set_yticks(y, labels)
    ax.set_xlabel("Median test-oracle regret (native metric direction)")
    ax.axvline(0, color=COLORS["dark"], lw=0.7)
    panel_label(ax, "c")

    ax = axes[1, 1]
    plot = seed.sort_values("top_model_switches", ascending=True).copy()
    y = np.arange(len(plot))
    ax.barh(y, plot["top_model_switches"], color=np.where(plot["task_type"].eq("classification"), COLORS["blue"], COLORS["orange"]), height=0.65)
    ax.set_yticks(y, [pretty.get(d, d) for d in plot["dataset"]])
    ax.set_xlabel("Selected-model switches across outer seeds")
    ax.set_xticks(range(0, int(plot["top_model_switches"].max()) + 1))
    panel_label(ax, "d")

    for ax in axes.ravel():
        ax.grid(axis="x" if ax in axes[1] else "y", color="#E7E9EC", lw=0.6)
    fig.tight_layout(w_pad=2.3, h_pad=2.0)
    return save_bundle(fig, "fig04_true_nested_validation")


def figure_moleculenet_and_clintox() -> Path:
    main_path = ROOT / "reports" / "manuscript_tables" / "table2_moleculenet_main_long.csv"
    rank_path = ROOT / "reports" / "supplement_experiment_revision_20260606" / "maintext_table_validation_bias_extended.csv"
    clintox_path = ROOT / "reports" / "reviewer_revision_20260607" / "clintox_fixed_precision_recall_consensus_strict_core_multifp.csv"
    main = pd.read_csv(main_path)
    rank = pd.read_csv(rank_path)
    clintox = pd.read_csv(clintox_path)
    copy_source(main_path, "fig05_moleculenet_source.csv")
    copy_source(rank_path, "fig05_validation_test_rank_audit.csv")
    copy_source(clintox_path, "fig05_clintox_fixed_precision_recall.csv")

    cats = ["Classical Morgan", "Chemprop", "FZYC-Mol final retained-best", "Best observed candidate"]
    cat_labels = ["Morgan", "Chemprop", "FZYC-Mol retained", "Test-oracle upper bound"]
    cat_colors = [COLORS["grey"], COLORS["purple"], COLORS["blue"], COLORS["orange"]]
    pretty = {"bbbp": "BBBP", "bace": "BACE", "clintox": "ClinTox", "esol": "ESOL", "freesolv": "FreeSolv", "lipo": "Lipo"}
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.4))

    for ax, task, ylabel, panel in [
        (axes[0, 0], "classification", "ROC-AUC", "a"),
        (axes[0, 1], "regression", "RMSE", "b"),
    ]:
        sub = main[main["task_type"].eq(task) & main["category"].isin(cats)].copy()
        datasets = list(dict.fromkeys(sub["dataset"]))
        x = np.arange(len(datasets))
        width = 0.19
        for j, (cat, label, color) in enumerate(zip(cats, cat_labels, cat_colors)):
            vals = sub[sub["category"].eq(cat)].set_index("dataset").reindex(datasets)
            ax.errorbar(x + (j - 1.5) * width, vals["value"], yerr=vals["std"], fmt="o", ms=3.3, capsize=2, color=color, label=label)
        ax.set_xticks(x, [pretty.get(d, d) for d in datasets])
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", color="#E7E9EC", lw=0.6)
        if task == "classification":
            ax.set_ylim(0.75, 1.01)
            ax.legend(ncol=2, loc="lower right")
        panel_label(ax, panel)

    ax = axes[1, 0]
    means = [clintox["recall_p80"].mean(), clintox["recall_p90"].mean()]
    sds = [clintox["recall_p80"].std(ddof=1), clintox["recall_p90"].std(ddof=1)]
    ax.bar([0, 1], means, yerr=sds, color=[COLORS["green"], COLORS["orange"]], width=0.55, capsize=3)
    ax.scatter(np.repeat(0, len(clintox)) + np.linspace(-0.08, 0.08, len(clintox)), clintox["recall_p80"], s=12, color=COLORS["dark"], zorder=3)
    ax.scatter(np.repeat(1, len(clintox)) + np.linspace(-0.08, 0.08, len(clintox)), clintox["recall_p90"], s=12, color=COLORS["dark"], zorder=3)
    ax.set_xticks([0, 1], ["Precision >= 0.80", "Precision >= 0.90"])
    ax.set_ylabel("ClinTox recall")
    ax.set_ylim(0, 1.03)
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    panel_label(ax, "c")

    ax = axes[1, 1]
    audit = rank[~rank["source"].eq("overall")].sort_values("median_spearman")
    y = np.arange(len(audit))
    ax.errorbar(audit["median_spearman"], y, xerr=[audit["median_spearman"] - audit.get("q25_spearman", audit["median_spearman"]), audit.get("q75_spearman", audit["median_spearman"]) - audit["median_spearman"]] if "q25_spearman" in audit else None, fmt="o", ms=3.5, color=COLORS["blue"])
    ax.set_yticks(y, [s.replace("_", " ") for s in audit["source"]])
    ax.set_xlabel("Validation-test rank Spearman")
    ax.axvline(0, color=COLORS["dark"], lw=0.7)
    overall = rank[rank["source"].eq("overall")].iloc[0]
    ax.text(0.02, 0.98, f"Overall median={overall['median_spearman']:.3f}\nTop-1={overall['top1_match_rate']:.3f}; Top-3={overall['test_top_in_valid_top3_rate']:.3f}", transform=ax.transAxes, va="top", fontsize=6.2)
    panel_label(ax, "d")
    fig.tight_layout(w_pad=2.0, h_pad=2.0)
    return save_bundle(fig, "fig05_moleculenet_and_rank_audit")


def figure_tdc_forest() -> Path:
    table_path = ROOT / "reports" / "manuscript_tables" / "table15_tdc_performance_mode_retained_best.csv"
    old_path = ROOT / "reports" / "tdc_full_panel_appendix_benchmark" / "metrics_raw.csv"
    new_path = ROOT / "reports" / "tdc_performance_mode_appendix_combined" / "selected_metrics_raw.csv"
    table = pd.read_csv(table_path)
    old = pd.read_csv(old_path)
    new = pd.read_csv(new_path)
    rows = []
    tcrit = 4.303
    for _, row in table.iterrows():
        dataset = row["dataset"]
        metric = row["official_metric"]
        direction = row["primary_direction"]
        if row["retained_source"] == "performance_mode":
            old_sub = old[(old["dataset"].eq(dataset)) & (old["model"].eq(row["previous_model"]))][["seed", "primary_value"]].rename(columns={"primary_value": "old"})
            new_sub = new[new["dataset"].eq(dataset)][["seed", "primary_value"]].rename(columns={"primary_value": "new"})
            paired = old_sub.merge(new_sub, on="seed", how="inner")
            delta = paired["new"] - paired["old"] if direction == "higher" else paired["old"] - paired["new"]
            rel = delta / max(abs(float(row["previous_primary_mean"])), 1e-8)
        else:
            rel = pd.Series([0.0, 0.0, 0.0])
        mean = float(rel.mean())
        sd = float(rel.std(ddof=1)) if len(rel) > 1 else 0.0
        ci = tcrit * sd / np.sqrt(max(1, len(rel)))
        rows.append({"dataset": dataset, "family": row["family"], "metric": metric, "n_seeds": len(rel), "retained_source": row["retained_source"], "relative_gain": mean, "ci95_low": mean - ci, "ci95_high": mean + ci, "raw_retained_value": row["retained_primary_mean"], "raw_previous_value": row["previous_primary_mean"]})
    forest = pd.DataFrame(rows).sort_values(["family", "relative_gain"], ascending=[True, True]).reset_index(drop=True)
    forest.to_csv(SRC / "fig06_tdc_22_endpoint_forest.csv", index=False)
    copy_source(table_path, "fig06_tdc_22_endpoint_raw_table.csv")

    fig, ax = plt.subplots(figsize=(7.2, 6.2))
    y = np.arange(len(forest))
    colors = np.where(forest["retained_source"].eq("performance_mode"), COLORS["blue"], COLORS["grey"])
    xerr = np.vstack([forest["relative_gain"] - forest["ci95_low"], forest["ci95_high"] - forest["relative_gain"]])
    ax.errorbar(forest["relative_gain"], y, xerr=xerr, fmt="none", ecolor=COLORS["light"], capsize=2, lw=1)
    ax.scatter(forest["relative_gain"], y, c=colors, s=22, zorder=3)
    labels = [f"{d} ({m})" for d, m in zip(forest["dataset"], forest["metric"])]
    ax.set_yticks(y, labels)
    ax.axvline(0, color=COLORS["dark"], lw=0.8)
    ax.set_xlabel("Relative gain over frozen RF/LGBM baseline (mean and 95% paired CI)")
    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    ax.grid(axis="x", color="#E7E9EC", lw=0.6)
    ax.text(0.99, 0.01, "Blue: promoted by the frozen validation policy\nGrey: baseline retained (tie by policy)", transform=ax.transAxes, ha="right", va="bottom", fontsize=6.2)
    panel_label(ax, "a")
    fig.tight_layout()
    return save_bundle(fig, "fig06_tdc_22_endpoint_forest")


def risk_curve(loss: np.ndarray, score: np.ndarray, task: str, coverages: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(loss)
    order = np.argsort(score)
    oracle_order = np.argsort(loss)
    full = float(np.sqrt(np.mean(loss))) if task == "regression" else float(np.mean(loss))
    obs, oracle, random = [], [], []
    for c in coverages:
        k = max(1, int(round(c * n)))
        if task == "regression":
            obs.append(float(np.sqrt(np.mean(loss[order[:k]]))))
            oracle.append(float(np.sqrt(np.mean(loss[oracle_order[:k]]))))
        else:
            obs.append(float(np.mean(loss[order[:k]])))
            oracle.append(float(np.mean(loss[oracle_order[:k]])))
        random.append(full)
    return np.asarray(obs), np.asarray(oracle), np.asarray(random)


def figure_risk_coverage() -> Path:
    raw_path = ROOT / "reports" / "risk_calibrated_selector" / "compound_risk_predictions.csv"
    raw = pd.read_csv(raw_path)
    wanted = [
        ("moleculenet", "bbbp", "BBBP", "classification"),
        ("moleculenet", "clintox", "ClinTox", "classification"),
        ("tdc_admet", "tdc_caco2_wang", "Caco2_Wang", "regression"),
        ("tdc_admet", "tdc_pgp_broccatelli", "Pgp_Broccatelli", "classification"),
    ]
    coverages = np.arange(0.1, 1.01, 0.1)
    curve_rows, metric_rows = [], []
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.2), sharex=True)
    for panel, (ax, (source, dataset, title, task)) in enumerate(zip(axes.ravel(), wanted)):
        subset = raw[(raw["source"].eq(source)) & (raw["dataset"].eq(dataset))].copy()
        per_seed = []
        for seed, group in subset.groupby("seed"):
            if task == "classification":
                loss = ((group["y_pred_calibrated"].to_numpy() >= 0.5).astype(int) != group["y_true"].to_numpy().astype(int)).astype(float)
            else:
                loss = (group["y_pred_calibrated"].to_numpy() - group["y_true"].to_numpy()) ** 2
            obs, oracle, random = risk_curve(loss, group["risk_score"].to_numpy(), task, coverages)
            per_seed.append(obs)
            aurc = float(np.trapezoid(obs, coverages))
            oracle_aurc = float(np.trapezoid(oracle, coverages))
            random_aurc = float(np.trapezoid(random, coverages))
            metric_rows.append({"source": source, "dataset": dataset, "seed": seed, "task_type": task, "aurc": aurc, "oracle_aurc": oracle_aurc, "e_aurc": aurc - oracle_aurc, "random_aurc": random_aurc, "gain_vs_random": random_aurc - aurc})
            for c, o, q, r in zip(coverages, obs, oracle, random):
                curve_rows.append({"source": source, "dataset": dataset, "seed": seed, "coverage": c, "observed_risk": o, "oracle_risk": q, "random_risk": r})
        matrix = np.vstack(per_seed)
        means = matrix.mean(axis=0)
        sds = matrix.std(axis=0, ddof=1) if len(matrix) > 1 else np.zeros_like(means)
        curve_df = pd.DataFrame(curve_rows)
        agg = curve_df[(curve_df["source"].eq(source)) & (curve_df["dataset"].eq(dataset))].groupby("coverage", as_index=False).agg(oracle=("oracle_risk", "mean"), random=("random_risk", "mean"))
        ax.plot(coverages, means, color=COLORS["blue"], marker="o", ms=2.5, lw=1.4, label="Risk-ranked retention")
        ax.fill_between(coverages, np.maximum(0, means - sds), means + sds, color=COLORS["blue"], alpha=0.12, linewidth=0)
        ax.plot(agg["coverage"], agg["oracle"], color=COLORS["green"], lw=1.1, ls="--", label="Error-oracle")
        ax.plot(agg["coverage"], agg["random"], color=COLORS["grey"], lw=1.1, ls=":", label="Random rejection")
        metrics = pd.DataFrame(metric_rows)
        m = metrics[(metrics["source"].eq(source)) & (metrics["dataset"].eq(dataset))]
        ax.text(0.04, 0.96, f"AURC={m['aurc'].mean():.3f}\nE-AURC={m['e_aurc'].mean():.3f}", transform=ax.transAxes, va="top", fontsize=6.2)
        ax.set_title(title)
        ax.set_ylabel("RMSE" if task == "regression" else "Error rate")
        ax.grid(color="#E7E9EC", lw=0.6)
        panel_label(ax, chr(ord("a") + panel))
    for ax in axes[-1]:
        ax.set_xlabel("Coverage retained")
    axes[0, 0].legend(ncol=1, loc="center right")
    fig.tight_layout(w_pad=1.8, h_pad=1.8)
    curves = pd.DataFrame(curve_rows)
    metrics = pd.DataFrame(metric_rows)
    curves.to_csv(SRC / "fig07_risk_coverage_curves.csv", index=False)
    metrics.to_csv(SRC / "fig07_aurc_eaurc_metrics.csv", index=False)
    return save_bundle(fig, "fig07_risk_coverage_aurc")


def figure_conformal_similarity() -> Path:
    conf_path = ROOT / "reports" / "remaining_missing_experiments_20260606" / "conformal_80_90_95_summary.csv"
    sim_path = ROOT / "reports" / "remaining_missing_experiments_20260606" / "exact_tanimoto_bins_summary.csv"
    conf = pd.read_csv(conf_path)
    sim = pd.read_csv(sim_path)
    copy_source(conf_path, "fig08_conformal_80_90_95.csv")
    copy_source(sim_path, "fig08_exact_tanimoto_bins.csv")
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.2))

    ax = axes[0, 0]
    for task, color, marker in [("classification", COLORS["blue"], "o"), ("regression", COLORS["orange"], "s")]:
        s = conf[conf["task_type"].eq(task)]
        ax.plot(s["target_coverage"], s["coverage_mean"], marker=marker, ms=4, lw=1.4, color=color, label=task.title())
    ax.plot([0.78, 0.97], [0.78, 0.97], color=COLORS["dark"], ls="--", lw=0.8, label="Ideal")
    ax.set(xlabel="Nominal coverage", ylabel="Empirical coverage", xlim=(0.78, 0.97), ylim=(0.78, 0.98))
    ax.legend()
    panel_label(ax, "a")

    ax = axes[0, 1]
    cls = conf[conf["task_type"].eq("classification")]
    reg = conf[conf["task_type"].eq("regression")]
    ax.plot(cls["target_coverage"], cls["avg_set_size_mean"], marker="o", color=COLORS["blue"], lw=1.4, label="Classification set size")
    ax.set_xlabel("Nominal coverage")
    ax.set_ylabel("Mean prediction-set size", color=COLORS["blue"])
    ax2 = ax.twinx()
    ax2.plot(reg["target_coverage"], reg["mean_width_mean"], marker="s", color=COLORS["orange"], lw=1.4, label="Regression interval width")
    ax2.set_ylabel("Mean regression interval width", color=COLORS["orange"])
    ax.spines["top"].set_visible(False); ax2.spines["top"].set_visible(False)
    panel_label(ax, "b")

    order = [">0.7", "0.5-0.7", "<0.5"]
    ax = axes[1, 0]
    for (source, task), group in sim.groupby(["source", "task_type"]):
        g = group.set_index("similarity_bin").reindex(order)
        label = f"{source.title()} {task[:3]}"
        color = COLORS["blue"] if source == "moleculenet" else COLORS["green"]
        marker = "o" if task == "classification" else "s"
        ax.plot(order, g["high_error_enrichment"], marker=marker, lw=1.3, color=color, alpha=0.9 if task == "classification" else 0.55, label=label)
    ax.axhline(1, color=COLORS["dark"], ls="--", lw=0.8)
    ax.set_ylabel("High-error enrichment")
    ax.set_xlabel("Maximum train-set Tanimoto similarity")
    ax.legend(ncol=2)
    panel_label(ax, "c")

    ax = axes[1, 1]
    cls = sim[(sim["source"].eq("moleculenet")) & (sim["task_type"].eq("classification"))].set_index("similarity_bin").reindex(order)
    reg = sim[(sim["source"].eq("moleculenet")) & (sim["task_type"].eq("regression"))].set_index("similarity_bin").reindex(order)
    ax.plot(order, cls["roc_auc"], marker="o", color=COLORS["blue"], lw=1.4, label="Classification ROC-AUC")
    ax.set_ylabel("ROC-AUC", color=COLORS["blue"])
    ax.set_xlabel("Maximum train-set Tanimoto similarity")
    ax2 = ax.twinx()
    ax2.plot(order, reg["rmse"], marker="s", color=COLORS["orange"], lw=1.4, label="Regression RMSE")
    ax2.set_ylabel("RMSE", color=COLORS["orange"])
    ax.spines["top"].set_visible(False); ax2.spines["top"].set_visible(False)
    panel_label(ax, "d")

    for ax in axes.ravel():
        ax.grid(axis="y", color="#E7E9EC", lw=0.6)
    fig.tight_layout(w_pad=2.1, h_pad=2.0)
    return save_bundle(fig, "fig08_conformal_and_similarity")


def figure_chemical_boundaries() -> Path:
    gap_path = ROOT / "reports" / "remaining_missing_experiments_20260606" / "moleculeace_gap_correlation_summary.csv"
    cyc_path = ROOT / "reports" / "full_missing_experiment_run_20260611" / "bro5_cycpept_pampa_compact_summary.csv"
    lin_path = ROOT / "reports" / "full_missing_experiment_run_20260611" / "linpept_compact_summary_20260611.csv"
    gap = pd.read_csv(gap_path)
    cyc = pd.read_csv(cyc_path)
    lin = pd.read_csv(lin_path)
    copy_source(gap_path, "fig09_moleculeace_gap_correlation.csv")
    copy_source(cyc_path, "fig09_cycpept_pampa.csv")
    copy_source(lin_path, "fig09_linpept.csv")
    task = gap.groupby("task", as_index=False).agg(gap_spearman=("gap_spearman", "mean"), gap_sd=("gap_spearman", "std"), direction_accuracy=("direction_accuracy", "mean"), direction_sd=("direction_accuracy", "std"), n_pairs=("n_pairs", "mean"))
    task = task.sort_values("gap_spearman")
    task.to_csv(SRC / "fig09_moleculeace_task_summary.csv", index=False)

    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.6))
    ax = axes[0, 0]
    y = np.arange(len(task))
    ax.errorbar(task["gap_spearman"], y, xerr=task["gap_sd"], fmt="o", ms=3, color=COLORS["blue"], ecolor=COLORS["light"], capsize=2)
    ax.set_yticks(y, task["task"])
    ax.axvline(0, color=COLORS["dark"], lw=0.8)
    ax.set_xlabel("Predicted-vs-true activity-gap Spearman")
    panel_label(ax, "a")

    ax = axes[0, 1]
    ax.scatter(task["gap_spearman"], task["direction_accuracy"], s=16 + np.sqrt(task["n_pairs"]) * 1.5, color=COLORS["green"], alpha=0.85)
    ax.axhline(0.5, color=COLORS["dark"], ls="--", lw=0.8)
    ax.axvline(0, color=COLORS["dark"], ls=":", lw=0.8)
    ax.set(xlabel="Gap Spearman", ylabel="Cliff-pair direction accuracy", ylim=(0.35, 1.02))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    panel_label(ax, "b")

    ax = axes[1, 0]
    cyc_means, cyc_sds = zip(*(parse_mean_sd(v) for v in cyc["test_RMSE"]))
    x = np.arange(len(cyc))
    ax.bar(x, cyc_means, yerr=cyc_sds, color=[COLORS["green"], COLORS["blue"], COLORS["orange"], COLORS["purple"]], width=0.65, capsize=3)
    ax.set_xticks(x, cyc["split"].str.title())
    ax.set_ylabel("CycPept-PAMPA RMSE")
    panel_label(ax, "c")

    ax = axes[1, 1]
    lin_plot = []
    for _, row in lin.iterrows():
        roc, roc_sd = parse_mean_sd(row["test_ROC_AUC"])
        pr, pr_sd = parse_mean_sd(row["test_PR_AUC"])
        lin_plot.append({"dataset": row["dataset"], "split": row["split"], "roc": roc, "roc_sd": roc_sd, "pr": pr, "pr_sd": pr_sd})
    lp = pd.DataFrame(lin_plot)
    markers = {"linpept_cellpen": "o", "linpept_nonfouling": "s"}
    colors = {"random": COLORS["green"], "scaffold": COLORS["blue"], "perimeter": COLORS["orange"]}
    for dataset, group in lp.groupby("dataset"):
        for _, row in group.iterrows():
            ax.errorbar(row["roc"], row["pr"], xerr=row["roc_sd"], yerr=row["pr_sd"], fmt=markers[dataset], ms=5, color=colors[row["split"]], capsize=2)
    for split, color in colors.items():
        ax.scatter([], [], color=color, label=split.title())
    ax.scatter([], [], marker="o", color=COLORS["dark"], label="CellPen")
    ax.scatter([], [], marker="s", color=COLORS["dark"], label="NonFouling")
    ax.set(xlabel="LinPept ROC-AUC", ylabel="LinPept PR-AUC", xlim=(0.70, 0.98), ylim=(0.62, 0.94))
    ax.legend(ncol=2, loc="lower right")
    panel_label(ax, "d")

    for ax in axes.ravel():
        ax.grid(color="#E7E9EC", lw=0.6)
    fig.tight_layout(w_pad=2.0, h_pad=2.0)
    return save_bundle(fig, "fig09_chemical_boundaries")


def figure_ablation() -> Path:
    path = ROOT / "reports" / "remaining_missing_experiments_20260606" / "unified_ablation_matrix_summary.csv"
    data = pd.read_csv(path)
    copy_source(path, "fig10_unified_ablation_matrix.csv")
    keep = [
        "best_single", "simple_mean", "no_validation_selector_fixed_morgan", "without_fusion",
        "without_ad_gate", "without_uncertainty_weighting", "without_hier_motif_multifp",
        "without_rescue_head_current",
    ]
    labels = {
        "best_single": "Best single",
        "simple_mean": "Simple mean",
        "no_validation_selector_fixed_morgan": "Fixed Morgan (no selector)",
        "without_fusion": "Without fusion",
        "without_ad_gate": "Without AD gate",
        "without_uncertainty_weighting": "Without uncertainty weighting",
        "without_hier_motif_multifp": "Without motif/multi-FP",
        "without_rescue_head_current": "Without rescue head",
    }
    sub = data[data["category"].isin(keep)].copy()
    sub["label"] = sub["category"].map(labels)
    pivot = sub.pivot(index="label", columns="task_type", values="mean_delta_vs_full_positive").reindex([labels[k] for k in keep])
    fraction = sub.pivot(index="label", columns="task_type", values="positive_fraction_vs_full").reindex(pivot.index)

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 4.4))
    y = np.arange(len(pivot))
    width = 0.34
    axes[0].barh(y - width / 2, pivot.get("classification", pd.Series(index=pivot.index, dtype=float)), height=width, color=COLORS["blue"], label="Classification")
    axes[0].barh(y + width / 2, pivot.get("regression", pd.Series(index=pivot.index, dtype=float)), height=width, color=COLORS["orange"], label="Regression")
    axes[0].set_yticks(y, pivot.index)
    axes[0].invert_yaxis()
    axes[0].axvline(0, color=COLORS["dark"], lw=0.8)
    axes[0].set_xlabel("Mean positive-direction delta versus full system")
    axes[0].legend()
    panel_label(axes[0], "a")

    axes[1].barh(y - width / 2, fraction.get("classification", pd.Series(index=fraction.index, dtype=float)), height=width, color=COLORS["blue"])
    axes[1].barh(y + width / 2, fraction.get("regression", pd.Series(index=fraction.index, dtype=float)), height=width, color=COLORS["orange"])
    axes[1].set_yticks(y, [""] * len(y))
    axes[1].invert_yaxis()
    axes[1].set_xlabel("Fraction of units outperforming full system")
    axes[1].xaxis.set_major_formatter(PercentFormatter(1.0))
    panel_label(axes[1], "b")
    for ax in axes:
        ax.grid(axis="x", color="#E7E9EC", lw=0.6)
    fig.tight_layout(w_pad=1.8)
    return save_bundle(fig, "fig10_unified_ablation")


def contact_sheet(paths: list[Path]) -> Path:
    fig, axes = plt.subplots(5, 2, figsize=(10, 17))
    for ax, path in zip(axes.ravel(), paths):
        image = plt.imread(path)
        ax.imshow(image)
        ax.set_title(path.stem, fontsize=9)
        ax.axis("off")
    for ax in axes.ravel()[len(paths):]:
        ax.axis("off")
    fig.tight_layout()
    out = OUT / "figure_contact_sheet.png"
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out


def write_contracts() -> None:
    text = """# Figure contracts and QA notes

Backend: Python (matplotlib), used exclusively for quantitative rendering and export.
Target output: Journal of Cheminformatics/Nature-leaning double-column figures, 183 mm maximum width.

## Core conclusion and panel map

- Figure 1: frozen workflow and evidence package; conceptual schematic retained unchanged from the prior revision.
- Figure 2: strict selector gate, freeze boundary and outputs; conceptual schematic retained unchanged from the prior revision.
- Figure 3: candidate-pool expansion does not monotonically improve model selection; regret, optimism, Top-3 hit and selection stability are shown.
- Figure 4: true 3x3 nested validation separates inner selection from outer evaluation across nine representative endpoints.
- Figure 5: frozen MoleculeNet results, ClinTox recall at fixed precision and the validation-test rank audit define predictive and selection evidence jointly.
- Figure 6: all 22 TDC endpoints are shown with relative gains and paired confidence intervals for promoted endpoints.
- Figure 7: risk-ranked retention is compared with error-oracle and random rejection baselines; AURC and E-AURC are reported.
- Figure 8: conformal coverage-efficiency and exact Tanimoto bins quantify reliability under coverage and similarity shifts.
- Figure 9: MoleculeACE gap correlation and public bRo5 peptide benchmarks define chemical edge cases.
- Figure 10: the unified ablation matrix reports both positive and negative component effects.

## QA

- All quantitative panels trace to CSV files in `source_data`.
- Error bars are defined in the manuscript captions; no visual significance marks are added without corresponding tests.
- SVG/PDF text remains editable; PNG uses 450 dpi and TIFF uses 600 dpi with LZW compression.
- Test-oracle results are labelled only as retrospective upper bounds and are not used for model selection.
- Figure 6 uses direction-normalized relative gain because endpoints use heterogeneous official metrics.
- Figure 7 integrates AURC over retained coverage 0.1-1.0; E-AURC is AURC minus error-oracle AURC.
"""
    (OUT / "figure_contracts_and_qa.md").write_text(text, encoding="utf-8")


def main() -> None:
    paths = retain_conceptual_figures()
    paths.extend(
        [
            figure_candidate_pool(),
            figure_nested_validation(),
            figure_moleculenet_and_clintox(),
            figure_tdc_forest(),
            figure_risk_coverage(),
            figure_conformal_similarity(),
            figure_chemical_boundaries(),
            figure_ablation(),
        ]
    )
    write_contracts()
    sheet = contact_sheet(paths)
    print("Generated figures:")
    for path in paths:
        print(path)
    print("Contact sheet:", sheet)


if __name__ == "__main__":
    main()
