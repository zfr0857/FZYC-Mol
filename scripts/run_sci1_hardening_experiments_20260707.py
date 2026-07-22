from __future__ import annotations

import json
import math
import shutil
import sys
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_paper12_strict_gap_experiments as strict


OUT = ROOT / "output" / "sci1_hardening_20260707"
TASKS6 = ["esol", "freesolv", "lipo", "bbbp", "bace", "clintox"]
SEEDS = [11, 23, 37, 53, 71]


def locate_strict_dir() -> Path:
    hits = [
        p
        for p in (ROOT / "output").iterdir()
        if p.is_dir() and (p / "strong_baseline_outer_scores.csv").exists()
    ]
    if not hits:
        raise FileNotFoundError("No strict strong-baseline output directory found.")
    return max(hits, key=lambda p: (p / "strong_baseline_outer_scores.csv").stat().st_mtime)


def locate_multiview_dir() -> Path:
    path = ROOT / "results" / "reviewer_core_20260624" / "multiview_nested"
    required = ["inner_scores.csv", "outer_candidate_scores.csv", "policy_detail.csv"]
    missing = [name for name in required if not (path / name).exists()]
    if missing:
        raise FileNotFoundError(f"Missing multiview outputs: {missing}")
    return path


def ci95(values: pd.Series) -> tuple[float, float, float]:
    x = pd.to_numeric(values, errors="coerce").dropna()
    if len(x) == 0:
        return math.nan, math.nan, math.nan
    mean = float(x.mean())
    if len(x) == 1:
        return mean, math.nan, math.nan
    se = float(x.std(ddof=1) / math.sqrt(len(x)))
    return mean, mean - 1.96 * se, mean + 1.96 * se


