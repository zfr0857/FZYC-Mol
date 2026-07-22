from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fzyc_mol.reporting.stage_c import build_stage_c_outputs  # noqa: E402


def build_outputs(
    root: Path = ROOT,
    *,
    modes: Sequence[str] = ("random_order", "random_subset", "family_balanced"),
    pool_sizes: Sequence[int] = (4, 8, 16, 32),
    seeds: Sequence[int] = tuple(range(100)),
) -> dict[str, Path]:
    source = root / "reports" / "draft10_core_experiments_20260621" / "expanded_nested"
    output = root / "results" / "candidate_pool"
    output.mkdir(parents=True, exist_ok=True)
    manifest, ranking, regret, decisions = build_stage_c_outputs(
        pd.read_csv(source / "inner_scores.csv"),
        pd.read_csv(source / "outer_candidate_scores.csv"),
        pd.read_csv(source / "candidate_registry.csv"),
        modes=modes,
        pool_sizes=pool_sizes,
        seeds=seeds,
    )
    paths = {
        "manifest": output / "subset_manifest.csv",
        "ranking": output / "subset_ranking_metrics_long.csv",
        "regret": output / "subset_regret_long.csv",
        "decisions": output / "subset_selection_reason.csv",
    }
    manifest.to_csv(paths["manifest"], index=False)
    ranking.to_csv(paths["ranking"], index=False)
    regret.to_csv(paths["regret"], index=False)
    decisions.to_csv(paths["decisions"], index=False)
    return paths


def main() -> None:
    for name, path in build_outputs().items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
