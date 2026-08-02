# Candidate-pool expansion audit

This repository accompanies **Candidate-pool expansion, validation-ranking
distortion and model-selection loss in molecular property prediction: a
retrospective nested audit**.

Package version and release: `paper-release-2026-08-r12.5`.

This release retains the complete `paper43_completion/` ten-split-seed analysis
layer and final Figures 1–8 from R11, and corrects the inconsistent Figure 1–7
inventory wording and submission-facing Figure 1 source without changing any
recorded result. The software release does not
assert the journal article's author order, affiliations, correspondence data,
ORCIDs, funding declarations or CRediT roles; those article metadata remain
the responsibility of the authors and are separate from this code release.

License: MIT for software. Public molecular datasets retain their original
licences and access conditions.

## Data sources

Dataset provenance, identifiers and source URLs are recorded in
`manifests/dataset_registry.json`, `manifests/data_manifest.csv` and Table S1
of Additional file 2. Dataset download and cleaning code is included; source
licences should be reviewed before downloading. The small public ESOL input
used by the cold-start test is included at
`data/raw/delaney-processed.csv`.

## Environment and hardware

- Python 3.13.7
- RDKit 2026.3.1
- Exact Python packages: `requirements-lock.txt`
- Conda environment: `environment.yml`
- CPU is sufficient for the statistical reproduction and classical models.
- A CUDA-capable GPU is recommended, but not required, for neural and
  pretrained-representation stages. Hardware-specific Torch packages are not
  installed silently.

Install with conda:

```text
conda env create -f environment.yml
conda activate fzyc-mol
```

or with a virtual environment:

```text
python -m venv .venv
python -m pip install -r requirements-lock.txt
python -m pip install -e .
```

The optional pretrained-candidate requirements are listed in
`environment/requirements-pretrained.txt`. An equivalent quick-reproduction
container can be built with `docker build -t fzyc-mol:paper-release-2026-08-r12.5 .`.

## Reproduction entry points

All commands below are run from the repository root.

Quick statistical reproduction and Figure 7 regeneration (no model refit):

```text
python scripts/reproduce_analysis.py --config configs/paper.yaml
```

Validate manuscript-facing values against machine-readable source tables:

```text
python scripts/validate_manuscript_numbers.py
```

Rebuild public data and cleaning audit:

```text
python scripts/download_open_data.py
python scripts/download_tdc_admet.py
python scripts/build_data_cleaning_audit.py
```

Generate the registered split manifests:

```text
python scripts/reproduce_full_study.py --config configs/paper.yaml --stage splits
```

Run the primary nested audit and the expanded composition intervention:

```text
python scripts/reproduce_full_study.py --config configs/paper.yaml --stage main-audit
python scripts/reproduce_full_study.py --config configs/paper.yaml --stage composition
```

Run all available training stages:

```text
python scripts/reproduce_full_study.py --config configs/paper.yaml
```

Rebuild manuscript figures and tables from checked machine-readable exports:

```text
python scripts/reproduce_analysis.py --config configs/paper.yaml --figures all --tables all
```

The Chemprop stages use the `chemprop` executable on `PATH`, or the path in
`CHEMPROP_EXECUTABLE`. The evaluated one-epoch D-MPNN configuration is locked
as reported in the manuscript; it is not presented as a fully optimized deep
learning benchmark.

The supported portable entry points are `scripts/reproduce_analysis.py` and
`scripts/reproduce_full_study.py`. Files under `scripts_current/` and the
retained Paper 31 audit directories are historical run-specific utilities and
provenance records; they are not all intended to run independently in a fresh
checkout.

## Expected outputs and runtime

- Quick reproduction: `reproduced_outputs/`; approximately 1–3 minutes on a
  modern CPU after installation.
- Generated split manifests: `splits/generated/`.
- Full-study results: `results/reproduced_full_study/`.
- Figure and table source data: `source_data/` and `reproduced_outputs/`. Final
  PDF/SVG/600-dpi PNG assets for Figures 1–8 and their checked source-data index
  are included under `reproduced_outputs/main_figures/` and
  `source_data/main_figures/`.

Full training can require hours to days depending on hardware, dataset cache,
and optional neural-model availability. Recorded downstream audit times exclude
model acquisition, encoder pretraining and cached embedding extraction, exactly
as stated in the manuscript.

