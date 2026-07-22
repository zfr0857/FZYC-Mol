from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(root: Path, files: Iterable[Path]) -> dict[str, object]:
    entries = []
    for path in sorted({Path(value).resolve() for value in files}, key=str):
        entries.append(
            {
                "path": path.relative_to(root.resolve()).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return {"schema_version": 1, "generated_utc": datetime.now(timezone.utc).isoformat(), "files": entries}


def verify_manifest(root: Path, manifest: dict[str, object]) -> list[str]:
    failures = []
    for entry in manifest["files"]:  # type: ignore[index]
        path = root / entry["path"]
        if not path.exists() or _sha256(path) != entry["sha256"]:
            failures.append(entry["path"])
    return failures


def release_files(root: Path = ROOT) -> list[Path]:
    files = []
    for pattern in [
        "src/**/*.py",
        "scripts/*.py",
        "tests/*.py",
        "configs/*.yaml",
        "results/source_data/*",
        "results/statistics/*",
        "results/external_panels/*",
        "results/reliability/*.csv",
        "results/cold_start/*",
        "results/manuscript_values.json",
        "results/audits/task_compliance.*",
        "results/audits/manuscript_value_verification.json",
        "results/audits/small_paper_2_audit.json",
    ]:
        files.extend(path for path in root.glob(pattern) if path.is_file())
    for name in [
        "README.md",
        "LICENSE",
        "CITATION.cff",
        "pyproject.toml",
        "requirements.lock",
        "environment.yml",
        "Dockerfile",
        "pytest.ini",
        "machine_inventory.json",
        "docs/methods_protocol.md",
        "docs/reproducibility.md",
        "docs/manuscript_change_log.md",
        "docs/manuscript_terminology_ledger.md",
        "docs/resource_gap_report.md",
        "output/小论文-2.docx",
        "output/小论文-2_修订痕迹.docx",
        ".github/workflows/tests.yml",
    ]:
        path = root / name
        if path.exists():
            files.append(path)
    return files


def main() -> None:
    manifest = build_manifest(ROOT, release_files())
    manifest_path = ROOT / "results" / "reproducibility_manifest.json"
    sums_path = ROOT / "SHA256SUMS"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    sums_path.write_text(
        "\n".join(f"{entry['sha256']}  {entry['path']}" for entry in manifest["files"]) + "\n", encoding="utf-8"
    )
    failures = verify_manifest(ROOT, manifest)
    print(f"files={len(manifest['files'])} failures={len(failures)}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
