from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr
from sklearn.covariance import LedoitWolf


ROOT = Path(__file__).resolve().parents[1]
CLUSTER = ROOT / "results" / "split_regime_transfer_20260716" / "similarity_cluster"
CLASS_SCAFFOLD = ROOT / "results" / "nested_selection" / "repeated_nested"
REG_SCAFFOLD = ROOT / "results" / "regression_seeded_scaffold_20260713" / "prefix32"
OUT = Path(os.environ.get("FZYC_TRANSFER_OUT", ROOT / "output" / "paper26_split_regime_transfer_20260716"))
TASKS = ("clintox", "bace", "esol")
SEEDS = (11, 23, 37, 53, 71)
KS = (4, 8, 16, 32)
TRANSFORMS = ("raw", "row_centred", "fixed_reference_relative", "within_unit_rank")
RNG_SEED = 20260716


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def source_root(regime: str, task: str, seed: int) -> Path:
    if regime == "similarity_cluster":
        return CLUSTER / f"seed_{seed}"
    return (REG_SCAFFOLD if task == "esol" else CLASS_SCAFFOLD) / f"seed_{seed}"


def load_regime(regime: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    inner_frames, outer_frames, policy_frames, split_frames = [], [], [], []
    for seed in SEEDS:
        for task in TASKS:
            base = source_root(regime, task, seed)
            task_dir = base / "tasks" / task
            location = task_dir if task_dir.exists() else base
            for name, target in [
                ("inner_scores.csv", inner_frames),
                ("outer_candidate_scores.csv", outer_frames),
                ("policy_detail.csv", policy_frames),
            ]:
                frame = pd.read_csv(location / name).rename(columns={"dataset": "task"})
                frame = frame.loc[frame["task"].eq(task)].copy()
                frame.insert(0, "seed", seed)
                if "split_regime" not in frame:
                    frame.insert(0, "split_regime", regime)
                target.append(frame)
            split_path = location / "split_manifest.csv"
            if split_path.exists():
                frame = pd.read_csv(split_path).rename(columns={"endpoint": "task", "dataset": "task"})
                frame = frame.loc[frame["task"].eq(task)].copy()
                if "seed" not in frame:
                    frame.insert(0, "seed", seed)
                if "split_regime" not in frame:
                    frame.insert(0, "split_regime", regime)
                split_frames.append(frame)
    return (
        pd.concat(inner_frames, ignore_index=True),
        pd.concat(outer_frames, ignore_index=True),
        pd.concat(policy_frames, ignore_index=True),
        pd.concat(split_frames, ignore_index=True) if split_frames else pd.DataFrame(),
    )


def ranking_units(inner: pd.DataFrame, outer: pd.DataFrame) -> pd.DataFrame:
    means = inner.groupby(
        ["split_regime", "task", "task_type", "seed", "outer_fold", "candidate_order"], as_index=False
    )["inner_utility"].mean()
    rows = []
    for key, group in means.groupby(["split_regime", "task", "task_type", "seed", "outer_fold"]):
        regime, task, task_type, seed, fold = key
        out = outer.loc[
            outer["split_regime"].eq(regime) & outer["task"].eq(task)
            & outer["seed"].eq(seed) & outer["outer_fold"].eq(fold)
        ]
        for k in KS:
            inn = group.loc[group["candidate_order"].le(k)].sort_values(
                ["inner_utility", "candidate_order"], ascending=[False, True]
            )
            audit = out.loc[out["candidate_order"].le(k)].sort_values(
                ["outer_utility", "candidate_order"], ascending=[False, True]
            ).iloc[0]
            rank = int(np.flatnonzero(inn["candidate_order"].to_numpy() == int(audit.candidate_order))[0] + 1)
            hit = int(rank <= 3)
            mrr = 1.0 / rank
            expected_mrr = sum(1.0 / i for i in range(1, k + 1)) / k
            rows.append({
                "split_regime": regime, "task": task, "task_type": task_type,
                "seed": seed, "outer_fold": fold, "candidate_count": k,
                "audit_best_candidate_order": int(audit.candidate_order),
                "audit_best_validation_rank": rank, "hit_at_3": hit,
                "chance_adjusted_hit": (hit - 3 / k) / (1 - 3 / k),
                "normalized_mrr_gain": (mrr - expected_mrr) / (1 - expected_mrr),
            })
    return pd.DataFrame(rows)


def ranking_summary(units: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    seed = units.groupby(
        ["split_regime", "task", "task_type", "seed", "candidate_count"], as_index=False
    )[["chance_adjusted_hit", "normalized_mrr_gain"]].mean()
    endpoint = seed.groupby(
        ["split_regime", "task", "task_type", "candidate_count"], as_index=False
    )[["chance_adjusted_hit", "normalized_mrr_gain"]].mean()
    return seed, endpoint


def cross_fitted_units(outer: pd.DataFrame, policy: pd.DataFrame) -> pd.DataFrame:
    selected = policy.loc[
        policy["policy"].eq("validation_best") & policy["pool_size"].isin(KS),
        ["split_regime", "task", "task_type", "seed", "outer_fold", "pool_size", "outer_utility"],
    ].rename(columns={"pool_size": "candidate_count", "outer_utility": "selected_utility"})
    rows = []
    for (regime, task, task_type), task_outer in outer.groupby(["split_regime", "task", "task_type"]):
        for k in KS:
            for held_seed in SEEDS:
                training = task_outer.loc[~task_outer["seed"].eq(held_seed) & task_outer["candidate_order"].le(k)]
                reference_order = int(training.groupby("candidate_order")["outer_utility"].mean().sort_values(ascending=False).index[0])
                held_ref = task_outer.loc[
                    task_outer["seed"].eq(held_seed) & task_outer["candidate_order"].eq(reference_order),
                    ["outer_fold", "outer_utility"],
                ].rename(columns={"outer_utility": "cross_reference_utility"})
                held_selected = selected.loc[
                    selected["split_regime"].eq(regime) & selected["task"].eq(task)
                    & selected["seed"].eq(held_seed) & selected["candidate_count"].eq(k)
                ]
                merged = held_selected.merge(held_ref, on="outer_fold")
                for row in merged.itertuples(index=False):
                    rows.append({
                        "split_regime": regime, "task": task, "task_type": task_type,
                        "seed": held_seed, "outer_fold": int(row.outer_fold), "candidate_count": k,
                        "cross_reference_candidate_order": reference_order,
                        "selected_utility": float(row.selected_utility),
                        "cross_reference_utility": float(row.cross_reference_utility),
                        "cross_fitted_gap": float(row.cross_reference_utility - row.selected_utility),
                    })
    return pd.DataFrame(rows)


def cross_effects(units: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(RNG_SEED)
    rows = []
    for (regime, task, task_type), group in units.groupby(["split_regime", "task", "task_type"]):
        wide = group.pivot_table(index=["seed", "outer_fold"], columns="candidate_count", values="cross_fitted_gap")
        delta = wide[32] - wide[4]
        seed_means = delta.groupby("seed").mean().reindex(SEEDS)
        draws = rng.choice(seed_means.to_numpy(), size=(10000, len(SEEDS)), replace=True).mean(axis=1)
        rows.append({
            "split_regime": regime, "task": task, "task_type": task_type,
            "cross_fitted_k32_minus_k4": float(seed_means.mean()),
            "bootstrap95_low": float(np.quantile(draws, 0.025)),
            "bootstrap95_high": float(np.quantile(draws, 0.975)),
            "positive_seed_means": int((seed_means > 0).sum()),
        })
    return pd.DataFrame(rows)


def transform(x: np.ndarray, mode: str) -> np.ndarray:
    if mode == "raw":
        return x
    if mode == "row_centred":
        return x - x.mean(axis=1, keepdims=True)
    if mode == "fixed_reference_relative":
        return x[:, 1:] - x[:, [0]]
    if mode == "within_unit_rank":
        return np.apply_along_axis(rankdata, 1, x)
    raise ValueError(mode)


def effective_rank(x: np.ndarray) -> dict[str, float]:
    keep = np.nanstd(x, axis=0) > 1e-12
    x = x[:, keep]
    if x.shape[1] <= 1:
        return {"entropy_rank": 1.0, "participation_rank": 1.0, "median_correlation": 1.0}
    sd = x.std(axis=0, ddof=1)
    z = (x - x.mean(axis=0)) / np.where(sd > 1e-12, sd, 1.0)
    cov = LedoitWolf().fit(z).covariance_
    scale = np.sqrt(np.clip(np.diag(cov), 1e-15, None))
    corr = np.clip(cov / np.outer(scale, scale), -1, 1)
    np.fill_diagonal(corr, 1)
    eig = np.clip(np.linalg.eigvalsh(corr), 0, None)
    p = eig / eig.sum()
    p = p[p > 1e-15]
    off = corr[np.triu_indices_from(corr, 1)]
    return {
        "entropy_rank": float(np.exp(-(p * np.log(p)).sum())),
        "participation_rank": float(eig.sum() ** 2 / np.square(eig).sum()),
        "median_correlation": float(np.median(off)),
    }


def diversity(outer: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (regime, task, task_type), group in outer.groupby(["split_regime", "task", "task_type"]):
        for k in KS:
            matrix = group.loc[group["candidate_order"].le(k)].pivot_table(
                index=["seed", "outer_fold"], columns="candidate_order", values="outer_utility"
            ).to_numpy(float)
            for mode in TRANSFORMS:
                values = transform(matrix, mode)
                metrics = effective_rank(values)
                rows.append({
                    "split_regime": regime, "task": task, "task_type": task_type,
                    "candidate_count": k, "transformation": mode,
                    "n_outer_units": matrix.shape[0], "n_matrix_columns": values.shape[1],
                    **metrics, "relative_entropy_rank": metrics["entropy_rank"] / values.shape[1],
                })
    return pd.DataFrame(rows)


def integrity(splits: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    cluster = splits.loc[splits["split_regime"].eq("similarity_cluster")].copy()
    summary = cluster.groupby(["task", "task_type"], as_index=False).agg(
        n_split_rows=("split_hash", "size"),
        unique_outer_assignments=("outer_split_hash", "nunique"),
        all_group_disjoint=("no_group_overlap", "all"),
        min_train_n=("train_n", "min"), max_train_n=("train_n", "max"),
        min_validation_n=("validation_n", "min"), max_validation_n=("validation_n", "max"),
        min_test_n=("test_n", "min"), max_test_n=("test_n", "max"),
        max_train_validation_tanimoto=("max_train_validation_tanimoto", "max"),
        max_train_test_tanimoto=("max_train_test_tanimoto", "max"),
        max_validation_test_tanimoto=("max_validation_test_tanimoto", "max"),
    )
    checks = {
        "all_three_tasks_present": summary["task"].nunique() == 3,
        "fifteen_unique_outer_fold_assignments_per_task": bool((summary["unique_outer_assignments"] == 15).all()),
        "all_similarity_components_disjoint": bool(summary["all_group_disjoint"].all()),
        "all_cross_fold_tanimoto_below_0_70": bool(
            summary[["max_train_validation_tanimoto", "max_train_test_tanimoto", "max_validation_test_tanimoto"]].max().max() < 0.70
        ),
    }
    return summary, checks


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    loaded = [load_regime(regime) for regime in ("scaffold", "similarity_cluster")]
    inner = pd.concat([item[0] for item in loaded], ignore_index=True)
    outer = pd.concat([item[1] for item in loaded], ignore_index=True)
    policy = pd.concat([item[2] for item in loaded], ignore_index=True)
    splits = pd.concat([item[3] for item in loaded if not item[3].empty], ignore_index=True)
    assert len(inner) == 2 * len(TASKS) * len(SEEDS) * 3 * 3 * 32
    assert len(outer) == 2 * len(TASKS) * len(SEEDS) * 3 * 32

    ranks = ranking_units(inner, outer)
    rank_seed, rank_endpoint = ranking_summary(ranks)
    cross_units = cross_fitted_units(outer, policy)
    effects = cross_effects(cross_units)
    effective = diversity(outer)
    split_summary, split_checks = integrity(splits)

    transport = rank_endpoint.pivot_table(
        index=["task", "task_type", "candidate_count"], columns="split_regime", values="chance_adjusted_hit"
    ).reset_index()
    transport["same_cahit_sign"] = np.sign(transport["scaffold"]) == np.sign(transport["similarity_cluster"])
    change = rank_endpoint.pivot_table(
        index=["split_regime", "task", "task_type"], columns="candidate_count", values="chance_adjusted_hit"
    ).reset_index()
    change["cahit_k32_minus_k4"] = change[32] - change[4]
    change_wide = change.pivot_table(
        index=["task", "task_type"], columns="split_regime", values="cahit_k32_minus_k4"
    ).reset_index()
    change_wide["same_cahit_change_direction"] = np.sign(change_wide["scaffold"]) == np.sign(change_wide["similarity_cluster"])
    effect_wide = effects.pivot_table(index=["task", "task_type"], columns="split_regime", values="cross_fitted_k32_minus_k4").reset_index()
    effect_wide["same_cross_effect_direction"] = np.sign(effect_wide["scaffold"]) == np.sign(effect_wide["similarity_cluster"])
    paired_diversity = effective.pivot_table(
        index=["task", "candidate_count", "transformation"], columns="split_regime", values="entropy_rank"
    ).dropna()
    diversity_rho = float(spearmanr(paired_diversity["scaffold"], paired_diversity["similarity_cluster"]).statistic)

    outputs = {
        "split_regime_ranking_units.csv": ranks,
        "split_regime_ranking_seed_summary.csv": rank_seed,
        "split_regime_ranking_endpoint_summary.csv": rank_endpoint,
        "split_regime_cross_fitted_units.csv": cross_units,
        "split_regime_cross_fitted_effects.csv": effects,
        "split_regime_effect_direction_concordance.csv": effect_wide,
        "split_regime_effective_diversity.csv": effective,
        "split_regime_cahit_transport.csv": transport,
        "split_regime_cahit_change_concordance.csv": change_wide,
        "similarity_split_integrity_summary.csv": split_summary,
    }
    for name, frame in outputs.items():
        frame.to_csv(OUT / name, index=False)
    audit = {
        "status": "complete" if all(split_checks.values()) else "failed",
        "tasks": list(TASKS), "seeds": list(SEEDS), "candidate_counts": list(KS),
        "nested_design": "five split seeds; three outer folds; three inner folds; 32 registered candidates",
        "similarity_group_definition": "Morgan-512 connected components joining pairs with Tanimoto >= 0.70",
        "split_checks": split_checks,
        "effective_diversity_spearman_between_regimes": diversity_rho,
        "same_cross_effect_direction_count": int(effect_wide["same_cross_effect_direction"].sum()),
        "same_cahit_change_direction_count": int(change_wide["same_cahit_change_direction"].sum()),
        "source_scope": "Scaffold results reuse the locked primary registry outputs; similarity-cluster results are new retraining outputs.",
        "outputs": {name: {"rows": len(frame), "sha256": sha(OUT / name)} for name, frame in outputs.items()},
    }
    (OUT / "split_regime_transfer_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
