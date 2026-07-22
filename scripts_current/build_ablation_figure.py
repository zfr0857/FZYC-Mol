from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fzyc_mol.statistics.hierarchical_bootstrap import hierarchical_bootstrap  # noqa: E402


def _summarize(frame: pd.DataFrame, ablation_class: str) -> pd.DataFrame:
    rows = []
    for index, (variant, group) in enumerate(frame.groupby("variant", sort=True)):
        result = hierarchical_bootstrap(
            group,
            endpoint_col="endpoint",
            unit_col="split_id",
            value_col="full32_fixed_normalized_regret",
            replicates=5000,
            seed=20260622 + index,
        )
        rows.append(
            {
                "ablation_class": ablation_class,
                "variant": variant,
                "mean_fixed_regret": result.estimate,
                "ci95_low": result.ci_low,
                "ci95_high": result.ci_high,
                "n_endpoints": result.n_endpoints,
                "primary_cluster_unit": "endpoint",
            }
        )
    return pd.DataFrame(rows)


def build_outputs(root: Path = ROOT) -> dict[str, Path]:
    nested = root / "results" / "nested_selection"
    governance = _summarize(pd.read_csv(nested / "governance_ablation.csv"), "governance_rule")
    family = _summarize(pd.read_csv(nested / "family_removal.csv"), "candidate_family_removal")
    summary = pd.concat([governance, family], ignore_index=True)
    source = root / "results" / "source_data" / "ablation_summary.csv"
    summary.to_csv(source, index=False)

    labels = {
        "frozen_one_se_governance": "Frozen one-SE",
        "validation_best": "Validation best",
        "one_se_low_variance": "One-SE, low variance",
        "one_se_low_cost": "One-SE, low cost",
        "full_pool": "Full pool",
        "remove_bagging": "Remove bagging",
        "remove_boosting": "Remove boosting",
        "remove_linear": "Remove linear",
    }
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.2), constrained_layout=True)
    for axis, (ablation_class, title, color) in zip(
        axes,
        [
            ("governance_rule", "a  Governance-rule ablation", "#3E7C8A"),
            ("candidate_family_removal", "b  Candidate-family removal", "#B56576"),
        ],
    ):
        data = summary.loc[summary["ablation_class"].eq(ablation_class)].copy()
        data["label"] = data["variant"].map(labels)
        x = range(len(data))
        axis.errorbar(
            list(x),
            data["mean_fixed_regret"],
            yerr=[data["mean_fixed_regret"] - data["ci95_low"], data["ci95_high"] - data["mean_fixed_regret"]],
            fmt="o",
            color=color,
            capsize=3,
            markersize=7,
        )
        axis.set_xticks(list(x), data["label"], rotation=24, ha="right")
        axis.set_title(title)
        axis.set_ylabel("Full-32 fixed normalized regret")
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(axis="y", color="#D9D9D9", linewidth=0.6)
    figure = root / "results" / "figures" / "ablation_separation.png"
    fig.savefig(figure, dpi=450, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return {"source": source, "figure": figure}


if __name__ == "__main__":
    print(build_outputs())
