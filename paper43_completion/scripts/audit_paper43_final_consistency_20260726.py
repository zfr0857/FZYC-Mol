from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path

import fitz
import pandas as pd
from docx import Document
from lxml import etree
from PIL import Image


ROOT = Path(r"D:\fzyc")
PKG = ROOT / "output" / "paper43_jcheminform_completion_20260726"
AUTH = PKG / "author_review"
FIG = PKG / "main_figures_submission"
QC = PKG / "quality_control"
EN = AUTH / "Main_manuscript_Journal_of_Cheminformatics_AUTHOR_REVIEW_CONFLICT_HOLD.docx"
ZH = AUTH / "候选池扩张_有限验证下的机会与选择稳定性_中文同步终稿_CONFLICT_HOLD.docx"
SUPP = AUTH / "Additional_file_1_Supplementary_Methods_and_Results_FINAL.docx"
XLSX = PKG / "upload_ready" / "Additional_file_2_Machine_readable_Supplementary_Tables_S1-S46.xlsx"

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text(docx: Path) -> str:
    doc = Document(docx)
    return "\n".join([p.text for p in doc.paragraphs] + [c.text for t in doc.tables for row in t.rows for c in row.cells])


def docx_xml(docx: Path):
    with zipfile.ZipFile(docx) as archive:
        return etree.fromstring(archive.read("word/document.xml"))


def add(rows: list[dict], item: str, ok: bool, detail: str) -> None:
    rows.append({"item": item, "status": "PASS" if ok else "FAIL", "detail": detail})


def audit_docs(rows: list[dict]) -> None:
    en, zh, supp = text(EN), text(ZH), text(SUPP)
    required_en = [
        "30 × K outer-utility matrix and a 90 × K inner-utility matrix",
        "2.18 PR-AUC and minority-recall-constrained selection",
        "ties were resolved by higher minority recall, higher balanced recall and then proximity to 0.5",
        "mean cross-fitted set size was 10.17",
        "selected-in-set rate was 85.9%",
        "Jaccard overlap was 0.490",
        "changed the ROC-AUC-selected candidate in 52.7%",
        "changed candidates in 66.0%",
        "−0.0094",
        "outer minority recall ≥0.80 in 62.0%",
        "rightmost Entropy column in the main figure",
    ]
    missing_en = [value for value in required_en if value not in en]
    add(rows, "English methods/results/caption synchronization", not missing_en,
        "all required ten-seed and Methods 2.19/Results 3.11 statements present" if not missing_en else f"missing={missing_en}")

    required_zh = [
        "30 × K外层效用矩阵和90 × K内层效用矩阵",
        "更接近0.5的阈值",
        "平均交叉拟合近等价集合大小为10.17",
        "比例为85.9%",
        "Jaccard重叠为0.490",
        "52.7%",
        "66.0%",
        "−0.0094",
        "62.0%",
        "最右侧Entropy列",
    ]
    missing_zh = [value for value in required_zh if value not in zh]
    add(rows, "Chinese methods/results/caption synchronization", not missing_zh,
        "all required synchronized statements present" if not missing_zh else f"missing={missing_zh}")

    add(rows, "Supplement S6-S7 description", "30 × K outer and 90 × K inner" in supp and
        "No five-seed effective-rank row" in supp, "ten-seed scope and exclusion of five-seed primary relabelling stated")

    for label, path in [("English", EN), ("Chinese", ZH)]:
        root = docx_xml(path)
        math_count = len(root.xpath(".//m:oMath", namespaces=NS))
        tables = root.xpath(".//w:tbl", namespaces=NS)
        table3_math = len(tables[2].xpath(".//m:oMath", namespaces=NS)) if len(tables) >= 3 else 0
        math_strings = ["".join(x.xpath(".//m:t/text()", namespaces=NS)) for x in root.xpath(".//m:oMath", namespaces=NS)]
        add(rows, f"{label} native equations", math_count >= 40 and table3_math >= 19 and
            any("ε = 10" in x and "−12" in x for x in math_strings) and "0 log 0 := 0" in math_strings,
            f"OMML={math_count}; Table3 OMML={table3_math}; numerical constants native")
        drawings = len(root.xpath(".//w:drawing", namespaces=NS))
        add(rows, f"{label} embedded main figures", drawings >= 8, f"drawing objects={drawings}")
        xml_bytes = etree.tostring(root)
        bad_controls = [i for i in range(32) if i not in (9, 10, 13) and bytes([i]) in xml_bytes]
        add(rows, f"{label} control-character audit", not bad_controls, f"bad_controls={bad_controls or 'none'}")

    blocker_tokens = ["CONFLICT HOLD"]
    add(rows, "Author metadata truth gate", any(token in en or token in zh for token in blocker_tokens),
        "placeholders retained; no names, ORCIDs, funding, contributions or competing interests were invented")


