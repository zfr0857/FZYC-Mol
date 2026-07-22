from __future__ import annotations

import math
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

try:
    from scipy.stats import wilcoxon
except Exception:  # pragma: no cover - scipy may be absent in minimal envs
    wilcoxon = None


ROOT = Path(__file__).resolve().parents[1]
TABLE_DIR = ROOT / "reports" / "manuscript_tables"
OUT_DIR = ROOT / "reports" / "formal_external_appendix"
FIG_DIR = ROOT / "reports" / "manuscript_figures_polished"

T15 = TABLE_DIR / "table15_tdc_performance_mode_retained_best.csv"
T16 = TABLE_DIR / "table16_tdc_roughness_literature_alignment.csv"
T19 = TABLE_DIR / "table19_moleculenet_rescue_integrated_selector.csv"
T1 = TABLE_DIR / "table1_dataset_protocol.csv"
FULL_RAW = ROOT / "reports" / "tdc_full_panel_appendix_benchmark" / "metrics_raw.csv"
PERF_RAW = ROOT / "reports" / "tdc_performance_mode_appendix_combined" / "selected_metrics_raw.csv"
PERF_CAND = ROOT / "reports" / "tdc_performance_mode_appendix_combined" / "candidate_metrics_raw.csv"
PERF_SUM = ROOT / "reports" / "tdc_performance_mode_appendix_combined" / "selected_metrics_summary.csv"
CAL = ROOT / "reports" / "validation_calibration" / "selected_vs_uncalibrated.csv"
INTERP = ROOT / "reports" / "interpretability_strengthening" / "high_error_interpretability_cases.csv"
SIG = ROOT / "reports" / "significance_selector" / "significance_tests.csv"
WTL = ROOT / "reports" / "significance_selector" / "win_tie_loss.csv"


def setup_style() -> None:
    sns.set_theme(style="whitegrid", context="paper", font_scale=1.0)
    plt.rcParams.update(
        {
            "figure.dpi": 140,
            "savefig.dpi": 320,
            "font.family": "DejaVu Sans",
            "axes.edgecolor": "#cbd5e1",
            "axes.labelcolor": "#111827",
            "xtick.color": "#334155",
            "ytick.color": "#334155",
            "grid.color": "#e2e8f0",
            "legend.frameon": True,
            "legend.framealpha": 0.95,
        }
    )


def ensure_dirs() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)


def read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path).fillna("")


def fmt(value: object, digits: int = 4) -> str:
    try:
        if pd.isna(value):
            return ""
        return f"{float(value):.{digits}f}"
    except Exception:
        return str(value)


def fmt_signed(value: object, digits: int = 4) -> str:
    try:
        if pd.isna(value):
            return ""
        return f"{float(value):+.{digits}f}"
    except Exception:
        return str(value)


def compact(text: object, max_len: int = 80) -> str:
    out = str(text).replace("\n", " ").replace("\r", " ").strip()
    if len(out) <= max_len:
        return out
    return out[: max_len - 1] + "..."


def candidate_group(model: object, candidate_type: object = "") -> str:
    m = str(model).lower()
    c = str(candidate_type).lower()
    if "underbag" in m or "undersampling" in c:
        return "undersampling ensemble"
    if "stack" in m or "stacking" in c:
        return "validation stacking"
    if "top" in m or "topk" in c:
        return "Top-K mean"
    if "catboost" in m:
        return "CatBoost"
    if "xgb" in m:
        return "XGBoost"
    if "extratrees" in m:
        return "ExtraTrees"
    if "lgbm" in m:
        return "LightGBM"
    if re.search(r"(^|_)rf(_|$)", m):
        return "Random Forest"
    return "other"


def positive_delta(new_value: float, old_value: float, direction: str) -> float:
    if str(direction) == "lower":
        return old_value - new_value
    return new_value - old_value