def strong_selection_and_pairing(strict_dir: Path) -> dict[str, object]:
    outer = pd.read_csv(strict_dir / "strong_baseline_outer_scores.csv")
    inner = pd.read_csv(strict_dir / "strong_baseline_inner_scores.csv")
    preds = pd.read_csv(strict_dir / "strong_baseline_outer_predictions.csv")

    OUT.mkdir(parents=True, exist_ok=True)
    for name in [
        "strong_baseline_registry.csv",
        "strong_baseline_inner_scores.csv",
        "strong_baseline_outer_scores.csv",
        "strong_baseline_outer_predictions.csv",
        "error_overlap_pairwise_detail.csv",
        "error_overlap_pairwise_summary.csv",
        "strong_baseline_runtime_status.csv",
    ]:
        src = strict_dir / name
        if src.exists():
            shutil.copy2(src, OUT / f"six_task_{name}")

    selection_rows = []
    paired_rows = []
    unit_cols = ["task", "task_type", "seed", "outer_fold"]
    for unit, group in outer.groupby(unit_cols, sort=True):
        task, task_type, seed, outer_fold = unit
        group = group.dropna(subset=["outer_utility", "inner_mean"]).copy()
        if group.empty:
            continue
        selected = group.sort_values(["inner_mean", "candidate_order"], ascending=[False, True]).iloc[0]
        oracle = group.sort_values(["outer_utility", "candidate_order"], ascending=[False, True]).iloc[0]
        full_range = max(float(group["outer_utility"].max() - group["outer_utility"].min()), 1e-12)
        validation_rank = (
            group.sort_values(["inner_mean", "candidate_order"], ascending=[False, True])
            .reset_index(drop=True)
            .reset_index()
        )
        oracle_rank = int(validation_rank.loc[validation_rank["candidate"].eq(oracle["candidate"]), "index"].iloc[0]) + 1
        rho = group[["inner_mean", "outer_utility"]].corr(method="spearman").iloc[0, 1]
        selection_rows.append(
            {
                "task": task,
                "task_type": task_type,
                "seed": int(seed),
                "outer_fold": int(outer_fold),
                "candidate_count": int(len(group)),
                "selected_candidate": selected["candidate"],
                "oracle_candidate": oracle["candidate"],
                "selected_outer_utility": float(selected["outer_utility"]),
                "oracle_outer_utility": float(oracle["outer_utility"]),
                "selection_loss": float(oracle["outer_utility"] - selected["outer_utility"]),
                "range_normalized_selection_loss": float((oracle["outer_utility"] - selected["outer_utility"]) / full_range),
                "outer_top1_hit": bool(selected["candidate"] == oracle["candidate"]),
                "oracle_validation_rank": oracle_rank,
                "inner_outer_spearman": float(rho) if pd.notna(rho) else np.nan,
            }
        )
        rdkit = group[group["candidate"].eq("rdkit_rf")]
        if not rdkit.empty:
            rd = rdkit.iloc[0]
            for _, row in group[~group["candidate"].eq("rdkit_rf")].iterrows():
                paired_rows.append(
                    {
                        "task": task,
                        "task_type": task_type,
                        "seed": int(seed),
                        "outer_fold": int(outer_fold),
                        "candidate": row["candidate"],
                        "candidate_family": row["family"],
                        "candidate_outer_utility": float(row["outer_utility"]),
                        "rdkit_outer_utility": float(rd["outer_utility"]),
                        "delta_vs_rdkit": float(row["outer_utility"] - rd["outer_utility"]),
                        "beats_rdkit": bool(row["outer_utility"] > rd["outer_utility"]),
                    }
                )

    selection = pd.DataFrame(selection_rows)
    paired = pd.DataFrame(paired_rows)
    selection.to_csv(OUT / "six_task_strong_selection_detail.csv", index=False)
    paired.to_csv(OUT / "six_task_strong_paired_vs_rdkit_detail.csv", index=False)

    selection_summary = selection.groupby(["task", "task_type"], as_index=False).agg(
        n_units=("selection_loss", "size"),
        top1_hit_rate=("outer_top1_hit", "mean"),
        mean_selection_loss=("selection_loss", "mean"),
        mean_range_normalized_selection_loss=("range_normalized_selection_loss", "mean"),
        mean_inner_outer_spearman=("inner_outer_spearman", "mean"),
        selected_candidates=("selected_candidate", lambda s: ";".join(sorted(set(map(str, s))))),
    )
    overall = pd.DataFrame(
        [
            {
                "task": "__overall__",
                "task_type": "mixed",
                "n_units": len(selection),
                "top1_hit_rate": float(selection["outer_top1_hit"].mean()),
                "mean_selection_loss": float(selection["selection_loss"].mean()),
                "mean_range_normalized_selection_loss": float(selection["range_normalized_selection_loss"].mean()),
                "mean_inner_outer_spearman": float(selection["inner_outer_spearman"].mean()),
                "selected_candidates": ";".join(sorted(set(map(str, selection["selected_candidate"])))),
            }
        ]
    )
    selection_summary = pd.concat([selection_summary, overall], ignore_index=True)
    selection_summary.to_csv(OUT / "six_task_strong_selection_scorecard.csv", index=False)

    pair_summary_rows = []
    for (candidate, task, task_type), group in paired.groupby(["candidate", "task", "task_type"], sort=True):
        mean, lo, hi = ci95(group["delta_vs_rdkit"])
        pair_summary_rows.append(
            {
                "candidate": candidate,
                "task": task,
                "task_type": task_type,
                "n_units": len(group),
                "mean_delta_vs_rdkit": mean,
                "ci95_low": lo,
                "ci95_high": hi,
                "win_rate_vs_rdkit": float(group["beats_rdkit"].mean()),
            }
        )
    pair_summary = pd.DataFrame(pair_summary_rows)
    pair_summary.to_csv(OUT / "six_task_strong_paired_vs_rdkit_summary.csv", index=False)

    endpoint_table = outer.groupby(["task", "task_type", "candidate"], as_index=False).agg(
        n_outer_units=("outer_utility", "size"),
        mean_outer_utility=("outer_utility", "mean"),
        sd_outer_utility=("outer_utility", "std"),
        mean_roc_auc=("roc_auc", "mean"),
        mean_pr_auc=("pr_auc", "mean"),
        mean_rmse=("rmse", "mean"),
        mean_fit_seconds=("fit_seconds", "mean"),
    )
    rdkit = endpoint_table[endpoint_table["candidate"].eq("rdkit_rf")][["task", "mean_outer_utility"]].rename(
        columns={"mean_outer_utility": "rdkit_mean_outer_utility"}
    )
    endpoint_table = endpoint_table.merge(rdkit, on="task", how="left")
    endpoint_table["delta_vs_rdkit_mean"] = endpoint_table["mean_outer_utility"] - endpoint_table["rdkit_mean_outer_utility"]
    endpoint_table.to_csv(OUT / "six_task_strong_endpoint_table.csv", index=False)

    return {
        "six_task_strong_tasks": sorted(outer["task"].unique().tolist()),
        "six_task_strong_candidates": sorted(outer["candidate"].unique().tolist()),
        "six_task_outer_rows": int(len(outer)),
        "six_task_inner_rows": int(len(inner)),
        "six_task_prediction_rows": int(len(preds)),
        "six_task_selection_units": int(len(selection)),
        "six_task_paired_rows": int(len(paired)),
        "six_task_top1_hit_rate": float(selection["outer_top1_hit"].mean()),
        "six_task_mean_range_normalized_selection_loss": float(selection["range_normalized_selection_loss"].mean()),
    }


