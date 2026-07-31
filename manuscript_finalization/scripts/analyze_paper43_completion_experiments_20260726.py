from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
import sklearn
from scipy.stats import spearmanr


ROOT = Path(r"D:\fzyc")
OUT = ROOT / "output" / "paper43_jcheminform_completion_20260726"
TABLES = OUT / "additional_files" / "tables"
FIGURES = OUT / "figures"
SOURCE = OUT / "source_data"
OLD_ROOT = ROOT / "results" / "nested_selection" / "repeated_nested"
METRIC_ROOT = ROOT / "results" / "paper43_metric_rerun"
REGRESSION_RERUN_ROOT = ROOT / "results" / "paper43_regression_split_rerun"
NEW_ROOT = ROOT / "results" / "paper43_additional_seeds"
OLD_SEEDS = [11, 23, 37, 53, 71]
NEW_SEEDS = [83, 97, 113, 127, 149]
SEEDS = OLD_SEEDS + NEW_SEEDS
POOL_SIZES = [4, 8, 16, 32]
CLASS_EPS = [0.005, 0.010, 0.020]
REG_EPS = [0.025, 0.050, 0.100]
RNG_SEED = 20260726

mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans"],
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "font.size": 8,
    }
)


def stable_seed(*parts: object) -> int:
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()
    return int(digest[:8], 16)


def task_dir(seed: int, metric: bool = False) -> Path:
    if seed in NEW_SEEDS:
        return NEW_ROOT / f"seed_{seed}" / "tasks"
    if metric:
        return METRIC_ROOT / f"seed_{seed}" / "tasks"
    return OLD_ROOT / f"seed_{seed}" / "tasks"


def core_task_path(seed: int, task: str) -> Path:
    if seed in NEW_SEEDS:
        return NEW_ROOT / f"seed_{seed}" / "tasks" / task
    if task in {"bbbp", "bace", "clintox", "tdc_hia_hou", "tdc_pgp_broccatelli"}:
        return METRIC_ROOT / f"seed_{seed}" / "tasks" / task
    return REGRESSION_RERUN_ROOT / f"seed_{seed}" / "tasks" / task


def require_runs() -> None:
    missing: list[str] = []
    for seed in SEEDS:
        base = task_dir(seed)
        if not base.exists():
            missing.append(str(base))
        metric_base = task_dir(seed, metric=True)
        for task in ["bbbp", "bace", "clintox", "tdc_hia_hou", "tdc_pgp_broccatelli"]:
            for name in ["inner_scores.csv", "outer_candidate_scores.csv", "outer_predictions.csv.gz"]:
                path = metric_base / task / name
                if not path.exists():
                    missing.append(str(path))
    for seed in OLD_SEEDS:
        for task in ["esol", "freesolv", "lipo", "tdc_caco2_wang"]:
            for name in ["inner_scores.csv", "outer_candidate_scores.csv", "outer_predictions.csv.gz", "split_manifest.csv"]:
                path = REGRESSION_RERUN_ROOT / f"seed_{seed}" / "tasks" / task / name
                if not path.exists():
                    missing.append(str(path))
    if missing:
        raise FileNotFoundError("Incomplete nested runs:\n" + "\n".join(missing[:30]))


def load_core() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    inner_parts, outer_parts, registry_parts = [], [], []
    tasks = ["bbbp", "bace", "clintox", "esol", "freesolv", "lipo", "tdc_caco2_wang", "tdc_hia_hou", "tdc_pgp_broccatelli"]
    for seed in SEEDS:
        for task in tasks:
            path = core_task_path(seed, task)
            inner = pd.read_csv(path / "inner_scores.csv")
            outer = pd.read_csv(path / "outer_candidate_scores.csv")
            registry = pd.read_csv(path / "candidate_registry.csv")
            for frame in (inner, outer, registry):
                frame["seed"] = seed
            inner_parts.append(inner)
            outer_parts.append(outer)
            registry_parts.append(registry)
    inner = pd.concat(inner_parts, ignore_index=True)
    outer = pd.concat(outer_parts, ignore_index=True)
    registry = pd.concat(registry_parts, ignore_index=True)
    keys = ["seed", "dataset", "outer_fold", "candidate_order", "candidate"]
    inner_mean = inner.groupby(keys + ["task_type", "family"], as_index=False).agg(
        inner_mean=("inner_utility", "mean"),
        inner_sd=("inner_utility", "std"),
        fit_seconds_inner=("fit_seconds", "sum"),
    )
    expected = len(SEEDS) * 9 * 3 * 32
    if len(inner_mean) != expected or len(outer) != expected:
        raise RuntimeError(f"Core matrix incomplete: inner={len(inner_mean)}, outer={len(outer)}, expected={expected}")
    check = registry.groupby(["dataset", "candidate_order"])["candidate"].nunique()
    if int(check.max()) != 1:
        raise RuntimeError("Candidate registry identity changed across seeds")
    return inner_mean, outer, registry


