from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "reports" / "submission_package"
POLISHED_FIGS = ROOT / "reports" / "manuscript_figures_polished"
HIRES_FIGS = ROOT / "reports" / "manuscript_figures_hires"
NATURE_FIGS = ROOT / "reports" / "manuscript_figures_nature_style"
POLISHED_TABLES = ROOT / "reports" / "manuscript_tables_polished"
TABLES = ROOT / "reports" / "manuscript_tables"


MAIN_FIGURES = [
    ("fig1_framework_overview_polished", "Figure_1_FZYC_Mol_framework"),
    ("fig2_moleculenet_rank_heatmap_polished", "Figure_2_MoleculeNet_model_family_ranks"),
    ("fig3_moleculenet_performance_dots", "Figure_3_MoleculeNet_main_performance"),
    ("fig4_split_realism_polished", "Figure_4_Split_realism_structure_shift"),
    ("fig5_tdc_official_split_delta", "Figure_5_Official_TDC_ADMET_scaffold_delta"),
    ("fig6_reliability_summary_polished", "Figure_6_Uncertainty_AD_reliability"),
    ("fig11_motif_fragment_interpretation", "Figure_7_Motif_fragment_interpretation"),
    ("fig22_formal_fixed_selector_integration", "Figure_8_Formal_fixed_selector_integration"),
    ("fig24_strong_baseline_selector_governance", "Figure_9_Strong_baseline_selector_governance"),
]


POLISHED_TABLE_PREVIEWS = [
    ("table2_moleculenet_main_polished", "Table_2_MoleculeNet_main_results_polished"),
    ("table3_tdc_official_admet_polished", "Table_3_TDC_official_split_polished"),
    ("table8_formal_fixed_selector_main_polished", "Table_8_Formal_fixed_selector_integration_polished"),
]


SUPPLEMENTARY_FIGURES = [
    ("fig7_risk_coverage_curves", "Figure_S1_Risk_coverage_curves"),
    ("fig8_calibration_curves", "Figure_S2_Calibration_curves"),
    ("fig9_ablation_significance", "Figure_S3_Ablation_significance"),
    ("fig10_validation_selector_map", "Figure_S4_Validation_selector_map"),
    ("fig12_conformal_diagnostics", "Figure_S5_Conformal_diagnostics"),
    ("fig13_efficiency_tradeoff", "Figure_S6_Efficiency_tradeoff"),
    ("fig14_enrichment_activity_cliffs", "Figure_S7_Enrichment_activity_cliffs"),
    ("fig15_external_appendix_retained_delta", "Figure_S8_External_appendix_retained_delta"),
    ("fig16_external_candidate_rank_cd", "Figure_S9_External_candidate_rank_cd"),
    ("fig17_moleculenet_targeted_rebuild_decision", "Figure_S10_MoleculeNet_targeted_rebuild_decision"),
    ("fig18_nature_multimethod_fusion_decision", "Figure_S11_Nature_multimethod_fusion_decision"),
    ("fig19_tdc_nature_multimethod_fusion_decision", "Figure_S12_TDC_Nature_multimethod_fusion_decision"),
    ("fig20_3d_roughness_regression_gate", "Figure_S13_3D_roughness_regression_gate"),
    ("fig21_selector_strategy_audit_decision", "Figure_S14_Selector_strategy_audit_decision"),
    ("fig22_formal_fixed_selector_integration", "Figure_S15_Formal_fixed_selector_integration"),
    ("fig23_fzyc_mol_model_structure", "Figure_S16_FZYC_Mol_model_structure"),
    ("fig24_strong_baseline_selector_governance", "Figure_S17_Strong_baseline_selector_governance"),
]


MAIN_TABLES = [
    ("table1_dataset_protocol.csv", "Table_1_Dataset_protocol.csv"),
    ("table2_moleculenet_main.csv", "Table_2_MoleculeNet_main_results.csv"),
    ("table2_moleculenet_main_pretty_20260603.csv", "Table_2_MoleculeNet_main_results_polished.csv"),
    ("table3_tdc_official_admet.csv", "Table_3_TDC_ADMET_official_splits.csv"),
    ("table3_tdc_official_admet_pretty_20260603.csv", "Table_3_TDC_ADMET_official_splits_polished.csv"),
    ("table4_split_realism.csv", "Table_4_Split_realism.csv"),
    ("table5_ablation_significance.csv", "Table_5_Ablation_significance.csv"),
    ("table6_reliability_ad.csv", "Table_6_Reliability_AD.csv"),
    ("table7_efficiency.csv", "Table_7_Efficiency.csv"),
    ("table8_formal_fixed_selector_main.csv", "Table_8_Formal_fixed_selector_integration.csv"),
]