## Repository map

- `configs/`: locked endpoint, candidate and paper reproduction settings.
- `data/`: licensed or redistributable example inputs and data documentation.
- `splits/`: checked split manifests and generation notes.
- `src/`: reusable package implementation.
- `scripts/`: portable download, analysis, training and validation entry points.
- `results/`: machine-readable reference results used by tests and audits.
- `source_data/`: manuscript figure/table source-data index, checked inputs for
  Figures 2–8 and the Figure 7–8 panel data; Figure 1 is a schematic.
- `tests/`: leakage, ranking, stability and reproduction regression tests.
- `docs/`: scope, audit trail and computational-exposure documentation.
- `paper31_expanded_intervention/experiment_exports/`: candidate-, fold- and
  seed-level intervention exports.
- `paper34_audit_sources/`: split, source-hash, Figure 7 and exposure records.

## Scope and limitations

This is a retrospective audit of the reported public endpoints, candidate
registries and split mechanisms, not prospective external validation.
Endpoint–pool–K cells and overlapping candidate subsets are not independent.
The modern panel contains frozen representation probes and a separately locked
one-epoch D-MPNN. Equal-budget findings concern downstream fit/predict exposure
and depend on registry order and evaluated hardware; they are not end-to-end
architecture-efficiency claims. Negative, missing and failed cells are retained.

## Integrity and citation

Run `python scripts/validate_manuscript_numbers.py` and verify `SHA256SUMS.txt`
before reusing the checked exports. The manuscript version is fixed by release
`paper-release-2026-08-r12.5`; its immutable commit is recorded in the GitHub release
and `docs/release-and-commit.md`.

For cross-platform verification, `scripts/build_release_inventory.py` hashes text
files after canonicalizing line endings to LF; binary files are hashed byte for
byte. This avoids false failures caused solely by Git's Windows line-ending
conversion.

Please cite the associated article and the software release described in
`CITATION.cff`:

> FZYC-Mol Authors. FZYC-Mol: candidate-pool expansion audit, release
> paper-release-2026-08-r12.5. GitHub. 2026.

Repository: <https://github.com/zfr0857/FZYC-Mol>

## 2026-07-28 formula and tolerance synchronization

The submission-facing layer separates the practical-equivalence tolerance tau from the numerical-stability constant epsilon_num=1e-12. The main manuscripts contain consecutively numbered native equations, and Figure 8 plus Table S38 use tau terminology. Journal author metadata are maintained separately from this software release and are not inferred here.


## R12 submission-format refinement

Release `paper-release-2026-08-r12.5` is a format-only successor to the immutable
`paper-release-2026-08-r12.4` tag. It is a metadata and submission-format
refinement of the immutable R11 analysis layer. It corrects the R11 README
inventory to Figures 1–8 and updates the title-free Figure 1 source and exports.
It additionally enforces the 8-pt minimum text size in Figures 2, 3, 5 and 6,
and synchronizes the machine-readable main Tables 3 and 4.
The R12.3 refinement sets the vertical inter-panel spacing of Figure 3 to 0.20
and Figure 6 to 0.70 while retaining non-overlapping panel titles, colour strips
and axes. It also aligns the Figure 8 A/B heading baseline and combines the former
D1/D2 displays into one D panel with independently normalized switch-rate and
outer-PR-AUC columns.
The R12.4 refinement moves the two Figure 6A colour strips from a vertical inset
anchor of -0.38 to -0.22 and uses 38% strip widths, placing them closer to panel A
without overlapping the model tick labels or the panel C heading.
The R12.5 refinement stores the unchanged 600-dpi Figure 6 raster as RGB rather
than RGBA to prevent a Microsoft Word PDF-export failure in the Chinese manuscript.
It does not change candidate eligibility, split seeds, thresholds, candidate
order, outer performance, machine-readable source results or retained negative
results. The release continues to include editable SVG, embedded-font PDF and
600-dpi PNG figures, source data, probability-level classification outputs,
split manifests, candidate/fold/split-seed outputs, equation-to-code mapping and
manuscript-number validation records.

The software release uses the existing collective software-author record in
`CITATION.cff`; it does not assert or infer the journal article's author order,
affiliations, correspondence information, ORCIDs or CRediT roles.
