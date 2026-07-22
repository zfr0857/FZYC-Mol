from __future__ import annotations

import json
import shutil
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OLD_PACKAGE = ROOT / "output" / "小论文-3_图表包"
PACKAGE = ROOT / "output" / "小论文-4_图表包"
FIG_DIR = PACKAGE / "figures"
SRC_DIR = PACKAGE / "source_data"
CORE = ROOT / "results" / "reviewer_core_20260624"
MULTI = CORE / "multiview_nested"

COL = {
    "ink": "#182230",
    "muted": "#667085",
    "line": "#98A2B3",
    "blue": "#3568A8",
    "blue2": "#7EA6D8",
    "green": "#4E9A73",
    "orange": "#D98C3F",
    "purple": "#8B75AF",
    "red": "#BF5B5B",
    "teal": "#3C8D93",
    "grey": "#737B86",
    "light": "#D8DEE6",
}


def setup() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Microsoft YaHei", "DejaVu Sans", "sans-serif"],
            "font.size": 8.0,
            "axes.titlesize": 9.5,
            "axes.labelsize": 8.5,
            "xtick.labelsize": 7.4,
            "ytick.labelsize": 7.4,
            "legend.fontsize": 7.0,
            "axes.linewidth": 0.85,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "legend.frameon": False,
            "svg.fonttype": "none",
            "savefig.facecolor": "white",
            "figure.facecolor": "white",
        }
    )


def panel(ax: plt.Axes, label: str, x: float = -0.16, y: float = 1.08) -> None:
    ax.text(x, y, label, transform=ax.transAxes, fontsize=10.2, fontweight="bold", va="top", color=COL["ink"])


def style(ax: plt.Axes, grid: str | None = "x") -> None:
    ax.tick_params(length=3, width=0.75, colors=COL["ink"])
    ax.spines["left"].set_color(COL["ink"])
    ax.spines["bottom"].set_color(COL["ink"])
    if grid:
        ax.grid(axis=grid, color="#E7EAF0", linewidth=0.55, zorder=0)


def copy_previous_assets() -> None:
    for path in (OLD_PACKAGE / "figures").glob("fig*.*"):
        shutil.copy2(path, FIG_DIR / path.name)
    for path in (OLD_PACKAGE / "source_data").glob("*.csv"):
        shutil.copy2(path, SRC_DIR / path.name)


def copy_new_source_data() -> None:
    root_files = [
        "paired_pool_effects.csv",
        "paired_pool_endpoint_effects.csv",
        "risk_component_summary.csv",
        "risk_quartiles.csv",
        "risk_loeo_predictions.csv",
        "risk_loeo_endpoint_summary.csv",
        "cross_endpoint_risk_features.csv",
        "cross_endpoint_meta_risk_predictions.csv",
        "cross_endpoint_meta_risk_model_selection.csv",
        "cross_endpoint_meta_risk_endpoint_summary.csv",
        "signal_recovery_units.csv",
        "signal_recovery_summary.csv",
    ]
    multi_files = [
        "candidate_registry.csv",
        "inner_scores.csv",
        "outer_candidate_scores.csv",
        "policy_detail.csv",
        "ranking_metrics.csv",
        "policy_summary.csv",
        "ranking_summary.csv",
        "validation_best_representation_counts.csv",
        "paired_multiview_effects.csv",
        "paired_multiview_effects_long.csv",
        "endpoint_policy_summary.csv",
        "endpoint_representation_counts.csv",
    ]
    for name in root_files:
        shutil.copy2(CORE / name, SRC_DIR / f"fig11_{name}")
    for name in multi_files:
        shutil.copy2(MULTI / name, SRC_DIR / f"fig11_multiview_{name}")
    for source, target in [
        (CORE / "reviewer_core_values.json", PACKAGE / "reviewer_core_values.json"),
        (CORE / "cross_endpoint_meta_risk_summary.json", PACKAGE / "cross_endpoint_meta_risk_summary.json"),
        (MULTI / "multiview_values.json", PACKAGE / "multiview_values.json"),
        (MULTI / "run_manifest.json", PACKAGE / "multiview_run_manifest.json"),
    ]:
        shutil.copy2(source, target)