SUPPLEMENTARY_TABLES = [
    ("table2_moleculenet_main_long.csv", "Table_S1_MoleculeNet_main_results_long.csv"),
    ("table8_structure_full_selector.csv", "Table_S2_Structure_full_selector.csv"),
    ("table9_risk_calibrated_selector.csv", "Table_S3_Risk_calibrated_selector.csv"),
    ("table10_moleculeace_cliff_objective_selector.csv", "Table_S4_MoleculeACE_cliff_objective_selector.csv"),
    ("table10_moleculeace_cliff_objective_selector_pairs.csv", "Table_S5_MoleculeACE_cliff_pairs.csv"),
    ("table11_reliability_summary.csv", "Table_S6_Reliability_summary.csv"),
    ("table12_structure_selector_boundary_cases.csv", "Table_S7_Structure_selector_boundary_cases.csv"),
    ("table13_openadmet_expansionrx_fast_external_benchmark.csv", "Table_S8_OpenADMET_ExpansionRx_fast_external.csv"),
    ("table14_tdc_full_panel_fast_appendix_benchmark.csv", "Table_S9_TDC_full_panel_fast_appendix.csv"),
    ("table15_tdc_performance_mode_retained_best.csv", "Table_S10_TDC_performance_mode_retained_best.csv"),
    ("table16_tdc_roughness_literature_alignment.csv", "Table_S11_TDC_roughness_literature_alignment.csv"),
    ("table17_moleculenet_meta_pool_selector.csv", "Table_S12_MoleculeNet_meta_pool_selector.csv"),
    ("table18_pretrained_rescue_heads.csv", "Table_S13_Pretrained_rescue_heads.csv"),
    ("table19_moleculenet_rescue_integrated_selector.csv", "Table_S14_MoleculeNet_rescue_integrated_selector.csv"),
    ("table20_formal_external_appendix_selector.csv", "Table_S15_Formal_external_appendix_selector.csv"),
    ("table21_external_candidate_pool_coverage.csv", "Table_S16_External_candidate_pool_coverage.csv"),
    ("table22_imbalanced_classification_metrics.csv", "Table_S17_Imbalanced_classification_metrics.csv"),
    ("table23_external_seed_stability_significance.csv", "Table_S18_External_seed_stability_significance.csv"),
    ("table24_targeted_improvement_case_studies.csv", "Table_S19_Targeted_improvement_case_studies.csv"),
    ("table25_external_win_tie_loss.csv", "Table_S20_External_win_tie_loss.csv"),
    ("table26_external_candidate_rank_summary.csv", "Table_S21_External_candidate_rank_summary.csv"),
    ("table27_moleculenet_targeted_rebuild_retained_best.csv", "Table_S22_MoleculeNet_targeted_rebuild_retained_best.csv"),
    ("table28_moleculenet_rebuild_priority_matrix.csv", "Table_S23_MoleculeNet_rebuild_priority_matrix.csv"),
    ("table29_nature_multimethod_fusion_retained_best.csv", "Table_S24_Nature_multimethod_fusion_retained_best.csv"),
    ("table30_nature_multimethod_fusion_candidate_families.csv", "Table_S25_Nature_multimethod_fusion_candidate_families.csv"),
    ("table31_nature_method_alignment_matrix.csv", "Table_S26_Nature_method_alignment_matrix.csv"),
    ("table32_tdc_nature_multimethod_fusion_retained_best.csv", "Table_S27_TDC_Nature_multimethod_fusion_retained_best.csv"),
    ("table33_tdc_nature_multimethod_fusion_candidate_families.csv", "Table_S28_TDC_Nature_multimethod_fusion_candidate_families.csv"),
    ("table34_tdc_nature_method_alignment_matrix.csv", "Table_S29_TDC_Nature_method_alignment_matrix.csv"),
    ("table35_3d_roughness_regression_retained_best.csv", "Table_S30_3D_roughness_regression_retained_best.csv"),
    ("table36_3d_roughness_candidate_families.csv", "Table_S31_3D_roughness_candidate_families.csv"),
    ("table37_3d_roughness_oracle_audit.csv", "Table_S32_3D_roughness_oracle_audit.csv"),
    ("table38_selector_strategy_audit_retained_best.csv", "Table_S33_Selector_strategy_audit_retained_best.csv"),
    ("table39_selector_strategy_candidates.csv", "Table_S34_Selector_strategy_candidates.csv"),
    ("table40_selector_strategy_policy_summary.csv", "Table_S35_Selector_strategy_policy_summary.csv"),
    ("table41_formal_fixed_selector_policy_results.csv", "Table_S36_Formal_fixed_selector_policy_results.csv"),
    (
        "table42_formal_risk_adjusted_integration_retained_best.csv",
        "Table_S37_Formal_risk_adjusted_integration_retained_best.csv",
    ),
    ("table43_formal_fixed_selector_policy_summary.csv", "Table_S38_Formal_fixed_selector_policy_summary.csv"),
    ("table44_strong_tabpfn_moleculenet_retained_best.csv", "Table_S39_Strong_TabPFN_MoleculeNet_retained_best.csv"),
    ("table45_strong_tabpfn_moleculenet_candidate_families.csv", "Table_S40_Strong_TabPFN_MoleculeNet_candidate_families.csv"),
    ("table46_strong_tabpfn_method_alignment_matrix.csv", "Table_S41_Strong_TabPFN_method_alignment_matrix.csv"),
    ("table47_strong_baseline_model_coverage.csv", "Table_S42_Strong_baseline_model_coverage.csv"),
    ("table48_low_performance_targeted_actions.csv", "Table_S43_Low_performance_targeted_actions.csv"),
    ("table49_same_split_model_comparison_registry.csv", "Table_S44_Same_split_model_comparison_registry.csv"),
    ("table50_tdc_performance_mode_custom_retained_best.csv", "Table_S45_TDC_TabPFN_guard_smoke_retained_best.csv"),
    ("table51_recent_paper_writing_alignment.csv", "Table_S46_Recent_paper_writing_alignment.csv"),
    ("table52_frontmatter_methods_revision_matrix.csv", "Table_S47_Frontmatter_methods_revision_matrix.csv"),
]

