from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "results" / "external_panels"
REPEAT_STATUS = ROOT / "results" / "nested_selection" / "repeated_nested" / "run_status.json"


def _wsl_path(path: Path) -> str:
    resolved = path.resolve()
    if not resolved.drive:
        return resolved.as_posix()
    drive = resolved.drive.rstrip(":").lower()
    tail = resolved.as_posix().split(":", 1)[1]
    return f"/mnt/{drive}{tail}"


@dataclass(frozen=True)
class BudgetRun:
    budget: int
    output_dir: Path
    shell_command: str


def build_budget_plan(output_root: Path = DEFAULT_OUTPUT, *, budgets: tuple[int, ...] = (30, 300, 1800)) -> list[BudgetRun]:
    python = "/mnt/d/fzyc/.venv-autogluon/bin/python"
    script = "/mnt/d/fzyc/scripts/run_autogluon_nested_wsl_20260621.py"
    return [
        BudgetRun(
            budget=budget,
            output_dir=output_root / f"autogluon_budget_{budget}",
            shell_command=(
                f"export FZYC_AUTOGLUON_OUT='{_wsl_path(output_root / f'autogluon_budget_{budget}')}'; "
                f"'{python}' '{script}' --time-limit {budget} --seed 20260621"
            ),
        )
        for budget in budgets
    ]


def repeats_complete() -> bool:
    if not REPEAT_STATUS.exists():
        return False
    rows = json.loads(REPEAT_STATUS.read_text(encoding="utf-8"))
    return len(rows) == 5 and all(row["status"] in {"completed", "completed_existing"} for row in rows)


def run_budgets(plan: list[BudgetRun], *, wait_for_repeats: bool = True) -> int:
    while wait_for_repeats and not repeats_complete():
        time.sleep(60)
    status_path = DEFAULT_OUTPUT / "autogluon_budget_status.json"
    log_path = DEFAULT_OUTPUT / "autogluon_budget_runner.log"
    statuses = []
    for item in plan:
        if (item.output_dir / "run_manifest.json").exists():
            statuses.append({"budget": item.budget, "status": "completed_existing", "output_dir": str(item.output_dir)})
            continue
        item.output_dir.mkdir(parents=True, exist_ok=True)
        started = datetime.now(timezone.utc)
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"\nSTART {started.isoformat()} budget={item.budget}\n")
            result = subprocess.run(
                ["wsl.exe", "-d", "Ubuntu-22.04", "--", "bash", "-lc", item.shell_command],
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
        statuses.append(
            {
                "budget": item.budget,
                "status": "completed" if result.returncode == 0 else "failed",
                "returncode": result.returncode,
                "output_dir": str(item.output_dir),
                "started_utc": started.isoformat(),
                "finished_utc": datetime.now(timezone.utc).isoformat(),
            }
        )
        status_path.write_text(json.dumps(statuses, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if all(row["status"] in {"completed", "completed_existing"} for row in statuses) else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--budgets", nargs="+", type=int, default=[30, 300, 1800])
    parser.add_argument("--no-wait", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raise SystemExit(run_budgets(build_budget_plan(budgets=tuple(args.budgets)), wait_for_repeats=not args.no_wait))


if __name__ == "__main__":
    main()