def bootstrap_seed_contrast(frame: pd.DataFrame, column: str, reps: int = 10000) -> tuple[float, float, float]:
    by_seed = frame.groupby("seed")[column].mean().sort_index()
    values = by_seed.to_numpy(float)
    rng = np.random.default_rng(stable_seed(column, len(frame)))
    draws = rng.choice(values, size=(reps, len(values)), replace=True).mean(axis=1)
    return float(values.mean()), float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def fixed_reference_analysis(inner: pd.DataFrame, outer: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    merged = inner.merge(
        outer[["seed", "dataset", "outer_fold", "candidate_order", "candidate", "outer_utility"]],
        on=["seed", "dataset", "outer_fold", "candidate_order", "candidate"],
        validate="one_to_one",
    )
    rows: list[dict[str, object]] = []
    eps_rows: list[dict[str, object]] = []
    for dataset, endpoint in merged.groupby("dataset", sort=True):
        task_type = str(endpoint["task_type"].iloc[0])
        eps_grid = CLASS_EPS if task_type == "classification" else REG_EPS
        for seed in SEEDS:
            training = endpoint[endpoint["seed"].ne(seed)]
            training_mean = training.groupby(["candidate_order", "candidate"], as_index=False)["outer_utility"].mean()
            full_ref = training_mean.sort_values(["outer_utility", "candidate_order"], ascending=[False, True]).iloc[0]
            full_ref_order = int(full_ref["candidate_order"])
            for outer_fold, unit in endpoint[endpoint["seed"].eq(seed)].groupby("outer_fold", sort=True):
                unit = unit.sort_values("candidate_order")
                for pool_size in POOL_SIZES:
                    pool = unit[unit["candidate_order"].le(pool_size)]
                    selected = pool.sort_values(["inner_mean", "candidate_order"], ascending=[False, True]).iloc[0]
                    oracle = pool.sort_values(["outer_utility", "candidate_order"], ascending=[False, True]).iloc[0]
                    k_training = training_mean[training_mean["candidate_order"].le(pool_size)]
                    k_ref = k_training.sort_values(["outer_utility", "candidate_order"], ascending=[False, True]).iloc[0]
                    fixed_eval = unit[unit["candidate_order"].eq(full_ref_order)].iloc[0]
                    k_eval = unit[unit["candidate_order"].eq(int(k_ref["candidate_order"]))].iloc[0]
                    rank = spearmanr(pool["inner_mean"], pool["outer_utility"]).statistic
                    record = {
                        "dataset": dataset,
                        "task_type": task_type,
                        "seed": seed,
                        "outer_fold": int(outer_fold),
                        "pool_size": pool_size,
                        "selected_candidate": selected["candidate"],
                        "fixed_k32_reference_candidate": fixed_eval["candidate"],
                        "k_dependent_reference_candidate": k_eval["candidate"],
                        "same_fold_oracle_candidate": oracle["candidate"],
                        "selected_utility": float(selected["outer_utility"]),
                        "fixed_k32_reference_utility": float(fixed_eval["outer_utility"]),
                        "k_dependent_reference_utility": float(k_eval["outer_utility"]),
                        "same_fold_oracle_utility": float(oracle["outer_utility"]),
                        "fixed_k32_gap": float(fixed_eval["outer_utility"] - selected["outer_utility"]),
                        "k_dependent_crossfit_gap": float(k_eval["outer_utility"] - selected["outer_utility"]),
                        "same_fold_opportunity_gap": float(oracle["outer_utility"] - selected["outer_utility"]),
                        "validation_audit_spearman": float(rank) if np.isfinite(rank) else np.nan,
                    }
                    rows.append(record)
                    inner_best = float(pool["inner_mean"].max())
                    for tau in eps_grid:
                        validation_set = set(pool.loc[pool["inner_mean"].ge(inner_best - tau), "candidate"])
                        crossfit_set = set(
                            k_training.loc[k_training["outer_utility"].ge(float(k_training["outer_utility"].max()) - tau), "candidate"]
                        )
                        same_set = set(pool.loc[pool["outer_utility"].ge(float(oracle["outer_utility"]) - tau), "candidate"])
                        union = validation_set | crossfit_set
                        eps_rows.append(
                            {
                                **{k: record[k] for k in ["dataset", "task_type", "seed", "outer_fold", "pool_size"]},
                                "tau": tau,
                                "tau_status": "retrospective practical-equivalence tolerance with sensitivity grid",
                                "fixed_tau_regret": max(0.0, record["fixed_k32_gap"] - tau),
                                "crossfit_tau_success": int(record["fixed_k32_gap"] <= tau),
                                "same_fold_tau_success": int(record["same_fold_opportunity_gap"] <= tau),
                                "validation_near_equivalent_n": len(validation_set),
                                "crossfit_near_equivalent_n": len(crossfit_set),
                                "same_fold_near_equivalent_n": len(same_set),
                                "validation_crossfit_set_jaccard": len(validation_set & crossfit_set) / len(union) if union else np.nan,
                                "selected_in_crossfit_set": int(str(selected["candidate"]) in crossfit_set),
                            }
                        )
    units = pd.DataFrame(rows)
    tau_units = pd.DataFrame(eps_rows)
    contrast_rows = []
    for dataset, endpoint in units.groupby("dataset", sort=True):
        wide = endpoint.pivot_table(index=["seed", "outer_fold"], columns="pool_size", values=["fixed_k32_gap", "k_dependent_crossfit_gap", "same_fold_opportunity_gap"])
        for metric in ["fixed_k32_gap", "k_dependent_crossfit_gap", "same_fold_opportunity_gap"]:
            delta = (wide[(metric, 32)] - wide[(metric, 4)]).rename("delta").reset_index()
            mean, low, high = bootstrap_seed_contrast(delta, "delta")
            contrast_rows.append(
                {
                    "dataset": dataset,
                    "task_type": endpoint["task_type"].iloc[0],
                    "estimand": metric,
                    "contrast": "K=32 minus K=4",
                    "n_seeds": len(SEEDS),
                    "n_folds_per_seed": 3,
                    "mean_natural_scale_effect": mean,
                    "seed_block_interval_low": low,
                    "seed_block_interval_high": high,
                    "interval_interpretation": "descriptive split-seed sensitivity interval",
                    "contrast_direction": "negative favors K=32; positive favors K=4",
                }
            )
    return units, pd.DataFrame(contrast_rows), tau_units


def recall_pair(y: np.ndarray, pred: np.ndarray, threshold: float, minority: int) -> tuple[float, float, float]:
    label = (pred >= threshold).astype(int)
    rec = []
    for cls in (0, 1):
        mask = y == cls
        rec.append(float(np.mean(label[mask] == cls)) if mask.any() else np.nan)
    return rec[minority], rec[1 - minority], float(np.nanmean(rec))


def metric_selection_analysis() -> tuple[pd.DataFrame, pd.DataFrame]:
    candidate_rows: list[dict[str, object]] = []
    prediction_cache: dict[tuple[int, str], pd.DataFrame] = {}
    class_tasks = ["bbbp", "bace", "clintox", "tdc_hia_hou", "tdc_pgp_broccatelli"]
    for seed in SEEDS:
        base = task_dir(seed, metric=True)
        for dataset in class_tasks:
            inner = pd.read_csv(base / dataset / "inner_scores.csv")
            outer = pd.read_csv(base / dataset / "outer_candidate_scores.csv")
            pred = pd.read_csv(base / dataset / "outer_predictions.csv.gz")
            prediction_cache[(seed, dataset)] = pred
            stats = inner.groupby(["outer_fold", "candidate_order", "candidate"], as_index=False).agg(
                inner_roc_auc=("inner_roc_auc", "mean"),
                inner_pr_auc=("inner_pr_auc", "mean"),
                inner_minority_recall=("minority_recall", "mean"),
                inner_majority_recall=("majority_recall", "mean"),
                minority_threshold=("minority_threshold", "median"),
                minority_label=("minority_label", lambda x: int(pd.Series(x).mode().iloc[0])),
            )
            merged = stats.merge(
                outer[["outer_fold", "candidate_order", "candidate", "roc_auc", "pr_auc"]],
                on=["outer_fold", "candidate_order", "candidate"],
                validate="one_to_one",
            )
            for row in merged.itertuples(index=False):
                group = pred[(pred["outer_fold"].eq(row.outer_fold)) & (pred["candidate"].eq(row.candidate))]
                minority_recall, majority_recall, balanced = recall_pair(
                    group["y_true"].to_numpy(int), group["y_pred"].to_numpy(float), row.minority_threshold, int(row.minority_label)
                )
                candidate_rows.append(
                    {
                        "seed": seed,
                        "dataset": dataset,
                        **row._asdict(),
                        "outer_minority_recall": minority_recall,
                        "outer_majority_recall": majority_recall,
                        "outer_balanced_recall": balanced,
                        "outer_minority_miss_rate": 1.0 - minority_recall,
                    }
                )
    candidates = pd.DataFrame(candidate_rows)
    rows: list[dict[str, object]] = []
    for dataset, endpoint in candidates.groupby("dataset", sort=True):
        for seed in SEEDS:
            training = endpoint[endpoint["seed"].ne(seed)]
            reference = {}
            for selector, target in [("roc_auc", "roc_auc"), ("pr_auc", "pr_auc")]:
                means = training.groupby(["candidate_order", "candidate"], as_index=False)[target].mean()
                reference[selector] = means.sort_values([target, "candidate_order"], ascending=[False, True]).iloc[0]
            op_means = training.groupby(["candidate_order", "candidate"], as_index=False)[["outer_minority_recall", "outer_majority_recall"]].mean()
            feasible = op_means[op_means["outer_minority_recall"].ge(0.80)]
            op_ref_pool = feasible if not feasible.empty else op_means
            reference["minority_constrained"] = op_ref_pool.sort_values(
                ["outer_majority_recall", "outer_minority_recall", "candidate_order"], ascending=[False, False, True]
            ).iloc[0]
            for outer_fold, unit in endpoint[endpoint["seed"].eq(seed)].groupby("outer_fold", sort=True):
                for pool_size in POOL_SIZES:
                    pool = unit[unit["candidate_order"].le(pool_size)]
                    roc_selected = pool.sort_values(["inner_roc_auc", "candidate_order"], ascending=[False, True]).iloc[0]
                    pr_selected = pool.sort_values(["inner_pr_auc", "candidate_order"], ascending=[False, True]).iloc[0]
                    feasible = pool[pool["inner_minority_recall"].ge(0.80)]
                    op_pool = feasible if not feasible.empty else pool
                    op_selected = op_pool.sort_values(
                        ["inner_majority_recall", "inner_minority_recall", "inner_pr_auc", "candidate_order"],
                        ascending=[False, False, False, True],
                    ).iloc[0]
                    for selector, selected, target in [
                        ("roc_auc", roc_selected, "roc_auc"),
                        ("pr_auc", pr_selected, "pr_auc"),
                        ("minority_constrained", op_selected, "outer_majority_recall"),
                    ]:
                        ref_order = int(reference[selector]["candidate_order"])
                        ref_eval = unit[unit["candidate_order"].eq(ref_order)].iloc[0]
                        rows.append(
                            {
                                "dataset": dataset,
                                "seed": seed,
                                "outer_fold": int(outer_fold),
                                "pool_size": pool_size,
                                "selector": selector,
                                "selected_candidate": selected["candidate"],
                                "fixed_k32_reference_candidate": ref_eval["candidate"],
                                "outer_roc_auc": float(selected["roc_auc"]),
                                "outer_pr_auc": float(selected["pr_auc"]),
                                "outer_minority_recall": float(selected["outer_minority_recall"]),
                                "outer_majority_recall": float(selected["outer_majority_recall"]),
                                "outer_balanced_recall": float(selected["outer_balanced_recall"]),
                                "outer_minority_miss_rate": float(selected["outer_minority_miss_rate"]),
                                "target_metric": target,
                                "target_value": float(selected[target]),
                                "fixed_reference_target_value": float(ref_eval[target]),
                                "fixed_reference_gap": float(ref_eval[target] - selected[target]),
                                "constraint_target": 0.80 if selector == "minority_constrained" else np.nan,
                                "inner_constraint_met": int(selected["inner_minority_recall"] >= 0.80) if selector == "minority_constrained" else np.nan,
                            }
                        )
    selections = pd.DataFrame(rows)
    roc = selections[selections["selector"].eq("roc_auc")].rename(columns={
        "selected_candidate": "roc_selected_candidate",
        "outer_roc_auc": "roc_selector_outer_roc_auc",
        "outer_pr_auc": "roc_selector_outer_pr_auc",
        "outer_minority_recall": "roc_selector_outer_minority_recall",
        "outer_balanced_recall": "roc_selector_outer_balanced_recall",
    })
    compare_rows = []
    keys = ["dataset", "seed", "outer_fold", "pool_size"]
    for selector in ["pr_auc", "minority_constrained"]:
        alt = selections[selections["selector"].eq(selector)]
        merged = alt.merge(roc[keys + ["roc_selected_candidate", "roc_selector_outer_roc_auc", "roc_selector_outer_pr_auc", "roc_selector_outer_minority_recall", "roc_selector_outer_balanced_recall"]], on=keys)
        for row in merged.itertuples(index=False):
            compare_rows.append(
                {
                    **{key: getattr(row, key) for key in keys},
                    "alternative_selector": selector,
                    "candidate_changed_vs_roc": int(row.selected_candidate != row.roc_selected_candidate),
                    "delta_outer_roc_auc_vs_roc_selector": row.outer_roc_auc - row.roc_selector_outer_roc_auc,
                    "delta_outer_pr_auc_vs_roc_selector": row.outer_pr_auc - row.roc_selector_outer_pr_auc,
                    "delta_outer_minority_recall_vs_roc_selector": row.outer_minority_recall - row.roc_selector_outer_minority_recall,
                    "delta_outer_balanced_recall_vs_roc_selector": row.outer_balanced_recall - row.roc_selector_outer_balanced_recall,
                }
            )
    return selections, pd.DataFrame(compare_rows)


def matrix_effective_rank(matrix: np.ndarray) -> float:
    if matrix.shape[1] == 1:
        return 1.0
    corr = np.corrcoef(matrix, rowvar=False)
    corr = np.nan_to_num(corr, nan=1.0, posinf=1.0, neginf=-1.0)
    eig = np.clip(np.linalg.eigvalsh(corr), 0.0, None)
    return float(eig.sum() ** 2 / max(float(np.square(eig).sum()), 1e-12))


def candidate_controls(inner: pd.DataFrame, outer: pd.DataFrame) -> pd.DataFrame:
    data = inner.merge(
        outer[["seed", "dataset", "outer_fold", "candidate_order", "candidate", "outer_utility"]],
        on=["seed", "dataset", "outer_fold", "candidate_order", "candidate"],
        validate="one_to_one",
    )
    rows: list[dict[str, object]] = []
    for dataset, endpoint in data.groupby("dataset", sort=True):
        for seed in SEEDS:
            train = endpoint[endpoint["seed"].ne(seed)]
            test = endpoint[endpoint["seed"].eq(seed)]
            pivot = train.pivot_table(index=["seed", "outer_fold"], columns="candidate_order", values="outer_utility")
            means = pivot.mean()
            base = [1, 2, 3, 4]
            remaining = list(range(5, 33))
            weak = sorted(remaining, key=lambda c: (means[c], c))
            best_base = int(means.loc[base].idxmax())
            corr = pivot.corrwith(pivot[best_base]).fillna(1.0)
            mean_rank = means.loc[remaining].rank(ascending=False, method="first")
            corr_rank = corr.loc[remaining].rank(ascending=True, method="first")
            complementary = sorted(remaining, key=lambda c: (mean_rank[c] + corr_rank[c], mean_rank[c], c))
            actual_orders = {
                "registered": list(range(1, 33)),
                "weak_added": base + weak,
                "complementary_strong_added": base + complementary,
            }
            for control, orders in actual_orders.items():
                for pool_size in POOL_SIZES:
                    use = orders[:pool_size]
                    train_matrix = pivot[use].to_numpy(float)
                    reference_order = int(means.loc[use].sort_values(ascending=False).index[0])
                    for outer_fold, unit in test.groupby("outer_fold", sort=True):
                        pool = unit.set_index("candidate_order").loc[use].reset_index()
                        selected = pool.sort_values(["inner_mean", "candidate_order"], ascending=[False, True]).iloc[0]
                        oracle = pool.sort_values(["outer_utility", "candidate_order"], ascending=[False, True]).iloc[0]
                        ref = pool[pool["candidate_order"].eq(reference_order)].iloc[0]
                        rows.append({
                            "dataset": dataset, "seed": seed, "outer_fold": int(outer_fold), "pool_size": pool_size,
                            "control": control, "selected_candidate": selected["candidate"],
                            "available_opportunity": float(oracle["outer_utility"] - pool.iloc[0]["outer_utility"]),
                            "same_fold_gap": float(oracle["outer_utility"] - selected["outer_utility"]),
                            "crossfit_gap": float(ref["outer_utility"] - selected["outer_utility"]),
                            "effective_rank": matrix_effective_rank(train_matrix), "unique_candidates": len(set(use)),
                        })
            donors = remaining
            for control in ["exact_duplicate", "near_duplicate_95pct_anchor"]:
                entries = [(f"base_{c}", c, None) for c in base]
                for i in range(28):
                    anchor = base[i % len(base)]
                    donor = donors[i]
                    entries.append((f"{control}_{i+1}", anchor, donor))
                for pool_size in POOL_SIZES:
                    use = entries[:pool_size]
                    train_cols = []
                    for _, anchor, donor in use:
                        values = pivot[anchor].to_numpy(float)
                        if control.startswith("near") and donor is not None:
                            values = 0.95 * values + 0.05 * pivot[donor].to_numpy(float)
                        train_cols.append(values)
                    train_matrix = np.column_stack(train_cols)
                    train_means = train_matrix.mean(axis=0)
                    reference_index = int(np.argmax(train_means))
                    for outer_fold, unit in test.groupby("outer_fold", sort=True):
                        indexed = unit.set_index("candidate_order")
                        values = []
                        for name, anchor, donor in use:
                            inner_value = float(indexed.loc[anchor, "inner_mean"])
                            outer_value = float(indexed.loc[anchor, "outer_utility"])
                            if control.startswith("near") and donor is not None:
                                inner_value = 0.95 * inner_value + 0.05 * float(indexed.loc[donor, "inner_mean"])
                                outer_value = 0.95 * outer_value + 0.05 * float(indexed.loc[donor, "outer_utility"])
                            values.append((name, inner_value, outer_value))
                        frame = pd.DataFrame(values, columns=["candidate", "inner_mean", "outer_utility"])
                        selected = frame.sort_values(["inner_mean", "candidate"], ascending=[False, True]).iloc[0]
                        oracle = frame.sort_values(["outer_utility", "candidate"], ascending=[False, True]).iloc[0]
                        ref = frame.iloc[reference_index]
                        rows.append({
                            "dataset": dataset, "seed": seed, "outer_fold": int(outer_fold), "pool_size": pool_size,
                            "control": control, "selected_candidate": selected["candidate"],
                            "available_opportunity": float(oracle["outer_utility"] - frame.iloc[0]["outer_utility"]),
                            "same_fold_gap": float(oracle["outer_utility"] - selected["outer_utility"]),
                            "crossfit_gap": float(ref["outer_utility"] - selected["outer_utility"]),
                            "effective_rank": matrix_effective_rank(train_matrix), "unique_candidates": len(set(x[1] for x in use)),
                        })
    return pd.DataFrame(rows)


def order_sensitivity(inner: pd.DataFrame, outer: pd.DataFrame, random_orders: int = 100) -> pd.DataFrame:
    data = inner.merge(
        outer[["seed", "dataset", "outer_fold", "candidate_order", "candidate", "outer_utility"]],
        on=["seed", "dataset", "outer_fold", "candidate_order", "candidate"], validate="one_to_one"
    )
    rows: list[dict[str, object]] = []
    for dataset, endpoint in data.groupby("dataset", sort=True):
        for seed in SEEDS:
            training = endpoint[endpoint["seed"].ne(seed)]
            test = endpoint[endpoint["seed"].eq(seed)]
            stats = training.groupby("candidate_order", as_index=True).agg(
                mean_outer=("outer_utility", "mean"), mean_cost=("fit_seconds_inner", "mean")
            )
            deterministic = {
                "registered": list(range(1, 33)),
                "crossfit_best_first": stats.sort_values(["mean_outer"], ascending=False).index.tolist(),
                "crossfit_worst_first": stats.sort_values(["mean_outer"], ascending=True).index.tolist(),
                "cost_first": stats.sort_values(["mean_cost", "mean_outer"], ascending=[True, False]).index.tolist(),
            }
            orders = [(name, 0, order) for name, order in deterministic.items()]
            rng = np.random.default_rng(stable_seed(dataset, seed, "order"))
            orders.extend(("random", i + 1, rng.permutation(np.arange(1, 33)).tolist()) for i in range(random_orders))
            for order_name, replicate, order in orders:
                for pool_size in POOL_SIZES:
                    eligible = order[:pool_size]
                    ref_order = int(stats.loc[eligible, "mean_outer"].idxmax())
                    for outer_fold, unit in test.groupby("outer_fold", sort=True):
                        pool = unit.set_index("candidate_order").loc[eligible].reset_index()
                        selected = pool.sort_values(["inner_mean", "candidate_order"], ascending=[False, True]).iloc[0]
                        oracle = pool.sort_values(["outer_utility", "candidate_order"], ascending=[False, True]).iloc[0]
                        ref = pool[pool["candidate_order"].eq(ref_order)].iloc[0]
                        rows.append({
                            "dataset": dataset, "seed": seed, "outer_fold": int(outer_fold), "pool_size": pool_size,
                            "order_rule": order_name, "order_replicate": replicate,
                            "selected_candidate": selected["candidate"],
                            "same_fold_gap": float(oracle["outer_utility"] - selected["outer_utility"]),
                            "crossfit_gap": float(ref["outer_utility"] - selected["outer_utility"]),
                            "mean_inner_fit_seconds_of_eligible": float(stats.loc[eligible, "mean_cost"].sum()),
                        })
    return pd.DataFrame(rows)


def recovery_simulation(inner: pd.DataFrame, outer: pd.DataFrame, reps: int = 2000) -> pd.DataFrame:
    data = inner.merge(
        outer[["seed", "dataset", "outer_fold", "candidate_order", "candidate", "outer_utility"]],
        on=["seed", "dataset", "outer_fold", "candidate_order", "candidate"], validate="one_to_one"
    )
    rows = []
    for dataset, endpoint in data.groupby("dataset", sort=True):
        inner_matrix = endpoint.pivot_table(index=["seed", "outer_fold"], columns="candidate_order", values="inner_mean").sort_index(axis=1)
        truth_matrix = endpoint.pivot_table(index=["seed", "outer_fold"], columns="candidate_order", values="outer_utility").sort_index(axis=1)
        residual = inner_matrix.to_numpy(float) - truth_matrix.to_numpy(float)
        covariance = np.cov(residual, rowvar=False, ddof=1)
        eig, vec = np.linalg.eigh(covariance)
        covariance = (vec * np.clip(eig, 1e-10, None)) @ vec.T
        avg_var = float(np.mean(np.diag(covariance)))
        for pool_size in POOL_SIZES:
            truth = truth_matrix.iloc[:, :pool_size].to_numpy(float)
            observed = inner_matrix.iloc[:, :pool_size].to_numpy(float)
            oracle = np.argmax(truth, axis=1)
            observed_selected = np.argmax(observed, axis=1)
            observed_gap = float(np.mean(truth[np.arange(len(truth)), oracle] - truth[np.arange(len(truth)), observed_selected]))
            for scenario, cov in [
                ("empirical_correlation_heteroskedastic", covariance[:pool_size, :pool_size]),
                ("independent_homoskedastic", np.eye(pool_size) * avg_var),
            ]:
                for noise_scale in [0.5, 1.0, 2.0]:
                    rng = np.random.default_rng(stable_seed(dataset, pool_size, scenario, noise_scale))
                    noise = rng.multivariate_normal(np.zeros(pool_size), cov * noise_scale**2, size=(reps, len(truth)))
                    scores = truth[None, :, :] + noise
                    selected = np.argmax(scores, axis=2)
                    selected_truth = np.take_along_axis(truth[None, :, :], selected[:, :, None], axis=2).squeeze(2)
                    oracle_truth = truth[np.arange(len(truth)), oracle]
                    gaps = (oracle_truth[None, :] - selected_truth).mean(axis=1)
                    recovery = (selected == oracle[None, :]).mean(axis=1)
                    rows.append({
                        "dataset": dataset, "pool_size": pool_size, "scenario": scenario, "noise_scale": noise_scale,
                        "simulation_replicates": reps, "n_audit_units": len(truth), "observed_mean_same_fold_gap": observed_gap,
                        "simulated_mean_gap": float(gaps.mean()), "simulated_gap_interval_low": float(np.quantile(gaps, 0.025)),
                        "simulated_gap_interval_high": float(np.quantile(gaps, 0.975)), "top1_recovery_mean": float(recovery.mean()),
                        "top1_recovery_interval_low": float(np.quantile(recovery, 0.025)), "top1_recovery_interval_high": float(np.quantile(recovery, 0.975)),
                        "observed_within_simulated_95pct_envelope": int(np.quantile(gaps, 0.025) <= observed_gap <= np.quantile(gaps, 0.975)),
                        "candidate_variance_cv": float(np.std(np.sqrt(np.diag(covariance))) / max(np.mean(np.sqrt(np.diag(covariance))), 1e-12)),
                    })
    return pd.DataFrame(rows)


def fit_log_audit() -> pd.DataFrame:
    rows = []
    sources = [
        ("legacy_historical_outputs", OLD_ROOT, OLD_SEEDS),
        ("primary_old_seed_classification_rerun", METRIC_ROOT, OLD_SEEDS),
        ("primary_old_seed_regression_split_update", REGRESSION_RERUN_ROOT, OLD_SEEDS),
        ("primary_additional_seeds", NEW_ROOT, NEW_SEEDS),
    ]
    for source, root, seeds in sources:
        for seed in seeds:
            base = root / f"seed_{seed}" / "tasks"
            for task_dir_path in sorted(p for p in base.iterdir() if p.is_dir()):
                inner = pd.read_csv(task_dir_path / "inner_scores.csv")
                outer = pd.read_csv(task_dir_path / "outer_candidate_scores.csv")
                expected_inner = 3 * 3 * 32
                expected_outer = 3 * 32
                rows.append({
                    "source": source, "seed": seed, "dataset": task_dir_path.name,
                    "inner_fits": len(inner), "outer_fits": len(outer), "total_fits": len(inner) + len(outer),
                    "expected_inner_fits": expected_inner, "expected_outer_fits": expected_outer,
                    "complete_fit_matrix": int(len(inner) == expected_inner and len(outer) == expected_outer),
                    "nonfinite_inner_utility": int((~np.isfinite(inner["inner_utility"])).sum()),
                    "nonfinite_outer_utility": int((~np.isfinite(outer["outer_utility"])).sum()),
                    "summed_fit_seconds": float(inner["fit_seconds"].sum() + outer["fit_seconds"].sum()),
                })
    return pd.DataFrame(rows)


def pretraining_overlap_audit() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "registry_scope": "nine-endpoint primary 32-candidate registry",
                "representation": "Morgan-512 classical learners",
                "checkpoint": "not applicable",
                "pretraining_used": False,
                "molecule_level_pretraining_manifest_available": True,
                "overlap_status": "not applicable",
                "interpretation": "Primary fixed-reference and metric-selection estimands do not use pretrained encoders.",
            },
            {
                "registry_scope": "six-endpoint modern-augmented sensitivity registry",
                "representation": "chemberta_mtr",
                "checkpoint": "DeepChem/ChemBERTa-77M-MTR",
                "pretraining_used": True,
                "molecule_level_pretraining_manifest_available": False,
                "overlap_status": "not auditable from released checkpoint metadata",
                "interpretation": "Frozen cached embedding; exact benchmark-molecule membership in pretraining cannot be excluded.",
            },
            {
                "registry_scope": "six-endpoint modern-augmented sensitivity registry",
                "representation": "chemberta_mlm",
                "checkpoint": "DeepChem/ChemBERTa-77M-MLM",
                "pretraining_used": True,
                "molecule_level_pretraining_manifest_available": False,
                "overlap_status": "not auditable from released checkpoint metadata",
                "interpretation": "Frozen cached embedding; exact benchmark-molecule membership in pretraining cannot be excluded.",
            },
            {
                "registry_scope": "six-endpoint modern-augmented sensitivity registry",
                "representation": "molformer",
                "checkpoint": "ibm/MoLFormer-XL-both-10pct",
                "pretraining_used": True,
                "molecule_level_pretraining_manifest_available": False,
                "overlap_status": "not auditable from released checkpoint metadata",
                "interpretation": "Frozen cached embedding; exact benchmark-molecule membership in pretraining cannot be excluded.",
            },
            {
                "registry_scope": "six-endpoint modern-augmented sensitivity registry",
                "representation": "chemprop_dmpnn",
                "checkpoint": "none; locally fitted locked one-epoch configuration",
                "pretraining_used": False,
                "molecule_level_pretraining_manifest_available": True,
                "overlap_status": "not applicable",
                "interpretation": "No external pretrained checkpoint was used for this registered candidate.",
            },
        ]
    )


