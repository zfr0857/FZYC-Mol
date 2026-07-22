from __future__ import annotations

from pathlib import Path

import pandas as pd

from .io import ExperimentConfig, write_csv


def moleculeace_status(config: ExperimentConfig) -> pd.DataFrame:
    """Report whether existing MoleculeACE outputs are ready for 30-task aggregation."""
    candidates = [
        config.root / "reports" / "moleculeace_multifp" / "metrics_raw.csv",
        config.root / "reports" / "moleculeace_cliff_objective_selector" / "metrics_raw.csv",
        config.root / "reports" / "moleculeace_cliff_ablation" / "cliff_aware_selector_summary.csv",
    ]
    rows = []
    for path in candidates:
        rows.append({"artifact": str(path), "exists": path.exists(), "size_bytes": path.stat().st_size if path.exists() else 0})
    frame = pd.DataFrame(rows)
    write_csv(frame, config.reports_dir / "moleculeace_input_status.csv")
    return frame


def aggregate_moleculeace_if_available(config: ExperimentConfig) -> pd.DataFrame:
    paths = [
        config.root / "reports" / "moleculeace_multifp" / "metrics_raw.csv",
        config.root / "reports" / "moleculeace_cliff_objective_selector" / "metrics_raw.csv",
    ]
    frames = []
    for path in paths:
        if path.exists():
            frame = pd.read_csv(path)
            frame["source_file"] = str(path)
            frames.append(frame)
    if not frames:
        status = moleculeace_status(config)
        write_csv(status[~status["exists"]], config.reports_dir / "missing_data_report.csv")
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True, sort=False)
    write_csv(out, config.reports_dir / "moleculeace_30_task_metrics_raw.csv")
    if {"task", "model"}.issubset(out.columns):
        summary = out.groupby(["task", "model"], dropna=False).mean(numeric_only=True).reset_index()
        write_csv(summary, config.reports_dir / "moleculeace_30_task_summary.csv")
    return out