def bootstrap_ci(values: np.ndarray, n_boot: int = 5000, seed: int = 20260601) -> tuple[float, float, float]:
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return math.nan, math.nan, math.nan
    rng = np.random.default_rng(seed)
    means = np.array([rng.choice(values, size=len(values), replace=True).mean() for _ in range(n_boot)])
    low, high = np.quantile(means, [0.025, 0.975])
    p = 2 * min((means <= 0).mean(), (means >= 0).mean())
    return float(low), float(high), float(min(1.0, p))


def wilcoxon_p(values: np.ndarray) -> float:
    values = values[np.isfinite(values)]
    values = values[np.abs(values) > 1e-12]
    if len(values) < 2 or wilcoxon is None:
        return math.nan
    try:
        return float(wilcoxon(values, alternative="two-sided").pvalue)
    except Exception:
        return math.nan


def save_frame(frame: pd.DataFrame, name: str) -> None:
    frame.to_csv(TABLE_DIR / name, index=False)
    frame.to_csv(OUT_DIR / name, index=False)


def build_external_selector_summary() -> pd.DataFrame:
    t15 = read(T15)
    rough = read(T16)[
        [
            "dataset",
            "roughness_proxy_mean",
            "roughness_band",
            "ood_band",
            "nn_tanimoto_mean",
            "neighbor_conflict_or_large_delta_rate_mean",
        ]
    ]
    merged = t15.merge(rough, on="dataset", how="left")
    rows = []
    for _, r in merged.iterrows():
        retained_delta = r["performance_delta_vs_previous"] if r["retained_source"] == "performance_mode" else 0.0
        rows.append(
            {
                "dataset": r["dataset"],
                "family": r["family"],
                "task_type": r["task_type"],
                "official_metric": r["official_metric"],
                "primary_direction": r["primary_direction"],
                "previous_model": r["previous_model"],
                "previous_primary_mean": r["previous_primary_mean"],
                "performance_model_counts": r["performance_model_counts"],
                "performance_primary_mean": r["performance_primary_mean"],
                "performance_primary_std": r["performance_primary_std"],
                "performance_delta_vs_previous": r["performance_delta_vs_previous"],
                "retained_source": r["retained_source"],
                "retained_primary_mean": r["retained_primary_mean"],
                "retained_model": r["retained_model"],
                "retained_delta_vs_previous": retained_delta,
                "roughness_proxy_mean": r["roughness_proxy_mean"],
                "roughness_band": r["roughness_band"],
                "ood_band": r["ood_band"],
                "nn_tanimoto_mean": r["nn_tanimoto_mean"],
                "neighbor_conflict_or_large_delta_rate_mean": r["neighbor_conflict_or_large_delta_rate_mean"],
                "manuscript_takeaway": (
                    "performance-mode retained; supports external selector"
                    if r["retained_source"] == "performance_mode"
                    else "previous fast baseline retained; selector avoids regression"
                ),
            }
        )
    out = pd.DataFrame(rows).sort_values("retained_delta_vs_previous", ascending=False)
    save_frame(out, "table20_formal_external_appendix_selector.csv")
    return out


def build_candidate_pool_coverage() -> pd.DataFrame:
    cand = read(PERF_CAND)
    selected = read(PERF_RAW)
    cand["candidate_group"] = [candidate_group(m, c) for m, c in zip(cand["model"], cand["candidate_type"])]
    selected["candidate_group"] = [candidate_group(m, c) for m, c in zip(selected["model"], selected["candidate_type"])]
    coverage = (
        cand.groupby("candidate_group", as_index=False)
        .agg(
            n_candidate_rows=("model", "size"),
            n_unique_models=("model", "nunique"),
            n_datasets=("dataset", "nunique"),
            n_dataset_seed_pairs=("seed", "size"),
        )
        .merge(
            selected.groupby("candidate_group", as_index=False).agg(
                selected_seed_count=("model", "size"),
                selected_dataset_count=("dataset", "nunique"),
            ),
            on="candidate_group",
            how="left",
        )
        .fillna({"selected_seed_count": 0, "selected_dataset_count": 0})
    )
    coverage["selected_seed_fraction"] = coverage["selected_seed_count"] / max(1, selected.shape[0])
    coverage = coverage.sort_values(["selected_seed_count", "n_candidate_rows"], ascending=False)
    save_frame(coverage, "table21_external_candidate_pool_coverage.csv")
    return coverage


