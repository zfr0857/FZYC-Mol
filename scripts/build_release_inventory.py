from __future__ import annotations

import csv
import hashlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", "__pycache__"}
EXCLUDED_FILES = {"CODE_AND_DATA_CONTENTS.csv", "SHA256SUMS.txt"}
TEXT_SUFFIXES = {
    ".cff", ".csv", ".ini", ".json", ".md", ".ps1", ".py", ".toml", ".tsv",
    ".txt", ".yaml", ".yml",
}
TEXT_NAMES = {".dockerignore", ".gitignore", "Dockerfile", "LICENSE", "PKG-INFO", "VERSION", "wslconfig.autogluon"}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_NAMES:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    value.update(data)
    return value.hexdigest()


def main() -> None:
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode("utf-8").split("\0")
    files = [
        ROOT / relative for relative in tracked
        if relative
        and Path(relative).name not in EXCLUDED_FILES
        and not EXCLUDED_PARTS.intersection(Path(relative).parts)
        and Path(relative).suffix.lower() != ".pyc"
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
