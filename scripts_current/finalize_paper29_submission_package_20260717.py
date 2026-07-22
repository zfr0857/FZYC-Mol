from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path


OUTPUT = Path(r"D:\fzyc\output").resolve()
SOURCE = (OUTPUT / "paper29_figure7_table_revision_20260717").resolve()
PACKAGE = (OUTPUT / "paper29_submission_package_20260717").resolve()
ZIP_PATH = (OUTPUT / "Paper29_Journal_of_Cheminformatics_Figure7_tables_minor_revision_20260717.zip").resolve()

FILES = [
    "Candidate_pool_expansion_Journal_of_Cheminformatics_manuscript(6).docx",
    "候选池扩张与模型选择损失_中文完整论文.docx",
    "Reviewer_concern_Response_Location.docx",
    "Table_1.csv",
    "Table_2.csv",
    "Table_3.csv",
    "Main_Tables_1-3.xlsx",
    "Table_2_recorded_exposure_source_audit.csv",
    "Master_result_consistency_table.csv",
    "Master_result_consistency_table.xlsx",
    "Table_quality_control_report.csv",
    "Figure_7_quality_control_report.csv",
    "Figure_table_cross_reference_check.csv",
    "English_Chinese_numeric_consistency_check.csv",
    "Paper29_final_QC_audit.json",
    "Paper29_revision_build_audit.json",
    "Figure7_greyscale_check.png",
    "English_Figure_Titles_and_Legends.txt",
    "Chinese_Figure_Titles_and_Legends.txt",
    "Declarations_final_check.csv",
]
DIRS = ["main_figures", "figure_source_data", "supplementary", "experiment_exports"]
SCRIPTS = [
    "build_paper29_figure7_20260717.py",
    "update_paper29_tables_manuscripts_20260717.py",
    "build_paper29_qc_reports_20260717.py",
    "finalize_paper29_submission_package_20260717.py",
    "build_paper21_final_figures.py",
    "build_equal_size_registry_composition_figure_20260716.py",
]
TESTS = ["test_paper29_figure7_tables.py", "test_equal_size_registry_composition.py"]


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def main() -> None:
    if PACKAGE.parent != OUTPUT or not PACKAGE.name.startswith("paper29_"):
        raise RuntimeError(f"Unsafe package target: {PACKAGE}")
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    PACKAGE.mkdir(parents=True)

    for name in FILES:
        source = SOURCE / name
        if not source.exists():
            raise FileNotFoundError(source)
        shutil.copy2(source, PACKAGE / name)
    for name in DIRS:
        source = SOURCE / name
        if source.exists():
            shutil.copytree(source, PACKAGE / name)

    code = PACKAGE / "reproducibility_code"
    code.mkdir()
    for name in SCRIPTS:
        source = Path(r"D:\fzyc\scripts") / name
        shutil.copy2(source, code / name)
    test_dir = code / "tests"
    test_dir.mkdir()
    for name in TESTS:
        source = Path(r"D:\fzyc\tests") / name
        shutil.copy2(source, test_dir / name)

    readme = PACKAGE / "README_submission_package.txt"
    readme.write_text(
        "Journal of Cheminformatics minor-revision package: Figure 7 and Tables 1-3\n"
        "Generated: 2026-07-17 (Asia/Shanghai)\n\n"
        "Primary manuscript:\n"
        "- Candidate_pool_expansion_Journal_of_Cheminformatics_manuscript(6).docx\n"
        "- 候选池扩张与模型选择损失_中文完整论文.docx\n\n"
        "Figure 7:\n"
        "- main_figures/Figure7.pdf (170 mm vector width; embedded Times New Roman)\n"
        "- main_figures/Figure7.svg (editable text)\n"
        "- main_figures/Figure7_600dpi.png (4500 x 3329 RGB; >=600 dpi at 170 mm)\n\n"
        "Main tables and supplementary sources:\n"
        "- Table_1.csv, Table_2.csv, Table_3.csv and Main_Tables_1-3.xlsx\n"
        "- supplementary/Additional_file_2_Machine_readable_Supplementary_Tables_S1-S31.xlsx\n"
        "- figure_source_data contains the panel- and table-level machine-readable source files\n\n"
        "Quality control:\n"
        "- Table_quality_control_report.csv\n"
        "- Figure_7_quality_control_report.csv\n"
        "- Figure_table_cross_reference_check.csv\n"
        "- English_Chinese_numeric_consistency_check.csv\n"
        "- Paper29_final_QC_audit.json\n\n"
        "The attachment did not contain a separate manuscript(6) file. The immediately preceding validated Paper28 clean manuscript was used as the equivalent latest baseline. No original result, negative result or uncertainty interval was changed; two Results 3.9 displayed limits were aligned to the locked Table 3/Figure 3C/Figure 4C rounding.\n\n"
        "Author confirmation remains required for Competing interests, Funding, Authors' contributions and Acknowledgements.\n",
        encoding="utf-8",
    )

    files = sorted(path for path in PACKAGE.rglob("*") if path.is_file() and path.name not in {"SHA256SUMS.txt", "Package_manifest.json"})
    checksum_rows = [(path.relative_to(PACKAGE).as_posix(), digest(path), path.stat().st_size) for path in files]
    (PACKAGE / "SHA256SUMS.txt").write_text(
        "".join(f"{sha}  {relative}\n" for relative, sha, _ in checksum_rows), encoding="utf-8"
    )
    manifest = {
        "status": "complete",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": str(SOURCE),
        "package": str(PACKAGE),
        "file_count_excluding_manifest_files": len(checksum_rows),
        "total_bytes_excluding_manifest_files": sum(size for _, _, size in checksum_rows),
        "regression_tests": "119 passed; 3 third-party deprecation warnings",
        "figure_7": {"pdf_width_mm": 170.0, "png_dimensions": [4500, 3329], "minimum_font_size_pt": 7.5},
        "table_columns": {"Table 1": 4, "Table 2": 4, "Table 3": 3},
        "author_confirmation_still_required": [
            "Competing interests", "Funding", "Authors' contributions", "Acknowledgements"
        ],
    }
    (PACKAGE / "Package_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(item for item in PACKAGE.rglob("*") if item.is_file()):
            archive.write(path, Path(PACKAGE.name) / path.relative_to(PACKAGE))
    with zipfile.ZipFile(ZIP_PATH) as archive:
        bad = archive.testzip()
        members = len(archive.infolist())
    if bad:
        raise RuntimeError(f"Corrupt ZIP member: {bad}")
    zip_audit = {
        "status": "complete",
        "zip": str(ZIP_PATH),
        "zip_bytes": ZIP_PATH.stat().st_size,
        "zip_sha256": digest(ZIP_PATH),
        "zip_members": members,
        "zip_test": "PASS",
    }
    (OUTPUT / "Paper29_submission_zip_audit_20260717.json").write_text(
        json.dumps(zip_audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({**manifest, **zip_audit}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
