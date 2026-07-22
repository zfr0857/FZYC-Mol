from __future__ import annotations

from pathlib import Path

from scripts.run_autogluon_budgets import build_budget_plan


def test_budget_plan_contains_required_300_and_1800_second_runs(tmp_path: Path) -> None:
    plan = build_budget_plan(tmp_path, budgets=(300, 1800))

    assert [item.budget for item in plan] == [300, 1800]
    assert all("FZYC_AUTOGLUON_OUT" in item.shell_command for item in plan)
    assert all(f"--time-limit {item.budget}" in item.shell_command for item in plan)
