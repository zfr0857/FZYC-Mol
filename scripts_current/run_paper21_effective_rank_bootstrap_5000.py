from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy.stats import rankdata
from sklearn.covariance import LedoitWolf


ROOT = Path("D:/fzyc")
BASE = Path(os.environ.get("FZYC_PREFIX_BASE", ROOT / "results" / "nested_selection" / "repeated_nested"))
OUT = Path(os.environ.get("FZYC_ANALYSIS_OUT", ROOT / "output" / "paper21_final_reanalysis_20260713"))
SEEDS = [11, 23, 37, 53, 71]
KS = [4, 8, 16, 32]
MODES = ["raw", "row_centred", "fixed_reference_relative", "within_unit_rank"]
N_BOOT = 5000
MASTER_SEED = 20260713


def load_outer() -> pd.DataFrame:
    frames = []
    for seed in SEEDS:
        frame = pd.read_csv(BASE / f"seed_{seed}" / "outer_candidate_scores.csv").rename(
            columns={"dataset": "task"}
        )
        if "seed" not in frame:
            frame.insert(0, "seed", seed)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def corr_from_cov(cov: np.ndarray) -> np.ndarray:
    scale = np.sqrt(np.clip(np.diag(cov), 1e-15, None))
    corr = np.clip(cov / np.outer(scale, scale), -1.0, 1.0)
    np.fill_diagonal(corr, 1.0)
    return corr


def rank_metrics(x: np.ndarray, shrinkage: bool) -> dict[str, float]:
    keep = np.nanstd(x, axis=0) > 1e-12
    x = np.asarray(x[:, keep], dtype=float)
    if x.shape[1] <= 1:
        return {"entropy_rank": 1.0, "participation_rank": 1.0, "median_correlation": 1.0}
    if shrinkage:
        sd = x.std(axis=0, ddof=1)
        z = (x - x.mean(axis=0)) / np.where(sd > 1e-12, sd, 1.0)
        corr = corr_from_cov(LedoitWolf().fit(z).covariance_)
    else:
        corr = np.nan_to_num(np.corrcoef(x, rowvar=False), nan=0.0)
        np.fill_diagonal(corr, 1.0)
    eig = np.clip(np.linalg.eigvalsh(corr), 0.0, None)
    total = float(eig.sum())
    p = eig / total if total > 0 else np.ones_like(eig) / len(eig)
    positive = p[p > 1e-15]
    off = corr[np.triu_indices_from(corr, k=1)]
    return {
        "entropy_rank": float(np.exp(-(positive * np.log(positive)).sum())),
        "participation_rank": float(total * total / np.square(eig).sum()),
        "median_correlation": float(np.median(off)) if len(off) else 1.0,
    }


def transform(x: np.ndarray, mode: str, reference_index: int = 0) -> np.ndarray:
    if mode == "raw":
        return x
    if mode == "row_centred":
        return x - x.mean(axis=1, keepdims=True)
    if mode == "within_unit_rank":
        return np.apply_along_axis(rankdata, 1, x)
    if mode == "fixed_reference_relative":
        keep = [j for j in range(x.shape[1]) if j != reference_index]
        return x[:, keep] - x[:, [reference_index]]
    raise ValueError(mode)


