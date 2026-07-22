from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
OUT = REPORTS / "supplement_experiment_revision_20260606"
OUT.mkdir(parents=True, exist_ok=True)


def fmt_num(x: float | int | str | None, digits: int = 3) -> str:
    if x is None:
        return ""
    try:
        if pd.isna(x):
            return ""
        return f"{float(x):.{digits}f}"
    except Exception:
        return str(x)


def metric_col(metric: str, prefix: str) -> str:
    return f"{prefix}_{str(metric).replace('-', '_')}"


def load_rank_source(source: str, path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    rows = []
    for _, r in df.iterrows():
        metric = r.get("selection_metric", r.get("primary_metric"))
        direction = r.get("selection_direction", r.get("primary_direction"))
        if pd.isna(metric) or pd.isna(direction):
            continue
        metric = str(metric).replace("-", "_")
        direction = str(direction)
        model = r.get("model", r.get("selected_candidate", r.get("model_name", "")))
        if pd.isna(model):
            model = ""
        if "selection_value" in df.columns:
            valid_value = r.get("selection_value")
            test_value = r.get(metric_col(metric, "test"))
        elif "validation_primary" in df.columns and "primary_value" in df.columns:
            valid_value = r.get("validation_primary")
            test_value = r.get("primary_value")
        else:
            continue
        if pd.isna(valid_value) or pd.isna(test_value):
            continue
        rows.append(
            {
                "source": source,
                "dataset": r.get("dataset"),
                "seed": r.get("seed"),
                "task_type": r.get("task_type"),
                "metric": metric,
                "direction": direction,
                "model": str(model),
                "valid_value": float(valid_value),
                "test_value": float(test_value),
            }
        )
    return pd.DataFrame(rows)


def build_validation_rank_audit() -> tuple[pd.DataFrame, pd.DataFrame]:
    sources = [
        ("validation_selector", REPORTS / "validation_selector" / "candidate_metrics_raw.csv"),
        ("validation_selector_expanded", REPORTS / "validation_selector_expanded" / "candidate_metrics_raw.csv"),
        ("moleculenet_targeted_rebuild", REPORTS / "moleculenet_targeted_rebuilds" / "candidate_metrics_raw.csv"),
        ("moleculenet_multimethod_fusion", REPORTS / "nature_multimethod_fusion_appendix" / "candidate_metrics_raw.csv"),
        ("tdc_multimethod_fusion", REPORTS / "tdc_nature_multimethod_fusion_appendix" / "candidate_metrics_raw.csv"),
        ("structure_full_selector", REPORTS / "structure_full_selector" / "candidate_metrics_raw.csv"),
        ("three_d_roughness", REPORTS / "three_d_roughness_regression_experts_20260603" / "candidate_metrics_raw.csv"),
        ("strong_tabpfn_pilot", REPORTS / "strong_tabpfn_moleculenet_pilot_20260603" / "candidate_metrics_raw.csv"),
    ]
    frames = [load_rank_source(src, path) for src, path in sources if path.exists()]
    all_df = pd.concat(frames, ignore_index=True)
    detail_rows = []
    keys = ["source", "dataset", "seed", "task_type", "metric", "direction"]
    for key, g in all_df.groupby(keys, dropna=False):
        if len(g) < 2:
            continue
        direction = key[-1]
        sign = 1.0 if direction == "higher" else -1.0
        tmp = g.copy()
        tmp["valid_utility"] = sign * tmp["valid_value"]
        tmp["test_utility"] = sign * tmp["test_value"]
        tmp["valid_rank"] = tmp["valid_utility"].rank(ascending=False, method="min")
        tmp["test_rank"] = tmp["test_utility"].rank(ascending=False, method="min")
        spearman = tmp["valid_rank"].corr(tmp["test_rank"], method="spearman")
        valid_top = tmp.sort_values(["valid_rank", "test_rank"]).iloc[0]
        test_top = tmp.sort_values(["test_rank", "valid_rank"]).iloc[0]
        valid_top3 = set(tmp.nsmallest(min(3, len(tmp)), "valid_rank")["model"])
        test_top3 = set(tmp.nsmallest(min(3, len(tmp)), "test_rank")["model"])
        if direction == "higher":
            optimism_gap = valid_top["valid_value"] - valid_top["test_value"]
            selected_test_regret = test_top["test_value"] - valid_top["test_value"]
        else:
            optimism_gap = valid_top["test_value"] - valid_top["valid_value"]
            selected_test_regret = valid_top["test_value"] - test_top["test_value"]
        detail_rows.append(
            {
                **dict(zip(keys, key)),
                "n_candidates": len(tmp),
                "spearman_valid_test_rank": spearman,
                "valid_top_equals_test_top": valid_top["model"] == test_top["model"],
                "test_top_in_valid_top3": test_top["model"] in valid_top3,
                "valid_top_in_test_top3": valid_top["model"] in test_top3,
                "top_valid_model": valid_top["model"],
                "top_test_model": test_top["model"],
                "top_valid_test_rank": float(valid_top["test_rank"]),
                "optimism_gap_native": float(optimism_gap),
                "selected_test_regret_native": float(max(0.0, selected_test_regret)),
            }
        )
    detail = pd.DataFrame(detail_rows)

    def summarize(g: pd.DataFrame) -> pd.Series:
        return pd.Series(
            {
                "n_dataset_seed_units": len(g),
                "median_spearman": g["spearman_valid_test_rank"].median(),
                "mean_spearman": g["spearman_valid_test_rank"].mean(),
                "q25_spearman": g["spearman_valid_test_rank"].quantile(0.25),
                "q75_spearman": g["spearman_valid_test_rank"].quantile(0.75),
                "median_candidates": g["n_candidates"].median(),
                "top1_match_rate": g["valid_top_equals_test_top"].mean(),
                "test_top_in_valid_top3_rate": g["test_top_in_valid_top3"].mean(),
                "valid_top_in_test_top3_rate": g["valid_top_in_test_top3"].mean(),
                "negative_rank_units": int((g["spearman_valid_test_rank"] < 0).sum()),
                "median_optimism_gap_native": g["optimism_gap_native"].median(),
                "median_selected_test_regret_native": g["selected_test_regret_native"].median(),
            }
        )

    summary = detail.groupby("source", dropna=False).apply(summarize).reset_index()
    overall = summarize(detail).to_frame().T
    overall.insert(0, "source", "overall")
    summary = pd.concat([summary, overall], ignore_index=True)
    detail.to_csv(OUT / "p0_validation_selection_bias_audit_detail.csv", index=False)
    summary.to_csv(OUT / "p0_validation_selection_bias_audit_summary.csv", index=False)
    return detail, summary


def build_compact_tables(rank_summary: pd.DataFrame) -> None:
    tracker = pd.DataFrame(
        [
            ["P0-1", "验证集选择偏差/嵌套验证诊断", "已补充", "新增 Top-3 命中率、验证-测试排名相关性、optimism gap 和 selected-test regret；低相关结果按治理风险解释。"],
            ["P0-2", "显著性与效应量", "已补充", "保留 seed-level paired bootstrap、Wilcoxon、95% CI；小幅收益按效应有限解释。"],
            ["P0-3", "系统消融", "已补充", "汇总 full selector 与单家族/去家族/强基线对比，强调 no_chemprop、no_pretrained 等负向或不稳定结果。"],
            ["P0-4", "低相似度与结构偏移", "已补充", "整合 random/scaffold/structure-separated 和 Tanimoto hard-subset 结果；分布外下降作为适用边界。"],
            ["P0-5", "MoleculeACE 活性悬崖", "已补充", "整合 MoleculeACE cliff objective selector 与 cliff subset 结果；数值悬崖预测仍作为限制。"],
            ["P1-1", "不平衡分类 PR-AUC/校准", "已补充", "ClinTox、DILI、hERG、CYP 等报告 PR-AUC、Brier、ECE 和富集指标。"],
            ["P1-2", "保形预测", "部分完成", "现有证据为 90% coverage；80%/95% coverage 不写成已完成，列为后续补跑。"],
            ["P1-3", "失败案例", "已补充", "保留 Lipophilicity、ClinTox 假阴性、高粗糙度 ADME 回归三类案例。"],
            ["P1-4", "负结果审计", "已补充", "3D-lite、粗糙度加权、固定策略和未接入候选统一进入负结果。"],
        ],
        columns=["priority", "requested_experiment", "status", "manuscript_action"],
    )
    tracker.to_csv(OUT / "supplement_experiment_coverage_tracker.csv", index=False)

    # Main-text compact rank table.
    rank_pick = rank_summary.copy()
    rank_pick = rank_pick[
        [
            "source",
            "n_dataset_seed_units",
            "median_spearman",
            "top1_match_rate",
            "test_top_in_valid_top3_rate",
            "negative_rank_units",
            "median_optimism_gap_native",
            "median_selected_test_regret_native",
        ]
    ]
    rank_pick.to_csv(OUT / "maintext_table_validation_bias_extended.csv", index=False)

    ablation = pd.read_csv(REPORTS / "manuscript_tables" / "table5_ablation_significance.csv")
    ablation_main = ablation[
        ablation["comparison"].isin(
            [
                "chemprop_only",
                "multifp_only",
                "pretrained_only",
                "core_only",
                "no_core",
                "no_multifp",
                "no_chemprop",
                "no_pretrained",
                "chemprop_baseline::chemprop_dmpnn_ens3",
                "strict_core_fast::dmpnn",
            ]
        )
    ].copy()
    ablation_main.to_csv(OUT / "maintext_table_systematic_ablation.csv", index=False)

    split = pd.read_csv(REPORTS / "manuscript_tables" / "table4_split_realism.csv")
    split["ood_penalty_text"] = np.where(
        split["task_type"].eq("classification"),
        "AUC scaffold->structure drop=" + split["scaffold_to_structure_drop"].map(lambda x: fmt_num(x, 3)),
        "RMSE scaffold->structure change=" + split["scaffold_to_structure_drop"].map(lambda x: fmt_num(x, 3)),
    )
    split_compact = split.sort_values("scaffold_to_structure_drop", ascending=False).head(10)
    split_compact.to_csv(OUT / "maintext_table_structure_shift_compact.csv", index=False)

    hard = pd.read_csv(REPORTS / "conformal_activity" / "hard_scaffold_metrics.csv")
    hard_rows = []
    for (task_type, threshold), g in hard.groupby(["task_type", "threshold"]):
        if task_type == "classification":
            hard_rows.append(
                {
                    "task_type": task_type,
                    "tanimoto_threshold": threshold,
                    "n_rows": len(g),
                    "mean_n": g["n"].mean(),
                    "mean_similarity": g["mean_similarity"].mean(),
                    "roc_auc_mean": g["roc_auc"].mean(),
                    "pr_auc_mean": g["pr_auc"].mean(),
                    "brier_mean": g["brier"].mean(),
                    "ece_mean": g["ece"].mean(),
                    "rmse_mean": np.nan,
                    "mae_mean": np.nan,
                }
            )
        else:
            hard_rows.append(
                {
                    "task_type": task_type,
                    "tanimoto_threshold": threshold,
                    "n_rows": len(g),
                    "mean_n": g["n"].mean(),
                    "mean_similarity": g["mean_similarity"].mean(),
                    "roc_auc_mean": np.nan,
                    "pr_auc_mean": np.nan,
                    "brier_mean": np.nan,
                    "ece_mean": np.nan,
                    "rmse_mean": g["rmse"].mean(),
                    "mae_mean": g["mae"].mean(),
                }
            )
    pd.DataFrame(hard_rows).to_csv(OUT / "maintext_table_low_similarity_bins.csv", index=False)

    ace = pd.read_csv(REPORTS / "manuscript_tables" / "table10_moleculeace_cliff_objective_selector.csv")
    ace.to_csv(OUT / "maintext_table_moleculeace_cliff_selector.csv", index=False)
    ace_pairs = pd.read_csv(REPORTS / "manuscript_tables" / "table10_moleculeace_cliff_objective_selector_pairs.csv")
    ace_examples = (
        ace_pairs.groupby("task", dropna=False)
        .agg(
            n_seed=("seed", "count"),
            baseline_rmse_mean=("baseline_rmse", "mean"),
            cliff_rmse_mean=("cliff_rmse", "mean"),
            delta_rmse_positive_mean=("delta_rmse_positive", "mean"),
            baseline_cliff_rmse_mean=("baseline_cliff_rmse", "mean"),
            cliff_cliff_rmse_mean=("cliff_cliff_rmse", "mean"),
            delta_cliff_rmse_positive_mean=("delta_cliff_rmse_positive", "mean"),
        )
        .reset_index()
    )
    ace_examples = ace_examples.sort_values("delta_cliff_rmse_positive_mean", ascending=False).head(8)
    ace_examples.to_csv(OUT / "maintext_table_moleculeace_cliff_examples.csv", index=False)
    ace_weighted = pd.read_csv(REPORTS / "manuscript_tables" / "table10_moleculeace_cliff_objective_selector.csv")
    ace_summary = pd.read_csv(REPORTS / "moleculeace_cliff_weighted" / "metrics_summary.csv", header=[0, 1])
    ace_summary.to_csv(OUT / "maintext_table_moleculeace_cliff_weighted_summary.csv", index=False)

    conf = pd.read_csv(REPORTS / "conformal_activity" / "conformal_summary.csv")
    conf_compact = (
        conf.groupby(["task_type", "alpha"], dropna=False)
        .agg(
            n=("dataset", "count"),
            coverage_mean=("coverage", "mean"),
            coverage_median=("coverage", "median"),
            avg_set_size_mean=("avg_set_size", "mean"),
            singleton_rate_mean=("singleton_rate", "mean"),
            empty_rate_mean=("empty_rate", "mean"),
            mean_width_mean=("mean_width", "mean"),
            median_abs_error_mean=("median_abs_error", "mean"),
        )
        .reset_index()
    )
    conf_compact.to_csv(OUT / "maintext_table_conformal_coverage_compact.csv", index=False)

    imb = pd.read_csv(REPORTS / "manuscript_tables" / "table22_imbalanced_classification_metrics.csv")
    imb[["dataset", "source", "positive_rate_or_query_positive_rate", "roc_auc_mean", "pr_auc_mean", "brier_mean", "ece_mean", "ef1_mean", "ef5_mean", "note"]].to_csv(
        OUT / "maintext_table_imbalanced_metrics_compact.csv", index=False
    )

    cases = pd.read_csv(REPORTS / "manuscript_tables" / "table24_targeted_improvement_case_studies.csv")
    cases[["case_id", "case_name", "dataset", "case_type", "primary_metric", "before", "after", "delta_positive", "interpretation"]].to_csv(
        OUT / "maintext_table_failure_cases_compact.csv", index=False
    )

    neg_rows = []
    policy = pd.read_csv(REPORTS / "manuscript_tables" / "table40_selector_strategy_policy_summary.csv")
    fixed = pd.read_csv(REPORTS / "manuscript_tables" / "table43_formal_fixed_selector_policy_summary.csv")
    rough = pd.read_csv(REPORTS / "manuscript_tables" / "table37_3d_roughness_oracle_audit.csv")
    for _, r in policy.iterrows():
        neg_rows.append(
            {
                "module": r["strategy"],
                "scope": f"{int(r['n_endpoint_pools'])} endpoint pools",
                "positive_rate": r["positive_rate"],
                "mean_delta_vs_current": r["mean_delta_vs_current"],
                "decision": "not promoted to final policy",
            }
        )
    for _, r in fixed.iterrows():
        neg_rows.append(
            {
                "module": r["fixed_policy"],
                "scope": f"{int(r['n_endpoint_metrics'])} endpoint metrics",
                "positive_rate": r["positive_rate"],
                "mean_delta_vs_current": r["mean_delta_vs_current"],
                "decision": "boundary evidence",
            }
        )
    for _, r in rough.iterrows():
        neg_rows.append(
            {
                "module": r["oracle_candidate_family"],
                "scope": f"{r['source']}::{r['dataset']}",
                "positive_rate": np.nan,
                "mean_delta_vs_current": r["validation_selected_delta_vs_previous"],
                "decision": r["manuscript_use"],
            }
        )
    pd.DataFrame(neg_rows).to_csv(OUT / "maintext_table_negative_result_audit.csv", index=False)


def build_markdown_summary() -> None:
    rank = pd.read_csv(OUT / "maintext_table_validation_bias_extended.csv")
    ablation = pd.read_csv(OUT / "maintext_table_systematic_ablation.csv")
    conformal = pd.read_csv(OUT / "maintext_table_conformal_coverage_compact.csv")
    lines = [
        "# Supplement Experiment Revision Summary",
        "",
        "## Validation selection bias",
        rank.to_markdown(index=False),
        "",
        "## Systematic ablation",
        ablation.to_markdown(index=False),
        "",
        "## Conformal coverage",
        conformal.to_markdown(index=False),
        "",
    ]
    (OUT / "supplement_revision_summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    _, rank_summary = build_validation_rank_audit()
    build_compact_tables(rank_summary)
    build_markdown_summary()
    print(f"Wrote supplement revision tables to {OUT}")


if __name__ == "__main__":
    main()
