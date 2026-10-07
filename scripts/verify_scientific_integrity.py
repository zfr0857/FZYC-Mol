from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {".git", ".pytest_cache", ".ruff_cache", ".mypy_cache", "__pycache__"}
POST_PREFIXES = (
    "manifests/",
    "splits/",
    "results/final/",
    "source_data/",
    "docs/Equation_to_code_mapping.csv",
)
PRE_PREFIXES = POST_PREFIXES
CONFIG_PATHS = {
    "configs/paper.yaml",
    "configs/candidate_registry.yaml",
    "configs/endpoints.yaml",
    "configs/data_cleaning.yaml",
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def category(relative: str) -> str:
    if relative in CONFIG_PATHS:
        return "config"
    if relative.startswith("splits/") or "/split_manifest" in relative or "/split_manifests/" in relative:
        return "split"
    if relative.startswith("source_data/") or "/source_data/" in relative or "/figure_source_data/" in relative:
        return "source_data"
    if relative.startswith("manifests/"):
        return "provenance"
    return "result"


def repository_files() -> list[Path]:
    return sorted(
        (
            path
            for path in ROOT.rglob("*")
            if path.is_file()
            and not EXCLUDED_PARTS.intersection(path.relative_to(ROOT).parts)
            and path.suffix.lower() != ".pyc"
        ),
        key=lambda item: item.relative_to(ROOT).as_posix(),
    )


def selected(path: Path, phase: str) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    prefixes = PRE_PREFIXES if phase == "pre" else POST_PREFIXES
    return relative in CONFIG_PATHS or relative.startswith(prefixes)


def snapshot(output: Path, phase: str) -> None:
    rows = []
    for path in repository_files():
        if selected(path, phase):
            relative = path.relative_to(ROOT).as_posix()
            rows.append(
                {
                    "category": category(relative),
                    "relative_path": relative,
                    "size_bytes": path.stat().st_size,
                    "sha256": digest(path),
                }
            )
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["category", "relative_path", "size_bytes", "sha256"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"snapshot={output.name} files={len(rows)}")


def compare(before: Path, after: Path) -> None:
    with before.open(encoding="utf-8", newline="") as handle:
        pre = list(csv.DictReader(handle))
    with after.open(encoding="utf-8", newline="") as handle:
        post = list(csv.DictReader(handle))
    final_hashes = {row["sha256"] for row in post}
    protected = [
        row
        for row in pre
        if row["category"] != "config"
        and not row["relative_path"].lower().endswith(("readme.md", ".md"))
        and not Path(row["relative_path"]).name.startswith("PACKAGE_")
    ]
    missing = [row for row in protected if row["sha256"] not in final_hashes]
    print(f"protected_pre_files={len(protected)}")
    print(f"preserved_by_sha256={len(protected) - len(missing)}")
    print(f"scientific_result_changes={len(missing)}")
    if missing:
        for row in missing[:25]:
            print(f"MISSING {row['category']} {row['relative_path']} {row['sha256']}")
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Snapshot and verify scientific files across repository cleanup.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    snapshot_parser = subparsers.add_parser("snapshot")
    snapshot_parser.add_argument("--phase", choices=["pre", "post"], required=True)
    snapshot_parser.add_argument("--output", type=Path, required=True)
    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("--before", type=Path, required=True)
    compare_parser.add_argument("--after", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "snapshot":
        snapshot(args.output, args.phase)
    else:
        compare(args.before, args.after)


if __name__ == "__main__":
    main()
