from __future__ import annotations

import math
import os
import shutil
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import build_small_paper3_figures as legacy
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.ticker import PercentFormatter
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / "output" / "小论文-4_图表包"
PACKAGE = Path(os.environ.get("FZYC_FIGURE_PACKAGE", str(ROOT / "output" / "小论文-5_图表包")))
FIG = PACKAGE / "figures"
SRC = PACKAGE / "source_data"
CORE = ROOT / "results" / "reviewer_core_20260624"
MULTI = CORE / "multiview_nested"

COL = {
    "ink": "#182230", "muted": "#667085", "line": "#98A2B3",
    "blue": "#3568A8", "blue2": "#7EA6D8", "green": "#4E9A73",
    "orange": "#D98C3F", "purple": "#8B75AF", "red": "#BF5B5B",
    "teal": "#3C8D93", "grey": "#737B86", "light": "#D8DEE6",
    "pblue": "#EAF2FB", "pgreen": "#EDF7F0", "porange": "#FFF3E8",
    "ppurple": "#F3EFF9", "pteal": "#EAF6F6",
}


def setup() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    SRC.mkdir(parents=True, exist_ok=True)
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Microsoft YaHei", "DejaVu Sans", "sans-serif"],
        "font.size": 10.0,
        "axes.titlesize": 11.4,
        "axes.labelsize": 10.3,
        "xtick.labelsize": 9.0,
        "ytick.labelsize": 9.0,
        "legend.fontsize": 8.5,
        "axes.linewidth": 0.9,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "savefig.facecolor": "white",
        "figure.facecolor": "white",
    })


def panel(ax: plt.Axes, label: str, x: float = -0.15, y: float = 1.08) -> None:
    ax.text(x, y, label, transform=ax.transAxes, fontsize=12.2, fontweight="bold", va="top", color=COL["ink"])


def style(ax: plt.Axes, grid: str | None = "y") -> None:
    ax.tick_params(length=3.2, width=0.8, colors=COL["ink"])
    ax.spines["left"].set_color(COL["ink"])
    ax.spines["bottom"].set_color(COL["ink"])
    if grid:
        ax.grid(axis=grid, color="#E7EAF0", linewidth=0.6, zorder=0)


def save(fig: plt.Figure, stem: str) -> None:
    fig.savefig(FIG / f"{stem}.svg", bbox_inches="tight")
    fig.savefig(FIG / f"{stem}.png", dpi=450, bbox_inches="tight")
    fig.savefig(FIG / f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)
    with Image.open(FIG / f"{stem}.png") as im:
        im.convert("RGB").save(FIG / f"{stem}.tiff", compression="tiff_lzw", dpi=(450, 450))


def copy_csv(path: Path, name: str | None = None) -> None:
    if path.exists():
        shutil.copy2(path, SRC / (name or path.name))


def copy_existing(old_stem: str, new_stem: str) -> None:
    for ext in ("png", "svg"):
        shutil.copy2(OLD / "figures" / f"{old_stem}.{ext}", FIG / f"{new_stem}.{ext}")
    with Image.open(FIG / f"{new_stem}.png") as im:
        rgb = im.convert("RGB")
        rgb.save(FIG / f"{new_stem}.tiff", compression="tiff_lzw", dpi=(450, 450))
        fig = plt.figure(figsize=(rgb.width / 450, rgb.height / 450), dpi=450)
        ax = fig.add_axes([0, 0, 1, 1]); ax.imshow(rgb); ax.axis("off")
        fig.savefig(FIG / f"{new_stem}.pdf", dpi=450, bbox_inches="tight", pad_inches=0)
        plt.close(fig)


def add_raster_formats(stem: str) -> None:
    with Image.open(FIG / f"{stem}.png") as im:
        rgb = im.convert("RGB")
        rgb.save(FIG / f"{stem}.tiff", compression="tiff_lzw", dpi=(450, 450))
        fig = plt.figure(figsize=(rgb.width / 450, rgb.height / 450), dpi=450)
        ax = fig.add_axes([0, 0, 1, 1]); ax.imshow(rgb); ax.axis("off")
        fig.savefig(FIG / f"{stem}.pdf", dpi=450, bbox_inches="tight", pad_inches=0)
        plt.close(fig)


def _workflow_box(ax, x, y, w, h, title, lines, fc, ec):
    patch = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.008,rounding_size=0.015", facecolor=fc, edgecolor=ec, lw=1.25)
    ax.add_patch(patch)
    ax.text(x + 0.014, y + h - 0.025, title, va="top", fontsize=10.0, fontweight="bold", color=COL["ink"])
    ax.text(x + 0.014, y + h - 0.083, "\n".join(lines), va="top", fontsize=7.8, linespacing=1.35, color=COL["muted"])


