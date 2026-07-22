from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path("D:/fzyc")
MINOR = Path(os.environ.get("FZYC_MINOR_OUT", ROOT / "output" / "paper25_pre_submission_minor_revision_20260715"))
ANALYSIS = Path(os.environ.get("FZYC_ANALYSIS_OUT", ROOT / "output" / "paper22_major_revision_20260713"))
SEEDS = [11, 23, 37, 53, 71]
KS = [4, 8, 16, 32]
SIGNALS = [0.0, 0.10, 0.25, 0.50, 0.75, 1.0]
CLASS_TASKS = ["bace", "bbbp", "clintox", "tdc_hia_hou", "tdc_pgp_broccatelli"]
REG_TASKS = ["esol", "freesolv", "lipo", "tdc_caco2_wang"]
RNG_SEED = 20260716


def harmonic(k: int) -> float:
    return float(np.sum(1.0 / np.arange(1, k + 1)))


def load_locked_outer_utilities() -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for seed in SEEDS:
        for task in CLASS_TASKS:
            path = ROOT / "results" / "nested_selection" / "repeated_nested" / f"seed_{seed}" / "tasks" / task / "outer_candidate_scores.csv"
            frame = pd.read_csv(path)
            frame["split_seed"] = seed
            frame["locked_source"] = "classification_original_locked"
            rows.append(frame)
        for task in REG_TASKS:
            path = ROOT / "results" / "regression_seeded_scaffold_20260713" / "prefix32" / f"seed_{seed}" / "tasks" / task / "outer_candidate_scores.csv"
            frame = pd.read_csv(path)
            frame["split_seed"] = seed
            frame["locked_source"] = "regression_distinct_seed_revision"
            rows.append(frame)
    data = pd.concat(rows, ignore_index=True)
    data = data.rename(columns={"dataset": "task"})
    expected = len(SEEDS) * (len(CLASS_TASKS) + len(REG_TASKS)) * 3 * 32
    if len(data) != expected:
        raise RuntimeError(f"Expected {expected} candidate rows, found {len(data)}")
    counts = data.groupby(["task", "split_seed", "outer_fold"]).candidate_order.nunique()
    if not counts.eq(32).all():
        raise RuntimeError("Every locked outer unit must contain exactly 32 candidate utilities")
    return data


def permutation_null(reps: int = 5000) -> tuple[pd.DataFrame, pd.DataFrame]:
    ranking = pd.read_csv(ANALYSIS / "chance_adjusted_ranking_units.csv")
    rng = np.random.default_rng(RNG_SEED)
    draw_rows: list[dict[str, float | int]] = []
    summary_rows: list[dict[str, float | int]] = []
    for k in KS:
        observed = ranking[ranking.candidate_count.eq(k)].sort_values(["task", "split_seed", "outer_fold"])
        tasks = observed.task.drop_duplicates().tolist()
        if len(observed) != 9 * 5 * 3 or len(tasks) != 9:
            raise RuntimeError(f"Unexpected ranking-unit structure at K={k}")
        ranks = rng.integers(1, k + 1, size=(reps, len(observed)))
        chance = min(3, k) / k
        cah = ((ranks <= min(3, k)).astype(float) - chance) / (1.0 - chance)
        random_mrr = harmonic(k) / k
        nmrr = ((1.0 / ranks) - random_mrr) / (1.0 - random_mrr)
        # Rows are task-major after sorting: 9 endpoints x 15 repeated outer units.
        cah_endpoint = cah.reshape(reps, 9, 15).mean(axis=2)
        nmrr_endpoint = nmrr.reshape(reps, 9, 15).mean(axis=2)
        cah_median = np.median(cah_endpoint, axis=1)
        nmrr_median = np.median(nmrr_endpoint, axis=1)
        draw_rows.extend(
            {
                "permutation": i + 1,
                "candidate_count": k,
                "chance_adjusted_hit_endpoint_median": float(cah_median[i]),
                "normalized_mrr_gain_endpoint_median": float(nmrr_median[i]),
            }
            for i in range(reps)
        )
        obs_endpoint = observed.groupby("task", as_index=False).agg(
            chance_adjusted_hit=("chance_adjusted_hit", "mean"),
            normalized_mrr_gain=("normalized_mrr_gain", "mean"),
        )
        for metric, null_values in [
            ("chance_adjusted_hit", cah_median),
            ("normalized_mrr_gain", nmrr_median),
        ]:
            obs_value = float(obs_endpoint[metric].median())
            summary_rows.append(
                {
                    "candidate_count": k,
                    "metric": metric,
                    "observed_endpoint_median": obs_value,
                    "null_median": float(np.median(null_values)),
                    "null_q025": float(np.quantile(null_values, 0.025)),
                    "null_q975": float(np.quantile(null_values, 0.975)),
                    "one_sided_p_observed_le_null": float((1 + np.sum(null_values >= obs_value)) / (reps + 1)),
                    "permutations": reps,
                }
            )
    return pd.DataFrame(draw_rows), pd.DataFrame(summary_rows)


