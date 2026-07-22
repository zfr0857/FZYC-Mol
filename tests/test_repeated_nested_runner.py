from __future__ import annotations

from pathlib import Path

from scripts.run_repeated_nested_selection import build_run_plan


def test_run_plan_uses_five_frozen_seeds_and_isolated_outputs(tmp_path: Path) -> None:
    plan = build_run_plan(tmp_path, seeds=(11, 23, 37, 53, 71))

    assert [item.seed for item in plan] == [11, 23, 37, 53, 71]
    assert len({item.output_dir for item in plan}) == 5
    assert all(item.output_dir.name == f"seed_{item.seed}" for item in plan)
    assert all("--max-candidates" in item.command for item in plan)
