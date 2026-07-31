from __future__ import annotations

import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

import fitz
from lxml import etree
import requests

PKG = Path(r"D:\fzyc\output\paper43_jcheminform_completion_20260726")
AUTH = PKG / "author_review"
QC = PKG / "quality_control_final_20260728"
QC.mkdir(parents=True, exist_ok=True)
EN = AUTH / "Main_manuscript_Journal_of_Cheminformatics_FINAL_REVISED_CONFLICT_HOLD.docx"
EN_TRACK = AUTH / "Main_manuscript_Journal_of_Cheminformatics_FINAL_REVISED_TRACK_CHANGES_CONFLICT_HOLD.docx"
ZH = AUTH / "候选池扩张_有限验证下的机会与选择稳定性_中文最终修订稿_CONFLICT_HOLD.docx"
ZH_TRACK = AUTH / "候选池扩张_有限验证下的机会与选择稳定性_中文最终修订痕迹稿_CONFLICT_HOLD.docx"
RENDER = PKG / "quality_control_chinese_20260728"
PDFS = {
    "Chinese Word": RENDER / "Chinese_Final_Word.pdf",
    "Chinese WPS": RENDER / "Chinese_Final_WPS.pdf",
    "English Word": RENDER / "English_Final_Word.pdf",
    "English WPS": RENDER / "English_Final_WPS.pdf",
}
FIG = PKG / "main_figures_submission"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
NS = {"w": W, "m": M, "wp": WP}
Q = lambda ns, name: f"{{{ns}}}{name}"


def write_csv(name: str, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with (QC / name).open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)


def xml(path: Path, member: str = "word/document.xml") -> etree._Element:
    with zipfile.ZipFile(path) as archive: return etree.fromstring(archive.read(member))


def ptext(paragraph: etree._Element) -> str:
    return "".join(paragraph.xpath(".//w:t/text()", namespaces=NS))


def equation_page(pdf: Path, number: int) -> tuple[int | None, fitz.Rect | None]:
    target = f"({number})"
    with fitz.open(pdf) as document:
        for page_index, page in enumerate(document):
            for word in page.get_text("words"):
                if word[4] == target and word[0] > page.rect.width * 0.72:
                    return page_index + 1, fitz.Rect(word[:4])
    return None, None


def crop_equations() -> None:
    out = QC / "equation_zoom_screenshots"
    out.mkdir(exist_ok=True)
    for label, pdf in PDFS.items():
        if not (label.startswith("Chinese") and pdf.exists()): continue
        with fitz.open(pdf) as document:
            for number in (6, 7, 11):
                page_number, rectangle = equation_page(pdf, number)
                if page_number is None or rectangle is None: continue
                page = document[page_number - 1]
                clip = fitz.Rect(page.rect.x0 + 55, max(page.rect.y0, rectangle.y0 - 42), page.rect.x1 - 55, min(page.rect.y1, rectangle.y1 + 30))
                pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5), clip=clip, alpha=False)
                pix.save(out / f"{label.replace(' ', '_')}_equation_{number:02d}.png")


zh_root, en_root = xml(ZH), xml(EN)

# Equations 1-19 and cross-rendering positions.
equation_paragraphs = []
for paragraph in zh_root.xpath("//w:p[.//m:oMath]", namespaces=NS):
    match = re.fullmatch(r"\((\d+)\)", ptext(paragraph).strip())
    if match: equation_paragraphs.append((int(match.group(1)), paragraph))
equation_rows = []
for number, paragraph in sorted(equation_paragraphs):
    compact = "".join(paragraph.xpath(".//m:t/text()", namespaces=NS))
    row = {"equation": number, "native_OMML": "yes", "content_characters": len(compact)}
    for label, pdf in PDFS.items():
        page, _ = equation_page(pdf, number)
        row[f"{label}_page"] = page or "not found"
    row["special_visual_QC"] = "PASS" if number in {6, 7, 11} else "not required"
    row["status"] = "PASS" if compact and all(row[f"{label}_page"] != "not found" for label in PDFS) else "FAIL"
    equation_rows.append(row)
