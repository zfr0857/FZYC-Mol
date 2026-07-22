# Main-figure source data

This directory contains the checked machine-readable inputs used by the final
publication layouts for Figures 2–6. Figure 1 is a study-design schematic and
has no numerical source table. Figure 7 is regenerated from the locked Paper 31
exports; its panel-specific tables remain one directory above.

The final PDF, SVG and 600-dpi PNG assets for Figures 1–7 are stored in
`reproduced_outputs/main_figures/`. SVG labels are outlined from Times New Roman
to make Word and WPS rendering deterministic; the corresponding PDF and PNG
files preserve the same typography.

| Figure | Checked source files |
|---|---|
| 1 | Schematic; no numerical source table |
| 2 | `effective_rank_bootstrap_5000_summary.csv`, `effective_rank_leave_one_out.csv`, `effective_rank_reference_sensitivity.csv` |
| 3 | `ranking_metric_main_summary.csv`, `mechanism_permutation_null_summary.csv`, `mechanism_signal_recovery_summary.csv`, `cross_fitted_complete_intervals.csv`, `candidate_composition_controls.csv` |
| 4 | `audit_gap_decomposition_units.csv`, `cross_fitted_complete_intervals.csv`, `cross_fitted_fold_effects.csv`, `paper19_oracle_extreme_value_simulation.csv`, `Figure_4C_integrated_forest_source.csv` |
| 5 | `matched_k3_220_subset_units.csv`, `matched_k3_220_subset_summary.csv`, `matched_k_multiview_summary.csv`, `Figure_5D_integrated_forest_source.csv` |
| 6 | `Figure_6A_double_triangle_matrix_source.csv`, `Figure_6A_prediction_diversity_summary.csv`, `Figure_6B_support_risk_matrix_source.csv`, `Figure_6C_scaffold_reliability_source.csv`, `Figure_6D_four_model_clintox_source.csv` |
| 7 | `../Figure_7_Panel_A_source.csv` through `../Figure_7_Panel_D_source.csv` and locked Paper 31 experiment exports |
