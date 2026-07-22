from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.experiment_update.aggregate_results import aggregate_results
from fzyc_mol.experiment_update.baselines_strong import run_strong_baselines
from fzyc_mol.experiment_update.bro5_panel import discover_bro5_data
from fzyc_mol.experiment_update.data_splits import generate_splits
from fzyc_mol.experiment_update.imbalance_panel import run_imbalance_panel
from fzyc_mol.experiment_update.io import load_config, write_csv
from fzyc_mol.experiment_update.moleculeace_cliff_audit import aggregate_moleculeace_if_available, moleculeace_status
from fzyc_mol.experiment_update.roughness_diagnostics import correlate_roughness_with_selector, run_roughness_diagnostics
from fzyc_mol.experiment_update.selector_audit import build_selector_audit


def write_plan(config, dry_run: bool) -> None:
    rows = [
        {"step": "data_splits", "artifact": "split_indices.csv", "runs_in_dry_run": True},
        {"step": "strong_baselines", "artifact": "strong_baselines_metrics.csv", "runs_in_dry_run": False},
        {"step": "imbalance_panel", "artifact": "imbalance_panel_metrics.csv", "runs_in_dry_run": False},
        {"step": "bro5_panel", "artifact": "bro5_data_status.csv", "runs_in_dry_run": True},
        {"step": "moleculeace_status", "artifact": "moleculeace_input_status.csv", "runs_in_dry_run": True},
        {"step": "roughness_diagnostics", "artifact": "roughness_diagnostics.csv", "runs_in_dry_run": True},
        {"step": "selector_audit", "artifact": "selector_audit.csv", "runs_in_dry_run": False},
        {"step": "aggregate_results", "artifact": "reports/manuscript_tables/experiment_update/*.csv", "runs_in_dry_run": True},
    ]
    write_csv(__import__("pandas").DataFrame(rows), config.reports_dir / "experiment_update_plan.csv")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FZYC-Mol experiment-update modules.")
    parser.add_argument("--config", default=str(ROOT / "configs" / "experiment_update.yaml"))
    parser.add_argument("--dry-run", action="store_true", help="Generate split/status/field reports without fitting strong baselines.")
    parser.add_argument("--skip-baselines", action="store_true")
    parser.add_argument("--skip-imbalance", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config, root=ROOT)
    config.ensure_dirs()
    write_plan(config, args.dry_run)

    discover_bro5_data(config)
    moleculeace_status(config)
    aggregate_moleculeace_if_available(config)
    if not args.dry_run:
        generate_splits(config)
        run_roughness_diagnostics(config)

    if not args.dry_run and not args.skip_baselines:
        run_strong_baselines(config)
        build_selector_audit(config)
        correlate_roughness_with_selector(config)
    if not args.dry_run and not args.skip_imbalance:
        run_imbalance_panel(config)

    outputs = aggregate_results(config)
    print(f"Wrote experiment-update artifacts under {config.reports_dir}")
    print(f"Wrote manuscript tables under {config.manuscript_tables_dir}")
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
