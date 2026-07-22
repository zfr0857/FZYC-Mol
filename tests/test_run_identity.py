from __future__ import annotations

from fzyc_mol.data.run_identity import build_run_id


def test_same_inputs_have_same_run_id() -> None:
    first = build_run_id(config={"model": "rf", "depth": 5}, data_hash="d", split_hash="s", seed=13, code_hash="c", prediction_hash="p")
    second = build_run_id(config={"depth": 5, "model": "rf"}, data_hash="d", split_hash="s", seed=13, code_hash="c", prediction_hash="p")

    assert first == second


def test_same_metric_but_different_predictions_are_not_duplicates() -> None:
    first = build_run_id(config={"model": "rf"}, data_hash="d", split_hash="s", seed=13, code_hash="c", prediction_hash="p1")
    second = build_run_id(config={"model": "rf"}, data_hash="d", split_hash="s", seed=13, code_hash="c", prediction_hash="p2")

    assert first != second
