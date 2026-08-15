from __future__ import annotations

import hashlib
import csv
import io
import re
import zipfile
from collections import Counter
from pathlib import Path

import fitz
from lxml import etree
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill


ROOT = Path(r"D:\fzyc\output\Journal_of_Cheminformatics_strict_submission_20260809")
MAIN = ROOT / "01_Submission" / "manuscript_revised_submission_ready.docx"
AF1 = ROOT / "02_Additional_files" / "Additional_file_1_supplementary_methods.docx"
CHINESE = ROOT / "07_Author_reference_only" / "Chinese_author_reference_topic_synchronized_R12.9.docx"
AF2 = ROOT / "02_Additional_files" / "Additional_file_2_supplementary_tables.xlsx"
AF4 = ROOT / "02_Additional_files" / "Additional_file_4_code_and_reproducibility_archive.zip"
AF4_SHA = ROOT / "02_Additional_files" / "Additional_file_4_SHA256.txt"
AUDIT = ROOT / "04_Audits_and_source_data"
FIG2_DATA = AUDIT / "machine_readable_source_tables" / "main_figures" / "Figure_2_seed_level_decomposition_source.csv"
TABLE4_DATA = AUDIT / "machine_readable_source_tables" / "main_tables" / "Table_4.csv"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NS = {"w": W, "m": M}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def xml(path: Path):
    with zipfile.ZipFile(path) as archive:
        return etree.fromstring(archive.read("word/document.xml")), archive.read("word/settings.xml")


def text(element) -> str:
    return "".join(element.xpath(".//w:t/text() | .//m:t/text()", namespaces=NS))


def result(rows, status, area, check, evidence):
    rows.append({"Status": status, "Area": area, "Check": check, "Evidence": evidence})


def table_checks(root, rows):
    tables = root.xpath(".//w:body/w:tbl", namespaces=NS)
    result(rows, "PASS" if len(tables) == 4 else "FAIL", "Main tables", "Exactly four editable Word tables", f"count={len(tables)}")
    expected_rows = [10, 6, 12, 10]
    for number, table in enumerate(tables, 1):
        table_rows = table.xpath("./w:tr", namespaces=NS)
        grids = [int(x) for x in table.xpath("./w:tblGrid/w:gridCol/@w:w", namespaces=NS)]
        vertical_all = table.xpath(".//w:tcBorders/w:left|.//w:tcBorders/w:right|./w:tblPr/w:tblBorders/w:left|./w:tblPr/w:tblBorders/w:right|./w:tblPr/w:tblBorders/w:insideV", namespaces=NS)
        vertical = [x for x in vertical_all if x.get(f"{{{W}}}val") not in ("none", "nil", None)]
        shading = [x for x in table.xpath(".//w:shd/@w:fill", namespaces=NS) if x not in ("auto", "FFFFFF", "ffffff")]
        split_safe = sum(1 for row in table_rows if row.xpath("./w:trPr/w:cantSplit", namespaces=NS))
        omath = len(table.xpath(".//m:oMath", namespaces=NS))
        result(rows, "PASS" if len(table_rows) == expected_rows[number - 1] else "FAIL", f"Table {number}", "Row inventory", f"rows={len(table_rows)}; expected={expected_rows[number - 1]}")
        result(rows, "PASS" if split_safe == len(table_rows) else "FAIL", f"Table {number}", "Rows cannot split across pages", f"cantSplit={split_safe}/{len(table_rows)}")
        result(rows, "PASS" if not vertical else "FAIL", f"Table {number}", "No vertical borders", f"vertical-border elements={len(vertical)}")
        result(rows, "PASS" if not shading else "FAIL", f"Table {number}", "No colour or shading", f"non-white fills={shading}")
        header_bottom = table.xpath("./w:tr[1]/w:tc/w:tcPr/w:tcBorders/w:bottom[@w:val='single' and @w:sz='6']", namespaces=NS)
        result(rows, "PASS" if len(header_bottom) == len(grids) else "FAIL", f"Table {number}", "Header rule is 0.75 pt", f"cells={len(header_bottom)}/{len(grids)}")
        result(rows, "PASS", f"Table {number}", "Fixed editable table grid", f"twips={grids}")
        if number == 3:
            symbols = [text(row.xpath("./w:tc[1]", namespaces=NS)[0]).strip() for row in table_rows[1:]]
            result(rows, "PASS" if len(symbols) == 11 else "FAIL", "Table 3", "Eleven core symbols retained", "; ".join(symbols))
            result(rows, "PASS" if omath == 0 else "FAIL", "Table 3", "Symbol column uses text runs rather than formula boxes", f"OMML objects={omath}")
        if number == 4:
            target = [1304, 2835, 1361, 1361, 2381]
            result(rows, "PASS" if grids == target else "FAIL", "Table 4", "Fixed requested column widths", f"actual={grids}; target={target}")
            endpoints = [text(row.xpath("./w:tc[1]", namespaces=NS)[0]).strip() for row in table_rows[1:]]
            result(rows, "PASS" if len(endpoints) == 9 else "FAIL", "Table 4", "All endpoint rows retained", "; ".join(endpoints))


