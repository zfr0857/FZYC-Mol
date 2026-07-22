# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "reports" / "formal_fixed_selector_integration_20260603" / "integrated_candidate_metrics.csv"
OUT_DIR = ROOT / "reports" / "draft8_14k_revision"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CORE_ENDPOINTS = [
    ("esol", "rmse"),
    ("freesolv", "rmse"),
    ("lipo", "rmse"),
    ("bbbp", "roc_auc"),
    ("bace", "roc_auc"),
    ("clintox", "roc_auc"),
    ("caco2_wang", "rmse"),
    ("hia_hou", "roc_auc"),
    ("pgp_broccatelli", "roc_auc"),
]
POOL_SIZES = [4, 8, 16, 32]

TYPE_PRIORITY = {
    "single_regressor": 0,
    "single_classifier": 0,
    "single_view_expert": 1,
    "embedding_head": 2,
    "undersampling_ensemble": 3,
    "topk_mean": 4,
    "validation_stacking": 5,
    "prediction_level_fusion": 6,
    "": 7,
    "nan": 7,
}
SOURCE_PRIORITY = {
    "moleculenet_targeted_rebuild": 0,
    "tdc_performance_mode": 0,
    "moleculenet_nature_fusion": 1,
    "tdc_nature_fusion": 1,
    "three_d_roughness_regression": 2,
}