def figure01_overall_workflow() -> None:

    # It avoids the column-title collision seen in the simplified temporary version.
    copy_existing("fig01_overall_workflow", "fig01_overall_workflow")
    pd.DataFrame([
        {"stage": "task protocol", "detail": "benchmarks, frozen splits, leakage controls"},
        {"stage": "molecular views", "detail": "graph and bonds, fingerprints, descriptors, frozen embeddings"},
        {"stage": "expert pool", "detail": "graph experts, tabular experts, frozen heads, registered candidates"},
        {"stage": "governance", "detail": "validation ranking, selection risk, AD/UQ gate, decision"},
        {"stage": "evidence outputs", "detail": "prediction, reliability, shift, audit trail"},
    ]).to_csv(SRC / "fig01_source_data.csv", index=False)


def regenerate_legacy_quantitative_figures() -> None:
    legacy.PACKAGE = PACKAGE; legacy.FIG_DIR = FIG; legacy.SRC_DIR = SRC
    jobs = [
        (legacy.figure03_candidate_pool_and_null, "fig03_candidate_pool_and_null", "fig02_candidate_pool_controls"),
        (legacy.figure04_nested_selection_risk, "fig04_nested_selection_risk", "fig03_repeated_nested_selection"),
        (legacy.figure05_moleculenet_rank_audit, "fig05_moleculenet_rank_audit", "fig06_moleculenet_decisions"),
        (legacy.figure06_tdc_gate_audit, "fig06_tdc_gate_audit", "fig07_tdc_gate_audit"),
    ]
    for fn, old, new in jobs:
        fn()
        for ext in ("png", "svg"):
            source, target = FIG/f"{old}.{ext}", FIG/f"{new}.{ext}"
            if target.exists(): target.unlink()
            source.replace(target)
        add_raster_formats(new)


def figure04_metric_calibration_and_meta_risk() -> None:
    ep = pd.read_csv(CORE / "paired_pool_endpoint_effects.csv")
    sig = pd.read_csv(CORE / "signal_recovery_summary.csv")
    quart = pd.read_csv(CORE / "risk_quartiles.csv")
    meta = pd.read_csv(CORE / "cross_endpoint_meta_risk_endpoint_summary.csv")
    for p in [CORE / "paired_pool_endpoint_effects.csv", CORE / "signal_recovery_summary.csv", CORE / "risk_quartiles.csv", CORE / "cross_endpoint_meta_risk_endpoint_summary.csv"]:
        copy_csv(p, f"fig04_{p.name}")

    fig, axes = plt.subplots(2, 2, figsize=(8.65, 6.85))
    ax = axes[0, 0]
    e = ep[(ep.metric == "fixed_normalized_regret") & (ep.comparison == "K=32 vs K=4")].dropna(subset=["32_minus_4"]).sort_values("32_minus_4")
    y = np.arange(len(e))
    ax.scatter(e["32_minus_4"], y, color=COL["blue"], s=30, zorder=3)
    ax.axvline(0, color=COL["ink"], lw=0.9)
    ax.set_yticks(y, e.endpoint.str.replace("tdc_", "", regex=False).str.replace("_", " ", regex=False))
    ax.tick_params(axis="y", labelsize=7.8)
    ax.set_xlabel("Paired fixed-regret change, K=32 − K=4")
    ax.set_title("Endpoint-paired expansion effect", loc="left")
    ax.text(0.98, 0.03, "Mean +0.122\n95% CI 0.072–0.175", transform=ax.transAxes, ha="right", va="bottom", fontsize=8.1, color=COL["muted"])
    style(ax, "x"); panel(ax, "a", -0.22)

    ax = axes[0, 1]
    s = sig[sig.pool_size == 32].sort_values("signal_correlation")
    ax.plot(s.signal_correlation, s.chance_adjusted_hit_mean, color=COL["blue"], marker="o", lw=1.7, label="Chance-adjusted Top-3")
    ax.fill_between(s.signal_correlation, s.chance_adjusted_hit_ci95_low, s.chance_adjusted_hit_ci95_high, color=COL["blue2"], alpha=0.25)
    ax.axhline(0, color=COL["ink"], lw=0.8, ls="--")
    ax.set(xlabel="Injected validation–outer signal", ylabel="Chance-adjusted hit", ylim=(-0.12, 1.05))
    ax2 = ax.twinx()
    ax2.plot(s.signal_correlation, s.fixed_normalized_regret_mean, color=COL["orange"], marker="s", lw=1.55, label="Fixed regret")
    ax2.set_ylabel("Fixed regret", color=COL["orange"]); ax2.tick_params(axis="y", colors=COL["orange"]); ax2.spines["top"].set_visible(False)
    handles = ax.get_lines()[:1] + ax2.get_lines()[:1]
    ax.legend(handles, [h.get_label() for h in handles], loc="upper center", fontsize=7.7)
    ax.set_title("Signal-recovery positive control (K=32)", loc="left")
    style(ax, "y"); panel(ax, "b")

    ax = axes[1, 0]
    ax.bar(np.arange(4), quart.mean_regret, color=[COL["blue2"], COL["light"], COL["orange"], COL["red"]], width=0.7)
    ax.set_xticks(np.arange(4), ["Q1\nlow", "Q2", "Q3", "Q4\nhigh"])
    ax.set_ylabel("Mean fixed regret")
    ax.set_title("Equal-weight selection-risk\nnegative validation", loc="left")
    ax.text(0.04, 0.94, "Within-stratum permutation P=0.953\nLOEO gate CI crossed zero", transform=ax.transAxes, va="top", fontsize=8.0, color=COL["muted"])
    style(ax, "y"); panel(ax, "c")

    ax = axes[1, 1]
    m = meta.sort_values("risk_gate_delta")
    y = np.arange(len(m))
    colors = np.where(m.risk_gate_delta < 0, COL["green"], COL["red"])
    ax.scatter(m.risk_gate_delta, y, color=colors, s=30, zorder=3)
    ax.axvline(0, color=COL["ink"], lw=0.9)
    ax.axvspan(-0.047, -0.020, color=COL["pgreen"], zorder=0)
    ax.set_yticks(y, m.endpoint.str.replace("tdc_", "", regex=False).str.replace("_", " ", regex=False))
    ax.tick_params(axis="y", labelsize=7.8)
    ax.set_xlabel("50% gate regret change (retained − all)")
    ax.set_title("Strict LOEO meta-risk", loc="left")
    ax.text(0.98, 0.04, "8/9 endpoints improved\nMean −0.034", transform=ax.transAxes, ha="right", va="bottom", fontsize=8.1, color=COL["muted"])
    style(ax, "x"); panel(ax, "d", -0.22)
    fig.tight_layout(w_pad=2.65, h_pad=3.05)
    save(fig, "fig04_metric_calibration_meta_risk")


