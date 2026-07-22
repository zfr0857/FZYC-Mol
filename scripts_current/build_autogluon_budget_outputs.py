from __future__ import annotations

import math
from collections import Counter
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def _entropy(values: pd.Series) -> float:
    counts = Counter(values.astype(str))
    if len(counts) <= 1:
        return 0.0
    probabilities = [count / len(values) for count in counts.values()]
    return -sum(value * math.log(value) for value in probabilities) / math.log(len(counts))


def build_outputs(root: Path = ROOT) -> dict[str, Path]:
    directories = {
        30: root / "results" / "external_panels" / "autogluon_budget_30",
        300: root / "results" / "external_panels" / "autogluon_budget_300",
        1800: root / "results" / "external_panels" / "autogluon_budget_1800",
    }
    summaries = []
    outer_frames = []
    policy_path = root / "reports" / "draft10_core_experiments_20260621" / "expanded_nested" / "policy_detail.csv"
    policy_wide = None
    policies = ("fixed_single", "validation_best", "one_se_stable", "risk_adjusted")
    if policy_path.exists():
        policy = pd.read_csv(policy_path)
        policy = policy.loc[policy["pool_size"].eq(32) & policy["policy"].isin(policies)]
        policy_wide = policy.pivot(index=["dataset", "outer_fold"], columns="policy", values="outer_utility").reset_index()
        policy_wide = policy_wide.rename(columns={name: f"{name}_outer_utility" for name in policies})
    for budget, folder in directories.items():
        summary = pd.read_csv(folder / "summary.csv")
        outer = pd.read_csv(folder / "outer_results.csv")
        summary["budget_seconds"] = budget
        outer["budget_seconds"] = budget
        if policy_wide is not None:
            outer = outer.merge(policy_wide, on=["dataset", "outer_fold"], how="left", validate="many_to_one")
            for policy_name in policies:
                outer[f"delta_vs_{policy_name}"] = outer["outer_utility"] - outer[f"{policy_name}_outer_utility"]
        stability = (
            outer.groupby("dataset", as_index=False)
            .agg(
                model_selection_entropy=("best_model", _entropy),
                modal_model_rate=("best_model", lambda values: float(values.value_counts(normalize=True).iloc[0])),
                actual_fit_seconds_mean=("fit_seconds", "mean"),
                model_count_mean=("model_count", "mean"),
                model_count_max=("model_count", "max"),
                peak_rss_mb_max=("peak_rss_mb", "max"),
            )
        )
        summary = summary.merge(stability, on="dataset", how="left")
        if policy_wide is not None:
            comparison_aggregations = {}
            for policy_name in policies:
                comparison_aggregations[f"{policy_name}_outer_utility_mean"] = (f"{policy_name}_outer_utility", "mean")
                comparison_aggregations[f"delta_vs_{policy_name}"] = (f"delta_vs_{policy_name}", "mean")
                comparison_aggregations[f"win_folds_vs_{policy_name}"] = (
                    f"delta_vs_{policy_name}",
                    lambda values: int((values > 1e-12).sum()),
                )
                comparison_aggregations[f"loss_folds_vs_{policy_name}"] = (
                    f"delta_vs_{policy_name}",
                    lambda values: int((values < -1e-12).sum()),
                )
            comparison = outer.groupby("dataset", as_index=False).agg(**comparison_aggregations)
            summary = summary.merge(comparison, on="dataset", how="left")
        summaries.append(summary)
        outer_frames.append(outer)
    output = root / "results" / "external_panels"
    output.mkdir(parents=True, exist_ok=True)
    paths = {"summary": output / "autogluon_budget.csv", "outer": output / "autogluon_budget_outer_long.csv"}
    pd.concat(summaries, ignore_index=True).to_csv(paths["summary"], index=False)
    pd.concat(outer_frames, ignore_index=True).to_csv(paths["outer"], index=False)
    return paths


def main() -> None:
    for name, path in build_outputs().items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