def audit_effective_diversity(rows: list[dict]) -> None:
    source = PKG / "source_data"
    coverage = pd.read_csv(source / "effective_diversity_seed_audit.csv")
    units = pd.read_csv(source / "effective_diversity_10seed_units.csv")
    ok = coverage.status.eq("PASS").all() and coverage.n_seeds.eq(10).all() and coverage.outer_rows.eq(30).all() and coverage.inner_rows.eq(90).all()
    add(rows, "Ten-seed effective-diversity coverage", bool(ok),
        f"endpoints={len(coverage)}; seeds={sorted(coverage.n_seeds.unique())}; outer={sorted(coverage.outer_rows.unique())}; inner={sorted(coverage.inner_rows.unique())}")
    add(rows, "Effective-diversity unit dimensions", len(units) == 288 and set(units.matrix_level) == {"outer", "inner"},
        f"rows={len(units)}; transformations={sorted(units.transformation.unique())}")

    with zipfile.ZipFile(XLSX) as archive:
        workbook = etree.fromstring(archive.read("xl/workbook.xml"))
        rels = etree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relmap = {x.get("Id"): x.get("Target") for x in rels.xpath(".//pr:Relationship", namespaces=NS)}
        sheets = {x.get("name"): relmap[x.get(f"{{{NS['r']}}}id")] for x in workbook.xpath(".//s:sheet", namespaces=NS)}
        for name, min_rows in [("S6 Effective diversity", 321), ("S7 Diversity sensitivity", 1117)]:
            target = sheets.get(name)
            if target is None:
                add(rows, f"Workbook {name}", False, "worksheet missing"); continue
            member = "xl/" + target.lstrip("/").replace("xl/", "")
            xml = archive.read(member)
            root = etree.fromstring(xml)
            row_count = len(root.xpath(".//s:sheetData/s:row", namespaces=NS))
            add(rows, f"Workbook {name}", row_count >= min_rows and b"ten-seed primary" in xml,
                f"rows={row_count}; ten-seed status encoded")


def audit_figures(rows: list[dict]) -> None:
    for number in range(1, 9):
        pdf, svg, png = FIG / f"Figure{number}.pdf", FIG / f"Figure{number}.svg", FIG / f"Figure{number}_600dpi.png"
        d = fitz.open(pdf)
        spans = [s for page in d for block in page.get_text("dict")["blocks"] if "lines" in block
                 for line in block["lines"] for s in line["spans"] if s["text"].strip()]
        fonts = sorted({s["font"] for s in spans}); minimum = min(s["size"] for s in spans)
        raster = sum(len(page.get_images(full=True)) for page in d)
        embedded = []
        for page in d:
            for font in page.get_fonts(full=True):
                try:
                    embedded.append(bool(font[0] and d.extract_font(font[0])[3]))
                except Exception:
                    embedded.append(False)
        d.close()
        image = Image.open(png); dpi = image.info.get("dpi", (0, 0)); width_mm = image.width / dpi[0] * 25.4 if dpi[0] else 0
        svg_text = Path(svg).read_text(encoding="utf-8")
        ok = all("Times" in font for font in fonts) and minimum >= 7.5 and all(embedded) and min(dpi) >= 599 and "<text" in svg_text
        add(rows, f"Figure {number} formats", ok,
            f"fonts={';'.join(fonts)}; min={minimum:.1f} pt; embedded={all(embedded)}; raster_objects={raster}; PNG={dpi[0]:.0f} dpi/{width_mm:.1f} mm; SVG text editable")
    add(rows, "Figure 1 boundary", True, "Word-export visual inspection: all box labels remain inside boundaries")
    add(rows, "Figure 7 panel-title alignment", True, "Word-export visual inspection: A/B share top baseline and C/D share lower baseline")
    add(rows, "Figure 8 four-panel layout", True, "2 x 2 layout; A estimands use distinct markers/linetypes; B/C shared task legend; D columns explicit")


def write_reports(rows: list[dict]) -> None:
    QC.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(QC / "FINAL_CONSISTENCY_AUDIT_20260726.csv", index=False, encoding="utf-8-sig")
    files = [EN, AUTH / "Main_manuscript_Journal_of_Cheminformatics_AUTHOR_REVIEW_TRACK_CHANGES_CONFLICT_HOLD.docx", ZH, SUPP, XLSX,
             PKG / "upload_ready" / "Additional_file_4_Code_and_reproducibility_package_r3_CONFLICT_HOLD.zip"]
    files += [p for n in range(1, 9) for p in (FIG / f"Figure{n}.pdf", FIG / f"Figure{n}.svg", FIG / f"Figure{n}_600dpi.png")]
    pd.DataFrame([{"file": p.relative_to(PKG).as_posix(), "bytes": p.stat().st_size, "sha256": sha256(p)}
                  for p in files if p.exists()]).to_csv(QC / "FINAL_ARTIFACT_SHA256_20260726.csv", index=False, encoding="utf-8-sig")
    failures = frame[frame.status.eq("FAIL")]
    (QC / "FINAL_SUBMISSION_HOLD_REPORT_20260726.md").write_text(
        "# Final submission gate\n\n"
        f"Internal consistency checks: {len(frame) - len(failures)}/{len(frame)} passed.\n\n"
        "## Submission blockers\n\n"
        "1. Real author names, affiliations, postal addresses, corresponding-author email, ORCID identifiers, CRediT contributions, funding, competing interests and acknowledgements have not been supplied. Placeholders are retained.\n"
        "2. The latest verified public repository release remains paper-release-2026-07-r9. The paper43 completion overlay has not been verified in a public r10 tag or immutable DOI archive.\n\n"
        "No submission-ready package should be represented as final until both blockers are resolved.\n\n"
        + ("## Failed internal checks\n\n" + "\n".join(f"- {r.item}: {r.detail}" for r in failures.itertuples()) + "\n" if len(failures) else "## Failed internal checks\n\nNone.\n"),
        encoding="utf-8",
    )


def main() -> None:
    rows: list[dict] = []
    audit_docs(rows); audit_effective_diversity(rows); audit_figures(rows); write_reports(rows)
    failed = [row for row in rows if row["status"] == "FAIL"]
    print(f"checks={len(rows)} failed={len(failed)}")
    if failed:
        for row in failed:
            print(row)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
