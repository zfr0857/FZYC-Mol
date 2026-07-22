from __future__ import annotations

from pathlib import Path

import pandas as pd

from .io import ExperimentConfig, output_manifest, write_csv


TABLE_MAP = {
    "strong_baselines_metrics.csv": "table_strong_baselines.csv",
    "selector_audit_summary.csv": "table_selector_audit.csv",
    "imbalance_panel_metrics.csv": "table_imbalance.csv",
    "bro5_data_status.csv": "table_bro5_data_status.csv",
    "moleculeace_30_task_summary.csv": "table_moleculeace.csv",
    "roughness_selector_risk_correlation.csv": "table_roughness_selector_risk.csv",
    "selector_audit.csv": "table_negative_results.csv",
}


def aggregate_results(config: ExperimentConfig) -> list[Path]:
    outputs = []
    for source_name, target_name in TABLE_MAP.items():
        source = config.reports_dir / source_name
        target = config.manuscript_tables_dir / target_name
        if not source.exists():
            continue
        frame = pd.read_csv(source)
        if target_name == "table_negative_results.csv" and {"regret", "selected_candidate"}.issubset(frame.columns):
            frame = frame[frame["regret"].fillna(0) > 0].copy()
        write_csv(frame, target)
        outputs.append(target)
    field_rows = []
    for path in outputs:
        frame = pd.read_csv(path, nrows=3)
        field_rows.append({"table": path.name, "fields": "; ".join(frame.columns)})
    if field_rows:
        outputs.append(write_csv(pd.DataFrame(field_rows), config.manuscript_tables_dir / "output_field_dictionary.csv"))
    outputs.append(output_manifest(outputs, config.manuscript_tables_dir / "output_manifest.csv"))
    return outputs
