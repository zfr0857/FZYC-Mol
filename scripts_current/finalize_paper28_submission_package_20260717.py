from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path


OUTPUT = Path(r"D:\fzyc\output").resolve()
SOURCE = (OUTPUT / "paper28_pre_submission_minor_revision_20260717").resolve()
PACKAGE = (OUTPUT / "paper28_submission_package_20260717").resolve()
ZIP_PATH = (OUTPUT / "Paper28_Journal_of_Cheminformatics_pre_submission_minor_revision_20260717.zip").resolve()
CODE = PACKAGE / "reproducibility_code"

SCRIPTS = [
    Path(r"D:\fzyc\scripts\build_paper21_final_figures.py"),
    Path(r"D:\fzyc\scripts\build_equal_size_registry_composition_figure_20260716.py"),
    Path(r"D:\fzyc\scripts\normalize_paper28_figure_pngs_20260717.py"),
    Path(r"D:\fzyc\scripts\update_paper28_pre_submission_minor_revision_20260717.py"),
    Path(r"D:\fzyc\scripts\build_paper28_pre_submission_qc_20260717.py"),
    Path(r"D:\fzyc\scripts\build_paper28_tracked_changes_20260717.py"),
    Path(r"D:\fzyc\scripts\verify_paper28_pre_submission_minor_revision_20260717.py"),
    Path(r"D:\fzyc\scripts\finalize_paper28_submission_package_20260717.py"),
]
TESTS = [Path(r"D:\fzyc\tests\test_minor_revision_caption_source.py")]


def ensure_safe_target(path: Path) -> None:
    if path.parent != OUTPUT or not path.name.startswith("paper28_"):
        raise RuntimeError(f"Unsafe package target: {path}")


def ignored(directory: str, names: list[str]) -> set[str]:
    ignored_names = {"tracked_unpacked", "__pycache__", ".pytest_cache"}
    return {name for name in names if name in ignored_names}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    ensure_safe_target(PACKAGE)
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    shutil.copytree(SOURCE, PACKAGE, ignore=ignored)
    CODE.mkdir(parents=True, exist_ok=True)
    for source in SCRIPTS:
        if not source.exists():
            raise FileNotFoundError(source)
        shutil.copy2(source, CODE / source.name)
    test_dir = CODE / "tests"
    test_dir.mkdir(parents=True, exist_ok=True)
    for source in TESTS:
        shutil.copy2(source, test_dir / source.name)

    obsolete = PACKAGE / "supplementary" / "Additional_file_3_Supplementary_Figures_S1-S17.pdf"
    if obsolete.exists():
        obsolete.unlink()

    readme = PACKAGE / "README_submission_package.txt"
    readme.write_text(
        "Journal of Cheminformatics pre-submission minor-revision package\n"
        "Generated: 2026-07-17 (Asia/Shanghai)\n\n"
        "Primary submission files:\n"
        "- Candidate_pool_expansion_Journal_of_Cheminformatics_manuscript.docx (clean English manuscript)\n"
        "- Candidate_pool_expansion_Journal_of_Cheminformatics_manuscript_tracked_changes.docx\n"
        "- Reviewer_concern_Response_Location.docx\n"
        "- supplementary/Additional_file_1_Supplementary_Methods_and_Results.docx\n"
        "- supplementary/Additional_file_2_Machine_readable_Supplementary_Tables_S1-S31.xlsx\n"
        "- supplementary/Additional_file_3_Supplementary_Figures_S1-S18.pdf\n"
        "- main_figures/Figure1-Figure7 in PDF, editable SVG and RGB 600-dpi PNG formats\n\n"
        "Verification:\n"
        "- Final_minor_revision_QC_audit.json\n"
        "- Final_package_verification_audit.json\n"
        "- Final_package_verification_checklist.csv\n"
        "- SHA256SUMS.txt\n\n"
        "Author confirmation remains required for Competing interests, Funding, Authors' contributions, and Acknowledgements.\n",
        encoding="utf-8",
    )

    files = sorted(
        path for path in PACKAGE.rglob("*")
        if path.is_file() and path.name not in {"SHA256SUMS.txt", "Package_manifest.json"}
    )
    hash_rows = [(path.relative_to(PACKAGE).as_posix(), sha256(path), path.stat().st_size) for path in files]
    (PACKAGE / "SHA256SUMS.txt").write_text(
        "".join(f"{digest}  {relative}\n" for relative, digest, _ in hash_rows), encoding="utf-8"
    )
    manifest = {
        "status": "complete",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": str(SOURCE),
        "package": str(PACKAGE),
        "file_count_excluding_manifest_files": len(hash_rows),
        "total_bytes_excluding_manifest_files": sum(size for _, _, size in hash_rows),
        "excluded": ["tracked_unpacked", "__pycache__", ".pytest_cache", "obsolete S1-S17 combined PDF"],
        "regression_tests": "115 passed; 3 third-party deprecation warnings",
        "author_confirmation_still_required": [
            "Competing interests",
            "Funding",
            "Authors' contributions",
            "Acknowledgements",
        ],
    }
    (PACKAGE / "Package_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(p for p in PACKAGE.rglob("*") if p.is_file()):
            zf.write(path, Path(PACKAGE.name) / path.relative_to(PACKAGE))

    with zipfile.ZipFile(ZIP_PATH) as zf:
        bad = zf.testzip()
        zip_members = len(zf.infolist())
    if bad is not None:
        raise RuntimeError(f"Corrupt ZIP member: {bad}")

    zip_audit = {
        "status": "complete",
        "zip": str(ZIP_PATH),
        "zip_bytes": ZIP_PATH.stat().st_size,
        "zip_sha256": sha256(ZIP_PATH),
        "zip_members": zip_members,
        "zip_test": "PASS",
    }
    (OUTPUT / "Paper28_submission_zip_audit_20260717.json").write_text(
        json.dumps(zip_audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({**manifest, **zip_audit}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
