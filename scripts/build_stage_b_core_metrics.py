from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fzyc_mol.reporting.stage_b import build_stage_b_outputs  # noqa: E402


def build_outputs(root: Path = ROOT, *, pool_sizes: Sequence[int] = (4, 8, 16, 32)) -> dict[str, Path]:
    source = root / "reports" / "draft10_core_experiments_20260621" / "expanded_nested"
    ranking_dir = root / "results" / "candidate_pool"
    nested_dir = root / "results" / "nested_selection"
    ranking_dir.mkdir(parents=True, exist_ok=True)
    nested_dir.mkdir(parents=True, exist_ok=True)

    ranking, regret, decisions = build_stage_b_outputs(
        pd.read_csv(source / "inner_scores.csv"),
        pd.read_csv(source / "outer_candidate_scores.csv"),
        pd.read_csv(source / "candidate_registry.csv"),
        pool_sizes=pool_sizes,
    )
    paths = {
        "ranking": ranking_dir / "ranking_metrics_long.csv",
        "regret": nested_dir / "regret_decomposition.csv",
        "decisions": nested_dir / "selection_reason.csv",
    }
    ranking.to_csv(paths["ranking"], index=False)
    regret.to_csv(paths["regret"], index=False)
    decisions.to_csv(paths["decisions"], index=False)
    return paths


def main() -> None:
    for name, path in build_outputs().items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
