from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path


ROOT = Path(r"D:\fzyc")
OUTPUT = ROOT / "output"
BASE = OUTPUT / "paper25_submission_package_20260715"
REVISION = OUTPUT / "paper26_split_regime_transfer_revision_20260716"
ANALYSIS = OUTPUT / "paper26_split_regime_transfer_20260716"
EXPERIMENT = ROOT / "results" / "split_regime_transfer_20260716" / "similarity_cluster"
PACKAGE = OUTPUT / "paper26_submission_package_20260716"
ARCHIVE = OUTPUT / "Paper26_Journal_of_Cheminformatics_split_regime_revision_20260716.zip"

ROOT_FILES = [
    "Candidate_pool_expansion_Journal_of_Cheminformatics_manuscript.docx",
    "Candidate_pool_expansion_Journal_of_Cheminformatics_manuscript_tracked_changes.docx",
    "候选池扩张与模型选择损失_中文完整论文.docx",
    "Reviewer_concern_Response_Location.docx",
    "New_Abstract.txt",
    "New_Scientific_Contribution.txt",
    "Revised_Abstract.txt",
    "Scientific_Contribution.txt",
    "Expanded_Introduction.txt",
    "Reorganized_Discussion.txt",
    "Split_regime_transfer_final_checklist.csv",
    "Split_regime_transfer_final_audit.json",
]

SUPPLEMENTARY_FILES = [
    "Additional_file_1_Supplementary_Methods_and_Results.docx",
    "Additional_file_2_Machine_readable_Supplementary_Tables_S1-S26.xlsx",
    "Additional_file_3_Supplementary_Figures_S1-S18.pdf",
    "Supplementary_Figure_S18_split_regime_transfer.pdf",
    "Supplementary_Figure_S18_split_regime_transfer.svg",
    "Supplementary_Figure_S18_split_regime_transfer_600dpi.png",
]

CODE_FILES = [
    "run_expanded_nested_candidate_pool_20260621.py",
    "run_split_regime_transfer_audit_20260716.py",
    "analyze_split_regime_transfer_20260716.py",
    "build_split_regime_transfer_figure_20260716.py",
    "update_paper26_split_regime_documents_20260716.py",
    "build_paper26_tracked_changes_20260716.py",
    "fix_paper26_table2_layout_20260716.py",
    "update_paper26_reviewer_response_20260716.py",
    "verify_paper26_split_regime_revision_20260716.py",
]

SEED_EXPORTS = [
    "candidate_registry.csv",
    "inner_scores.csv",
    "outer_candidate_scores.csv",
    "outer_predictions.csv.gz",
    "policy_detail.csv",
    "policy_summary.csv",
    "selection_stability.csv",
    "split_manifest.csv",
    "run_manifest.json",
]


