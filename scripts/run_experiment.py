from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.train import run_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FZYC-Mol benchmark experiments.")
    parser.add_argument("--config", default=str(ROOT / "configs" / "smoke.json"))
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    args = parser.parse_args()

    config_path = Path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    metrics = run_config(config, data_dir=args.data_dir)
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