def rerun_reproducibility_audit() -> pd.DataFrame:
    rows = []
    rerun_sources = [("classification_metric", METRIC_ROOT), ("regression_split_manifest", REGRESSION_RERUN_ROOT)]
    for rerun_type, rerun_root in rerun_sources:
        for seed in OLD_SEEDS:
            original = OLD_ROOT / f"seed_{seed}" / "tasks"
            rerun = rerun_root / f"seed_{seed}" / "tasks"
            for task_dir_path in sorted(p for p in rerun.iterdir() if p.is_dir()):
                task = task_dir_path.name
                old_inner = pd.read_csv(original / task / "inner_scores.csv")
                new_inner = pd.read_csv(task_dir_path / "inner_scores.csv")
                old_outer = pd.read_csv(original / task / "outer_candidate_scores.csv")
                new_outer = pd.read_csv(task_dir_path / "outer_candidate_scores.csv")
                old_complete = json.loads((original / task / "complete.json").read_text(encoding="utf-8"))
                new_complete = json.loads((task_dir_path / "complete.json").read_text(encoding="utf-8"))
                inner_keys = ["outer_fold", "inner_fold", "candidate_order", "candidate"]
                outer_keys = ["outer_fold", "candidate_order", "candidate"]
                inner_cmp = old_inner.merge(new_inner, on=inner_keys, suffixes=("_old", "_new"), validate="one_to_one")
                outer_cmp = old_outer.merge(new_outer, on=outer_keys, suffixes=("_old", "_new"), validate="one_to_one")
                rows.append(
                    {
                        "seed": seed,
                        "dataset": task,
                        "rerun_type": rerun_type,
                        "legacy_outer_split_type": old_complete.get("outer_split_type", "not recorded"),
                        "current_outer_split_type": new_complete.get("outer_split_type", "not recorded"),
                        "split_regime_changed": int(old_complete.get("outer_split_type") != new_complete.get("outer_split_type")),
                        "inner_rows_compared": len(inner_cmp),
                        "outer_rows_compared": len(outer_cmp),
                        "max_abs_inner_utility_difference": float(np.max(np.abs(inner_cmp["inner_utility_old"] - inner_cmp["inner_utility_new"]))),
                        "max_abs_outer_utility_difference": float(np.max(np.abs(outer_cmp["outer_utility_old"] - outer_cmp["outer_utility_new"]))),
                        "mean_abs_outer_utility_difference": float(np.mean(np.abs(outer_cmp["outer_utility_old"] - outer_cmp["outer_utility_new"]))),
                    }
                )
    return pd.DataFrame(rows)


