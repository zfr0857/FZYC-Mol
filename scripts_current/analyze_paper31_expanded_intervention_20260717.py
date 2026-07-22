from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr
from sklearn.covariance import LedoitWolf


ROOT = Path(__file__).resolve().parents[1]
OLD_NEW = ROOT / "results" / "equal_size_registry_composition_20260716" / "new_candidates"
NEW = ROOT / "results" / "paper31_expanded_intervention_20260717" / "new_candidates"
HOM = ROOT / "results" / "nested_selection" / "repeated_nested"
MULTI = ROOT / "results" / "reviewer_core_20260624" / "multiview_nested"
OLD_CHEMPROP = ROOT / "output" / "小论文-12_严格补实验"
NEW_CHEMPROP = ROOT / "results" / "paper31_expanded_intervention_20260717" / "chemprop"
OUT = ROOT / "output" / "paper31_expanded_intervention_20260717"

TASKS = ["clintox", "bace", "bbbp", "esol", "lipo", "tdc_caco2_wang"]
SEEDS = [11, 23, 37, 53, 71]
KS = [4, 8, 16, 32]
ABLATION_KS = [16, 32]
REPRESENTATIONS = ["morgan512", "maccs", "rdkit2d", "multiview"]
CLASSIC_FAMILIES = [
    "linear", "random_forest", "lightgbm", "extra_trees",
    "linear_alt", "random_forest_alt", "lightgbm_alt", "xgboost",
]
EMBEDDING_REPRESENTATIONS = ["chemberta_mtr", "chemberta_mlm", "molformer"]
EMBEDDING_FAMILIES = ["linear", "linear_alt", "linear_strong", "linear_sparse", "lightgbm"]
POOL_NAMES = ["Homogeneous Morgan", "Classical multiview", "Modern-augmented"]
PRIMARY_ANCHOR = "morgan512__linear"
SECONDARY_ANCHOR = "morgan512__random_forest"
EPSILON = 1e-12
RNG_SEED = 20260717


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
        raise ValueError(f"{source} missing required columns: {missing}")
    frame = frame.loc[frame.task.isin(TASKS)].copy()
    frame["source"] = source
    if "representation" not in frame:
        frame["representation"] = "morgan512" if source == "homogeneous" else "dmpnn_graph"
    if "family" not in frame:
        frame["family"] = "unknown"
    return frame


def load_csv_parts(paths: list[Path], filename: str) -> pd.DataFrame:
    found = [path / filename for path in paths if (path / filename).exists()]
    if not found:
        raise FileNotFoundError(f"No {filename} found under {paths}")
    return pd.concat([pd.read_csv(path) for path in found], ignore_index=True)


def load_chemprop(root: Path, kind: str) -> pd.DataFrame:
    if kind == "inner":
        frame = pd.read_csv(root / "chemprop_inner_scores.csv")
        return normalize(frame, kind, f"chemprop_dmpnn:{root.name}")
    raw = pd.read_csv(root / "chemprop_outer_scores.csv")
    times = pd.read_csv(root / "chemprop_outer_predictions.csv").groupby(
        ["task", "seed", "outer_fold"], as_index=False
    )["fit_predict_seconds"].first()
    raw = raw.merge(times, on=["task", "seed", "outer_fold"], validate="one_to_one")
    return normalize(raw, kind, f"chemprop_dmpnn:{root.name}")


def load_sources() -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    hom_inner, hom_outer = [], []
    for seed in SEEDS:
        i = pd.read_csv(HOM / f"seed_{seed}" / "inner_scores.csv")
        o = pd.read_csv(HOM / f"seed_{seed}" / "outer_candidate_scores.csv")
        i["seed"] = seed
        o["seed"] = seed
        hom_inner.append(i)
        hom_outer.append(o)
    hom_i = normalize(pd.concat(hom_inner, ignore_index=True), "inner", "homogeneous")
    hom_o = normalize(pd.concat(hom_outer, ignore_index=True), "outer", "homogeneous")

    base_i = normalize(pd.read_csv(MULTI / "inner_scores.csv"), "inner", "multiview_base")
    base_o = normalize(pd.read_csv(MULTI / "outer_candidate_scores.csv"), "outer", "multiview_base")

    new_i = normalize(load_csv_parts([OLD_NEW, NEW], "inner_scores.csv"), "inner", "new_nested_candidates")
    new_o = normalize(load_csv_parts([OLD_NEW, NEW], "outer_candidate_scores.csv"), "outer", "new_nested_candidates")
    new_i = new_i.drop_duplicates(["task", "seed", "outer_fold", "inner_fold", "candidate"], keep="last")
    new_o = new_o.drop_duplicates(["task", "seed", "outer_fold", "candidate"], keep="last")

    dmp_i = pd.concat([load_chemprop(path, "inner") for path in [OLD_CHEMPROP, NEW_CHEMPROP]], ignore_index=True)
    dmp_o = pd.concat([load_chemprop(path, "outer") for path in [OLD_CHEMPROP, NEW_CHEMPROP]], ignore_index=True)
    dmp_i = dmp_i.drop_duplicates(["task", "seed", "outer_fold", "inner_fold", "candidate"], keep="last")
    dmp_o = dmp_o.drop_duplicates(["task", "seed", "outer_fold", "candidate"], keep="last")
    for frame in (dmp_i, dmp_o):
        frame["representation"] = "dmpnn_graph"
        frame["family"] = "chemprop_dmpnn"

    return (
        {"hom": hom_i, "base": base_i, "new": new_i, "dmpnn": dmp_i},
        {"hom": hom_o, "base": base_o, "new": new_o, "dmpnn": dmp_o},
    )


