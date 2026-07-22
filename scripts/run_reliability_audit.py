from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fzyc_mol.reporting.stage_d import build_risk_coverage_outputs, build_tdc_gate_outputs  # noqa: E402


def combine_conformal_outputs(root: Path = ROOT) -> Path:
    reliability = root / "results" / "reliability"
    frames = []
    for suffix in ("020", "010", "005"):
        frame = pd.read_csv(reliability / f"conformal_alpha_{suffix}" / "conformal_summary.csv")
        frame["target_coverage"] = 1.0 - frame["alpha"]
        frames.append(frame)
    output = reliability / "conformal_long.csv"
    combined = pd.concat(frames, ignore_index=True)
    order = [column for column in ("target_coverage", "dataset", "seed") if column in combined]
    combined.sort_values(order).to_csv(output, index=False)
    return output


def build_outputs(root: Path = ROOT, *, bootstrap_replicates: int = 5000) -> dict[str, Path]:
    external = root / "results" / "external_panels"
    reliability = root / "results" / "reliability"
    external.mkdir(parents=True, exist_ok=True)
    reliability.mkdir(parents=True, exist_ok=True)

    gate, confusion = build_tdc_gate_outputs(
        pd.read_csv(root / "reports" / "manuscript_tables" / "table15_tdc_performance_mode_retained_best.csv"),
        pd.read_csv(root / "reports" / "tdc_performance_mode_appendix_combined" / "selected_metrics_raw.csv"),
        pd.read_csv(root / "reports" / "tdc_full_panel_appendix_benchmark" / "metrics_raw.csv"),
        bootstrap_replicates=bootstrap_replicates,
    )
    curve, metrics = build_risk_coverage_outputs(
        pd.read_csv(root / "reports" / "risk_calibrated_selector" / "compound_risk_predictions.csv")
    )
    paths = {
        "tdc_gate": external / "tdc_gate_audit.csv",
        "tdc_confusion": external / "tdc_gate_confusion_matrix.csv",
        "risk_curve": reliability / "risk_coverage_long.csv",
        "risk_metrics": reliability / "risk_coverage_metrics.csv",
    }
    gate.to_csv(paths["tdc_gate"], index=False)
    confusion.to_csv(paths["tdc_confusion"], index=False)
    curve.to_csv(paths["risk_curve"], index=False)
    metrics.to_csv(paths["risk_metrics"], index=False)
    return paths


def main() -> None:
    for name, path in build_outputs().items():
        print(f"{name}: {path}")
    print(f"conformal: {combine_conformal_outputs()}")


if __name__ == "__main__":
    main()
