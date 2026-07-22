from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "小论文-11_加厚实验"
AUDIT = ROOT / "results" / "audits" / "small_paper_11_thickened_experiments.json"

MULTIVIEW = ROOT / "results" / "reviewer_core_20260624" / "multiview_nested"
SOURCE = ROOT / "results" / "source_data"
MISSING = ROOT / "reports" / "remaining_missing_experiments_20260606"
TABLES = ROOT / "reports" / "manuscript_tables"


POOL_STAGES = OrderedDict(
    [
        ("morgan_only", ("Morgan-only", ["morgan512"])),
        ("plus_maccs", ("Morgan + MACCS", ["morgan512", "maccs"])),
        ("plus_rdkit2d", ("Morgan + MACCS + RDKit2D", ["morgan512", "maccs", "rdkit2d"])),
        (
            "plus_multiview",
            ("Morgan + MACCS + RDKit2D + multiview", ["morgan512", "maccs", "rdkit2d", "multiview"]),
        ),
    ]
)


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def finite_float(x) -> float | None:
    if x is None or pd.isna(x):
        return None
    return float(x)


def effective_k(df: pd.DataFrame, index_cols: list[str], candidate_orders: list[int], value_col: str) -> dict[str, float]:
    sub = df[df["candidate_order"].isin(candidate_orders)].copy()
    piv = sub.pivot_table(index=index_cols, columns="candidate_order", values=value_col, aggfunc="mean")
    piv = piv.dropna(axis=1, how="all")
    if piv.shape[1] < 2:
        return {"nominal_K": float(piv.shape[1]), "K_eff": float(piv.shape[1]), "median_corr": np.nan, "n_units": float(piv.shape[0])}
    corr = piv.corr(min_periods=5).fillna(0)
    np.fill_diagonal(corr.values, 1.0)
    vals = np.clip(np.linalg.eigvalsh(corr.values), 1e-12, None)
    off_diag = corr.values[np.triu_indices_from(corr.values, k=1)]
    return {
        "nominal_K": float(piv.shape[1]),
        "K_eff": float((vals.sum() ** 2) / (vals @ vals)),
        "median_corr": float(np.median(off_diag)),
        "n_units": float(piv.shape[0]),
    }


def make_candidate_stage_tables(registry: pd.DataFrame) -> dict[str, int]:
    stage_rows = []
    for stage_id, (stage_label, reps) in POOL_STAGES.items():
        sub = registry[registry["representation"].isin(reps)].copy()
        per_seed_k = sub.groupby(["task", "seed"])["candidate_order"].nunique()
        for _, row in (
            sub.drop_duplicates(["task", "seed", "candidate_order"])
            .groupby(["representation", "family", "model_class"], dropna=False)
            .agg(
                registered_rows=("candidate_order", "size"),
                unique_tasks=("task", "nunique"),
                unique_seeds=("seed", "nunique"),
                min_feature_count=("feature_count", "min"),
                max_feature_count=("feature_count", "max"),
            )
            .reset_index()
        ).iterrows():
            stage_rows.append(
                {
                    "stage_id": stage_id,
                    "stage_label": stage_label,
                    "stage_K_per_task_seed_median": float(per_seed_k.median()),
                    **row.to_dict(),
                }
            )
    pd.DataFrame(stage_rows).to_csv(OUT / "candidate_registry_stage_summary.csv", index=False)
    registry.to_csv(OUT / "candidate_registry_full_multiview.csv", index=False)
    return {
        "registry_rows": int(len(registry)),
        "unique_tasks": int(registry["task"].nunique()),
        "unique_candidates_per_task_seed": int(registry.groupby(["task", "seed"])["candidate_order"].nunique().max()),
    }


