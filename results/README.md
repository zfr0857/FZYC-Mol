# Results

`final/` contains the locked machine-readable reference results used by the manuscript:

- `five_seed_reference/`: paired candidate-pool and multiview reference audit.
- `composition_intervention/`: candidate-, fold-, seed-, ablation-, equal-budget-, and selection-stability exports.
- `ten_seed_audit/`: preserved run records and validation summaries for the ten-seed analysis.
- `probability_level/`: endpoint-level held-out risk predictions.
- `figures/`: one canonical copy of Figures 1–8 in SVG, PDF, and 600 dpi PNG, plus the 1200 dpi Figure 7 asset.
- `validation/`: packaged manuscript-number and quick-reproduction reports.

Quick and full reruns write to ignored `results/reproduced_analysis/` and `results/reproduced_full_study/` directories so that reference files cannot be overwritten accidentally.
