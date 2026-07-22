from __future__ import annotations

import json
import math
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from rdkit import RDLogger
from scipy.stats import spearmanr
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import average_precision_score, roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_shared_split_multiview_nested_20260624 as shared


RDLogger.DisableLog("rdApp.*")
warnings.filterwarnings("ignore", category=UserWarning)

TASKS6 = ["esol", "freesolv", "lipo", "bbbp", "bace", "clintox"]
SEEDS = [11, 23, 37, 53, 71]
ALPHAS = [0.05, 0.10, 0.20]
BUDGETS = [0.01, 0.05, 0.10]

HARD = ROOT / "output" / "sci1_hardening_20260707"
OUT = ROOT / "output" / "sci1_mechanism_uq_decision_20260707"


@dataclass
class TaskContext:
    task: str
    task_type: str
    frame: pd.DataFrame
    y: np.ndarray
    morgan: np.ndarray
    scaffolds: np.ndarray
    splits: dict[int, list[tuple[np.ndarray, np.ndarray]]]


def q_conformal(scores: np.ndarray, alpha: float) -> float:
    values = np.asarray(scores, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return math.nan
    ordered = np.sort(values)
    k = int(math.ceil((len(ordered) + 1) * (1.0 - alpha)))
    k = min(max(k, 1), len(ordered))
    return float(ordered[k - 1])


def sim_bin(value: float) -> str:
    if not np.isfinite(value):
        return "unknown"
    if value < 0.50:
        return "<0.5"
    if value < 0.70:
        return "0.5-0.7"
    return ">0.7"


def safe_spearman(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 3 or len(np.unique(x[mask])) < 2 or len(np.unique(y[mask])) < 2:
        return math.nan
    return float(spearmanr(x[mask], y[mask]).correlation)


def ece_score(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    y = np.asarray(y, dtype=int)
    p = np.clip(np.asarray(p, dtype=float), 0.0, 1.0)
    edges = np.linspace(0.0, 1.0, bins + 1)
    out = 0.0
    n = len(y)
    if n == 0:
        return math.nan
    for lo, hi in zip(edges[:-1], edges[1:]):
        if hi == 1.0:
            mask = (p >= lo) & (p <= hi)
        else:
            mask = (p >= lo) & (p < hi)
        if not mask.any():
            continue
        out += float(mask.mean() * abs(y[mask].mean() - p[mask].mean()))
    return out


def risk_coverage_auc(error: np.ndarray, uncertainty: np.ndarray) -> float:
    error = np.asarray(error, dtype=float)
    uncertainty = np.asarray(uncertainty, dtype=float)
    mask = np.isfinite(error) & np.isfinite(uncertainty)
    if mask.sum() < 3:
        return math.nan
    order = np.argsort(uncertainty[mask])
    err = error[mask][order]
    coverage = np.arange(1, len(err) + 1, dtype=float) / len(err)
    risk = np.cumsum(err) / np.arange(1, len(err) + 1)
    return float(np.trapezoid(risk, coverage))


def classification_metrics(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    out = {
        "roc_auc": math.nan,
        "pr_auc": math.nan,
        "brier": float(np.mean((p - y) ** 2)) if len(y) else math.nan,
        "ece": ece_score(y, p),
    }
    if len(np.unique(y)) == 2:
        out["roc_auc"] = float(roc_auc_score(y, p))
        out["pr_auc"] = float(average_precision_score(y, p))
    return out


def load_contexts() -> dict[str, TaskContext]:
    registry = json.loads((ROOT / "data" / "dataset_registry.json").read_text(encoding="utf-8"))
    contexts: dict[str, TaskContext] = {}
    for task in TASKS6:
        frame, task_type = shared.load_task(task, registry)
        reps, scaffolds, keep = shared.featurize(frame["smiles"])
        frame = frame.loc[keep].reset_index(drop=True)
        y = frame["y"].to_numpy()
        splits: dict[int, list[tuple[np.ndarray, np.ndarray]]] = {}
        for seed in SEEDS:
            outer_splits, _ = shared.make_splits(y, scaffolds, task_type, 3, seed)
            splits[seed] = outer_splits
        contexts[task] = TaskContext(
            task=task,
            task_type=task_type,
            frame=frame,
            y=y,
            morgan=reps["morgan512"].astype(np.float32),
            scaffolds=scaffolds,
            splits=splits,
        )
    return contexts


def max_tanimoto_to_train(morgan: np.ndarray, train_idx: np.ndarray, test_idx: np.ndarray) -> np.ndarray:
    train = morgan[train_idx]
    test = morgan[test_idx]
    inter = test @ train.T
    test_sum = test.sum(axis=1)[:, None]
    train_sum = train.sum(axis=1)[None, :]
    denom = test_sum + train_sum - inter
    sims = np.divide(inter, denom, out=np.zeros_like(inter), where=denom > 0)
    return sims.max(axis=1)


def build_sample_metadata(contexts: dict[str, TaskContext]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for task, ctx in contexts.items():
        for seed, splits in ctx.splits.items():
            for outer_fold, (train_idx, test_idx) in enumerate(splits, start=1):
                nn = max_tanimoto_to_train(ctx.morgan, train_idx, test_idx)
                train_scaffolds = set(ctx.scaffolds[train_idx].tolist())
                for local_i, sample_index in enumerate(test_idx):
                    scaffold = str(ctx.scaffolds[sample_index])
                    rows.append(
                        {
                            "task": task,
                            "task_type": ctx.task_type,
                            "seed": seed,
                            "outer_fold": outer_fold,
                            "sample_index": int(sample_index),
                            "smiles": str(ctx.frame.iloc[sample_index]["smiles"]),
                            "y_true_from_registry": float(ctx.y[sample_index]),
                            "max_train_tanimoto": float(nn[local_i]),
                            "tanimoto_bin": sim_bin(float(nn[local_i])),
                            "scaffold": scaffold,
                            "scaffold_status": "known_scaffold" if scaffold in train_scaffolds else "novel_scaffold",
                        }
                    )
    meta = pd.DataFrame(rows)
    meta.to_csv(OUT / "sample_scaffold_similarity_metadata.csv", index=False)
    return meta


def empirical_mechanism_anchors() -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    nested_path = ROOT / "results" / "nested_selection" / "repeated_regret_decomposition.csv"
    if nested_path.exists():
        nested = pd.read_csv(nested_path)
        good = nested[nested["status"].eq("completed")].copy()
        for k, group in good.groupby("pool_size", sort=True):
            rows.append(
                {
                    "anchor_source": "32-candidate lightweight nested selection",
                    "correlation_regime": "high_correlated_lightweight",
                    "candidate_count": int(k),
                    "validation_information_fraction": 1.0,
                    "n_units": int(len(group)),
                    "mean_range_normalized_selection_loss": float(group["fixed_normalized_regret"].mean()),
                    "top1_hit_rate": float((group["raw_regret"].abs() < 1e-12).mean()),
                }
            )

    val_path = HARD / "validation_information_sensitivity_summary.csv"
    if val_path.exists():
        val = pd.read_csv(val_path)
        mapping = {
            "morgan_only": "high_correlated_lightweight",
            "fingerprints_only": "high_correlated_lightweight",
            "no_multiview_concat": "medium_correlated_multiview",
            "full_multiview": "medium_correlated_multiview",
        }
        for row in val.itertuples(index=False):
            rows.append(
                {
                    "anchor_source": f"9-endpoint {row.variant} validation-information sensitivity",
                    "correlation_regime": mapping.get(str(row.variant), "medium_correlated_multiview"),
                    "candidate_count": int(row.candidate_count),
                    "validation_information_fraction": float(row.validation_information_fraction),
                    "n_units": int(row.n_units),
                    "mean_range_normalized_selection_loss": float(row.mean_range_normalized_selection_loss),
                    "top1_hit_rate": float(row.top1_hit_rate),
                }
            )

    strong_path = HARD / "six_task_strong_selection_detail.csv"
    if strong_path.exists():
        strong = pd.read_csv(strong_path)
        rows.append(
            {
                "anchor_source": "6-task deep/foundation strong-baseline panel",
                "correlation_regime": "low_correlated_deep_foundation",
                "candidate_count": int(strong["candidate_count"].median()),
                "validation_information_fraction": 1.0,
                "n_units": int(len(strong)),
                "mean_range_normalized_selection_loss": float(strong["range_normalized_selection_loss"].mean()),
                "top1_hit_rate": float(strong["outer_top1_hit"].mean()),
            }
        )

    anchors = pd.DataFrame(rows)
    anchors.to_csv(OUT / "mechanism_empirical_anchor.csv", index=False)
    return anchors


def simulate_one_grid(noise_scale: float, n_rep: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    regimes = {
        "high_correlated_lightweight": 0.90,
        "medium_correlated_multiview": 0.50,
        "low_correlated_deep_foundation": 0.15,
    }
    rows: list[dict[str, object]] = []
    for regime, rho in regimes.items():
        for frac in [0.25, 0.50, 0.75, 1.00]:
            for k in [4, 8, 16, 32, 64]:
                common = rng.normal(size=(n_rep, 1))
                independent = rng.normal(size=(n_rep, k))
                true = math.sqrt(rho) * common + math.sqrt(1.0 - rho) * independent
                true = true / max(float(true.std()), 1e-12)
                noise = rng.normal(scale=noise_scale * (1.0 + 0.35 * (1.0 - rho)) / math.sqrt(frac), size=(n_rep, k))
                validation = true + noise
                selected_idx = np.argmax(validation, axis=1)
                oracle_idx = np.argmax(true, axis=1)
                selected = true[np.arange(n_rep), selected_idx]
                oracle = true[np.arange(n_rep), oracle_idx]
                baseline = true[:, 0]
                full_range = np.maximum(true.max(axis=1) - true.min(axis=1), 1e-12)
                norm_loss = (oracle - selected) / full_range
                rows.append(
                    {
                        "correlation_regime": regime,
                        "pairwise_candidate_correlation": rho,
                        "validation_information_fraction": frac,
                        "candidate_count": k,
                        "n_replicates": n_rep,
                        "noise_scale": noise_scale,
                        "mean_range_normalized_selection_loss": float(norm_loss.mean()),
                        "top1_hit_rate": float((selected_idx == oracle_idx).mean()),
                        "mean_attainable_gain_vs_first_candidate": float((oracle - baseline).mean()),
                        "mean_realized_gain_vs_first_candidate": float((selected - baseline).mean()),
                        "mean_selection_loss_raw": float((oracle - selected).mean()),
                        "mean_candidate_range": float(full_range.mean()),
                    }
                )
    out = pd.DataFrame(rows)
    ref = (
        out[out["candidate_count"].eq(64)]
        .groupby("correlation_regime")["mean_candidate_range"]
        .mean()
        .rename("k64_reference_range")
        .reset_index()
    )
    out = out.merge(ref, on="correlation_regime", how="left")
    out["fixed_k64_normalized_selection_loss"] = out["mean_selection_loss_raw"] / out["k64_reference_range"]
    return out


def mechanism_experiment() -> pd.DataFrame:
    anchors = empirical_mechanism_anchors()
    target = 0.043
    if not anchors.empty:
        full = anchors[
            anchors["anchor_source"].str.contains("full_multiview", regex=False)
            & anchors["validation_information_fraction"].eq(1.0)
        ]
        if not full.empty:
            target = float(full["mean_range_normalized_selection_loss"].iloc[0])

    candidates = np.linspace(0.015, 0.30, 20)
    errors: list[tuple[float, float]] = []
    for scale in candidates:
        sim = simulate_one_grid(scale, n_rep=700, seed=20260707)
        probe = sim[
            sim["correlation_regime"].eq("medium_correlated_multiview")
            & sim["candidate_count"].eq(16)
            & sim["validation_information_fraction"].eq(1.0)
        ]["mean_range_normalized_selection_loss"].iloc[0]
        errors.append((abs(float(probe) - target), float(scale)))
    noise_scale = min(errors)[1]
    detail = simulate_one_grid(noise_scale, n_rep=4000, seed=20260708)
    detail.to_csv(OUT / "mechanism_controlled_simulation_grid.csv", index=False)

    summary = detail.copy()
    summary["mechanism_interpretation"] = np.where(
        summary["validation_information_fraction"] < 1.0,
        "lower validation information increases ranking noise",
        "full validation information reference",
    )
    summary.to_csv(OUT / "mechanism_controlled_simulation_summary.csv", index=False)
    return summary


def conformal_crossfold(preds: pd.DataFrame, meta: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = preds.merge(
        meta[["task", "seed", "outer_fold", "sample_index", "max_train_tanimoto", "tanimoto_bin", "scaffold_status"]],
        on=["task", "seed", "outer_fold", "sample_index"],
        how="left",
    )
    detail_rows: list[dict[str, object]] = []
    unit_cols = ["task", "task_type", "candidate", "seed"]
    for (task, task_type, candidate, seed), group in data.groupby(unit_cols, sort=True):
        for outer_fold, test in group.groupby("outer_fold", sort=True):
            cal = group[group["outer_fold"] != outer_fold]
            for alpha in ALPHAS:
                if task_type == "classification":
                    cal_y = cal["y_true"].astype(int).to_numpy()
                    cal_p = cal["y_pred"].clip(0.0, 1.0).to_numpy()
                    test_y = test["y_true"].astype(int).to_numpy()
                    test_p = test["y_pred"].clip(0.0, 1.0).to_numpy()

                    score = np.where(cal_y == 1, 1.0 - cal_p, cal_p)
                    q_all = q_conformal(score, alpha)
                    q0 = q_conformal(cal_p[cal_y == 0], alpha)
                    q1 = q_conformal((1.0 - cal_p)[cal_y == 1], alpha)
                    methods = [
                        ("split_conformal", q_all, q_all, None),
                        ("label_conditional_conformal", q0, q1, None),
                    ]
                    for method, q_zero, q_one, _ in methods:
                        include_zero = test_p <= q_zero
                        include_one = (1.0 - test_p) <= q_one
                        covered = np.where(test_y == 1, include_one, include_zero)
                        set_size = include_zero.astype(int) + include_one.astype(int)
                        detail_rows.append(
                            {
                                "task": task,
                                "task_type": task_type,
                                "candidate": candidate,
                                "seed": int(seed),
                                "outer_fold": int(outer_fold),
                                "alpha": alpha,
                                "target_coverage": 1.0 - alpha,
                                "method": method,
                                "n_test": int(len(test)),
                                "coverage": float(covered.mean()),
                                "class_0_coverage": float(covered[test_y == 0].mean()) if np.any(test_y == 0) else math.nan,
                                "class_1_coverage": float(covered[test_y == 1].mean()) if np.any(test_y == 1) else math.nan,
                                "avg_set_size": float(set_size.mean()),
                                "avg_interval_width": math.nan,
                                "calibration_n": int(len(cal)),
                            }
                        )

                    include_zero = np.zeros(len(test), dtype=bool)
                    include_one = np.zeros(len(test), dtype=bool)
                    for i, bin_name in enumerate(test["tanimoto_bin"].fillna("unknown").astype(str).tolist()):
                        subset0 = cal[(cal["tanimoto_bin"].eq(bin_name)) & (cal["y_true"].astype(int).eq(0))]
                        subset1 = cal[(cal["tanimoto_bin"].eq(bin_name)) & (cal["y_true"].astype(int).eq(1))]
                        q0_bin = q_conformal(subset0["y_pred"].to_numpy(), alpha) if len(subset0) >= 10 else q0
                        q1_bin = q_conformal((1.0 - subset1["y_pred"]).to_numpy(), alpha) if len(subset1) >= 10 else q1
                        include_zero[i] = test_p[i] <= q0_bin
                        include_one[i] = (1.0 - test_p[i]) <= q1_bin
                    covered = np.where(test_y == 1, include_one, include_zero)
                    set_size = include_zero.astype(int) + include_one.astype(int)
                    detail_rows.append(
                        {
                            "task": task,
                            "task_type": task_type,
                            "candidate": candidate,
                            "seed": int(seed),
                            "outer_fold": int(outer_fold),
                            "alpha": alpha,
                            "target_coverage": 1.0 - alpha,
                            "method": "mondrian_label_similarity_conformal",
                            "n_test": int(len(test)),
                            "coverage": float(covered.mean()),
                            "class_0_coverage": float(covered[test_y == 0].mean()) if np.any(test_y == 0) else math.nan,
                            "class_1_coverage": float(covered[test_y == 1].mean()) if np.any(test_y == 1) else math.nan,
                            "avg_set_size": float(set_size.mean()),
                            "avg_interval_width": math.nan,
                            "calibration_n": int(len(cal)),
                        }
                    )
                else:
                    cal_y = cal["y_true"].to_numpy(dtype=float)
                    cal_pred = cal["y_pred"].to_numpy(dtype=float)
                    test_y = test["y_true"].to_numpy(dtype=float)
                    test_pred = test["y_pred"].to_numpy(dtype=float)
                    q_all = q_conformal(np.abs(cal_y - cal_pred), alpha)
                    lo = test_pred - q_all
                    hi = test_pred + q_all
                    covered = (test_y >= lo) & (test_y <= hi)
                    detail_rows.append(
                        {
                            "task": task,
                            "task_type": task_type,
                            "candidate": candidate,
                            "seed": int(seed),
                            "outer_fold": int(outer_fold),
                            "alpha": alpha,
                            "target_coverage": 1.0 - alpha,
                            "method": "split_conformal_residual",
                            "n_test": int(len(test)),
                            "coverage": float(covered.mean()),
                            "class_0_coverage": math.nan,
                            "class_1_coverage": math.nan,
                            "avg_set_size": math.nan,
                            "avg_interval_width": float(np.mean(hi - lo)),
                            "calibration_n": int(len(cal)),
                        }
                    )
                    lo_m = np.empty(len(test), dtype=float)
                    hi_m = np.empty(len(test), dtype=float)
                    for i, bin_name in enumerate(test["tanimoto_bin"].fillna("unknown").astype(str).tolist()):
                        subset = cal[cal["tanimoto_bin"].eq(bin_name)]
                        q_bin = q_conformal(np.abs(subset["y_true"] - subset["y_pred"]), alpha) if len(subset) >= 20 else q_all
                        lo_m[i] = test_pred[i] - q_bin
                        hi_m[i] = test_pred[i] + q_bin
                    covered_m = (test_y >= lo_m) & (test_y <= hi_m)
                    detail_rows.append(
                        {
                            "task": task,
                            "task_type": task_type,
                            "candidate": candidate,
                            "seed": int(seed),
                            "outer_fold": int(outer_fold),
                            "alpha": alpha,
                            "target_coverage": 1.0 - alpha,
                            "method": "mondrian_similarity_residual",
                            "n_test": int(len(test)),
                            "coverage": float(covered_m.mean()),
                            "class_0_coverage": math.nan,
                            "class_1_coverage": math.nan,
                            "avg_set_size": math.nan,
                            "avg_interval_width": float(np.mean(hi_m - lo_m)),
                            "calibration_n": int(len(cal)),
                        }
                    )

    detail = pd.DataFrame(detail_rows)
    detail.to_csv(OUT / "conformal_crossfold_detail.csv", index=False)
    summary = (
        detail.groupby(["task", "task_type", "candidate", "alpha", "target_coverage", "method"], as_index=False)
        .agg(
            n_folds=("n_test", "size"),
            mean_n_test=("n_test", "mean"),
            mean_coverage=("coverage", "mean"),
            sd_coverage=("coverage", "std"),
            mean_class_0_coverage=("class_0_coverage", "mean"),
            mean_class_1_coverage=("class_1_coverage", "mean"),
            mean_set_size=("avg_set_size", "mean"),
            mean_interval_width=("avg_interval_width", "mean"),
        )
    )
    summary.to_csv(OUT / "conformal_crossfold_summary.csv", index=False)
    return detail, summary


def cqr_regression(contexts: dict[str, TaskContext]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    for task in ["esol", "freesolv", "lipo"]:
        ctx = contexts[task]
        x = ctx.morgan
        y = ctx.y.astype(float)
        for seed, splits in ctx.splits.items():
            for outer_fold, (outer_train, outer_test) in enumerate(splits, start=1):
                inner_splits, _ = shared.make_splits(y[outer_train], ctx.scaffolds[outer_train], "regression", 3, seed + outer_fold)
                tr_local, cal_local = inner_splits[0]
                train_idx = outer_train[tr_local]
                cal_idx = outer_train[cal_local]
                for alpha in ALPHAS:
                    lower_model = GradientBoostingRegressor(
                        loss="quantile",
                        alpha=alpha / 2.0,
                        n_estimators=45,
                        max_depth=2,
                        learning_rate=0.06,
                        subsample=0.85,
                        random_state=seed + outer_fold,
                    )
                    upper_model = GradientBoostingRegressor(
                        loss="quantile",
                        alpha=1.0 - alpha / 2.0,
                        n_estimators=45,
                        max_depth=2,
                        learning_rate=0.06,
                        subsample=0.85,
                        random_state=seed + outer_fold + 1000,
                    )
                    lower_model.fit(x[train_idx], y[train_idx])
                    upper_model.fit(x[train_idx], y[train_idx])
                    lo_cal = lower_model.predict(x[cal_idx])
                    hi_cal = upper_model.predict(x[cal_idx])
                    score = np.maximum(lo_cal - y[cal_idx], y[cal_idx] - hi_cal)
                    qhat = q_conformal(score, alpha)
                    lo = lower_model.predict(x[outer_test]) - qhat
                    hi = upper_model.predict(x[outer_test]) + qhat
                    covered = (y[outer_test] >= lo) & (y[outer_test] <= hi)
                    rows.append(
                        {
                            "task": task,
                            "seed": int(seed),
                            "outer_fold": int(outer_fold),
                            "alpha": alpha,
                            "target_coverage": 1.0 - alpha,
                            "method": "conformalized_quantile_regression_morgan",
                            "n_train": int(len(train_idx)),
                            "n_calibration": int(len(cal_idx)),
                            "n_test": int(len(outer_test)),
                            "coverage": float(covered.mean()),
                            "mean_interval_width": float(np.mean(hi - lo)),
                            "qhat": float(qhat),
                        }
                    )
    detail = pd.DataFrame(rows)
    detail.to_csv(OUT / "cqr_regression_detail.csv", index=False)
    summary = (
        detail.groupby(["task", "alpha", "target_coverage", "method"], as_index=False)
        .agg(
            n_folds=("coverage", "size"),
            mean_coverage=("coverage", "mean"),
            sd_coverage=("coverage", "std"),
            mean_interval_width=("mean_interval_width", "mean"),
            mean_qhat=("qhat", "mean"),
        )
    )
    summary.to_csv(OUT / "cqr_regression_summary.csv", index=False)
    return detail, summary


def ensemble_uncertainty(preds: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    unit_cols = ["task", "task_type", "seed", "outer_fold", "sample_index", "smiles", "y_true"]
    agg = (
        preds.groupby(unit_cols, as_index=False)
        .agg(mean_prediction=("y_pred", "mean"), prediction_std=("y_pred", "std"), n_candidates=("candidate", "nunique"))
    )
    for (task, task_type, seed, outer_fold), group in agg.groupby(["task", "task_type", "seed", "outer_fold"], sort=True):
        if task_type == "classification":
            prob = group["mean_prediction"].clip(1e-6, 1.0 - 1e-6).to_numpy()
            y = group["y_true"].astype(int).to_numpy()
            entropy = -(prob * np.log(prob) + (1.0 - prob) * np.log(1.0 - prob))
            uncertainty = entropy + group["prediction_std"].fillna(0.0).to_numpy()
            error = ((prob >= 0.5).astype(int) != y).astype(float)
        else:
            y = group["y_true"].to_numpy(dtype=float)
            uncertainty = group["prediction_std"].fillna(0.0).to_numpy()
            error = np.abs(group["mean_prediction"].to_numpy(dtype=float) - y)
        high_threshold = float(np.nanquantile(error, 0.75)) if len(error) else math.nan
        high_error = error >= high_threshold if np.isfinite(high_threshold) else np.zeros(len(error), dtype=bool)
        top_n = max(1, int(math.ceil(0.10 * len(group))))
        high_uncertainty = np.argsort(-uncertainty)[:top_n]
        base_rate = float(np.mean(high_error)) if len(high_error) else math.nan
        top_rate = float(np.mean(high_error[high_uncertainty])) if len(high_uncertainty) else math.nan
        rows.append(
            {
                "task": task,
                "task_type": task_type,
                "seed": int(seed),
                "outer_fold": int(outer_fold),
                "n": int(len(group)),
                "mean_candidate_count": float(group["n_candidates"].mean()),
                "uncertainty_error_spearman": safe_spearman(uncertainty, error),
                "risk_coverage_auc": risk_coverage_auc(error, uncertainty),
                "top10_uncertainty_high_error_rate": top_rate,
                "overall_high_error_rate": base_rate,
                "top10_high_error_enrichment": float(top_rate / base_rate) if base_rate and np.isfinite(base_rate) else math.nan,
            }
        )
    detail = pd.DataFrame(rows)
    detail.to_csv(OUT / "ensemble_uncertainty_detail.csv", index=False)
    summary = (
        detail.groupby(["task", "task_type"], as_index=False)
        .agg(
            n_units=("n", "size"),
            mean_uncertainty_error_spearman=("uncertainty_error_spearman", "mean"),
            mean_risk_coverage_auc=("risk_coverage_auc", "mean"),
            mean_top10_high_error_enrichment=("top10_high_error_enrichment", "mean"),
        )
    )
    overall = pd.DataFrame(
        [
            {
                "task": "__overall__",
                "task_type": "mixed",
                "n_units": int(len(detail)),
                "mean_uncertainty_error_spearman": float(detail["uncertainty_error_spearman"].mean()),
                "mean_risk_coverage_auc": float(detail["risk_coverage_auc"].mean()),
                "mean_top10_high_error_enrichment": float(detail["top10_high_error_enrichment"].mean()),
            }
        ]
    )
    summary = pd.concat([summary, overall], ignore_index=True)
    summary.to_csv(OUT / "ensemble_uncertainty_summary.csv", index=False)
    return summary


def calibration_under_ood(preds: pd.DataFrame, meta: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = preds[preds["candidate"].eq("rdkit_rf")].merge(
        meta[["task", "seed", "outer_fold", "sample_index", "max_train_tanimoto", "tanimoto_bin", "scaffold_status"]],
        on=["task", "seed", "outer_fold", "sample_index"],
        how="left",
    )
    data = data[data["task_type"].eq("classification")].copy()
    rows: list[dict[str, object]] = []
    for keys, group in data.groupby(["task", "seed", "outer_fold", "tanimoto_bin", "scaffold_status"], dropna=False, sort=True):
        task, seed, outer_fold, tan_bin, scaffold_status = keys
        y = group["y_true"].astype(int).to_numpy()
        p = group["y_pred"].clip(0.0, 1.0).to_numpy()
        metrics = classification_metrics(y, p)
        rows.append(
            {
                "task": task,
                "seed": int(seed),
                "outer_fold": int(outer_fold),
                "tanimoto_bin": tan_bin,
                "scaffold_status": scaffold_status,
                "n": int(len(group)),
                "positive_rate": float(np.mean(y)) if len(y) else math.nan,
                "mean_max_train_tanimoto": float(group["max_train_tanimoto"].mean()),
                **metrics,
            }
        )
    detail = pd.DataFrame(rows)
    detail.to_csv(OUT / "calibration_ood_scaffold_detail.csv", index=False)
    summary = (
        detail.groupby(["task", "tanimoto_bin", "scaffold_status"], as_index=False)
        .agg(
            n_units=("n", "size"),
            total_n=("n", "sum"),
            mean_positive_rate=("positive_rate", "mean"),
            mean_max_train_tanimoto=("mean_max_train_tanimoto", "mean"),
            mean_roc_auc=("roc_auc", "mean"),
            mean_pr_auc=("pr_auc", "mean"),
            mean_brier=("brier", "mean"),
            mean_ece=("ece", "mean"),
        )
    )
    summary.to_csv(OUT / "calibration_ood_scaffold_summary.csv", index=False)
    return detail, summary


def clintox_negative_result(preds: pd.DataFrame, conformal_summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    data = preds[(preds["task"].eq("clintox")) & (preds["task_type"].eq("classification"))].copy()
    for candidate, group in data.groupby("candidate", sort=True):
        y = group["y_true"].astype(int).to_numpy()
        p = group["y_pred"].clip(0.0, 1.0).to_numpy()
        pred_label = (p >= 0.5).astype(int)
        pos = y == 1
        neg = y == 0
        fn = int(np.sum(pos & (pred_label == 0)))
        tp = int(np.sum(pos & (pred_label == 1)))
        fp = int(np.sum(neg & (pred_label == 1)))
        tn = int(np.sum(neg & (pred_label == 0)))
        rows.append(
            {
                "candidate": candidate,
                "n_predictions": int(len(group)),
                "minority_positive_n": int(pos.sum()),
                "minority_positive_rate": float(pos.mean()),
                "true_positive": tp,
                "false_negative": fn,
                "false_positive": fp,
                "true_negative": tn,
                "minority_recall": float(tp / max(tp + fn, 1)),
                "minority_false_negative_rate": float(fn / max(tp + fn, 1)),
                "false_negative_cost_10x": float(10 * fn + fp),
            }
        )

    conformal = conformal_summary[
        conformal_summary["task"].eq("clintox")
        & conformal_summary["task_type"].eq("classification")
        & conformal_summary["alpha"].eq(0.10)
        & conformal_summary["method"].isin(["label_conditional_conformal", "mondrian_label_similarity_conformal"])
    ][["candidate", "method", "mean_class_1_coverage", "mean_set_size"]]
    out = pd.DataFrame(rows).merge(conformal, on="candidate", how="left")
    out.to_csv(OUT / "clintox_minority_negative_result.csv", index=False)
    return out


def selected_predictions(preds: pd.DataFrame) -> pd.DataFrame:
    sel = pd.read_csv(HARD / "six_task_strong_selection_detail.csv")[
        ["task", "task_type", "seed", "outer_fold", "selected_candidate"]
    ]
    merged = preds.merge(sel, on=["task", "task_type", "seed", "outer_fold"], how="inner")
    selected = merged[merged["candidate"].eq(merged["selected_candidate"])].copy()
    selected["candidate"] = "fzyc_selected"
    selected["family"] = "selection_policy"
    return selected[preds.columns]


def decision_value(preds: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cls = preds[preds["task_type"].eq("classification")].copy()
    strategies = pd.concat([cls, selected_predictions(preds[preds["task_type"].eq("classification")])], ignore_index=True)
    rows: list[dict[str, object]] = []
    for keys, group in strategies.groupby(["task", "seed", "outer_fold", "candidate"], sort=True):
        task, seed, outer_fold, candidate = keys
        y = group["y_true"].astype(int).to_numpy()
        p = group["y_pred"].to_numpy(dtype=float)
        prevalence = float(y.mean()) if len(y) else math.nan
        order = np.argsort(-p)
        oracle_hits = np.sort(y)[::-1]
        for budget in BUDGETS:
            n_top = max(1, int(math.ceil(budget * len(group))))
            chosen = order[:n_top]
            hits = int(y[chosen].sum())
            precision = float(hits / n_top)
            oracle = int(oracle_hits[:n_top].sum())
            rows.append(
                {
                    "task": task,
                    "seed": int(seed),
                    "outer_fold": int(outer_fold),
                    "candidate": candidate,
                    "budget_fraction": budget,
                    "n_screened": int(n_top),
                    "prevalence": prevalence,
                    "positives_found": hits,
                    "precision_at_budget": precision,
                    "enrichment_at_budget": float(precision / prevalence) if prevalence else math.nan,
                    "oracle_positives_at_budget": oracle,
                    "regret_vs_oracle_positives": int(oracle - hits),
                }
            )
    detail = pd.DataFrame(rows)
    detail.to_csv(OUT / "decision_enrichment_detail.csv", index=False)
    summary = (
        detail.groupby(["task", "candidate", "budget_fraction"], as_index=False)
        .agg(
            n_units=("positives_found", "size"),
            mean_n_screened=("n_screened", "mean"),
            mean_prevalence=("prevalence", "mean"),
            mean_positives_found=("positives_found", "mean"),
            mean_precision=("precision_at_budget", "mean"),
            mean_enrichment=("enrichment_at_budget", "mean"),
            mean_regret_vs_oracle=("regret_vs_oracle_positives", "mean"),
        )
    )
    summary.to_csv(OUT / "decision_enrichment_summary.csv", index=False)

    tox_rows: list[dict[str, object]] = []
    tox = strategies[strategies["task"].eq("clintox")].copy()
    for keys, group in tox.groupby(["seed", "outer_fold", "candidate"], sort=True):
        seed, outer_fold, candidate = keys
        y = group["y_true"].astype(int).to_numpy()
        p = group["y_pred"].to_numpy(dtype=float)
        pred = (p >= 0.5).astype(int)
        fn = int(np.sum((y == 1) & (pred == 0)))
        fp = int(np.sum((y == 0) & (pred == 1)))
        tox_rows.append(
            {
                "seed": int(seed),
                "outer_fold": int(outer_fold),
                "candidate": candidate,
                "threshold": 0.5,
                "n": int(len(group)),
                "toxicity_positive_rate": float(y.mean()),
                "false_negative": fn,
                "false_positive": fp,
                "cost_fn10_fp1": float(10 * fn + fp),
                "cost_per_100_molecules": float(100.0 * (10 * fn + fp) / max(len(group), 1)),
            }
        )
    tox_cost = pd.DataFrame(tox_rows)
    tox_cost.to_csv(OUT / "toxicity_false_negative_cost.csv", index=False)

    queue_rows: list[dict[str, object]] = []
    for keys, group in tox.groupby(["seed", "outer_fold", "candidate"], sort=True):
        seed, outer_fold, candidate = keys
        y = group["y_true"].astype(int).to_numpy()
        p = group["y_pred"].to_numpy(dtype=float)
        order_safe = np.argsort(p)
        for budget in BUDGETS:
            n_queue = max(1, int(math.ceil(budget * len(group))))
            advanced = order_safe[:n_queue]
            toxic_advanced = int(y[advanced].sum())
            queue_rows.append(
                {
                    "seed": int(seed),
                    "outer_fold": int(outer_fold),
                    "candidate": candidate,
                    "advance_budget_fraction": budget,
                    "n_advanced_as_low_toxicity": int(n_queue),
                    "toxic_molecules_advanced": toxic_advanced,
                    "toxic_advanced_rate": float(toxic_advanced / n_queue),
                }
            )
    queue = pd.DataFrame(queue_rows)
    queue.to_csv(OUT / "toxicity_queue_simulation.csv", index=False)
    return summary, tox_cost, queue


def systematic_failures(preds: pd.DataFrame, meta: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rdkit = preds[preds["candidate"].eq("rdkit_rf")].merge(
        meta[["task", "seed", "outer_fold", "sample_index", "max_train_tanimoto", "tanimoto_bin", "scaffold_status"]],
        on=["task", "seed", "outer_fold", "sample_index"],
        how="left",
    )
    rows: list[dict[str, object]] = []
    for task, group in rdkit.groupby("task", sort=True):
        task_type = str(group["task_type"].iloc[0])
        if task_type == "regression":
            g = group.copy()
            g["abs_error"] = (g["y_pred"] - g["y_true"]).abs()
            threshold = float(g["abs_error"].quantile(0.90))
            q_low, q_high = float(g["y_true"].quantile(0.05)), float(g["y_true"].quantile(0.95))
            candidates = [
                (
                    "low_tanimoto_high_error",
                    g[(g["max_train_tanimoto"] < 0.50) & (g["abs_error"] >= threshold)],
                    "Low nearest-neighbour similarity coincides with a top-decile prediction error.",
                ),
                (
                    "novel_scaffold_high_error",
                    g[(g["scaffold_status"].eq("novel_scaffold")) & (g["abs_error"] >= threshold)],
                    "The Bemis-Murcko scaffold is absent from the training fold and error is in the top decile.",
                ),
                (
                    "extreme_label_high_error",
                    g[((g["y_true"] <= q_low) | (g["y_true"] >= q_high)) & (g["abs_error"] >= threshold)],
                    "The target lies in an extreme-label tail where interpolation is unreliable.",
                ),
            ]
            for category, subset, reason in candidates:
                for row in subset.sort_values("abs_error", ascending=False).head(25).itertuples(index=False):
                    rows.append(
                        {
                            "category": category,
                            "source": "six_task_rdkit_rf",
                            "task": task,
                            "seed": int(row.seed),
                            "outer_fold": int(row.outer_fold),
                            "smiles": row.smiles,
                            "partner_smiles": "",
                            "y_true": float(row.y_true),
                            "y_pred": float(row.y_pred),
                            "abs_error": float(row.abs_error),
                            "error_type": "large_regression_error",
                            "max_train_tanimoto": float(row.max_train_tanimoto),
                            "scaffold_status": row.scaffold_status,
                            "reason": reason,
                        }
                    )
        else:
            g = group.copy()
            g["pred_label"] = (g["y_pred"] >= 0.5).astype(int)
            g["error_flag"] = g["pred_label"] != g["y_true"].astype(int)
            g["abs_error"] = (g["y_pred"] - g["y_true"]).abs()
            candidates = [
                (
                    "classification_false_negative",
                    g[(g["y_true"].astype(int).eq(1)) & (g["pred_label"].eq(0))],
                    "A positive-class molecule is below the fixed decision threshold.",
                ),
                (
                    "low_tanimoto_misclassification",
                    g[(g["max_train_tanimoto"] < 0.50) & (g["error_flag"])],
                    "Low nearest-neighbour similarity coincides with a classification error.",
                ),
                (
                    "novel_scaffold_misclassification",
                    g[(g["scaffold_status"].eq("novel_scaffold")) & (g["error_flag"])],
                    "The Bemis-Murcko scaffold is absent from the training fold and the class is misassigned.",
                ),
            ]
            for category, subset, reason in candidates:
                for row in subset.sort_values("abs_error", ascending=False).head(25).itertuples(index=False):
                    rows.append(
                        {
                            "category": category,
                            "source": "six_task_rdkit_rf",
                            "task": task,
                            "seed": int(row.seed),
                            "outer_fold": int(row.outer_fold),
                            "smiles": row.smiles,
                            "partner_smiles": "",
                            "y_true": float(row.y_true),
                            "y_pred": float(row.y_pred),
                            "abs_error": float(row.abs_error),
                            "error_type": "false_negative" if int(row.y_true) == 1 else "false_positive",
                            "max_train_tanimoto": float(row.max_train_tanimoto),
                            "scaffold_status": row.scaffold_status,
                            "reason": reason,
                        }
                    )

    cliff_paths = list((ROOT / "output").glob("*11*/*cliff_pair_cases.csv"))
    for path in cliff_paths[:1]:
        cliff = pd.read_csv(path)
        cliff = cliff[cliff["case_type"].astype(str).str.contains("failure", case=False, na=False)]
        for row in cliff.sort_values("gap_abs_error", ascending=False).head(25).itertuples(index=False):
            rows.append(
                {
                    "category": "activity_cliff_pair_failure",
                    "source": "MoleculeACE",
                    "task": row.task,
                    "seed": int(row.seed),
                    "outer_fold": math.nan,
                    "smiles": row.smiles_i,
                    "partner_smiles": row.smiles_j,
                    "y_true": float(row.y_i),
                    "y_pred": float(row.pred_i),
                    "abs_error": float(row.gap_abs_error),
                    "error_type": "activity_cliff_gap_underestimated",
                    "max_train_tanimoto": float(row.similarity),
                    "scaffold_status": "pair_similarity_high",
                    "reason": "A high-Tanimoto pair has a large activity gap that the model compresses.",
                }
            )

    for path in [
        ROOT / "reports" / "bro5_cycpept_pampa_20260611" / "test_predictions_with_ad.csv",
        ROOT / "reports" / "bro5_linpept_20260611" / "test_predictions_with_ad.csv",
    ]:
        if not path.exists():
            continue
        bro = pd.read_csv(path)
        if "abs_error" in bro.columns:
            bro["case_error"] = bro["abs_error"]
            subset = bro[(bro["split"].astype(str).eq("perimeter")) | (bro["max_train_valid_tanimoto"] < 0.70)]
            for row in subset.sort_values("case_error", ascending=False).head(25).itertuples(index=False):
                rows.append(
                    {
                        "category": "bRo5_perimeter_high_error",
                        "source": "bRo5",
                        "task": row.dataset,
                        "seed": int(row.seed),
                        "outer_fold": math.nan,
                        "smiles": row.smiles,
                        "partner_smiles": "",
                        "y_true": float(row.y_true),
                        "y_pred": float(row.y_pred),
                        "abs_error": float(row.case_error),
                        "error_type": "large_regression_error",
                        "max_train_tanimoto": float(row.max_train_valid_tanimoto),
                        "scaffold_status": str(row.tanimoto_bin),
                        "reason": "bRo5 perimeter molecule with low analogue support and large prediction error.",
                    }
                )
        elif "y_score" in bro.columns:
            bro["pred_label"] = (bro["y_score"] >= 0.5).astype(int)
            bro["error_flag"] = bro["pred_label"] != bro["y_true"].astype(int)
            subset = bro[(bro["error_flag"]) & ((bro["split"].astype(str).eq("perimeter")) | (bro["max_train_valid_tanimoto"] < 0.70))]
            for row in subset.sort_values("risk_score", ascending=False).head(25).itertuples(index=False):
                rows.append(
                    {
                        "category": "bRo5_perimeter_misclassification",
                        "source": "bRo5",
                        "task": row.dataset,
                        "seed": int(row.seed),
                        "outer_fold": math.nan,
                        "smiles": row.smiles,
                        "partner_smiles": "",
                        "y_true": float(row.y_true),
                        "y_pred": float(row.y_score),
                        "abs_error": float(abs(row.y_score - row.y_true)),
                        "error_type": "false_negative" if int(row.y_true) == 1 and row.y_score < 0.5 else "false_positive",
                        "max_train_tanimoto": float(row.max_train_valid_tanimoto),
                        "scaffold_status": str(row.tanimoto_bin),
                        "reason": "bRo5 perimeter peptide misclassified under low analogue support.",
                    }
                )

    pool = pd.DataFrame(rows)
    pool.to_csv(OUT / "systematic_failure_case_pool.csv", index=False)
    reps = (
        pool.sort_values(["category", "abs_error"], ascending=[True, False])
        .groupby("category", group_keys=False)
        .head(5)
        .reset_index(drop=True)
    )
    reps.to_csv(OUT / "systematic_failure_representatives.csv", index=False)
    summary = (
        pool.groupby(["category", "source"], as_index=False)
        .agg(
            n_cases=("smiles", "size"),
            n_tasks=("task", "nunique"),
            median_abs_error=("abs_error", "median"),
            median_max_train_tanimoto=("max_train_tanimoto", "median"),
        )
    )
    summary.to_csv(OUT / "failure_case_category_summary.csv", index=False)
    return reps, summary


def make_figures() -> list[str]:
    paths: list[str] = []

    mech = pd.read_csv(OUT / "mechanism_controlled_simulation_summary.csv")
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6), sharey=True)
    for ax, regime in zip(axes, mech["correlation_regime"].drop_duplicates().tolist()):
        sub = mech[mech["correlation_regime"].eq(regime)]
        for frac, group in sub.groupby("validation_information_fraction", sort=True):
            ax.plot(
                group["candidate_count"],
                group["fixed_k64_normalized_selection_loss"],
                marker="o",
                linewidth=1.8,
                label=f"{frac:.0%}",
            )
        ax.set_xscale("log", base=2)
        ax.set_xticks([4, 8, 16, 32, 64])
        ax.set_xticklabels(["4", "8", "16", "32", "64"])
        ax.set_title(regime.replace("_", " "), fontsize=10)
        ax.set_xlabel("K")
        ax.grid(axis="y", color="#d9dee7", linewidth=0.8)
    axes[0].set_ylabel("Fixed-scale selection loss")
    axes[-1].legend(title="Validation", frameon=False, fontsize=8)
    fig.tight_layout()
    for ext in ["png", "svg"]:
        path = OUT / f"fig_mechanism_selection_loss.{ext}"
        fig.savefig(path, dpi=300, bbox_inches="tight")
        paths.append(str(path))
    plt.close(fig)

    conf = pd.read_csv(OUT / "conformal_crossfold_summary.csv")
    conf = conf[(conf["candidate"].eq("rdkit_rf")) & (conf["alpha"].eq(0.10))]
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    plot = (
        conf.groupby(["task_type", "method"], as_index=False)
        .agg(mean_coverage=("mean_coverage", "mean"))
        .sort_values(["task_type", "method"])
    )
    label_map = {
        "label_conditional_conformal": "Label-conditional",
        "mondrian_label_similarity_conformal": "Mondrian label-sim",
        "split_conformal": "Split",
        "mondrian_similarity_residual": "Mondrian residual",
        "split_conformal_residual": "Residual split",
    }
    labels = (plot["task_type"] + "\n" + plot["method"].map(label_map).fillna(plot["method"])).tolist()
    ax.bar(np.arange(len(plot)), plot["mean_coverage"], color="#4f7db8")
    ax.axhline(0.90, color="#222222", linewidth=1.0)
    ax.set_xticks(np.arange(len(plot)))
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Mean coverage")
    ax.set_ylim(0, 1.05)
    ax.grid(axis="y", color="#d9dee7", linewidth=0.8)
    fig.tight_layout()
    for ext in ["png", "svg"]:
        path = OUT / f"fig_conformal_coverage.{ext}"
        fig.savefig(path, dpi=300, bbox_inches="tight")
        paths.append(str(path))
    plt.close(fig)

    decision = pd.read_csv(OUT / "decision_enrichment_summary.csv")
    keep = ["fzyc_selected", "chemberta_mtr_linear_probe", "molformer_linear_probe", "gnn_gcn"]
    decision = decision[decision["candidate"].isin(keep)]
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    for candidate, group in decision.groupby("candidate", sort=False):
        collapsed = group.groupby("budget_fraction", as_index=False)["mean_enrichment"].mean()
        label = candidate
        if candidate == "fzyc_selected":
            label = "FZYC selected (= RDKit-RF)"
        ax.plot(collapsed["budget_fraction"] * 100, collapsed["mean_enrichment"], marker="o", label=label)
    ax.set_xlabel("Screening budget (%)")
    ax.set_ylabel("Mean enrichment")
    ax.set_xticks([1, 5, 10])
    ax.grid(axis="y", color="#d9dee7", linewidth=0.8)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    for ext in ["png", "svg"]:
        path = OUT / f"fig_decision_enrichment.{ext}"
        fig.savefig(path, dpi=300, bbox_inches="tight")
        paths.append(str(path))
    plt.close(fig)
    return paths


def write_audit(values: dict[str, object]) -> None:
    audit = {
        **values,
        "output_dir": str(OUT),
        "required_mechanism_grid_complete": bool(
            (OUT / "mechanism_controlled_simulation_summary.csv").exists()
            and len(pd.read_csv(OUT / "mechanism_controlled_simulation_summary.csv")) == 3 * 4 * 5
        ),
        "label_conditional_conformal_done": "label_conditional_conformal"
        in set(pd.read_csv(OUT / "conformal_crossfold_summary.csv")["method"]),
        "mondrian_conformal_done": any(
            "mondrian" in m for m in pd.read_csv(OUT / "conformal_crossfold_summary.csv")["method"].unique()
        ),
        "cqr_done": (OUT / "cqr_regression_summary.csv").exists(),
        "ensemble_uncertainty_done": (OUT / "ensemble_uncertainty_summary.csv").exists(),
        "ood_calibration_done": (OUT / "calibration_ood_scaffold_summary.csv").exists(),
        "clintox_negative_done": (OUT / "clintox_minority_negative_result.csv").exists(),
        "decision_value_done": (OUT / "decision_enrichment_summary.csv").exists(),
        "toxicity_queue_done": (OUT / "toxicity_queue_simulation.csv").exists(),
        "systematic_failures_done": (OUT / "systematic_failure_representatives.csv").exists(),
    }
    audit["passed"] = all(v for k, v in audit.items() if k.endswith("_done") or k.endswith("_complete"))
    (OUT / "sci1_mechanism_uq_decision_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    preds = pd.read_csv(HARD / "six_task_strong_baseline_outer_predictions.csv")
    contexts = load_contexts()
    meta = build_sample_metadata(contexts)

    mechanism = mechanism_experiment()
    conformal_detail, conformal_summary = conformal_crossfold(preds, meta)
    cqr_detail, cqr_summary = cqr_regression(contexts)
    ensemble_summary = ensemble_uncertainty(preds)
    calibration_detail, calibration_summary = calibration_under_ood(preds, meta)
    clin = clintox_negative_result(preds, conformal_summary)
    decision_summary, tox_cost, queue = decision_value(preds)
    failures, failure_summary = systematic_failures(preds, meta)
    figure_paths = make_figures()

    values = {
        "mechanism_rows": int(len(mechanism)),
        "conformal_detail_rows": int(len(conformal_detail)),
        "cqr_rows": int(len(cqr_detail)),
        "ensemble_summary_rows": int(len(ensemble_summary)),
        "calibration_detail_rows": int(len(calibration_detail)),
        "clintox_rows": int(len(clin)),
        "decision_summary_rows": int(len(decision_summary)),
        "toxicity_cost_rows": int(len(tox_cost)),
        "queue_rows": int(len(queue)),
        "failure_representative_rows": int(len(failures)),
        "failure_summary_rows": int(len(failure_summary)),
        "figure_paths": figure_paths,
    }
    write_audit(values)
    print(json.dumps(values, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