def canonical_type(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def utility(values: pd.Series | np.ndarray, direction: str) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    return arr if direction == "higher" else -arr


def prepare_endpoint(raw: pd.DataFrame, dataset: str, metric: str) -> pd.DataFrame:
    sub = raw[
        raw["canonical_dataset"].eq(dataset)
        & raw["primary_metric"].eq(metric)
        & np.isfinite(raw["validation_primary"])
        & np.isfinite(raw["primary_value"])
    ].copy()
    if sub.empty:
        raise ValueError(f"No candidate rows for {dataset}/{metric}")

    # Some historical runs were imported twice with identical validation/test
    # values but slightly different wall-clock measurements. Keep the fastest
    # duplicate so each registered candidate contributes one row per seed.
    sub = (
        sub.sort_values(["model", "seed", "fit_seconds"], kind="stable")
        .drop_duplicates(["model", "seed"], keep="first")
        .reset_index(drop=True)
    )

    n_seeds = sub["seed"].nunique()
    complete = sub.groupby("model")["seed"].nunique()
    keep = complete[complete.eq(n_seeds)].index
    sub = sub[sub["model"].isin(keep)].copy()
    sub["candidate_type"] = sub["candidate_type"].map(canonical_type)
    sub["type_priority"] = sub["candidate_type"].map(TYPE_PRIORITY).fillna(7).astype(int)
    sub["source_priority"] = sub["source"].map(SOURCE_PRIORITY).fillna(9).astype(int)

    registry = (
        sub[["model", "candidate_type", "source", "type_priority", "source_priority"]]
        .drop_duplicates("model")
        .sort_values(["type_priority", "source_priority", "model"], kind="stable")
        .reset_index(drop=True)
    )
    registry["registry_order"] = np.arange(1, len(registry) + 1)
    sub = sub.merge(registry[["model", "registry_order"]], on="model", how="left")
    sub["validation_utility"] = utility(sub["validation_primary"], str(sub["primary_direction"].iloc[0]))
    sub["test_utility"] = utility(sub["primary_value"], str(sub["primary_direction"].iloc[0]))
    return sub


def summarize_selection(
    pool: pd.DataFrame,
    policy: str,
    rng: np.random.Generator,
) -> tuple[pd.DataFrame, str]:
    seeds = sorted(pool["seed"].unique())
    models = sorted(pool["model"].unique())
    direction = str(pool["primary_direction"].iloc[0])

    if policy == "fixed_single":
        selected_model = (
            pool[["model", "registry_order"]]
            .drop_duplicates("model")
            .sort_values(["registry_order", "model"])
            .iloc[0]["model"]
        )
        chosen = pool[pool["model"].eq(selected_model)].copy()
        label = str(selected_model)
    elif policy == "one_se_stable":
        stats = (
            pool.groupby("model", as_index=False)
            .agg(
                validation_mean=("validation_utility", "mean"),
                validation_sd=("validation_utility", "std"),
                fit_seconds=("fit_seconds", "mean"),
                registry_order=("registry_order", "first"),
            )
            .fillna({"validation_sd": 0.0})
        )
        best = stats.sort_values(["validation_mean", "model"], ascending=[False, True]).iloc[0]
        se = float(best["validation_sd"]) / math.sqrt(max(1, len(seeds)))
        eligible = stats[stats["validation_mean"] >= float(best["validation_mean"]) - se].copy()
        selected_model = eligible.sort_values(
            ["validation_sd", "fit_seconds", "registry_order", "model"],
            ascending=[True, True, True, True],
        ).iloc[0]["model"]
        chosen = pool[pool["model"].eq(selected_model)].copy()
        label = str(selected_model)
    elif policy == "risk_adjusted":
        stats = (
            pool.groupby("model", as_index=False)
            .agg(
                validation_mean=("validation_utility", "mean"),
                validation_sd=("validation_utility", "std"),
                fit_seconds=("fit_seconds", "mean"),
                registry_order=("registry_order", "first"),
            )
            .fillna({"validation_sd": 0.0})
        )
        stats["score"] = stats["validation_mean"] - 0.5 * stats["validation_sd"]
        selected_model = stats.sort_values(
            ["score", "fit_seconds", "registry_order", "model"],
            ascending=[False, True, True, True],
        ).iloc[0]["model"]
        chosen = pool[pool["model"].eq(selected_model)].copy()
        label = str(selected_model)
    elif policy == "validation_best":
        chosen = (
            pool.sort_values(["seed", "validation_utility", "model"], ascending=[True, False, True])
            .groupby("seed", as_index=False)
            .head(1)
            .copy()
        )
        label = ";".join(f"{m}:{n}" for m, n in chosen["model"].value_counts().items())
    elif policy == "random_expected":
        chosen = (
            pool.groupby("seed", as_index=False)
            .agg(
                validation_utility=("validation_utility", "mean"),
                test_utility=("test_utility", "mean"),
                validation_primary=("validation_primary", "mean"),
                primary_value=("primary_value", "mean"),
            )
        )
        chosen["model"] = "random expectation"
        label = "random expectation"
    elif policy == "test_oracle":
        chosen = (
            pool.sort_values(["seed", "test_utility", "model"], ascending=[True, False, True])
            .groupby("seed", as_index=False)
            .head(1)
            .copy()
        )
        label = ";".join(f"{m}:{n}" for m, n in chosen["model"].value_counts().items())
    else:
        raise ValueError(policy)

    chosen = chosen.sort_values("seed").reset_index(drop=True)
    if len(chosen) != len(seeds):
        raise ValueError(f"{policy} returned {len(chosen)} rows for {len(seeds)} seeds")
    return chosen, label


def family_selector(pool: pd.DataFrame, candidate_type: str) -> tuple[pd.DataFrame, str] | None:
    family = pool[pool["candidate_type"].eq(candidate_type)].copy()
    if family.empty or family["seed"].nunique() != pool["seed"].nunique():
        return None
    chosen = (
        family.sort_values(["seed", "validation_utility", "model"], ascending=[True, False, True])
        .groupby("seed", as_index=False)
        .head(1)
        .copy()
    )
    if len(chosen) != pool["seed"].nunique():
        return None
    label = ";".join(f"{m}:{n}" for m, n in chosen["model"].value_counts().items())
    return chosen, label


def evaluate_policy(
    pool: pd.DataFrame,
    chosen: pd.DataFrame,
    dataset: str,
    metric: str,
    pool_size: int,
    policy: str,
    selected_label: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for seed, seed_pool in pool.groupby("seed"):
        row = chosen[chosen["seed"].eq(seed)].iloc[0]
        test_values = seed_pool["test_utility"].to_numpy(dtype=float)
        valid_values = seed_pool["validation_utility"].to_numpy(dtype=float)
        oracle = float(np.max(test_values))
        worst = float(np.min(test_values))
        scale = max(oracle - worst, 1e-8)
        test_utility = float(row["test_utility"])
        validation_utility = float(row["validation_utility"])
        validation_ranked = seed_pool.sort_values(["validation_utility", "model"], ascending=[False, True])
        test_oracle_model = seed_pool.sort_values(["test_utility", "model"], ascending=[False, True]).iloc[0]["model"]
        top3_hit = int(test_oracle_model in set(validation_ranked.head(3)["model"]))
        rows.append(
            {
                "dataset": dataset,
                "primary_metric": metric,
                "task_type": str(pool["task_type"].iloc[0]),
                "primary_direction": str(pool["primary_direction"].iloc[0]),
                "seed": int(seed),
                "pool_size": int(pool_size),
                "policy": policy,
                "selected_model": str(row.get("model", selected_label)),
                "selected_model_summary": selected_label,
                "validation_utility": validation_utility,
                "test_utility": test_utility,
                "test_oracle_utility": oracle,
                "test_regret_native": oracle - test_utility,
                "normalized_test_regret": (oracle - test_utility) / scale,
                "optimism_gap_native": validation_utility - test_utility,
                "normalized_optimism_gap": (validation_utility - test_utility) / scale,
                "top3_hit": top3_hit,
                "candidate_count": int(seed_pool["model"].nunique()),
            }
        )
    return rows


def main() -> None:
    raw = pd.read_csv(INPUT)
    rng = np.random.default_rng(20260621)
    detail_rows: list[dict[str, object]] = []
    registry_rows: list[pd.DataFrame] = []

    for dataset, metric in CORE_ENDPOINTS:
        endpoint = prepare_endpoint(raw, dataset, metric)
        registry = (
            endpoint[["model", "candidate_type", "source", "registry_order"]]
            .drop_duplicates("model")
            .sort_values("registry_order")
            .copy()
        )
        registry.insert(0, "dataset", dataset)
        registry.insert(1, "primary_metric", metric)
        registry_rows.append(registry)

        for pool_size in POOL_SIZES:
            pool = endpoint[endpoint["registry_order"] <= pool_size].copy()
            if pool["model"].nunique() < pool_size:
                raise ValueError(f"{dataset}/{metric} has only {pool['model'].nunique()} models at K={pool_size}")
            for policy in ["fixed_single", "validation_best", "one_se_stable", "risk_adjusted", "random_expected", "test_oracle"]:
                chosen, label = summarize_selection(pool, policy, rng)
                detail_rows.extend(evaluate_policy(pool, chosen, dataset, metric, pool_size, policy, label))

            if pool_size == max(POOL_SIZES):
                for candidate_type, policy in [("topk_mean", "topk_family"), ("validation_stacking", "stacking_family")]:
                    result = family_selector(pool, candidate_type)
                    if result is not None:
                        chosen, label = result
                        detail_rows.extend(evaluate_policy(pool, chosen, dataset, metric, pool_size, policy, label))

    detail = pd.DataFrame(detail_rows)
    detail.to_csv(OUT_DIR / "candidate_pool_stress_detail.csv", index=False)
    pd.concat(registry_rows, ignore_index=True).to_csv(OUT_DIR / "candidate_registry_order.csv", index=False)

    summary = (
        detail.groupby(["pool_size", "policy"], as_index=False)
        .agg(
            n_endpoint_seeds=("normalized_test_regret", "size"),
            n_endpoints=("dataset", "nunique"),
            normalized_regret_mean=("normalized_test_regret", "mean"),
            normalized_regret_median=("normalized_test_regret", "median"),
            normalized_regret_sd=("normalized_test_regret", "std"),
            optimism_gap_mean=("normalized_optimism_gap", "mean"),
            optimism_gap_median=("normalized_optimism_gap", "median"),
            top3_hit_rate=("top3_hit", "mean"),
        )
    )
    summary["regret_sem"] = summary["normalized_regret_sd"] / np.sqrt(summary["n_endpoint_seeds"])
    summary["regret_ci95_low"] = summary["normalized_regret_mean"] - 1.96 * summary["regret_sem"]
    summary["regret_ci95_high"] = summary["normalized_regret_mean"] + 1.96 * summary["regret_sem"]
    summary.to_csv(OUT_DIR / "candidate_pool_stress_summary.csv", index=False)

    stability = (
        detail[detail["policy"].isin(["validation_best", "one_se_stable", "risk_adjusted"])]
        .groupby(["dataset", "primary_metric", "pool_size", "policy"])
        .agg(
            n_seeds=("seed", "nunique"),
            n_selected_models=("selected_model", "nunique"),
            modal_selection_rate=("selected_model", lambda s: float(s.value_counts(normalize=True).iloc[0])),
        )
        .reset_index()
    )
    stability.to_csv(OUT_DIR / "candidate_pool_selection_stability.csv", index=False)

    benchmark = summary[summary["pool_size"].eq(max(POOL_SIZES))].copy()
    benchmark.to_csv(OUT_DIR / "selector_benchmark_summary.csv", index=False)

    print(summary.to_string(index=False))
    print("\nSelection stability\n", stability.groupby(["pool_size", "policy"])["modal_selection_rate"].mean().to_string())


if __name__ == "__main__":
    main()
