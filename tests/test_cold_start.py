from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.run_cold_start import run_cold_start


def test_cold_start_rebuilds_endpoint_audit_risk_and_figure(tmp_path: Path) -> None:
    paths = run_cold_start(tmp_path, max_rows=120, seed=11)

    assert all(path.exists() for path in paths.values())
    audit = pd.read_csv(paths["candidate_audit"])
    assert audit.iloc[0]["endpoint"] == "esol"
    assert audit.iloc[0]["status"] == "completed"
