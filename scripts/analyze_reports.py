from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.analysis import analyze_report_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze prediction reports for paper figures.")
    parser.add_argument("--report-dir", default=str(ROOT / "reports" / "smoke"))
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--split", default="scaffold")
    parser.add_argument("--max-rows", type=int, default=None)
    args = parser.parse_args()

    applicability, gates = analyze_report_dir(
        report_dir=args.report_dir,
        data_dir=args.data_dir,
        split_name=args.split,
        max_rows=args.max_rows,
    )
    print(f"applicability rows: {len(applicability)}")
    print(f"gate rows: {len(gates)}")


if __name__ == "__main__":
    main()
