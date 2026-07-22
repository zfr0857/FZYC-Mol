from __future__ import annotations

import pandas as pd


def audit_tdc_gate(frame: pd.DataFrame) -> pd.DataFrame:
    """Classify every promoted and retained endpoint using outer-test evidence."""

    required = {"endpoint", "promoted", "test_delta", "ci_low", "ci_high"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"missing gate columns: {sorted(missing)}")
    output = frame.copy()

    def category(row: pd.Series) -> str:
        if float(row["ci_low"]) <= 0 <= float(row["ci_high"]):
            return "inconclusive_due_to_wide_ci"
        if bool(row["promoted"]):
            return "promoted_and_improved" if float(row["test_delta"]) > 0 else "promoted_but_harmed"
        return "retained_but_candidate_would_improve" if float(row["test_delta"]) > 0 else "retained_and_avoided_harm"

    output["gate_category"] = output.apply(category, axis=1)
    return output