def figure05_multiview_confirmation() -> None:
    policy = pd.read_csv(MULTI / "policy_summary.csv")
    paired = pd.read_csv(MULTI / "paired_multiview_effects.csv")
    counts = pd.read_csv(MULTI / "endpoint_representation_counts.csv")
    overall = pd.read_csv(MULTI / "validation_best_representation_counts.csv")
    for p in [MULTI / "policy_summary.csv", MULTI / "paired_multiview_effects.csv", MULTI / "endpoint_representation_counts.csv", MULTI / "validation_best_representation_counts.csv", MULTI / "candidate_registry.csv"]:
        copy_csv(p, f"fig05_{p.name}")

    fig, axes = plt.subplots(2, 2, figsize=(8.2, 6.35))
    ax = axes[0, 0]
    order = ["fixed_morgan_rf", "one_se_stable", "risk_adjusted", "validation_best"]
    p = policy[(policy.variant == "full_multiview") & policy.policy.isin(order)].copy()
    p["policy"] = pd.Categorical(p.policy, order, ordered=True); p = p.sort_values("policy")
    x = np.arange(len(p)); y = p.mean_normalized_regret.to_numpy()
    yerr = np.vstack([y - p.endpoint_cluster_ci95_low.to_numpy(), p.endpoint_cluster_ci95_high.to_numpy() - y])
    ax.bar(x, y, color=[COL["grey"], COL["purple"], COL["orange"], COL["blue"]], width=0.68)
    ax.errorbar(x, y, yerr=yerr, fmt="none", color=COL["ink"], capsize=3, lw=1)
    ax.set_xticks(x, ["Fixed\nMorgan RF", "one-SE", "Risk-\nadjusted", "Validation-\nbest"])
    ax.set_ylabel("Mean normalized regret")
    ax.set_title("Governance in the 12-candidate pool", loc="left")
    style(ax, "y"); panel(ax, "a")

    ax = axes[0, 1]
    wanted = [
        "attainable multiview gain vs Morgan-only oracle",
        "realized multiview validation-best gain vs Morgan-only",
        "concatenated multiview gain vs separate-view pool",
        "validation-best gain vs one-SE in full pool",
    ]
    labels = ["Attainable vs\nMorgan oracle", "Realized vs\nMorgan selection", "Concat vs\nseparate views", "Validation-best\nvs one-SE"]
    q = paired.set_index("comparison").loc[wanted].reset_index()
    y = np.arange(len(q)); val = q.mean_normalized_utility_gain.to_numpy()
    xerr = np.vstack([val - q.endpoint_cluster_ci95_low.to_numpy(), q.endpoint_cluster_ci95_high.to_numpy() - val])
    ax.errorbar(val, y, xerr=xerr, fmt="o", color=COL["blue"], ecolor=COL["light"], capsize=3, ms=5)
    ax.axvline(0, color=COL["ink"], lw=0.9)
    ax.set_yticks(y, labels); ax.set_xlabel("Paired normalized utility gain")
    ax.set_title("Attainable and realised multiview gain", loc="left")
    style(ax, "x"); panel(ax, "b", -0.20)

    ax = axes[1, 0]
    o = overall[overall.variant == "full_multiview"].set_index("selected_representation").reindex(["morgan512", "maccs", "rdkit2d", "multiview"]).fillna(0)
    ax.bar(np.arange(4), o["size"], color=[COL["blue2"], COL["green"], COL["orange"], COL["purple"]], width=0.68)
    ax.set_xticks(np.arange(4), ["Morgan", "MACCS", "RDKit2D", "Concatenated\nmultiview"])
    ax.set_ylabel("Validation-best selections (n=135)")
    ax.set_title("Representation selected on frozen validation folds", loc="left")
    for i, v in enumerate(o["size"]): ax.text(i, v + 2, f"{int(v)}", ha="center", fontsize=8.2)
    style(ax, "y"); panel(ax, "c")

    ax = axes[1, 1]
    heat = counts.pivot(index="task", columns="selected_representation", values="size").fillna(0)
    heat = heat.reindex(columns=["morgan512", "maccs", "rdkit2d", "multiview"], fill_value=0)
    im = ax.imshow(heat.to_numpy(), aspect="auto", cmap="Blues", vmin=0)
    ax.set_xticks(np.arange(4), ["Morgan", "MACCS", "RDKit2D", "Concat"], rotation=25, ha="right")
    ax.set_yticks(np.arange(len(heat)), [x.replace("tdc_", "").replace("_", " ") for x in heat.index])
    ax.tick_params(axis="both", labelsize=7.6)
    for i in range(heat.shape[0]):
        for j in range(heat.shape[1]):
            ax.text(j, i, f"{int(heat.iloc[i, j])}", ha="center", va="center", fontsize=7.2, color=COL["ink"])
    ax.set_title("Endpoint × representation selection map", loc="left")
    panel(ax, "d", -0.20)
    cbar = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.03); cbar.ax.tick_params(labelsize=7.2)
    fig.tight_layout(w_pad=2.2, h_pad=2.1)
    save(fig, "fig05_multiview_confirmation")


