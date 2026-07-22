from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
OUT = REPORTS / "supplement_experiment_revision_20260606"
OUT.mkdir(parents=True, exist_ok=True)


def shape(path: Path) -> str:
    if not path.exists():
        return "missing"
    try:
        df = pd.read_csv(path)
        return f"{len(df)} rows, {len(df.columns)} cols"
    except Exception:
        return "exists"


def exists(paths: list[Path]) -> bool:
    return all(p.exists() for p in paths)


items = [
    {
        "priority": "P0-1",
        "item": "验证集选择偏差审计 / nested validation 诊断",
        "status": "核心已跑；nested 未跑",
        "evidence": [
            REPORTS / "supplement_experiment_revision_20260606" / "p0_validation_selection_bias_audit_detail.csv",
            REPORTS / "supplement_experiment_revision_20260606" / "p0_validation_selection_bias_audit_summary.csv",
        ],
        "gap": "已完成 validation-test rank audit、Top-1、Top-3、optimism gap；没有真正跑内外层 nested validation。清单里 nested 是资源允许时的可选增强。",
        "action": "可投稿最低版可接受；若冲一区/高影响，建议补 2-3 个代表终点的 nested validation。",
    },
    {
        "priority": "P0-2",
        "item": "统计显著性、置信区间与效应量",
        "status": "已跑",
        "evidence": [
            REPORTS / "significance_selector" / "significance_tests.csv",
            REPORTS / "formal_external_appendix" / "table23_external_seed_stability_significance.csv",
            REPORTS / "manuscript_tables" / "table23_external_seed_stability_significance.csv",
        ],
        "gap": "已有 paired bootstrap、Wilcoxon、CI；仍需在正文所有微小提升处保持谨慎语气，不能把 ClinTox 这类极小差值写成强改善。",
        "action": "保留当前写法；必要时把 significance_tests.csv 的代表行补入附录。",
    },
    {
        "priority": "P0-3",
        "item": "系统消融实验",
        "status": "部分已跑",
        "evidence": [
            REPORTS / "manuscript_tables" / "table5_ablation_significance.csv",
            REPORTS / "selector_ablation" / "family_ablation_aggregate.csv",
            REPORTS / "validation_selector_ablation" / "candidate_metrics_raw.csv",
            REPORTS / "manuscript_figures_hires" / "fig9_ablation_significance.png",
        ],
        "gap": "已有家族级消融、强基线对照和部分 selector ablation；没有形成清单要求的统一矩阵：Full、best single、simple mean、w/o selector、w/o fusion、w/o AD gate、w/o uncertainty weighting、w/o motif/fingerprint、w/o rescue head 在 MoleculeNet 6 + Caco2/HIA/Pgp 上逐项齐全。",
        "action": "这是最重要的未完整项之一。建议补成一张统一 ablation matrix，再更新主文 S3。",
    },
    {
        "priority": "P0-4",
        "item": "低相似度子集与结构分布偏移",
        "status": "部分已跑",
        "evidence": [
            REPORTS / "conformal_activity" / "hard_scaffold_metrics.csv",
            REPORTS / "manuscript_tables" / "table4_split_realism.csv",
            REPORTS / "supplement_experiment_revision_20260606" / "maintext_table_low_similarity_bins.csv",
            REPORTS / "supplement_experiment_revision_20260606" / "maintext_table_structure_shift_compact.csv",
        ],
        "gap": "已有 hard-scaffold/threshold 分析和 random/scaffold/structure-separated 对照；但没有严格按 >0.7、0.5-0.7、<0.5 三个互斥 Tanimoto bin 输出性能、校准、不确定性和风险富集，也没有完整 OOD degradation heatmap。",
        "action": "建议补 exact Tanimoto bins；这是标题“结构分布偏移”的关键证据口径。",
    },
    {
        "priority": "P0-5",
        "item": "MoleculeACE 活性悬崖验证",
        "status": "大部分已跑",
        "evidence": [
            REPORTS / "moleculeace_cliff_objective_selector" / "metrics_summary.csv",
            REPORTS / "moleculeace_cliff_objective_ablation" / "significance_summary.csv",
            REPORTS / "moleculeace_cliff_objective_ablation" / "cliff_aware_selector_pairs.csv",
            REPORTS / "manuscript_figures" / "fig10_moleculeace_cliff_objective_selector.png",
        ],
        "gap": "已有 51 个 seed 配对、cliff subset RMSE/MAE 和显著性汇总；缺少清单点名的“邻近分子预测差异 vs 真实差异相关性”和代表性 cliff pair 案例图。",
        "action": "若继续增强，补 prediction-gap/true-gap correlation 与 2-3 个 cliff pair 图；当前正文按有限收益/风险识别写是稳妥的。",
    },
    {
        "priority": "P1-1",
        "item": "Calibration 与 PR-AUC 主结果",
        "status": "已跑",
        "evidence": [
            REPORTS / "validation_calibration" / "calibration_metrics_summary.csv",
            REPORTS / "manuscript_tables" / "table22_imbalanced_classification_metrics.csv",
            REPORTS / "manuscript_figures_hires" / "fig8_calibration_curves.png",
        ],
        "gap": "结果文件充分；需要保证正文不只看 ROC-AUC。",
        "action": "已在修订稿中处理。",
    },
    {
        "priority": "P1-2",
        "item": "Conformal prediction 80/90/95 主表",
        "status": "部分已跑",
        "evidence": [
            REPORTS / "conformal_activity" / "conformal_summary.csv",
            REPORTS / "conformal_activity" / "figures" / "conformal_coverage.png",
            REPORTS / "manuscript_figures_hires" / "fig12_conformal_diagnostics.png",
        ],
        "gap": "只发现 alpha=0.1，即 90% 目标覆盖率；没有 80% 和 95% 两个目标覆盖率完整结果。",
        "action": "这是明确未跑完项。要么补跑 alpha=0.2/0.05，要么继续像修订稿那样标注“部分完成”。",
    },
    {
        "priority": "P1-3",
        "item": "Risk-coverage 曲线",
        "status": "已跑",
        "evidence": [
            REPORTS / "uncertainty_ad_expanded" / "risk_coverage.csv",
            REPORTS / "uncertainty_ad_tdc_admet" / "risk_coverage.csv",
            REPORTS / "manuscript_figures_hires" / "fig7_risk_coverage_curves.png",
            REPORTS / "submission_package" / "supplementary_figures" / "Figure_S1_Risk_coverage_curves.png",
        ],
        "gap": "已有 100%-50% coverage 风险曲线数据/图；上次新增的 coverage tracker 没单独列它。",
        "action": "建议在下一版 4.6 覆盖表补一行“P1-3 已完成”，不需要重跑。",
    },
    {
        "priority": "P1-4",
        "item": "失败案例分析",
        "status": "部分已跑",
        "evidence": [
            REPORTS / "manuscript_tables" / "table24_targeted_improvement_case_studies.csv",
            REPORTS / "scaffold_fragment_cases" / "selector_high_error_cases.csv",
        ],
        "gap": "已有 3 个案例，但类别不全：有 ClinTox 假阴性和高粗糙度 ADME；缺少清单点名的低相似度失败案例、MoleculeACE 活性悬崖失败案例，且不是 3-5 个完整案例面板。",
        "action": "建议再补 2 个失败案例：一个低 Tanimoto OOD，一个 MoleculeACE cliff pair。",
    },
    {
        "priority": "P1-5",
        "item": "完整负结果审计",
        "status": "已跑",
        "evidence": [
            REPORTS / "supplement_experiment_revision_20260606" / "maintext_table_negative_result_audit.csv",
            REPORTS / "manuscript_tables" / "table40_selector_strategy_policy_summary.csv",
            REPORTS / "manuscript_tables" / "table37_3d_roughness_oracle_audit.csv",
        ],
        "gap": "结果文件充分；负结果已写入修订稿。",
        "action": "无需重跑。",
    },
    {
        "priority": "P2-1",
        "item": "计算成本与收益比",
        "status": "已跑",
        "evidence": [
            REPORTS / "efficiency" / "efficiency_compact.csv",
            REPORTS / "efficiency" / "efficiency_summary.csv",
            REPORTS / "manuscript_tables" / "table7_efficiency.csv",
            REPORTS / "manuscript_figures_hires" / "fig13_efficiency_tradeoff.png",
        ],
        "gap": "已有结果；上次新增 4.6 未强调 P2。",
        "action": "若目标期刊要求成本论证，可在讨论或补充表中恢复这部分。",
    },
    {
        "priority": "P2-2",
        "item": "TDC 全终点附录",
        "status": "大部分已跑",
        "evidence": [
            REPORTS / "formal_external_appendix" / "table20_formal_external_appendix_selector.csv",
            REPORTS / "formal_external_appendix" / "table21_external_candidate_pool_coverage.csv",
            REPORTS / "formal_external_appendix" / "table25_external_win_tie_loss.csv",
        ],
        "gap": "已有 formal external appendix；需确认是否覆盖作者想要的“全终点”范围，当前更像已成型的外部附录而非无限扩展全库。",
        "action": "可作为补充材料使用；若投稿前冲更高刊，可再扩大终点数。",
    },
    {
        "priority": "P2-3",
        "item": "鲁棒性与敏感性分析",
        "status": "部分已跑",
        "evidence": [
            REPORTS / "selector_strategy_audit_20260603" / "selector_strategy_policy_summary.csv",
            REPORTS / "formal_fixed_selector_integration_20260603" / "formal_fixed_selector_policy_summary.csv",
            REPORTS / "conformal_activity" / "hard_scaffold_metrics.csv",
        ],
        "gap": "已有 risk-adjusted lambda、stability tie-breaker、Tanimoto threshold 的部分敏感性；没有完整覆盖不同 Top-K、不同 seed 数量、不同 Tanimoto bin 阈值的系统敏感性矩阵。",
        "action": "可列为未完全跑完的增强项，不影响最低可投稿版。",
    },
    {
        "priority": "P2-4",
        "item": "代码和数据审计包",
        "status": "部分已整理",
        "evidence": [
            REPORTS / "submission_package" / "README.md",
            REPORTS / "submission_package" / "main_tables",
            REPORTS / "submission_package" / "supplementary_tables",
        ],
        "gap": "submission_package 已有 181 个文件；但还需最终确认固定划分文件、候选预测矩阵、环境文件和图表生成脚本是否全部可复现。",
        "action": "投稿前单独做 reproducibility checklist。",
    },
]


