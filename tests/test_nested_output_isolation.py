from __future__ import annotations

import importlib.util
from pathlib import Path


def test_nested_runner_honors_isolated_output_directory(monkeypatch, tmp_path: Path) -> None:
    requested = tmp_path / "repeat_seed_11"
    monkeypatch.setenv("FZYC_NESTED_OUT", str(requested))
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_expanded_nested_candidate_pool_20260621.py"
    spec = importlib.util.spec_from_file_location("isolated_nested_runner", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.OUT == requested
    assert module.TASK_DIR == requested / "tasks"
