from __future__ import annotations

import csv
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", "__pycache__"}
EXCLUDED_FILES = {"CODE_AND_DATA_CONTENTS.csv", "SHA256SUMS.txt"}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    files = [
        path for path in ROOT.rglob("*")
        if path.is_file()
        and not EXCLUDED_PARTS.intersection(path.relative_to(ROOT).parts)
        and path.name not in EXCLUDED_FILES
        and path.suffix.lower() != ".pyc"
    ]
    rows = [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": digest(path),
        }
        for path in sorted(files, key=lambda item: item.relative_to(ROOT).as_posix())
    ]
    with (ROOT / "CODE_AND_DATA_CONTENTS.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "size_bytes", "sha256"])
        writer.writeheader()
        writer.writerows(rows)
    (ROOT / "SHA256SUMS.txt").write_text(
        "".join(f"{row['sha256']}  {row['path']}\n" for row in rows), encoding="utf-8"
    )
    print(f"inventory_files={len(rows)}")


if __name__ == "__main__":
    main()