def build_imbalanced_metrics() -> pd.DataFrame:
    selected = read(PERF_RAW)
    perf_sum = read(PERF_SUM)
    rough = read(T16)
    t1 = read(T1)
    t19 = read(T19)
    calibration = read(CAL)

    target_tdc = {
        "dili",
        "herg",
        "cyp2c9_substrate_carbonmangels",
        "cyp2d6_substrate_carbonmangels",
        "cyp3a4_substrate_carbonmangels",
    }
    rows: list[dict[str, object]] = []
    for dataset in sorted(target_tdc):
        sub = selected[(selected["dataset"].eq(dataset)) & (selected["task_type"].eq("classification"))].copy()
        if sub.empty:
            continue
        summary = perf_sum[perf_sum["dataset"].eq(dataset)].iloc[0]
        rough_row = rough[rough["dataset"].eq(dataset)]
        pos_rate = rough_row["query_positive_rate_mean"].iloc[0] if not rough_row.empty else np.nan
        rows.append(
            {
                "dataset": dataset,
                "source": "TDC full-panel appendix",
                "task_type": "classification",
                "positive_rate_or_query_positive_rate": pos_rate,
                "official_metric": summary["official_metric"],
                "selected_model_counts": summary["performance_model_counts"],
                "uses_undersampling_ensemble": "underbag" in str(summary["performance_model_counts"]),
                "roc_auc_mean": sub["roc_auc"].mean(),
                "roc_auc_std": sub["roc_auc"].std(ddof=1),
                "pr_auc_mean": sub["pr_auc"].mean(),
                "pr_auc_std": sub["pr_auc"].std(ddof=1),
                "brier_mean": sub["brier"].mean(),
                "ece_mean": sub["ece"].mean(),
                "ef1_mean": sub["ef1"].mean(),
                "ef5_mean": sub["ef5"].mean(),
                "note": "external imbalanced ADMET/Tox classification endpoint",
            }
        )

    clin = t19[t19["dataset"].eq("clintox")]
    if not clin.empty:
        clin = clin.iloc[0]
        proto = t1[t1["dataset"].eq("clintox")]
        pos_rate = proto["positive_rate"].iloc[0] if not proto.empty else np.nan
        cal = calibration[calibration["dataset"].eq("clintox")]
        rows.append(
            {
                "dataset": "clintox",
                "source": "MoleculeNet rescue-integrated selector",
                "task_type": "classification",
                "positive_rate_or_query_positive_rate": pos_rate,
                "official_metric": "roc_auc",
                "selected_model_counts": clin["selected_model_counts"],
                "uses_undersampling_ensemble": False,
                "roc_auc_mean": clin["roc_auc_mean"],
                "roc_auc_std": clin["integrated_primary_std"],
                "pr_auc_mean": clin["pr_auc_mean"],
                "pr_auc_std": np.nan,
                "brier_mean": clin["brier_mean"],
                "ece_mean": clin["ece_mean"],
                "ef1_mean": np.nan,
                "ef5_mean": np.nan,
                "calibration_delta_brier_mean": cal["delta_brier_positive"].mean() if not cal.empty else np.nan,
                "calibration_delta_ece_mean": cal["delta_ece_positive"].mean() if not cal.empty else np.nan,
                "note": "low-positive-rate MoleculeNet toxicity endpoint; ROC-AUC should be read with PR-AUC/Brier/ECE",
            }
        )
    out = pd.DataFrame(rows)
    save_frame(out, "table22_imbalanced_classification_metrics.csv")
    return out