DOCS = [
    ("README.md", "Project_README.md"),
    ("docs/manuscript_draft_full_en_20260527.md", "Manuscript_draft_full_en.md"),
    ("docs/manuscript_draft_full_zh_integrated_20260531.md", "Manuscript_draft_full_zh_integrated.md"),
    ("docs/manuscript_draft_full_zh_polished_20260601.docx", "Manuscript_draft_full_zh_integrated.docx"),
    ("docs/manuscript_draft_full_zh_polished_20260601.docx", "Manuscript_draft_full_zh_polished_20260601.docx"),
    ("docs/manuscript_draft_full_zh_detailed_20260601.docx", "Manuscript_draft_full_zh_detailed_20260601.docx"),
    ("docs/manuscript_draft_full_zh_polished_20260602.docx", "Manuscript_draft_full_zh_polished_20260602.docx"),
    (
        "docs/manuscript_draft_full_zh_detailed_20260602_visual_polish_20260602.docx",
        "Manuscript_draft_full_zh_detailed_20260602.docx",
    ),
    (
        "docs/manuscript_draft_full_zh_detailed_20260602_visual_polish_20260602.docx",
        "Manuscript_draft_full_zh_detailed_20260602_visual_polish_20260602.docx",
    ),
    ("docs/reference_list_expanded_20260601.md", "Reference_list_expanded_20260601.md"),
    ("docs/reference_list_expanded_20260602.md", "Reference_list_expanded_20260602.md"),
    ("docs/manuscript_draft_update_zh_20260531.md", "Manuscript_draft_update_zh.md"),
    ("docs/figure_captions_polished_20260527.md", "Figure_captions.md"),
    ("docs/table_notes_20260527.md", "Table_notes.md"),
    ("docs/supplementary_information_draft_en_20260527.md", "Supplementary_information_draft.md"),
    ("docs/reproducibility_appendix_20260527.md", "Reproducibility_appendix.md"),
    ("docs/manuscript_optimization_actions_20260527.md", "Optimization_actions.md"),
    ("docs/final_results_synthesis_20260531.md", "Final_results_synthesis.md"),
    ("docs/recent_literature_competitive_improvement_20260531.md", "Recent_literature_competitive_improvement.md"),
    ("docs/recent_literature_competitive_improvement_20260602.md", "Recent_literature_competitive_improvement_20260602.md"),
    ("docs/nature_literature_method_fusion_update_20260602.md", "Nature_literature_method_fusion_update_20260602.md"),
    ("reports/model_module_improvement/model_module_improvement_report.md", "Model_module_improvement_report.md"),
    ("reports/validation_selector_rescue_integration/README.md", "Rescue_integrated_selector_report.md"),
    ("reports/tdc_performance_mode_appendix_combined/README.md", "TDC_performance_mode_combined_report.md"),
    ("reports/formal_external_appendix/README.md", "Formal_external_appendix_update.md"),
    ("reports/moleculenet_targeted_rebuilds/README.md", "MoleculeNet_targeted_rebuilds_report.md"),
    ("reports/nature_multimethod_fusion_appendix/README.md", "Nature_multimethod_fusion_report.md"),
    ("reports/tdc_nature_multimethod_fusion_appendix/README.md", "TDC_Nature_multimethod_fusion_report.md"),
    ("reports/three_d_roughness_regression_experts_20260603/README.md", "ThreeD_roughness_regression_report.md"),
    ("docs/three_d_roughness_regression_update_20260603.md", "ThreeD_roughness_regression_update_20260603.md"),
    ("reports/selector_strategy_audit_20260603/README.md", "Selector_strategy_audit_report.md"),
    ("docs/selector_strategy_audit_update_20260603.md", "Selector_strategy_audit_update_20260603.md"),
    ("reports/formal_fixed_selector_integration_20260603/README.md", "Formal_fixed_selector_integration_report.md"),
    ("docs/formal_fixed_selector_integration_update_20260603.md", "Formal_fixed_selector_integration_update_20260603.md"),
    ("reports/strong_tabpfn_moleculenet_pilot_20260603/README.md", "Strong_TabPFN_MoleculeNet_pilot_report.md"),
    ("reports/tdc_tabpfn_guard_smoke_20260603/README.md", "TDC_TabPFN_guard_smoke_report.md"),
    ("docs/strong_baseline_model_improvement_update_20260603.md", "Strong_baseline_model_improvement_update_20260603.md"),
    ("docs/manuscript_draft_full_zh_polished_20260603.docx", "Manuscript_draft_full_zh_polished_20260603.docx"),
    ("docs/manuscript_draft_full_zh_polished_20260603.md", "Manuscript_draft_full_zh_polished_20260603.md"),
    (
        "docs/manuscript_draft_full_zh_complete_integrated_single_paper_20260603.docx",
        "Manuscript_draft_full_zh_complete_integrated_20260603.docx",
    ),
    (
        "docs/manuscript_draft_full_zh_complete_integrated_single_paper_20260603.md",
        "Manuscript_draft_full_zh_complete_integrated_20260603.md",
    ),
    (
        "docs/manuscript_draft_full_zh_complete_integrated_single_paper_20260603.docx",
        "Manuscript_draft_full_zh_complete_integrated_single_paper_20260603.docx",
    ),
    (
        "docs/manuscript_draft_full_zh_complete_integrated_single_paper_20260603.md",
        "Manuscript_draft_full_zh_complete_integrated_single_paper_20260603.md",
    ),
    (
        "docs/manuscript_draft_full_zh_complete_integrated_single_paper_20260604.docx",
        "Manuscript_draft_full_zh_complete_integrated_single_paper_20260604.docx",
    ),
    (
        "docs/manuscript_draft_full_zh_complete_integrated_single_paper_20260604.md",
        "Manuscript_draft_full_zh_complete_integrated_single_paper_20260604.md",
    ),
    (
        "docs/manuscript_draft_full_zh_complete_integrated_single_paper_20260604_normative.docx",
        "Manuscript_draft_full_zh_complete_integrated_single_paper_20260604_normative.docx",
    ),
    (
        "docs/manuscript_draft_full_zh_complete_integrated_single_paper_20260604_normative.md",
        "Manuscript_draft_full_zh_complete_integrated_single_paper_20260604_normative.md",
    ),
    (
        "docs/manuscript_frontmatter_methods_normative_review_20260604.md",
        "Manuscript_frontmatter_methods_normative_review_20260604.md",
    ),
    (
        "docs/manuscript_draft_full_zh_complete_integrated_single_paper_20260604_final_clean.docx",
        "Manuscript_draft_full_zh_complete_integrated_single_paper_20260604_final_clean.docx",
    ),
    (
        "docs/manuscript_draft_full_zh_complete_integrated_single_paper_20260604_final_clean.md",
        "Manuscript_draft_full_zh_complete_integrated_single_paper_20260604_final_clean.md",
    ),
    (
        "docs/manuscript_draft_full_zh_complete_integrated_single_paper_20260604_academic_polished.docx",
        "Manuscript_draft_full_zh_complete_integrated_single_paper_20260604_academic_polished.docx",
    ),
    (
        "docs/manuscript_draft_full_zh_complete_integrated_single_paper_20260604_academic_polished.md",
        "Manuscript_draft_full_zh_complete_integrated_single_paper_20260604_academic_polished.md",
    ),
    (
        "docs/academic_language_polish_report_20260604.md",
        "Academic_language_polish_report_20260604.md",
    ),
    (
        "docs/manuscript_draft_full_zh_complete_integrated_single_paper_20260604_academic_integrated.docx",
        "Manuscript_draft_full_zh_complete_integrated_single_paper_20260604_academic_integrated.docx",
    ),
    (
        "docs/manuscript_draft_full_zh_complete_integrated_single_paper_20260604_academic_integrated.md",
        "Manuscript_draft_full_zh_complete_integrated_single_paper_20260604_academic_integrated.md",
    ),
    (
        "docs/manuscript_results_integration_restructure_report_20260604.md",
        "Manuscript_results_integration_restructure_report_20260604.md",
    ),
    (
        "docs/manuscript_figure_hires_report_20260604.md",
        "Manuscript_figure_hires_report_20260604.md",
    ),
    (
        "docs/manuscript_draft_full_zh_complete_integrated_single_paper_20260604_academic_integrated_ordered_3line.docx",
        "Manuscript_draft_full_zh_complete_integrated_single_paper_20260604_academic_integrated_ordered_3line.docx",
    ),
    (
        "docs/manuscript_draft_full_zh_complete_integrated_single_paper_20260604_academic_integrated_ordered_3line.md",
        "Manuscript_draft_full_zh_complete_integrated_single_paper_20260604_academic_integrated_ordered_3line.md",
    ),
    (
        "docs/manuscript_draft_full_zh_complete_integrated_single_paper_20260605_nine_chapter_structure.docx",
        "Manuscript_draft_full_zh_complete_integrated_single_paper_20260605_nine_chapter_structure.docx",
    ),
    (
        "docs/manuscript_draft_full_zh_complete_integrated_single_paper_20260605_nine_chapter_structure.md",
        "Manuscript_draft_full_zh_complete_integrated_single_paper_20260605_nine_chapter_structure.md",
    ),
    (
        "docs/manuscript_nine_chapter_restructure_report_20260605.md",
        "Manuscript_nine_chapter_restructure_report_20260605.md",
    ),
    (
        "docs/初稿-1.docx",
        "初稿-1.docx",
    ),
    (
        "docs/初稿-1.md",
        "初稿-1.md",
    ),
    (
        "docs/nature_style_figure_update_report_20260605.md",
        "Nature_style_figure_update_report_20260605.md",
    ),
]


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def copy_pair(src_stem: str, dst_stem: str, dst_dir: Path) -> list[str]:
    copied: list[str] = []
    for ext in [".png", ".svg"]:
        nature_src = NATURE_FIGS / f"{src_stem}{ext}"
        hires_src = HIRES_FIGS / f"{src_stem}{ext}"
        src = nature_src if nature_src.exists() else hires_src if hires_src.exists() else POLISHED_FIGS / f"{src_stem}{ext}"
        dst = dst_dir / f"{dst_stem}{ext}"
        if not src.exists():
            raise FileNotFoundError(src)
        shutil.copy2(src, dst)
        copied.append(str(dst.relative_to(ROOT)))
    return copied


