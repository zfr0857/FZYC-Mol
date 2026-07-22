from __future__ import annotations

import json
from collections.abc import Sequence

import pandas as pd

from fzyc_mol.selection.candidate_pool_audit import (
    audit_candidate_pool_summary,
    summarize_validation_scores,
)
from fzyc_mol.selection.candidate_subsets import build_subset


def build_stage_c_outputs(
    inner_scores: pd.DataFrame,
    outer_scores: pd.DataFrame,
    registry: pd.DataFrame,
    *,
    modes: Sequence[str] = ("random_order", "random_subset", "family_balanced"),
    pool_sizes: Sequence[int] = (4, 8, 16, 32),
    seeds: Sequence[int] = tuple(range(100)),
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Evaluate predeclared subset perturbations on frozen outer units."""

    manifest_rows: list[dict[str, object]] = []
    ranking_rows: list[dict[str, object]] = []
    regret_rows: list[dict[str, object]] = []
    decision_rows: list[dict[str, object]] = []
    for dataset, reg in registry.groupby("dataset", sort=True):
        reg = reg.sort_values("candidate_order", kind="stable")
        task_type = str(reg["task_type"].iloc[0])
        subset_registry = reg.rename(
            columns={"candidate": "candidate_id", "candidate_order": "registry_order"}
        )[["candidate_id", "family", "registry_order"]]
        full_ids = subset_registry["candidate_id"].astype(str).tolist()
        baseline_id = full_ids[0]
        outer_folds = sorted(outer_scores.loc[outer_scores["dataset"].eq(dataset), "outer_fold"].unique())
        unit_cache: dict[int, tuple[object, dict[str, float], int]] = {}
        for outer_fold in outer_folds:
            outer = outer_scores[
                outer_scores["dataset"].eq(dataset) & outer_scores["outer_fold"].eq(outer_fold)
            ]
            outer_map = dict(zip(outer["candidate"].astype(str), outer["outer_utility"].astype(float), strict=True))
            inner = inner_scores[
                inner_scores["dataset"].eq(dataset) & inner_scores["outer_fold"].eq(outer_fold)
            ].rename(columns={"candidate": "candidate_id", "inner_utility": "val_utility"})
            unit_cache[int(outer_fold)] = (
                summarize_validation_scores(inner, full_ids),
                outer_map,
                int(inner["inner_fold"].nunique()),
            )
        for mode in modes:
            for pool_size in pool_sizes:
                if pool_size > len(full_ids):
                    continue
                for seed in seeds:
                    subset = build_subset(
                        subset_registry,
                        int(pool_size),
                        mode=mode,
                        seed=int(seed),
                        force_include=(baseline_id,),
                    )
                    subset_id = f"{dataset}:{mode}:k{pool_size}:seed{seed}"
                    order_id = f"{mode}:seed{seed}" if mode == "random_order" else "not_applicable"
                    manifest_rows.append(
                        {
                            "endpoint": dataset,
                            "task_type": task_type,
                            "mode": mode,
                            "pool_size": int(pool_size),
                            "subset_seed": int(seed),
                            "subset_id": subset_id,
                            "order_id": order_id,
                            "candidate_ids": ";".join(subset.candidate_ids),
                            "family_counts": json.dumps(dict(subset.family_counts), sort_keys=True),
                            "forced_candidates": baseline_id,
                        }
                    )
                    for outer_fold in outer_folds:
                        validation_cache, outer_map, n_inner = unit_cache[int(outer_fold)]
                        audit = audit_candidate_pool_summary(
                            validation_cache,
                            outer_map,
                            full_test_utility=outer_map,
                            pool_candidate_ids=subset.candidate_ids,
                            baseline_id=baseline_id,
                            task_type=task_type,
                            n_inner=n_inner,
                        )
                        metadata = {
                            "endpoint": dataset,
                            "task_type": task_type,
                            "repeat": 1,
                            "outer_fold": int(outer_fold),
                            "split_id": f"{dataset}:repeat1:outer{outer_fold}",
                            "mode": mode,
                            "pool_size": int(pool_size),
                            "subset_seed": int(seed),
                            "subset_id": subset_id,
                            "order_id": order_id,
                            "status": audit.status,
                        }
                        if audit.status != "completed":
                            decision_rows.append({**metadata, "selected_candidate": "", "selection_reason": "", "missing_candidates": ";".join(audit.missing_candidates)})
                            continue
                        assert audit.decision is not None and audit.ranking is not None and audit.regret is not None
                        ranking_rows.append({**metadata, **audit.ranking})
                        regret_rows.append({**metadata, "selected_candidate": audit.decision.candidate_id, **audit.regret})
                        decision_rows.append(
                            {
                                **metadata,
                                "selected_candidate": audit.decision.candidate_id,
                                "one_se_candidates": ";".join(audit.decision.one_se_candidates),
                                "selection_reason": json.dumps(audit.decision.reason_trace, ensure_ascii=False),
                                "missing_candidates": "",
                            }
                        )
    return (
        pd.DataFrame(manifest_rows),
        pd.DataFrame(ranking_rows),
        pd.DataFrame(regret_rows),
        pd.DataFrame(decision_rows),
    )