def build_seed_stability_significance() -> tuple[pd.DataFrame, pd.DataFrame]:
    t15 = read(T15)
    full = read(FULL_RAW)
    selected = read(PERF_RAW)
    rows = []
    deltas_all = []
    for _, r in t15.iterrows():
        dataset = r["dataset"]
        previous_model = r["previous_model"]
        direction = r["primary_direction"]
        base = full[(full["dataset"].eq(dataset)) & (full["model"].eq(previous_model))][
            ["dataset", "seed", "primary_value"]
        ].rename(columns={"primary_value": "previous_primary"})
        perf = selected[selected["dataset"].eq(dataset)][
            ["dataset", "seed", "model", "candidate_type", "primary_value", "validation_primary"]
        ].rename(columns={"primary_value": "performance_primary"})
        merged = base.merge(perf, on=["dataset", "seed"], how="inner")
        if merged.empty:
            continue
        merged["positive_delta"] = [
            positive_delta(n, o, direction) for n, o in zip(merged["performance_primary"], merged["previous_primary"])
        ]
        values = merged["positive_delta"].to_numpy(dtype=float)
        low, high, p_boot = bootstrap_ci(values)
        p_wil = wilcoxon_p(values)
        deltas_all.extend(values.tolist())
        rows.append(
            {
                "dataset": dataset,
                "task_type": r["task_type"],
                "official_metric": r["official_metric"],
                "primary_direction": direction,
                "previous_model": previous_model,
                "performance_model_counts": r["performance_model_counts"],
                "n_paired_seeds": len(values),
                "mean_positive_delta": float(np.mean(values)),
                "std_positive_delta": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
                "bootstrap_ci_low": low,
                "bootstrap_ci_high": high,
                "bootstrap_p_two_sided": p_boot,
                "wilcoxon_p_two_sided": p_wil,
                "seed_win_count": int((values > 1e-12).sum()),
                "seed_tie_count": int((np.abs(values) <= 1e-12).sum()),
                "seed_loss_count": int((values < -1e-12).sum()),
                "decision": "win" if np.mean(values) > 1e-12 else ("loss" if np.mean(values) < -1e-12 else "tie"),
            }
        )
    out = pd.DataFrame(rows).sort_values("mean_positive_delta", ascending=False)
    overall_values = np.array(deltas_all, dtype=float)
    low, high, p_boot = bootstrap_ci(overall_values)
    retained_deltas = t15["performance_delta_vs_previous"].where(
        t15["retained_source"].eq("performance_mode"), 0.0
    ).astype(float)
    retained_low, retained_high, retained_p_boot = bootstrap_ci(retained_deltas.to_numpy(dtype=float))
    overall = pd.DataFrame(
        [
            {
                "scope": "performance_mode_candidate_vs_previous",
                "unit": "endpoint_seed",
                "n_units": len(overall_values),
                "mean_positive_delta": float(np.mean(overall_values)),
                "std_positive_delta": float(np.std(overall_values, ddof=1)),
                "bootstrap_ci_low": low,
                "bootstrap_ci_high": high,
                "bootstrap_p_two_sided": p_boot,
                "wilcoxon_p_two_sided": wilcoxon_p(overall_values),
                "win": int((out["decision"] == "win").sum()),
                "tie": int((out["decision"] == "tie").sum()),
                "loss": int((out["decision"] == "loss").sum()),
                "interpretation": "raw performance-mode candidates; not all are retained",
            },
            {
                "scope": "retained_best_selector_vs_previous",
                "unit": "endpoint",
                "n_units": len(retained_deltas),
                "mean_positive_delta": float(retained_deltas.mean()),
                "std_positive_delta": float(retained_deltas.std(ddof=1)),
                "bootstrap_ci_low": retained_low,
                "bootstrap_ci_high": retained_high,
                "bootstrap_p_two_sided": retained_p_boot,
                "wilcoxon_p_two_sided": wilcoxon_p(retained_deltas.to_numpy(dtype=float)),
                "win": int((retained_deltas > 1e-12).sum()),
                "tie": int((retained_deltas.abs() <= 1e-12).sum()),
                "loss": int((retained_deltas < -1e-12).sum()),
                "interpretation": "manuscript-facing retained-best selector; previous result kept when candidate is weaker",
            },
        ]
    )
    save_frame(out, "table23_external_seed_stability_significance.csv")
    save_frame(overall, "table25_external_win_tie_loss.csv")
    return out, overall


