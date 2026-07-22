from __future__ import annotations

from pathlib import Path


def test_autogluon_runner_uses_environment_scoped_output() -> None:
    script = (Path(__file__).resolve().parents[1] / "scripts" / "run_autogluon_nested_wsl_20260621.py").read_text(encoding="utf-8")

    assert "FZYC_AUTOGLUON_OUT" in script
    assert "os.environ.get" in script


def test_autogluon_runner_records_required_cost_fields() -> None:
    script = (Path(__file__).resolve().parents[1] / "scripts" / "run_autogluon_nested_wsl_20260621.py").read_text(encoding="utf-8")

    assert '"model_count"' in script
    assert '"peak_rss_mb"' in script
