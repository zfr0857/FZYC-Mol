from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from fzyc_mol.selection.selection_closure import (
    build_selection_risk_frame,
    leave_one_endpoint_out_policy,
    permutation_null_for_unit,
    selection_risk_curve,
)


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "selection_closure"
NESTED = ROOT / "results" / "nested_selection"
REPEATED = NESTED / "repeated_nested"


def stable_seed(*parts: object) -> int:
    digest = hashlib.sha256("|".join(map(str, parts)).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def endpoint_bootstrap_spearman(frame: pd.DataFrame, n_boot: int = 2000, seed: int = 20260623) -> tuple[float, float]:
    endpoints = np.array(sorted(frame["endpoint"].unique()))
    rng = np.random.default_rng(seed)
    values: list[float] = []
    for _ in range(n_boot):
        sampled = rng.choice(endpoints, size=len(endpoints), replace=True)
        chunks = []
        for draw, endpoint in enumerate(sampled):
            part = frame.loc[frame["endpoint"] == endpoint].copy()
            part["bootstrap_endpoint"] = f"{endpoint}:{draw}"
            chunks.append(part)
        boot = pd.concat(chunks, ignore_index=True)
        rho = spearmanr(boot["selection_risk"], boot["fixed_normalized_regret"]).statistic
        if np.isfinite(rho):
            values.append(float(rho))
    return tuple(np.quantile(values, [0.025, 0.975]))


def run_selection_risk() -> dict[str, object]:
    nested = pd.read_csv(NESTED / "nested_results_long.csv")
    regret = pd.read_csv(NESTED / "repeated_regret_decomposition.csv")
    frame = build_selection_risk_frame(nested, regret)
    frame.to_csv(RESULTS / "selection_risk_units.csv", index=False)

    rows = []
    curve_rows = []
    for label, part in [("all", frame), *[(str(k), frame.loc[frame["pool_size"] == k]) for k in (4, 8, 16, 32)]]:
        rho = float(spearmanr(part["selection_risk"], part["fixed_normalized_regret"]).statistic)
        low = part.loc[part["selection_risk"] <= part["selection_risk"].median(), "fixed_normalized_regret"]
        high = part.loc[part["selection_risk"] > part["selection_risk"].median(), "fixed_normalized_regret"]
        ci_low, ci_high = endpoint_bootstrap_spearman(part)
        rows.append(
            {
                "pool_size": label,
                "n_units": len(part),
                "spearman_rho": rho,
                "spearman_ci95_low": ci_low,
                "spearman_ci95_high": ci_high,
                "low_risk_half_regret": float(low.mean()),
                "high_risk_half_regret": float(high.mean()),
                "regret_ratio_low_over_high": float(low.mean() / high.mean()),
            }
        )
        curve = selection_risk_curve(part)
        curve.insert(0, "pool_size", label)
        curve_rows.append(curve)
    summary = pd.DataFrame(rows)
    curves = pd.concat(curve_rows, ignore_index=True)
    summary.to_csv(RESULTS / "selection_risk_summary.csv", index=False)
    curves.to_csv(RESULTS / "selection_risk_curve.csv", index=False)
    return {
        "overall_spearman": float(summary.loc[summary["pool_size"] == "all", "spearman_rho"].iloc[0]),
        "overall_spearman_ci95": [
            float(summary.loc[summary["pool_size"] == "all", "spearman_ci95_low"].iloc[0]),
            float(summary.loc[summary["pool_size"] == "all", "spearman_ci95_high"].iloc[0]),
        ],
        "low_risk_half_regret": float(summary.loc[summary["pool_size"] == "all", "low_risk_half_regret"].iloc[0]),
        "high_risk_half_regret": float(summary.loc[summary["pool_size"] == "all", "high_risk_half_regret"].iloc[0]),
    }


def load_candidate_utilities() -> tuple[pd.DataFrame, pd.DataFrame]:
    inner_parts = []
    outer_parts = []
    for seed_dir in sorted(REPEATED.glob("seed_*")):
        repeat_seed = int(seed_dir.name.split("_")[-1])
        inner = pd.read_csv(seed_dir / "inner_scores.csv")
        outer = pd.read_csv(seed_dir / "outer_candidate_scores.csv")
        inner["repeat_seed"] = repeat_seed
        outer["repeat_seed"] = repeat_seed
        inner_parts.append(inner)
        outer_parts.append(outer)
    inner = pd.concat(inner_parts, ignore_index=True)
    outer = pd.concat(outer_parts, ignore_index=True)
    inner_mean = (
        inner.groupby(["repeat_seed", "dataset", "outer_fold", "candidate_order", "candidate"], as_index=False)[
            "inner_utility"
        ].mean()
    )
    return inner_mean, outer


def run_null_calibration(n_permutations: int = 1000) -> dict[str, object]:
    inner, outer = load_candidate_utilities()
    observed_rank = pd.read_csv(NESTED / "repeated_ranking_metrics_long.csv")
    observed_regret = pd.read_csv(NESTED / "repeated_regret_decomposition.csv")
    observed = observed_rank.merge(
        observed_regret[
            ["endpoint", "repeat_seed", "outer_fold", "pool_size", "fixed_normalized_regret"]
        ],
        on=["endpoint", "repeat_seed", "outer_fold", "pool_size"],
        validate="one_to_one",
    )

    global_arrays: dict[int, dict[str, list[np.ndarray]]] = {
        k: {"hit": [], "regret": []} for k in (4, 8, 16, 32)
    }
    unit_rows = []
    for (seed, dataset, outer_fold), inner_unit in inner.groupby(
        ["repeat_seed", "dataset", "outer_fold"], sort=True
    ):
        outer_unit = outer.loc[
            (outer["repeat_seed"] == seed)
            & (outer["dataset"] == dataset)
            & (outer["outer_fold"] == outer_fold)
        ]
        merged = inner_unit.merge(
            outer_unit[["candidate_order", "candidate", "outer_utility"]],
            on=["candidate_order", "candidate"],
            validate="one_to_one",
        ).sort_values("candidate_order")
        for pool_size in (4, 8, 16, 32):
            unit = merged.iloc[:pool_size]
            null = permutation_null_for_unit(
                unit["inner_utility"].to_numpy(),
                unit["outer_utility"].to_numpy(),
                n_permutations=n_permutations,
                seed=stable_seed(seed, dataset, outer_fold, pool_size),
            )
            global_arrays[pool_size]["hit"].append(null["chance_adjusted_top3_hit"].to_numpy())
            global_arrays[pool_size]["regret"].append(null["fixed_normalized_regret"].to_numpy())
            unit_rows.append(
                {
                    "endpoint": dataset,
                    "repeat_seed": seed,
                    "outer_fold": outer_fold,
                    "pool_size": pool_size,
                    "null_chance_adjusted_hit_mean": float(null["chance_adjusted_top3_hit"].mean()),
                    "null_fixed_regret_mean": float(null["fixed_normalized_regret"].mean()),
                    "null_fixed_regret_ci95_low": float(null["fixed_normalized_regret"].quantile(0.025)),
                    "null_fixed_regret_ci95_high": float(null["fixed_normalized_regret"].quantile(0.975)),
                }
            )
    pd.DataFrame(unit_rows).to_csv(RESULTS / "null_calibration_units.csv", index=False)

    distribution_rows = []
    summary_rows = []
    for pool_size in (4, 8, 16, 32):
        hit_means = np.vstack(global_arrays[pool_size]["hit"]).mean(axis=0)
        regret_means = np.vstack(global_arrays[pool_size]["regret"]).mean(axis=0)
        for permutation, (hit, regret) in enumerate(zip(hit_means, regret_means, strict=True)):
            distribution_rows.append(
                {
                    "pool_size": pool_size,
                    "permutation": permutation,
                    "null_chance_adjusted_hit_mean": hit,
                    "null_fixed_regret_mean": regret,
                }
            )
        obs = observed.loc[observed["pool_size"] == pool_size]
        observed_hit = float(obs["chance_adjusted_hit"].mean())
        observed_regret_value = float(obs["fixed_normalized_regret"].mean())
        summary_rows.append(
            {
                "pool_size": pool_size,
                "n_outer_units": len(obs),
                "observed_chance_adjusted_hit": observed_hit,
                "null_chance_adjusted_hit_mean": float(hit_means.mean()),
                "null_chance_adjusted_hit_ci95_low": float(np.quantile(hit_means, 0.025)),
                "null_chance_adjusted_hit_ci95_high": float(np.quantile(hit_means, 0.975)),
                "p_hit_observed_le_null": float((1 + np.sum(hit_means >= observed_hit)) / (n_permutations + 1)),
                "observed_fixed_regret": observed_regret_value,
                "null_fixed_regret_mean": float(regret_means.mean()),
                "null_fixed_regret_ci95_low": float(np.quantile(regret_means, 0.025)),
                "null_fixed_regret_ci95_high": float(np.quantile(regret_means, 0.975)),
                "p_regret_observed_ge_null": float((1 + np.sum(regret_means <= observed_regret_value)) / (n_permutations + 1)),
            }
        )
    distribution = pd.DataFrame(distribution_rows)
    summary = pd.DataFrame(summary_rows)
    distribution.to_csv(RESULTS / "null_calibration_distribution.csv", index=False)
    summary.to_csv(RESULTS / "null_calibration_summary.csv", index=False)
    return {
        str(int(row.pool_size)): {
            "observed_chance_adjusted_hit": float(row.observed_chance_adjusted_hit),
            "null_chance_adjusted_hit_mean": float(row.null_chance_adjusted_hit_mean),
            "observed_fixed_regret": float(row.observed_fixed_regret),
            "null_fixed_regret_mean": float(row.null_fixed_regret_mean),
        }
        for row in summary.itertuples(index=False)
    }


def run_policy_transfer() -> dict[str, object]:
    governance = pd.read_csv(NESTED / "governance_ablation.csv")
    transfer = leave_one_endpoint_out_policy(governance)
    transfer["oracle_gap"] = transfer["heldout_regret"] - transfer["heldout_oracle_regret"]
    transfer["oracle_match"] = transfer["selected_variant"] == transfer["heldout_oracle_variant"]
    transfer.to_csv(RESULTS / "leave_one_endpoint_out_policy.csv", index=False)
    counts = transfer["selected_variant"].value_counts().to_dict()
    return {
        "n_endpoints": int(len(transfer)),
        "selected_variant_counts": {str(key): int(value) for key, value in counts.items()},
        "oracle_match_count": int(transfer["oracle_match"].sum()),
        "mean_heldout_regret": float(transfer["heldout_regret"].mean()),
        "mean_heldout_oracle_regret": float(transfer["heldout_oracle_regret"].mean()),
    }


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    values = {
        "selection_risk": run_selection_risk(),
        "null_calibration": run_null_calibration(),
        "policy_transfer": run_policy_transfer(),
    }
    (RESULTS / "selection_closure_values.json").write_text(
        json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(values, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
