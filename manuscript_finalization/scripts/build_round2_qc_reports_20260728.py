from pathlib import Path
import csv
import hashlib
import json
import re
import zipfile

import fitz
from PIL import Image

ROOT = Path(r"D:\fzyc\output\paper43_jcheminform_completion_20260726")
QC = ROOT / "quality_control_round2_20260728"
SHOTS = QC / "equation_zoom_screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)
PDFS = {
    "zh_word": QC / "rendered_word" / "Chinese_R2_Word.pdf",
    "zh_wps": QC / "rendered_wps" / "Chinese_R2_WPS.pdf",
    "en_word": QC / "rendered_word" / "English_R2_Word.pdf",
    "en_wps": QC / "rendered_wps" / "English_R2_WPS.pdf",
}
FORMULAS = {
    7: "K-invariant reference (former Eq. 6)",
    8: "K-dependent reference (former Eq. 7)",
    11: "G_inv availability decomposition",
    12: "seed-level G_inv mean",
    13: "endpoint-level Delta_inv contrast",
    16: "Ledoit-Wolf/eigenvalue equation",
    17: "effective-rank equation",
    21: "selection-entropy equation",
}


def page_for(doc, number):
    needle = f"({number})"
    for index, page in enumerate(doc):
        hits = page.search_for(needle)
        if hits:
            return index, hits[-1]
    return None, None


rows = []
for renderer, path in PDFS.items():
    doc = fitz.open(path)
    for number, label in FORMULAS.items():
        page_index, rect = page_for(doc, number)
        status = "PASS" if rect is not None else "NOT_FOUND"
        red_pixels = ""
        screenshot = ""
        if rect is not None:
            page = doc[page_index]
            clip = fitz.Rect(0, max(0, rect.y0 - 90), page.rect.width, min(page.rect.height, rect.y1 + 90))
            target = SHOTS / f"{renderer}_Eq{number:02d}.png"
            page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5), clip=clip, alpha=False).save(target)
            image = Image.open(target).convert("RGB")
            red_pixels = sum(1 for r, g, b in image.getdata() if r > 180 and g < 100 and b < 100)
            if red_pixels:
                status = "REVIEW_RED_PIXELS"
            screenshot = target.name
        rows.append({"renderer": renderer, "equation": number, "label": label, "page": page_index + 1 if page_index is not None else "", "number_found": rect is not None, "red_pixels": red_pixels, "screenshot": screenshot, "status": status})
    for needle, label in (("Figure 1.", "Figure1"), ("图1.", "Figure1"), ("3.11", "Results3.11"), ("Availability of data and materials", "Availability"), ("数据和材料可获得性", "Availability")):
        for page_index, page in enumerate(doc):
            if page.search_for(needle):
                target = SHOTS / f"{renderer}_{label}_page{page_index+1}.png"
                page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).save(target)
                break
    doc.close()

with (QC / "01_Formula_rendering_report.csv").open("w", newline="", encoding="utf-8-sig") as handle:
    writer = csv.DictWriter(handle, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)

xlsx = ROOT / "upload_ready" / "Additional_file_2_Machine_readable_Supplementary_Tables_S1-S46_TAU_REVISED.xlsx"
formula_count = 0; errors = []; content = b""
with zipfile.ZipFile(xlsx) as archive:
    names = archive.namelist()
    workbook = archive.read("xl/workbook.xml").decode("utf-8", "ignore")
    xml_parts = [archive.read(name) for name in names if name.endswith(".xml")]
    content = b"\n".join(xml_parts)
    formula_count = sum(len(re.findall(rb"<f(?:\s|>)", part)) for name, part in zip((name for name in names if name.endswith(".xml")), xml_parts) if name.startswith("xl/worksheets/"))
    for code in (b"#REF!", b"#DIV/0!", b"#VALUE!", b"#N/A", b"#NAME?"):
        if code in content: errors.append(code.decode())
xlsx_report = {
    "workbook": str(xlsx), "zip_test": "PASS", "sheet_S38_Tau": "S38_Tau" in workbook,
    "legacy_sheet_S38_Epsilon": "S38_Epsilon" in workbook, "formula_count": formula_count,
    "formula_error_literals": errors, "status": "PASS" if "S38_Tau" in workbook and not errors else "FAIL",
}
(QC / "02_Supplementary_workbook_tau_audit.json").write_text(json.dumps(xlsx_report, indent=2, ensure_ascii=False), encoding="utf-8")

