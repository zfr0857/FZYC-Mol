from __future__ import annotations

import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from build_selector_strategy_audit import (
    SOURCE_PATHS,
    better_sort,
    choose_risk_adjusted,
    choose_stability_tie,
    direction_delta,
    model_summary,
    normalize_source,
    parse_formatted_mean,
    parse_formatted_std,
)


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "formal_fixed_selector_integration_20260603"
TABLE_DIR = ROOT / "reports" / "manuscript_tables"
FIG_DIR = ROOT / "reports" / "manuscript_figures_polished"

TABLE41_PATH = TABLE_DIR / "table41_formal_fixed_selector_policy_results.csv"
TABLE42_PATH = TABLE_DIR / "table42_formal_risk_adjusted_integration_retained_best.csv"
TABLE43_PATH = TABLE_DIR / "table43_formal_fixed_selector_policy_summary.csv"
FIG22_PATH = FIG_DIR / "fig22_formal_fixed_selector_integration"

PRIMARY_POLICY = "risk_adjusted_lambda_0.5"


def canonical_dataset(dataset: str) -> str:
    text = str(dataset)
    return text[4:] if text.startswith("tdc_") else text


def normalize_metric(metric: object) -> str:
    return str(metric).replace("-", "_")


def metric_direction(metric: str, fallback: str | None = None) -> str:
    if fallback in {"lower", "higher"}:
        return fallback
    return "lower" if normalize_metric(metric) in {"rmse", "mae"} else "higher"


def update_lookup(
    lookup: dict[tuple[str, str], dict[str, object]],
    dataset: str,
    metric: str,
    direction: str,
    mean: float,
    std: float,
    source: str,
    model: str,
) -> None:
    if not math.isfinite(mean):
        return
    key = (canonical_dataset(dataset), normalize_metric(metric))
    current = lookup.get(key)
    candidate = {
        "current_dataset": canonical_dataset(dataset),
        "current_primary_metric": normalize_metric(metric),
        "current_primary_direction": direction,
        "current_retained_primary_mean": float(mean),
        "current_retained_primary_std": float(std) if math.isfinite(std) else np.nan,
        "current_retained_source": source,
        "current_retained_model": model,
    }
    if current is None:
        lookup[key] = candidate
        return
    old_mean = float(current["current_retained_primary_mean"])
    if direction_delta(direction, old_mean, mean) > 0:
        lookup[key] = candidate


def load_current_retained_lookup() -> dict[tuple[str, str], dict[str, object]]:
    lookup: dict[tuple[str, str], dict[str, object]] = {}

    table2 = TABLE_DIR / "table2_moleculenet_main.csv"
    if table2.exists():
        df = pd.read_csv(table2)
        for _, row in df.iterrows():
            metric = normalize_metric(row["primary_metric"])
            direction = metric_direction(metric)
            mean = parse_formatted_mean(row["FZYC-Mol final retained-best"])
            std = parse_formatted_std(row["FZYC-Mol final retained-best"])
            update_lookup(
                lookup,
                row["dataset"],
                metric,
                direction,
                mean,
                std,
                "table2_final_retained",
                "FZYC-Mol final retained-best",
            )

    table15 = TABLE_DIR / "table15_tdc_performance_mode_retained_best.csv"
    if table15.exists():
        df = pd.read_csv(table15)
        for _, row in df.iterrows():
            source = str(row.get("retained_source", "table15_retained"))
            if source == "performance_mode":
                std = float(row.get("performance_primary_std", np.nan))
            else:
                std = float(row.get("previous_primary_std", np.nan))
            update_lookup(
                lookup,
                row["dataset"],
                row["official_metric"],
                metric_direction(row["official_metric"], str(row.get("primary_direction", ""))),
                float(row["retained_primary_mean"]),
                std,
                f"table15_{source}",
                str(row.get("retained_model", "")),
            )

    table32 = TABLE_DIR / "table32_tdc_nature_multimethod_fusion_retained_best.csv"
    if table32.exists():
        df = pd.read_csv(table32)
        for _, row in df.iterrows():
            update_lookup(
                lookup,
                row["dataset"],
                row["primary_metric"],
                metric_direction(row["primary_metric"], str(row.get("primary_direction", ""))),
                float(row["retained_primary_mean"]),
                float(row.get("retained_primary_std", np.nan)),
                f"table32_{row.get('retained_source', 'retained')}",
                str(row.get("retained_model", "")),
            )

    table35 = TABLE_DIR / "table35_3d_roughness_regression_retained_best.csv"
    if table35.exists():
        df = pd.read_csv(table35)
        for _, row in df.iterrows():
            update_lookup(
                lookup,
                row["dataset"],
                row["primary_metric"],
                metric_direction(row["primary_metric"], str(row.get("primary_direction", ""))),
                float(row["retained_primary_mean"]),
                float(row.get("previous_primary_std", np.nan)),
                f"table35_{row.get('retained_source', 'retained')}",
                str(row.get("retained_model", "")),
            )

    return lookup