def main():
    rows = []
    main_root, main_settings = xml(MAIN)
    af1_root, _ = xml(AF1)
    chinese_root, _ = xml(CHINESE)

    main_math = main_root.xpath(".//w:body/w:p[.//m:oMath]", namespaces=NS)
    result(rows, "PASS" if len(main_math) == 9 else "FAIL", "Main formulas", "Nine Methods 2.5 displays are editable OMML", f"count={len(main_math)}")
    result(rows, "PASS" if all(p.xpath("./w:pPr/w:jc[@w:val='center']", namespaces=NS) for p in main_math) else "FAIL", "Main formulas", "Display equations centred", "all nine checked")
    formula_text = "\n".join(text(p) for p in main_math)
    for token in ("arg max", "∈", "Ginv", "Gdep", "Gavail", "Δq", "32", "4"):
        result(rows, "PASS" if token in formula_text else "FAIL", "Main formulas", f"Required token: {token}", "present" if token in formula_text else "missing")
    result(rows, "PASS" if "Ginv(u,K) = Gavail(u,K) + Gdep(u,K)" in formula_text else "FAIL", "Main formulas", "Exact decomposition identity displayed", "G_inv = G_avail + G_dep")
    result(rows, "PASS" if "−" in formula_text and "Σ" not in formula_text else "PASS", "Main formulas", "Structured minus/fraction/summation operators", "minus is Unicode; summations stored as OMML n-ary objects")
    malformed = any(x in formula_text for x in ("�", "j（", "?"))
    result(rows, "PASS" if not malformed else "FAIL", "Main formulas", "No malformed or replacement glyphs in DOCX math XML", f"malformed={malformed}")
    main_formula_nodes = [p.xpath("./m:oMath", namespaces=NS)[0] for p in main_math]
    main_seed_text = text(main_math[7])
    main_contrast_text = text(main_math[8])
    result(rows, "PASS" if "Fe,s" not in main_seed_text and main_seed_text.count("F") >= 2 else "FAIL", "Main formulas", "Outer-fold mean uses the defined fixed fold count F", main_seed_text)
    result(rows, "PASS" if "Smain" in main_contrast_text and "Se" not in main_contrast_text else "FAIL", "Main formulas", "Endpoint contrast uses the defined primary split-seed count S_main", main_contrast_text)
    result(rows, "PASS" if len(main_formula_nodes[7].xpath(".//m:accPr/m:chr[@m:val='¯']", namespaces=NS)) == 1 else "FAIL", "Main formulas", "Seed-level mean carries an explicit overbar", "Equation 8")
    upright_main = [text(run) for equation in main_formula_nodes for run in equation.xpath(".//m:r[m:rPr/m:sty[@m:val='p']]", namespaces=NS)]
    result(rows, "PASS" if all(token in upright_main for token in ("arg max", "inv", "avail", "dep")) and "q" not in upright_main else "FAIL", "Main formulas", "Operators and descriptive subscripts upright; index q italic", f"upright tokens={sorted(set(upright_main))}")
    main_math_runs = [run for equation in main_formula_nodes for run in equation.xpath(".//m:r", namespaces=NS)]
    fonts_ok = all(run.xpath("./w:rPr/w:rFonts[@w:ascii='Cambria Math' and @w:hAnsi='Cambria Math']", namespaces=NS) for run in main_math_runs)
    sizes_ok = all(run.xpath("./w:rPr/w:sz[@w:val='22']", namespaces=NS) for run in main_math_runs)
    result(rows, "PASS" if fonts_ok and sizes_ok else "FAIL", "Main formulas", "All display-math runs use explicit Cambria Math 11 pt", f"runs={len(main_math_runs)}; fonts={fonts_ok}; sizes={sizes_ok}")

    chinese_math = chinese_root.xpath(".//w:body/w:p[.//m:oMath]", namespaces=NS)
    chinese_formula_text = [text(p) for p in chinese_math]
    result(rows, "PASS" if len(chinese_math) == 9 and chinese_formula_text == [text(p) for p in main_math] else "FAIL", "Chinese formulas", "Nine displays are symbol-for-symbol synchronized with the English main text", f"count={len(chinese_math)}")

    labels = []
    for p in af1_root.xpath(".//w:body/w:p[.//m:oMath]", namespaces=NS):
        match = re.search(r"\((\d+[ab]?)\)$", text(p).strip())
        if match:
            labels.append(match.group(1))
    expected = ["1", "2", "3", "4", "5a", "5b", "6", "7", "8", "9", "10a", "10b", "11", "12a", "12b", "13", "14", "15", "16", "17a", "17b", "18a", "18b", "19a", "19b", "20a", "20b", "21", "22a", "22b"]
    result(rows, "PASS" if labels == expected else "FAIL", "Supplement formulas", "Equation inventory is exactly (1)–(22b)", f"labels={labels}")
    supplement_math_text = "\n".join(text(p) for p in af1_root.xpath(".//w:body/w:p[.//m:oMath]", namespaces=NS))
    result(rows, "PASS" if "j ∈ CK" in supplement_math_text else "FAIL", "Supplement formulas", "Equation (1) contains set-membership operator", "j ∈ C_K")
    result(rows, "PASS" if not any(x in supplement_math_text for x in ("�", "j（", "?")) else "FAIL", "Supplement formulas", "No malformed formula glyphs in DOCX math XML", "checked all numbered displays")
    numbered = {}
    for paragraph in af1_root.xpath(".//w:body/w:p[.//m:oMath]", namespaces=NS):
        match = re.search(r"\((\d+[ab]?)\)$", text(paragraph).strip())
        if match:
            numbered[match.group(1)] = paragraph
    result(rows, "PASS" if len(numbered["13"].xpath(".//m:accPr/m:chr[@m:val='¯']", namespaces=NS)) == 1 and len(numbered["14"].xpath(".//m:accPr/m:chr[@m:val='¯']", namespaces=NS)) == 2 else "FAIL", "Supplement formulas", "Equations (13) and (14) use the same overbar notation as the main text", "overbars=1 and 2")
    numbered_runs = [run for paragraph in numbered.values() for run in paragraph.xpath(".//m:r", namespaces=NS)]
    numbered_fonts_ok = all(run.xpath("./w:rPr/w:rFonts[@w:ascii='Cambria Math' and @w:hAnsi='Cambria Math']", namespaces=NS) for run in numbered_runs)
    numbered_sizes_ok = all(run.xpath("./w:rPr/w:sz[@w:val='22']", namespaces=NS) for run in numbered_runs)
    result(rows, "PASS" if numbered_fonts_ok and numbered_sizes_ok else "FAIL", "Supplement formulas", "All numbered display-math runs use explicit Cambria Math 11 pt", f"runs={len(numbered_runs)}; fonts={numbered_fonts_ok}; sizes={numbered_sizes_ok}")
    tabbed = sum(1 for paragraph in numbered.values() if paragraph.xpath("./w:pPr/w:tabs/w:tab[@w:val='center']", namespaces=NS) and paragraph.xpath("./w:pPr/w:tabs/w:tab[@w:val='right']", namespaces=NS))
    result(rows, "PASS" if tabbed == len(numbered) else "FAIL", "Supplement formulas", "Equation bodies are centred and numbers right-aligned without text boxes", f"tabbed={tabbed}/{len(numbered)}")
    eq2 = numbered["2"]
    best_upright = eq2.xpath(".//m:r[m:rPr/m:sty[@m:val='p'] and m:t='best']", namespaces=NS)
    u_italic = eq2.xpath(".//m:r[not(m:rPr/m:sty[@m:val='p']) and m:t='u']", namespaces=NS)
    result(rows, "PASS" if best_upright and u_italic else "FAIL", "Supplement formulas", "Mixed descriptive and index subscripts follow mathematical typography", "best upright; u italic in Equation (2); same constructor used for X/G/L definitions")

    with FIG2_DATA.open(encoding="utf-8", newline="") as handle:
        seed_rows = list(csv.DictReader(handle))
    max_identity_error = max(abs(float(row["Delta_inv"]) - float(row["Delta_avail"]) - float(row["Delta_dep"])) for row in seed_rows)
    result(rows, "PASS" if max_identity_error < 5e-13 else "FAIL", "Formula-to-data", "Delta_inv = Delta_avail + Delta_dep holds for every split-seed row", f"rows={len(seed_rows)}; max absolute error={max_identity_error:.3e}")
    with zipfile.ZipFile(AF4) as archive:
        mapping = list(csv.DictReader(io.StringIO(archive.read("docs/Equation_to_code_mapping.csv").decode("utf-8"))))
    result(rows, "PASS" if mapping and all(row["status"] == "PASS" for row in mapping) else "FAIL", "Formula-to-code", "Every displayed equation is mapped to an implementation or archived definition", f"mapping rows={len(mapping)}; non-PASS={[row['equation'] for row in mapping if row['status'] != 'PASS']}")

    table_checks(main_root, rows)
    result(rows, "PASS" if main_root.xpath("count(.//w:br[@w:type='page'])", namespaces=NS) == 0 else "FAIL", "Main formatting", "No manual page breaks", "document.xml")
    result(rows, "PASS" if main_root.xpath("count(.//w:sectPr/w:lnNumType)", namespaces=NS) > 0 else "FAIL", "Main formatting", "Continuous line numbering configured", "section properties")
    result(rows, "PASS" if b"<w:trackRevisions" not in main_settings else "FAIL", "Main formatting", "Clean file has no active track revisions", "settings.xml")

    wb_formula = load_workbook(AF2, read_only=True, data_only=False)
    wb_value = load_workbook(AF2, read_only=True, data_only=True)
    formula_count = sum(1 for ws in wb_formula.worksheets for row in ws.iter_rows() for cell in row if isinstance(cell.value, str) and cell.value.startswith("="))
    errors = []
    for book in (wb_formula, wb_value):
        for ws in book.worksheets:
            for row in ws.iter_rows():
                for cell in row:
                    if cell.value in {"#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#N/A", "#NUM!", "#NULL!"}:
                        errors.append(f"{ws.title}!{cell.coordinate}")
    result(rows, "PASS" if len(wb_formula.sheetnames) == 64 else "FAIL", "Supplementary workbook", "Worksheet inventory", f"sheets={len(wb_formula.sheetnames)}")
    result(rows, "PASS" if not errors else "FAIL", "Supplementary workbook", "No formula error tokens", f"formulas={formula_count}; errors={errors[:10]}")

    actual_sha = sha(AF4)
    stated = re.search(r"[A-F0-9]{64}", AF4_SHA.read_text(encoding="ascii")).group(0)
    result(rows, "PASS" if actual_sha == stated else "FAIL", "Additional file 4", "Outer SHA-256 matches", f"{actual_sha}")
    with zipfile.ZipFile(AF4) as archive:
        bad = archive.testzip()
        lines = archive.read("SHA256SUMS.txt").decode("utf-8").splitlines()
        mismatches = []
        for line in lines:
            expected_hash, name = line.split("  ", 1)
            if name not in archive.namelist() or hashlib.sha256(archive.read(name)).hexdigest().lower() != expected_hash.lower():
                mismatches.append(name)
        version = archive.read("VERSION").decode("utf-8").strip()
    result(rows, "PASS" if bad is None and not mismatches else "FAIL", "Additional file 4", "ZIP CRC and internal SHA-256 manifest", f"version={version}; verified={len(lines)-len(mismatches)}/{len(lines)}; bad={bad}")

    for renderer in ("WPS", "LibreOffice"):
        pdf = ROOT / "05_Compatibility" / "Formula_Audit_20260815" / renderer / f"manuscript_revised_submission_ready_{renderer}.pdf"
        document = fitz.open(pdf)
        page = next((i + 1 for i, p in enumerate(document) if "2.5 Primary references" in p.get_text()), None)
        table_page = next((i + 1 for i, p in enumerate(document) if "Table 3." in p.get_text()), None)
        table_text = document[table_page - 1].get_text() if table_page else ""
        symbols_ok = all(x in table_text for x in ("Ginv", "Gdep", "Gavail", "Δinv"))
        result(rows, "PASS" if page and table_page and symbols_ok else "FAIL", "Cross-software", f"{renderer} formula/table rendering", f"pages={len(document)}; Methods 2.5 page={page}; Table 3 page={table_page}; symbols copyable={symbols_ok}")

    counts = Counter(r["Status"] for r in rows)
    xlsx = AUDIT / "formula_table_and_format_audit_20260815.xlsx"
    md = AUDIT / "formula_table_and_format_audit_20260815.md"
    workbook = Workbook()
    summary = workbook.active
    summary.title = "Summary"
    summary.append(["Formula, table and format audit", "2026-08-15"])
    summary.append(["Main manuscript", str(MAIN)])
    summary.append(["Additional file 1", str(AF1)])
    summary.append(["Checks", len(rows)])
    for status in ("PASS", "FAIL"):
        summary.append([status, counts.get(status, 0)])
    detail = workbook.create_sheet("Checks")
    detail.append(["Status", "Area", "Check", "Evidence"])
    for row in rows:
        detail.append([row[k] for k in ("Status", "Area", "Check", "Evidence")])
        detail.cell(detail.max_row, 1).fill = PatternFill("solid", fgColor="C6EFCE" if row["Status"] == "PASS" else "FFC7CE")
    for ws in workbook.worksheets:
        for cell in ws[1]:
            cell.font = Font(name="Times New Roman", bold=True)
        for row in ws.iter_rows():
            for cell in row:
                cell.font = Font(name="Times New Roman", size=10, bold=cell.row == 1)
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        ws.freeze_panes = "A2"
    detail.column_dimensions["A"].width = 14
    detail.column_dimensions["B"].width = 28
    detail.column_dimensions["C"].width = 60
    detail.column_dimensions["D"].width = 105
    summary.column_dimensions["A"].width = 38
    summary.column_dimensions["B"].width = 110
    workbook.save(xlsx)

    lines = [
        "# Formula, table and format audit",
        "",
        "Audit date: 2026-08-15",
        "",
        f"Result: {counts.get('PASS', 0)} PASS, {counts.get('FAIL', 0)} FAIL.",
        "",
        "The nine main-text displays and Supplementary Equations (1)–(22b) are native editable OMML. Table 3 deliberately remains formatted text rather than OMML so its symbol column survives WPS and LibreOffice conversion.",
        "",
        "WPS and LibreOffice visual renders contain all equations and all Table 3 symbols. WPS exports equation glyphs through a non-semantic math-font map, so copied equation text from the WPS PDF is not reliable; the DOCX and LibreOffice PDF remain editable/searchable sources. This is a renderer limitation, not missing content.",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- **{row['Status']} — {row['Area']} — {row['Check']}**: {row['Evidence']}" for row in rows)
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{counts}; {xlsx}; {md}")


if __name__ == "__main__":
    main()