def _risk_curve(loss: np.ndarray, score: np.ndarray, task: str, coverages: np.ndarray):
    order = np.argsort(score); oracle_order = np.argsort(loss)
    full = float(np.sqrt(np.mean(loss))) if task == "regression" else float(np.mean(loss))
    obs, oracle = [], []
    for c in coverages:
        k = max(1, int(round(c * len(loss))))
        if task == "regression":
            obs.append(float(np.sqrt(np.mean(loss[order[:k]])))); oracle.append(float(np.sqrt(np.mean(loss[oracle_order[:k]]))))
        else:
            obs.append(float(np.mean(loss[order[:k]]))); oracle.append(float(np.mean(loss[oracle_order[:k]])))
    return np.asarray(obs), np.asarray(oracle), np.repeat(full, len(coverages))


def figure08_prediction_reliability_and_conformal() -> None:
    raw_path = ROOT / "reports" / "risk_calibrated_selector" / "compound_risk_predictions.csv"
    conf_path = ROOT / "results" / "source_data" / "conformal_long.csv"
    raw = pd.read_csv(raw_path); conf = pd.read_csv(conf_path)
    copy_csv(raw_path, "fig08_compound_risk_predictions.csv"); copy_csv(conf_path, "fig08_conformal_long.csv")
    fig, axes = plt.subplots(2, 3, figsize=(9.2, 6.0))
    coverages = np.arange(0.1, 1.01, 0.1)
    wanted = [("moleculenet", "bbbp", "BBBP", "classification"), ("moleculenet", "clintox", "ClinTox", "classification"), ("tdc_admet", "tdc_caco2_wang", "Caco2", "regression")]
    curve_rows = []
    for i, (ax, (source, endpoint, title, task)) in enumerate(zip(axes[0], wanted)):
        subset = raw[(raw.source == source) & (raw.dataset == endpoint)]
        observed, oracle, random = [], [], []
        for seed, g in subset.groupby("seed"):
            if task == "classification":
                loss = ((g.y_pred_calibrated.to_numpy() >= 0.5).astype(int) != g.y_true.to_numpy().astype(int)).astype(float)
            else:
                loss = (g.y_pred_calibrated.to_numpy() - g.y_true.to_numpy()) ** 2
            o, q, r = _risk_curve(loss, g.risk_score.to_numpy(), task, coverages)
            observed.append(o); oracle.append(q); random.append(r)
            for c, ov, oq, rr in zip(coverages, o, q, r): curve_rows.append({"source": source, "endpoint": endpoint, "seed": seed, "coverage": c, "observed_risk": ov, "oracle_risk": oq, "random_risk": rr})
        om = np.mean(observed, 0); osd = np.std(observed, 0, ddof=1); qm = np.mean(oracle, 0); rm = np.mean(random, 0)
        ax.plot(coverages, om, color=COL["blue"], marker="o", ms=3, lw=1.55, label="Risk-ranked")
        ax.fill_between(coverages, np.maximum(0, om-osd), om+osd, color=COL["pblue"])
        ax.plot(coverages, qm, color=COL["green"], ls="--", lw=1.25, label="Oracle risk lower bound")
        ax.plot(coverages, rm, color=COL["grey"], ls=":", lw=1.25, label="Random rejection")
        ax.set_title(title, loc="left"); ax.set_xlabel("Coverage retained"); ax.set_ylabel("RMSE" if task == "regression" else "Error rate")
        style(ax); panel(ax, chr(ord("a")+i));
        if i == 0: ax.legend(loc="best", fontsize=7.2)
    pd.DataFrame(curve_rows).to_csv(SRC / "fig08_prediction_risk_curves.csv", index=False)

    cls = conf[conf.task_type == "classification"]
    reg = conf[conf.task_type == "regression"]
    rows = []
    for task, frame in [("classification", cls), ("regression", reg)]:
        for target, g in frame.groupby("target_coverage"):
            row = {"task_type": task, "target_coverage": target, "coverage": g.coverage.mean(), "coverage_sd": g.coverage.std(ddof=1)}
            if task == "classification": row.update({"class0": g.class_0_coverage.mean(), "class1": g.class_1_coverage.mean(), "set_size": g.avg_set_size.mean(), "fallback": g.fallback_reason.notna().mean()})
            else: row.update({"width_sd": g.normalized_width_sd.mean()})
            rows.append(row)
    summary = pd.DataFrame(rows); summary.to_csv(SRC / "fig08_conformal_summary.csv", index=False)
    c = summary[summary.task_type == "classification"]; r = summary[summary.task_type == "regression"]
    ax = axes[1, 0]
    ax.plot(c.target_coverage, c.coverage, marker="o", color=COL["blue"], lw=1.5, label="Overall")
    ax.plot(c.target_coverage, c.class0, marker="s", color=COL["green"], lw=1.3, label="Class 0")
    ax.plot(c.target_coverage, c.class1, marker="^", color=COL["orange"], lw=1.3, label="Class 1")
    ax.plot([0.78,0.97],[0.78,0.97], color=COL["ink"], ls="--", lw=0.8)
    ax.set(xlabel="Nominal coverage", ylabel="Classification coverage", xlim=(0.78,0.97), ylim=(0.62,1.0)); ax.legend(loc="lower right", fontsize=7.2); style(ax); panel(ax,"d")
    ax = axes[1, 1]
    ax.errorbar(r.target_coverage, r.coverage, yerr=r.coverage_sd, marker="o", color=COL["purple"], lw=1.5, capsize=3)
    ax.plot([0.78,0.97],[0.78,0.97], color=COL["ink"], ls="--", lw=0.8)
    ax.set(xlabel="Nominal coverage", ylabel="Regression coverage", xlim=(0.78,0.97), ylim=(0.72,1.02)); style(ax); panel(ax,"e")
    ax = axes[1, 2]
    ax.plot(r.target_coverage, r.width_sd, marker="o", color=COL["teal"], lw=1.5, label="Width / train-label SD")
    ax.set(xlabel="Nominal coverage", ylabel="Standardised interval width"); style(ax); panel(ax,"f")
    ax2 = ax.twinx(); ax2.plot(c.target_coverage, c.fallback, marker="s", color=COL["orange"], lw=1.3, label="Pooled fallback")
    ax2.set_ylabel("Classification fallback", color=COL["orange"]); ax2.yaxis.set_major_formatter(PercentFormatter(1)); ax2.tick_params(axis="y", colors=COL["orange"]); ax2.spines["top"].set_visible(False)
    fig.tight_layout(w_pad=2.1, h_pad=2.0)
    save(fig, "fig08_prediction_reliability_conformal")