rows = []
for item in items:
    evidence = item["evidence"]
    rows.append(
        {
            "priority": item["priority"],
            "experiment": item["item"],
            "completion_status": item["status"],
            "evidence_paths": "; ".join(str(p) for p in evidence),
            "evidence_shapes": "; ".join(f"{p.name}: {shape(p)}" for p in evidence),
            "remaining_gap": item["gap"],
            "recommended_action": item["action"],
        }
    )

df = pd.DataFrame(rows)
csv_path = OUT / "missing_experiment_audit.csv"
md_path = OUT / "missing_experiment_audit.md"
df.to_csv(csv_path, index=False, encoding="utf-8-sig")

lines = [
    "# Missing Experiment Audit",
    "",
    "Status labels: 已跑 = result files found and manuscript can support the claim; 部分已跑 = evidence exists but does not fully match the checklist wording; 未跑 = no result file found.",
    "",
]
for r in rows:
    lines.extend(
        [
            f"## {r['priority']} {r['experiment']}",
            f"- 状态：{r['completion_status']}",
            f"- 证据：{r['evidence_shapes']}",
            f"- 缺口：{r['remaining_gap']}",
            f"- 建议：{r['recommended_action']}",
            "",
        ]
    )
md_path.write_text("\n".join(lines), encoding="utf-8")

print(csv_path)
print(md_path)
