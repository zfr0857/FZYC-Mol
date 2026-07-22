from __future__ import annotations

import math
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "selector_strategy_audit_20260603"
TABLE_DIR = ROOT / "reports" / "manuscript_tables"
FIG_DIR = ROOT / "reports" / "manuscript_figures_polished"

TABLE38_PATH = TABLE_DIR / "table38_selector_strategy_audit_retained_best.csv"
TABLE39_PATH = TABLE_DIR / "table39_selector_strategy_candidates.csv"
TABLE40_PATH = TABLE_DIR / "table40_selector_strategy_policy_summary.csv"
FIG21_PATH = FIG_DIR / "fig21_selector_strategy_audit_decision"

SOURCE_PATHS = {
    "moleculenet_targeted_rebuild": ROOT / "reports" / "moleculenet_targeted_rebuilds" / "candidate_metrics_raw.csv",
    "moleculenet_nature_fusion": ROOT / "reports" / "nature_multimethod_fusion_appendix" / "candidate_metrics_raw.csv",
    "tdc_performance_mode": ROOT / "reports" / "tdc_performance_mode_appendix_combined" / "candidate_metrics_raw.csv",
    "tdc_nature_fusion": ROOT / "reports" / "tdc_nature_multimethod_fusion_appendix" / "candidate_metrics_raw.csv",
    "three_d_roughness_regression": ROOT
    / "reports"
    / "three_d_roughness_regression_experts_20260603"
    / "candidate_metrics_raw.csv",
}


def parse_formatted_mean(value: object) -> float:
    match = re.search(r"[-+]?\d+(?:\.\d+)?", str(value))
    return float(match.group(0)) if match else float("nan")


def parse_formatted_std(value: object) -> float:
    text = str(value)
    if "+/-" not in text:
        return float("nan")
    return parse_formatted_mean(text.split("+/-", 1)[1])


def direction_delta(direction: str, old: float, new: float) -> float:
    return old - new if direction == "lower" else new - old


def better_sort(direction: str) -> bool:
    return direction == "lower"


def primary_metric(row: pd.Series) -> str:
    for col in ["primary_metric", "official_metric", "selection_metric"]:
        if col in row and pd.notna(row[col]):
            return str(row[col]).replace("-", "_")
    raise KeyError("missing primary metric")


