from __future__ import annotations

import pandas as pd

from fzyc_mol.benchmarks.tdc_gate import audit_tdc_gate


def test_gate_audit_keeps_retained_candidates_as_real_outcomes() -> None:
    frame = pd.DataFrame(
        {
            "endpoint": ["a", "b", "c", "d", "e"],
            "promoted": [True, True, False, False, False],
            "test_delta": [0.1, -0.1, 0.2, -0.2, 0.01],
            "ci_low": [0.05, -0.2, 0.1, -0.3, -0.1],
            "ci_high": [0.2, -0.01, 0.3, -0.1, 0.1],
        }
    )

    audit = audit_tdc_gate(frame)

    assert audit.set_index("endpoint")["gate_category"].to_dict() == {
        "a": "promoted_and_improved",
        "b": "promoted_but_harmed",
        "c": "retained_but_candidate_would_improve",
        "d": "retained_and_avoided_harm",
        "e": "inconclusive_due_to_wide_ci",
    }
