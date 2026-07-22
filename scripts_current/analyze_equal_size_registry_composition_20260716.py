from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr
from sklearn.covariance import LedoitWolf


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "equal_size_registry_composition_20260716"
NEW = RESULTS / "new_candidates"
HOM = ROOT / "results" / "nested_selection" / "repeated_nested"
MULTI = ROOT / "results" / "reviewer_core_20260624" / "multiview_nested"
CHEMPROP = ROOT / "output" / "小论文-12_严格补实验"
OUT = ROOT / "output" / "paper27_equal_size_registry_composition_20260716"
TASKS = ["clintox", "bace", "esol"]
SEEDS = [11, 23, 37, 53, 71]
KS = [16, 32]
REPRESENTATIONS = ["morgan512", "maccs", "rdkit2d", "multiview"]
CLASSIC_FAMILIES = [
    "linear", "random_forest", "lightgbm", "extra_trees",
    "linear_alt", "random_forest_alt", "lightgbm_alt", "xgboost",
]
EMBEDDING_REPRESENTATIONS = ["chemberta_mtr", "chemberta_mlm", "molformer"]
EMBEDDING_FAMILIES = ["linear", "linear_alt", "linear_strong", "linear_sparse", "lightgbm"]
TRANSFORMS = ["raw", "row_centred", "fixed_reference_relative", "within_unit_rank"]
RNG_SEED = 20260716


def normalize(frame: pd.DataFrame, kind: str, source: str) -> pd.DataFrame:
    frame = frame.copy()
    if "dataset" in frame.columns:
        frame = frame.rename(columns={"dataset": "task"})
    if "fit_predict_seconds" in frame.columns:
        frame = frame.rename(columns={"fit_predict_seconds": "fit_seconds"})
    utility = "inner_utility" if kind == "inner" else "outer_utility"
    required = ["task", "task_type", "seed", "outer_fold", "candidate", utility, "fit_seconds"]
    if kind == "inner":
        required.append("inner_fold")
    missing = [column for column in required if column not in frame]
    if missing:
        raise ValueError(f"{source} missing {missing}")
    frame["source"] = source
    if "representation" not in frame:
        frame["representation"] = "morgan512" if source == "homogeneous" else "dmpnn_graph"
    if "family" not in frame:
        frame["family"] = "unknown"
    return frame


def load_sources() -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    hom_inner, hom_outer = [], []
    for seed in SEEDS:
        inner = pd.read_csv(HOM / f"seed_{seed}" / "inner_scores.csv")
        outer = pd.read_csv(HOM / f"seed_{seed}" / "outer_candidate_scores.csv")
        inner["seed"] = seed
        outer["seed"] = seed
        hom_inner.append(inner.loc[inner["dataset"].isin(TASKS)])
        hom_outer.append(outer.loc[outer["dataset"].isin(TASKS)])
    hom_inner = normalize(pd.concat(hom_inner, ignore_index=True), "inner", "homogeneous")
    hom_outer = normalize(pd.concat(hom_outer, ignore_index=True), "outer", "homogeneous")

    base_inner = normalize(pd.read_csv(MULTI / "inner_scores.csv"), "inner", "multiview_base")
    base_outer = normalize(pd.read_csv(MULTI / "outer_candidate_scores.csv"), "outer", "multiview_base")
    base_inner = base_inner.loc[base_inner.task.isin(TASKS)].copy()
    base_outer = base_outer.loc[base_outer.task.isin(TASKS)].copy()

    new_inner = normalize(pd.read_csv(NEW / "inner_scores.csv"), "inner", "new_nested_candidates")
    new_outer = normalize(pd.read_csv(NEW / "outer_candidate_scores.csv"), "outer", "new_nested_candidates")

    dmp_inner = normalize(pd.read_csv(CHEMPROP / "chemprop_inner_scores.csv"), "inner", "chemprop_dmpnn")
    dmp_outer_raw = pd.read_csv(CHEMPROP / "chemprop_outer_scores.csv")
    dmp_outer_time = pd.read_csv(CHEMPROP / "chemprop_outer_predictions.csv").groupby(
        ["task", "seed", "outer_fold"], as_index=False
    )["fit_predict_seconds"].first()
    dmp_outer_raw = dmp_outer_raw.merge(dmp_outer_time, on=["task", "seed", "outer_fold"], validate="one_to_one")
    dmp_outer = normalize(dmp_outer_raw, "outer", "chemprop_dmpnn")
    dmp_inner["representation"] = "dmpnn_graph"
    dmp_outer["representation"] = "dmpnn_graph"
    dmp_inner["family"] = "chemprop_dmpnn"
    dmp_outer["family"] = "chemprop_dmpnn"

    return (
        {"hom": hom_inner, "base": base_inner, "new": new_inner, "dmpnn": dmp_inner},
        {"hom": hom_outer, "base": base_outer, "new": new_outer, "dmpnn": dmp_outer},
    )


