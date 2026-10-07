# Reproducibility scope

## Quick validation

`scripts/validate_manuscript_numbers.py` checks the locked candidate-pool registry, K ladder, endpoint counts, direction counts, outer-unit count, and matched-subset count. `scripts/reproduce_analysis.py` reads the canonical composition-intervention tables and regenerates Figure 7 in a separate output directory.

These commands do not retrain models and do not modify `results/final/`.

## Full workflow

`scripts/reproduce_full_study.py --config configs/paper.yaml` exposes the locked stages for split-manifest validation, the main nested audit, the composition intervention, and optional Chemprop inner/outer panels. The top-level configuration fixes endpoints, seed lists, fold counts, and the K ladder.

Full fitting can require substantial CPU/GPU time and third-party datasets. Chemprop and pretrained-model stages require the optional environment in `requirements-pretrained.txt`.

## Canonical versus generated files

- Canonical inputs: `configs/`, `data/`, `manifests/`, and `splits/final/`.
- Canonical implementation: `src/fzyc_mol/` and the supported scripts listed in the root README.
- Canonical reference outputs: `results/final/` and `source_data/`.
- Generated reruns: `results/reproduced_analysis/`, `results/reproduced_full_study/`, and `data/processed/`; these are ignored by Git.

The cleanup integrity check matches protected files by raw SHA-256, allowing directory and filename changes while detecting any content change.
