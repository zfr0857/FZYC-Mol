from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproduce checked statistics and manuscript assets.")
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "paper.yaml")
    parser.add_argument("--figures", default="figure7", choices=["figure7", "all"])
    parser.add_argument("--tables", default="none", choices=["none", "all"])
    args = parser.parse_args()
    if not args.config.resolve().is_file():
        raise FileNotFoundError(args.config)

    sys.path.insert(0, str(ROOT))
    from entrypoints.quick_reproduce import main as reproduce

    reproduce()
    if args.figures == "all" or args.tables == "all":
        print("Checked source-data assets are available in source_data/ and reproduced_outputs/.")


if __name__ == "__main__":
    main()