def copy_polished_table_pair(src_stem: str, dst_stem: str, dst_dir: Path) -> list[str]:
    copied: list[str] = []
    for ext in [".png", ".svg"]:
        src = POLISHED_TABLES / f"{src_stem}{ext}"
        dst = dst_dir / f"{dst_stem}{ext}"
        if not src.exists():
            raise FileNotFoundError(src)
        shutil.copy2(src, dst)
        copied.append(str(dst.relative_to(ROOT)))
    return copied


def copy_table(src_name: str, dst_name: str, dst_dir: Path) -> str:
    src = TABLES / src_name
    dst = dst_dir / dst_name
    if not src.exists():
        raise FileNotFoundError(src)
    shutil.copy2(src, dst)
    return str(dst.relative_to(ROOT))


def copy_doc(src_name: str, dst_name: str, dst_dir: Path) -> str:
    src = ROOT / src_name
    dst = dst_dir / dst_name
    if not src.exists():
        raise FileNotFoundError(src)
    shutil.copy2(src, dst)
    return str(dst.relative_to(ROOT))


def build_readme(copied: dict[str, list[str]]) -> None:
    lines = [
        "# FZYC-Mol Submission Package",
        "",
        "This directory collects manuscript-facing figures and tables with stable names.",
        "",
        "## Main Figures",
    ]
    for file in copied["main_figures"]:
        lines.append(f"- `{file}`")
    lines.extend(["", "## Supplementary Figures"])
    for file in copied["supplementary_figures"]:
        lines.append(f"- `{file}`")
    lines.extend(["", "## Main Tables"])
    for file in copied["main_tables"]:
        lines.append(f"- `{file}`")
    lines.extend(["", "## Polished Table Previews"])
    for file in copied["polished_table_previews"]:
        lines.append(f"- `{file}`")
    lines.extend(["", "## Supplementary Tables"])
    for file in copied["supplementary_tables"]:
        lines.append(f"- `{file}`")
    lines.extend(["", "## Drafts and Notes"])
    for file in copied["docs"]:
        lines.append(f"- `{file}`")
    lines.extend(
        [
            "",
            "## Recommended Use",
            "",
            "- Use PNG files for quick manuscript drafting; exported high-resolution figures are preferred when available.",
            "- Use SVG files for final vector-quality submission if the journal accepts them.",
            "- Figure captions are in `docs/figure_captions_polished_20260527.md`.",
            "- Table notes are in `docs/table_notes_20260527.md`.",
            "- Supplementary information draft is in `docs/supplementary_information_draft_en_20260527.md`.",
            "- Run `python scripts\\check_manuscript_consistency.py` after building the package to create `number_audit.csv` and `number_audit.md`.",
        ]
    )
    (PACKAGE / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    reset_dir(PACKAGE)
    main_fig_dir = PACKAGE / "main_figures"
    supp_fig_dir = PACKAGE / "supplementary_figures"
    main_table_dir = PACKAGE / "main_tables"
    supp_table_dir = PACKAGE / "supplementary_tables"
    polished_table_dir = PACKAGE / "polished_tables"
    doc_dir = PACKAGE / "docs"
    for path in [main_fig_dir, supp_fig_dir, main_table_dir, supp_table_dir, polished_table_dir, doc_dir]:
        path.mkdir(parents=True, exist_ok=True)

    copied = {
        "main_figures": [],
        "supplementary_figures": [],
        "main_tables": [],
        "supplementary_tables": [],
        "polished_table_previews": [],
        "docs": [],
    }
    for src, dst in MAIN_FIGURES:
        copied["main_figures"].extend(copy_pair(src, dst, main_fig_dir))
    for src, dst in SUPPLEMENTARY_FIGURES:
        copied["supplementary_figures"].extend(copy_pair(src, dst, supp_fig_dir))
    for src, dst in MAIN_TABLES:
        copied["main_tables"].append(copy_table(src, dst, main_table_dir))
    for src, dst in POLISHED_TABLE_PREVIEWS:
        copied["polished_table_previews"].extend(copy_polished_table_pair(src, dst, polished_table_dir))
    for src, dst in SUPPLEMENTARY_TABLES:
        copied["supplementary_tables"].append(copy_table(src, dst, supp_table_dir))
    for src, dst in DOCS:
        copied["docs"].append(copy_doc(src, dst, doc_dir))

    build_readme(copied)
    print(f"Built submission package at {PACKAGE}")


if __name__ == "__main__":
    main()