def build_case_studies() -> pd.DataFrame:
    t19 = read(T19)
    t15 = read(T15)
    rough = read(T16)
    interp = read(INTERP)
    rows: list[dict[str, object]] = []

    lipo = t19[t19["dataset"].eq("lipo")].iloc[0]
    rows.append(
        {
            "case_id": "Case 1",
            "case_name": "Lipo rescue success",
            "dataset": "lipo",
            "case_type": "endpoint-level targeted rescue",
            "evidence": "rescue-integrated selector selected a rescue-aware stack only for Lipo",
            "primary_metric": lipo["primary_metric"],
            "before": f"{fmt(lipo['current_primary_mean'])} +/- {fmt(lipo['current_primary_std'])}",
            "after": f"{fmt(lipo['integrated_primary_mean'])} +/- {fmt(lipo['integrated_primary_std'])}",
            "delta_positive": lipo["integration_delta_vs_current"],
            "selected_model_or_signal": lipo["selected_model_counts"],
            "smiles": "",
            "y_true": "",
            "y_pred": "",
            "risk_or_roughness": "",
            "interpretation": "Low-cost validation-only rescue improves lipophilicity without changing stable endpoints.",
        }
    )

    clin = interp[interp["dataset"].eq("clintox")].copy()
    clin = clin.sort_values(["risk_percentile", "abs_error"], ascending=False).iloc[0]
    rows.append(
        {
            "case_id": "Case 2",
            "case_name": "ClinTox high-risk false negative",
            "dataset": "clintox",
            "case_type": "molecule-level imbalanced classification risk",
            "evidence": "positive ClinTox label with low predicted probability and high risk percentile",
            "primary_metric": "ROC-AUC plus PR-AUC/Brier/ECE",
            "before": "",
            "after": "",
            "delta_positive": "",
            "selected_model_or_signal": f"risk percentile {fmt(clin['risk_percentile'], 3)}; calibrator {clin['calibrator']}",
            "smiles": compact(clin["smiles"], 120),
            "y_true": clin["y_true"],
            "y_pred": fmt(clin["y_pred"], 4),
            "risk_or_roughness": fmt(clin["risk_score"], 4),
            "interpretation": compact(
                f"Matched motifs/fragments: {clin['matched_top_brics_motifs']} | {clin['brics_fragments']}",
                180,
            ),
        }
    )

    endpoint = "half_life_obach"
    perf = t15[t15["dataset"].eq(endpoint)].iloc[0]
    rough_row = rough[rough["dataset"].eq(endpoint)].iloc[0]
    pred_file = ROOT / "reports" / "tdc_full_panel_appendix_benchmark" / f"{endpoint}_{perf['previous_model']}_scaffold_seed23_predictions.csv"
    pred = pd.read_csv(pred_file)
    pred["abs_error"] = (pred["y_true"] - pred["y_pred"]).abs()
    worst = pred.sort_values("abs_error", ascending=False).iloc[0]
    rows.append(
        {
            "case_id": "Case 3",
            "case_name": "High-roughness ADME regression rescue",
            "dataset": endpoint,
            "case_type": "endpoint/molecule-level roughness case",
            "evidence": "high roughness endpoint with performance-mode retained improvement",
            "primary_metric": perf["official_metric"],
            "before": fmt(perf["previous_primary_mean"]),
            "after": fmt(perf["retained_primary_mean"]),
            "delta_positive": perf["performance_delta_vs_previous"],
            "selected_model_or_signal": perf["retained_model"],
            "smiles": compact(worst["smiles"], 120),
            "y_true": fmt(worst["y_true"], 4),
            "y_pred": fmt(worst["y_pred"], 4),
            "risk_or_roughness": fmt(rough_row["roughness_proxy_mean"], 4),
            "interpretation": (
                "Nearest-neighbor roughness and extreme target scale explain why Top-K/stacking or target transforms help."
            ),
        }
    )
    out = pd.DataFrame(rows)
    save_frame(out, "table24_targeted_improvement_case_studies.csv")
    return out


