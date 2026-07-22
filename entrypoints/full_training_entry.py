from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["new-candidates", "chemprop-inner", "chemprop-outer"])
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    scripts = workspace / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    for source in (PACKAGE / "scripts_current").iterdir():
        if source.is_file() and source.suffix.lower() in {".py", ".ps1"}:
            shutil.copy2(source, scripts / source.name)
    if (PACKAGE / "configs_current").exists():
        shutil.copytree(PACKAGE / "configs_current", workspace / "configs", dirs_exist_ok=True)

    data_dir = workspace / "data"
    if not data_dir.exists():
        raise FileNotFoundError(
            f"{data_dir} is absent. Run the packaged download and cleaning scripts after reviewing source licences."
        )

    driver_path = PACKAGE / "paper31_expanded_intervention" / "reproducibility_code" / "run_paper31_expansion_training_20260717.py"
    spec = importlib.util.spec_from_file_location("paper31_training_driver", driver_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load training driver from {driver_path}")
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    setattr(driver, "ROOT", workspace)
    setattr(driver, "RESULTS", workspace / "results" / "paper31_expanded_intervention_20260717")
    sys.argv = [str(driver_path), args.stage] + (["--force"] if args.force else [])
    driver.main()


if __name__ == "__main__":
    main()
