from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGES = ("splits", "main-audit", "composition", "chemprop-inner", "chemprop-outer")


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def materialize_splits(output: Path) -> None:
    source = ROOT / "paper34_audit_sources" / "split_manifests"
    output.mkdir(parents=True, exist_ok=True)
    for path in source.glob("*.csv"):
        shutil.copy2(path, output / path.name)


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
            materialize_splits(ROOT / config["outputs"]["splits"])
        elif stage == "main-audit":
            command = [
                python,
                str(ROOT / "scripts" / "run_shared_split_multiview_nested_20260624.py"),
                "--tasks",
                *config["primary_endpoints"],
                "--seeds",
                *map(str, config["seeds"]),
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
                str(ROOT / "scripts_current" / "run_equal_size_registry_composition_20260716.py"),
                "--tasks",
                "clintox",
                "bace",
                "esol",
                "--seeds",
                *map(str, config["seeds"]),
                "--outer-folds",
                str(config["outer_folds"]),
                "--inner-folds",
                str(config["inner_folds"]),
            ]
            if args.force:
                initial.append("--force")
            run(initial)
            command = [python, str(ROOT / "entrypoints" / "full_training_entry.py"),
                       "new-candidates", "--workspace", str(args.workspace)]
            if args.force:
                command.append("--force")
            run(command)
        else:
            command = [python, str(ROOT / "entrypoints" / "full_training_entry.py"),
                       stage, "--workspace", str(args.workspace)]
            if args.force:
                command.append("--force")
            run(command)


if __name__ == "__main__":
    main()