def pool_orders() -> dict[str, list[str]]:
    classic = [f"{rep}__{family}" for family in CLASSIC_FAMILIES for rep in REPRESENTATIONS]
    modern_candidates = ["chemprop_dmpnn"] + [
        f"{rep}__{family}" for family in EMBEDDING_FAMILIES for rep in EMBEDDING_REPRESENTATIONS
    ]
    modern: list[str] = []
    for classical, contemporary in zip(classic[:16], modern_candidates):
        modern.extend([classical, contemporary])
    homogeneous = [PRIMARY_ANCHOR] + [f"hom::order{i:02d}" for i in range(1, 32)]
    if not (len(homogeneous) == len(classic) == len(modern) == 32):
        raise AssertionError("All frozen registries must contain 32 candidates")
    return {
        "Homogeneous Morgan": homogeneous,
        "Classical multiview": classic,
        "Modern-augmented": modern,
    }


def assemble_pools(
    inner_sources: dict[str, pd.DataFrame], outer_sources: dict[str, pd.DataFrame]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    orders = pool_orders()
    registries, inner_parts, outer_parts = [], [], []
    for pool, order in orders.items():
        if pool == "Homogeneous Morgan":
            anchor_i = inner_sources["base"].loc[inner_sources["base"].candidate.eq(PRIMARY_ANCHOR)].copy()
            anchor_o = outer_sources["base"].loc[outer_sources["base"].candidate.eq(PRIMARY_ANCHOR)].copy()
            old_i = inner_sources["hom"].loc[inner_sources["hom"].candidate_order.le(31)].copy()
            old_o = outer_sources["hom"].loc[outer_sources["hom"].candidate_order.le(31)].copy()
            old_i["candidate"] = old_i.candidate_order.map(lambda x: f"hom::order{int(x):02d}")
            old_o["candidate"] = old_o.candidate_order.map(lambda x: f"hom::order{int(x):02d}")
            inner = pd.concat([anchor_i, old_i], ignore_index=True)
            outer = pd.concat([anchor_o, old_o], ignore_index=True)
        elif pool == "Classical multiview":
            inner = pd.concat([inner_sources["base"], inner_sources["new"]], ignore_index=True)
            outer = pd.concat([outer_sources["base"], outer_sources["new"]], ignore_index=True)
        else:
            inner = pd.concat([inner_sources["base"], inner_sources["new"], inner_sources["dmpnn"]], ignore_index=True)
            outer = pd.concat([outer_sources["base"], outer_sources["new"], outer_sources["dmpnn"]], ignore_index=True)
        inner = inner.loc[inner.candidate.isin(order)].copy()
        outer = outer.loc[outer.candidate.isin(order)].copy()
        mapping = {candidate: index + 1 for index, candidate in enumerate(order)}
        inner["pool"] = pool
        outer["pool"] = pool
        inner["pool_order"] = inner.candidate.map(mapping)
        outer["pool_order"] = outer.candidate.map(mapping)
        if inner.pool_order.isna().any() or outer.pool_order.isna().any():
            raise ValueError(f"Unmapped candidate in {pool}")
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


def verify_balance(inner: pd.DataFrame, outer: pd.DataFrame) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    expected_inner_units = len(TASKS) * len(SEEDS) * 3 * 3
    expected_outer_units = len(TASKS) * len(SEEDS) * 3
    for pool in POOL_NAMES:
        for k in KS:
            i = inner.loc[inner.pool.eq(pool) & inner.pool_order.le(k)]
            o = outer.loc[outer.pool.eq(pool) & outer.pool_order.le(k)]
            checks[f"{pool}_K{k}_inner_rows"] = len(i) == expected_inner_units * k
            checks[f"{pool}_K{k}_outer_rows"] = len(o) == expected_outer_units * k
            complete_i = i.groupby(["task", "seed", "outer_fold", "inner_fold"]).candidate.nunique()
            complete_o = o.groupby(["task", "seed", "outer_fold"]).candidate.nunique()
            checks[f"{pool}_K{k}_inner_exact"] = bool((complete_i == k).all())
            checks[f"{pool}_K{k}_outer_exact"] = bool((complete_o == k).all())
    return checks


def external_anchor_table(outer_sources: dict[str, pd.DataFrame]) -> pd.DataFrame:
    base = outer_sources["base"].loc[
        outer_sources["base"].candidate.isin([PRIMARY_ANCHOR, SECONDARY_ANCHOR])
    ].copy()
    return base[["task", "task_type", "seed", "outer_fold", "candidate", "outer_utility"]]


def _selection_record(
    eligible_i: pd.DataFrame,
    eligible_o: pd.DataFrame,
    anchor_utility: float,
    anchor_name: str,
    pool: str,
    task: str,
    task_type: str,
    seed: int,
    outer_fold: int,
    k: int,
    design: str,
) -> dict[str, object]:
    stats = eligible_i.groupby(["candidate", "pool_order", "representation", "family"], as_index=False).agg(
        inner_mean=("inner_utility", "mean"), inner_sd=("inner_utility", "std"),
        inner_fit_seconds=("fit_seconds", "sum"),
    )
    stats = stats.sort_values(["inner_mean", "pool_order"], ascending=[False, True]).reset_index(drop=True)
    selected = stats.iloc[0]
    outer_sorted = eligible_o.sort_values(["outer_utility", "pool_order"], ascending=[False, True]).reset_index(drop=True)
    oracle = outer_sorted.iloc[0]
    selected_outer = eligible_o.loc[eligible_o.candidate.eq(selected.candidate)].iloc[0]
    top3 = set(stats.head(min(3, len(stats))).candidate)
    inner_oracle_rank = int(stats.index[stats.candidate.eq(oracle.candidate)][0]) + 1
    reciprocal_rank = 1.0 / inner_oracle_rank
    chance_mrr = sum(1.0 / j for j in range(1, k + 1)) / k
    oracle_gain = float(oracle.outer_utility - anchor_utility)
    selected_gain = float(selected_outer.outer_utility - anchor_utility)
    audit_seconds = float(eligible_i.fit_seconds.sum() + eligible_o.fit_seconds.sum())
    utility_range = float(eligible_o.outer_utility.max() - eligible_o.outer_utility.min())
    selection_loss = float(oracle.outer_utility - selected_outer.outer_utility)
    return {
        "design": design, "pool": pool, "task": task, "task_type": task_type,
        "seed": int(seed), "outer_fold": int(outer_fold), "candidate_count": int(k),
        "eligible_candidate_count": int(len(stats)), "anchor_scheme": anchor_name,
        "selected_candidate": selected.candidate, "selected_representation": selected.representation,
        "selected_family": selected.family, "oracle_candidate": oracle.candidate,
        "anchor_utility": float(anchor_utility), "selected_utility": float(selected_outer.outer_utility),
        "oracle_utility": float(oracle.outer_utility), "oracle_opportunity_gain": oracle_gain,
        "selected_model_gain": selected_gain,
        "same_unit_selection_gap": selection_loss,
        "outer_utility_range": utility_range,
        "range_normalized_selection_loss": selection_loss / (utility_range + EPSILON),
        "top3_hit": int(oracle.candidate in top3),
        "chance_adjusted_hit3": (int(oracle.candidate in top3) - min(3, k) / k) / (1 - min(3, k) / k)
        if k > 3 else np.nan,
        "inner_rank_of_outer_oracle": inner_oracle_rank, "reciprocal_rank": reciprocal_rank,
        "random_order_mrr_expectation": chance_mrr,
        # A one-candidate budget has chance MRR = 1, so chance adjustment is
        # mathematically undefined; retain the audit unit and mark only this
        # derived field missing instead of dividing by zero.
        "chance_adjusted_mrr": (
            (reciprocal_rank - chance_mrr) / (1 - chance_mrr)
            if abs(1 - chance_mrr) > EPSILON else np.nan
        ),
        "audit_fit_seconds": audit_seconds,
        "downstream_efficiency_per_second": selected_gain / max(audit_seconds, EPSILON),
        "selected_gain_per_audit_hour": selected_gain / max(audit_seconds / 3600, EPSILON),
        "opportunity_capture_fraction": selected_gain / oracle_gain if oracle_gain > EPSILON else np.nan,
    }


def selection_units(
    inner: pd.DataFrame,
    outer: pd.DataFrame,
    anchor_external: pd.DataFrame,
    anchor_scheme: str = "shared_morgan_linear",
    ks: list[int] | None = None,
    design: str = "equal_K",
) -> pd.DataFrame:
    if ks is None:
        ks = KS
    rows = []
    for key, outer_unit in outer.groupby(["pool", "task", "task_type", "seed", "outer_fold"]):
        pool, task, task_type, seed, outer_fold = key
        inner_unit = inner.loc[
            inner.pool.eq(pool) & inner.task.eq(task) & inner.seed.eq(seed) & inner.outer_fold.eq(outer_fold)
        ]
        for k in ks:
            eligible_o = outer_unit.loc[outer_unit.pool_order.le(k)].copy()
            eligible_i = inner_unit.loc[inner_unit.pool_order.le(k)].copy()
            if anchor_scheme == "registry_median":
                median_order = int(math.ceil(k / 2))
                anchor_row = eligible_o.loc[eligible_o.pool_order.eq(median_order)].iloc[0]
                anchor_name = f"registry_median_order_{median_order}"
                anchor_utility = float(anchor_row.outer_utility)
            else:
                candidate = PRIMARY_ANCHOR if anchor_scheme == "shared_morgan_linear" else SECONDARY_ANCHOR
                anchor_row = anchor_external.loc[
                    anchor_external.task.eq(task) & anchor_external.seed.eq(seed)
                    & anchor_external.outer_fold.eq(outer_fold) & anchor_external.candidate.eq(candidate)
                ]
                if len(anchor_row) != 1:
                    raise ValueError(f"Missing external anchor {candidate}: {task}/{seed}/{outer_fold}")
                anchor_name = anchor_scheme
                anchor_utility = float(anchor_row.iloc[0].outer_utility)
            rows.append(_selection_record(
                eligible_i, eligible_o, anchor_utility, anchor_name, pool, task, task_type,
                seed, outer_fold, k, design,
            ))
    return pd.DataFrame(rows)


def add_cross_fitted_gap(units: pd.DataFrame, outer: pd.DataFrame) -> pd.DataFrame:
    units = units.copy()
    units["cross_reference_candidate"] = ""
    units["cross_reference_utility"] = np.nan
    units["cross_fitted_selection_gap"] = np.nan
    for (design, pool, task, task_type, k), group in units.groupby(
        ["design", "pool", "task", "task_type", "candidate_count"]
    ):
        for held_seed in SEEDS:
            held_units = group.loc[group.seed.eq(held_seed)]
            eligible_names = set()
            for names in held_units.selected_candidate:
                eligible_names.add(names)
            candidate_outer = outer.loc[outer.pool.eq(pool) & outer.task.eq(task) & outer.pool_order.le(k)]
            train = candidate_outer.loc[~candidate_outer.seed.eq(held_seed)]
            reference = train.groupby("candidate").outer_utility.mean().sort_values(ascending=False).index[0]
            held_reference = candidate_outer.loc[
                candidate_outer.seed.eq(held_seed) & candidate_outer.candidate.eq(reference),
                ["outer_fold", "outer_utility"],
            ].set_index("outer_fold").outer_utility
            mask = (
                units.design.eq(design) & units.pool.eq(pool) & units.task.eq(task)
                & units.candidate_count.eq(k) & units.seed.eq(held_seed)
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
        "range_normalized_selection_loss",
        "chance_adjusted_hit3", "chance_adjusted_mrr", "cross_fitted_selection_gap",
        "audit_fit_seconds", "downstream_efficiency_per_second", "selected_gain_per_audit_hour",
        "opportunity_capture_fraction",
    ]
    for optional in [
        "homogeneous_normalized_oracle_opportunity",
        "homogeneous_normalized_selected_gain",
        "homogeneous_normalized_cross_fitted_gap",
    ]:
        if optional in units:
            metrics.append(optional)
    rows = []
    keys = ["design", "pool", "task", "task_type", "candidate_count", "anchor_scheme"]
    for key, group in units.groupby(keys):
        row = dict(zip(keys, key))
        for metric in metrics:
            seed_means = group.groupby("seed")[metric].mean().reindex(SEEDS).to_numpy(float)
            finite = seed_means[np.isfinite(seed_means)]
            row[f"{metric}_mean"] = float(np.mean(finite)) if len(finite) else np.nan
            row[f"{metric}_n_seed_blocks"] = int(len(finite))
            row[f"{metric}_n_outer_units"] = int(group[metric].notna().sum())
            if len(finite):
                draws = rng.choice(finite, size=(10000, len(finite)), replace=True).mean(axis=1)
                row[f"{metric}_low"] = float(np.quantile(draws, 0.025))
                row[f"{metric}_high"] = float(np.quantile(draws, 0.975))
            else:
                row[f"{metric}_low"] = row[f"{metric}_high"] = np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def _effective_rank(matrix: np.ndarray) -> dict[str, float]:
    keep = np.nanstd(matrix, axis=0) > EPSILON
    x = matrix[:, keep]
    if x.shape[1] <= 1:
        return {
            "entropy_rank": 1.0, "participation_rank": 1.0,
            "median_correlation": 1.0, "ledoit_wolf_shrinkage_alpha": np.nan,
            "eigenvalue_probability_json": "[1.0]",
        }
    sd = x.std(axis=0, ddof=1)
    z = (x - x.mean(axis=0)) / np.where(sd > EPSILON, sd, 1.0)
    estimator = LedoitWolf().fit(z)
    cov = estimator.covariance_
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
        "ledoit_wolf_shrinkage_alpha": float(estimator.shrinkage_),
        "eigenvalue_probability_json": json.dumps(p.tolist()),
    }


