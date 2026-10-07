from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGES = ("splits", "main-audit", "composition", "chemprop-inner", "chemprop-outer")


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def validate_splits(directory: Path) -> None:
    required = {"composition_split_units.csv", "similarity_split_manifest.csv"}
    missing = sorted(name for name in required if not (directory / name).is_file())
    if missing:
        raise FileNotFoundError(f"Missing locked split manifests in {directory}: {missing}")
    nested = list((directory / "ten_seed_audit").rglob("split_manifest.csv"))
    if len(nested) != 105:
        raise RuntimeError(f"Expected 105 locked nested-CV split manifests, found {len(nested)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the locked manuscript study stages.")
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "paper.yaml")
    parser.add_argument("--stage", choices=STAGES)
    parser.add_argument("--workspace", type=Path, default=ROOT)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    stages = [args.stage] if args.stage else list(STAGES)
    python = sys.executable

    for stage in stages:
        if stage == "splits":
            validate_splits(ROOT / config["outputs"]["splits"])
        elif stage == "main-audit":
            command = [
                python,
                str(ROOT / "scripts" / "run_nested_multiview_audit.py"),
                "--tasks",
                *config["primary_endpoints"],
                "--seeds",
                *map(str, config["primary_seeds"]),
                "--outer-folds",
                str(config["outer_folds"]),
                "--inner-folds",
                str(config["inner_folds"]),
            ]
            if args.force:
                command.append("--force")
            run(command)
        elif stage == "composition":
            initial = [
                python,
                str(ROOT / "scripts" / "run_equal_size_registry_composition.py"),
                "--tasks",
                "clintox",
                "bace",
                "esol",
                "--seeds",
                *map(str, config["composition_seeds"]),
                "--outer-folds",
                str(config["outer_folds"]),
                "--inner-folds",
                str(config["inner_folds"]),
            ]
            if args.force:
                initial.append("--force")
            run(initial)
            command = [python, str(ROOT / "scripts" / "run_expanded_intervention.py"), "new-candidates"]
            if args.force:
                command.append("--force")
            run(command)
        else:
            command = [python, str(ROOT / "scripts" / "run_expanded_intervention.py"), stage]
            if args.force:
                command.append("--force")
            run(command)


if __name__ == "__main__":
    main()
