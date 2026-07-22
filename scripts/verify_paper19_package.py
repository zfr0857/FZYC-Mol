from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    package_root = Path(__file__).resolve().parents[1]
    manifest = package_root / "manifests" / "PACKAGE_CONTENTS.csv"
    if not manifest.exists():
        print(f"Missing manifest: {manifest}")
        return 2

    missing: list[str] = []
    mismatched: list[str] = []
    checked = 0
    with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rel = row["relative_path"]
            path = package_root / Path(rel)
            if not path.exists():
                missing.append(rel)
                continue
            checked += 1
            if sha256(path) != row["sha256"]:
                mismatched.append(rel)

    print(
        {
            "checked": checked,
            "missing": len(missing),
            "mismatched": len(mismatched),
            "passed": not missing and not mismatched,
        }
    )
    if missing:
        print("Missing files:")
        print("\n".join(missing[:20]))
    if mismatched:
        print("Hash mismatches:")
        print("\n".join(mismatched[:20]))
    return 0 if not missing and not mismatched else 1


if __name__ == "__main__":
    sys.exit(main())
