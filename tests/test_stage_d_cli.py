from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.run_reliability_audit import build_outputs, combine_conformal_outputs


def test_stage_d_cli_writes_gate_and_risk_outputs(tmp_path: Path) -> None:
    tables = tmp_path / "reports" / "manuscript_tables"
    performance_dir = tmp_path / "reports" / "tdc_performance_mode_appendix_combined"
    baseline_dir = tmp_path / "reports" / "tdc_full_panel_appendix_benchmark"
    risk_dir = tmp_path / "reports" / "risk_calibrated_selector"
    for path in (tables, performance_dir, baseline_dir, risk_dir):
        path.mkdir(parents=True)
    pd.DataFrame(
        {"dataset": ["a"], "previous_model": ["base"], "primary_direction": ["higher"], "retained_source": ["performance_mode"]}
    ).to_csv(tables / "table15_tdc_performance_mode_retained_best.csv", index=False)
    pd.DataFrame({"dataset": ["a", "a"], "seed": [1, 2], "primary_value": [0.8, 0.9]}).to_csv(
        performance_dir / "selected_metrics_raw.csv", index=False
    )
    pd.DataFrame(
        {"dataset": ["a", "a"], "seed": [1, 2], "model": ["base", "base"], "primary_value": [0.7, 0.8]}
    ).to_csv(baseline_dir / "metrics_raw.csv", index=False)
    pd.DataFrame(
        {
            "source": ["x"] * 4,
            "dataset": ["demo"] * 4,
            "seed": [1] * 4,
            "y_true": [0, 0, 0, 0],
            "y_pred_calibrated": [0, 1, 2, 3],
            "risk_score": [0, 1, 2, 3],
        }
    ).to_csv(risk_dir / "compound_risk_predictions.csv", index=False)

    paths = build_outputs(tmp_path, bootstrap_replicates=100)

    assert all(path.exists() for path in paths.values())
    assert len(pd.read_csv(paths["tdc_gate"])) == 1


def test_combines_corrected_conformal_levels(tmp_path: Path) -> None:
    root = tmp_path / "results" / "reliability"
    for suffix, alpha in [("020", 0.2), ("010", 0.1), ("005", 0.05)]:
        folder = root / f"conformal_alpha_{suffix}"
        folder.mkdir(parents=True)
        pd.DataFrame({"dataset": ["demo"], "task_type": ["regression"], "alpha": [alpha], "coverage": [1 - alpha]}).to_csv(
            folder / "conformal_summary.csv", index=False
        )

    output = combine_conformal_outputs(tmp_path)
    combined = pd.read_csv(output)

    assert len(combined) == 3
    assert list(combined["target_coverage"]) == [0.8, 0.9, 0.95]
