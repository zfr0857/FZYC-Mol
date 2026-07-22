from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results" / "paper31_expanded_intervention_20260717"
TASKS = ["bbbp", "lipo", "tdc_caco2_wang"]
SEEDS = [11, 23, 37, 53, 71]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["new-candidates", "chemprop-inner", "chemprop-outer"])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "scripts"))
    common = ["paper31", "--tasks", *TASKS, "--seeds", *map(str, SEEDS), "--outer-folds", "3", "--inner-folds", "3"]
    if args.force:
        common.append("--force")
    if args.stage == "new-candidates":
        import run_equal_size_registry_composition_20260716 as module
        module.OUT = RESULTS / "new_candidates"
    elif args.stage == "chemprop-inner":
        import run_paper12_chemprop_inner_panel as module
        module.OUT = RESULTS / "chemprop"
        module.WORK = RESULTS / "chemprop_inner_work"
        common += ["--epochs", "1", "--batch-size", "512"]
    else:
        import run_paper12_chemprop_outer_panel as module
        module.OUT = RESULTS / "chemprop"
        module.WORK = RESULTS / "chemprop_outer_work"
        common += ["--epochs", "1", "--batch-size", "256"]
    sys.argv = common
    module.main()


if __name__ == "__main__":
    main()
