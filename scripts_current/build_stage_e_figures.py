from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PALETTE = {"random_order": "#3B6FB6", "random_subset": "#D97706", "family_balanced": "#2A9D8F"}


def build_figures(
    candidate: pd.DataFrame,
    tdc: pd.DataFrame,
    conformal: pd.DataFrame,
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "candidate_pool": output_dir / "candidate_pool_control.png",
        "tdc_gate": output_dir / "tdc_gate_audit.png",
        "conformal": output_dir / "conformal_corrected.png",
    }

    fig, axes = plt.subplots(1, 3, figsize=(11.2, 3.4))
    for mode, group in candidate.groupby("mode", sort=True):
        group = group.sort_values("pool_size")
        color = PALETTE.get(mode, "#555555")
        error = [group["mean"] - group["ci95_low"], group["ci95_high"] - group["mean"]]
        axes[0].errorbar(group["pool_size"], group["mean"], yerr=error, marker="o", capsize=3, color=color, label=mode)
        axes[1].plot(group["pool_size"], group["chance_adjusted_hit_mean"], marker="o", color=color)
        axes[2].plot(group["pool_size"], group["rank_percentile_mean"], marker="o", color=color)
    axes[0].set_ylabel("Fixed-denominator regret")
    axes[1].set_ylabel("Chance-adjusted Top-3 hit")
    axes[2].set_ylabel("Oracle rank percentile")
    for axis in axes:
        axis.set_xlabel("Candidate-pool size")
        axis.spines[["top", "right"]].set_visible(False)
    axes[0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(paths["candidate_pool"], dpi=240)
    plt.close(fig)

    counts = tdc["gate_category"].value_counts().sort_values()
    fig, axis = plt.subplots(figsize=(6.8, 3.4))
    axis.barh(counts.index.str.replace("_", " "), counts.values, color="#4C78A8")
    axis.set_xlabel("Endpoints")
    axis.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(paths["tdc_gate"], dpi=240)
    plt.close(fig)

    summary = conformal.groupby(["task_type", "target_coverage"], as_index=False)["coverage"].mean()
    fig, axis = plt.subplots(figsize=(5.2, 3.6))
    for task, group in summary.groupby("task_type", sort=True):
        axis.plot(group["target_coverage"], group["coverage"], marker="o", label=task)
    low = float(summary["target_coverage"].min())
    axis.plot([low, 1.0], [low, 1.0], linestyle="--", color="#777777", label="nominal")
    axis.set_xlabel("Target coverage")
    axis.set_ylabel("Empirical coverage")
    axis.legend(frameon=False)
    axis.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(paths["conformal"], dpi=240)
    plt.close(fig)
    return paths


def main() -> None:
    source = ROOT / "results" / "source_data"
    paths = build_figures(
        pd.read_csv(source / "candidate_pool_summary.csv"),
        pd.read_csv(source / "tdc_gate_audit.csv"),
        pd.read_csv(source / "conformal_long.csv"),
        ROOT / "results" / "figures",
    )
    for name, path in paths.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
