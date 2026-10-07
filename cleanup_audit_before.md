# Repository Cleanup Audit — Before Changes

Baseline: immutable tag `paper-release-2026-08-r12.9` at commit `85c4ee7`.

- Tracked files: 2,090
- Tracked size: 179,557,100 bytes
- Baseline compileall: PASS
- Baseline pytest: PASS (82 tests)
- Baseline manuscript-number validation: PASS
- Baseline quick analysis reproduction: PASS

## KEEP

- Root governance and environment files: `LICENSE`, `CITATION.cff`, `VERSION`, `.gitignore`, `environment.yml`, `requirements-lock.txt`, `pyproject.toml`, and `Dockerfile`.
- `configs/paper.yaml` as the single public top-level experiment configuration, plus the static endpoint/candidate/data registries it references.
- `data/`, `manifests/`, `splits/`, `src/fzyc_mol/`, and `tests/`.
- Machine-readable scientific outputs currently under `results/`, `source_data/`, `paper31_expanded_intervention/experiment_exports/`, and the ten-seed records under `paper43_completion/`.
- Final figure and table source data, retained once in canonical locations.
- Portable download, training, analysis, validation, and inventory scripts that are directly reachable from the final reproduction entry points.

## MOVE

- `paper31_expanded_intervention/experiment_exports/` → `results/final/composition_intervention/`.
- `paper43_completion/run_records/` → `results/final/ten_seed_audit/run_records/`.
- `paper43_completion/probability_level_outputs/` → `results/final/probability_level/`.
- `results/reviewer_core_20260624/` → `results/final/five_seed_reference/` as explicitly labelled secondary/reference evidence.
- Canonical final figures → `results/final/figures/`.
- Final paper-facing source data → `source_data/figures/` and `source_data/tables/`.
- Necessary final-analysis scripts embedded in historical Paper 31/43 or manuscript-formatting directories → `scripts/`, with repository-root-relative paths.

## MERGE

- `configs_current/` into `configs/`: all 24 files are SHA256-identical to files already in `configs/`; `configs/paper.yaml` exists only in the canonical directory.
- `src_current/` into `src/`: all 44 files are SHA256-identical.
- `scripts_current/` into `scripts/`: 197 files are identical; only final-entry dependencies will be retained from the non-identical historical utilities.
- `paper34_audit_sources/` into `splits/`, `results/final/`, and `source_data/`: all 13 files have identical copies elsewhere.
- Repeated Figure 1–8 exports and source-data copies into one canonical figure/result location.

## DELETE AFTER VALIDATION

- `configs_current/`, `src_current/`, and `scripts_current/` after imports and path references are repaired.
- `submission_documents/`: submission-system documents and duplicated figure/source-data copies; 68 of 81 files are byte-identical elsewhere, while the 13 unique files are journal documents or submission audits rather than scientific result sources.
- `manuscript_finalization/`: Word/WPS/PDF/font/formula QC assets and screenshots, after migrating the one Figure 7 rendering dependency and equation-to-code mapping.
- `paper34_audit_sources/`: entirely duplicated by canonical scientific directories.
- `paper31_expanded_intervention/` and `paper43_completion/` only after all unique machine-readable scientific content is migrated and SHA256-verified.
- Tracked caches, `__pycache__/`, `*.pyc`, temporary logs, and repeated figure copies.
- Historical manuscript-building, submission-formatting, and dated Paper 25–31 scripts that are unreachable from the final reproduction entry points.

## REVIEW

- Five-seed and ten-seed outputs must remain explicitly distinguished; no evidence layer will be relabelled as an independent confirmation.
- `configs/paper.yaml` currently labels an older release and conflates five-seed composition work with the ten-seed primary audit; it requires a metadata/path correction without changing any registered seed or result.
- `environment.yml` and `Dockerfile` reference obsolete requirement paths and must be synchronized with root `requirements-lock.txt`.
- Full model refitting is not required for cleanup acceptance, but saved reference outputs, source data, split checksums, manuscript values, and all repository paths must be validated.

## Dependency Audit Summary

- `configs_current` is referenced only by `entrypoints/full_training_entry.py`.
- `scripts_current` is referenced by `README.md`, `entrypoints/full_training_entry.py`, and `scripts/reproduce_full_study.py`.
- `manuscript_finalization` is referenced by `entrypoints/quick_reproduce.py` for Figure 7 rendering.
- `paper34_audit_sources` is referenced by the README, split documentation, and `scripts/reproduce_full_study.py`.
- `paper31_expanded_intervention` is referenced by the two entry points and manuscript-value validation.
- `paper43_completion` is referenced only by historical/finalization scripts and documentation, not by the current quick validation entry points.

No directory will be removed until its dependencies are redirected, baseline scientific files are hashed, and the pre-deletion test stage passes.