def compute_staged_multiview(inner: pd.DataFrame, outer: pd.DataFrame, registry: pd.DataFrame) -> dict[str, float]:
    stage_orders = {}
    stage_labels = {}
    reg_unique = registry.drop_duplicates(["task", "seed", "candidate_order", "representation"])
    for stage_id, (stage_label, reps) in POOL_STAGES.items():
        stage_labels[stage_id] = stage_label
        stage_orders[stage_id] = {
            key: sorted(group["candidate_order"].unique().tolist())
            for key, group in reg_unique[reg_unique["representation"].isin(reps)].groupby(["task", "seed"])
        }

    rows = []
    unit_cols = ["task", "task_type", "seed", "outer_fold"]
    for unit, outer_unit in outer.groupby(unit_cols, dropna=False):
        task, task_type, seed, outer_fold = unit
        inner_unit = inner[
            (inner["task"].eq(task))
            & (inner["seed"].eq(seed))
            & (inner["outer_fold"].eq(outer_fold))
        ]
        if inner_unit.empty:
            continue
        full_range = float(outer_unit["outer_utility"].max() - outer_unit["outer_utility"].min())
        stage_cache = {}
        for stage_id, orders_by_key in stage_orders.items():
            orders = orders_by_key.get((task, seed), [])
            if not orders:
                continue
            inner_stage = inner_unit[inner_unit["candidate_order"].isin(orders)]
            outer_stage = outer_unit[outer_unit["candidate_order"].isin(orders)]
            if inner_stage.empty or outer_stage.empty:
                continue
            validation_means = inner_stage.groupby("candidate_order")["inner_utility"].mean()
            selected_order = int(validation_means.idxmax())
            selected_outer = float(outer_stage.loc[outer_stage["candidate_order"].eq(selected_order), "outer_utility"].mean())
            oracle_idx = int(outer_stage.groupby("candidate_order")["outer_utility"].mean().idxmax())
            oracle_outer = float(outer_stage.loc[outer_stage["candidate_order"].eq(oracle_idx), "outer_utility"].mean())
            stage_cache[stage_id] = {
                "selected_order": selected_order,
                "selected_outer": selected_outer,
                "oracle_order": oracle_idx,
                "oracle_outer": oracle_outer,
                "stage_K": int(len(orders)),
                "full_range": full_range,
            }
        if "morgan_only" not in stage_cache:
            continue
        base_selected = stage_cache["morgan_only"]["selected_outer"]
        base_oracle = stage_cache["morgan_only"]["oracle_outer"]
        for stage_id, values in stage_cache.items():
            g_attain = values["oracle_outer"] - base_oracle
            l_select = values["oracle_outer"] - values["selected_outer"]
            g_realized = values["selected_outer"] - base_selected
            rows.append(
                {
                    "task": task,
                    "task_type": task_type,
                    "seed": seed,
                    "outer_fold": outer_fold,
                    "stage_id": stage_id,
                    "stage_label": stage_labels[stage_id],
                    "stage_K": values["stage_K"],
                    "selected_order": values["selected_order"],
                    "oracle_order": values["oracle_order"],
                    "selected_outer_utility": values["selected_outer"],
                    "oracle_outer_utility": values["oracle_outer"],
                    "morgan_selected_outer_utility": base_selected,
                    "morgan_oracle_outer_utility": base_oracle,
                    "G_attain_vs_morgan_oracle": g_attain,
                    "L_select_within_stage": l_select,
                    "G_realized_vs_morgan_selected": g_realized,
                    "eta_vs_morgan": g_realized / g_attain if abs(g_attain) > 1e-12 else np.nan,
                    "full_12_pool_range": full_range,
                    "full_range_normalized_selection_loss": l_select / full_range if full_range > 1e-12 else np.nan,
                }
            )

    detail = pd.DataFrame(rows)
    detail.to_csv(OUT / "heterogeneous_staged_pool_detail.csv", index=False)

    summary = (
        detail.groupby(["stage_id", "stage_label", "stage_K"], sort=False)
        .agg(
            n_units=("selected_outer_utility", "size"),
            selected_outer_mean=("selected_outer_utility", "mean"),
            oracle_outer_mean=("oracle_outer_utility", "mean"),
            G_attain_mean=("G_attain_vs_morgan_oracle", "mean"),
            L_select_mean=("L_select_within_stage", "mean"),
            G_realized_mean=("G_realized_vs_morgan_selected", "mean"),
            eta_median=("eta_vs_morgan", "median"),
            full_range_normalized_selection_loss_mean=("full_range_normalized_selection_loss", "mean"),
        )
        .reset_index()
    )
    summary.to_csv(OUT / "heterogeneous_staged_pool_summary.csv", index=False)

    endpoint = (
        detail.groupby(["task", "task_type", "stage_id", "stage_label", "stage_K"], sort=False)
        .agg(
            n_units=("selected_outer_utility", "size"),
            selected_outer_mean=("selected_outer_utility", "mean"),
            oracle_outer_mean=("oracle_outer_utility", "mean"),
            G_realized_mean=("G_realized_vs_morgan_selected", "mean"),
            L_select_mean=("L_select_within_stage", "mean"),
            eta_median=("eta_vs_morgan", "median"),
        )
        .reset_index()
    )
    endpoint.to_csv(OUT / "heterogeneous_staged_pool_endpoint_effects.csv", index=False)

    k_rows = []
    for stage_id, (stage_label, _) in POOL_STAGES.items():
        all_orders = sorted({order for orders in stage_orders[stage_id].values() for order in orders})
        k_rows.append(
            {
                "stage_id": stage_id,
                "stage_label": stage_label,
                "source": "inner_validation",
                **effective_k(inner, ["task", "seed", "outer_fold", "inner_fold"], all_orders, "inner_utility"),
            }
        )
        k_rows.append(
            {
                "stage_id": stage_id,
                "stage_label": stage_label,
                "source": "outer_test",
                **effective_k(outer, ["task", "seed", "outer_fold"], all_orders, "outer_utility"),
            }
        )
    pd.DataFrame(k_rows).to_csv(OUT / "heterogeneous_pool_effective_diversity.csv", index=False)

    mv = summary[summary["stage_id"].eq("plus_multiview")].iloc[0]
    return {
        "multiview_stage_K": int(mv["stage_K"]),
        "multiview_n_units": int(mv["n_units"]),
        "multiview_G_realized": float(mv["G_realized_mean"]),
        "multiview_G_attain": float(mv["G_attain_mean"]),
        "multiview_L_select": float(mv["L_select_mean"]),
        "multiview_eta": finite_float(mv["eta_median"]),
    }