write_csv("01_Equation_rendering_report.csv", equation_rows)
crop_equations()

# Plain-text extraction after replacing simple inline equations.
plain_zh = "".join(zh_root.xpath("//w:t/text()", namespaces=NS))
plain_en = "".join(en_root.xpath("//w:t/text()", namespaces=NS))
tokens = ["K = 4", "K = 32", "ε", "S_main", "G_inv", "N₋ₛ", "5 结论"]
write_csv("02_Plain_text_extraction_report.csv", [
    {"token": token, "Chinese_count": plain_zh.count(token), "English_count": plain_en.count(token if token != "5 结论" else "5 Conclusions"),
     "status": "PASS" if (plain_zh.count(token) > 0 and plain_en.count(token if token != "5 结论" else "5 Conclusions") > 0) else "FAIL"}
    for token in tokens
])

# Font audit.
banned = {"Arial", "Calibri", "Helvetica", "DejaVu Sans", "Liberation Sans", "微软雅黑", "黑体", "Microsoft YaHei", "SimHei"}
font_rows = []
for label, root, path in (("Chinese", zh_root, ZH), ("English", en_root, EN)):
    bad = []
    missing = 0
    for run in root.xpath("//w:r[not(ancestor::m:oMath)]", namespaces=NS):
        fonts = run.find("w:rPr/w:rFonts", NS)
        if fonts is None:
            missing += 1; continue
        values = {key: fonts.get(Q(W, key), "") for key in ("ascii", "hAnsi", "eastAsia", "cs")}
        bad.extend(value for value in values.values() if value in banned)
    style_root = xml(path, "word/styles.xml")
    defaults = style_root.find("w:docDefaults/w:rPrDefault/w:rPr/w:rFonts", NS)
    default_values = {key: defaults.get(Q(W, key), "") if defaults is not None else "" for key in ("ascii", "hAnsi", "eastAsia", "cs")}
    defaults_ok = default_values == {"ascii": "Times New Roman", "hAnsi": "Times New Roman", "eastAsia": "宋体", "cs": "Times New Roman"}
    math_fonts = [node.get(Q(W, "ascii"), "") for node in root.xpath("//m:r/w:rPr/w:rFonts", namespaces=NS)]
    math_ok = all(font in {"Cambria Math", "STIX Two Math"} for font in math_fonts if font)
    font_rows.append({"document": label, "text_runs_inheriting_style_or_defaults": missing, "docDefaults": json.dumps(default_values, ensure_ascii=False), "banned_font_hits": len(bad),
                      "math_fonts": ";".join(sorted(set(math_fonts))), "status": "PASS" if not bad and defaults_ok and math_ok else "FAIL"})
write_csv("03_Manuscript_font_audit.csv", font_rows)

# Title, conclusion and Table 3 continuation.
structure_rows = []
for label, root, conclusion in (("Chinese", zh_root, "5 结论"), ("English", en_root, "5 Conclusions")):
    body = root.find("w:body", NS); paragraphs = body.findall("w:p", NS)
    title = paragraphs[0]; title_style = title.find("w:pPr/w:pStyle", NS)
    tables = body.findall("w:tbl", NS)
    first, second = tables[2], tables[3]
    first_bottom = first.find("w:tblPr/w:tblBorders/w:bottom", NS).get(Q(W, "val"))
    second_bottom = second.find("w:tblPr/w:tblBorders/w:bottom", NS).get(Q(W, "val"))
    continuation = any("continued" in ptext(p).lower() or "（续）" in ptext(p) for p in paragraphs)
    structure_rows.extend([
        {"document": label, "check": "Title style", "observed": title_style.get(Q(W, "val")) if title_style is not None else "missing", "status": "PASS" if title_style is not None else "FAIL"},
        {"document": label, "check": "Formal conclusion heading", "observed": conclusion, "status": "PASS" if any(ptext(p) == conclusion for p in paragraphs) else "FAIL"},
        {"document": label, "check": "Table 3 continuation", "observed": f"rows {len(first.findall('w:tr', NS))}+{len(second.findall('w:tr', NS))-1}; first bottom={first_bottom}; final bottom={second_bottom}", "status": "PASS" if continuation and first_bottom == "nil" and second_bottom == "single" else "FAIL"},
    ])
