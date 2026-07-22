from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "paper31_expanded_intervention" / "experiment_exports"
OUT = ROOT / "reproduced_outputs"


def load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module {name!r} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    required = [
        "Paper31_endpoint_pool_K_summary.csv",
        "Paper31_selection_units.csv",
        "Paper31_selection_stability.csv",
        "Paper31_equal_budget_units.csv",
    ]
    missing = [name for name in required if not (EXPORTS / name).exists()]
    if missing:
        raise FileNotFoundError(missing)

    summary = pd.read_csv(EXPORTS / required[0])
    modern = summary.loc[
        summary.design.eq("equal_K")
        & summary.anchor_scheme.eq("shared_morgan_linear")
        & summary.pool.eq("Modern-augmented")
        & summary.candidate_count.eq(32)
    ]
    by_task = modern.groupby("task", as_index=False)["homogeneous_normalized_selected_gain_mean"].mean()
    positive = int((by_task.homogeneous_normalized_selected_gain_mean > 0).sum())

    base = load(
        ROOT / "paper31_expanded_intervention" / "reproducibility_code" / "build_paper31_figures_20260717.py",
        "paper31_figures_portable",
    )
    setattr(base, "DATA", EXPORTS)
    figure = load(
        ROOT / "manuscript_finalization" / "build_paper32_figure7_large_text_20260718.py",
        "paper34_figure7_portable",
    )
    setattr(figure, "OUT", OUT / "main_figures")
    setattr(figure, "load_base", lambda: base)
    figure.main()

    report = {
        "package_version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        "source_rows": {name: int(len(pd.read_csv(EXPORTS / name))) for name in required},
        "composition_endpoints": int(by_task.task.nunique()),
        "modern_K32_positive_endpoints": positive,
        "figure7_svg_sha256": sha256(OUT / "main_figures" / "Figure7.svg"),
        "status": "pass" if int(by_task.task.nunique()) == 6 and positive == 6 else "fail",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "quick_reproduction_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
