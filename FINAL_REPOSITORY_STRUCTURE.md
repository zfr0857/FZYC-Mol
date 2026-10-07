# Final repository structure

```text
FZYC-Mol/
├── README.md
├── LICENSE
├── CITATION.cff
├── VERSION
├── environment.yml
├── requirements-lock.txt
├── requirements-pretrained.txt
├── pyproject.toml
├── Dockerfile
├── configs/
│   ├── paper.yaml
│   └── supporting static registries
├── data/
│   ├── raw/
│   └── README.md
├── splits/
│   ├── final/
│   └── README.md
├── src/
│   └── fzyc_mol/
├── scripts/
│   ├── reproduce_full_study.py
│   ├── reproduce_analysis.py
│   ├── validate_manuscript_numbers.py
│   └── required data, training, figure, and verification helpers
├── results/
│   ├── final/
│   │   ├── five_seed_reference/
│   │   ├── composition_intervention/
│   │   ├── ten_seed_audit/
│   │   ├── probability_level/
│   │   ├── figures/
│   │   └── validation/
│   └── README.md
├── source_data/
│   ├── figures/
│   ├── tables/
│   └── README.md
├── manifests/
│   ├── dataset_registry.json
│   ├── data_manifest.csv
│   └── endpoint_registry.csv
├── tests/
├── docs/
│   ├── reproducibility-scope.md
│   └── Equation_to_code_mapping.csv
├── pre_cleanup_reference_hashes.csv
├── post_cleanup_reference_hashes.csv
├── FILE_INVENTORY.csv
└── SHA256SUMS.txt
```

## Roles and entry points

- `configs/paper.yaml` is the only top-level manuscript workflow configuration.
- `src/fzyc_mol/` is the only implementation package.
- `splits/final/` is the only location for locked manuscript split manifests.
- `results/final/` is the only location for locked reference results and rendered figures.
- `source_data/` is the only location for machine-readable figure/table inputs.
- `python scripts/validate_manuscript_numbers.py` validates manuscript-facing invariants.
- `python scripts/reproduce_analysis.py --config configs/paper.yaml` performs the quick analysis reproduction.
- `python scripts/reproduce_full_study.py --config configs/paper.yaml` enters the staged full workflow.

Generated reruns are separated from locked reference results and ignored by Git.