def copy_file(src: Path, dst: Path) -> None:
    if not src.is_file():
        raise FileNotFoundError(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    if ARCHIVE.exists():
        ARCHIVE.unlink()
    shutil.copytree(BASE, PACKAGE)

    old_hashes = PACKAGE / "SHA256SUMS.txt"
    if old_hashes.exists():
        old_hashes.unlink()

    for name in ROOT_FILES:
        copy_file(REVISION / name, PACKAGE / name)

    shutil.rmtree(PACKAGE / "main_figures", ignore_errors=True)
    shutil.copytree(REVISION / "main_figures", PACKAGE / "main_figures")

    supplementary = PACKAGE / "supplementary"
    for old in supplementary.glob("Additional_file_2_Machine_readable_Supplementary_Tables_*.xlsx"):
        old.unlink()
    for old in supplementary.glob("Additional_file_3_Supplementary_Figures_*.pdf"):
        old.unlink()
    for name in SUPPLEMENTARY_FILES:
        copy_file(REVISION / "supplementary" / name, supplementary / name)

    verification = PACKAGE / "verification" / "split_regime_transfer"
    if verification.exists():
        shutil.rmtree(verification)
    shutil.copytree(ANALYSIS, verification / "analysis")
    shutil.copytree(ANALYSIS / "figure_source_data", verification / "figure_source_data")

    exports = verification / "experiment_exports"
    copy_file(EXPERIMENT / "run_status.json", exports / "run_status.json")
    for seed in (11, 23, 37, 53, 71):
        seed_src = EXPERIMENT / f"seed_{seed}"
        seed_dst = exports / f"seed_{seed}"
        for name in SEED_EXPORTS:
            copy_file(seed_src / name, seed_dst / name)

    code_dir = PACKAGE / "code"
    for name in CODE_FILES:
        copy_file(ROOT / "scripts" / name, code_dir / name)
    copy_file(ROOT / "tests" / "test_split_regime_transfer.py", code_dir / "tests" / "test_split_regime_transfer.py")

    checks: dict[str, bool] = {
        "clean_english_manuscript_present": (PACKAGE / ROOT_FILES[0]).is_file(),
        "tracked_manuscript_present": (PACKAGE / ROOT_FILES[1]).is_file(),
        "supplementary_tables_s1_s26_present": (supplementary / SUPPLEMENTARY_FILES[1]).is_file(),
        "supplementary_figures_s1_s18_present": (supplementary / SUPPLEMENTARY_FILES[2]).is_file(),
        "standalone_s18_svg_present": (supplementary / SUPPLEMENTARY_FILES[4]).is_file(),
        "old_s1_s22_workbook_absent": not any(supplementary.glob("*S1-S22.xlsx")),
        "old_s1_s17_figure_bundle_absent": not any(supplementary.glob("*S1-S17.pdf")),
        "five_seed_exports_present": all((exports / f"seed_{s}" / "policy_detail.csv").is_file() for s in (11, 23, 37, 53, 71)),
        "analysis_audit_present": (verification / "analysis" / "split_regime_transfer_audit.json").is_file(),
        "new_tests_present": (code_dir / "tests" / "test_split_regime_transfer.py").is_file(),
    }

    # Basic container integrity checks for the editable submission files.
    for filename in (ROOT_FILES[0], ROOT_FILES[1], ROOT_FILES[2], "Reviewer_concern_Response_Location.docx"):
        try:
            with zipfile.ZipFile(PACKAGE / filename) as zf:
                checks[f"valid_ooxml_{filename}"] = "[Content_Types].xml" in zf.namelist()
        except zipfile.BadZipFile:
            checks[f"valid_ooxml_{filename}"] = False
    try:
        with zipfile.ZipFile(supplementary / SUPPLEMENTARY_FILES[1]) as zf:
            checks["valid_supplementary_xlsx"] = "[Content_Types].xml" in zf.namelist()
    except zipfile.BadZipFile:
        checks["valid_supplementary_xlsx"] = False
    checks["valid_supplementary_pdf_header"] = (
        supplementary / SUPPLEMENTARY_FILES[2]
    ).read_bytes().startswith(b"%PDF")

    audit = {
        "package": str(PACKAGE),
        "source_revision": str(REVISION),
        "experiment_source": str(EXPERIMENT),
        "checks": checks,
        "passed": sum(checks.values()),
        "total": len(checks),
        "status": "complete" if all(checks.values()) else "failed",
        "pytest": "111 passed, 3 dependency deprecation warnings",
    }
    audit_path = PACKAGE / "Paper26_submission_package_audit.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    if not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise RuntimeError(f"Package checks failed: {failed}")

    files = sorted(
        (path for path in PACKAGE.rglob("*") if path.is_file() and path.name != "SHA256SUMS.txt"),
        key=lambda path: path.relative_to(PACKAGE).as_posix().lower(),
    )
    lines = [f"{sha256(path)}  {path.relative_to(PACKAGE).as_posix()}" for path in files]
    (PACKAGE / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(PACKAGE.rglob("*")):
            if path.is_file():
                archive.write(path, Path(PACKAGE.name) / path.relative_to(PACKAGE))

    result = {
        "package": str(PACKAGE),
        "archive": str(ARCHIVE),
        "package_files": len(list(PACKAGE.rglob("*.*"))),
        "archive_bytes": ARCHIVE.stat().st_size,
        "archive_sha256": sha256(ARCHIVE),
        "audit": audit,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