def pool_orders() -> dict[str, list[str]]:
    classic = [f"{representation}__{family}" for family in CLASSIC_FAMILIES for representation in REPRESENTATIONS]
    modern_candidates = ["chemprop_dmpnn"] + [
        f"{representation}__{family}"
        for family in EMBEDDING_FAMILIES
        for representation in EMBEDDING_REPRESENTATIONS
    ]
    modern: list[str] = []
    for classic_candidate, modern_candidate in zip(classic[:16], modern_candidates):
        modern.extend([classic_candidate, modern_candidate])
    homogeneous = ["morgan512__linear"] + [f"hom::order{i:02d}" for i in range(1, 32)]
    assert len(homogeneous) == len(classic) == len(modern) == 32
    return {"Homogeneous Morgan": homogeneous, "Classical multiview": classic, "Modern-augmented": modern}


def assemble_pools(
    inner_sources: dict[str, pd.DataFrame], outer_sources: dict[str, pd.DataFrame]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    orders = pool_orders()
    registries = []
    inner_parts, outer_parts = [], []
    for pool, order in orders.items():
        if pool == "Homogeneous Morgan":
            anchor_i = inner_sources["base"].loc[inner_sources["base"].candidate.eq("morgan512__linear")].copy()
            anchor_o = outer_sources["base"].loc[outer_sources["base"].candidate.eq("morgan512__linear")].copy()
            old_i = inner_sources["hom"].loc[inner_sources["hom"].candidate_order.le(31)].copy()
            old_o = outer_sources["hom"].loc[outer_sources["hom"].candidate_order.le(31)].copy()
            old_i["candidate"] = old_i.candidate_order.map(lambda value: f"hom::order{int(value):02d}")
            old_o["candidate"] = old_o.candidate_order.map(lambda value: f"hom::order{int(value):02d}")
            inner = pd.concat([anchor_i, old_i], ignore_index=True)
            outer = pd.concat([anchor_o, old_o], ignore_index=True)
        elif pool == "Classical multiview":
            inner = pd.concat([inner_sources["base"], inner_sources["new"]], ignore_index=True)
            outer = pd.concat([outer_sources["base"], outer_sources["new"]], ignore_index=True)
            inner = inner.loc[inner.candidate.isin(order)].copy()
            outer = outer.loc[outer.candidate.isin(order)].copy()
        else:
            inner = pd.concat([inner_sources["base"], inner_sources["new"], inner_sources["dmpnn"]], ignore_index=True)
            outer = pd.concat([outer_sources["base"], outer_sources["new"], outer_sources["dmpnn"]], ignore_index=True)
            inner = inner.loc[inner.candidate.isin(order)].copy()
            outer = outer.loc[outer.candidate.isin(order)].copy()
        mapping = {candidate: i + 1 for i, candidate in enumerate(order)}
        inner["pool"] = pool
        outer["pool"] = pool
        inner["pool_order"] = inner.candidate.map(mapping)
        outer["pool_order"] = outer.candidate.map(mapping)
        if inner.pool_order.isna().any() or outer.pool_order.isna().any():
            raise ValueError(f"Unmapped candidates in {pool}")
        inner_parts.append(inner)
        outer_parts.append(outer)
        meta = pd.concat([
            inner[["candidate", "representation", "family", "source"]],
            outer[["candidate", "representation", "family", "source"]],
        ]).drop_duplicates("candidate")
        meta["pool"] = pool
        meta["pool_order"] = meta.candidate.map(mapping)
        registries.append(meta)
    registry = pd.concat(registries, ignore_index=True).sort_values(["pool", "pool_order"])
    inner = pd.concat(inner_parts, ignore_index=True)
    outer = pd.concat(outer_parts, ignore_index=True)
    return inner, outer, registry


def verify_balance(inner: pd.DataFrame, outer: pd.DataFrame) -> dict[str, object]:
    expected_inner = 3 * 5 * 3 * 3
    expected_outer = 3 * 5 * 3
    checks = {}
    for pool in pool_orders():
        for k in KS:
            i = inner.loc[inner.pool.eq(pool) & inner.pool_order.le(k)]
            o = outer.loc[outer.pool.eq(pool) & outer.pool_order.le(k)]
            checks[f"{pool}_K{k}_inner_candidate_units"] = int(len(i)) == expected_inner * k
            checks[f"{pool}_K{k}_outer_candidate_units"] = int(len(o)) == expected_outer * k
            checks[f"{pool}_K{k}_exact_candidates"] = i.candidate.nunique() == o.candidate.nunique() == k
    return checks


def selection_units(inner: pd.DataFrame, outer: pd.DataFrame) -> pd.DataFrame:
    rows = []
    keys = ["pool", "task", "task_type", "seed", "outer_fold"]
    for key, outer_unit in outer.groupby(keys):
        pool, task, task_type, seed, outer_fold = key
        inner_unit = inner.loc[
            inner.pool.eq(pool) & inner.task.eq(task) & inner.seed.eq(seed) & inner.outer_fold.eq(outer_fold)
        ]
        for k in KS:
            eligible_o = outer_unit.loc[outer_unit.pool_order.le(k)].copy()
            eligible_i = inner_unit.loc[inner_unit.pool_order.le(k)].copy()
            stats = eligible_i.groupby(["candidate", "pool_order"], as_index=False).agg(
                inner_mean=("inner_utility", "mean"), inner_sd=("inner_utility", "std"),
                inner_fit_seconds=("fit_seconds", "sum"),
            )
            selected = stats.sort_values(["inner_mean", "pool_order"], ascending=[False, True]).iloc[0]
            oracle = eligible_o.sort_values(["outer_utility", "pool_order"], ascending=[False, True]).iloc[0]
            selected_outer = eligible_o.loc[eligible_o.candidate.eq(selected.candidate)].iloc[0]
            anchor_outer = eligible_o.loc[eligible_o.candidate.eq("morgan512__linear")].iloc[0]
            top3 = set(stats.sort_values(["inner_mean", "pool_order"], ascending=[False, True]).head(3).candidate)
            audit_seconds = float(eligible_i.fit_seconds.sum() + eligible_o.fit_seconds.sum())
            oracle_gain = float(oracle.outer_utility - anchor_outer.outer_utility)
            selected_gain = float(selected_outer.outer_utility - anchor_outer.outer_utility)
            rows.append({
                "pool": pool, "task": task, "task_type": task_type, "seed": int(seed),
                "outer_fold": int(outer_fold), "candidate_count": k,
                "selected_candidate": selected.candidate, "oracle_candidate": oracle.candidate,
                "anchor_utility": float(anchor_outer.outer_utility),
                "selected_utility": float(selected_outer.outer_utility), "oracle_utility": float(oracle.outer_utility),
                "oracle_opportunity_gain": oracle_gain, "selected_model_gain": selected_gain,
                "same_unit_selection_gap": float(oracle.outer_utility - selected_outer.outer_utility),
                "top3_hit": int(oracle.candidate in top3),
                "chance_adjusted_hit3": (int(oracle.candidate in top3) - 3 / k) / (1 - 3 / k),
                "audit_fit_seconds": audit_seconds,
                "selected_gain_per_audit_hour": selected_gain / max(audit_seconds / 3600, 1e-12),
                "opportunity_capture_fraction": selected_gain / oracle_gain if oracle_gain > 1e-12 else np.nan,
            })
    return pd.DataFrame(rows)


def add_cross_fitted_gap(units: pd.DataFrame, outer: pd.DataFrame) -> pd.DataFrame:
    units = units.copy()
    units["cross_reference_candidate"] = ""
    units["cross_reference_utility"] = np.nan
    units["cross_fitted_selection_gap"] = np.nan
    for (pool, task, task_type, k), group in units.groupby(["pool", "task", "task_type", "candidate_count"]):
        candidate_outer = outer.loc[outer.pool.eq(pool) & outer.task.eq(task) & outer.pool_order.le(k)]
        for held_seed in SEEDS:
            train = candidate_outer.loc[~candidate_outer.seed.eq(held_seed)]
            reference = train.groupby("candidate").outer_utility.mean().sort_values(ascending=False).index[0]
            held_reference = candidate_outer.loc[
                candidate_outer.seed.eq(held_seed) & candidate_outer.candidate.eq(reference),
                ["outer_fold", "outer_utility"],
            ].set_index("outer_fold").outer_utility
            mask = (
                units.pool.eq(pool) & units.task.eq(task) & units.candidate_count.eq(k) & units.seed.eq(held_seed)
            )
            for index in units.index[mask]:
                fold = int(units.at[index, "outer_fold"])
                reference_utility = float(held_reference.loc[fold])
                units.at[index, "cross_reference_candidate"] = reference
                units.at[index, "cross_reference_utility"] = reference_utility
                units.at[index, "cross_fitted_selection_gap"] = reference_utility - units.at[index, "selected_utility"]
    if units.cross_fitted_selection_gap.isna().any():
        raise ValueError("Incomplete cross-fitted gaps")
    return units


def bootstrap_summary(units: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(RNG_SEED)
    metrics = [
        "oracle_opportunity_gain", "selected_model_gain", "same_unit_selection_gap",
        "chance_adjusted_hit3", "cross_fitted_selection_gap", "audit_fit_seconds",
        "selected_gain_per_audit_hour", "opportunity_capture_fraction",
    ]
    rows = []
    for key, group in units.groupby(["pool", "task", "task_type", "candidate_count"]):
        row = dict(zip(["pool", "task", "task_type", "candidate_count"], key))
        for metric in metrics:
            seed_means = group.groupby("seed")[metric].mean().reindex(SEEDS).to_numpy(float)
            finite = seed_means[np.isfinite(seed_means)]
            row[f"{metric}_mean"] = float(np.mean(finite)) if len(finite) else np.nan
            if len(finite):
                draws = rng.choice(finite, size=(10000, len(finite)), replace=True).mean(axis=1)
                row[f"{metric}_low"] = float(np.quantile(draws, .025))
                row[f"{metric}_high"] = float(np.quantile(draws, .975))
            else:
                row[f"{metric}_low"] = row[f"{metric}_high"] = np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def transform(matrix: np.ndarray, mode: str) -> np.ndarray:
    if mode == "raw":
        return matrix
    if mode == "row_centred":
        return matrix - matrix.mean(axis=1, keepdims=True)
    if mode == "fixed_reference_relative":
        return matrix[:, 1:] - matrix[:, [0]]
    if mode == "within_unit_rank":
        return np.apply_along_axis(rankdata, 1, matrix)
    raise ValueError(mode)


def effective_rank(matrix: np.ndarray) -> dict[str, float]:
    keep = np.nanstd(matrix, axis=0) > 1e-12
    x = matrix[:, keep]
    if x.shape[1] <= 1:
        return {"entropy_rank": 1.0, "participation_rank": 1.0, "median_correlation": 1.0}
    sd = x.std(axis=0, ddof=1)
    z = (x - x.mean(axis=0)) / np.where(sd > 1e-12, sd, 1.0)
    cov = LedoitWolf().fit(z).covariance_
    scale = np.sqrt(np.clip(np.diag(cov), 1e-15, None))
    corr = np.clip(cov / np.outer(scale, scale), -1, 1)
    np.fill_diagonal(corr, 1.0)
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
    for key, group in outer.groupby(["pool", "task", "task_type"]):
        for k in KS:
            matrix = group.loc[group.pool_order.le(k)].pivot_table(
                index=["seed", "outer_fold"], columns="pool_order", values="outer_utility"
            ).to_numpy(float)
            for mode in TRANSFORMS:
                values = transform(matrix, mode)
                metrics = effective_rank(values)
                rows.append({
                    "pool": key[0], "task": key[1], "task_type": key[2], "candidate_count": k,
                    "transformation": mode, "n_outer_units": matrix.shape[0],
                    "n_matrix_columns": values.shape[1], **metrics,
                    "relative_entropy_rank": metrics["entropy_rank"] / values.shape[1],
                })
    return pd.DataFrame(rows)


def paired_pool_effects(units: pd.DataFrame) -> pd.DataFrame:
    rows = []
    metrics = ["oracle_opportunity_gain", "selected_model_gain", "cross_fitted_selection_gap", "chance_adjusted_hit3"]
    baseline = "Homogeneous Morgan"
    for task in TASKS:
        for k in KS:
            base = units.loc[units.pool.eq(baseline) & units.task.eq(task) & units.candidate_count.eq(k)].set_index(["seed", "outer_fold"])
            for pool in ("Classical multiview", "Modern-augmented"):
                comp = units.loc[units.pool.eq(pool) & units.task.eq(task) & units.candidate_count.eq(k)].set_index(["seed", "outer_fold"])
                for metric in metrics:
                    delta = comp[metric] - base[metric]
                    seed_delta = delta.groupby("seed").mean()
                    rows.append({
                        "task": task, "candidate_count": k, "comparison": f"{pool} - {baseline}",
                        "metric": metric, "mean_paired_difference": float(seed_delta.mean()),
                        "positive_seed_means": int((seed_delta > 0).sum()), "negative_seed_means": int((seed_delta < 0).sum()),
                    })
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    inner_sources, outer_sources = load_sources()
    inner, outer, registry = assemble_pools(inner_sources, outer_sources)
    checks = verify_balance(inner, outer)
    if not all(checks.values()):
        raise RuntimeError([key for key, value in checks.items() if not value])
    units = add_cross_fitted_gap(selection_units(inner, outer), outer)
    summary = bootstrap_summary(units)
    diversity_table = diversity(outer)
    paired = paired_pool_effects(units)

    raw_diversity = diversity_table.loc[diversity_table.transformation.eq("raw")]
    merged = summary.merge(
        raw_diversity[["pool", "task", "candidate_count", "entropy_rank", "relative_entropy_rank"]],
        on=["pool", "task", "candidate_count"], how="left",
    )
    association = {
        "relative_diversity_vs_same_unit_gap_spearman": float(spearmanr(
            merged.relative_entropy_rank, merged.same_unit_selection_gap_mean
        ).statistic),
        "relative_diversity_vs_cross_fitted_gap_spearman": float(spearmanr(
            merged.relative_entropy_rank, merged.cross_fitted_selection_gap_mean
        ).statistic),
        "relative_diversity_vs_oracle_gain_spearman": float(spearmanr(
            merged.relative_entropy_rank, merged.oracle_opportunity_gain_mean
        ).statistic),
        "n_endpoint_pool_k_cells": int(len(merged)),
    }

    registry.to_csv(OUT / "equal_size_candidate_registry.csv", index=False)
    inner.to_csv(OUT / "equal_size_inner_scores.csv.gz", index=False, compression="gzip")
    outer.to_csv(OUT / "equal_size_outer_candidate_scores.csv.gz", index=False, compression="gzip")
    units.to_csv(OUT / "equal_size_selection_units.csv", index=False)
    summary.to_csv(OUT / "equal_size_endpoint_summary.csv", index=False)
    diversity_table.to_csv(OUT / "equal_size_effective_diversity.csv", index=False)
    paired.to_csv(OUT / "equal_size_paired_pool_effects.csv", index=False)
    merged.to_csv(OUT / "equal_size_story_cells.csv", index=False)
    audit = {
        "status": "complete", "checks": checks, "association": association,
        "design": {
            "tasks": TASKS, "seeds": SEEDS, "outer_folds": 3, "inner_folds": 3, "candidate_counts": KS,
            "shared_anchor": "morgan512__linear", "pool_count": 3,
            "modern_scope": "frozen ChemBERTa/MoLFormer embeddings with nested heads plus locked one-epoch D-MPNN",
            "cost_scope": "observed downstream fit/predict wall time; encoder pretraining and cached embedding extraction excluded",
        },
        "rows": {
            "inner": int(len(inner)), "outer": int(len(outer)), "selection_units": int(len(units)),
            "summary": int(len(summary)), "diversity": int(len(diversity_table)),
        },
    }
    (OUT / "equal_size_registry_composition_audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(audit, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