def build_external_delta_figure(summary: pd.DataFrame) -> None:
    plot = summary.copy()
    plot["retained_delta_vs_previous"] = pd.to_numeric(plot["retained_delta_vs_previous"], errors="coerce")
    gains = plot[plot["retained_delta_vs_previous"] > 1e-12].sort_values("retained_delta_vs_previous", ascending=True)
    counts = pd.Series(
        {
            "win\naccepted": int((plot["retained_delta_vs_previous"] > 1e-12).sum()),
            "tie\nprevious": int((plot["retained_delta_vs_previous"].abs() <= 1e-12).sum()),
            "loss": int((plot["retained_delta_vs_previous"] < -1e-12).sum()),
        }
    )
    fig, axes = plt.subplots(1, 2, figsize=(12.4, 5.4), gridspec_kw={"width_ratios": [1.75, 0.85]})
    ax = axes[0]
    ax.barh(gains["dataset"], gains["retained_delta_vs_previous"], color="#059669")
    ax.axvline(0, color="#111827", lw=1.0)
    ax.set_xlabel("Retained-best delta vs previous fast baseline")
    ax.set_ylabel("")
    ax.set_title("Accepted external gains")
    for y, value in enumerate(gains["retained_delta_vs_previous"]):
        ax.text(value, y, f" {value:+.3f}", va="center", fontsize=8.0, color="#334155")
    axes[1].bar(counts.index, counts.values, color=["#059669", "#94a3b8", "#e11d48"])
    axes[1].set_title("Endpoint outcome")
    axes[1].set_ylabel("Number of endpoints")
    for idx, value in enumerate(counts.values):
        axes[1].text(idx, value + 0.35, str(value), ha="center", va="bottom", fontsize=10, fontweight="bold")
    axes[1].set_ylim(0, max(counts.values) + 3)
    fig.suptitle("Formal external appendix: validation-only retained-best selector", fontsize=14, fontweight="bold")
    fig.tight_layout()
    for ext in [".png", ".svg"]:
        fig.savefig(FIG_DIR / f"fig15_external_appendix_retained_delta{ext}", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def build_rank_figure() -> pd.DataFrame:
    cand = read(PERF_CAND)
    cand["primary_value"] = pd.to_numeric(cand["primary_value"], errors="coerce")
    cand = cand.dropna(subset=["primary_value"])
    cand["candidate_group"] = [candidate_group(m, c) for m, c in zip(cand["model"], cand["candidate_type"])]
    groups = ["Random Forest", "LightGBM", "XGBoost", "ExtraTrees", "CatBoost", "Top-K mean", "validation stacking", "undersampling ensemble"]
    rows = []
    for (dataset, seed), sub in cand.groupby(["dataset", "seed"]):
        direction = sub["primary_direction"].iloc[0]
        best_by_group = (
            sub[sub["candidate_group"].isin(groups)]
            .groupby("candidate_group", as_index=False)
            .agg(primary_value=("primary_value", "max" if direction == "higher" else "min"))
        )
        if best_by_group.empty:
            continue
        best_by_group["rank"] = best_by_group["primary_value"].rank(ascending=direction == "lower", method="average")
        for _, r in best_by_group.iterrows():
            rows.append({"dataset": dataset, "seed": seed, "candidate_group": r["candidate_group"], "rank": r["rank"]})
    rank_df = pd.DataFrame(rows)
    rank_summary = (
        rank_df.groupby("candidate_group", as_index=False)
        .agg(mean_rank=("rank", "mean"), std_rank=("rank", "std"), n=("rank", "size"))
        .sort_values("mean_rank")
    )
    save_frame(rank_summary, "table26_external_candidate_rank_summary.csv")

    fig, ax = plt.subplots(figsize=(9.8, 4.9))
    rank_summary = rank_summary.sort_values("mean_rank", ascending=True).reset_index(drop=True)
    y = np.arange(len(rank_summary))
    xerr = rank_summary["std_rank"].fillna(0) / np.sqrt(rank_summary["n"].clip(lower=1))
    ax.errorbar(rank_summary["mean_rank"], y, xerr=xerr, fmt="o", color="#2563eb", ecolor="#94a3b8", capsize=3)
    ax.set_yticks(y)
    ax.set_yticklabels(rank_summary["candidate_group"])
    ax.invert_yaxis()
    ax.set_xlabel("Mean rank across external endpoint-seed units (lower is better)")
    ax.set_ylabel("")
    ax.set_title("Critical-difference-style rank summary for external candidates")
    ax.grid(True, axis="x", alpha=0.35)
    fig.tight_layout()
    for ext in [".png", ".svg"]:
        fig.savefig(FIG_DIR / f"fig16_external_candidate_rank_cd{ext}", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return rank_summary


def write_report(
    summary: pd.DataFrame,
    coverage: pd.DataFrame,
    imbalance: pd.DataFrame,
    stats: pd.DataFrame,
    overall: pd.DataFrame,
    cases: pd.DataFrame,
) -> None:
    n_perf = int((summary["retained_source"] == "performance_mode").sum())
    n_total = len(summary)
    retained_row = overall[overall["scope"].eq("retained_best_selector_vs_previous")].iloc[0]
    candidate_row = overall[overall["scope"].eq("performance_mode_candidate_vs_previous")].iloc[0]
    lines = [
        "# Formal External Appendix and Targeted Improvement Update",
        "",
        "This report consolidates the five requested additions without restarting large-model training.",
        "",
        "## 1. Formal External Benchmark Appendix",
        "",
        f"- External TDC endpoints covered: {n_total}.",
        f"- Endpoints where performance-mode candidates are retained: {n_perf}.",
        f"- Raw performance-mode candidate endpoint-seed mean positive delta: {candidate_row['mean_positive_delta']:.4f}.",
        f"- Manuscript-facing retained-best win/tie/loss by endpoint: {retained_row['win']}/{retained_row['tie']}/{retained_row['loss']}.",
        "",
        "## 2. Candidate Pool",
        "",
    ]
    for _, row in coverage.head(8).iterrows():
        lines.append(
            f"- {row['candidate_group']}: {int(row['n_candidate_rows'])} candidate rows; "
            f"{int(row['selected_seed_count'])} selected seed-level wins."
        )
    lines.extend(
        [
            "",
            "## 3. Imbalanced Classification Metrics",
            "",
            "ClinTox, DILI, hERG and CYP substrate endpoints are summarized with PR-AUC, Brier, ECE, and enrichment metrics where available.",
            "",
            "## 4. Statistical Stability",
            "",
            "New table23 reports paired seed-level deltas, bootstrap confidence intervals, Wilcoxon p-values, and win/tie/loss counts for external TDC performance-mode candidates vs the previous fast baseline.",
            "",
            "## 5. Targeted Case Studies",
            "",
        ]
    )
    for _, row in cases.iterrows():
        lines.append(f"- {row['case_id']} ({row['dataset']}): {row['case_name']} - {row['interpretation']}")
    lines.extend(
        [
            "",
            "## Generated Tables",
            "",
            "- `table20_formal_external_appendix_selector.csv`",
            "- `table21_external_candidate_pool_coverage.csv`",
            "- `table22_imbalanced_classification_metrics.csv`",
            "- `table23_external_seed_stability_significance.csv`",
            "- `table24_targeted_improvement_case_studies.csv`",
            "- `table25_external_win_tie_loss.csv`",
            "- `table26_external_candidate_rank_summary.csv`",
            "",
            "## Generated Figures",
            "",
            "- `fig15_external_appendix_retained_delta.png`",
            "- `fig16_external_candidate_rank_cd.png`",
        ]
    )
    (OUT_DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    setup_style()
    ensure_dirs()
    summary = build_external_selector_summary()
    coverage = build_candidate_pool_coverage()
    imbalance = build_imbalanced_metrics()
    stats, overall = build_seed_stability_significance()
    cases = build_case_studies()
    build_external_delta_figure(summary)
    build_rank_figure()
    write_report(summary, coverage, imbalance, stats, overall, cases)
    print(f"Wrote formal external appendix outputs to {OUT_DIR}")
    print(f"Wrote manuscript tables to {TABLE_DIR}")
    print(f"Wrote figures to {FIG_DIR}")


if __name__ == "__main__":
    main()
