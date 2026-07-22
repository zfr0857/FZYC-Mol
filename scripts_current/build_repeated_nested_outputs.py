from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fzyc_mol.reporting.stage_b import build_stage_b_outputs  # noqa: E402
from fzyc_mol.selection.stability_metrics import mean_pairwise_jaccard, selection_stability  # noqa: E402


def build_outputs(
    root: Path = ROOT,
    *,
    seeds: Sequence[int] = (11, 23, 37, 53, 71),
    pool_sizes: Sequence[int] = (4, 8, 16, 32),
) -> dict[str, Path]:
    repeat_root = root / "results" / "nested_selection" / "repeated_nested"
    ranking_frames = []
    regret_frames = []
    decision_frames = []
    registry_frames = []
    for repeat, seed in enumerate(seeds, start=1):
        folder = repeat_root / f"seed_{seed}"
        registry = pd.read_csv(folder / "candidate_registry.csv")
        ranking, regret, decisions = build_stage_b_outputs(
            pd.read_csv(folder / "inner_scores.csv"),
            pd.read_csv(folder / "outer_candidate_scores.csv"),
            registry,
            pool_sizes=pool_sizes,
        )
        for frame in (ranking, regret, decisions):
            frame["repeat"] = repeat
            frame["repeat_seed"] = seed
            frame["split_id"] = frame["endpoint"].astype(str) + f":seed{seed}:outer" + frame["outer_fold"].astype(str)
        ranking_frames.append(ranking)
        regret_frames.append(regret)
        decision_frames.append(decisions)
        registry_frames.append(registry)
    ranking = pd.concat(ranking_frames, ignore_index=True)
    regret = pd.concat(regret_frames, ignore_index=True)
    decisions = pd.concat(decision_frames, ignore_index=True)
    registry = pd.concat(registry_frames, ignore_index=True).drop_duplicates(["dataset", "candidate"])
    endpoint = (
        regret.groupby(["endpoint", "pool_size"], as_index=False)
        .agg(
            n_outer_units=("split_id", "nunique"),
            fixed_regret_mean=("fixed_normalized_regret", "mean"),
            raw_regret_mean=("raw_regret", "mean"),
        )
        .merge(
            ranking.groupby(["endpoint", "pool_size"], as_index=False).agg(
                chance_adjusted_hit_mean=("chance_adjusted_hit", "mean"),
                mrr_mean=("mrr", "mean"),
                rank_percentile_mean=("rank_percentile", "mean"),
            ),
            on=["endpoint", "pool_size"],
        )
    )
    output = root / "results" / "nested_selection"
    family = registry.drop_duplicates("candidate").set_index("candidate")["family"].astype(str).to_dict()
    stability_rows = []
    for (endpoint_name, pool_size), group in decisions.groupby(["endpoint", "pool_size"], sort=True):
        available = (
            registry.loc[registry["dataset"].eq(endpoint_name)]
            .sort_values("candidate_order")["candidate"]
            .astype(str)
            .tolist()[: int(pool_size)]
        )
        selected = group["selected_candidate"].dropna().astype(str).tolist()
        top_sets = [set(str(value).split(";")) - {""} for value in group["one_se_candidates"].fillna("")]
        stability_rows.append(
            {
                "endpoint": endpoint_name,
                "mode": "repeated_nested_fixed_prefix",
                "pool_size": int(pool_size),
                **selection_stability(selected, family, available_candidates=available),
                "pairwise_jaccard": mean_pairwise_jaccard(top_sets),
            }
        )
    stability = pd.DataFrame(stability_rows)
    paths = {
        "ranking": output / "repeated_ranking_metrics_long.csv",
        "regret": output / "repeated_regret_decomposition.csv",
        "decisions": output / "nested_results_long.csv",
        "summary": output / "repeated_endpoint_summary.csv",
        "stability": output / "repeated_stability_metrics.csv",
    }
    ranking.to_csv(paths["ranking"], index=False)
    regret.to_csv(paths["regret"], index=False)
    decisions.to_csv(paths["decisions"], index=False)
    endpoint.to_csv(paths["summary"], index=False)
    stability.to_csv(paths["stability"], index=False)
    return paths


def main() -> None:
    for name, path in build_outputs().items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