def load_integrated_candidates() -> pd.DataFrame:
    frames = []
    for source, path in SOURCE_PATHS.items():
        if not path.exists():
            continue
        frame = normalize_source(source, path)
        if frame.empty:
            continue
        frame["source"] = source
        frame["raw_model"] = frame["model"].astype(str)
        frame["model"] = frame["source"].astype(str) + "::" + frame["raw_model"].astype(str)
        frame["canonical_dataset"] = frame["dataset"].map(canonical_dataset)
        frame["primary_metric"] = frame["primary_metric"].map(normalize_metric)
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out = out[np.isfinite(out["validation_primary"]) & np.isfinite(out["primary_value"])].reset_index(drop=True)
    return out


def split_model_id(model_id: str) -> tuple[str, str]:
    if "::" not in model_id:
        return "", model_id
    source, model = model_id.split("::", 1)
    return source, model


def select_policy_rows(candidates: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    policies = {
        "risk_adjusted_lambda_0.5": lambda ms: choose_risk_adjusted(ms, 0.5),
        "stability_tie_breaker": choose_stability_tie,
    }
    rows: list[dict[str, object]] = []
    model_rows = []
    current_lookup = load_current_retained_lookup()

    group_cols = ["canonical_dataset", "task_type", "primary_metric", "primary_direction"]
    for group_key, sub in candidates.groupby(group_cols, sort=True):
        dataset, task_type, metric, direction = group_key
        ms = model_summary(sub)
        if ms.empty:
            continue
        model_rows.append(ms.assign(canonical_dataset=dataset, task_type=task_type))
        current = current_lookup.get((dataset, metric), {})
        current_mean = float(current.get("current_retained_primary_mean", np.nan))
        current_std = float(current.get("current_retained_primary_std", np.nan))

        for policy, chooser in policies.items():
            selected = chooser(ms)
            selected_source, selected_model = split_model_id(str(selected["model"]))
            delta = (
                direction_delta(direction, current_mean, float(selected["primary_mean"]))
                if math.isfinite(current_mean)
                else np.nan
            )
            rows.append(
                {
                    "canonical_dataset": dataset,
                    "task_type": task_type,
                    "primary_metric": metric,
                    "primary_direction": direction,
                    "fixed_policy": policy,
                    "n_sources": int(sub["source"].nunique()),
                    "n_candidate_models": int(ms["model"].nunique()),
                    "n_candidate_rows": int(len(sub)),
                    "n_seeds": int(selected["n_seeds"]),
                    "selected_source": selected_source,
                    "selected_model": selected_model,
                    "selected_candidate_type": selected["candidate_type"],
                    "selected_validation_mean": float(selected["validation_mean"]),
                    "selected_validation_std": float(selected["validation_std"]),
                    "selected_primary_mean": float(selected["primary_mean"]),
                    "selected_primary_std": float(selected["primary_std"]),
                    "current_retained_primary_mean": current_mean,
                    "current_retained_primary_std": current_std,
                    "current_retained_source": current.get("current_retained_source", ""),
                    "current_retained_model": current.get("current_retained_model", ""),
                    "delta_vs_current_retained": delta,
                    "fixed_policy_signal": "positive_vs_current"
                    if math.isfinite(delta) and delta > 0
                    else "not_positive_vs_current",
                }
            )
    policy_results = pd.DataFrame(rows)
    model_table = pd.concat(model_rows, ignore_index=True) if model_rows else pd.DataFrame()
    return policy_results, model_table


def build_retained_best(policy_results: pd.DataFrame) -> pd.DataFrame:
    primary = policy_results[policy_results["fixed_policy"].eq(PRIMARY_POLICY)].copy()
    rows = []
    for row in primary.itertuples(index=False):
        delta = float(row.delta_vs_current_retained)
        promoted = math.isfinite(delta) and delta > 0
        rows.append(
            {
                "canonical_dataset": row.canonical_dataset,
                "task_type": row.task_type,
                "primary_metric": row.primary_metric,
                "primary_direction": row.primary_direction,
                "fixed_policy": row.fixed_policy,
                "n_sources": row.n_sources,
                "n_candidate_models": row.n_candidate_models,
                "selected_source": row.selected_source,
                "selected_model": row.selected_model,
                "selected_primary_mean": row.selected_primary_mean,
                "selected_primary_std": row.selected_primary_std,
                "current_retained_primary_mean": row.current_retained_primary_mean,
                "current_retained_primary_std": row.current_retained_primary_std,
                "delta_vs_current_retained": row.delta_vs_current_retained,
                "retained_source": "formal_fixed_policy" if promoted else "current_retained",
                "retained_primary_mean": row.selected_primary_mean if promoted else row.current_retained_primary_mean,
                "retained_primary_std": row.selected_primary_std if promoted else row.current_retained_primary_std,
                "retained_model": row.selected_model if promoted else row.current_retained_model,
                "promotion_status": "promoted_by_fixed_policy" if promoted else "kept_current_retained",
            }
        )
    return pd.DataFrame(rows)


def build_policy_summary(policy_results: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for policy, sub in policy_results.groupby("fixed_policy", sort=False):
        finite = sub[np.isfinite(sub["delta_vs_current_retained"])].copy()
        positive = finite[finite["delta_vs_current_retained"] > 0]
        negative = finite[finite["delta_vs_current_retained"] < 0]
        rows.append(
            {
                "fixed_policy": policy,
                "n_endpoint_metrics": int(len(finite)),
                "n_positive_vs_current": int(len(positive)),
                "n_negative_vs_current": int(len(negative)),
                "positive_rate": float(len(positive) / len(finite)) if len(finite) else np.nan,
                "mean_delta_vs_current": float(finite["delta_vs_current_retained"].mean()) if len(finite) else np.nan,
                "median_delta_vs_current": float(finite["delta_vs_current_retained"].median()) if len(finite) else np.nan,
                "mean_positive_delta": float(positive["delta_vs_current_retained"].mean()) if len(positive) else np.nan,
                "largest_positive_delta": float(positive["delta_vs_current_retained"].max()) if len(positive) else np.nan,
                "largest_negative_delta": float(negative["delta_vs_current_retained"].min()) if len(negative) else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values(["n_positive_vs_current", "mean_delta_vs_current"], ascending=[False, False])


def plot_integration(policy_results: pd.DataFrame, summary: pd.DataFrame) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    primary = policy_results[
        policy_results["fixed_policy"].eq(PRIMARY_POLICY) & np.isfinite(policy_results["delta_vs_current_retained"])
    ].copy()
    positives = primary[primary["delta_vs_current_retained"] > 0].sort_values("delta_vs_current_retained").tail(12)
    colors = {
        "risk_adjusted_lambda_0.5": "#166534",
        "stability_tie_breaker": "#1d4ed8",
    }
    policy_labels = {
        "risk_adjusted_lambda_0.5": "risk-adjusted",
        "stability_tie_breaker": "stability tie-breaker",
    }
    dataset_labels = {
        "bbbp": "BBBP",
        "clintox": "ClinTox",
        "herg": "hERG",
        "ld50_zhu": "LD50",
        "half_life_obach": "Half-life",
        "clearance_microsome_az": "Clearance microsome",
        "clearance_hepatocyte_az": "Clearance hepatocyte",
        "cyp2c9_substrate_carbonmangels": "CYP2C9 substrate",
        "vdss_lombardo": "VDss",
        "pgp_broccatelli": "Pgp",
    }
    source_labels = {
        "moleculenet_nature_fusion": "MN fusion",
        "moleculenet_targeted_rebuild": "MN targeted",
        "tdc_performance_mode": "TDC performance",
        "tdc_nature_fusion": "TDC fusion",
        "three_d_roughness_regression": "3D-lite",
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
    fig, axes = plt.subplots(1, 2, figsize=(13.8, 6.3), gridspec_kw={"width_ratios": [0.9, 1.2]})

    ax = axes[0]
    ordered = summary.sort_values("n_positive_vs_current", ascending=True)
    y = np.arange(len(ordered))
    ax.barh(y, ordered["n_positive_vs_current"], color=[colors.get(p, "#64748b") for p in ordered["fixed_policy"]], height=0.55)
    ax.set_yticks(y)
    ax.set_yticklabels([policy_labels.get(str(p), str(p)) for p in ordered["fixed_policy"]], fontsize=8.5)
    ax.set_xlabel("Positive endpoint-metrics")
    ax.set_title("A  Fixed policy integration", loc="left", fontsize=11.5, fontweight="bold")
    ax.grid(axis="x", color="#e5e7eb", linewidth=0.65, alpha=0.85)
    for yy, row in zip(y, ordered.itertuples(index=False)):
        ax.text(
            row.n_positive_vs_current + 0.1,
            yy,
            f"{row.n_positive_vs_current}/{row.n_endpoint_metrics}",
            va="center",
            fontsize=8.0,
        )

    ax = axes[1]
    if positives.empty:
        ax.text(0.5, 0.5, "No positive primary-policy signals", transform=ax.transAxes, ha="center", va="center")
        ax.set_axis_off()
    else:
        labels = [
            f"{dataset_labels.get(str(r.canonical_dataset), str(r.canonical_dataset))}\n"
            f"{source_labels.get(str(r.selected_source), str(r.selected_source))}"
            for r in positives.itertuples(index=False)
        ]
        deltas = positives["delta_vs_current_retained"].astype(float).to_numpy()
        y = np.arange(len(positives))
        ax.barh(y, deltas, color="#166534", height=0.56, edgecolor="white", linewidth=0.8)
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=7.5)
        ax.set_xlabel("Delta vs current retained-best")
        ax.set_title("B  Primary policy positive integrations", loc="left", fontsize=11.5, fontweight="bold")
        ax.grid(axis="x", color="#e5e7eb", linewidth=0.65, alpha=0.85)
        span = max(0.002, float(np.nanmax(np.abs(deltas))) * 0.06)
        for yy, delta in zip(y, deltas):
            ax.text(delta + span, yy, f"{delta:+.4f}", va="center", fontsize=7.3, color="#14532d")
        ax.set_xlim(0, max(0.03, float(np.nanmax(deltas)) + span * 8))

    fig.text(
        0.13,
        0.035,
        "Primary policy is fixed before integration. Retained-best promotions are reported separately from the fixed-policy audit.",
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
        fig.savefig(FIG22_PATH.with_suffix(f".{ext}"), bbox_inches="tight")
    plt.close(fig)


def write_readme(summary: pd.DataFrame, retained: pd.DataFrame) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Formal fixed-selector integration",
        "",
        f"Primary fixed policy: `{PRIMARY_POLICY}`.",
        "The run integrates available candidates by canonical endpoint and primary metric, then applies the fixed policy globally.",
        "No endpoint-specific policy is chosen using test labels.",
        "",
        "Outputs:",
        f"- Policy results: `{TABLE41_PATH}`",
        f"- Primary-policy retained-best table: `{TABLE42_PATH}`",
        f"- Policy summary: `{TABLE43_PATH}`",
        f"- Figure: `{FIG22_PATH.with_suffix('.png')}`",
        "",
        "Policy summary:",
    ]
    for row in summary.itertuples(index=False):
        lines.append(
            f"- `{row.fixed_policy}`: {row.n_positive_vs_current}/{row.n_endpoint_metrics} positive, "
            f"mean delta={row.mean_delta_vs_current:+.4f}, largest positive={row.largest_positive_delta:+.4f}."
        )
    promoted = retained[retained["promotion_status"].eq("promoted_by_fixed_policy")]
    lines.extend(["", "Primary-policy promotions:"])
    if promoted.empty:
        lines.append("- None.")
    else:
        for row in promoted.itertuples(index=False):
            lines.append(
                f"- `{row.canonical_dataset}`: {row.current_retained_primary_mean:.4f} -> "
                f"{row.retained_primary_mean:.4f}, delta={row.delta_vs_current_retained:+.4f}, "
                f"model=`{row.selected_source}::{row.selected_model}`."
            )
    lines.extend(
        [
            "",
            "Interpretation boundary: the fixed-policy table should be reported honestly even where it underperforms.",
            "The retained-best table is a conservative manuscript summary of endpoints that can be promoted after the fixed policy is declared.",
        ]
    )
    (REPORT_DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    candidates = load_integrated_candidates()
    candidates.to_csv(REPORT_DIR / "integrated_candidate_metrics.csv", index=False)
    policy_results, model_table = select_policy_rows(candidates)
    retained = build_retained_best(policy_results)
    summary = build_policy_summary(policy_results)

    policy_results.to_csv(TABLE41_PATH, index=False)
    retained.to_csv(TABLE42_PATH, index=False)
    summary.to_csv(TABLE43_PATH, index=False)
    policy_results.to_csv(REPORT_DIR / "formal_fixed_selector_policy_results.csv", index=False)
    retained.to_csv(REPORT_DIR / "formal_risk_adjusted_integration_retained_best.csv", index=False)
    summary.to_csv(REPORT_DIR / "formal_fixed_selector_policy_summary.csv", index=False)
    if not model_table.empty:
        model_table.to_csv(REPORT_DIR / "integrated_model_summary.csv", index=False)
    plot_integration(policy_results, summary)
    write_readme(summary, retained)
    print(f"Wrote {REPORT_DIR}")
    print(f"Wrote {TABLE41_PATH}")
    print(f"Wrote {TABLE42_PATH}")
    print(f"Wrote {TABLE43_PATH}")
    print(f"Wrote {FIG22_PATH.with_suffix('.png')}")


if __name__ == "__main__":
    main()
