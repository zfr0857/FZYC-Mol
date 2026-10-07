# Data

`raw/` contains the redistributable ESOL/Delaney file packaged with this repository. Downloaded third-party datasets belong in `raw/`; derived features belong in `processed/` and are ignored by Git.

The canonical dataset registry is `manifests/dataset_registry.json`, and provenance/checksum records are in `manifests/data_manifest.csv`. Use `scripts/download_open_data.py` for supported public URLs and `scripts/download_tdc_admet.py` for TDC ADMET tasks. Always review upstream licence and access terms before redistribution.
