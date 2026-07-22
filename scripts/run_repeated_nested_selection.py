from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "results" / "nested_selection" / "repeated_nested"
NESTED_SCRIPT = ROOT / "scripts" / "run_expanded_nested_candidate_pool_20260621.py"


@dataclass(frozen=True)
class RunSpec:
    seed: int
    output_dir: Path
    log_path: Path
    command: tuple[str, ...]


def build_run_plan(output_root: Path = DEFAULT_OUTPUT, *, seeds: tuple[int, ...] = (11, 23, 37, 53, 71)) -> list[RunSpec]:
    plan = []
    for seed in seeds:
        output_dir = output_root / f"seed_{seed}"
        plan.append(
            RunSpec(
                seed=seed,
                output_dir=output_dir,
                log_path=output_root / "logs" / f"seed_{seed}.log",
                command=(
                    sys.executable,
                    str(NESTED_SCRIPT),
                    "--seed",
                    str(seed),
                    "--outer-folds",
                    "3",
                    "--inner-folds",
                    "3",
                    "--max-candidates",
                    "32",
                ),
            )
        )
    return plan


def run_plan(plan: list[RunSpec], output_root: Path = DEFAULT_OUTPUT) -> int:
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "logs").mkdir(parents=True, exist_ok=True)
    statuses: list[dict[str, object]] = []
    for spec in plan:
        if (spec.output_dir / "run_manifest.json").exists():
            statuses.append({"seed": spec.seed, "status": "completed_existing", "output_dir": str(spec.output_dir)})
            continue
        spec.output_dir.mkdir(parents=True, exist_ok=True)
        environment = os.environ.copy()
        environment["FZYC_NESTED_OUT"] = str(spec.output_dir)
        started = datetime.now(timezone.utc)
        with spec.log_path.open("a", encoding="utf-8") as log:
            log.write(f"\nSTART {started.isoformat()} {' '.join(spec.command)}\n")
            result = subprocess.run(spec.command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, check=False)
        status = "completed" if result.returncode == 0 else "failed"
        statuses.append(
            {
                "seed": spec.seed,
                "status": status,
                "returncode": result.returncode,
                "output_dir": str(spec.output_dir),
                "log_path": str(spec.log_path),
                "started_utc": started.isoformat(),
                "finished_utc": datetime.now(timezone.utc).isoformat(),
                "command": list(spec.command),
            }
        )
        (output_root / "run_status.json").write_text(json.dumps(statuses, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if all(item["status"] in {"completed", "completed_existing"} for item in statuses) else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", nargs="+", type=int, default=[11, 23, 37, 53, 71])
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raise SystemExit(run_plan(build_run_plan(args.output_root, seeds=tuple(args.seeds)), args.output_root))


if __name__ == "__main__":
    main()