def signal_recovery(outer: pd.DataFrame, reps: int = 500) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    rng = np.random.default_rng(RNG_SEED + 1)
    rows: list[dict[str, float | int | str]] = []
    keys = ["task", "task_type", "split_seed", "outer_fold", "locked_source"]
    for values, unit in outer.groupby(keys, sort=True):
        task, task_type, seed, outer_fold, source = values
        unit = unit.sort_values("candidate_order")
        full = unit.outer_utility.to_numpy(float)
        full_range = max(float(np.ptp(full)), 1e-12)
        for k in KS:
            utility = full[:k]
            oracle = int(np.argmax(utility))
            z = (utility - utility.mean()) / max(float(utility.std(ddof=0)), 1e-12)
            chance = min(3, k) / k
            random_mrr = harmonic(k) / k
            for signal in SIGNALS:
                n = 1 if signal == 1.0 else reps
                noise = rng.normal(size=(n, k))
                score = signal * z[None, :] + np.sqrt(max(0.0, 1.0 - signal**2)) * noise
                order = np.argsort(-score, axis=1)
                rank = np.argmax(order == oracle, axis=1) + 1
                selected = order[:, 0]
                top3 = (rank <= min(3, k)).astype(float)
                rows.append(
                    {
                        "task": task,
                        "task_type": task_type,
                        "split_seed": seed,
                        "outer_fold": outer_fold,
                        "candidate_count": k,
                        "injected_signal": signal,
                        "simulation_replicates": n,
                        "chance_adjusted_hit": float(np.mean((top3 - chance) / (1.0 - chance))),
                        "normalized_mrr_gain": float(np.mean(((1.0 / rank) - random_mrr) / (1.0 - random_mrr))),
                        "fixed_range_selection_loss": float(np.mean((utility[oracle] - utility[selected]) / full_range)),
                        "locked_source": source,
                    }
                )
    units = pd.DataFrame(rows)
    endpoint = units.groupby(["task", "task_type", "candidate_count", "injected_signal"], as_index=False).agg(
        chance_adjusted_hit=("chance_adjusted_hit", "mean"),
        normalized_mrr_gain=("normalized_mrr_gain", "mean"),
        fixed_range_selection_loss=("fixed_range_selection_loss", "mean"),
    )
    summaries: list[dict[str, float | int]] = []
    for (k, signal), group in endpoint.groupby(["candidate_count", "injected_signal"], sort=True):
        row: dict[str, float | int] = {"candidate_count": int(k), "injected_signal": float(signal), "endpoints": len(group)}
        for metric in ["chance_adjusted_hit", "normalized_mrr_gain", "fixed_range_selection_loss"]:
            values = group[metric].to_numpy(float)
            row[f"{metric}_median"] = float(np.median(values))
            row[f"{metric}_q25"] = float(np.quantile(values, 0.25))
            row[f"{metric}_q75"] = float(np.quantile(values, 0.75))
        summaries.append(row)
    summary = pd.DataFrame(summaries)
    monotonic: dict[str, object] = {}
    for k, group in summary.groupby("candidate_count"):
        group = group.sort_values("injected_signal")
        monotonic[str(int(k))] = {
            "chance_adjusted_hit_non_decreasing": bool(np.all(np.diff(group.chance_adjusted_hit_median) >= -1e-12)),
            "normalized_mrr_gain_non_decreasing": bool(np.all(np.diff(group.normalized_mrr_gain_median) >= -1e-12)),
            "selection_loss_non_increasing": bool(np.all(np.diff(group.fixed_range_selection_loss_median) <= 1e-12)),
        }
    audit = {
        "locked_outer_rows": len(outer),
        "locked_outer_units": int(outer.groupby(["task", "split_seed", "outer_fold"]).ngroups),
        "tasks": int(outer.task.nunique()),
        "distinct_split_seeds": sorted(int(x) for x in outer.split_seed.unique()),
        "signal_levels": SIGNALS,
        "simulation_replicates_per_nonperfect_cell": reps,
        "monotonicity": monotonic,
    }
    return units, summary, audit


def main() -> None:
    MINOR.mkdir(parents=True, exist_ok=True)
    outer = load_locked_outer_utilities()
    null_draws, null_summary = permutation_null()
    signal_units, signal_summary, audit = signal_recovery(outer)
    null_draws.to_csv(MINOR / "mechanism_permutation_null_draws.csv.gz", index=False, compression="gzip")
    null_summary.to_csv(MINOR / "mechanism_permutation_null_summary.csv", index=False)
    signal_units.to_csv(MINOR / "mechanism_signal_recovery_units.csv", index=False)
    signal_summary.to_csv(MINOR / "mechanism_signal_recovery_summary.csv", index=False)
    result = {
        **audit,
        "permutation_replicates": int(null_draws.permutation.max()),
        "all_observed_cahit_above_null_975": bool(
            (null_summary.query("metric == 'chance_adjusted_hit'").observed_endpoint_median.to_numpy()
             > null_summary.query("metric == 'chance_adjusted_hit'").null_q975.to_numpy()).all()
        ),
        "max_null_signal_abs_cahit": float(signal_summary.query("injected_signal == 0").chance_adjusted_hit_median.abs().max()),
        "max_perfect_signal_selection_loss": float(signal_summary.query("injected_signal == 1").fixed_range_selection_loss_median.max()),
    }
    (MINOR / "mechanism_calibration_audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