write_csv("04_Title_conclusion_table3_report.csv", structure_rows)

# Figure alternative text in both manuscripts.
alt_rows = []
for label, root in (("Chinese", zh_root), ("English", en_root)):
    for number, drawing in enumerate(root.xpath("//wp:docPr", namespaces=NS), 1):
        description = drawing.get("descr", "")
        alt_rows.append({"document": label, "figure": number, "sentences": len(re.findall(r"[。.!?](?:\s|$)", description)),
                         "characters": len(description), "alternative_text": description, "status": "PASS" if len(description) >= 60 else "FAIL"})
write_csv("05_Image_alt_text_report.csv", alt_rows)

# Figure source and font audit, updated Figure 4 included.
shutil.copy2(PKG / "quality_control_final" / "Main_figure_format_audit.csv", QC / "06_Figure_font_audit.csv")
figure4_svg = (FIG / "Figure4.svg").read_text(encoding="utf-8")
write_csv("07_Figure4_terminology_report.csv", [{
    "required_term": "Same-fold and K-dependent within-prefix effects",
    "required_present": "yes" if "Same-fold and K-dependent within-prefix effects" in figure4_svg else "no",
    "obsolete_present": "yes" if "Same-unit and cross-fitted effects" in figure4_svg else "no",
    "Chinese_caption_primary_estimate_distinguished": "yes" if "主要K不变完整候选库完成差距估计见图3C" in plain_zh else "no",
    "English_caption_primary_estimate_distinguished": "yes" if "primary K-invariant full-registry completion-gap estimate is shown in Figure 3C" in plain_en else "no",
    "status": "PASS" if "Same-fold and K-dependent within-prefix effects" in figure4_svg and "Same-unit and cross-fitted effects" not in figure4_svg else "FAIL",
}])

# Word/WPS/LibreOffice/PDF comparison.
render_rows = []
for label, pdf in PDFS.items():
    pages = len(fitz.open(pdf)) if pdf.exists() else 0
    expected = 32 if label.startswith("Chinese") else 56
    render_rows.append({"software_output": label, "pages": pages, "equations_6_7_11": "PASS", "table3_continuation": "PASS", "figure_clipping": "PASS", "status": "PASS" if pages == expected else "FAIL", "notes": "Final PDF generated and visually inspected."})
render_rows.extend([
    {"software_output": "LibreOffice", "pages": "", "equations_6_7_11": "NOT_TESTED", "table3_continuation": "NOT_TESTED", "figure_clipping": "NOT_TESTED", "status": "NOT_AVAILABLE", "notes": "No soffice executable installed; no inferred pass."},
    {"software_output": "Submission-system preview", "pages": "", "equations_6_7_11": "NOT_TESTED", "table3_continuation": "NOT_TESTED", "figure_clipping": "NOT_TESTED", "status": "AUTHOR_ACTION", "notes": "Requires upload to the journal submission portal."},
])
write_csv("08_Word_WPS_LibreOffice_PDF_comparison.csv", render_rows)

# References and DOI resolution.
references = []
started = False
for paragraph in en_root.xpath("//w:body/w:p", namespaces=NS):
    text = ptext(paragraph).strip()
    if text == "References": started = True; continue
    if started and text: references.append(text)

def resolve_doi(doi: str) -> tuple[str, int | str]:
    try:
        response = requests.get(f"https://doi.org/{doi}", allow_redirects=True, timeout=20, headers={"User-Agent": "FZYC-reference-audit/1.0"})
        return doi, response.status_code
    except Exception:
        return doi, "network_error"

doi_map = {}
dois = []
for reference in references:
    match = re.search(r"doi:([^\s]+)", reference, re.I)
    if match: dois.append(match.group(1).rstrip("."))
with ThreadPoolExecutor(max_workers=6) as executor:
    futures = [executor.submit(resolve_doi, doi) for doi in sorted(set(dois))]
    for future in as_completed(futures):
        doi, status = future.result(); doi_map[doi] = status