def duplicate_sensitivity(tasks: list[str] = TASKS6, seeds: list[int] = SEEDS) -> dict[str, object]:
    detail_path = OUT / "six_task_duplicate_sensitivity_detail.csv"
    done: set[tuple[str, str, int, int]] = set()
    rows: list[dict[str, object]] = []
    if detail_path.exists():
        old = pd.read_csv(detail_path)
        rows.extend(old.to_dict("records"))
        done = {
            (str(r.task), str(r.policy), int(r.seed), int(r.outer_fold))
            for r in old.itertuples(index=False)
        }

    policies = ["global_dedup", "train_fold_only_aggregate", "keep_duplicates_grouped"]
    for task in tasks:
        for policy in policies:
            frame, task_type = strict.duplicate_policy_frame(task, policy)
            reps, groups, y, filtered = strict.featurize_frame(frame)
            for seed in seeds:
                outer_splits, split_type = strict.make_splits(y, groups, task_type, 3, seed)
                for outer_fold, (outer_train, outer_test) in enumerate(outer_splits, start=1):
                    key = (task, policy, seed, outer_fold)
                    if key in done:
                        continue
                    if policy == "train_fold_only_aggregate":
                        train_frame = strict.aggregate_train_fold(filtered, outer_train, task_type)
                        train_reps, _, train_y, _ = strict.featurize_frame(train_frame)
                        x_train = train_reps["morgan512"]
                        y_train = train_y
                        x_test = reps["morgan512"][outer_test]
                    else:
                        x_train = reps["morgan512"][outer_train]
                        y_train = y[outer_train]
                        x_test = reps["morgan512"][outer_test]
                    model = strict.make_tabular_model(task_type, "rf", seed)
                    pred = strict.predict_tabular(task_type, model, x_train, y_train, x_test)
                    util = strict.metric_utility(task_type, y[outer_test], pred)
                    row = {
                        "task": task,
                        "task_type": task_type,
                        "policy": policy,
                        "seed": seed,
                        "outer_fold": outer_fold,
                        "split_type": split_type,
                        "n_total_after_policy": len(filtered),
                        "n_train": len(y_train),
                        "n_test": len(outer_test),
                        "outer_utility": util,
                        **strict.compute_metric_columns(task_type, y[outer_test], pred),
                    }
                    rows.append(row)
                    pd.DataFrame(rows).to_csv(detail_path, index=False)
                    print(f"duplicate {task} {policy} seed={seed} outer={outer_fold}", flush=True)

    detail = pd.DataFrame(rows)
    summary = detail.groupby(["task", "task_type", "policy"], as_index=False).agg(
        n_outer_units=("outer_utility", "size"),
        n_total_after_policy=("n_total_after_policy", "median"),
        outer_utility_mean=("outer_utility", "mean"),
        outer_utility_sd=("outer_utility", "std"),
        roc_auc_mean=("roc_auc", "mean"),
        rmse_mean=("rmse", "mean"),
    )
    base = summary[summary["policy"].eq("global_dedup")][["task", "outer_utility_mean"]].rename(
        columns={"outer_utility_mean": "global_dedup_outer_utility_mean"}
    )
    summary = summary.merge(base, on="task", how="left")
    summary["delta_vs_global_dedup"] = summary["outer_utility_mean"] - summary["global_dedup_outer_utility_mean"]
    summary["abs_delta_vs_global_dedup"] = summary["delta_vs_global_dedup"].abs()
    summary.to_csv(OUT / "six_task_duplicate_sensitivity_summary.csv", index=False)
    return {
        "duplicate_detail_rows": int(len(detail)),
        "duplicate_summary_rows": int(len(summary)),
        "duplicate_tasks": sorted(detail["task"].unique().tolist()),
        "duplicate_max_abs_delta_vs_global": float(summary["abs_delta_vs_global_dedup"].max()),
    }