def effective_diversity(outer: pd.DataFrame, anchors: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (pool, task, task_type), group in outer.groupby(["pool", "task", "task_type"]):
        for k in KS:
            subset = group.loc[group.pool_order.le(k)]
            table = subset.pivot_table(index=["seed", "outer_fold"], columns="pool_order", values="outer_utility")
            matrix = table.to_numpy(float)
            index = table.index
            shared = anchors.loc[anchors.task.eq(task) & anchors.candidate.eq(PRIMARY_ANCHOR)].set_index(
                ["seed", "outer_fold"]
            ).reindex(index).outer_utility.to_numpy(float)
            rf = anchors.loc[anchors.task.eq(task) & anchors.candidate.eq(SECONDARY_ANCHOR)].set_index(
                ["seed", "outer_fold"]
            ).reindex(index).outer_utility.to_numpy(float)
            median_order = int(math.ceil(k / 2))
            registry_median = table[median_order].to_numpy(float)
            transforms = {
                "raw": matrix,
                "row_centred": matrix - matrix.mean(axis=1, keepdims=True),
                "shared_morgan_linear_relative": matrix - shared[:, None],
                "fixed_morgan_rf_relative": matrix - rf[:, None],
                "registry_median_relative": matrix - registry_median[:, None],
                "within_unit_rank": np.apply_along_axis(rankdata, 1, matrix),
            }
            for mode, values in transforms.items():
                metrics = _effective_rank(values)
                rows.append({
                    "pool": pool, "task": task, "task_type": task_type, "candidate_count": k,
                    "transformation": mode, "n_outer_units": matrix.shape[0],
                    "n_matrix_columns": values.shape[1], **metrics,
                    "relative_entropy_rank": metrics["entropy_rank"] / values.shape[1],
                })
    return pd.DataFrame(rows)


def selection_stability(units: pd.DataFrame, design_filter: str | None = "equal_K") -> pd.DataFrame:
    rows = []
    primary = units.loc[units.anchor_scheme.eq("shared_morgan_linear")].copy()
    if design_filter is not None:
        primary = primary.loc[primary.design.eq(design_filter)]
    for key, group in primary.groupby(["pool", "task", "task_type", "candidate_count"]):
        pool, task, task_type, k = key
        entropy_k = int(group.eligible_candidate_count.max()) if design_filter is None else int(k)
        candidate_freq = group.selected_candidate.value_counts(normalize=True)
        rep_freq = group.selected_representation.value_counts(normalize=True)
        family_freq = group.selected_family.value_counts(normalize=True)

        def raw_entropy(freq: pd.Series) -> float:
            p = freq.to_numpy(float)
            return float(-(p * np.log(p)).sum())

        def entropy(freq: pd.Series, denominator: int) -> float:
            h = raw_entropy(freq)
            return h / math.log(denominator) if denominator > 1 else 0.0

        agreements = []
        for held_seed in SEEDS:
            other_mode = group.loc[~group.seed.eq(held_seed)].selected_candidate.mode().iloc[0]
            agreements.extend(group.loc[group.seed.eq(held_seed)].selected_candidate.eq(other_mode).astype(float))
        switches = []
        for _, seed_group in group.groupby("seed"):
            ordered = seed_group.sort_values("outer_fold").selected_candidate.tolist()
            switches.append(sum(left != right for left, right in zip(ordered[:-1], ordered[1:])))
        rows.append({
            "pool": pool, "task": task, "task_type": task_type, "candidate_count": int(k),
            "candidate_selection_entropy": raw_entropy(candidate_freq),
            "candidate_selection_entropy_normalized": entropy(candidate_freq, entropy_k),
            "entropy_denominator_candidate_count": entropy_k,
            "representation_selection_entropy_normalized": entropy(rep_freq, max(2, group.selected_representation.nunique())),
            "family_selection_entropy_normalized": entropy(family_freq, max(2, group.selected_family.nunique())),
            "modal_candidate": candidate_freq.index[0], "modal_candidate_share": float(candidate_freq.iloc[0]),
            "leave_one_seed_out_agreement": float(np.mean(agreements)),
            "mean_adjacent_fold_switches_per_seed": float(np.mean(switches)),
            "max_adjacent_fold_switches": int(max(switches)),
        })
    return pd.DataFrame(rows)


def budget_effective_diversity(outer: pd.DataFrame, units: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (pool, task, task_type, nominal_k), group in units.groupby(
        ["pool", "task", "task_type", "candidate_count"]
    ):
        common_k = int(group.eligible_candidate_count.min())
        subset = outer.loc[
            outer.pool.eq(pool) & outer.task.eq(task) & outer.pool_order.le(common_k)
        ]
        matrix = subset.pivot_table(
            index=["seed", "outer_fold"], columns="pool_order", values="outer_utility"
        ).to_numpy(float)
        transforms = {
            "raw": matrix,
            "row_centred": matrix - matrix.mean(axis=1, keepdims=True),
            "within_unit_rank": np.apply_along_axis(rankdata, 1, matrix),
        }
        for mode, values in transforms.items():
            metrics = _effective_rank(values)
            rows.append({
                "pool": pool, "task": task, "task_type": task_type,
                "candidate_count": int(nominal_k), "common_prefix_candidate_count": common_k,
                "transformation": mode, "n_outer_units": matrix.shape[0], **metrics,
                "relative_entropy_rank": metrics["entropy_rank"] / max(common_k, 1),
                "definition_note": "effective rank of the candidate prefix common to all budget-matched outer units",
            })
    return pd.DataFrame(rows)


def selection_frequencies(units: pd.DataFrame) -> pd.DataFrame:
    primary = units.loc[units.anchor_scheme.eq("shared_morgan_linear") & units.design.eq("equal_K")]
    rows = []
    for key, group in primary.groupby(["pool", "task", "task_type", "candidate_count"]):
        base = dict(zip(["pool", "task", "task_type", "candidate_count"], key))
        for level, column in [
            ("candidate", "selected_candidate"),
            ("representation", "selected_representation"),
            ("learner_family", "selected_family"),
        ]:
            counts = group[column].value_counts(dropna=False)
            for value, count in counts.items():
                rows.append({
                    **base, "frequency_level": level, "selected_value": value,
                    "selected_count": int(count), "selected_proportion": float(count / len(group)),
                    "n_outer_units": int(len(group)),
                })
    return pd.DataFrame(rows)


def ablation_orders() -> dict[str, list[str]]:
    classic = pool_orders()["Classical multiview"]
    full = pool_orders()["Modern-augmented"]
    chemberta = [
        f"{rep}__{family}" for family in EMBEDDING_FAMILIES
        for rep in ["chemberta_mtr", "chemberta_mlm"]
    ]
    molformer = [f"molformer__{family}" for family in EMBEDDING_FAMILIES]

    def interleave_locked(additions: list[str]) -> list[str]:
        result = [classic[0]]
        classic_cursor = 1
        for addition in additions:
            result.append(classic[classic_cursor])
            result.append(addition)
            classic_cursor += 1
        result.extend(classic[classic_cursor: 32 - len(additions)])
        if len(result) != 32 or len(set(result)) != 32:
            raise AssertionError("Ablation registries must contain 32 unique candidates")
        return result

    return {
        "Classical multiview": classic,
        "+ChemBERTa": interleave_locked(chemberta),
        "+MoLFormer": interleave_locked(molformer),
        "+D-MPNN": interleave_locked(["chemprop_dmpnn"]),
        "Full modern-augmented": full,
    }


def assemble_ablation(inner_sources: dict[str, pd.DataFrame], outer_sources: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    all_i = pd.concat([inner_sources["base"], inner_sources["new"], inner_sources["dmpnn"]], ignore_index=True)
    all_o = pd.concat([outer_sources["base"], outer_sources["new"], outer_sources["dmpnn"]], ignore_index=True)
    inner_parts, outer_parts, registry_parts = [], [], []
    for pool, order in ablation_orders().items():
        mapping = {candidate: idx + 1 for idx, candidate in enumerate(order)}
        i = all_i.loc[all_i.candidate.isin(order)].copy()
        o = all_o.loc[all_o.candidate.isin(order)].copy()
        i["pool"] = pool
        o["pool"] = pool
        i["pool_order"] = i.candidate.map(mapping)
        o["pool_order"] = o.candidate.map(mapping)
        inner_parts.append(i)
        outer_parts.append(o)
        meta = i[["candidate", "representation", "family"]].drop_duplicates("candidate")
        meta["pool"] = pool
        meta["pool_order"] = meta.candidate.map(mapping)
        registry_parts.append(meta)
    return pd.concat(inner_parts), pd.concat(outer_parts), pd.concat(registry_parts)


def budget_matched_units(
    inner: pd.DataFrame, outer: pd.DataFrame, anchors: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    unit_cost = []
    for key, outer_unit in outer.groupby(["pool", "task", "task_type", "seed", "outer_fold"]):
        pool, task, task_type, seed, fold = key
        inner_unit = inner.loc[
            inner.pool.eq(pool) & inner.task.eq(task) & inner.seed.eq(seed) & inner.outer_fold.eq(fold)
        ]
        candidate_cost = inner_unit.groupby(["candidate", "pool_order"], as_index=False).fit_seconds.sum()
        candidate_cost = candidate_cost.merge(
            outer_unit[["candidate", "pool_order", "fit_seconds"]], on=["candidate", "pool_order"], validate="one_to_one"
        )
        candidate_cost["candidate_fit_seconds"] = candidate_cost.fit_seconds_x + candidate_cost.fit_seconds_y
        for k in ABLATION_KS:
            total = float(candidate_cost.loc[candidate_cost.pool_order.le(k), "candidate_fit_seconds"].sum())
            unit_cost.append({
                "pool": pool, "task": task, "task_type": task_type, "seed": int(seed),
                "outer_fold": int(fold), "candidate_count": k, "equal_k_fit_seconds": total,
            })
    cost_table = pd.DataFrame(unit_cost)
    thresholds = cost_table.loc[cost_table.pool.eq("Classical multiview")].groupby(
        ["task", "task_type", "candidate_count"], as_index=False
    ).equal_k_fit_seconds.median().rename(columns={"equal_k_fit_seconds": "budget_seconds"})

    rows = []
    for key, outer_unit in outer.groupby(["pool", "task", "task_type", "seed", "outer_fold"]):
        pool, task, task_type, seed, fold = key
        inner_unit = inner.loc[
            inner.pool.eq(pool) & inner.task.eq(task) & inner.seed.eq(seed) & inner.outer_fold.eq(fold)
        ]
        for k in ABLATION_KS:
            budget = float(thresholds.loc[
                thresholds.task.eq(task) & thresholds.candidate_count.eq(k), "budget_seconds"
            ].iloc[0])
            eligible_i = inner_unit.loc[inner_unit.pool_order.le(k)].copy()
            eligible_o = outer_unit.loc[outer_unit.pool_order.le(k)].copy()
            costs = eligible_i.groupby(["candidate", "pool_order"], as_index=False).fit_seconds.sum()
            costs = costs.merge(
                eligible_o[["candidate", "pool_order", "fit_seconds"]],
                on=["candidate", "pool_order"], validate="one_to_one",
            ).sort_values("pool_order")
            costs["candidate_fit_seconds"] = costs.fit_seconds_x + costs.fit_seconds_y
            costs["cumulative_seconds"] = costs.candidate_fit_seconds.cumsum()
            keep = costs.loc[costs.cumulative_seconds.le(budget), "candidate"].tolist()
            if not keep:
                keep = [costs.iloc[0].candidate]
            eligible_i = eligible_i.loc[eligible_i.candidate.isin(keep)]
            eligible_o = eligible_o.loc[eligible_o.candidate.isin(keep)]
            anchor = anchors.loc[
                anchors.task.eq(task) & anchors.seed.eq(seed) & anchors.outer_fold.eq(fold)
                & anchors.candidate.eq(PRIMARY_ANCHOR)
            ].iloc[0]
            record = _selection_record(
                eligible_i, eligible_o, float(anchor.outer_utility), "shared_morgan_linear",
                pool, task, task_type, seed, fold, len(keep), f"equal_budget_from_K{k}",
            )
            record["nominal_candidate_count"] = k
            record["eligible_candidate_count"] = len(keep)
            record["candidate_count"] = k
            record["budget_seconds"] = budget
            record["budget_utilization"] = record["audit_fit_seconds"] / max(budget, EPSILON)
            rows.append(record)
    return pd.DataFrame(rows), thresholds


def add_cross_fitted_budget_gap(units: pd.DataFrame, outer: pd.DataFrame) -> pd.DataFrame:
    units = units.copy()
    units["cross_reference_candidate"] = ""
    units["cross_reference_utility"] = np.nan
    units["cross_fitted_selection_gap"] = np.nan
    for index, row in units.iterrows():
        eligible = outer.loc[
            outer.pool.eq(row.pool) & outer.task.eq(row.task)
            & outer.pool_order.le(int(row.eligible_candidate_count))
        ]
        train = eligible.loc[~eligible.seed.eq(int(row.seed))]
        reference = train.groupby("candidate").outer_utility.mean().sort_values(ascending=False).index[0]
        held = eligible.loc[
            eligible.seed.eq(int(row.seed)) & eligible.outer_fold.eq(int(row.outer_fold))
            & eligible.candidate.eq(reference)
        ]
        if len(held) != 1:
            raise ValueError("Incomplete budget-matched cross-fitting reference")
        reference_utility = float(held.iloc[0].outer_utility)
        units.at[index, "cross_reference_candidate"] = reference
        units.at[index, "cross_reference_utility"] = reference_utility
        units.at[index, "cross_fitted_selection_gap"] = reference_utility - float(row.selected_utility)
    return units


def add_paired_homogeneous_normalization(units: pd.DataFrame) -> pd.DataFrame:
    units = units.copy()
    keys = ["design", "task", "seed", "outer_fold", "candidate_count", "anchor_scheme"]
    denom = units.loc[units.pool.eq("Homogeneous Morgan"), keys + ["oracle_opportunity_gain"]].rename(
        columns={"oracle_opportunity_gain": "paired_homogeneous_best_gain"}
    )
    if denom.duplicated(keys).any():
        raise ValueError("Paired homogeneous denominator is not unique")
    units = units.merge(denom, on=keys, how="left", validate="many_to_one")
    valid = units.paired_homogeneous_best_gain.abs().gt(EPSILON)
    units["homogeneous_normalized_selected_gain"] = np.where(
        valid, units.selected_model_gain / units.paired_homogeneous_best_gain, np.nan
    )
    units["homogeneous_normalized_oracle_opportunity"] = np.where(
        valid, units.oracle_opportunity_gain / units.paired_homogeneous_best_gain, np.nan
    )
    units["homogeneous_normalized_cross_fitted_gap"] = np.where(
        valid, units.cross_fitted_selection_gap / units.paired_homogeneous_best_gain, np.nan
    )
    units["homogeneous_denominator_valid"] = valid
    return units


def normalization_sensitivity(units: pd.DataFrame) -> pd.DataFrame:
    source = units.loc[units.design.eq("equal_K")].copy()
    anchors = source[["anchor_scheme", "task", "seed", "outer_fold", "anchor_utility"]].drop_duplicates()
    mad = anchors.groupby(["anchor_scheme", "task"]).anchor_utility.apply(
        lambda x: float(np.median(np.abs(x - np.median(x))))
    ).rename("endpoint_mad").reset_index()
    source = source.merge(mad, on=["anchor_scheme", "task"], how="left", validate="many_to_one")
    long_rows = []
    for _, row in source.iterrows():
        scales = {
            "raw": 1.0,
            "endpoint_MAD": float(row.endpoint_mad),
            "homogeneous_audit_best": float(row.paired_homogeneous_best_gain),
        }
        for normalization, scale in scales.items():
            valid = abs(scale) > EPSILON
            for metric in ["oracle_opportunity_gain", "selected_model_gain", "cross_fitted_selection_gap"]:
                value = float(row[metric])
                long_rows.append({
                    "anchor_scheme": row.anchor_scheme, "pool": row.pool, "task": row.task,
                    "task_type": row.task_type, "seed": int(row.seed), "outer_fold": int(row.outer_fold),
                    "candidate_count": int(row.candidate_count), "normalization": normalization,
                    "metric": metric, "raw_value": value, "scale": scale,
                    "normalized_value": value / scale if valid else np.nan,
                    "denominator_valid": valid, "epsilon": EPSILON,
                })
    long = pd.DataFrame(long_rows)
    rng = np.random.default_rng(RNG_SEED + 34)
    rows = []
    keys = ["anchor_scheme", "pool", "task", "task_type", "candidate_count", "normalization", "metric"]
    for key, group in long.groupby(keys):
        seed_means = group.groupby("seed").normalized_value.mean().reindex(SEEDS).to_numpy(float)
        finite = seed_means[np.isfinite(seed_means)]
        row = dict(zip(keys, key))
        row["normalized_mean"] = float(np.mean(finite)) if len(finite) else np.nan
        row["minimum_absolute_denominator"] = float(group.scale.abs().min())
        row["invalid_outer_units"] = int((~group.denominator_valid).sum())
        if len(finite):
            draws = rng.choice(finite, size=(10000, len(finite)), replace=True).mean(axis=1)
            row["normalized_low"] = float(np.quantile(draws, 0.025))
            row["normalized_high"] = float(np.quantile(draws, 0.975))
        else:
            row["normalized_low"] = row["normalized_high"] = np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def anchor_normalization_direction_concordance(table: pd.DataFrame) -> pd.DataFrame:
    source = table.loc[table.metric.eq("selected_model_gain")].copy()
    keys = ["pool", "task", "task_type", "candidate_count"]
    reference = source.loc[
        source.anchor_scheme.eq("shared_morgan_linear") & source.normalization.eq("raw"),
        keys + ["normalized_mean"],
    ].rename(columns={"normalized_mean": "reference_raw_mean"})
    rows = []
    for (anchor, normalization), group in source.groupby(["anchor_scheme", "normalization"]):
        merged = group.merge(reference, on=keys, validate="one_to_one")
        same = np.sign(merged.normalized_mean) == np.sign(merged.reference_raw_mean)
        rows.append({
            "anchor_scheme": anchor, "normalization": normalization,
            "same_direction_cells": int(same.sum()), "total_cells": int(len(same)),
            "direction_concordance": float(same.mean()),
            "invalid_summary_cells": int(merged.normalized_mean.isna().sum()),
            "reference": "shared Morgan linear anchor on raw endpoint scale",
        })
    return pd.DataFrame(rows)


def paired_pool_effects(units: pd.DataFrame) -> pd.DataFrame:
    rows = []
    metrics = [
        "oracle_opportunity_gain", "selected_model_gain", "cross_fitted_selection_gap",
        "chance_adjusted_hit3", "chance_adjusted_mrr",
    ]
    primary = units.loc[units.design.eq("equal_K") & units.anchor_scheme.eq("shared_morgan_linear")]
    baseline = "Homogeneous Morgan"
    for task in TASKS:
        for k in KS:
            base = primary.loc[primary.pool.eq(baseline) & primary.task.eq(task) & primary.candidate_count.eq(k)].set_index(
                ["seed", "outer_fold"]
            )
            for pool in ["Classical multiview", "Modern-augmented"]:
                comp = primary.loc[primary.pool.eq(pool) & primary.task.eq(task) & primary.candidate_count.eq(k)].set_index(
                    ["seed", "outer_fold"]
                )
                for metric in metrics:
                    delta = comp[metric] - base[metric]
                    seed_delta = delta.groupby("seed").mean()
                    rows.append({
                        "task": task, "candidate_count": k, "comparison": f"{pool} - {baseline}",
                        "metric": metric, "mean_paired_difference": float(seed_delta.mean()),
                        "positive_seed_means": int((seed_delta > 0).sum()),
                        "negative_seed_means": int((seed_delta < 0).sum()),
                    })
    return pd.DataFrame(rows)


def association_table(summary: pd.DataFrame, diversity: pd.DataFrame) -> pd.DataFrame:
    primary = summary.loc[
        summary.design.eq("equal_K") & summary.anchor_scheme.eq("shared_morgan_linear")
    ].merge(
        diversity.loc[diversity.transformation.eq("raw"),
                      ["pool", "task", "candidate_count", "entropy_rank", "relative_entropy_rank"]],
        on=["pool", "task", "candidate_count"], validate="one_to_one",
    )
    rows = []
    for metric in ["same_unit_selection_gap_mean", "cross_fitted_selection_gap_mean", "oracle_opportunity_gain_mean"]:
        result = spearmanr(primary.relative_entropy_rank, primary[metric])
        rows.append({
            "diversity_measure": "relative_entropy_rank", "outcome": metric,
            "spearman_rho": float(result.statistic), "p_value_descriptive": float(result.pvalue),
            "n_endpoint_pool_k_cells": int(len(primary)),
            "inference_unit_note": "descriptive cell-level association; not used as confirmatory endpoint inference",
        })
    return pd.DataFrame(rows)


def expansion_effects(units: pd.DataFrame) -> pd.DataFrame:
    source = units.loc[units.design.eq("equal_K")].copy()
    rows = []
    for key, group in source.groupby(["pool", "task", "task_type", "anchor_scheme"]):
        pool, task, task_type, anchor_scheme = key
        seed_k = group.groupby(["seed", "candidate_count"]).cross_fitted_selection_gap.mean().unstack()
        if 4 not in seed_k or 32 not in seed_k:
            continue
        delta = seed_k[32] - seed_k[4]
        rows.append({
            "pool": pool, "task": task, "task_type": task_type, "anchor_scheme": anchor_scheme,
            "K_high": 32, "K_low": 4, "delta_CF_endpoint": float(delta.mean()),
            "positive_seed_deltas": int((delta > 0).sum()), "negative_seed_deltas": int((delta < 0).sum()),
            "seed_11": float(delta.get(11, np.nan)), "seed_23": float(delta.get(23, np.nan)),
            "seed_37": float(delta.get(37, np.nan)), "seed_53": float(delta.get(53, np.nan)),
            "seed_71": float(delta.get(71, np.nan)),
        })
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    inner_sources, outer_sources = load_sources()
    inner, outer, registry = assemble_pools(inner_sources, outer_sources)
    checks = verify_balance(inner, outer)
    failed = [key for key, value in checks.items() if not value]
    if failed:
        raise RuntimeError(f"Balance audit failed: {failed}")
    anchors = external_anchor_table(outer_sources)

    primary_units = selection_units(inner, outer, anchors, "shared_morgan_linear")
    primary_units = add_cross_fitted_gap(primary_units, outer)
    anchor_units = [primary_units]
    for scheme in ["fixed_morgan_rf", "registry_median"]:
        sensitivity = selection_units(inner, outer, anchors, scheme)
        sensitivity = add_cross_fitted_gap(sensitivity, outer)
        anchor_units.append(sensitivity)
    units = add_paired_homogeneous_normalization(pd.concat(anchor_units, ignore_index=True))
    summary = bootstrap_summary(units)
    diversity = effective_diversity(outer, anchors)
    stability = selection_stability(units)
    frequencies = selection_frequencies(units)
    paired = paired_pool_effects(units)
    associations = association_table(summary, diversity)
    expansion = expansion_effects(units)
    normalization = normalization_sensitivity(units)
    direction_sensitivity = anchor_normalization_direction_concordance(normalization)

    ablation_i, ablation_o, ablation_registry = assemble_ablation(inner_sources, outer_sources)
    ablation_units = selection_units(
        ablation_i, ablation_o, anchors, "shared_morgan_linear", ks=ABLATION_KS, design="component_ablation"
    )
    ablation_units = add_cross_fitted_gap(ablation_units, ablation_o)
    ablation_summary = bootstrap_summary(ablation_units)
    ablation_diversity = effective_diversity(ablation_o, anchors)
    ablation_diversity = ablation_diversity.loc[ablation_diversity.candidate_count.isin(ABLATION_KS)].copy()
    ablation_frequency = (
        ablation_units.groupby(
            ["pool", "task", "task_type", "candidate_count", "selected_representation", "selected_family"],
            as_index=False,
        ).size().rename(columns={"size": "selected_count"})
    )
    ablation_frequency["selected_proportion"] = ablation_frequency.selected_count / 15.0

    budget_units, budget_thresholds = budget_matched_units(inner, outer, anchors)
    budget_units = add_cross_fitted_budget_gap(budget_units, outer)
    budget_units = add_paired_homogeneous_normalization(budget_units)
    budget_summary = bootstrap_summary(budget_units)
    budget_stability = selection_stability(budget_units, design_filter=None)
    budget_diversity = budget_effective_diversity(outer, budget_units)

    exports = {
        "Paper31_candidate_registry.csv": registry,
        "Paper31_inner_scores.csv.gz": inner,
        "Paper31_outer_candidate_scores.csv.gz": outer,
        "Paper31_selection_units.csv": units,
        "Paper31_endpoint_pool_K_summary.csv": summary,
        "Paper31_effective_diversity_sensitivity.csv": diversity,
        "Paper31_selection_stability.csv": stability,
        "Paper31_selection_frequencies.csv": frequencies,
        "Paper31_paired_pool_effects.csv": paired,
        "Paper31_diversity_outcome_associations.csv": associations,
        "Paper31_cross_fitted_expansion_effects.csv": expansion,
        "Paper31_anchor_normalization_sensitivity.csv": normalization,
        "Paper31_anchor_normalization_direction_concordance.csv": direction_sensitivity,
        "Paper31_ablation_registry.csv": ablation_registry,
        "Paper31_component_ablation_units.csv": ablation_units,
        "Paper31_component_ablation_summary.csv": ablation_summary,
        "Paper31_component_ablation_diversity.csv": ablation_diversity,
        "Paper31_component_ablation_selection_frequency.csv": ablation_frequency,
        "Paper31_equal_budget_units.csv": budget_units,
        "Paper31_equal_budget_summary.csv": budget_summary,
        "Paper31_equal_budget_thresholds.csv": budget_thresholds,
        "Paper31_equal_budget_selection_stability.csv": budget_stability,
        "Paper31_equal_budget_effective_diversity.csv": budget_diversity,
    }
    for filename, frame in exports.items():
        kwargs = {"compression": "gzip"} if filename.endswith(".gz") else {}
        frame.to_csv(OUT / filename, index=False, **kwargs)

    audit = {
        "status": "complete",
        "frozen_design": {
            "tasks": TASKS, "seeds": SEEDS, "outer_folds": 3, "inner_folds": 3,
            "candidate_counts": KS, "primary_anchor": PRIMARY_ANCHOR,
            "secondary_anchor": SECONDARY_ANCHOR, "epsilon": EPSILON,
            "primary_normalization": "paired outer-unit homogeneous audit-best opportunity gain",
            "equation_22_24_level": "paired outer-unit denominator, followed by fold-to-seed-to-endpoint aggregation",
            "near_zero_denominator_rule": f"set normalized value to missing when absolute denominator <= {EPSILON}",
            "uncertainty": "outer-fold effects averaged within seed; five seeds are bootstrap blocks",
            "no_cell_pseudoreplication": True,
            "ablation_rule": "fixed locked tail replacement, defined before expanded outcomes were read",
            "budget_rule": "locked registry prefix under median Classical-multiview downstream audit time per endpoint/K",
        },
        "balance_checks": checks,
        "rows": {filename: int(len(frame)) for filename, frame in exports.items()},
        "source_scope": {
            "pretrained_encoders": "frozen cached embeddings; encoder pretraining excluded",
            "downstream_budget": "measured inner-plus-outer fit/predict wall time",
            "dmpnn": "one-epoch nested Chemprop D-MPNN downstream fit",
            "execution_device": "CPU; locally installed PyTorch build had no CUDA support",
            "logical_processor_count": os.cpu_count(),
        },
    }
    (OUT / "Paper31_expanded_intervention_audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(audit, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
