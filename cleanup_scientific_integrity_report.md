# Repository cleanup and scientific-integrity report

## Scope

The repository was consolidated from the fixed `paper-release-2026-08-r12.9` state on branch `cleanup/final-reproducibility-core`. The historical tag and all earlier tags were left unchanged.

The operation reorganized files, removed development/submission artifacts, corrected imports and relative paths, and simplified public documentation. It did not retrain models or recalculate reference results.

## Pre-cleanup audit

- Original tracked files: **2,090**
- Original tracked size: **179,557,100 bytes**
- Baseline tests: **82 passed**
- Baseline compile check: **passed**
- Baseline manuscript-number validation: **passed**
- Baseline quick analysis reproduction: **passed**
- Protected scientific files in the raw-hash comparison: **1,065**
- Duplicate protected instances identified by SHA-256: **242**

The pre-cleanup disposition and dependency evidence are recorded in `cleanup_audit_before.md`. The raw reference hashes are in `pre_cleanup_reference_hashes.csv`.

## Consolidation performed

- Merged duplicate `configs_current/` content into canonical `configs/` and retained `configs/paper.yaml` as the sole workflow entry.
- Confirmed `src_current/` was byte-identical to `src/`; retained only `src/fzyc_mol/`.
- Reduced the public script set to supported entry points, their tested dependencies, and necessary data/figure/integrity helpers.
- Moved composition-intervention exports to `results/final/composition_intervention/`.
- Moved the five-seed reference audit to `results/final/five_seed_reference/`.
- Moved ten-seed run records and validation evidence to `results/final/ten_seed_audit/`.
- Moved probability-level outputs to `results/final/probability_level/`.
- Moved one canonical Figure 1–8 set to `results/final/figures/`.
- Consolidated all locked split manifests under `splits/final/` without regenerating them.
- Consolidated figure/table source data under `source_data/figures/` and `source_data/tables/`.
- Preserved the equation-to-code map at `docs/Equation_to_code_mapping.csv`.
- Replaced verbose training logs with the existing structured execution audit plus `results/final/validation/failure_summary.csv`, derived only from recorded completion/limitation evidence.
- Corrected `environment.yml`, `Dockerfile`, and GitHub Actions to use the root `requirements-lock.txt` and current entry points.

## Removed historical material

The following noncanonical directories were removed after the first post-migration test gate passed:

- `configs_current/`
- `src_current/`
- `scripts_current/`
- `submission_documents/`
- `manuscript_finalization/`
- `paper34_audit_sources/`
- `paper31_expanded_intervention/` after unique result/code migration
- `paper43_completion/` after unique result/source-data/split migration
- obsolete `entrypoints/` and duplicate `environment/`

Historical manuscripts, submission documents, rendering screenshots, QC workbooks, duplicate figures, stale inventories, and run logs were excluded from the final reproducibility core.

## Scientific integrity

The final comparison matches each protected pre-cleanup scientific file to a byte-identical raw SHA-256 in a canonical post-cleanup location. Configuration/documentation changes are reported separately and are not treated as scientific outputs.

- Protected pre-cleanup files: **1,065**
- Preserved by raw SHA-256: **1,065**
- Missing or content-changed protected files: **0**
- Split manifests regenerated: **0**
- Model retraining performed during cleanup: **0**
- Scientific result changes: **0**

See `post_cleanup_reference_hashes.csv` for the canonical post-cleanup snapshot.

## Final validation

- `python -m compileall -q src scripts tests`: **PASS**
- `python -m pytest -q`: **PASS — 82 passed**
- `python scripts/validate_manuscript_numbers.py`: **PASS**
- `python scripts/reproduce_analysis.py --config configs/paper.yaml`: **PASS**
- `python scripts/reproduce_full_study.py --config configs/paper.yaml --stage splits`: **PASS**
- Raw SHA-256 scientific-integrity comparison: **PASS**

## Final footprint

- Final tracked files: **1,231**
- Final tracked size: **65,250,685 bytes**
- Files removed: **859**
- Size reduction: **114,306,415 bytes**

**Scientific result changes: 0**
