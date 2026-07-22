from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.build_autogluon_budget_outputs import build_outputs


def test_combines_all_autogluon_budgets(tmp_path: Path) -> None:
    external = tmp_path / "results" / "external_panels"
    expanded = tmp_path / "reports" / "draft10_core_experiments_20260621" / "expanded_nested"
    expanded.mkdir(parents=True)
    policies = ["fixed_single", "validation_best", "one_se_stable", "risk_adjusted"]
    pd.DataFrame(
        [
            {
                "dataset": "demo",
                "outer_fold": fold,
                "pool_size": 32,
                "policy": policy,
                "outer_utility": 0.7 + 0.01 * index,
            }
            for fold in (1, 2)
            for index, policy in enumerate(policies)
        ]
    ).to_csv(expanded / "policy_detail.csv", index=False)
    for budget, folder in [(30, external / "autogluon_budget_30"), (300, external / "autogluon_budget_300"), (1800, external / "autogluon_budget_1800")]:
        folder.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"dataset": ["demo"], "task_type": ["classification"], "primary_mean": [0.8], "fit_seconds_mean": [budget / 10]}).to_csv(folder / "summary.csv", index=False)
        pd.DataFrame({"dataset": ["demo", "demo"], "outer_fold": [1, 2], "best_model": ["A", "B"], "fit_seconds": [1, 2], "model_count": [4, 4], "peak_rss_mb": [512, 520], "outer_utility": [0.8, 0.8]}).to_csv(folder / "outer_results.csv", index=False)

    paths = build_outputs(tmp_path)
    summary = pd.read_csv(paths["summary"])

    assert set(summary["budget_seconds"]) == {30, 300, 1800}
    assert "model_selection_entropy" in summary
    assert "peak_rss_mb_max" in summary
    assert "delta_vs_validation_best" in summary
