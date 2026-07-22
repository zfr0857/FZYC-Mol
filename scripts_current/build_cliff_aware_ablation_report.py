from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = ROOT / "reports" / "moleculeace_multifp"
CLIFF_DIR = ROOT / "reports" / "moleculeace_cliff_weighted"
OUT_DIR = ROOT / "reports" / "moleculeace_cliff_ablation"

BASE_MODELS = ["rf_multifp", "extratrees_multifp", "xgb_multifp", "lgbm_multifp"]


def setup_style() -> None:
    sns.set_theme(style="whitegrid", context="paper", font_scale=1.05)
    plt.rcParams.update(
        {
            "figure.dpi": 140,
            "savefig.dpi": 320,
            "font.family": "DejaVu Sans",
            "axes.titleweight": "bold",
            "axes.edgecolor": "#cbd5e1",
            "grid.color": "#e2e8f0",
            "legend.frameon": True,
            "legend.framealpha": 0.95,
        }
    )


def read_test_metrics(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path / "metrics_raw.csv")
    return frame[frame["split"].eq("test")].copy()


def paired_model_ablation(cliff: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for model in BASE_MODELS:
        base = cliff[cliff["model"].eq(model)].copy()
        weighted = cliff[cliff["model"].eq(f"{model}_cliffw")].copy()
        merged = weighted.merge(base, on=["task", "seed"], suffixes=("_cliffw", "_base"))
        if merged.empty:
            continue
        out = pd.DataFrame(
            {
                "task": merged["task"],
                "seed": merged["seed"],
                "model": model,
                "delta_rmse_positive": merged["rmse_base"] - merged["rmse_cliffw"],
                "delta_mae_positive": merged["mae_base"] - merged["mae_cliffw"],
                "delta_cliff_rmse_positive": merged["cliff_rmse_base"] - merged["cliff_rmse_cliffw"],
                "delta_cliff_mae_positive": merged["cliff_mae_base"] - merged["cliff_mae_cliffw"],
                "delta_noncliff_rmse_positive": merged["noncliff_rmse_base"] - merged["noncliff_rmse_cliffw"],
                "base_rmse": merged["rmse_base"],
                "cliffw_rmse": merged["rmse_cliffw"],
                "base_cliff_rmse": merged["cliff_rmse_base"],
                "cliffw_cliff_rmse": merged["cliff_rmse_cliffw"],
            }
        )
        rows.append(out)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def selector_ablation(base: pd.DataFrame, cliff: pd.DataFrame) -> pd.DataFrame:
    base_sel = base[base["selected_by_validation"].fillna(0).astype(float).eq(1)].copy()
    cliff_sel = cliff[cliff["selected_by_validation"].fillna(0).astype(float).eq(1)].copy()
    merged = cliff_sel.merge(base_sel, on=["task", "seed"], suffixes=("_cliffaware", "_baseline"))
    if merged.empty:
        return pd.DataFrame()
    out = pd.DataFrame(
        {
            "task": merged["task"],
            "seed": merged["seed"],
            "baseline_model": merged["model_baseline"],
            "cliffaware_model": merged["model_cliffaware"],
            "delta_rmse_positive": merged["rmse_baseline"] - merged["rmse_cliffaware"],
            "delta_mae_positive": merged["mae_baseline"] - merged["mae_cliffaware"],
            "delta_cliff_rmse_positive": merged["cliff_rmse_baseline"] - merged["cliff_rmse_cliffaware"],
            "delta_cliff_mae_positive": merged["cliff_mae_baseline"] - merged["cliff_mae_cliffaware"],
            "delta_noncliff_rmse_positive": merged["noncliff_rmse_baseline"] - merged["noncliff_rmse_cliffaware"],
            "baseline_rmse": merged["rmse_baseline"],
            "cliffaware_rmse": merged["rmse_cliffaware"],
            "baseline_cliff_rmse": merged["cliff_rmse_baseline"],
            "cliffaware_cliff_rmse": merged["cliff_rmse_cliffaware"],
        }
    )
    out["selected_cliff_weighted"] = out["cliffaware_model"].str.contains("_cliffw", regex=False).astype(int)
    return out


def summarize_delta(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    metric_cols = [c for c in frame.columns if c.startswith("delta_")]
    rows = []
    grouped = [((), frame)] if not group_cols else frame.groupby(group_cols, dropna=False)
    for keys, group in grouped:
        if not group_cols:
            item = {}
        else:
            if not isinstance(keys, tuple):
                keys = (keys,)
            item = dict(zip(group_cols, keys))
        for col in metric_cols:
            values = pd.to_numeric(group[col], errors="coerce").dropna().to_numpy(dtype=float)
            if len(values) == 0:
                continue
            rows.append(
                {
                    **item,
                    "metric": col,
                    "n": len(values),
                    "mean_delta": float(np.mean(values)),
                    "median_delta": float(np.median(values)),
                    "positive_fraction": float((values > 0).mean()),
                    "std_delta": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
                }
            )
    return pd.DataFrame(rows)


def plot_reports(model_pairs: pd.DataFrame, selector_pairs: pd.DataFrame) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    setup_style()

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2))
    model_summary = summarize_delta(model_pairs, ["model"])
    cliff_model = model_summary[model_summary["metric"].eq("delta_cliff_rmse_positive")].sort_values("mean_delta", ascending=False)
    axes[0].bar(cliff_model["model"], cliff_model["mean_delta"], color="#0891b2", edgecolor="white")
    axes[0].axhline(0, color="#334155", linewidth=0.9)
    axes[0].set_ylabel("Cliff RMSE improvement")
    axes[0].set_title("Cliff-weighted expert ablation")
    axes[0].tick_params(axis="x", rotation=25)

    if not selector_pairs.empty:
        task_summary = selector_pairs.groupby("task", as_index=False)["delta_cliff_rmse_positive"].mean()
        task_summary = task_summary.sort_values("delta_cliff_rmse_positive", ascending=False).head(20)
        colors = ["#059669" if value >= 0 else "#dc2626" for value in task_summary["delta_cliff_rmse_positive"]]
        axes[1].barh(task_summary["task"], task_summary["delta_cliff_rmse_positive"], color=colors, edgecolor="white")
        axes[1].axvline(0, color="#334155", linewidth=0.9)
        axes[1].invert_yaxis()
        axes[1].set_xlabel("Cliff RMSE improvement")
        axes[1].set_title("Validation-selected cliff-aware selector")
    fig.suptitle("MoleculeACE activity-cliff ablation", fontsize=15, fontweight="bold")
    fig.text(0.5, 0.01, "Positive values mean lower RMSE after adding cliff-aware weighting or allowing the selector to choose cliff-aware experts.", ha="center", fontsize=9, color="#475569")
    fig.savefig(OUT_DIR / "moleculeace_cliff_ablation.png", bbox_inches="tight")
    fig.savefig(OUT_DIR / "moleculeace_cliff_ablation.svg", bbox_inches="tight")
    plt.close(fig)

    if not selector_pairs.empty:
        fig, ax = plt.subplots(figsize=(6.8, 5.6))
        ax.scatter(selector_pairs["delta_rmse_positive"], selector_pairs["delta_cliff_rmse_positive"], c=selector_pairs["selected_cliff_weighted"], cmap="viridis", alpha=0.75)
        ax.axhline(0, color="#334155", linewidth=0.9)
        ax.axvline(0, color="#334155", linewidth=0.9)
        ax.set_xlabel("Overall RMSE improvement")
        ax.set_ylabel("Cliff RMSE improvement")
        ax.set_title("Overall vs cliff-specific gains")
        fig.savefig(OUT_DIR / "moleculeace_selector_cliff_scatter.png", bbox_inches="tight")
        fig.savefig(OUT_DIR / "moleculeace_selector_cliff_scatter.svg", bbox_inches="tight")
        plt.close(fig)