def hierarchical_indices(seed_values: np.ndarray, fold_values: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    rows = []
    for sampled_seed in rng.choice(SEEDS, size=len(SEEDS), replace=True):
        available = np.flatnonzero(seed_values == sampled_seed)
        rows.extend(rng.choice(available, size=3, replace=True).tolist())
    return np.asarray(rows, dtype=int)


def run_job(job: dict[str, object]) -> tuple[dict[str, object], list[dict[str, object]]]:
    raw = np.asarray(job["matrix"], dtype=float)
    seed_values = np.asarray(job["seed_values"], dtype=int)
    fold_values = np.asarray(job["fold_values"], dtype=int)
    mode = str(job["mode"])
    ref_index = int(job.get("reference_index", 0))
    rng = np.random.default_rng(int(job["rng_seed"]))
    point_emp = rank_metrics(transform(raw, mode, ref_index), False)
    point_lw = rank_metrics(transform(raw, mode, ref_index), True)
    draws = []
    values = {name: np.empty(N_BOOT, dtype=float) for name in point_lw}
    for b in range(N_BOOT):
        idx = hierarchical_indices(seed_values, fold_values, rng)
        metrics = rank_metrics(transform(raw[idx], mode, ref_index), True)
        for name, value in metrics.items():
            values[name][b] = value
            draws.append({
                "task": job["task"], "task_type": job["task_type"],
                "candidate_count": job["candidate_count"], "transformation": mode,
                "reference_label": job.get("reference_label", "candidate_1"),
                "bootstrap": b + 1, "metric": name, "value": value,
            })
    summary = {
        "task": job["task"], "task_type": job["task_type"],
        "candidate_count": job["candidate_count"], "transformation": mode,
        "reference_label": job.get("reference_label", "candidate_1"),
        "n_outer_units": raw.shape[0], "n_columns_after_transform": transform(raw, mode, ref_index).shape[1],
        "bootstrap_replicates": N_BOOT,
        "split_replication_status": job["split_replication_status"],
    }
    for name in point_lw:
        summary[f"empirical_{name}"] = point_emp[name]
        summary[f"ledoit_wolf_{name}"] = point_lw[name]
        summary[f"bootstrap_median_{name}"] = float(np.median(values[name]))
        summary[f"bootstrap_ci95_low_{name}"] = float(np.quantile(values[name], 0.025))
        summary[f"bootstrap_ci95_high_{name}"] = float(np.quantile(values[name], 0.975))
        for n in [1000, 2000, 3000, 4000, 5000]:
            prefix = f"mc_{n}_{name}"
            summary[f"{prefix}_median"] = float(np.median(values[name][:n]))
            summary[f"{prefix}_ci_low"] = float(np.quantile(values[name][:n], 0.025))
            summary[f"{prefix}_ci_high"] = float(np.quantile(values[name][:n], 0.975))
    return summary, draws


def omission_sensitivity(matrix: pd.DataFrame, mode: str) -> list[dict[str, object]]:
    rows = []
    for omission_type, values, column in [("seed", SEEDS, "seed"), ("outer_fold", [1, 2, 3], "outer_fold")]:
        for omitted in values:
            x = matrix.loc[~matrix[column].eq(omitted)].drop(columns=["seed", "outer_fold"]).to_numpy(float)
            metrics = rank_metrics(transform(x, mode), True)
            rows.append({"omission_type": omission_type, "omitted": omitted, **metrics})
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    outer = load_outer()
    jobs = []
    omissions = []
    job_index = 0
    reference_orders = {
        "candidate_1": 1,
        "predefined_linear_baseline": 2,
        "fixed_morgan_rf": 5,
        "registry_median_candidate": 16,
    }
    for task in sorted(outer["task"].unique()):
        task_type = str(outer.loc[outer["task"].eq(task), "task_type"].iloc[0])
        split_status = "five distinct seeded scaffold partitions"
        for k in KS:
            matrix = outer.loc[outer["task"].eq(task) & outer["candidate_order"].le(k)].pivot_table(
                index=["seed", "outer_fold"], columns="candidate_order", values="outer_utility"
            ).reset_index()
            raw = matrix.drop(columns=["seed", "outer_fold"]).to_numpy(float)
            for mode in MODES:
                jobs.append({
                    "task": task, "task_type": task_type, "candidate_count": k,
                    "mode": mode, "reference_label": "candidate_1", "reference_index": 0,
                    "matrix": raw, "seed_values": matrix["seed"].to_numpy(),
                    "fold_values": matrix["outer_fold"].to_numpy(),
                    "split_replication_status": split_status,
                    "rng_seed": MASTER_SEED + job_index * 9973,
                })
                job_index += 1
                if k == 32:
                    for row in omission_sensitivity(matrix, mode):
                        omissions.append({"task": task, "task_type": task_type, "transformation": mode, **row})
            if k == 32:
                orders = list(matrix.drop(columns=["seed", "outer_fold"]).columns.astype(int))
                for label, order in reference_orders.items():
                    if label == "candidate_1":
                        continue
                    jobs.append({
                        "task": task, "task_type": task_type, "candidate_count": k,
                        "mode": "fixed_reference_relative", "reference_label": label,
                        "reference_index": orders.index(order), "matrix": raw,
                        "seed_values": matrix["seed"].to_numpy(),
                        "fold_values": matrix["outer_fold"].to_numpy(),
                        "split_replication_status": split_status,
                        "rng_seed": MASTER_SEED + job_index * 9973,
                    })
                    job_index += 1
    n_jobs = min(12, max(1, (os.cpu_count() or 2) - 1))
    results = Parallel(n_jobs=n_jobs, backend="loky", verbose=10)(delayed(run_job)(job) for job in jobs)
    summaries = pd.DataFrame([item[0] for item in results])
    draws = pd.DataFrame([row for item in results for row in item[1]])
    summaries.to_csv(OUT / "effective_rank_bootstrap_5000_summary.csv", index=False)
    draws.to_csv(OUT / "effective_rank_bootstrap_5000_draws.csv.gz", index=False, compression="gzip")
    pd.DataFrame(omissions).to_csv(OUT / "effective_rank_leave_one_out.csv", index=False)
    reference = summaries.loc[
        summaries["transformation"].eq("fixed_reference_relative") & summaries["candidate_count"].eq(32)
    ]
    reference.to_csv(OUT / "effective_rank_reference_sensitivity.csv", index=False)
    stability_rows = []
    for _, row in summaries.iterrows():
        for metric in ["entropy_rank", "participation_rank", "median_correlation"]:
            stability_rows.append({
                "task": row["task"], "task_type": row["task_type"],
                "candidate_count": row["candidate_count"], "transformation": row["transformation"],
                "reference_label": row["reference_label"], "metric": metric,
                "abs_median_change_4000_to_5000": abs(row[f"mc_5000_{metric}_median"] - row[f"mc_4000_{metric}_median"]),
                "abs_ci_low_change_4000_to_5000": abs(row[f"mc_5000_{metric}_ci_low"] - row[f"mc_4000_{metric}_ci_low"]),
                "abs_ci_high_change_4000_to_5000": abs(row[f"mc_5000_{metric}_ci_high"] - row[f"mc_4000_{metric}_ci_high"]),
            })
    stability = pd.DataFrame(stability_rows)
    stability.to_csv(OUT / "effective_rank_monte_carlo_stability.csv", index=False)
    audit = {
        "hierarchical_bootstrap_replicates": N_BOOT,
        "master_seed": MASTER_SEED,
        "n_jobs": n_jobs,
        "n_analysis_jobs": len(jobs),
        "max_abs_median_change_4000_to_5000": float(stability["abs_median_change_4000_to_5000"].max()),
        "max_abs_ci_bound_change_4000_to_5000": float(stability[["abs_ci_low_change_4000_to_5000", "abs_ci_high_change_4000_to_5000"]].to_numpy().max()),
        "regression_uncertainty_note": "The hierarchical bootstrap resamples five distinct seeded scaffold partitions and their outer folds; endpoint-level intervals remain conditional on the predefined split generator.",
    }
    (OUT / "effective_rank_bootstrap_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
