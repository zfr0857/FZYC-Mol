from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results" / "reviewer_core_20260624" / "multiview_nested"
RNG_SEED = 20260624


def exact_sign_flip_p(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    observed = abs(float(values.mean()))
    null = [
        abs(float(np.mean(values * np.asarray(signs))))
        for signs in itertools.product([-1.0, 1.0], repeat=len(values))
    ]
    return float(np.mean(np.asarray(null) >= observed - 1e-15))


def cluster_ci(frame: pd.DataFrame, value_col: str, reps: int = 10_000) -> tuple[float, float]:
    endpoint_values = {task: group[value_col].to_numpy(float) for task, group in frame.groupby("task", sort=True)}
    tasks = list(endpoint_values)
    rng = np.random.default_rng(RNG_SEED)
    draws = []
    for _ in range(reps):
        sampled = rng.choice(tasks, len(tasks), replace=True)
        draws.append(np.mean(np.concatenate([endpoint_values[task] for task in sampled])))
    return tuple(np.quantile(draws, [0.025, 0.975]).astype(float))


def paired_effect(
    policies: pd.DataFrame,
    ranges: pd.DataFrame,
    left_variant: str,
    left_policy: str,
    right_variant: str,
    right_policy: str,
    label: str,
) -> tuple[dict[str, object], pd.DataFrame]:
    keys = ["task", "seed", "outer_fold"]
    left = policies[
        policies["variant"].eq(left_variant) & policies["policy"].eq(left_policy)
    ][keys + ["outer_utility", "selected_representation", "selected_family"]].rename(
        columns={
            "outer_utility": "left_outer_utility",
            "selected_representation": "left_representation",
            "selected_family": "left_family",
        }
    )
    right = policies[
        policies["variant"].eq(right_variant) & policies["policy"].eq(right_policy)
    ][keys + ["outer_utility", "selected_representation", "selected_family"]].rename(
        columns={
            "outer_utility": "right_outer_utility",
            "selected_representation": "right_representation",
            "selected_family": "right_family",
        }
    )
    paired = left.merge(right, on=keys, validate="one_to_one").merge(ranges, on=keys, validate="one_to_one")
    paired["raw_utility_gain"] = paired["left_outer_utility"] - paired["right_outer_utility"]
    paired["normalized_utility_gain"] = paired["raw_utility_gain"] / paired["full_utility_range"]
    endpoint = paired.groupby("task", as_index=False)["normalized_utility_gain"].mean()
    low, high = cluster_ci(paired, "normalized_utility_gain")
    summary = {
        "comparison": label,
        "left_variant": left_variant,
        "left_policy": left_policy,
        "right_variant": right_variant,
        "right_policy": right_policy,
        "paired_outer_units": len(paired),
        "mean_normalized_utility_gain": float(paired["normalized_utility_gain"].mean()),
        "endpoint_cluster_ci95_low": low,
        "endpoint_cluster_ci95_high": high,
        "endpoint_median_gain": float(endpoint["normalized_utility_gain"].median()),
        "endpoints_positive": int((endpoint["normalized_utility_gain"] > 0).sum()),
        "endpoints_negative": int((endpoint["normalized_utility_gain"] < 0).sum()),
        "exact_sign_flip_p": exact_sign_flip_p(endpoint["normalized_utility_gain"].to_numpy(float)),
    }
    paired["comparison"] = label
    return summary, paired


def main() -> None:
    policies = pd.read_csv(BASE / "policy_detail.csv")
    outer = pd.read_csv(BASE / "outer_candidate_scores.csv")
    keys = ["task", "seed", "outer_fold"]
    ranges = outer.groupby(keys, as_index=False).agg(
        full_utility_max=("outer_utility", "max"),
        full_utility_min=("outer_utility", "min"),
    )
    ranges["full_utility_range"] = (
        ranges["full_utility_max"] - ranges["full_utility_min"]
    ).clip(lower=1e-12)
    comparisons = [
        (
            "full_multiview",
            "test_oracle",
            "morgan_only",
            "test_oracle",
            "attainable multiview gain vs Morgan-only oracle",
        ),
        (
            "full_multiview",
            "validation_best",
            "morgan_only",
            "validation_best",
            "realized multiview validation-best gain vs Morgan-only",
        ),
        (
            "full_multiview",
            "validation_best",
            "full_multiview",
            "fixed_morgan_rf",
            "full-pool validation-best gain vs fixed Morgan RF",
        ),
        (
            "full_multiview",
            "validation_best",
            "full_multiview",
            "one_se_stable",
            "validation-best gain vs one-SE in full pool",
        ),
        (
            "full_multiview",
            "validation_best",
            "full_multiview",
            "risk_adjusted",
            "validation-best gain vs risk-adjusted in full pool",
        ),
        (
            "full_multiview",
            "validation_best",
            "no_multiview_concat",
            "validation_best",
            "concatenated multiview gain vs separate-view pool",
        ),
    ]
    summary_rows = []
    paired_rows = []
    for args in comparisons:
        summary, paired = paired_effect(policies, ranges, *args)
        summary_rows.append(summary)
        paired_rows.append(paired)
    summary = pd.DataFrame(summary_rows)
    detail = pd.concat(paired_rows, ignore_index=True)
    summary.to_csv(BASE / "paired_multiview_effects.csv", index=False)
    detail.to_csv(BASE / "paired_multiview_effects_long.csv", index=False)

    endpoint_policy = policies[
        policies["policy"].isin(["validation_best", "one_se_stable", "risk_adjusted"])
    ].groupby(["task", "variant", "policy"], as_index=False).agg(
        mean_normalized_regret=("normalized_regret", "mean"),
        median_normalized_regret=("normalized_regret", "median"),
        mean_outer_utility=("outer_utility", "mean"),
        selected_representations=("selected_representation", "nunique"),
    )
    endpoint_policy.to_csv(BASE / "endpoint_policy_summary.csv", index=False)
    representation_counts = policies[
        policies["variant"].eq("full_multiview") & policies["policy"].eq("validation_best")
    ].groupby(["task", "selected_representation"], as_index=False).size()
    representation_counts.to_csv(BASE / "endpoint_representation_counts.csv", index=False)

    values = {
        row["comparison"]: {
            key: value
            for key, value in row.items()
            if key not in {"comparison", "left_variant", "left_policy", "right_variant", "right_policy"}
        }
        for row in summary_rows
    }
    (BASE / "multiview_values.json").write_text(
        json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