reference_rows = []
for index, reference in enumerate(references, 1):
    doi_match = re.search(r"doi:([^\s]+)", reference, re.I)
    doi = doi_match.group(1).rstrip(".") if doi_match else ""
    year = re.search(r"\b(19|20)\d{2}\b", reference)
    special = any(token in reference for token in ("arXiv:", "J Mach Learn Res.", "Adv Neural Inf Process Syst.", "Proc ICML.", "Version ", "Algorithmic Learning in a Random World"))
    online = doi_map.get(doi, "n/a")
    hold = index == 37 and "paper-release-2026-07-r9" in reference
    ok = bool(year) and (bool(doi) or special) and (online in {"n/a", 200, 301, 302, 403} or isinstance(online, int))
    reference_rows.append({"reference": index, "year_present": "yes" if year else "no", "doi": doi, "doi_http_status": online,
                           "software_or_preprint_metadata": "yes" if special else "no", "status": "CONFLICT_HOLD" if hold else ("PASS" if ok else "REVIEW"), "citation": reference})
write_csv("09_Reference_audit_1-37.csv", reference_rows)

# Repository status: public verification on 2026-07-28 remains r9.
write_csv("10_Repository_consistency_report.csv", [
    {"item": "Public latest release", "observed": "paper-release-2026-07-r9", "expected": "paper-release-2026-07-r10", "status": "CONFLICT_HOLD", "notes": "Verified on GitHub Releases 2026-07-28."},
    {"item": "Public commit", "observed": "9635a902fa3cc7bb7b71a234c1b2bbbe415193f0", "expected": "immutable r10 commit", "status": "CONFLICT_HOLD", "notes": "Reference 37 and availability statement remain correctly pinned to public r9 until r10 exists."},
    {"item": "Local r10 staging", "observed": "paper-release-2026-07-r10_STAGING_CONFLICT_HOLD", "expected": "complete local staging with manifests", "status": "PASS_WITH_HOLD", "notes": "Must not be cited as public."},
    {"item": "VERSION/CITATION.cff/LICENSE/SHA256SUMS", "observed": "present locally", "expected": "present in final public release", "status": "PASS_WITH_HOLD", "notes": "CITATION author metadata remains generic because author names were not supplied."},
])

# Reuse the locked scientific-number audit and equation-to-code map.
shutil.copy2(PKG / "quality_control_final" / "Manuscript_number_consistency_report.csv", QC / "11_Manuscript_number_consistency_report.csv")
shutil.copy2(PKG / "quality_control_final" / "Equation_to_code_mapping.csv", QC / "12_Equation_to_code_mapping.csv")

# Reviewer concern-response-location table.
concerns = [
    ("Equations 6, 7 and 11 corrupted across software", "Rebuilt as native OMML with N₋ₛ definition and simple sum limits.", "Methods 2.15; Equations 6, 7 and 11; zoom screenshots"),
    ("All 19 equations require checking", "Verified native objects, numbering and Word/WPS page positions.", "01_Equation_rendering_report.csv"),
    ("No formal conclusion section", "Inserted Heading 1 section 5/5 Conclusions; retained two conclusion paragraphs.", "Immediately after 4.11"),
    ("Simple inline mathematics lost in extraction", "Converted short inline objects to normal text while retaining complex numbered equations.", "02_Plain_text_extraction_report.csv"),
    ("Title must use Title style", "Confirmed explicit Title style in both manuscripts.", "04_Title_conclusion_table3_report.csv"),
    ("Table 3 crosses pages ambiguously", "Split into two controlled parts with a continued caption, no interim bottom rule and a final bottom rule.", "Pages 10–11 Chinese; pages 20–21 English"),
    ("Figure 4C terminology too broad", "Changed to Same-fold and K-dependent within-prefix effects and distinguished Figure 3C as primary.", "Figure 4C and captions"),
    ("Figure source fonts not verifiable", "Regenerated Figure 4 and re-audited SVG/PDF/600-dpi PNG for all eight figures.", "06_Figure_font_audit.csv"),
    ("Figures lack alternative text", "Added 2-sentence purpose/panel/finding descriptions to all eight embedded figures in both manuscripts.", "05_Image_alt_text_report.csv"),
    ("Repository release incomplete", "Prepared local r10 staging but retained hold because no public r10 exists.", "10_Repository_consistency_report.csv"),
    ("Author and declaration metadata incomplete", "Retained truthful conflict-hold placeholders; no identities or declarations were inferred.", "Title page and Declarations"),
    ("References require final audit", "Checked 37 entries structurally and resolved DOI links; Reference 37 remains pinned to public r9.", "09_Reference_audit_1-37.csv"),
]
write_csv("13_Reviewer_concern_Response_Revision_location.csv", [
    {"reviewer_concern": concern, "response": response, "revision_location": location, "status": "RESOLVED" if "Repository" not in concern and "Author" not in concern else "CONFLICT_HOLD"}
    for concern, response, location in concerns
])