def make_reliability_tables() -> dict[str, float]:
    tdc = read_csv(SOURCE / "tdc_gate_audit.csv")
    tdc["interval_crosses_zero"] = tdc["ci_low"] * tdc["ci_high"] <= 0
    tdc_summary = (
        tdc.groupby(["promoted", "gate_category"], dropna=False)
        .agg(
            n_endpoints=("endpoint", "size"),
            mean_delta=("test_delta", "mean"),
            median_delta=("test_delta", "median"),
            cross_zero_count=("interval_crosses_zero", "sum"),
            seed_wins=("seed_win_count", "sum"),
            seed_ties=("seed_tie_count", "sum"),
            seed_losses=("seed_loss_count", "sum"),
        )
        .reset_index()
    )
    tdc.to_csv(OUT / "tdc_gate_endpoint_detail.csv", index=False)
    tdc_summary.to_csv(OUT / "tdc_gate_evidence_stratification.csv", index=False)

    conformal = read_csv(SOURCE / "conformal_long.csv")
    conformal_summary = (
        conformal.groupby(["dataset", "task_type", "target_coverage"])
        .agg(
            n_seed_candidates=("coverage", "size"),
            coverage_mean=("coverage", "mean"),
            coverage_min=("coverage", "min"),
            class0_coverage_mean=("class_0_coverage", "mean"),
            class1_coverage_mean=("class_1_coverage", "mean"),
            avg_set_size_mean=("avg_set_size", "mean"),
            empty_rate_max=("empty_rate", "max"),
            mean_width_mean=("mean_width", "mean"),
            normalized_width_sd_mean=("normalized_width_sd", "mean"),
            fallback_count=("fallback_reason", lambda s: int(s.notna().sum())),
        )
        .reset_index()
    )
    conformal_summary.to_csv(OUT / "conformal_endpoint_detail.csv", index=False)

    cleaning = read_csv(ROOT / "results" / "audits" / "data_cleaning_events.csv")
    cleaning_summary = (
        cleaning.groupby(["endpoint", "action", "reason"], dropna=False)
        .agg(n_rows=("source_row", "size"), n_unique_standardized_smiles=("standardized_smiles", "nunique"))
        .reset_index()
    )
    cleaning_summary.to_csv(OUT / "duplicate_and_cleaning_audit_summary.csv", index=False)

    return {
        "tdc_promoted": int(tdc["promoted"].sum()),
        "tdc_promoted_cross_zero": int(((tdc["promoted"]) & (tdc["interval_crosses_zero"])).sum()),
        "tdc_endpoint_count": int(len(tdc)),
        "conformal_rows": int(len(conformal)),
        "conformal_min_coverage": float(conformal["coverage"].min()),
        "cleaning_events": int(len(cleaning)),
    }


