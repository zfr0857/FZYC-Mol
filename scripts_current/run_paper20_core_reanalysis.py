from __future__ import annotations

import hashlib
import itertools
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata, t
from sklearn.covariance import LedoitWolf


ROOT = Path("D:/fzyc")
BASE = Path(os.environ.get("FZYC_PREFIX_BASE", ROOT / "results" / "nested_selection" / "repeated_nested"))
MULTI = Path(os.environ.get("FZYC_MULTIVIEW_BASE", ROOT / "results" / "reviewer_core_20260624" / "multiview_nested"))
OUT = Path(os.environ.get("FZYC_CORE_OUT", ROOT / "output" / "paper20_candidate_pool_audit_20260712"))
SEEDS = [11, 23, 37, 53, 71]
KS = [4, 8, 16, 32]
N_HIER = 100
N_BOOT = 10000
RNG_SEED = 20260712


def load_seed_csv(name: str) -> pd.DataFrame:
    frames = []
    for seed in SEEDS:
        frame = pd.read_csv(BASE / f"seed_{seed}" / name).rename(columns={"dataset": "task"})
        if "seed" not in frame:
            frame.insert(0, "seed", seed)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def frame_hash(frame: pd.DataFrame, columns: list[str]) -> str:
    stable = frame[columns].sort_values(columns).to_csv(index=False, float_format="%.15g")
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def corr_from_cov(cov: np.ndarray) -> np.ndarray:
    scale = np.sqrt(np.clip(np.diag(cov), 1e-15, None))
    corr = np.clip(cov / np.outer(scale, scale), -1.0, 1.0)
    np.fill_diagonal(corr, 1.0)
    return corr


def rank_metrics(corr: np.ndarray) -> dict[str, float]:
    eig = np.clip(np.linalg.eigvalsh(corr), 0.0, None)
    total = float(eig.sum())
    p = eig / total if total > 0 else np.ones_like(eig) / len(eig)
    p = p[p > 1e-15]
    off = corr[np.triu_indices_from(corr, k=1)]
    return {
        "entropy_rank": float(np.exp(-(p * np.log(p)).sum())),
        "participation_rank": float(total * total / np.square(eig).sum()),
        "median_correlation": float(np.median(off)) if len(off) else 1.0,
    }


def matrix_metrics(x: np.ndarray, shrinkage: bool) -> dict[str, float]:
    x = np.asarray(x, dtype=float)
    keep = np.nanstd(x, axis=0) > 1e-12
    x = x[:, keep]
    if x.shape[1] <= 1:
        return {"entropy_rank": 1.0, "participation_rank": 1.0, "median_correlation": 1.0}
    if shrinkage:
        sd = x.std(axis=0, ddof=1)
        z = (x - x.mean(axis=0)) / np.where(sd > 1e-12, sd, 1.0)
        corr = corr_from_cov(LedoitWolf().fit(z).covariance_)
    else:
        corr = np.nan_to_num(np.corrcoef(x, rowvar=False), nan=0.0)
        np.fill_diagonal(corr, 1.0)
    return rank_metrics(corr)


def transform_matrix(x: np.ndarray, mode: str) -> np.ndarray:
    if mode == "raw":
        return x
    if mode == "row_centred":
        return x - x.mean(axis=1, keepdims=True)
    if mode == "fixed_reference_relative":
        return x[:, 1:] - x[:, [0]]
    if mode == "within_unit_rank":
        return np.apply_along_axis(rankdata, 1, x)
    raise ValueError(mode)


