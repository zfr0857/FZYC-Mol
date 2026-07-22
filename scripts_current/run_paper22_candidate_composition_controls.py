from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import digamma


ROOT = Path("D:/fzyc")
sys.path.insert(0, str(ROOT / "src"))

from fzyc_mol.reporting.stage_c import build_stage_c_outputs  # noqa: E402
from fzyc_mol.selection.candidate_pool_audit import (  # noqa: E402
    audit_candidate_pool_summary,
    summarize_validation_scores,
)


PREFIX = Path(
    os.environ.get(
        "FZYC_PREFIX_BASE",
        ROOT / "results" / "paper22_combined_nested_20260713" / "prefix32",
    )
)
OUT = Path(
    os.environ.get(
        "FZYC_ANALYSIS_OUT",
        ROOT / "output" / "paper22_major_revision_20260713",
    )
)
SEEDS = (11, 23, 37, 53, 71)


def registered_prefix_ranking(
    split_seed: int,
    inner_scores: pd.DataFrame,
    outer_scores: pd.DataFrame,
    registry: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for endpoint, reg in registry.groupby("dataset", sort=True):
        reg = reg.sort_values("candidate_order", kind="stable")
        task_type = str(reg["task_type"].iloc[0])
        all_ids = reg["candidate"].astype(str).tolist()
        baseline_id = all_ids[0]
        for outer_fold in sorted(
            outer_scores.loc[outer_scores["dataset"].eq(endpoint), "outer_fold"].unique()
        ):
            inner = inner_scores[
                inner_scores["dataset"].eq(endpoint)
                & inner_scores["outer_fold"].eq(outer_fold)
            ].rename(columns={"candidate": "candidate_id", "inner_utility": "val_utility"})
            cache = summarize_validation_scores(inner, all_ids)
            outer = outer_scores[
                outer_scores["dataset"].eq(endpoint)
                & outer_scores["outer_fold"].eq(outer_fold)
            ]
            outer_map = dict(
                zip(outer["candidate"].astype(str), outer["outer_utility"].astype(float), strict=True)
            )
            for pool_size in (4, 8, 16, 32):
                pool_ids = all_ids[:pool_size]
                audit = audit_candidate_pool_summary(
                    cache,
                    outer_map,
                    full_test_utility=outer_map,
                    pool_candidate_ids=pool_ids,
                    baseline_id=baseline_id,
                    task_type=task_type,
                    n_inner=int(inner["inner_fold"].nunique()),
                )
                if audit.status != "completed" or audit.ranking is None:
                    raise RuntimeError(
                        f"registered-prefix ranking failed: {endpoint}, seed {split_seed}, "
                        f"outer {outer_fold}, K={pool_size}"
                    )
                rank = dict(audit.ranking)
                random_mrr = float((digamma(pool_size + 1) + np.euler_gamma) / pool_size)
                rank["normalized_mrr_gain"] = (
                    float(rank["mrr"]) - random_mrr
                ) / (1.0 - random_mrr)
                rows.append(
                    {
                        "task": endpoint,
                        "task_type": task_type,
                        "split_seed": split_seed,
                        "outer_fold": int(outer_fold),
                        "candidate_count": pool_size,
                        **rank,
                    }
                )
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ranking_frames: list[pd.DataFrame] = []
    regret_frames: list[pd.DataFrame] = []
    decision_frames: list[pd.DataFrame] = []
    manifest_frames: list[pd.DataFrame] = []
    registered_frames: list[pd.DataFrame] = []

    for split_seed in SEEDS:
        source = PREFIX / f"seed_{split_seed}"
        inner_scores = pd.read_csv(source / "inner_scores.csv")
        outer_scores = pd.read_csv(source / "outer_candidate_scores.csv")
        registry = pd.read_csv(source / "candidate_registry.csv")
        registered_frames.append(
            registered_prefix_ranking(split_seed, inner_scores, outer_scores, registry)
        )
        manifest, ranking, regret, decisions = build_stage_c_outputs(
            inner_scores,
            outer_scores,
            registry,
            modes=("random_order", "random_subset", "family_balanced"),
            pool_sizes=(4, 8, 16, 32),
            seeds=tuple(range(100)),
        )
        for frame in (manifest, ranking, regret, decisions):
            frame.insert(0, "split_seed", split_seed)
            if "split_id" in frame.columns:
                frame["split_id"] = (
                    frame["endpoint"].astype(str)
                    + f":seed{split_seed}:outer"
                    + frame["outer_fold"].astype(str)
                )
        manifest_frames.append(manifest)
        ranking_frames.append(ranking)
        regret_frames.append(regret)
        decision_frames.append(decisions)
        print(f"candidate-composition controls complete: split seed {split_seed}", flush=True)

    manifest_all = pd.concat(manifest_frames, ignore_index=True)
    ranking_all = pd.concat(ranking_frames, ignore_index=True)
    regret_all = pd.concat(regret_frames, ignore_index=True)
    decision_all = pd.concat(decision_frames, ignore_index=True)
    registered = pd.concat(registered_frames, ignore_index=True)

    endpoint_registered = (
        registered.groupby(["task", "candidate_count"], as_index=False)
        .agg(
            chance_adjusted_top3=("chance_adjusted_hit", "mean"),
            normalized_mrr_gain=("normalized_mrr_gain", "mean"),
            ndcg=("ndcg", "mean"),
            spearman=("spearman", "mean"),
            kendall=("kendall", "mean"),
            rank_percentile=("rank_percentile", "mean"),
        )
    )
    registered_summary = (
        endpoint_registered.groupby("candidate_count", as_index=False)
        .agg(
            n_endpoints=("task", "nunique"),
            mean_chance_adjusted_top3=("chance_adjusted_top3", "mean"),
            mean_normalized_mrr_gain=("normalized_mrr_gain", "mean"),
            mean_ndcg=("ndcg", "mean"),
            mean_spearman=("spearman", "mean"),
            mean_kendall=("kendall", "mean"),
            mean_rank_percentile=("rank_percentile", "mean"),
        )
    )

    summary = (
        ranking_all.groupby(["mode", "pool_size"], as_index=False)
        .agg(
            n_endpoints=("endpoint", "nunique"),
            n_split_seeds=("split_seed", "nunique"),
            n_outer_subset_units=("chance_adjusted_hit", "size"),
            chance_adjusted_hit_mean=("chance_adjusted_hit", "mean"),
            chance_adjusted_hit_median=("chance_adjusted_hit", "median"),
            mrr_mean=("mrr", "mean"),
            ndcg_mean=("ndcg", "mean"),
            spearman_mean=("spearman", "mean"),
            kendall_mean=("kendall", "mean"),
            rank_percentile_mean=("rank_percentile", "mean"),
        )
        .sort_values(["mode", "pool_size"])
    )
    registered_control = registered_summary.rename(
        columns={
            "candidate_count": "pool_size",
            "mean_chance_adjusted_top3": "chance_adjusted_hit_mean",
            "mean_normalized_mrr_gain": "normalized_mrr_gain",
            "mean_ndcg": "ndcg_mean",
            "mean_spearman": "spearman_mean",
            "mean_kendall": "kendall_mean",
            "mean_rank_percentile": "rank_percentile_mean",
        }
    )
    registered_control.insert(0, "mode", "registered_prefix")
    registered_control["n_split_seeds"] = len(SEEDS)
    registered_control["n_outer_subset_units"] = len(SEEDS) * 3 * registered_control["n_endpoints"]
    registered_control["chance_adjusted_hit_median"] = np.nan
    registered_control["mrr_mean"] = np.nan
    summary = pd.concat([summary, registered_control], ignore_index=True, sort=False).sort_values(
        ["mode", "pool_size"]
    )
    summary.to_csv(OUT / "candidate_composition_controls.csv", index=False)
    registered.to_csv(OUT / "chance_adjusted_ranking_units.csv", index=False)
    registered_summary.to_csv(OUT / "chance_adjusted_ranking_summary.csv", index=False)
    manifest_all.to_csv(OUT / "candidate_composition_subset_manifest.csv.gz", index=False, compression="gzip")
    ranking_all.to_csv(OUT / "candidate_composition_ranking_units.csv.gz", index=False, compression="gzip")
    regret_all.to_csv(OUT / "candidate_composition_regret_units.csv.gz", index=False, compression="gzip")
    decision_all.to_csv(OUT / "candidate_composition_decisions.csv.gz", index=False, compression="gzip")
    print(summary.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