def copy_existing_completion_experiments() -> dict[str, float]:
    copied = {}
    for name in [
        "true_nested_validation/true_nested_validation_summary.csv",
        "true_nested_validation/true_nested_validation_detail.csv",
        "nested_seed_validation_summary.csv",
        "unified_ablation_matrix_summary.csv",
        "conformal_80_90_95_summary.csv",
        "exact_tanimoto_bins_summary.csv",
        "moleculeace_cliff_pair_cases.csv",
        "moleculeace_gap_correlation_summary.csv",
        "extended_failure_cases.csv",
        "low_similarity_failure_cases.csv",
    ]:
        src = MISSING / name
        if src.exists():
            dst = OUT / ("completion_" + name.replace("/", "_"))
            dst.write_bytes(src.read_bytes())
            copied[name] = str(dst)
    manifest = pd.DataFrame([{"source": k, "copied_to": v} for k, v in copied.items()])
    manifest.to_csv(OUT / "existing_completion_experiment_manifest.csv", index=False)
    return {"copied_completion_tables": int(len(copied))}


def make_strong_baseline_matrix() -> dict[str, float]:
    coverage = read_csv(TABLES / "table47_strong_baseline_model_coverage.csv")
    rows = []
    for _, row in coverage.iterrows():
        status = str(row["current_status"])
        rows.append(
            {
                "model_or_direction": row["model_or_direction"],
                "evidence_file": row["evidence_file"],
                "current_status": row["current_status"],
                "paper_use": row["paper_location"],
                "confirmatory_same_outer_split": "yes" if "implemented and runnable" in status and "selector pool" in str(row["result_or_decision"]) else "no",
                "boundary_note": row["next_action"],
            }
        )

    chemprop_path = ROOT / "reports" / "chemprop_baseline" / "metrics_summary.csv"
    if chemprop_path.exists():
        chem = read_csv(chemprop_path)
        chem = chem[chem["dataset"].notna()].copy()
        rows.append(
            {
                "model_or_direction": "Chemprop / D-MPNN historical same-split baseline",
                "evidence_file": str(chemprop_path),
                "current_status": f"{chem['dataset'].nunique()} datasets, {chem['model'].nunique()} model rows",
                "paper_use": "supplementary boundary evidence only",
                "confirmatory_same_outer_split": "no",
                "boundary_note": "Existing outputs are not the 3x3x5 confirmatory nested multiview rerun for 小论文-11.",
            }
        )

    adapter_path = ROOT / "reports" / "pretrained_lightweight_adapter_20260611" / "adapter_selected_summary.csv"
    if adapter_path.exists():
        adapters = read_csv(adapter_path)
        adapters = adapters[adapters["dataset"].notna()].copy()
        rows.append(
            {
                "model_or_direction": "ChemBERTa / MoLFormer frozen embedding adapters",
                "evidence_file": str(adapter_path),
                "current_status": f"{adapters['dataset'].nunique()} datasets, {adapters['encoder'].nunique()} encoders",
                "paper_use": "supplementary boundary evidence only",
                "confirmatory_same_outer_split": "no",
                "boundary_note": "Useful pretrained evidence, but not unified with the confirmatory outer splits.",
            }
        )

    matrix = pd.DataFrame(rows)
    matrix.to_csv(OUT / "strong_baseline_evidence_matrix.csv", index=False)
    return {"strong_baseline_rows": int(len(matrix))}


