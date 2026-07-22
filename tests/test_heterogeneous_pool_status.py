from __future__ import annotations

from scripts.build_heterogeneous_pool_status import build_status_rows


def test_historical_predictions_without_frozen_outer_splits_are_not_promoted() -> None:
    rows = build_status_rows(available_artifacts={"chemberta_frozen_head"})
    chemberta = next(row for row in rows if row["candidate_id"] == "chemberta_frozen_head")

    assert chemberta["artifact_available"] is True
    assert chemberta["outer_split_compatible"] is False
    assert chemberta["status"] == "not_completed"
    assert chemberta["test_utility"] is None
