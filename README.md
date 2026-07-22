# Candidate-pool expansion audit: code and reproducibility package

Package version: `paper35-final-minor-revision-20260718`

License: MIT (software). Public molecular datasets are not redistributed;
their original licences and access conditions continue to apply.

This is the manuscript's Additional file 4. It contains source code, locked
environment files, data acquisition and cleaning scripts, candidate
registries, split manifests, fold/seed/candidate exports, figure and table
source data, timing and failure logs, and portable quick and training-level
entry points. The maintained source repository is
<https://github.com/zfr0857/FZYC-Mol>. No Zenodo record or DOI is
claimed unless one is added to a later archived release.

## Contents

- `entrypoints/quick_reproduce.py`: verifies the machine-readable Figure 7
  inputs, recalculates the six-endpoint modern-augmentation direction check,
  and regenerates the final Figure 7 assets.
- `entrypoints/full_training_entry.py`: stages the checked-in scripts and
  invokes the locked Paper 31 training stages in a user-selected workspace.
- `environment/`: Python/conda environment files with pinned versions,
  including Python 3.13.7, RDKit 2026.3.1 and the main analysis libraries.
- `Dockerfile`: equivalent container entry point for the bundled quick
  reproduction, built from the same locked Python requirements.
- `scripts_current/`, `src_current/`, `configs_current/`: source snapshot used
  for the final audit.
- `paper31_expanded_intervention/experiment_exports/`: per-fold, per-seed and
  per-candidate exports, registry files, split-loop outputs and timing data.
- `paper31_expanded_intervention/verification/training_logs/`: captured stdout
  and stderr logs for new-candidate and similarity-split stages.
- `paper34_audit_sources/`: final Figure 7 source tables, split manifests,
  source hashes and computational-exposure records.
- `data/raw/delaney-processed.csv`: the public ESOL input used by the bundled
  cold-start regression test.
- `results/reviewer_core_20260624/`: retained reviewer-facing result tables,
  manifests, and shared-split multiview outputs used by the regression tests.
- `manuscript_finalization/`: the final Figure 7 and manuscript assembly code.
- `CODE_AND_DATA_CONTENTS.csv`, `SHA256SUMS.txt`: machine-readable inventory
  and integrity hashes.

## Environment

From the package root in PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r environment\requirements.lock
```

Alternatively, clone the maintained repository first:

```text
git clone https://github.com/zfr0857/FZYC-Mol.git
cd FZYC-Mol
```

The pretrained-candidate stages may require the additional packages listed in
`environment/requirements-pretrained.txt`. Hardware-specific runtimes are not
silently installed by the entry points.

The Chemprop stages call `chemprop` from `PATH` by default. If the executable
is installed elsewhere, set `CHEMPROP_EXECUTABLE` to its full path before
running `chemprop-inner` or `chemprop-outer`.

Equivalent Docker quick reproduction:

```text
docker build -t candidate-pool-audit:paper35 .
docker run --rm candidate-pool-audit:paper35
```

## Quick reproduction of statistics and Figure 7

```powershell
.\.venv\Scripts\python.exe entrypoints\quick_reproduce.py
```

Outputs are written to `reproduced_outputs/`. The script reads only the bundled
machine-readable exports; it does not refit molecular models.

## Training-level reproduction

First obtain the public datasets with the checked-in acquisition scripts and
review each source licence:

```powershell
.\.venv\Scripts\python.exe scripts_current\download_open_data.py
.\.venv\Scripts\python.exe scripts_current\download_tdc_admet.py
.\.venv\Scripts\python.exe scripts_current\build_data_cleaning_audit.py
```

Then run the locked expansion stages in a workspace containing the downloaded
and cleaned data:

```powershell
.\.venv\Scripts\python.exe entrypoints\full_training_entry.py --workspace D:\audit_reproduction new-candidates
.\.venv\Scripts\python.exe entrypoints\full_training_entry.py --workspace D:\audit_reproduction chemprop-inner
.\.venv\Scripts\python.exe entrypoints\full_training_entry.py --workspace D:\audit_reproduction chemprop-outer
```

The one-epoch D-MPNN configuration is intentionally preserved because it is
the evaluated locked configuration, not a claim of fully optimized modern
architecture performance. Downstream timing excludes pretrained-encoder
acquisition, pretraining and cached embedding extraction.

## Scope and integrity

The package supports a retrospective audit within the evaluated endpoints,
registries and split mechanisms. Endpoint–pool–K cells and overlapping
candidate subsets are not independent experiments. Missing or unavailable
cells, negative results and captured error logs are retained rather than
imputed. Run `entrypoints/quick_reproduce.py` and verify `SHA256SUMS.txt` before
using the exports.

The supported portable interfaces are the two scripts in `entrypoints/`.
Run-specific utilities retained in `scripts/`, `scripts_current/`, and the
audit-source directories document the complete analysis history; some expect
the directory layout recorded for the original run and are not independent
command-line interfaces.