def _mean_sd(value: object) -> tuple[float, float]:
    import re
    vals = re.findall(r"[-+]?\d+(?:\.\d+)?", str(value))
    return (float(vals[0]), float(vals[1]) if len(vals)>1 else 0.0) if vals else (math.nan, math.nan)


def _box(ax, x, y, w, h, title, body, fc):
    p = FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.008,rounding_size=0.02",facecolor=fc,edgecolor=COL["line"],lw=1.0)
    ax.add_patch(p); ax.text(x+0.018,y+h-0.028,title,va="top",fontsize=9.1,fontweight="bold",color=COL["ink"])
    ax.text(x+0.018,y+h-0.085,body,va="top",fontsize=7.8,linespacing=1.35,color=COL["muted"])


def figure09_chemical_boundaries_and_decision_card() -> None:
    gap_path = ROOT / "reports" / "remaining_missing_experiments_20260606" / "moleculeace_gap_correlation_summary.csv"
    cyc_path = ROOT / "reports" / "full_missing_experiment_run_20260611" / "bro5_cycpept_pampa_compact_summary.csv"
    lin_path = ROOT / "reports" / "full_missing_experiment_run_20260611" / "linpept_compact_summary_20260611.csv"
    fail_path = ROOT / "reports" / "supplement_experiment_revision_20260606" / "maintext_table_failure_cases_compact.csv"
    gap = pd.read_csv(gap_path); cyc = pd.read_csv(cyc_path); lin = pd.read_csv(lin_path)
    for p in [gap_path,cyc_path,lin_path,fail_path]: copy_csv(p, f"fig09_{p.name}")
    task = gap.groupby("task",as_index=False).agg(gap_spearman=("gap_spearman","mean"), gap_sd=("gap_spearman","std"), direction_accuracy=("direction_accuracy","mean"), n_pairs=("n_pairs","mean")).sort_values("gap_spearman")
    task.to_csv(SRC / "fig09_moleculeace_task_summary.csv",index=False)

    fig = plt.figure(figsize=(9.2, 6.25)); gs = fig.add_gridspec(2,3,wspace=0.62,hspace=0.62)
    ax=fig.add_subplot(gs[0,0]); y=np.arange(len(task)); ax.errorbar(task.gap_spearman,y,xerr=task.gap_sd,fmt="o",ms=3.5,color=COL["blue"],ecolor=COL["light"],capsize=2); ax.set_yticks(y,task.task); ax.tick_params(axis="y",labelsize=6.8); ax.axvline(0,color=COL["ink"],lw=.8); ax.set_xlabel("Activity-gap Spearman"); ax.set_title("MoleculeACE task heterogeneity",loc="left"); style(ax,"x"); panel(ax,"a",-0.25)
    ax=fig.add_subplot(gs[0,1]); ax.scatter(task.gap_spearman,task.direction_accuracy,s=18+np.sqrt(task.n_pairs)*1.7,color=COL["green"],alpha=.85); ax.axhline(.5,color=COL["ink"],ls="--",lw=.8); ax.axvline(0,color=COL["ink"],ls=":",lw=.8); ax.set(xlabel="Gap Spearman",ylabel="Cliff-pair direction accuracy",ylim=(.35,1.02)); ax.yaxis.set_major_formatter(PercentFormatter(1)); ax.set_title("Direction does not imply magnitude",loc="left"); style(ax); panel(ax,"b")
    ax=fig.add_subplot(gs[0,2]); means,sds=zip(*(_mean_sd(v) for v in cyc.test_RMSE)); x=np.arange(len(cyc)); ax.bar(x,means,yerr=sds,color=[COL["green"],COL["blue"],COL["orange"],COL["purple"]],width=.68,capsize=3); ax.set_xticks(x,cyc.split.str.title(),rotation=20,ha="right"); ax.set_ylabel("CycPept-PAMPA RMSE"); ax.set_title("bRo5 split pressure",loc="left"); style(ax); panel(ax,"c")
    rows=[]
    for _,row in lin.iterrows():
        roc,roc_sd=_mean_sd(row.test_ROC_AUC); pr,pr_sd=_mean_sd(row.test_PR_AUC); rows.append({"dataset":row.dataset,"split":row.split,"roc":roc,"roc_sd":roc_sd,"pr":pr,"pr_sd":pr_sd})
    lp=pd.DataFrame(rows); lp.to_csv(SRC/"fig09_linpept_parsed.csv",index=False)
    ax=fig.add_subplot(gs[1,0]); markers={"linpept_cellpen":"o","linpept_nonfouling":"s"}; colors={"random":COL["green"],"scaffold":COL["blue"],"perimeter":COL["orange"]}
    for dataset,g in lp.groupby("dataset"):
        for _,row in g.iterrows(): ax.errorbar(row.roc,row.pr,xerr=row.roc_sd,yerr=row.pr_sd,fmt=markers[dataset],ms=5,color=colors[row.split],capsize=2)
    handles=[Line2D([],[],marker="o",color="none",markerfacecolor=c,label=s.title()) for s,c in colors.items()]+[Line2D([],[],marker="o",color=COL["ink"],label="CellPen",ls="none"),Line2D([],[],marker="s",color=COL["ink"],label="NonFouling",ls="none")]
    ax.set(xlabel="LinPept ROC-AUC",ylabel="LinPept PR-AUC",xlim=(.70,.98),ylim=(.62,.94)); ax.legend(handles=handles,ncol=2,loc="lower right",fontsize=6.7); ax.set_title("Peptide transfer boundary",loc="left"); style(ax); panel(ax,"d")
    ax=fig.add_subplot(gs[1,1:]); cases=[("FreeSolv",0.333,6.43),("FreeSolv",0.304,4.49),("Lipophilicity",0.217,5.90)]; x=[c[1] for c in cases]; y=[c[2] for c in cases]; ax.scatter(x,y,s=[45,45,55],color=[COL["blue"],COL["blue2"],COL["orange"]]);
    for (name,xx,yy) in cases: ax.annotate(name,(xx,yy),xytext=(4,4),textcoords="offset points",fontsize=7.5)
    ax.axvline(.5,color=COL["ink"],ls="--",lw=.8); ax.set(xlabel="Nearest-neighbour Tanimoto",ylabel="Absolute error",xlim=(.18,.52)); ax.set_title("Representative low-similarity failures",loc="left"); style(ax); panel(ax,"e")
    save(fig,"fig09_chemical_boundaries_decision_card")