def figure11() -> None:
    endpoint_effects = pd.read_csv(CORE / "paired_pool_endpoint_effects.csv")
    signal = pd.read_csv(CORE / "signal_recovery_summary.csv")
    quartiles = pd.read_csv(CORE / "risk_quartiles.csv")
    meta = pd.read_csv(CORE / "cross_endpoint_meta_risk_endpoint_summary.csv")
    policy = pd.read_csv(MULTI / "policy_summary.csv")
    paired = pd.read_csv(MULTI / "paired_multiview_effects.csv")

    fig, axes = plt.subplots(2, 3, figsize=(7.2, 5.75))

    ax = axes[0, 0]
    effect = endpoint_effects[
        endpoint_effects["metric"].eq("fixed_normalized_regret")
        & endpoint_effects["comparison"].eq("K=32 vs K=4")
    ].sort_values("32_minus_4")
    y = np.arange(len(effect))
    ax.scatter(effect["32_minus_4"], y, color=COL["blue"], s=22, zorder=3)
    ax.axvline(0, color=COL["ink"], lw=0.8)
    ax.set_yticks(y, effect["endpoint"].str.replace("tdc_", "").str.replace("_", " "))
    ax.tick_params(axis="y", labelsize=6.7)
    ax.set_xlabel("Paired regret change, K=32 − K=4")
    ax.set_title("Endpoint-paired expansion effect", loc="left")
    style(ax, "x"); panel(ax, "a", -0.24)

    ax = axes[0, 1]
    s = signal[signal["pool_size"].eq(32)].sort_values("signal_correlation")
    ax.plot(s["signal_correlation"], s["chance_adjusted_hit_mean"], color=COL["blue"], marker="o", lw=1.5, label="Chance-adjusted Top-3")
    ax.fill_between(s["signal_correlation"], s["chance_adjusted_hit_ci95_low"], s["chance_adjusted_hit_ci95_high"], color=COL["blue2"], alpha=0.22)
    ax.axhline(0, color=COL["ink"], lw=0.7, ls="--")
    ax.set(xlabel="Injected validation–outer signal", ylabel="Chance-adjusted hit", ylim=(-0.12, 1.05))
    ax2 = ax.twinx()
    ax2.plot(s["signal_correlation"], s["fixed_normalized_regret_mean"], color=COL["orange"], marker="s", lw=1.35, label="Fixed regret")
    ax2.set_ylabel("Fixed regret", color=COL["orange"])
    ax2.tick_params(axis="y", colors=COL["orange"], labelsize=7.0)
    ax2.spines["top"].set_visible(False)
    handles = ax.get_lines()[:1] + ax2.get_lines()[:1]
    ax.legend(handles, [line.get_label() for line in handles], loc="upper center", bbox_to_anchor=(0.5, 1.00), fontsize=6.5)
    ax.set_title("Signal recovery (K=32)", loc="left")
    style(ax, "y"); panel(ax, "b")

    ax = axes[0, 2]
    qlabels = ["Q1\nlow", "Q2", "Q3", "Q4\nhigh"]
    ax.bar(np.arange(4), quartiles["mean_regret"], color=[COL["blue2"], COL["light"], COL["orange"], COL["red"]], width=0.72)
    ax.set_xticks(np.arange(4), qlabels)
    ax.set_ylabel("Mean fixed regret")
    ax.set_title("Equal-weight risk score", loc="left")
    ax.text(0.03, 0.96, "Within-stratum permutation\np = 0.953", transform=ax.transAxes, va="top", fontsize=6.7, color=COL["muted"])
    style(ax, "y"); panel(ax, "c")

    ax = axes[1, 0]
    meta = meta.sort_values("risk_gate_delta")
    y = np.arange(len(meta))
    ax.scatter(meta["risk_gate_delta"], y, color=np.where(meta["risk_gate_delta"] < 0, COL["green"], COL["red"]), s=22)
    ax.axvline(0, color=COL["ink"], lw=0.8)
    ax.axvspan(-0.0467, -0.0205, color=COL["pgreen"] if "pgreen" in COL else "#EDF7F0", alpha=0.9, zorder=0)
    ax.set_yticks(y, meta["endpoint"].str.replace("tdc_", "").str.replace("_", " "))
    ax.tick_params(axis="y", labelsize=6.7)
    ax.set_xlabel("50% gate regret change (retained − all)")
    ax.set_title("LOEO meta-risk gate", loc="left")
    style(ax, "x"); panel(ax, "d", -0.24)

    ax = axes[1, 1]
    full = policy[policy["variant"].eq("full_multiview") & policy["policy"].isin(["fixed_morgan_rf", "one_se_stable", "risk_adjusted", "validation_best"])].copy()
    order = ["fixed_morgan_rf", "one_se_stable", "risk_adjusted", "validation_best"]
    full["policy"] = pd.Categorical(full["policy"], order, ordered=True)
    full = full.sort_values("policy")
    x = np.arange(len(full))
    yerr = np.vstack([
        full["mean_normalized_regret"] - full["endpoint_cluster_ci95_low"],
        full["endpoint_cluster_ci95_high"] - full["mean_normalized_regret"],
    ])
    ax.bar(x, full["mean_normalized_regret"], color=[COL["grey"], COL["purple"], COL["orange"], COL["blue"]], width=0.68)
    ax.errorbar(x, full["mean_normalized_regret"], yerr=yerr, fmt="none", color=COL["ink"], capsize=2.5, lw=0.9)
    ax.set_xticks(x, ["Fixed\nMorgan RF", "one-SE", "Risk-\nadjusted", "Validation-\nbest"])
    ax.set_ylabel("Mean normalized regret")
    ax.set_title("Shared-split multiview pool", loc="left")
    style(ax, "y"); panel(ax, "e")

    ax = axes[1, 2]
    labels = {
        "attainable multiview gain vs Morgan-only oracle": "Attainable vs\nMorgan oracle",
        "realized multiview validation-best gain vs Morgan-only": "Realized vs\nMorgan selection",
        "full-pool validation-best gain vs fixed Morgan RF": "Selected vs\nfixed Morgan RF",
        "validation-best gain vs one-SE in full pool": "Validation-best\nvs one-SE",
        "concatenated multiview gain vs separate-view pool": "Concat vs\nseparate views",
    }
    effect = paired[paired["comparison"].isin(labels)].copy()
    effect["display"] = effect["comparison"].map(labels)
    effect = effect.sort_values("mean_normalized_utility_gain")
    y = np.arange(len(effect))
    xerr = np.vstack([
        effect["mean_normalized_utility_gain"] - effect["endpoint_cluster_ci95_low"],
        effect["endpoint_cluster_ci95_high"] - effect["mean_normalized_utility_gain"],
    ])
    ax.errorbar(effect["mean_normalized_utility_gain"], y, xerr=xerr, fmt="o", ms=4.5, color=COL["blue"], ecolor=COL["light"], capsize=2.5)
    ax.axvline(0, color=COL["ink"], lw=0.8)
    ax.set_yticks(y, effect["display"])
    ax.tick_params(axis="y", labelsize=6.6)
    ax.set_xlabel("Paired normalized utility gain")
    ax.set_title("Paired multiview gains", loc="left")
    style(ax, "x"); panel(ax, "f", -0.23)

    fig.tight_layout(w_pad=1.6, h_pad=2.0)
    fig.savefig(FIG_DIR / "fig11_reviewer_core_closure.svg", bbox_inches="tight")
    fig.savefig(FIG_DIR / "fig11_reviewer_core_closure.png", dpi=450, bbox_inches="tight")
    plt.close(fig)


def write_contract() -> None:
    text = """# 小论文-4 图形与证据契约\n\nFigure 11 closes four reviewer-facing gaps: endpoint-paired effect inference, signal-recovery calibration, honest prospective validation of selection risk, and shared-split multiview candidate retraining. The equal-weight risk score is explicitly downgraded to a descriptive diagnostic because its within-endpoint/pool permutation test is negative; the nested cross-endpoint meta-risk result is reported separately. All quantitative panels trace to CSV files in `source_data`. SVG text remains editable and PNG is exported at 450 dpi.\n"""
    (PACKAGE / "figure_contracts_and_qa.md").write_text(text, encoding="utf-8")


def main() -> None:
    setup()
    copy_previous_assets()
    copy_new_source_data()
    figure11()
    write_contract()
    print(f"Generated package with {len(list(FIG_DIR.glob('*.svg')))} SVG and {len(list(FIG_DIR.glob('*.png')))} PNG files")


if __name__ == "__main__":
    main()
