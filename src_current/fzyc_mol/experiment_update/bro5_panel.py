from __future__ import annotations

from pathlib import Path

import pandas as pd

from .io import ExperimentConfig, write_csv


def discover_bro5_data(config: ExperimentConfig) -> pd.DataFrame:
    rows = []
    data_root = config.data_dir / "bro5"
    for dataset in config.datasets("bro5"):
        candidates = list(data_root.glob(f"{dataset}*.csv")) + list(data_root.glob(f"{dataset}*.tsv"))
        if candidates:
            rows.append({"dataset": dataset, "status": "available", "path": str(candidates[0])})
        else:
            rows.append(
                {
                    "dataset": dataset,
                    "status": "missing_data",
                    "path": "",
                    "reason": "Place a CSV/TSV file under data/bro5 with columns smiles and y before running bRo5 evaluation.",
                }
            )
    out = pd.DataFrame(rows)
    write_csv(out, config.reports_dir / "bro5_data_status.csv")
    missing = out[out["status"].eq("missing_data")]
    if not missing.empty:
        write_csv(missing, config.reports_dir / "missing_data_report.csv")
    return out
