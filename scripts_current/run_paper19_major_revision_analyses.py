from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import digamma
from sklearn.covariance import LedoitWolf


ROOT = Path("D:/fzyc")
BASE = ROOT / "results" / "nested_selection" / "repeated_nested"
MULTI = ROOT / "results" / "reviewer_core_20260624" / "multiview_nested"
PREV = ROOT / "output" / "paper19_rejection_driven_experiments_20260712"
OUT = ROOT / "output" / "paper19_major_revision_20260712"
SEEDS = [11, 23, 37, 53, 71]
KS = [4, 8, 16, 32]
RNG_SEED = 20260712
N_HIER = 500
N_BOOT = 10000


def load_seed_csv(name: str) -> pd.DataFrame:
    frames = []
    for seed in SEEDS:
        frame = pd.read_csv(BASE / f"seed_{seed}" / name).rename(columns={"dataset": "task"})
        frame.insert(0, "seed", seed)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def corr_from_cov(cov: np.ndarray) -> np.ndarray:
    scale = np.sqrt(np.clip(np.diag(cov), 1e-15, None))
    corr = cov / np.outer(scale, scale)
    corr = np.clip(corr, -1.0, 1.0)
    np.fill_diagonal(corr, 1.0)
    return corr


def rank_metrics(corr: np.ndarray) -> dict[str, float]:
    eig = np.clip(np.linalg.eigvalsh(corr), 0.0, None)
    total = float(eig.sum())
    p = eig / total if total > 0 else np.ones_like(eig) / len(eig)
    p = p[p > 1e-15]
    entropy = float(np.exp(-(p * np.log(p)).sum()))
    participation = float(total * total / np.square(eig).sum())
    off = corr[np.triu_indices_from(corr, k=1)]
    return {
        "entropy_effective_rank": entropy,
        "participation_effective_rank": participation,
        "median_pairwise_correlation": float(np.median(off)),
    }


def matrix_metrics(x: np.ndarray, shrinkage: bool) -> dict[str, float]:
    x = np.asarray(x, dtype=float)
    if x.shape[1] == 1:
        return {
            "entropy_effective_rank": 1.0,
            "participation_effective_rank": 1.0,
            "median_pairwise_correlation": 1.0,
        }
    if shrinkage:
        sd = x.std(axis=0, ddof=1)
        sd[~np.isfinite(sd) | (sd < 1e-12)] = 1.0
        z = (x - x.mean(axis=0)) / sd
        corr = corr_from_cov(LedoitWolf(assume_centered=False).fit(z).covariance_)
    else:
        corr = np.corrcoef(x, rowvar=False)
        corr = np.nan_to_num(corr, nan=0.0)
        np.fill_diagonal(corr, 1.0)
    return rank_metrics(corr)