def figure10_governance_automl_transfer() -> None:
    ablation_path = ROOT / "results" / "source_data" / "ablation_summary.csv"
    automl_path = ROOT / "results" / "source_data" / "autogluon_budget.csv"
    loeo_path = ROOT / "results" / "selection_closure" / "leave_one_endpoint_out_policy.csv"
    ablation = pd.read_csv(ablation_path); automl = pd.read_csv(automl_path); loeo = pd.read_csv(loeo_path)
    for p in [ablation_path, automl_path, loeo_path]: copy_csv(p, f"fig10_{p.name}")
    fig, axes = plt.subplots(2, 2, figsize=(8.4, 6.3))
    label_map = {
        "validation_best":"Validation-best", "frozen_one_se_governance":"Frozen one-SE",
        "one_se_low_variance":"one-SE low variance", "one_se_low_cost":"one-SE low cost",
        "full_pool":"Full pool", "remove_bagging":"Remove bagging",
        "remove_boosting":"Remove boosting", "remove_linear":"Remove linear",
    }
    for ax, cls, title, lab, colour in [
        (axes[0,0],"governance_rule","Governance-rule ablation","a",COL["blue"]),
        (axes[0,1],"candidate_family_removal","Candidate-family removal","b",COL["orange"]),
    ]:
        s=ablation[ablation.ablation_class.eq(cls)].sort_values("mean_fixed_regret")
        y=np.arange(len(s)); x=s.mean_fixed_regret.to_numpy(); xerr=np.vstack([x-s.ci95_low.to_numpy(),s.ci95_high.to_numpy()-x])
        ax.errorbar(x,y,xerr=xerr,fmt="o",ms=5,color=colour,ecolor=COL["light"],capsize=3)
        ax.set_yticks(y,[label_map.get(v,v.replace("_"," ")) for v in s.variant]); ax.tick_params(axis="y",labelsize=8.3)
        ax.set_xlabel("Mean fixed-denominator regret"); ax.set_title(title,loc="left"); style(ax,"x"); panel(ax,lab,-0.21)

    ax=axes[1,0]
    summary=[]
    for budget,g in automl.groupby("budget_seconds"):
        delta=g.delta_vs_validation_best.astype(float)
        summary.append({"budget":int(budget),"wins":int((delta>0).sum()),"losses":int((delta<0).sum()),"runtime":float(g.actual_fit_seconds_mean.sum())})
    auto=pd.DataFrame(summary).sort_values("budget"); auto.to_csv(SRC/"fig10_autogluon_budget_summary.csv",index=False)
    x=np.arange(len(auto)); ax.bar(x,auto.wins,color=COL["green"],width=.64,label="Endpoints won"); ax.bar(x,-auto.losses,color=COL["red"],width=.64,label="Endpoints lost")
    ax.axhline(0,color=COL["ink"],lw=.8); ax.set_xticks(x,["30 s","300 s","1,800 s"]); ax.set_ylabel("Endpoint count vs validation-best"); ax.set_title("AutoGluon performance–cost boundary",loc="left"); style(ax,"y"); panel(ax,"c")
    ax2=ax.twinx(); ax2.plot(x,auto.runtime,color=COL["purple"],marker="o",lw=1.5,label="Actual total fit time"); ax2.set_ylabel("Actual total fit time (s)",color=COL["purple"]); ax2.tick_params(axis="y",colors=COL["purple"]); ax2.spines["top"].set_visible(False)
    ax2.set_ylim(0, max(180, float(auto.runtime.max()) * 1.08))
    ax.set_ylim(-2.75,7.85)
    for xpos, row in enumerate(auto.itertuples(index=False)):
        ax.text(xpos, row.wins - 0.25, f"won {int(row.wins)}", ha="center", va="top", fontsize=7.0, color="white", fontweight="bold")
        ax.text(xpos, -row.losses / 2, f"lost {int(row.losses)}", ha="center", va="center", fontsize=7.0, color="white", fontweight="bold")

    ax=axes[1,1]
    s=loeo.sort_values("heldout_regret"); y=np.arange(len(s))
    ax.hlines(y,s.heldout_oracle_regret,s.heldout_regret,color=COL["light"],lw=2.5)
    ax.scatter(s.heldout_regret,y,color=COL["blue"],s=28,label="LOEO-selected rule")
    ax.scatter(s.heldout_oracle_regret,y,color=COL["orange"],marker="D",s=25,label="Endpoint oracle")
    ax.set_yticks(y,s.held_endpoint.str.replace("tdc_","",regex=False).str.replace("_"," ",regex=False)); ax.tick_params(axis="y",labelsize=8.0)
    ax.set_xlabel("Held-out endpoint fixed regret"); ax.set_title("Leave-one-endpoint-out rule transfer",loc="left"); style(ax,"x"); panel(ax,"d",-.21); ax.legend(loc="lower right",fontsize=7.6)
    fig.tight_layout(w_pad=2.1,h_pad=2.2)
    save(fig,"fig10_governance_automl_transfer")