def _seed_from_path(path: Path) -> int:
    for part in path.parts:
        if part.startswith("seed_"):
            return int(part.split("_", 1)[1])
    return -1


def _compact_complexity(params_text: str) -> str:
    try:
        params = json.loads(params_text)
    except Exception:
        return ""
    keep = [
        "C",
        "penalty",
        "solver",
        "n_estimators",
        "max_depth",
        "max_features",
        "min_samples_leaf",
        "learning_rate",
        "num_leaves",
        "subsample",
        "colsample_bytree",
        "max_iter",
    ]
    return "; ".join(f"{k}={params[k]}" for k in keep if k in params and params[k] is not None)


def _randomness_source(params_text: str, family: str) -> str:
    try:
        params = json.loads(params_text)
    except Exception:
        return "unknown"
    random_state = params.get("random_state")
    if random_state is not None:
        return f"estimator_random_state={random_state}"
    if family in {"linear"}:
        return "deterministic solver; split seed controls data partition"
    return "split seed plus estimator defaults"


def make_lightweight32_candidate_audits() -> dict[str, float]:
    registries, outers, inners = [], [], []
    for path in sorted((ROOT / "results" / "nested_selection" / "repeated_nested").glob("seed_*/candidate_registry.csv")):
        df = pd.read_csv(path)
        df["repeat_seed"] = _seed_from_path(path)
        registries.append(df)
    for path in sorted((ROOT / "results" / "nested_selection" / "repeated_nested").glob("seed_*/outer_candidate_scores.csv")):
        df = pd.read_csv(path)
        df["repeat_seed"] = _seed_from_path(path)
        outers.append(df)
    for path in sorted((ROOT / "results" / "nested_selection" / "repeated_nested").glob("seed_*/inner_scores.csv")):
        df = pd.read_csv(path)
        df["repeat_seed"] = _seed_from_path(path)
        inners.append(df)

    registry = pd.concat(registries, ignore_index=True)
    outer = pd.concat(outers, ignore_index=True)
    inner = pd.concat(inners, ignore_index=True)

    fit = (
        outer.groupby(["dataset", "repeat_seed", "candidate_order", "candidate"])
        .agg(
            outer_fit_seconds_mean=("fit_seconds", "mean"),
            outer_fit_seconds_median=("fit_seconds", "median"),
            outer_units=("outer_utility", "size"),
        )
        .reset_index()
    )
    merged = registry.merge(fit, on=["dataset", "repeat_seed", "candidate_order", "candidate"], how="left")
    merged["candidate_id"] = merged["candidate"]
    merged["representation"] = "morgan512"
    merged["learner"] = merged["model_class"]
    merged["model_complexity"] = merged["params"].map(_compact_complexity)
    merged["randomness_source"] = [
        _randomness_source(params, family) for params, family in zip(merged["params"], merged["family"])
    ]
    merged["training_time"] = merged["outer_fit_seconds_mean"]
    merged["candidate_eligibility"] = "registered before inner selection in fixed-prefix lightweight pool"
    merged["candidate_status"] = np.where(merged["outer_units"].fillna(0).gt(0), "completed", "registered_no_outer_score")
    cols = [
        "dataset",
        "task_type",
        "repeat_seed",
        "candidate_order",
        "candidate_id",
        "representation",
        "learner",
        "params",
        "model_complexity",
        "randomness_source",
        "training_time",
        "candidate_eligibility",
        "candidate_status",
        "family",
        "outer_fit_seconds_mean",
        "outer_fit_seconds_median",
        "outer_units",
    ]
    merged[cols].to_csv(OUT / "lightweight32_candidate_registry_enriched.csv", index=False)

    outer_piv = outer.pivot_table(
        index=["dataset", "repeat_seed", "outer_fold"], columns="candidate_order", values="outer_utility", aggfunc="mean"
    )
    outer_piv.corr(min_periods=10).to_csv(OUT / "lightweight32_outer_utility_correlation_matrix.csv")

    inner_rank = inner.copy()
    inner_rank["validation_rank"] = inner_rank.groupby(["dataset", "repeat_seed", "outer_fold", "inner_fold"])[
        "inner_utility"
    ].rank(method="average", ascending=False)
    rank_piv = inner_rank.pivot_table(
        index=["dataset", "repeat_seed", "outer_fold", "inner_fold"],
        columns="candidate_order",
        values="validation_rank",
        aggfunc="mean",
    )
    rank_piv.corr(min_periods=10).to_csv(OUT / "lightweight32_validation_rank_correlation_matrix.csv")

    pd.DataFrame(
        [
            {
                "requested_measure": "candidate error overlap rate",
                "status": "not_computed",
                "reason": "The repeated-nested lightweight32 output contains per-candidate aggregate scores but no per-sample predictions for every candidate/fold, so error-overlap cannot be recomputed without rerunning prediction export.",
                "next_action": "Rerun repeated nested selection with per-sample candidate predictions retained, then compute pairwise overlap of incorrect classification calls or large-error regression cases.",
            }
        ]
    ).to_csv(OUT / "lightweight32_error_overlap_status.csv", index=False)

    return {
        "lightweight32_registry_rows": int(len(merged)),
        "lightweight32_completed_rows": int(merged["candidate_status"].eq("completed").sum()),
        "lightweight32_outer_corr_shape": int(outer_piv.shape[1]),
        "lightweight32_rank_corr_shape": int(rank_piv.shape[1]),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    inner = read_csv(MULTIVIEW / "inner_scores.csv")
    outer = read_csv(MULTIVIEW / "outer_candidate_scores.csv")
    registry = read_csv(MULTIVIEW / "candidate_registry.csv")

    audit: dict[str, float | int | str | None] = {
        "output_dir": str(OUT),
        "inner_rows": int(len(inner)),
        "outer_rows": int(len(outer)),
    }
    audit.update(make_candidate_stage_tables(registry))
    audit.update(compute_staged_multiview(inner, outer, registry))
    audit.update(make_reliability_tables())
    audit.update(copy_existing_completion_experiments())
    audit.update(make_strong_baseline_matrix())
    audit.update(make_lightweight32_candidate_audits())

    required = [
        "candidate_registry_stage_summary.csv",
        "heterogeneous_staged_pool_summary.csv",
        "heterogeneous_staged_pool_endpoint_effects.csv",
        "heterogeneous_pool_effective_diversity.csv",
        "tdc_gate_evidence_stratification.csv",
        "conformal_endpoint_detail.csv",
        "duplicate_and_cleaning_audit_summary.csv",
        "strong_baseline_evidence_matrix.csv",
        "existing_completion_experiment_manifest.csv",
        "lightweight32_candidate_registry_enriched.csv",
        "lightweight32_outer_utility_correlation_matrix.csv",
        "lightweight32_validation_rank_correlation_matrix.csv",
        "lightweight32_error_overlap_status.csv",
    ]
    missing = [name for name in required if not (OUT / name).exists()]
    audit["required_outputs_missing"] = missing
    audit["passed"] = not missing and audit["outer_rows"] > 0 and audit["copied_completion_tables"] >= 5

    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    if not audit["passed"]:
        raise SystemExit(json.dumps(audit, ensure_ascii=False, indent=2))
    print(OUT)
    print(AUDIT)


if __name__ == "__main__":
    main()