def save_figures(fixed: pd.DataFrame, metric_compare: pd.DataFrame, controls: pd.DataFrame, recovery: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0))
    summary = fixed.groupby(["pool_size"])[["fixed_k32_gap", "k_dependent_crossfit_gap", "same_fold_opportunity_gap"]].mean()
    for col, label in [("fixed_k32_gap", "K-invariant K=32 reference"), ("k_dependent_crossfit_gap", "K-dependent cross-fit"), ("same_fold_opportunity_gap", "same-fold opportunity bound")]:
        axes[0].plot(summary.index, summary[col], marker="o", label=label)
    axes[0].axhline(0, color="0.4", lw=0.7)
    axes[0].set(xlabel="Nominal candidate count K", ylabel="Mean natural-utility gap", xticks=POOL_SIZES)
    axes[0].legend(fontsize=6)
    tau = pd.read_csv(TABLES / "tau_near_equivalence_units.csv") if (TABLES / "tau_near_equivalence_units.csv").exists() else None
    if tau is not None:
        working = tau[((tau["task_type"].eq("classification")) & (tau["tau"].eq(0.01))) | ((tau["task_type"].eq("regression")) & (tau["tau"].eq(0.05)))]
        rate = working.groupby("pool_size")["crossfit_tau_success"].mean()
        size = working.groupby("pool_size")["crossfit_near_equivalent_n"].mean()
        axes[1].plot(rate.index, rate, marker="o", color="#0072B2", label="τ-success rate")
        ax2 = axes[1].twinx()
        ax2.plot(size.index, size, marker="s", color="#D55E00", label="near-equivalent set size")
        axes[1].set(xlabel="Nominal candidate count K", ylabel="τ-success rate", xticks=POOL_SIZES, ylim=(0, 1.05))
        ax2.set_ylabel("Mean set size")
    fig.tight_layout()
    fig.savefig(FIGURES / "Figure_2_fixed_reference_and_equivalence.pdf", bbox_inches="tight")
    fig.savefig(FIGURES / "Figure_2_fixed_reference_and_equivalence.png", dpi=600, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0))
    for selector, color in [("pr_auc", "#0072B2"), ("minority_constrained", "#D55E00")]:
        part = metric_compare[metric_compare["alternative_selector"].eq(selector)].groupby("pool_size").mean(numeric_only=True)
        axes[0].plot(part.index, part["candidate_changed_vs_roc"], marker="o", label=selector, color=color)
        axes[1].plot(part.index, part["delta_outer_minority_recall_vs_roc_selector"], marker="o", label=selector, color=color)
    axes[0].set(xlabel="K", ylabel="Selection disagreement with ROC-AUC", xticks=POOL_SIZES, ylim=(0, 1))
    axes[1].axhline(0, color="0.4", lw=0.7)
    axes[1].set(xlabel="K", ylabel="Δ outer minority recall", xticks=POOL_SIZES)
    axes[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(FIGURES / "Figure_5_metric_dependent_selection.pdf", bbox_inches="tight")
    fig.savefig(FIGURES / "Figure_5_metric_dependent_selection.png", dpi=600, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0))
    summary = controls.groupby(["control", "pool_size"], as_index=False).mean(numeric_only=True)
    for name, part in summary.groupby("control"):
        axes[0].plot(part["pool_size"], part["effective_rank"], marker="o", label=name)
        axes[1].plot(part["pool_size"], part["same_fold_gap"], marker="o", label=name)
    axes[0].set(xlabel="K", ylabel="Effective rank", xticks=POOL_SIZES)
    axes[1].set(xlabel="K", ylabel="Mean same-fold opportunity gap", xticks=POOL_SIZES)
    axes[0].legend(fontsize=5)
    fig.tight_layout()
    fig.savefig(FIGURES / "Figure_6_constructed_candidate_controls.pdf", bbox_inches="tight")
    fig.savefig(FIGURES / "Figure_6_constructed_candidate_controls.png", dpi=600, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(4.8, 3.2))
    part = recovery[(recovery["scenario"].eq("empirical_correlation_heteroskedastic")) & (recovery["noise_scale"].eq(1.0))]
    for dataset, group in part.groupby("dataset"):
        ax.plot(group["pool_size"], group["top1_recovery_mean"], marker="o", alpha=0.7, label=dataset)
    ax.set(xlabel="K", ylabel="Simulated top-1 recovery", xticks=POOL_SIZES, ylim=(0, 1))
    ax.legend(fontsize=5, ncol=3)
    fig.tight_layout()
    fig.savefig(FIGURES / "Figure_3_empirical_recovery_simulation.pdf", bbox_inches="tight")
    fig.savefig(FIGURES / "Figure_3_empirical_recovery_simulation.png", dpi=600, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    for path in [TABLES, FIGURES, SOURCE]:
        path.mkdir(parents=True, exist_ok=True)
    require_runs()
    inner, outer, registry = load_core()
    fixed, contrasts, tau = fixed_reference_analysis(inner, outer)
    selections, metric_compare = metric_selection_analysis()
    controls = candidate_controls(inner, outer)
    order = order_sensitivity(inner, outer)
    recovery = recovery_simulation(inner, outer)
    fits = fit_log_audit()
    pretraining = pretraining_overlap_audit()
    reproducibility = rerun_reproducibility_audit()
    completion = pd.DataFrame(
        [
            ["K-invariant K=32 seed-isolated reference", "completed", "10 seeds; fixed comparator identity across K"],
            ["Practical-equivalence grid and near-equivalent sets", "completed", "classification 0.005/0.010/0.020; regression 0.025/0.050/0.100"],
            ["PR-AUC-driven classification selection", "completed", "five classification endpoints; 10 seeds"],
            ["Minority-recall-constrained selection", "completed", "training-defined minority; inner target 0.80"],
            ["Empirical correlated heteroskedastic recovery", "completed", "2,000 replicates per endpoint/K/scenario/scale"],
            ["Exact and near-duplicate controls", "completed", "stored-utility construction"],
            ["Weak and complementary-strong controls", "completed", "non-held-seed construction"],
            ["Candidate-order sensitivity", "completed", "registered/best/worst/cost plus 100 random orders"],
            ["Additional split seeds", "completed", "five added; ten total under the current split implementation"],
            ["Legacy regression split transition", "completed", "historical unseeded GroupKFold outputs excluded from the current ten-seed primary matrix"],
            ["Fit-count and failure audit", "completed", "all expected inner/outer cells checked"],
            ["External/time/source split", "not feasible", "no independent cohort or timestamp/source metadata; three-endpoint structure transfer retained"],
            ["Exact pretrained-corpus overlap", "unresolved", "checkpoint-level identities available; molecule-level corpus manifests unavailable"],
            ["Author metadata and public repository", "author action required", "names/ORCIDs/declarations and persistent DOI/URL unavailable"],
        ],
        columns=["experiment_or_requirement", "status", "evidence_or_reason"],
    )

    outputs = {
        "fixed_reference_units.csv": fixed,
        "fixed_reference_k32_vs_k4_contrasts.csv": contrasts,
        "tau_near_equivalence_units.csv": tau,
        "classification_metric_selection_units.csv": selections,
        "classification_metric_selector_comparisons.csv": metric_compare,
        "constructed_candidate_control_units.csv": controls,
        "candidate_order_sensitivity_units.csv": order,
        "empirical_heteroskedastic_recovery_simulation.csv": recovery,
        "fit_execution_audit.csv": fits,
        "pretraining_overlap_audit.csv": pretraining,
        "legacy_to_current_rerun_audit.csv": reproducibility,
        "supplementary_experiment_completion_status.csv": completion,
        "candidate_registry_10seed_audit.csv": registry,
    }
    for name, frame in outputs.items():
        frame.to_csv(TABLES / name, index=False)
        frame.to_csv(SOURCE / name, index=False)
    save_figures(fixed, metric_compare, controls, recovery)

    summary = {
        "status": "complete",
        "seeds": SEEDS,
        "n_endpoints": int(fixed["dataset"].nunique()),
        "n_fixed_reference_units": len(fixed),
        "n_metric_selection_units": len(selections),
        "n_constructed_control_units": len(controls),
        "n_order_sensitivity_units": len(order),
        "n_simulation_summaries": len(recovery),
        "total_primary_current_fits": int(fits[fits["source"].str.startswith("primary_")]["total_fits"].sum()),
        "old_seed_classification_rerun_fits": int(fits[fits["source"].eq("primary_old_seed_classification_rerun")]["total_fits"].sum()),
        "old_seed_regression_split_update_fits": int(fits[fits["source"].eq("primary_old_seed_regression_split_update")]["total_fits"].sum()),
        "legacy_regression_split_regime": "unseeded GroupKFold; excluded from the current ten-seed primary matrix",
        "current_regression_split_regime": "seeded scaffold-group-balanced folds for all ten seeds",
        "all_fit_matrices_complete": bool(fits["complete_fit_matrix"].all()),
        "software": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__, "sklearn": sklearn.__version__},
        "tau": {"classification_roc_auc": CLASS_EPS, "regression_rmse": REG_EPS, "working_threshold_is_retrospective": True},
        "minority_constraint": {"target_recall": 0.80, "minority_defined_from_training_fold": True},
    }
    (OUT / "EXPERIMENT_COMPLETION_MANIFEST.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
