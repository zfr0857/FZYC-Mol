from __future__ import annotations

import json
from collections.abc import Sequence

import pandas as pd

from fzyc_mol.selection.candidate_pool_audit import audit_candidate_pool


def build_stage_b_outputs(
    inner_scores: pd.DataFrame,
    outer_scores: pd.DataFrame,
    registry: pd.DataFrame,
    *,
    pool_sizes: Sequence[int] = (4, 8, 16, 32),
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Rebuild fixed-prefix audit metrics from existing nested predictions."""

    ranking_rows: list[dict[str, object]] = []
    regret_rows: list[dict[str, object]] = []
    decision_rows: list[dict[str, object]] = []
    units = outer_scores[["dataset", "task_type", "outer_fold"]].drop_duplicates()
    for unit in units.itertuples(index=False):
        reg = registry[registry["dataset"].eq(unit.dataset)].sort_values("candidate_order")
        full_ids = reg["candidate"].astype(str).tolist()
        outer = outer_scores[
            outer_scores["dataset"].eq(unit.dataset) & outer_scores["outer_fold"].eq(unit.outer_fold)
        ]
        outer_map = dict(zip(outer["candidate"].astype(str), outer["outer_utility"].astype(float), strict=True))
        inner = inner_scores[
            inner_scores["dataset"].eq(unit.dataset) & inner_scores["outer_fold"].eq(unit.outer_fold)
        ].rename(columns={"candidate": "candidate_id", "inner_utility": "val_utility"})
        baseline_id = full_ids[0]
        for pool_size in pool_sizes:
            if pool_size > len(full_ids):
                continue
            pool_ids = full_ids[:pool_size]
            subset_id = f"fixed_prefix_k{pool_size}"
            audit = audit_candidate_pool(
                inner,
                outer_map,
                full_test_utility=outer_map,
                pool_candidate_ids=pool_ids,
                baseline_id=baseline_id,
                task_type=unit.task_type,
            )
            metadata = {
                "endpoint": unit.dataset,
                "task_type": unit.task_type,
                "repeat": 1,
                "outer_fold": int(unit.outer_fold),
                "split_id": f"{unit.dataset}:repeat1:outer{unit.outer_fold}",
                "pool_size": int(pool_size),
                "subset_id": subset_id,
                "order_id": "original_registry",
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
                    "one_se_threshold": audit.decision.threshold,
                    "selection_reason": json.dumps(audit.decision.reason_trace, ensure_ascii=False),
                    "columns_read": ";".join(audit.decision.columns_read),
                    "missing_candidates": "",
                }
            )
    return pd.DataFrame(ranking_rows), pd.DataFrame(regret_rows), pd.DataFrame(decision_rows)