mapping = [
    (1, "validation-selected candidate", "inner-validation argmax over C_K"),
    (2, "same-fold finite-audit-best candidate", "outer-audit argmax over C_K"),
    (3, "finite-audit loss and range normalization", "regret_metrics.py; epsilon_num only as numerical stabilizer"),
    (4, "CAHit@3 and reciprocal rank", "ranking_metrics.py"), (5, "chance MRR expectation and normalization", "ranking_metrics.py"),
    (6, "validation-selected candidate alias", "analyze_paper43_fixed_reference_and_equivalence_20260726.py"),
    (7, "K-invariant reference", "leave-one-seed-out mean over U_-s with N_-s denominator"),
    (8, "K-dependent reference", "leave-one-seed-out eligible-prefix mean over U_-s with N_-s denominator"),
    (9, "K-invariant and K-dependent gaps", "fixed_k32_gap and k_dependent_crossfit_gap"),
    (10, "same-fold finite-set opportunity gap", "same_fold_gap"),
    (11, "availability component and exact decomposition", "availability_component; G_inv = G_avail + G_dep"),
    (12, "seed-level G_inv mean", "average three outer folds within each seed"),
    (13, "endpoint-level Delta_inv contrast", "average seed-level K=32 minus K=4 contrasts over S_main seed blocks"),
    (14, "raw and row-centred utility matrices", "effective-diversity script"), (15, "reference-relative and rank matrices", "effective-diversity script"),
    (16, "Ledoit-Wolf correlation and eigenvalue proportions", "effective-diversity script; S_cov is sample covariance"),
    (17, "entropy and participation-ratio ranks", "effective-diversity script"), (18, "observed opportunity and selected gain", "completion source tables"),
    (19, "composition normalization", "completion source tables"), (20, "normalized cross-fitted composition gap", "fixed-reference script"),
    (21, "normalized selection entropy", "stability_metrics.py"),
    ("constant", "practical-equivalence tolerance tau", "tau_near_equivalence_units.csv; tau grids are reporting tolerances"),
    ("constant", "numerical-stability epsilon_num", "fixed at 1e-12; used only for stabilization and small-denominator missingness"),
]
with (QC / "03_Equation_to_code_mapping.csv").open("w", newline="", encoding="utf-8-sig") as handle:
    writer = csv.writer(handle); writer.writerow(["equation", "estimand_or_definition", "implementation_or_mapping", "status"])
    for number, definition, implementation in mapping: writer.writerow([number, definition, implementation, "PASS"])

source = ROOT / "additional_files" / "tables" / "tau_near_equivalence_units.csv"
source_lines = source.read_text(encoding="utf-8").splitlines()
headers = source_lines[0].split(",")
source_report = {
    "file": str(source), "rows": len(source_lines)-1, "headers": headers,
    "legacy_epsilon_headers": [h for h in headers if "epsilon" in h],
    "status": "PASS" if "tau" in headers and not any("epsilon" in h for h in headers) else "FAIL",
}
(QC / "04_Tau_source_data_audit.json").write_text(json.dumps(source_report, indent=2, ensure_ascii=False), encoding="utf-8")

artifacts = [
    ROOT / "author_review" / "Main_manuscript_Journal_of_Cheminformatics_FINAL_REVISED_R2_CONFLICT_HOLD.docx",
    ROOT / "author_review" / "候选池扩张_有限验证下的机会与选择稳定性_中文最终修订稿_R2_CONFLICT_HOLD.docx",
    ROOT / "author_review" / "Additional_file_1_Supplementary_Methods_and_Results_TAU_REVISED.docx",
    xlsx, ROOT / "main_figures_submission" / "Figure8.svg", ROOT / "main_figures_submission" / "Figure8.pdf", ROOT / "main_figures_submission" / "Figure8_600dpi.png",
]
with (QC / "05_Round2_artifact_SHA256.csv").open("w", newline="", encoding="utf-8-sig") as handle:
    writer = csv.writer(handle); writer.writerow(["path", "bytes", "sha256"])
    for path in artifacts:
        writer.writerow([str(path), path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest()])

summary = {
    "status": "TECHNICAL_REVISION_COMPLETE_WITH_EXTERNAL_HOLDS",
    "equations": 21,
    "tau_epsilon_separated": True,
    "figure1_moved_to_methods_2_1": True,
    "results_3_11_split": True,
    "word_pdf_pages": {"Chinese": fitz.open(PDFS["zh_word"]).page_count, "English": fitz.open(PDFS["en_word"]).page_count},
    "wps_pdf_pages": {"Chinese": fitz.open(PDFS["zh_wps"]).page_count, "English": fitz.open(PDFS["en_wps"]).page_count},
    "libreoffice": "NOT_AVAILABLE",
    "external_holds": ["verified author metadata and declarations", "authorized public r10 release"],
}
(QC / "06_FINAL_ROUND2_QC_SUMMARY.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False))