def validation_information_sensitivity(multiview_dir: Path) -> dict[str, object]:
    inner = pd.read_csv(multiview_dir / "inner_scores.csv")
    outer = pd.read_csv(multiview_dir / "outer_candidate_scores.csv")
    variants = {
        "morgan_only": ["morgan512"],
        "fingerprints_only": ["morgan512", "maccs"],
        "no_multiview_concat": ["morgan512", "maccs", "rdkit2d"],
        "full_multiview": ["morgan512", "maccs", "rdkit2d", "multiview"],
    }
    fractions = [0.25, 0.50, 0.75, 1.00]
    rng = np.random.default_rng(20260707)
    rows = []
    unit_cols = ["task", "task_type", "seed", "outer_fold"]
    for unit, out_group in outer.groupby(unit_cols, sort=True):
        task, task_type, seed, outer_fold = unit
        in_group = inner[
            inner["task"].eq(task)
            & inner["task_type"].eq(task_type)
            & inner["seed"].eq(seed)
            & inner["outer_fold"].eq(outer_fold)
        ]
        stats = in_group.groupby(["candidate", "representation", "family", "candidate_order"], as_index=False).agg(
            inner_mean=("inner_utility", "mean"),
            inner_sd=("inner_utility", "std"),
        )
        merged = stats.merge(out_group[["candidate", "outer_utility"]], on="candidate", how="inner")
        for variant, reps in variants.items():
            pool = merged[merged["representation"].isin(reps)].copy()
            if len(pool) < 2:
                continue
            oracle = pool.sort_values(["outer_utility", "candidate_order"], ascending=[False, True]).iloc[0]
            full_range = max(float(pool["outer_utility"].max() - pool["outer_utility"].min()), 1e-12)
            for frac in fractions:
                reps_n = 1 if frac == 1.0 else 300
                losses = []
                hits = []
                for _ in range(reps_n):
                    noise_scale = np.sqrt(max(0.0, 1.0 / frac - 1.0))
                    scores = pool["inner_mean"].to_numpy(float)
                    if frac < 1.0:
                        sd = pool["inner_sd"].fillna(0.0).to_numpy(float)
                        scores = scores + rng.normal(0.0, sd * noise_scale)
                    idx = int(np.argmax(scores))
                    selected = pool.iloc[idx]
                    losses.append(float((oracle["outer_utility"] - selected["outer_utility"]) / full_range))
                    hits.append(bool(selected["candidate"] == oracle["candidate"]))
                rows.append(
                    {
                        "task": task,
                        "task_type": task_type,
                        "seed": int(seed),
                        "outer_fold": int(outer_fold),
                        "variant": variant,
                        "candidate_count": int(len(pool)),
                        "validation_information_fraction": frac,
                        "simulation_replicates": reps_n,
                        "mean_range_normalized_selection_loss": float(np.mean(losses)),
                        "top1_hit_rate": float(np.mean(hits)),
                    }
                )
    detail = pd.DataFrame(rows)
    detail.to_csv(OUT / "validation_information_sensitivity_detail.csv", index=False)
    summary = detail.groupby(["variant", "candidate_count", "validation_information_fraction"], as_index=False).agg(
        n_units=("mean_range_normalized_selection_loss", "size"),
        mean_range_normalized_selection_loss=("mean_range_normalized_selection_loss", "mean"),
        top1_hit_rate=("top1_hit_rate", "mean"),
    )
    summary.to_csv(OUT / "validation_information_sensitivity_summary.csv", index=False)
    return {
        "validation_sensitivity_rows": int(len(detail)),
        "validation_sensitivity_variants": sorted(detail["variant"].unique().tolist()),
    }


