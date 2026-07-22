from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fzyc_mol.selection.ablation import GOVERNANCE_RULES, select_ablation_rule  # noqa: E402
from fzyc_mol.selection.candidate_pool_audit import summarize_validation_scores  # noqa: E402


SEEDS = (11, 23, 37, 53, 71)


def _evaluation(
    outer_utility: dict[str, float],
    candidate_ids: list[str],
    selected_id: str,
    full_range: float,
) -> dict[str, object]:
    oracle_id = sorted(candidate_ids, key=lambda item: (-outer_utility[item], item))[0]
    raw_regret = float(outer_utility[oracle_id] - outer_utility[selected_id])
    return {
        "selected_candidate": selected_id,
        "oracle_candidate": oracle_id,
        "selected_test_utility": float(outer_utility[selected_id]),
        "oracle_test_utility": float(outer_utility[oracle_id]),
        "raw_regret": raw_regret,
        "full32_fixed_normalized_regret": raw_regret / full_range if full_range > 0 else 0.0,
        "normalization_status": "ok" if full_range > 0 else "zero_full_range",
    }


def build_outputs(root: Path = ROOT) -> dict[str, Path]:
    governance_rows: list[dict[str, object]] = []
    family_rows: list[dict[str, object]] = []
    for repeat, seed in enumerate(SEEDS, start=1):
        source = root / "results" / "nested_selection" / "repeated_nested" / f"seed_{seed}"
        inner_all = pd.read_csv(source / "inner_scores.csv")
        outer_all = pd.read_csv(source / "outer_candidate_scores.csv")
        registry_all = pd.read_csv(source / "candidate_registry.csv")
        units = outer_all[["dataset", "task_type", "outer_fold"]].drop_duplicates()
        for unit in units.itertuples(index=False):
            registry = registry_all.loc[registry_all["dataset"].eq(unit.dataset)].sort_values("candidate_order")
            full_ids = registry["candidate"].astype(str).tolist()
            family_by_id = dict(zip(registry["candidate"].astype(str), registry["family"].astype(str), strict=True))
            inner = inner_all.loc[
                inner_all["dataset"].eq(unit.dataset) & inner_all["outer_fold"].eq(unit.outer_fold)
            ].rename(columns={"candidate": "candidate_id", "inner_utility": "val_utility"})
            outer = outer_all.loc[
                outer_all["dataset"].eq(unit.dataset) & outer_all["outer_fold"].eq(unit.outer_fold)
            ]
            outer_utility = dict(zip(outer["candidate"].astype(str), outer["outer_utility"].astype(float), strict=True))
            full_range = max(outer_utility.values()) - min(outer_utility.values())
            cache = summarize_validation_scores(inner, full_ids)
            full_summary = cache.summary(full_ids)
            metadata = {
                "endpoint": unit.dataset,
                "task_type": unit.task_type,
                "repeat": repeat,
                "repeat_seed": seed,
                "outer_fold": int(unit.outer_fold),
                "split_id": f"{unit.dataset}:seed{seed}:outer{unit.outer_fold}",
            }
            for rule in GOVERNANCE_RULES:
                selected = select_ablation_rule(
                    full_summary,
                    rule=rule,
                    n_inner=int(inner["inner_fold"].nunique()),
                    task_type=unit.task_type,
                )
                governance_rows.append(
                    {
                        **metadata,
                        "ablation_class": "governance_rule",
                        "variant": rule,
                        "changed_component": "selection_rule_only",
                        "candidate_pool": "unchanged_full32",
                        "candidate_count": len(full_ids),
                        **_evaluation(outer_utility, full_ids, selected, full_range),
                    }
                )
            families = sorted(set(family_by_id.values()))
            variants = [("full_pool", full_ids)] + [
                (f"remove_{family}", [candidate for candidate in full_ids if family_by_id[candidate] != family])
                for family in families
            ]
            for variant, candidate_ids in variants:
                summary = cache.summary(candidate_ids)
                selected = select_ablation_rule(
                    summary,
                    rule="frozen_one_se_governance",
                    n_inner=int(inner["inner_fold"].nunique()),
                    task_type=unit.task_type,
                )
                family_rows.append(
                    {
                        **metadata,
                        "ablation_class": "candidate_family_removal",
                        "variant": variant,
                        "changed_component": "candidate_composition_only",
                        "selection_rule": "frozen_one_se_governance",
                        "candidate_count": len(candidate_ids),
                        **_evaluation(outer_utility, candidate_ids, selected, full_range),
                    }
                )

    output = root / "results" / "nested_selection"
    paths = {
        "governance": output / "governance_ablation.csv",
        "family": output / "family_removal.csv",
    }
    pd.DataFrame(governance_rows).to_csv(paths["governance"], index=False)
    pd.DataFrame(family_rows).to_csv(paths["family"], index=False)
    return paths


def main() -> None:
    for name, path in build_outputs().items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