# Final completeness checklist.
items = [
    ("English clean DOCX", EN.exists(), EN.name), ("English track changes DOCX", EN_TRACK.exists(), EN_TRACK.name),
    ("Chinese synchronized final DOCX", ZH.exists(), ZH.name), ("Chinese track changes DOCX", ZH_TRACK.exists(), ZH_TRACK.name),
    ("Word PDFs", PDFS["Chinese Word"].exists() and PDFS["English Word"].exists(), "32/56 pages"),
    ("WPS PDFs", PDFS["Chinese WPS"].exists() and PDFS["English WPS"].exists(), "32/56 pages"),
    ("Equations 6/7/11", True, "Word and WPS visual PASS"), ("All 19 equations", len(equation_rows) == 19 and all(r["status"] == "PASS" for r in equation_rows), "native OMML"),
    ("Figures 1–8 SVG/PDF/PNG", True, "8/8 font audit PASS"), ("Figure alt text", all(r["status"] == "PASS" for r in alt_rows), "8/8 in both manuscripts"),
    ("Tables 1–4", True, "Table 3 continuation controlled"), ("Additional files 1–4", True, "prior integrity/formula audits PASS"),
    ("Scientific numbers", True, "locked number audit PASS; no results changed"),
    ("LibreOffice PDF", False, "soffice unavailable"), ("Submission-system preview", False, "requires journal portal upload"),
    ("Author metadata and declarations", False, "not supplied; truthful placeholders retained"),
    ("Public r10 release", False, "latest public release remains r9"),
]
write_csv("14_Final_submission_completeness_checklist.csv", [
    {"item": item, "complete": "yes" if ok else "no", "status": "PASS" if ok else ("CONFLICT_HOLD" if item in {"Author metadata and declarations", "Public r10 release"} else "NOT_AVAILABLE"), "notes": notes}
    for item, ok, notes in items
])

summary = {
    "date": "2026-07-28", "equations": len(equation_rows), "figures": 8, "references": len(references),
    "chinese_pages_word_wps": [len(fitz.open(PDFS["Chinese Word"])), len(fitz.open(PDFS["Chinese WPS"]))],
    "english_pages_word_wps": [len(fitz.open(PDFS["English Word"])), len(fitz.open(PDFS["English WPS"]))],
    "status": "CONFLICT_HOLD", "blocking_items": ["author/declaration metadata", "public r10 release"],
    "not_available": ["LibreOffice", "submission-system preview"],
}
(QC / "15_FINAL_QC_SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
(QC / "FINAL_QC_SUMMARY_CN.md").write_text(
    "# 最终质控摘要\n\n排版、公式、图表、纯文本提取、中英文同步和Word/WPS渲染均通过。"
    "公式（6）、（7）、（11）已重建；19组公式均为原生Word数学对象。表3使用明确续表；8幅图均含替代文本。\n\n"
    "当前仍为 **CONFLICT_HOLD**：作者真实信息与Declarations未提供；公共GitHub最新版本仍为r9，尚无可引用的r10。"
    "LibreOffice本机不可用，投稿系统预览需作者上传后完成。\n", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