def component_ablation_summary(multiview_dir: Path) -> dict[str, object]:
    policies = pd.read_csv(multiview_dir / "policy_detail.csv")
    ranking = pd.read_csv(multiview_dir / "ranking_metrics.csv")
    policy_summary = policies.groupby(["variant", "policy"], as_index=False).agg(
        n_outer_units=("normalized_regret", "size"),
        n_tasks=("task", "nunique"),
        mean_normalized_regret=("normalized_regret", "mean"),
        median_normalized_regret=("normalized_regret", "median"),
        mean_outer_utility=("outer_utility", "mean"),
    )
    full = policy_summary[policy_summary["variant"].eq("full_multiview") & policy_summary["policy"].eq("validation_best")]
    if not full.empty:
        full_regret = float(full["mean_normalized_regret"].iloc[0])
        full_utility = float(full["mean_outer_utility"].iloc[0])
        policy_summary["delta_regret_vs_full_validation_best"] = policy_summary["mean_normalized_regret"] - full_regret
        policy_summary["delta_utility_vs_full_validation_best"] = policy_summary["mean_outer_utility"] - full_utility
    policy_summary.to_csv(OUT / "component_policy_ablation_summary.csv", index=False)

    ranking_summary = ranking.groupby(["variant", "candidate_count"], as_index=False).agg(
        n_outer_units=("mrr", "size"),
        chance_adjusted_hit_mean=("chance_adjusted_hit", "mean"),
        mrr_mean=("mrr", "mean"),
        spearman_mean=("spearman", "mean"),
    )
    ranking_summary.to_csv(OUT / "component_ranking_ablation_summary.csv", index=False)
    return {
        "component_policy_rows": int(len(policy_summary)),
        "component_ranking_rows": int(len(ranking_summary)),
    }


def boundary_ood_scorecard() -> dict[str, object]:
    rows: list[dict[str, object]] = []
    tdc = ROOT / "results" / "source_data" / "tdc_gate_audit.csv"
    if tdc.exists():
        df = pd.read_csv(tdc)
        rows.append(
            {
                "experiment": "TDC gate audit",
                "scope": "22 public ADMET endpoints",
                "n_units": len(df),
                "primary_value": int(df["promoted"].sum()) if "promoted" in df.columns else np.nan,
                "interpretation": "External public-panel heterogeneity and gate-status audit.",
            }
        )
    bro5 = ROOT / "reports" / "full_missing_experiment_run_20260611" / "bro5_cycpept_pampa_compact_summary.csv"
    if bro5.exists():
        df = pd.read_csv(bro5)
        def first_float(value: object) -> float:
            match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", str(value))
            return float(match.group(0)) if match else np.nan

        rows.append(
            {
                "experiment": "bRo5 CycPept-PAMPA split contrast",
                "scope": "random/scaffold/perimeter/time splits",
                "n_units": len(df),
                "primary_value": first_float(df.loc[df["split"].eq("time"), "test_RMSE"].iloc[0]) if df["split"].eq("time").any() else np.nan,
                "interpretation": "Time and perimeter splits provide a chemical-boundary stress test.",
            }
        )
    molace = ROOT / "output" / "小论文-11_加厚实验" / "completion_moleculeace_gap_correlation_summary.csv"
    if molace.exists():
        df = pd.read_csv(molace)
        rows.append(
            {
                "experiment": "MoleculeACE activity-cliff gap audit",
                "scope": "completed MoleculeACE task-seed units",
                "n_units": len(df),
                "primary_value": float(df["gap_spearman"].mean()) if "gap_spearman" in df.columns else np.nan,
                "interpretation": "Activity-cliff evidence is retained as a boundary analysis.",
            }
        )
    scorecard = pd.DataFrame(rows)
    scorecard.to_csv(OUT / "ood_time_boundary_scorecard.csv", index=False)
    return {"ood_boundary_rows": int(len(scorecard))}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    strict_dir = locate_strict_dir()
    multiview_dir = locate_multiview_dir()
    audit = {
        "strict_source_dir": str(strict_dir),
        "multiview_source_dir": str(multiview_dir),
    }
    audit.update(strong_selection_and_pairing(strict_dir))
    audit.update(duplicate_sensitivity())
    audit.update(validation_information_sensitivity(multiview_dir))
    audit.update(component_ablation_summary(multiview_dir))
    audit.update(boundary_ood_scorecard())
    required = [
        "six_task_strong_endpoint_table.csv",
        "six_task_strong_selection_scorecard.csv",
        "six_task_strong_paired_vs_rdkit_summary.csv",
        "six_task_error_overlap_pairwise_detail.csv",
        "six_task_duplicate_sensitivity_summary.csv",
        "validation_information_sensitivity_summary.csv",
        "component_policy_ablation_summary.csv",
        "component_ranking_ablation_summary.csv",
        "ood_time_boundary_scorecard.csv",
    ]
    missing = [name for name in required if not (OUT / name).exists()]
    audit["missing_outputs"] = missing
    audit["passed"] = not missing and audit["six_task_outer_rows"] >= 360 and audit["duplicate_summary_rows"] == 18
    (OUT / "sci1_hardening_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