def write_readme(model_summary: pd.DataFrame, selector_summary: pd.DataFrame, selector_pairs: pd.DataFrame) -> None:
    lines = [
        "# MoleculeACE cliff-aware ablation",
        "",
        "This report compares ordinary multi-fingerprint experts with cliff-weighted experts and compares the baseline validation selector with a cliff-aware candidate pool.",
        "",
        "Key model-level deltas:",
        "",
        model_summary.to_markdown(index=False),
        "",
        "Selector-level deltas:",
        "",
        selector_summary.to_markdown(index=False) if not selector_summary.empty else "No selector rows.",
        "",
    ]
    if not selector_pairs.empty:
        selected_rate = float(selector_pairs["selected_cliff_weighted"].mean())
        lines.extend(
            [
                f"The cliff-aware selector chose a cliff-weighted best-single expert in {selected_rate:.1%} of task-seed runs.",
                "",
                "Top selector gains by task:",
                "",
                selector_pairs.groupby("task", as_index=False)[["delta_rmse_positive", "delta_cliff_rmse_positive", "delta_noncliff_rmse_positive"]]
                .mean()
                .sort_values("delta_cliff_rmse_positive", ascending=False)
                .head(12)
                .to_markdown(index=False),
                "",
            ]
        )
    (OUT_DIR / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    global OUT_DIR

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-dir", type=Path, default=BASE_DIR, help="Baseline MoleculeACE metrics directory.")
    parser.add_argument("--cliff-dir", type=Path, default=CLIFF_DIR, help="Cliff-aware MoleculeACE metrics directory.")
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR, help="Directory for ablation tables and figures.")
    args = parser.parse_args()

    base_dir = args.base_dir if args.base_dir.is_absolute() else ROOT / args.base_dir
    cliff_dir = args.cliff_dir if args.cliff_dir.is_absolute() else ROOT / args.cliff_dir
    OUT_DIR = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base = read_test_metrics(base_dir)
    cliff = read_test_metrics(cliff_dir)
    model_pairs = paired_model_ablation(cliff)
    selector_pairs = selector_ablation(base, cliff)
    model_pairs.to_csv(OUT_DIR / "cliff_weighted_expert_pairs.csv", index=False)
    selector_pairs.to_csv(OUT_DIR / "cliff_aware_selector_pairs.csv", index=False)
    model_summary = summarize_delta(model_pairs, ["model"])
    selector_summary = summarize_delta(selector_pairs, []) if not selector_pairs.empty else pd.DataFrame()
    model_summary.to_csv(OUT_DIR / "cliff_weighted_expert_summary.csv", index=False)
    selector_summary.to_csv(OUT_DIR / "cliff_aware_selector_summary.csv", index=False)
    plot_reports(model_pairs, selector_pairs)
    write_readme(model_summary, selector_summary, selector_pairs)
    print(f"Wrote cliff-aware ablation report to {OUT_DIR}")


if __name__ == "__main__":
    main()