def hierarchical_sample(frame: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
    sampled = []
    for seed in rng.choice(SEEDS, len(SEEDS), replace=True):
        unit = frame.loc[frame["seed"].eq(seed)]
        rows = rng.choice(unit.index.to_numpy(), 3, replace=True)
        sampled.append(unit.loc[rows].drop(columns=["seed", "outer_fold"]).to_numpy(float))
    return np.vstack(sampled)


def effective_diversity(outer: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(RNG_SEED)
    point_rows, sensitivity_rows, boot_rows = [], [], []
    modes = ["raw", "row_centred", "fixed_reference_relative", "within_unit_rank"]
    for task in sorted(outer["task"].unique()):
        task_type = outer.loc[outer["task"].eq(task), "task_type"].iloc[0]
        for k in KS:
            matrix = outer.loc[outer["task"].eq(task) & outer["candidate_order"].le(k)].pivot_table(
                index=["seed", "outer_fold"], columns="candidate_order", values="outer_utility"
            ).reset_index()
            raw = matrix.drop(columns=["seed", "outer_fold"]).to_numpy(float)
            for mode in modes:
                x = transform_matrix(raw, mode)
                empirical = matrix_metrics(x, False)
                shrinkage = matrix_metrics(x, True)
                draws = {name: [] for name in shrinkage}
                for b in range(N_HIER):
                    sampled = hierarchical_sample(matrix, rng)
                    metrics = matrix_metrics(transform_matrix(sampled, mode), True)
                    for name, value in metrics.items():
                        draws[name].append(value)
                        boot_rows.append({
                            "task": task, "candidate_count": k, "transformation": mode,
                            "bootstrap": b, "metric": name, "value": value,
                        })
                row = {
                    "task": task, "task_type": task_type, "candidate_count": k,
                    "transformation": mode, "n_outer_units": len(matrix),
                    "n_matrix_columns": x.shape[1],
                }
                for name in empirical:
                    row[f"empirical_{name}"] = empirical[name]
                    row[f"shrinkage_{name}"] = shrinkage[name]
                    row[f"hierarchical_ci95_low_{name}"] = float(np.quantile(draws[name], 0.025))
                    row[f"hierarchical_ci95_high_{name}"] = float(np.quantile(draws[name], 0.975))
                point_rows.append(row)
                if k == 32:
                    for omission_type, values, column in [
                        ("seed", SEEDS, "seed"), ("outer_fold", [1, 2, 3], "outer_fold")
                    ]:
                        for omitted in values:
                            sub = matrix.loc[~matrix[column].eq(omitted)].drop(columns=["seed", "outer_fold"]).to_numpy(float)
                            metrics = matrix_metrics(transform_matrix(sub, mode), True)
                            sensitivity_rows.append({
                                "task": task, "task_type": task_type, "transformation": mode,
                                "omission_type": omission_type, "omitted": omitted, **metrics,
                            })
    point = pd.DataFrame(point_rows)
    boot = pd.DataFrame(boot_rows)
    summary_rows = []
    for (k, mode), group in point.groupby(["candidate_count", "transformation"]):
        row = {"candidate_count": k, "transformation": mode, "n_endpoints": len(group)}
        for metric in ["entropy_rank", "participation_rank", "median_correlation"]:
            values = group[f"shrinkage_{metric}"].to_numpy(float)
            row[f"endpoint_median_{metric}"] = float(np.median(values))
            row[f"endpoint_q25_{metric}"] = float(np.quantile(values, 0.25))
            row[f"endpoint_q75_{metric}"] = float(np.quantile(values, 0.75))
            row[f"endpoint_min_{metric}"] = float(np.min(values))
            row[f"endpoint_max_{metric}"] = float(np.max(values))
            row[f"overall_inferential_interval_status_{metric}"] = "not estimated; endpoints are not treated as a random sample"
        summary_rows.append(row)
    return point, pd.DataFrame(sensitivity_rows), pd.DataFrame(summary_rows)


def clustered_interval(seed_values: pd.Series, rng: np.random.Generator) -> tuple[float, float]:
    values = seed_values.reindex(SEEDS).to_numpy(float)
    draws = rng.choice(values, size=(N_BOOT, len(values)), replace=True).mean(axis=1)
    return float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def audit_decomposition(outer: pd.DataFrame, policy: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    selected = policy.loc[policy["policy"].eq("validation_best") & policy["pool_size"].isin(KS),
        ["task", "task_type", "seed", "outer_fold", "pool_size", "selected_candidate", "outer_utility"]
    ].rename(columns={"pool_size": "candidate_count", "outer_utility": "selected_utility"})
    fixed = outer.loc[outer["candidate_order"].eq(1), ["task", "seed", "outer_fold", "outer_utility"]].rename(
        columns={"outer_utility": "fixed_reference_utility"}
    )
    best_rows = []
    for k in KS:
        sub = outer.loc[outer["candidate_order"].le(k)]
        best = sub.groupby(["task", "seed", "outer_fold"], as_index=False)["outer_utility"].max()
        best["candidate_count"] = k
        best_rows.append(best.rename(columns={"outer_utility": "observed_audit_best_utility"}))
    units = selected.merge(fixed, on=["task", "seed", "outer_fold"]).merge(
        pd.concat(best_rows), on=["task", "seed", "outer_fold", "candidate_count"]
    )
    units["observed_audit_best_gain"] = units["observed_audit_best_utility"] - units["fixed_reference_utility"]
    units["selected_model_gain"] = units["selected_utility"] - units["fixed_reference_utility"]
    units["incremental_observed_audit_gap"] = units["observed_audit_best_utility"] - units["selected_utility"]
    units["realization_ratio"] = np.where(
        units["observed_audit_best_gain"] > 1e-12,
        units["selected_model_gain"] / units["observed_audit_best_gain"], np.nan,
    )
    summary = units.groupby(["task_type", "candidate_count"], as_index=False).agg(
        n_outer_units=("task", "size"),
        mean_observed_audit_best_gain=("observed_audit_best_gain", "mean"),
        mean_selected_model_gain=("selected_model_gain", "mean"),
        mean_incremental_observed_audit_gap=("incremental_observed_audit_gap", "mean"),
        median_realization_ratio=("realization_ratio", "median"),
    )
    return units, summary


def cross_fitted_reference(outer: pd.DataFrame, policy: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    selected = policy.loc[policy["policy"].eq("validation_best") & policy["pool_size"].isin(KS),
        ["task", "task_type", "seed", "outer_fold", "pool_size", "selected_candidate", "outer_utility"]
    ].rename(columns={"pool_size": "candidate_count", "outer_utility": "selected_utility"})
    rows = []
    for task in sorted(outer["task"].unique()):
        for k in KS:
            for held_seed in SEEDS:
                train = outer.loc[outer["task"].eq(task) & ~outer["seed"].eq(held_seed) & outer["candidate_order"].le(k)]
                means = train.groupby("candidate_order", as_index=False)["outer_utility"].mean().sort_values(
                    ["outer_utility", "candidate_order"], ascending=[False, True]
                )
                reference_order = int(means.iloc[0]["candidate_order"])
                reference_candidate = train.loc[train["candidate_order"].eq(reference_order), "candidate"].iloc[0]
                held = outer.loc[
                    outer["task"].eq(task) & outer["seed"].eq(held_seed) & outer["candidate_order"].le(k)
                ]
                audit_best = held.groupby("outer_fold", as_index=False)["outer_utility"].max().rename(
                    columns={"outer_utility": "observed_audit_best_utility"}
                )
                reference = held.loc[held["candidate_order"].eq(reference_order), ["outer_fold", "outer_utility"]].rename(
                    columns={"outer_utility": "cross_fitted_reference_utility"}
                )
                sel = selected.loc[
                    selected["task"].eq(task) & selected["seed"].eq(held_seed) & selected["candidate_count"].eq(k)
                ]
                merged = sel.merge(audit_best, on="outer_fold").merge(reference, on="outer_fold")
                merged["cross_fitted_reference_order"] = reference_order
                merged["cross_fitted_reference_candidate"] = reference_candidate
                merged["same_unit_gap"] = merged["observed_audit_best_utility"] - merged["selected_utility"]
                merged["cross_fitted_gap"] = merged["cross_fitted_reference_utility"] - merged["selected_utility"]
                merged["reference_difference"] = merged["observed_audit_best_utility"] - merged["cross_fitted_reference_utility"]
                rows.append(merged)
    units = pd.concat(rows, ignore_index=True)
    endpoint = units.groupby(["task", "task_type", "candidate_count"], as_index=False).agg(
        mean_same_unit_gap=("same_unit_gap", "mean"),
        mean_cross_fitted_gap=("cross_fitted_gap", "mean"),
        mean_reference_difference=("reference_difference", "mean"),
        positive_cross_fitted_units=("cross_fitted_gap", lambda x: int((x > 0).sum())),
    )
    rng = np.random.default_rng(RNG_SEED + 2)
    effects = []
    for (task, task_type), group in units.groupby(["task", "task_type"]):
        seed_k = group.groupby(["seed", "candidate_count"])[["same_unit_gap", "cross_fitted_gap", "reference_difference"]].mean().unstack()
        row = {"task": task, "task_type": task_type}
        for metric in ["same_unit_gap", "cross_fitted_gap", "reference_difference"]:
            delta = seed_k[metric][32] - seed_k[metric][4]
            low, high = clustered_interval(delta, rng)
            row[f"k32_minus_k4_{metric}"] = delta.mean()
            row[f"seed_clustered_ci95_low_{metric}"] = low
            row[f"seed_clustered_ci95_high_{metric}"] = high
            row[f"positive_seed_means_{metric}"] = int((delta > 0).sum())
        effects.append(row)
    return units, endpoint, pd.DataFrame(effects)


def evaluate_multiview_pool(inner: pd.DataFrame, outer: pd.DataFrame, pool_name: str,
                            orders: list[int], group: str, composition: str) -> pd.DataFrame:
    inn = inner.loc[inner["candidate_order"].isin(orders)]
    means = inn.groupby(
        ["task", "task_type", "seed", "outer_fold", "candidate_order", "candidate", "representation", "family"],
        as_index=False,
    )["inner_utility"].mean()
    chosen = means.sort_values(
        ["task", "seed", "outer_fold", "inner_utility", "candidate_order"],
        ascending=[True, True, True, False, True],
    ).groupby(["task", "seed", "outer_fold"], as_index=False).first()
    out = outer[["task", "seed", "outer_fold", "candidate_order", "outer_utility"]]
    chosen = chosen.merge(out, on=["task", "seed", "outer_fold", "candidate_order"], how="left")
    chosen["pool_name"] = pool_name
    chosen["analysis_group"] = group
    chosen["pool_size"] = len(orders)
    chosen["composition"] = composition
    return chosen


def multiview_matched_k() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    inner = pd.read_csv(MULTI / "inner_scores.csv")
    outer = pd.read_csv(MULTI / "outer_candidate_scores.csv")
    reps = ["morgan512", "maccs", "rdkit2d", "multiview"]
    families = ["linear", "random_forest", "lightgbm"]
    lookup = inner[["representation", "family", "candidate_order"]].drop_duplicates()

    def orders_for(rep_set: list[str], family_set: list[str] = families) -> list[int]:
        use = lookup.loc[lookup["representation"].isin(rep_set) & lookup["family"].isin(family_set)]
        return sorted(use["candidate_order"].astype(int).unique().tolist())

    pools = []
    ladder = [
        ("ladder_K3", reps[:1]), ("ladder_K6", reps[:2]),
        ("ladder_K9", reps[:3]), ("ladder_K12", reps[:4]),
    ]
    for name, rep_set in ladder:
        pools.append(evaluate_multiview_pool(inner, outer, name, orders_for(rep_set), "incremental_ladder", "+".join(rep_set)))
    for n in [2, 3]:
        for combo in itertools.combinations(reps, n):
            name = f"matched_K{3*n}_" + "_".join(combo)
            pools.append(evaluate_multiview_pool(inner, outer, name, orders_for(list(combo)), f"matched_K{3*n}", "+".join(combo)))
    non_morgan = reps[1:]
    for i, perm in enumerate(itertools.permutations(non_morgan), start=1):
        orders = []
        labels = []
        for family, rep in zip(families, perm):
            order = int(lookup.loc[lookup["family"].eq(family) & lookup["representation"].eq(rep), "candidate_order"].iloc[0])
            orders.append(order)
            labels.append(f"{family}:{rep}")
        pools.append(evaluate_multiview_pool(inner, outer, f"matched_K3_alt_{i}", orders, "matched_K3", ";".join(labels)))
    pools.append(evaluate_multiview_pool(inner, outer, "matched_K3_morgan", orders_for(["morgan512"]), "matched_K3", "morgan512 across three learners"))
    for family in families:
        pools.append(evaluate_multiview_pool(inner, outer, f"within_{family}_K4", orders_for(reps, [family]), "within_learner", f"four representations; {family}"))
    units = pd.concat(pools, ignore_index=True)

    baselines = units.loc[units["pool_name"].isin(["matched_K3_morgan", "ladder_K3"]),
        ["task", "seed", "outer_fold", "pool_name", "outer_utility"]
    ].drop_duplicates(["task", "seed", "outer_fold"]).rename(columns={"outer_utility": "morgan_k3_utility"})
    comparisons = units.merge(baselines[["task", "seed", "outer_fold", "morgan_k3_utility"]], on=["task", "seed", "outer_fold"])
    comparisons["gain_vs_morgan_k3"] = comparisons["outer_utility"] - comparisons["morgan_k3_utility"]
    morgan_family = outer.loc[outer["representation"].eq("morgan512"),
        ["task", "seed", "outer_fold", "family", "outer_utility"]
    ].rename(columns={"outer_utility": "same_learner_morgan_utility"})
    comparisons = comparisons.merge(morgan_family, on=["task", "seed", "outer_fold", "family"], how="left")
    comparisons["comparison_reference"] = np.where(
        comparisons["analysis_group"].eq("within_learner"), "same-learner Morgan candidate", "Morgan K = 3 pool"
    )
    comparisons["comparison_reference_utility"] = np.where(
        comparisons["analysis_group"].eq("within_learner"),
        comparisons["same_learner_morgan_utility"], comparisons["morgan_k3_utility"],
    )
    comparisons["representation_composition_effect"] = comparisons["outer_utility"] - comparisons["comparison_reference_utility"]
    summary = comparisons.groupby(["analysis_group", "pool_name", "pool_size", "composition", "task", "task_type"], as_index=False).agg(
        mean_selected_utility=("outer_utility", "mean"),
        mean_gain_vs_morgan_k3=("gain_vs_morgan_k3", "mean"),
        mean_representation_composition_effect=("representation_composition_effect", "mean"),
        positive_outer_units=("gain_vs_morgan_k3", lambda x: int((x > 0).sum())),
    )
    frequency = units.groupby(["analysis_group", "pool_name", "representation", "family"], as_index=False).size().rename(columns={"size": "selection_count"})
    return comparisons, summary, frequency


def multiview_verification() -> tuple[pd.DataFrame, dict[str, object]]:
    policy = pd.read_csv(MULTI / "policy_detail.csv")
    use = policy.loc[policy["policy"].eq("validation_best") & policy["variant"].isin(["morgan_only", "full_multiview"])]
    wide = use.pivot_table(
        index=["task", "task_type", "seed", "outer_fold"], columns="variant", values=["outer_utility", "selected_candidate"] , aggfunc="first"
    )
    wide.columns = ["_".join(col) for col in wide.columns]
    wide = wide.reset_index().rename(columns={
        "outer_utility_morgan_only": "morgan_utility", "outer_utility_full_multiview": "multiview_utility",
        "selected_candidate_morgan_only": "morgan_selected_candidate", "selected_candidate_full_multiview": "multiview_selected_candidate",
    })
    wide["paired_gain"] = wide["multiview_utility"] - wide["morgan_utility"]
    rng = np.random.default_rng(RNG_SEED + 4)
    rows = []
    for (task, task_type), group in wide.groupby(["task", "task_type"]):
        seed_means = group.groupby("seed")["paired_gain"].mean().reindex(SEEDS)
        low, high = clustered_interval(seed_means, rng)
        mean = seed_means.mean()
        sem = seed_means.std(ddof=1) / np.sqrt(len(seed_means))
        critical = t.ppf(0.975, len(seed_means) - 1)
        loo = [seed_means.drop(index=seed).mean() for seed in SEEDS]
        rows.append({
            "task": task, "task_type": task_type, "mean_paired_gain": mean,
            "seed_clustered_ci95_low": low, "seed_clustered_ci95_high": high,
            "t_ci95_low": mean - critical * sem, "t_ci95_high": mean + critical * sem,
            "leave_one_seed_min": min(loo), "leave_one_seed_max": max(loo),
            "exact_zero_width_seed_interval": bool(seed_means.max() == seed_means.min()),
        })
    audit = {
        "source_file_sha256": {
            name: sha256(MULTI / name) for name in ["inner_scores.csv", "outer_candidate_scores.csv", "policy_detail.csv", "candidate_registry.csv", "run_manifest.json"]
        },
        "split_key_sha256": frame_hash(wide, ["task", "seed", "outer_fold"]),
        "paired_score_sha256": frame_hash(wide, ["task", "seed", "outer_fold", "morgan_utility", "multiview_utility", "paired_gain"]),
        "prediction_hash": "requires source data: candidate-level prediction exports are not present in the multiview result directory",
        "n_units": len(wide), "n_endpoints": wide["task"].nunique(), "seeds": SEEDS, "outer_folds": [1, 2, 3],
    }
    return pd.DataFrame(rows), audit


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    outer = load_seed_csv("outer_candidate_scores.csv")
    policy = load_seed_csv("policy_detail.csv")
    diversity, diversity_sensitivity, diversity_summary = effective_diversity(outer)
    decomposition_units, decomposition_summary = audit_decomposition(outer, policy)
    cross_units, cross_endpoint, cross_effects = cross_fitted_reference(outer, policy)
    matched_units, matched_summary, matched_frequency = multiview_matched_k()
    multi_verify, hash_audit = multiview_verification()
    outputs = {
        "utility_pattern_diversity_endpoint.csv": diversity,
        "utility_pattern_diversity_sensitivity.csv": diversity_sensitivity,
        "utility_pattern_diversity_summary.csv": diversity_summary,
        "audit_gap_decomposition_units.csv": decomposition_units,
        "audit_gap_decomposition_summary.csv": decomposition_summary,
        "cross_fitted_reference_units.csv": cross_units,
        "cross_fitted_reference_endpoint.csv": cross_endpoint,
        "cross_fitted_k32_minus_k4.csv": cross_effects,
        "matched_k_multiview_units.csv": matched_units,
        "matched_k_multiview_summary.csv": matched_summary,
        "matched_k_selection_frequency.csv": matched_frequency,
        "multiview_zero_width_verification.csv": multi_verify,
    }
    for name, frame in outputs.items():
        frame.to_csv(OUT / name, index=False)
    audit = {
        "analysis_label": "retrospective candidate-pool audit core reanalysis",
        "hierarchical_bootstrap_replicates": N_HIER,
        "seed_clustered_bootstrap_replicates": N_BOOT,
        "candidate_pool_sizes": KS,
        "seeds": SEEDS,
        "outer_folds": [1, 2, 3],
        "forbidden_claims": ["test oracle", "true oracle", "true attainable upper bound", "independent confirmation"],
        "multiview_verification": hash_audit,
        "outputs": {name: {"rows": len(frame), "sha256": sha256(OUT / name)} for name, frame in outputs.items()},
    }
    (OUT / "core_reanalysis_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(OUT), "files": list(outputs), "audit": "core_reanalysis_audit.json"}, indent=2))


if __name__ == "__main__":
    main()