def normalize_source(source_name: str, path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path)
    rows = []
    for _, row in raw.iterrows():
        metric = primary_metric(row)
        direction = str(row.get("primary_direction", row.get("selection_direction", "lower")))
        if direction not in {"lower", "higher"}:
            direction = "lower" if metric in {"rmse", "mae"} else "higher"
        validation_primary = row.get("validation_primary", row.get("selection_value", np.nan))
        primary_value = row.get("primary_value", np.nan)
        if pd.isna(primary_value):
            metric_col = metric.replace("-", "_")
            primary_value = row.get(f"test_{metric_col}", row.get(metric_col, np.nan))
        if pd.isna(validation_primary) or pd.isna(primary_value):
            continue
        rows.append(
            {
                "source": source_name,
                "dataset": str(row["dataset"]),
                "family": str(row.get("family", "")),
                "task_type": str(row["task_type"]),
                "seed": int(row["seed"]),
                "model": str(row["model"]),
                "candidate_type": str(row.get("candidate_type", row.get("method", ""))),
                "primary_metric": metric,
                "primary_direction": direction,
                "validation_primary": float(validation_primary),
                "primary_value": float(primary_value),
                "fit_seconds": float(row.get("fit_seconds", 0.0)) if pd.notna(row.get("fit_seconds", 0.0)) else 0.0,
                "valid_brier": float(row.get("valid_brier", np.nan)) if pd.notna(row.get("valid_brier", np.nan)) else np.nan,
                "valid_ece": float(row.get("valid_ece", np.nan)) if pd.notna(row.get("valid_ece", np.nan)) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def load_candidates() -> pd.DataFrame:
    frames = []
    for source, path in SOURCE_PATHS.items():
        if path.exists():
            frames.append(normalize_source(source, path))
    out = pd.concat(frames, ignore_index=True)
    out = out[np.isfinite(out["validation_primary"]) & np.isfinite(out["primary_value"])].reset_index(drop=True)
    return out


def tolerance(metric: str, direction: str, best_value: float) -> float:
    if direction == "higher":
        return 0.005 if metric in {"roc_auc", "pr_auc", "spearman"} else max(0.005, abs(best_value) * 0.01)
    return max(0.005, abs(best_value) * 0.02)


def add_validation_ranks(sub: pd.DataFrame) -> pd.DataFrame:
    pieces = []
    for _, seed_sub in sub.groupby("seed"):
        seed_sub = seed_sub.copy()
        direction = str(seed_sub["primary_direction"].iloc[0])
        seed_sub["validation_rank"] = seed_sub["validation_primary"].rank(
            method="min",
            ascending=better_sort(direction),
        )
        best = seed_sub.sort_values("validation_primary", ascending=better_sort(direction)).iloc[0]["validation_primary"]
        if direction == "lower":
            seed_sub["validation_regret"] = seed_sub["validation_primary"] - best
        else:
            seed_sub["validation_regret"] = best - seed_sub["validation_primary"]
        pieces.append(seed_sub)
    return pd.concat(pieces, ignore_index=True)


def model_summary(sub: pd.DataFrame) -> pd.DataFrame:
    sub = add_validation_ranks(sub)
    n_seeds = sub["seed"].nunique()
    rows = []
    for model, group in sub.groupby("model", sort=False):
        if group["seed"].nunique() < n_seeds:
            continue
        metric = str(group["primary_metric"].iloc[0])
        direction = str(group["primary_direction"].iloc[0])
        val = group["validation_primary"].astype(float)
        test = group["primary_value"].astype(float)
        rows.append(
            {
                "model": model,
                "candidate_type": ";".join(sorted(set(group["candidate_type"].astype(str)))),
                "n_seeds": int(group["seed"].nunique()),
                "primary_metric": metric,
                "primary_direction": direction,
                "validation_mean": float(val.mean()),
                "validation_std": float(val.std(ddof=1)) if len(val) > 1 else 0.0,
                "validation_median": float(val.median()),
                "validation_rank_mean": float(group["validation_rank"].mean()),
                "validation_regret_mean": float(group["validation_regret"].mean()),
                "validation_regret_p90": float(group["validation_regret"].quantile(0.90)),
                "primary_mean": float(test.mean()),
                "primary_std": float(test.std(ddof=1)) if len(test) > 1 else 0.0,
                "fit_seconds_mean": float(group["fit_seconds"].mean()),
                "valid_brier_mean": float(group["valid_brier"].mean()) if group["valid_brier"].notna().any() else np.nan,
                "valid_ece_mean": float(group["valid_ece"].mean()) if group["valid_ece"].notna().any() else np.nan,
            }
        )
    return pd.DataFrame(rows)


def choose_by_mean(ms: pd.DataFrame) -> pd.Series:
    direction = str(ms["primary_direction"].iloc[0])
    return ms.sort_values("validation_mean", ascending=better_sort(direction)).iloc[0]


def choose_stability_tie(ms: pd.DataFrame) -> pd.Series:
    direction = str(ms["primary_direction"].iloc[0])
    metric = str(ms["primary_metric"].iloc[0])
    best = choose_by_mean(ms)
    tol = tolerance(metric, direction, float(best["validation_mean"]))
    if direction == "lower":
        pool = ms[ms["validation_mean"] <= float(best["validation_mean"]) + tol].copy()
    else:
        pool = ms[ms["validation_mean"] >= float(best["validation_mean"]) - tol].copy()
    return pool.sort_values(["validation_std", "validation_rank_mean", "fit_seconds_mean"], ascending=[True, True, True]).iloc[0]


def choose_risk_adjusted(ms: pd.DataFrame, lam: float) -> pd.Series:
    ms = ms.copy()
    direction = str(ms["primary_direction"].iloc[0])
    if direction == "lower":
        ms["score"] = ms["validation_mean"] + lam * ms["validation_std"]
        return ms.sort_values(["score", "validation_rank_mean"]).iloc[0]
    ms["score"] = ms["validation_mean"] - lam * ms["validation_std"]
    return ms.sort_values(["score", "validation_rank_mean"], ascending=[False, True]).iloc[0]


def choose_rank(ms: pd.DataFrame) -> pd.Series:
    direction = str(ms["primary_direction"].iloc[0])
    return ms.sort_values(["validation_rank_mean", "validation_mean"], ascending=[True, better_sort(direction)]).iloc[0]


def choose_regret_guard(ms: pd.DataFrame) -> pd.Series:
    direction = str(ms["primary_direction"].iloc[0])
    return ms.sort_values(
        ["validation_regret_p90", "validation_regret_mean", "validation_mean"],
        ascending=[True, True, better_sort(direction)],
    ).iloc[0]


def choose_calibration_tie(ms: pd.DataFrame) -> pd.Series | None:
    if str(ms["task_type"].iloc[0]) != "classification":
        return None
    if not ms["valid_brier_mean"].notna().any() and not ms["valid_ece_mean"].notna().any():
        return None
    direction = str(ms["primary_direction"].iloc[0])
    metric = str(ms["primary_metric"].iloc[0])
    best = choose_by_mean(ms)
    tol = tolerance(metric, direction, float(best["validation_mean"]))
    if direction == "lower":
        pool = ms[ms["validation_mean"] <= float(best["validation_mean"]) + tol].copy()
    else:
        pool = ms[ms["validation_mean"] >= float(best["validation_mean"]) - tol].copy()
    pool["cal_score"] = pool["valid_brier_mean"].fillna(pool["valid_brier_mean"].median()) + pool["valid_ece_mean"].fillna(
        pool["valid_ece_mean"].median()
    )
    return pool.sort_values(["cal_score", "validation_std"]).iloc[0]


def seed_best_summary(sub: pd.DataFrame) -> dict[str, object]:
    selected = []
    for _, seed_sub in sub.groupby("seed"):
        direction = str(seed_sub["primary_direction"].iloc[0])
        selected.append(seed_sub.sort_values("validation_primary", ascending=better_sort(direction)).iloc[0])
    selected_df = pd.DataFrame(selected)
    return {
        "strategy": "per_seed_validation_best",
        "selected_model": "; ".join(f"{k}:{v}" for k, v in selected_df["model"].value_counts().items()),
        "validation_mean": float(selected_df["validation_primary"].mean()),
        "validation_std": float(selected_df["validation_primary"].std(ddof=1)) if len(selected_df) > 1 else 0.0,
        "primary_mean": float(selected_df["primary_value"].mean()),
        "primary_std": float(selected_df["primary_value"].std(ddof=1)) if len(selected_df) > 1 else 0.0,
        "n_seeds": int(selected_df["seed"].nunique()),
    }


def strategy_rows_for_group(source: str, dataset: str, sub: pd.DataFrame) -> tuple[list[dict[str, object]], pd.DataFrame]:
    metric = str(sub["primary_metric"].iloc[0])
    direction = str(sub["primary_direction"].iloc[0])
    task_type = str(sub["task_type"].iloc[0])
    rows = []
    base = seed_best_summary(sub)
    rows.append(base)
    ms = model_summary(sub)
    ms["source"] = source
    ms["dataset"] = dataset
    ms["task_type"] = task_type
    if ms.empty:
        return rows, ms
    strategies: list[tuple[str, pd.Series | None]] = [
        ("repeated_validation_mean", choose_by_mean(ms)),
        ("stability_tie_breaker", choose_stability_tie(ms)),
        ("risk_adjusted_lambda_0.5", choose_risk_adjusted(ms, 0.5)),
        ("mean_rank_selector", choose_rank(ms)),
        ("regret_guard_selector", choose_regret_guard(ms)),
        ("calibration_tie_breaker", choose_calibration_tie(ms.assign(task_type=task_type))),
    ]
    for strategy, chosen in strategies:
        if chosen is None:
            continue
        rows.append(
            {
                "strategy": strategy,
                "selected_model": chosen["model"],
                "validation_mean": float(chosen["validation_mean"]),
                "validation_std": float(chosen["validation_std"]),
                "primary_mean": float(chosen["primary_mean"]),
                "primary_std": float(chosen["primary_std"]),
                "n_seeds": int(chosen["n_seeds"]),
            }
        )
    for row in rows:
        row.update(
            {
                "source": source,
                "dataset": dataset,
                "task_type": task_type,
                "primary_metric": metric,
                "primary_direction": direction,
            }
        )
        row["delta_vs_per_seed_best"] = direction_delta(direction, float(base["primary_mean"]), float(row["primary_mean"]))
    return rows, ms


def load_current_retained_lookup() -> dict[tuple[str, str], dict[str, object]]:
    lookup: dict[tuple[str, str], dict[str, object]] = {}
    table2 = TABLE_DIR / "table2_moleculenet_main.csv"
    if table2.exists():
        df = pd.read_csv(table2)
        for _, row in df.iterrows():
            formatted = row["FZYC-Mol final retained-best"]
            for source in ["moleculenet_targeted_rebuild", "moleculenet_nature_fusion", "three_d_roughness_regression"]:
                lookup[(source, str(row["dataset"]))] = {
                    "retained_primary_mean": parse_formatted_mean(formatted),
                    "retained_primary_std": parse_formatted_std(formatted),
                    "retained_source": "current_table2",
                }
    table15 = TABLE_DIR / "table15_tdc_performance_mode_retained_best.csv"
    if table15.exists():
        df = pd.read_csv(table15)
        for _, row in df.iterrows():
            lookup[("tdc_performance_mode", str(row["dataset"]))] = {
                "retained_primary_mean": float(row["retained_primary_mean"]),
                "retained_primary_std": float(row.get("previous_primary_std", np.nan)),
                "retained_source": str(row["retained_source"]),
            }
    table32 = TABLE_DIR / "table32_tdc_nature_multimethod_fusion_retained_best.csv"
    if table32.exists():
        df = pd.read_csv(table32)
        for _, row in df.iterrows():
            lookup[("tdc_nature_fusion", str(row["dataset"]))] = {
                "retained_primary_mean": float(row["retained_primary_mean"]),
                "retained_primary_std": float(row["retained_primary_std"]),
                "retained_source": str(row["retained_source"]),
            }
    return lookup


def build_strategy_delta_table(strategy_df: pd.DataFrame) -> pd.DataFrame:
    lookup = load_current_retained_lookup()
    rows = []
    for row in strategy_df.itertuples(index=False):
        source = str(row.source)
        dataset = str(row.dataset)
        direction = str(row.primary_direction)
        retained = lookup.get((source, dataset), {})
        retained_mean = float(retained.get("retained_primary_mean", np.nan))
        retained = lookup.get((source, dataset), {})
        rows.append(
            {
                "source": source,
                "dataset": dataset,
                "task_type": row.task_type,
                "primary_metric": row.primary_metric,
                "primary_direction": direction,
                "n_seeds": int(row.n_seeds),
                "strategy": row.strategy,
                "selected_model": row.selected_model,
                "strategy_validation_mean": float(row.validation_mean),
                "strategy_validation_std": float(row.validation_std),
                "strategy_primary_mean": float(row.primary_mean),
                "strategy_primary_std": float(row.primary_std),
                "delta_vs_per_seed_best": float(row.delta_vs_per_seed_best),
                "current_retained_primary_mean": retained_mean,
                "current_retained_source": retained.get("retained_source", ""),
                "delta_vs_current_retained": direction_delta(direction, retained_mean, float(row.primary_mean))
                if math.isfinite(retained_mean)
                else np.nan,
                "selector_signal": "positive_vs_current"
                if math.isfinite(retained_mean) and direction_delta(direction, retained_mean, float(row.primary_mean)) > 0
                else "not_positive_vs_current",
            }
        )
    return pd.DataFrame(rows)


def build_policy_summary(delta_table: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for strategy, sub in delta_table[~delta_table["strategy"].eq("per_seed_validation_best")].groupby("strategy", sort=False):
        finite = sub[np.isfinite(sub["delta_vs_current_retained"])].copy()
        positive = finite[finite["delta_vs_current_retained"] > 0]
        rows.append(
            {
                "strategy": strategy,
                "n_endpoint_pools": int(len(finite)),
                "n_positive_vs_current": int(len(positive)),
                "positive_rate": float(len(positive) / len(finite)) if len(finite) else np.nan,
                "mean_delta_vs_current": float(finite["delta_vs_current_retained"].mean()) if len(finite) else np.nan,
                "median_delta_vs_current": float(finite["delta_vs_current_retained"].median()) if len(finite) else np.nan,
                "mean_positive_delta": float(positive["delta_vs_current_retained"].mean()) if len(positive) else np.nan,
                "largest_positive_delta": float(positive["delta_vs_current_retained"].max()) if len(positive) else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values(["n_positive_vs_current", "mean_delta_vs_current"], ascending=[False, False])


def plot_decision(delta_table: pd.DataFrame, policy_summary: pd.DataFrame) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    positives = delta_table[
        (~delta_table["strategy"].eq("per_seed_validation_best"))
        & (delta_table["delta_vs_current_retained"] > 0)
        & np.isfinite(delta_table["delta_vs_current_retained"])
    ].copy()
    positives = positives.sort_values("delta_vs_current_retained", ascending=True).tail(12)
    strategy_colors = {
        "risk_adjusted_lambda_0.5": "#166534",
        "stability_tie_breaker": "#1d4ed8",
        "repeated_validation_mean": "#0f766e",
        "mean_rank_selector": "#b45309",
        "regret_guard_selector": "#7c3aed",
        "calibration_tie_breaker": "#be123c",
    }
    source_labels = {
        "moleculenet_targeted_rebuild": "MN targeted",
        "moleculenet_nature_fusion": "MN fusion",
        "tdc_performance_mode": "TDC perf.",
        "tdc_nature_fusion": "TDC fusion",
        "three_d_roughness_regression": "3D-lite",
    }
    dataset_labels = {
        "freesolv": "FreeSolv",
        "lipo": "Lipo",
        "bbbp": "BBBP",
        "clintox": "ClinTox",
        "half_life_obach": "Half-life",
        "clearance_microsome_az": "Clearance microsome",
        "clearance_hepatocyte_az": "Clearance hepatocyte",
        "cyp2c9_substrate_carbonmangels": "CYP2C9 substrate",
        "hia_hou": "HIA",
        "herg": "hERG",
        "vdss_lombardo": "VDss",
        "tdc_pgp_broccatelli": "Pgp",
        "tdc_caco2_wang": "Caco2",
    }
    strategy_labels = {
        "risk_adjusted_lambda_0.5": "risk-adjusted",
        "stability_tie_breaker": "stability tie",
        "repeated_validation_mean": "repeated mean",
        "mean_rank_selector": "mean rank",
        "regret_guard_selector": "regret guard",
        "calibration_tie_breaker": "calibration tie",
    }
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "figure.dpi": 180,
            "savefig.dpi": 320,
            "axes.edgecolor": "#cbd5e1",
            "axes.labelcolor": "#0f172a",
            "xtick.color": "#334155",
            "ytick.color": "#334155",
        }
    )
    fig, axes = plt.subplots(1, 2, figsize=(14.6, 7.0), gridspec_kw={"width_ratios": [0.82, 1.34]})
    ax = axes[0]
    ps = policy_summary.sort_values("n_positive_vs_current", ascending=True)
    y_pos = np.arange(len(ps))
    ax.barh(
        y_pos,
        ps["n_positive_vs_current"],
        color=[strategy_colors.get(str(s), "#1b8a6b") for s in ps["strategy"]],
        height=0.58,
    )
    ax.set_yticks(y_pos)
    ax.set_yticklabels(ps["strategy"], fontsize=8.0)
    ax.set_xlabel("Endpoint pools with positive delta")
    ax.set_title("A  Fixed selector policies", loc="left", fontsize=11.5, fontweight="bold")
    ax.grid(axis="x", color="#e5e7eb", linewidth=0.65, alpha=0.85)
    for y, row in zip(y_pos, ps.itertuples(index=False)):
        ax.text(row.n_positive_vs_current + 0.12, y, f"{row.n_positive_vs_current}", va="center", fontsize=8.0, color="#14532d")

    ax = axes[1]
    if positives.empty:
        ax.text(0.5, 0.5, "No positive selector signals", transform=ax.transAxes, ha="center", va="center")
        ax.set_axis_off()
    else:
        labels = [
            (
                f"{dataset_labels.get(str(row.dataset), str(row.dataset))}"
                f" ({source_labels.get(str(row.source), str(row.source))})\n"
                f"{strategy_labels.get(str(row.strategy), str(row.strategy))}"
            )
            for row in positives.itertuples(index=False)
        ]
        deltas = positives["delta_vs_current_retained"].astype(float).to_numpy()
        y_pos = np.arange(len(positives))
        ax.barh(
            y_pos,
            deltas,
            color=[strategy_colors.get(str(s), "#1b8a6b") for s in positives["strategy"]],
            edgecolor="white",
            height=0.56,
            linewidth=0.8,
        )
        ax.axvline(0, color="#334155", lw=0.9)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, fontsize=7.5)
        ax.set_xlabel("Positive delta vs current retained-best")
        ax.set_title("B  Strongest positive fixed-policy signals", loc="left", fontsize=11.5, fontweight="bold")
        ax.grid(axis="x", color="#e5e7eb", linewidth=0.65, alpha=0.85)
        span = max(0.002, float(np.nanmax(np.abs(deltas))) * 0.06)
        for y, row, delta in zip(y_pos, positives.itertuples(index=False), deltas):
            ax.text(delta + span, y, f"{delta:+.3f}", va="center", fontsize=7.2, color="#14532d")
        ax.set_xlim(0, max(0.03, float(np.nanmax(deltas)) + span * 8))
    fig.text(
        0.125,
        0.03,
        "Each policy is evaluated as a fixed validation-only selector. Bars are audit signals, not endpoint-wise test-selected strategy choices.",
        fontsize=8.2,
        color="#475569",
        ha="left",
        va="center",
    )
    for ax in axes:
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        ax.spines["left"].set_color("#e2e8f0")
        ax.spines["bottom"].set_color("#e2e8f0")
    fig.tight_layout(rect=[0, 0.06, 1, 1])
    for ext in ["png", "svg"]:
        fig.savefig(FIG21_PATH.with_suffix(f".{ext}"), bbox_inches="tight")
    plt.close(fig)


def write_readme(summary: pd.DataFrame) -> None:
    lines = [
        "# Selector strategy audit",
        "",
        "This audit reuses existing candidate metrics and does not retrain models.",
        "It compares per-seed validation-best selection with repeated-validation, stability-aware, risk-adjusted, rank-based and regret-guarded selectors.",
        "",
        "Outputs:",
        f"- Fixed-strategy audit table: `{TABLE38_PATH}`",
        f"- Strategy candidate table: `{TABLE39_PATH}`",
        f"- Policy-level summary: `{TABLE40_PATH}`",
        f"- Decision figure: `{FIG21_PATH.with_suffix('.png')}`",
        "",
        "Positive fixed-policy selector signals:",
    ]
    promoted = summary[(summary["selector_signal"].eq("positive_vs_current")) & (~summary["strategy"].eq("per_seed_validation_best"))]
    if promoted.empty:
        lines.append("- None.")
    else:
        for row in promoted.itertuples(index=False):
            lines.append(
                f"- `{row.source}:{row.dataset}` via `{row.strategy}`, "
                f"delta vs retained={row.delta_vs_current_retained:+.4f}."
            )
    lines.extend(
        [
            "",
            "Important boundary: strategies are audited as fixed policies. The report does not select the best strategy per endpoint using test labels.",
            "All choices use validation metrics only; test labels are used for final audit after the strategy is fixed.",
        ]
    )
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    candidates = load_candidates()
    candidates.to_csv(REPORT_DIR / "normalized_candidate_metrics.csv", index=False)

    strategy_rows = []
    model_rows = []
    for (source, dataset), sub in candidates.groupby(["source", "dataset"], sort=False):
        rows, models = strategy_rows_for_group(source, dataset, sub)
        strategy_rows.extend(rows)
        if not models.empty:
            model_rows.append(models)
    strategy_df = pd.DataFrame(strategy_rows)
    model_df = pd.concat(model_rows, ignore_index=True) if model_rows else pd.DataFrame()
    delta_table = build_strategy_delta_table(strategy_df)
    policy_summary = build_policy_summary(delta_table)

    strategy_df.to_csv(REPORT_DIR / "strategy_metrics_raw.csv", index=False)
    model_df.to_csv(TABLE39_PATH, index=False)
    model_df.to_csv(REPORT_DIR / "model_strategy_candidates.csv", index=False)
    delta_table.to_csv(TABLE38_PATH, index=False)
    delta_table.to_csv(REPORT_DIR / "selector_strategy_retained_best.csv", index=False)
    policy_summary.to_csv(TABLE40_PATH, index=False)
    policy_summary.to_csv(REPORT_DIR / "selector_strategy_policy_summary.csv", index=False)
    plot_decision(delta_table, policy_summary)
    write_readme(delta_table)
    print(f"Wrote {REPORT_DIR}")
    print(f"Wrote {TABLE38_PATH}")
    print(f"Wrote {TABLE39_PATH}")
    print(f"Wrote {FIG21_PATH.with_suffix('.png')}")


if __name__ == "__main__":
    main()
