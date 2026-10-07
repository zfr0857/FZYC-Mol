from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "results" / "final" / "composition_intervention"
OUT = ROOT / "results" / "reproduced_analysis"


def load_module(path: Path, name: str) -> ModuleType:
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
    parser = argparse.ArgumentParser(description="Reproduce checked statistics and manuscript assets.")
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "paper.yaml")
    parser.add_argument("--figures", default="figure7", choices=["figure7", "all"])
    parser.add_argument("--tables", default="none", choices=["none", "all"])
    args = parser.parse_args()
    config_path = args.config.resolve()
    if not config_path.is_file():
        raise FileNotFoundError(config_path)
    yaml.safe_load(config_path.read_text(encoding="utf-8"))

    required = [
        "endpoint_pool_K_summary.csv",
        "selection_units.csv",
        "selection_stability.csv",
        "equal_budget_units.csv",
    ]
    missing = [name for name in required if not (EXPORTS / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing canonical result files: {missing}")

    summary = pd.read_csv(EXPORTS / required[0])
    modern = summary.loc[
        summary.design.eq("equal_K")
        & summary.anchor_scheme.eq("shared_morgan_linear")
        & summary.pool.eq("Modern-augmented")
        & summary.candidate_count.eq(32)
    ]
    by_task = modern.groupby("task", as_index=False)["homogeneous_normalized_selected_gain_mean"].mean()
    positive = int(by_task.homogeneous_normalized_selected_gain_mean.gt(0).sum())

    figure = load_module(ROOT / "scripts" / "build_final_figure7.py", "final_figure7")
    figure.OUT = OUT / "figures"
    figure.main()

    rendered = OUT / "figures" / "Figure7.svg"
    report = {
        "package_version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        "source_rows": {name: int(len(pd.read_csv(EXPORTS / name))) for name in required},
        "composition_endpoints": int(by_task.task.nunique()),
        "modern_K32_positive_endpoints": positive,
        "figure7_svg_sha256": sha256(rendered),
        "status": "pass" if int(by_task.task.nunique()) == 6 and positive == 6 else "fail",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "quick_reproduction_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    if args.figures == "all" or args.tables == "all":
        print("Canonical reference assets remain in results/final/ and source_data/.")
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