def figure11_failures_negative_results_traceability() -> None:
    failure_path=ROOT/"reports"/"supplement_experiment_revision_20260606"/"maintext_table_failure_cases_compact.csv"
    failures=pd.read_csv(failure_path); copy_csv(failure_path,"fig11_failure_cases.csv")
    strategies=pd.DataFrame({"strategy":["Risk-adjusted","Stability tie-break"],"positive":[10,7],"negative":[22,25]})
    signals=pd.DataFrame({
        "case":["ClinTox false negative","FreeSolv low similarity 1","FreeSolv low similarity 2","Lipophilicity low similarity","Half-life extreme label"],
        "signal":[0.913,1-0.333,1-0.304,1-0.217,0.413],
        "signal_type":["risk percentile","1 − Tanimoto","1 − Tanimoto","1 − Tanimoto","roughness"],
    })
    fragments=pd.DataFrame({"dataset":["BACE","BBBP","ClinTox"],"support":[62,76,5],"annotation":["Δ +0.527\npositive rate","Δ −0.602\npositive rate","14.18× enrichment; exploratory"]})
    inventory=pd.DataFrame({"evidence":["Multiview fits","Selection units","Conformal units","Risk units","TDC endpoints"],"count":[6480,540,90,85,22]})
    for name,df in [("strategies",strategies),("case_signals",signals),("fragment_support",fragments),("evidence_inventory",inventory)]: df.to_csv(SRC/f"fig11_{name}.csv",index=False)
    fig,axes=plt.subplots(2,2,figsize=(8.4,6.25))
    ax=axes[0,0]; y=np.arange(len(strategies)); ax.barh(y,strategies.positive,color=COL["green"],label="Positive"); ax.barh(y,strategies.negative,left=strategies.positive,color=COL["light"],label="Negative"); ax.set_yticks(y,strategies.strategy); ax.set_xlabel("Endpoint–metric units (n=32)"); ax.set_title("Fixed-strategy negative results",loc="left"); ax.invert_yaxis(); style(ax,"x"); panel(ax,"a",-.20); ax.legend(loc="lower right")
    for i,row in strategies.iterrows(): ax.text(row.positive/2,i,str(row.positive),ha="center",va="center",color="white",fontweight="bold"); ax.text(row.positive+row.negative/2,i,str(row.negative),ha="center",va="center",color=COL["ink"])

    ax=axes[0,1]; s=signals.sort_values("signal"); y=np.arange(len(s)); colours=[COL["red"] if t=="risk percentile" else COL["orange"] if t=="roughness" else COL["blue"] for t in s.signal_type]
    ax.hlines(y,0,s.signal,color=COL["light"],lw=2); ax.scatter(s.signal,y,color=colours,s=38,zorder=3); ax.set_yticks(y,s.case); ax.tick_params(axis="y",labelsize=7.8); ax.set_xlim(0,1); ax.set_xlabel("Recorded boundary signal (case-specific scale)"); ax.set_title("Representative failure evidence",loc="left"); style(ax,"x"); panel(ax,"b",-.23)

    ax=axes[1,0]; x=np.arange(len(fragments)); bars=ax.bar(x,fragments.support,color=[COL["green"],COL["blue"],COL["grey"]],width=.65); ax.set_xticks(x,fragments.dataset); ax.set_ylabel("Fragment support count"); ax.set_title("Association strength is bounded by support",loc="left",pad=10); style(ax,"y"); panel(ax,"c")
    for i,(bar,ann) in enumerate(zip(bars,fragments.annotation)):
        if i < 2: ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()-5,ann,ha="center",va="top",fontsize=6.7,linespacing=1.05,color="white",fontweight="bold")
        else: ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+2,"14.18× enrichment\nsupport = 5; exploratory",ha="center",va="bottom",fontsize=7.2,color=COL["muted"])
    ax.set_ylim(0,90)

    ax=axes[1,1]; inv=inventory.sort_values("count"); y=np.arange(len(inv)); ax.barh(y,inv["count"],color=[COL["teal"],COL["blue2"],COL["green"],COL["orange"],COL["purple"]]); ax.set_yticks(y,inv.evidence); ax.set_xscale("log"); ax.set_xlabel("Recorded units (log scale)"); ax.set_title("Traceable evidence inventory",loc="left"); style(ax,"x"); panel(ax,"d",-.20)
    for i,v in enumerate(inv["count"]): ax.text(v*1.08,i,f"{int(v):,}",va="center",fontsize=8.0)
    fig.tight_layout(w_pad=2.1,h_pad=2.2)
    save(fig,"fig11_failures_negative_results_traceability")


def copy_package_sources() -> None:
    for p in (OLD / "source_data").glob("*.csv"):
        if not (SRC / p.name).exists(): shutil.copy2(p,SRC/p.name)


def main() -> None:
    setup(); copy_package_sources(); figure01_overall_workflow(); regenerate_legacy_quantitative_figures()
    figure04_metric_calibration_and_meta_risk()
    figure05_multiview_confirmation()
    figure08_prediction_reliability_and_conformal()
    figure09_chemical_boundaries_and_decision_card()
    figure10_governance_automl_transfer()
    figure11_failures_negative_results_traceability()
    print(f"built {len(list(FIG.glob('*.png')))} PNG figures in {FIG}")


if __name__ == "__main__": main()
