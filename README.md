# FZYC-Mol

Reproducibility repository for **Auditing Model-Selection Reliability under Candidate-Pool Expansion in Molecular Property Prediction**.

This repository contains the locked configuration, canonical implementation, fixed split manifests, machine-readable reference results, and figure/table source data used for the manuscript. Historical manuscript drafts, submission-system files, rendering checks, duplicate scripts, and development-stage copies are intentionally excluded.

## Repository map

- `configs/paper.yaml`: single top-level manuscript configuration.
- `src/fzyc_mol/`: canonical Python implementation.
- `data/`: redistributable raw data and locally generated processed data.
- `manifests/`: dataset registry, provenance, and expected checksums.
- `splits/final/`: locked split manifests; these files must not be regenerated for reference-result validation.
- `scripts/`: supported data, experiment, analysis, and validation entry points.
- `results/final/`: canonical machine-readable reference results and final figures.
- `source_data/`: figure and main-table source data.
- `tests/`: unit and reference-result tests.
- `docs/reproducibility-scope.md`: what is reproduced quickly versus retrained in the full workflow.

## Environment

Python 3.13.7 is the locked environment version.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-lock.txt
```

The optional pretrained/Chemprop stages require:

```bash
python -m pip install -r requirements-pretrained.txt
```

Conda users can instead create the environment from `environment.yml`. The `Dockerfile` runs the quick analysis reproduction by default.

## Data

The small ESOL/Delaney file is included under `data/raw/`. Other datasets are obtained from their public providers because redistribution terms differ. Source URLs, expected filenames, access metadata, and packaged-file checksums are recorded in `manifests/`.

```bash
python scripts/download_open_data.py
python scripts/download_tdc_admet.py
python scripts/build_data_cleaning_audit.py
```

Review the upstream licence and access terms before downloading or redistributing any third-party dataset.

## Reproduction

Validate all manuscript-facing invariants against the bundled reference results:

```bash
python scripts/validate_manuscript_numbers.py
```

Reproduce the checked analysis and Figure 7 from canonical result tables:

```bash
python scripts/reproduce_analysis.py --config configs/paper.yaml
```

Generated quick-analysis files are written to `results/reproduced_analysis/` and do not overwrite the locked files in `results/final/`.

Run the complete staged experiment workflow:

```bash
python scripts/reproduce_full_study.py --config configs/paper.yaml
```

The full workflow uses the locked seed lists, 3 outer folds, 3 inner folds, and candidate-pool sizes 4, 8, 16, and 32 specified in `configs/paper.yaml`. It can be run one stage at a time with `--stage`. Full model fitting, especially optional Chemprop stages, is substantially slower than the quick validation.

## Reference outputs

- Final figures: `results/final/figures/`
- Five-seed reference audit: `results/final/five_seed_reference/`
- Composition intervention: `results/final/composition_intervention/`
- Ten-seed audit records: `results/final/ten_seed_audit/`
- Probability-level outputs: `results/final/probability_level/`
- Figure source data: `source_data/figures/`
- Main tables: `source_data/tables/`
- Locked split manifests: `splits/final/`

Figure 1 is a workflow schematic and therefore has no numerical source table. The source-data README maps the remaining figures and tables to their files.

## Verification

```bash
python -m compileall -q src scripts tests
python -m pytest -q
python scripts/verify_scientific_integrity.py compare --before pre_cleanup_reference_hashes.csv --after post_cleanup_reference_hashes.csv
```

`FILE_INVENTORY.csv` and `SHA256SUMS.txt` describe the current repository state. Their text-file hashes canonicalize line endings to LF for cross-platform verification; binary files are hashed byte-for-byte. The scientific-integrity report separately records raw-byte checks for protected scientific files and confirms whether any changed.

## Citation and licence

Citation metadata are provided in `CITATION.cff`. The source code is released under the MIT License; third-party datasets remain subject to their original terms.
