from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from fzyc_mol.benchmarks.tdc_gate import audit_tdc_gate
from fzyc_mol.reliability.risk_coverage import risk_coverage_audit


def build_tdc_gate_outputs(
    retained_summary: pd.DataFrame,
    performance_raw: pd.DataFrame,
    baseline_raw: pd.DataFrame,
    *,
    bootstrap_replicates: int = 5000,
    seed: int = 20260622,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build a paired-seed TDC gate audit for promoted and retained endpoints."""

    meta = retained_summary[["dataset", "previous_model", "primary_direction", "retained_source"]].copy()
    baseline = baseline_raw.merge(
        meta[["dataset", "previous_model"]],
        left_on=["dataset", "model"],
        right_on=["dataset", "previous_model"],
        how="inner",
    )[["dataset", "seed", "primary_value"]].rename(columns={"primary_value": "baseline_value"})
    performance = performance_raw[["dataset", "seed", "primary_value"]].rename(columns={"primary_value": "candidate_value"})
    paired = performance.merge(baseline, on=["dataset", "seed"], how="inner").merge(meta, on="dataset", how="left")
    paired["positive_delta"] = np.where(
        paired["primary_direction"].eq("higher"),
        paired["candidate_value"] - paired["baseline_value"],
        paired["baseline_value"] - paired["candidate_value"],
    )
    rng = np.random.default_rng(seed)
    rows = []
    for dataset, group in paired.groupby("dataset", sort=True):
        deltas = group["positive_delta"].to_numpy(dtype=float)
        boot = rng.choice(deltas, size=(bootstrap_replicates, len(deltas)), replace=True).mean(axis=1)
        info = group.iloc[0]
        rows.append(
            {
                "endpoint": dataset,
                "promoted": info["retained_source"] == "performance_mode",
                "n_paired_seeds": len(deltas),
                "test_delta": float(np.mean(deltas)),
                "test_delta_sd": float(np.std(deltas, ddof=1)) if len(deltas) > 1 else 0.0,
                "ci_low": float(np.quantile(boot, 0.025)),
                "ci_high": float(np.quantile(boot, 0.975)),
                "seed_win_count": int(np.sum(deltas > 0)),
                "seed_tie_count": int(np.sum(deltas == 0)),
                "seed_loss_count": int(np.sum(deltas < 0)),
                "previous_model": info["previous_model"],
                "primary_direction": info["primary_direction"],
            }
        )
    audit = audit_tdc_gate(pd.DataFrame(rows))
    confusion = audit.groupby(["promoted", "gate_category"], as_index=False).size().rename(columns={"size": "count"})
    return audit, confusion


def build_risk_coverage_outputs(
    predictions: pd.DataFrame,
    *,
    coverages: Sequence[float] = tuple(np.linspace(0.1, 1.0, 19)),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rebuild corrected per-endpoint/per-seed risk curves from sample predictions."""

    required = {"source", "dataset", "seed", "y_true", "y_pred_calibrated", "risk_score"}
    missing = required - set(predictions.columns)
    if missing:
        raise ValueError(f"missing risk columns: {sorted(missing)}")
    curve_rows: list[dict[str, object]] = []
    metric_rows: list[dict[str, object]] = []
    for keys, group in predictions.groupby(["source", "dataset", "seed"], sort=True):
        source, dataset, seed = keys
        values = set(group["y_true"].dropna().unique())
        probability_like = group["y_pred_calibrated"].between(0.0, 1.0).all()
        task_type = "classification" if values.issubset({0, 1, 0.0, 1.0}) and probability_like else "regression"
        audit = risk_coverage_audit(
            group["y_true"],
            group["y_pred_calibrated"],
            group["risk_score"],
            task_type=task_type,
            coverages=coverages,
        )
        metadata = {"source": source, "endpoint": dataset, "seed": int(seed), "task_type": task_type, "n": len(group)}
        curve_rows.extend({**metadata, **row} for row in audit.curve.to_dict(orient="records"))
        metric_rows.append(
            {
                **metadata,
                "aurc": audit.aurc,
                "oracle_lower_bound_aurc": audit.oracle_aurc,
                "e_aurc": audit.e_aurc,
                "random_baseline_risk": audit.random_baseline_risk,
            }
        )
    return pd.DataFrame(curve_rows), pd.DataFrame(metric_rows)