def hierarchical_rows(frame: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
    rows = []
    sampled_seeds = rng.choice(SEEDS, size=len(SEEDS), replace=True)
    for seed in sampled_seeds:
        unit = frame.loc[frame["seed"].eq(seed)]
        idx = rng.choice(unit.index.to_numpy(), size=3, replace=True)
        rows.append(unit.loc[idx].drop(columns=["seed", "outer_fold"]).to_numpy(float))
    return np.vstack(rows)


def effective_diversity(outer: pd.DataFrame, inner: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(RNG_SEED)
    point_rows: list[dict[str, object]] = []
    sensitivity_rows: list[dict[str, object]] = []
    boot_rows: list[dict[str, object]] = []
    for task in sorted(outer["task"].unique()):
        task_type = str(outer.loc[outer["task"].eq(task), "task_type"].iloc[0])
        for k in KS:
            o = outer.loc[outer["task"].eq(task) & outer["candidate_order"].le(k)].pivot_table(
                index=["seed", "outer_fold"], columns="candidate_order", values="outer_utility"
            ).reset_index()
            i = inner.loc[inner["task"].eq(task) & inner["candidate_order"].le(k)].pivot_table(
                index=["seed", "outer_fold", "inner_fold"], columns="candidate_order", values="inner_utility"
            )
            empirical = matrix_metrics(o.drop(columns=["seed", "outer_fold"]).to_numpy(float), False)
            shrink = matrix_metrics(o.drop(columns=["seed", "outer_fold"]).to_numpy(float), True)
            inner_shrink = matrix_metrics(i.to_numpy(float), True)
            draws = {key: np.empty(N_HIER, dtype=float) for key in shrink}
            for b in range(N_HIER):
                metrics = matrix_metrics(hierarchical_rows(o, rng), True)
                for key, value in metrics.items():
                    draws[key][b] = value
            row: dict[str, object] = {
                "task": task,
                "task_type": task_type,
                "candidate_count": k,
                "outer_matrix_rows": 15,
                "outer_matrix_columns": k,
                "inner_matrix_rows": 45,
                "inner_matrix_columns": k,
                **{f"empirical_outer_{key}": value for key, value in empirical.items()},
                **{f"shrinkage_outer_{key}": value for key, value in shrink.items()},
                **{f"shrinkage_inner_{key}": value for key, value in inner_shrink.items()},
            }
            for key, values in draws.items():
                row[f"hierarchical_ci95_low_{key}"] = float(np.quantile(values, 0.025))
                row[f"hierarchical_ci95_high_{key}"] = float(np.quantile(values, 0.975))
            point_rows.append(row)
            if k == 32:
                for omitted in SEEDS:
                    x = o.loc[~o["seed"].eq(omitted)].drop(columns=["seed", "outer_fold"]).to_numpy(float)
                    m = matrix_metrics(x, True)
                    sensitivity_rows.append({"task": task, "omission_type": "seed", "omitted": omitted, **m})
                for omitted in [1, 2, 3]:
                    x = o.loc[~o["outer_fold"].eq(omitted)].drop(columns=["seed", "outer_fold"]).to_numpy(float)
                    m = matrix_metrics(x, True)
                    sensitivity_rows.append({"task": task, "omission_type": "outer_fold", "omitted": omitted, **m})
            for b in range(N_HIER):
                boot_rows.append(
                    {
                        "task": task,
                        "candidate_count": k,
                        "bootstrap": b,
                        "entropy_effective_rank": draws["entropy_effective_rank"][b],
                        "participation_effective_rank": draws["participation_effective_rank"][b],
                        "median_pairwise_correlation": draws["median_pairwise_correlation"][b],
                    }
                )
    point = pd.DataFrame(point_rows)
    sensitivity = pd.DataFrame(sensitivity_rows)
    boot = pd.DataFrame(boot_rows)
    summary_rows = []
    for k, group in point.groupby("candidate_count"):
        b = boot.loc[boot["candidate_count"].eq(k)].groupby("bootstrap").agg(
            entropy=("entropy_effective_rank", "mean"),
            participation=("participation_effective_rank", "mean"),
            correlation=("median_pairwise_correlation", "mean"),
        )
        summary_rows.append(
            {
                "candidate_count": k,
                "n_endpoints": len(group),
                "mean_shrinkage_entropy_rank": group["shrinkage_outer_entropy_effective_rank"].mean(),
                "hierarchical_ci95_low_entropy": b["entropy"].quantile(0.025),
                "hierarchical_ci95_high_entropy": b["entropy"].quantile(0.975),
                "mean_shrinkage_participation_rank": group["shrinkage_outer_participation_effective_rank"].mean(),
                "hierarchical_ci95_low_participation": b["participation"].quantile(0.025),
                "hierarchical_ci95_high_participation": b["participation"].quantile(0.975),
                "mean_shrinkage_median_correlation": group["shrinkage_outer_median_pairwise_correlation"].mean(),
                "hierarchical_ci95_low_correlation": b["correlation"].quantile(0.025),
                "hierarchical_ci95_high_correlation": b["correlation"].quantile(0.975),
            }
        )
    return point, sensitivity, pd.DataFrame(summary_rows)


def harmonic_number(k: int) -> float:
    return float(digamma(k + 1) + np.euler_gamma)


def ranking_metrics() -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = pd.read_csv(ROOT / "results" / "nested_selection" / "repeated_ranking_metrics_long.csv")
    frame = frame.loc[frame["status"].eq("completed") & frame["pool_size"].isin(KS)].copy()
    frame = frame.rename(columns={"endpoint": "task", "repeat_seed": "seed"})
    frame["mrr_random_expectation"] = frame["candidate_count"].map(lambda k: harmonic_number(int(k)) / int(k))
    frame["normalized_mrr_gain"] = (
        frame["mrr"] - frame["mrr_random_expectation"]
    ) / (1.0 - frame["mrr_random_expectation"])
    frame["chance_adjusted_top3"] = frame["chance_adjusted_hit"]
    metric_cols = [
        "chance_adjusted_top3",
        "normalized_mrr_gain",
        "rank_percentile",
        "ndcg",
        "spearman",
        "kendall",
        "top1_hit",
        "mrr",
    ]
    endpoint = frame.groupby(["task", "candidate_count"], as_index=False)[metric_cols].mean()
    rng = np.random.default_rng(RNG_SEED + 1)
    summary_rows = []
    for k, group in endpoint.groupby("candidate_count"):
        row: dict[str, object] = {"candidate_count": k, "n_endpoints": len(group)}
        for metric in metric_cols:
            values = group[metric].to_numpy(float)
            draws = rng.choice(values, size=(N_BOOT, len(values)), replace=True).mean(axis=1)
            row[f"mean_{metric}"] = float(values.mean())
            row[f"endpoint_bootstrap_ci95_low_{metric}"] = float(np.quantile(draws, 0.025))
            row[f"endpoint_bootstrap_ci95_high_{metric}"] = float(np.quantile(draws, 0.975))
        summary_rows.append(row)
    return frame, pd.DataFrame(summary_rows)


def seed_clustered_selection_loss() -> pd.DataFrame:
    paired = pd.read_csv(PREV / "paper19_k32_vs_k4_paired_units.csv")
    paired = paired.loc[paired["policy"].eq("validation_best")].copy()
    rng = np.random.default_rng(RNG_SEED + 2)
    rows = []
    for (task, task_type), group in paired.groupby(["task", "task_type"]):
        seed_means = group.groupby("seed")["delta_raw_selection_loss_k32_minus_k4"].mean().reindex(SEEDS)
        draws = rng.choice(seed_means.to_numpy(float), size=(N_BOOT, len(SEEDS)), replace=True).mean(axis=1)
        loo = [seed_means.drop(index=seed).mean() for seed in SEEDS]
        old = pd.read_csv(PREV / "paper19_k32_vs_k4_endpoint_effects.csv")
        old = old.loc[(old["task"].eq(task)) & old["policy"].eq("validation_best")].iloc[0]
        rows.append(
            {
                "task": task,
                "task_type": task_type,
                "effect_scale": "ROC-AUC loss" if task_type == "classification" else "RMSE loss",
                "mean_delta": seed_means.mean(),
                "seed_clustered_ci95_low": float(np.quantile(draws, 0.025)),
                "seed_clustered_ci95_high": float(np.quantile(draws, 0.975)),
                "fold_bootstrap_ci95_low": old["ci95_low"],
                "fold_bootstrap_ci95_high": old["ci95_high"],
                "positive_seed_means": int((seed_means > 0).sum()),
                "leave_one_seed_out_min": float(min(loo)),
                "leave_one_seed_out_max": float(max(loo)),
            }
        )
    return pd.DataFrame(rows)


def multiview_absolute() -> tuple[pd.DataFrame, pd.DataFrame]:
    policy = pd.read_csv(MULTI / "policy_detail.csv")
    use = policy.loc[
        policy["policy"].eq("validation_best")
        & policy["variant"].isin(["morgan_only", "full_multiview"])
    ].copy()
    wide = use.pivot_table(
        index=["task", "task_type", "seed", "outer_fold"],
        columns="variant",
        values="outer_utility",
    ).reset_index()
    wide["raw_gain"] = wide["full_multiview"] - wide["morgan_only"]
    paired = pd.read_csv(MULTI / "paired_multiview_effects_long.csv")
    norm = paired.loc[
        paired["comparison"].eq("realized multiview validation-best gain vs Morgan-only")
    ][["task", "seed", "outer_fold", "normalized_utility_gain", "full_utility_range"]]
    wide = wide.merge(norm, on=["task", "seed", "outer_fold"], how="left")
    reps = use.loc[use["variant"].eq("full_multiview")]
    rng = np.random.default_rng(RNG_SEED + 3)
    rows = []
    for (task, task_type), group in wide.groupby(["task", "task_type"]):
        seed_means = group.groupby("seed")["raw_gain"].mean().reindex(SEEDS)
        draws = rng.choice(seed_means.to_numpy(float), size=(N_BOOT, len(SEEDS)), replace=True).mean(axis=1)
        selected = reps.loc[reps["task"].eq(task), "selected_representation"]
        mode = selected.value_counts().index[0]
        morgan_perf = group["morgan_only"].mean()
        full_perf = group["full_multiview"].mean()
        if task_type == "regression":
            morgan_perf = -morgan_perf
            full_perf = -full_perf
            scale = "RMSE reduction"
        else:
            scale = "ROC-AUC gain"
        rows.append(
            {
                "task": task,
                "task_type": task_type,
                "performance_metric": "RMSE" if task_type == "regression" else "ROC-AUC",
                "morgan_only_selected_performance": morgan_perf,
                "full_multiview_selected_performance": full_perf,
                "raw_gain_definition": scale,
                "mean_raw_paired_gain": seed_means.mean(),
                "seed_clustered_ci95_low": float(np.quantile(draws, 0.025)),
                "seed_clustered_ci95_high": float(np.quantile(draws, 0.975)),
                "positive_paired_units": int((group["raw_gain"] > 0).sum()),
                "mean_normalized_gain": group["normalized_utility_gain"].mean(),
                "median_full_pool_utility_range": group["full_utility_range"].median(),
                "most_selected_representation": mode,
                "most_selected_representation_count": int((selected == mode).sum()),
            }
        )
    return wide, pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    inner = load_seed_csv("inner_scores.csv")
    outer = load_seed_csv("outer_candidate_scores.csv")
    diversity, sensitivity, diversity_summary = effective_diversity(outer, inner)
    ranking_units, ranking_summary = ranking_metrics()
    loss = seed_clustered_selection_loss()
    multiview_units, multiview = multiview_absolute()
    outputs = {
        "effective_diversity_shrinkage_endpoint.csv": diversity,
        "effective_diversity_k32_omission_sensitivity.csv": sensitivity,
        "effective_diversity_shrinkage_summary.csv": diversity_summary,
        "chance_adjusted_ranking_units.csv": ranking_units,
        "chance_adjusted_ranking_summary.csv": ranking_summary,
        "selection_loss_seed_clustered.csv": loss,
        "multiview_absolute_paired_units.csv": multiview_units,
        "multiview_absolute_endpoint_summary.csv": multiview,
    }
    for name, frame in outputs.items():
        frame.to_csv(OUT / name, index=False)
    audit = {
        "bootstrap": {"hierarchical_effective_rank": N_HIER, "endpoint_or_seed_clustered": N_BOOT},
        "effective_rank_matrix": {
            "outer": "15 rows (5 seeds x 3 outer folds) by K candidate utilities per endpoint",
            "inner": "45 rows (5 seeds x 3 outer folds x 3 inner folds) by K candidate utilities per endpoint",
            "estimator": "Ledoit-Wolf shrinkage covariance converted to correlation",
        },
        "unavailable": [
            "K=32 prediction-matrix effective rank: all-candidate per-sample predictions were not exported",
            "independent external confirmation",
        ],
        "interpretive_limits": [
            "Outer-fold and seed replicates quantify design sensitivity but are not independent biological or task-level replicates.",
            "Multiview gains compare frozen selectors and include the additional selection opportunity of the full pool.",
        ],
    }
    (OUT / "major_revision_analysis_audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print({name: len(frame) for name, frame in outputs.items()})


if __name__ == "__main__":
    main()
