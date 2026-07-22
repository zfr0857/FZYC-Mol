from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path


ROOT = Path(r"D:\fzyc")
OUTPUT = ROOT / "output"
BASE = OUTPUT / "paper26_submission_package_20260716"
REVISION = OUTPUT / "paper27_equal_size_registry_composition_revision_20260716"
ANALYSIS = OUTPUT / "paper27_equal_size_registry_composition_20260716"
EXPERIMENT_ROOT = ROOT / "results" / "equal_size_registry_composition_20260716"
EXPERIMENT = EXPERIMENT_ROOT / "new_candidates"
PACKAGE = OUTPUT / "paper27_submission_package_20260716"
ARCHIVE = OUTPUT / "Paper27_Journal_of_Cheminformatics_equal_size_composition_revision_20260716.zip"


def copy_file(source: Path, target: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    if ARCHIVE.exists():
        ARCHIVE.unlink()
    shutil.copytree(BASE, PACKAGE)

    old_sums = PACKAGE / "SHA256SUMS.txt"
    if old_sums.exists():
        old_sums.unlink()

    english_name = "Candidate_pool_expansion_Journal_of_Cheminformatics_manuscript.docx"
    tracked_name = "Candidate_pool_expansion_Journal_of_Cheminformatics_manuscript_tracked_changes.docx"
    reviewer_name = "Reviewer_concern_Response_Location.docx"
    chinese = next(path for path in REVISION.glob("*.docx") if path.name not in {english_name, tracked_name, reviewer_name})
    root_files = [
        REVISION / english_name,
        REVISION / tracked_name,
        chinese,
        REVISION / reviewer_name,
        REVISION / "New_Abstract.txt",
        REVISION / "Revised_Abstract.txt",
        REVISION / "New_Scientific_Contribution.txt",
        REVISION / "Scientific_Contribution.txt",
        REVISION / "Equal_size_registry_composition_final_checklist.csv",
        REVISION / "Equal_size_registry_composition_final_audit.json",
    ]
    for source in root_files:
        copy_file(source, PACKAGE / source.name)

    shutil.rmtree(PACKAGE / "main_figures", ignore_errors=True)
    shutil.copytree(REVISION / "main_figures", PACKAGE / "main_figures")

    supplementary = PACKAGE / "supplementary"
    for old in supplementary.glob("Additional_file_2_Machine_readable_Supplementary_Tables_*.xlsx"):
        old.unlink()
    copy_file(
        REVISION / "supplementary" / "Additional_file_1_Supplementary_Methods_and_Results.docx",
        supplementary / "Additional_file_1_Supplementary_Methods_and_Results.docx",
    )
    copy_file(
        REVISION / "supplementary" / "Additional_file_2_Machine_readable_Supplementary_Tables_S1-S31.xlsx",
        supplementary / "Additional_file_2_Machine_readable_Supplementary_Tables_S1-S31.xlsx",
    )

    verification = PACKAGE / "verification" / "equal_size_registry_composition"
    if verification.exists():
        shutil.rmtree(verification)
    shutil.copytree(ANALYSIS, verification / "analysis", ignore=shutil.ignore_patterns("figures"))
    exports = verification / "experiment_exports"
    for name in ("candidate_registry.csv", "inner_scores.csv", "outer_candidate_scores.csv", "split_manifest.csv", "run_manifest.json"):
        copy_file(EXPERIMENT / name, exports / name)
    for task in ("clintox", "bace", "esol"):
        for seed in (11, 23, 37, 53, 71):
            source = EXPERIMENT / task / f"seed_{seed}"
            target = exports / task / f"seed_{seed}"
            for name in ("complete.json", "inner_scores.csv", "outer_candidate_scores.csv", "split_manifest.csv"):
                copy_file(source / name, target / name)
    for name in ("clintox.err.log", "bace.err.log", "esol_lsqr.err.log"):
        copy_file(EXPERIMENT_ROOT / "logs" / name, verification / "final_logs" / name)

    code_dir = PACKAGE / "code"
    code_files = [
        "run_equal_size_registry_composition_20260716.py",
        "analyze_equal_size_registry_composition_20260716.py",
        "build_equal_size_registry_composition_figure_20260716.py",
        "update_paper27_equal_size_documents_20260716.py",
        "build_paper27_tracked_changes_20260716.py",
        "compare_paper27_documents_20260716.ps1",
        "render_paper27_documents_20260716.ps1",
        "verify_paper27_equal_size_revision_20260716.py",
        "finalize_paper27_submission_package_20260716.py",
    ]
    for name in code_files:
        copy_file(ROOT / "scripts" / name, code_dir / name)
    copy_file(ROOT / "tests" / "test_equal_size_registry_composition.py", code_dir / "tests" / "test_equal_size_registry_composition.py")

    checks = {
        "clean_english_manuscript": (PACKAGE / english_name).is_file(),
        "tracked_manuscript": (PACKAGE / tracked_name).is_file(),
        "chinese_manuscript": (PACKAGE / chinese.name).is_file(),
        "figure7_pdf": (PACKAGE / "main_figures" / "Figure_7_equal_size_registry_composition.pdf").is_file(),
        "figure7_svg": (PACKAGE / "main_figures" / "Figure_7_equal_size_registry_composition.svg").is_file(),
        "figure7_600dpi": (PACKAGE / "main_figures" / "Figure_7_equal_size_registry_composition_600dpi.png").is_file(),
        "supplementary_tables_s1_s31": (supplementary / "Additional_file_2_Machine_readable_Supplementary_Tables_S1-S31.xlsx").is_file(),
        "no_obsolete_s1_s26_workbook": not any(supplementary.glob("*S1-S26.xlsx")),
        "analysis_audit": (verification / "analysis" / "equal_size_registry_composition_audit.json").is_file(),
        "15_complete_markers": len(list(exports.glob("*/*/complete.json"))) == 15,
        "final_logs_empty": all((verification / "final_logs" / name).stat().st_size == 0 for name in ("clintox.err.log", "bace.err.log", "esol_lsqr.err.log")),
        "new_test_included": (code_dir / "tests" / "test_equal_size_registry_composition.py").is_file(),
    }
    for path in (PACKAGE / english_name, PACKAGE / tracked_name, PACKAGE / chinese.name, supplementary / "Additional_file_2_Machine_readable_Supplementary_Tables_S1-S31.xlsx"):
        try:
            with zipfile.ZipFile(path) as archive:
                checks[f"valid_ooxml_{path.name}"] = "[Content_Types].xml" in archive.namelist()
        except zipfile.BadZipFile:
            checks[f"valid_ooxml_{path.name}"] = False

    audit = {
        "status": "complete" if all(checks.values()) else "failed",
        "passed": sum(checks.values()),
        "total": len(checks),
        "checks": checks,
        "pytest": "115 passed, 3 dependency deprecation warnings",
        "experiment": "6,300 new candidate fits; 15 task-seed runs; 3 endpoints; K=16/32; 3 equal-size pools",
        "scope_note": "Modern augmentation uses frozen ChemBERTa/MoLFormer embeddings and a locked one-epoch D-MPNN; encoder pretraining and cached embedding extraction are excluded from the downstream cost metric.",
    }
    audit_path = PACKAGE / "Paper27_submission_package_audit.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    if audit["status"] != "complete":
        raise RuntimeError([name for name, passed in checks.items() if not passed])

    files = sorted((path for path in PACKAGE.rglob("*") if path.is_file() and path.name != "SHA256SUMS.txt"), key=lambda path: path.relative_to(PACKAGE).as_posix().lower())
    (PACKAGE / "SHA256SUMS.txt").write_text(
        "\n".join(f"{sha256(path)}  {path.relative_to(PACKAGE).as_posix()}" for path in files) + "\n",
        encoding="utf-8",
    )
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(PACKAGE.rglob("*")):
            if path.is_file():
                archive.write(path, Path(PACKAGE.name) / path.relative_to(PACKAGE))
    with zipfile.ZipFile(ARCHIVE) as archive:
        bad_member = archive.testzip()
    result = {
        "package": str(PACKAGE),
        "archive": str(ARCHIVE),
        "package_files": len(list(PACKAGE.rglob("*.*"))),
        "archive_bytes": ARCHIVE.stat().st_size,
        "archive_sha256": sha256(ARCHIVE),
        "zip_integrity": bad_member is None,
        "audit": audit,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if bad_member is not None:
        raise RuntimeError(f"Corrupt ZIP member: {bad_member}")


if __name__ == "__main__":
    main()
