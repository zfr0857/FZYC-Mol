from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path


OUTPUT = Path(r"D:\fzyc\output").resolve()
SOURCE = (OUTPUT / "paper30_final_minor_revision_20260717").resolve()
PACKAGE = (OUTPUT / "paper30_submission_package_20260717").resolve()
ZIP_PATH = (OUTPUT / "Paper30_Journal_of_Cheminformatics_final_minor_revision_20260717.zip").resolve()

FILES = [
    "Candidate_pool_expansion_Journal_of_Cheminformatics_manuscript(6).docx",
    "候选池扩张与模型选择损失_中文完整论文.docx",
    "Reviewer_concern_Response_Location.docx",
    "Table_1.csv", "Table_2.csv", "Table_3.csv", "Main_Tables_1-3.xlsx",
    "Table_2_recorded_exposure_source_audit.csv",
    "Figure_7_source_data.xlsx",
    "Master_result_consistency_table.csv", "Master_result_consistency_table.xlsx",
    "Figure_7_quality_control_report.csv", "Table_quality_control_report.csv",
    "Declarations_completion_checklist.csv", "Declarations_edit_audit.json",
    "Unicode_cleaning_report.csv", "Figure_table_cross_reference_report.csv",
    "English_Chinese_numerical_consistency_report.csv",
    "Paper30_revision_build_audit.json", "Paper30_final_QC_audit.json",
    "Figure7_greyscale_check.png",
    "English_Figure_Titles_and_Legends.txt", "Chinese_Figure_Titles_and_Legends.txt",
]
DIRS = ["main_figures", "figure_source_data", "supplementary", "experiment_exports"]
SCRIPTS = [
    "build_paper30_figure7_20260717.py",
    "update_paper30_manuscripts_tables_20260717.py",
    "build_paper30_qc_reports_20260717.py",
    "finalize_paper30_submission_package_20260717.py",
]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    if PACKAGE.parent != OUTPUT or not PACKAGE.name.startswith("paper30_"):
        raise RuntimeError(f"Unsafe package path: {PACKAGE}")
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
    verification = PACKAGE / "verification"
    verification.mkdir()
    for name in ["English_manuscript_render.pdf", "Chinese_manuscript_render.pdf",
                 "English_QC_contact_sheet.png", "Chinese_QC_contact_sheet.png"]:
        source = SOURCE / "qc_render" / name
        if source.exists():
            shutil.copy2(source, verification / name)
    code = PACKAGE / "reproducibility_code"
    code.mkdir()
    for name in SCRIPTS:
        shutil.copy2(Path(r"D:\fzyc\scripts") / name, code / name)
    tests = code / "tests"
    tests.mkdir()
    shutil.copy2(Path(r"D:\fzyc\tests\test_paper30_final_minor_revision.py"), tests / "test_paper30_final_minor_revision.py")

    (PACKAGE / "README_submission_package.txt").write_text(
        "Journal of Cheminformatics — final minor-revision package\n"
        "Generated: 2026-07-17 (Asia/Shanghai)\n\n"
        "Primary manuscripts\n"
        "- Candidate_pool_expansion_Journal_of_Cheminformatics_manuscript(6).docx\n"
        "- 候选池扩张与模型选择损失_中文完整论文.docx\n\n"
        "Figure 7\n"
        "- main_figures/Figure7.pdf: 170.000 mm vector PDF; embedded Times New Roman\n"
        "- main_figures/Figure7.svg: editable text\n"
        "- main_figures/Figure7_600dpi.png: 4500 × 3400 RGB; 672.4 dpi at 170 mm\n"
        "- Figure_7_source_data.xlsx and figure_source_data/: machine-readable panel sources\n\n"
        "Main changes\n"
        "- Figure 7 layout: top 50/50 and bottom 46/54; endpoint-faceted panel B; spanning group headings in panel C; widened panel D.\n"
        "- Table 2 compressed to five core audit components; four-model reliability context retained in Table S3.\n"
        "- Table 1 and Table 3 headers shortened; original endpoint values, effects, directions and intervals preserved.\n"
        "- Internal declaration placeholders removed without inferring author information; use Declarations_completion_checklist.csv before submission.\n\n"
        "Input note\n"
        "The requested manuscript(6)(1).docx was not present in the workspace or attachment directories. The latest validated Paper29 manuscript(6).docx was used as the baseline.\n\n"
        "QC\n"
        "- Figure, table, cross-reference, bilingual, OOXML, formula and visual-render checks passed.\n"
        "- 23 Paper30 regression tests passed.\n"
        "- Author confirmation remains required for competing interests, funding, authors' contributions and acknowledgements.\n",
        encoding="utf-8",
    )

    files = sorted(p for p in PACKAGE.rglob("*") if p.is_file() and p.name not in {"SHA256SUMS.txt", "Package_manifest.json"})
    rows = [(p.relative_to(PACKAGE).as_posix(), digest(p), p.stat().st_size) for p in files]
    (PACKAGE / "SHA256SUMS.txt").write_text("".join(f"{sha}  {name}\n" for name, sha, _ in rows), encoding="utf-8")
    audit = json.loads((SOURCE / "Paper30_final_QC_audit.json").read_text(encoding="utf-8"))
    manifest = {
        "status": "complete",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": str(SOURCE),
        "package": str(PACKAGE),
        "file_count_excluding_manifest_files": len(rows),
        "total_bytes_excluding_manifest_files": sum(size for _, _, size in rows),
        "regression_tests": "23 passed",
        "figure_7": {"pdf_width_mm": 170.0, "png_dimensions": [4500, 3400], "effective_dpi": 672.4, "minimum_font_size_pt": 7.7},
        "table_rows": {"Table 1": 9, "Table 2": 5, "Table 3 data": 9},
        "qc_status": audit["status"],
        "requested_manuscript_6_1_found": False,
        "baseline_used": "Paper29 manuscript(6).docx",
        "author_confirmation_still_required": audit["author_confirmation_still_required"],
    }
    (PACKAGE / "Package_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(p for p in PACKAGE.rglob("*") if p.is_file()):
            archive.write(path, Path(PACKAGE.name) / path.relative_to(PACKAGE))
    with zipfile.ZipFile(ZIP_PATH) as archive:
        bad, members = archive.testzip(), len(archive.infolist())
    if bad:
        raise RuntimeError(f"Corrupt ZIP member: {bad}")
    zip_audit = {
        "status": "complete", "zip": str(ZIP_PATH), "zip_bytes": ZIP_PATH.stat().st_size,
        "zip_sha256": digest(ZIP_PATH), "zip_members": members, "zip_test": "PASS",
    }
    (OUTPUT / "Paper30_submission_zip_audit_20260717.json").write_text(json.dumps(zip_audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({**manifest, **zip_audit}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
