from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_expanded_nested_candidate_pool_20260621.py"
DEFAULT_OUT = ROOT / "results" / "split_regime_transfer_20260716" / "similarity_cluster"
DEFAULT_TASKS = ("clintox", "bace", "esol")
DEFAULT_SEEDS = (11, 23, 37, 53, 71)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", nargs="+", default=list(DEFAULT_TASKS))
    parser.add_argument("--seeds", nargs="+", type=int, default=list(DEFAULT_SEEDS))
    parser.add_argument("--threshold", type=float, default=0.70)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    log_dir = args.output_root / "logs"
    log_dir.mkdir(exist_ok=True)
    statuses = []
    for seed in args.seeds:
        destination = args.output_root / f"seed_{seed}"
        command = [
            sys.executable, str(RUNNER), "--tasks", *args.tasks,
            "--seed", str(seed), "--outer-folds", "3", "--inner-folds", "3",
            "--max-candidates", "32", "--split-regime", "similarity_cluster",
            "--similarity-threshold", str(args.threshold),
        ]
        started = datetime.now(timezone.utc)
        environment = os.environ.copy()
        environment["FZYC_NESTED_OUT"] = str(destination)
        with (log_dir / f"seed_{seed}.log").open("a", encoding="utf-8") as log:
            log.write(f"\nSTART {started.isoformat()} {' '.join(command)}\n")
            result = subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
        statuses.append({
            "seed": seed,
            "status": "completed" if result.returncode == 0 else "failed",
            "returncode": result.returncode,
            "output_dir": str(destination),
            "started_utc": started.isoformat(),
            "finished_utc": datetime.now(timezone.utc).isoformat(),
            "command": command,
        })
        (args.output_root / "run_status.json").write_text(
            json.dumps(statuses, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"seed {seed}: {statuses[-1]['status']}", flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
