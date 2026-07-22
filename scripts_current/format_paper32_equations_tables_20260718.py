from __future__ import annotations

import copy
import json
import re
import shutil
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree


ROOT = Path(r"D:\fzyc")
SOURCE = ROOT / "output" / "paper31_submission_package_20260717"
OUT = ROOT / "output" / "paper32_equation_table_format_20260718"

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NS = {"w": W, "m": M}
qn = etree.QName

GROUPS = [
    [1, 2], [3, 4], [5, 6], [7, 8], [9], [10, 11], [12, 13],
    [14, 15], [16, 17], [18, 19], [20, 21], [22, 23], [24, 25], [26, 27],
]
TARGET_OVERRIDE = {22: 23, 24: 25}


def node_text(node: etree._Element) -> str:
    return "".join(node.xpath(".//w:t/text()|.//m:t/text()", namespaces=NS))


def set_child(parent: etree._Element, tag: str, **attrs: str) -> etree._Element:
    child = parent.find(f"w:{tag}", NS)
    if child is None:
        child = etree.SubElement(parent, qn(W, tag))
    for key, value in attrs.items():
        child.set(qn(W, key), value)
    return child


def clean_math(math: etree._Element) -> etree._Element:
    result = copy.deepcopy(math)
    texts = result.xpath(".//m:t", namespaces=NS)
    if texts and texts[-1].text:
        texts[-1].text = re.sub(r"[,.]\s*$", "", texts[-1].text)
    return result


def separator() -> etree._Element:
    run = etree.Element(qn(M, "r"))
    text = etree.SubElement(run, qn(M, "t"))
    text.text = "   ;   "
    return run


def centred_equation_paragraph(template: etree._Element, maths: list[etree._Element]) -> etree._Element:
    paragraph = copy.deepcopy(template)
    for child in list(paragraph):
        if child.tag != qn(W, "pPr"):
            paragraph.remove(child)
    ppr = paragraph.find("w:pPr", NS)
    if ppr is None:
        ppr = etree.Element(qn(W, "pPr"))
        paragraph.insert(0, ppr)
    for tag in ["tabs", "jc", "spacing"]:
        old = ppr.find(f"w:{tag}", NS)
        if old is not None:
            ppr.remove(old)
    etree.SubElement(ppr, qn(W, "keepLines")) if ppr.find("w:keepLines", NS) is None else None
    spacing = etree.SubElement(ppr, qn(W, "spacing"))
    spacing.set(qn(W, "before"), "100")
    spacing.set(qn(W, "after"), "100")
    jc = etree.SubElement(ppr, qn(W, "jc"))
    jc.set(qn(W, "val"), "center")

    math_para = etree.SubElement(paragraph, qn(M, "oMathPara"))
    math_para_pr = etree.SubElement(math_para, qn(M, "oMathParaPr"))
    math_jc = etree.SubElement(math_para_pr, qn(M, "jc"))
    math_jc.set(qn(M, "val"), "center")
    merged = etree.SubElement(math_para, qn(M, "oMath"))
    for index, math in enumerate(maths):
        if index:
            merged.append(separator())
        for child in clean_math(math):
            merged.append(copy.deepcopy(child))
    return paragraph


def replace_text(tree: etree._Element, replacements: dict[str, str]) -> None:
    for paragraph in tree.xpath(".//w:p", namespaces=NS):
        texts = paragraph.xpath(".//w:t", namespaces=NS)
        if not texts:
            continue
        combined = "".join(t.text or "" for t in texts)
        updated = combined
        for old, new in replacements.items():
            updated = updated.replace(old, new)
        if updated != combined:
            texts[0].text = updated
            for extra in texts[1:]:
                extra.text = ""


def merge_equations(tree: etree._Element, language: str) -> tuple[int, int]:
    body = tree.find(".//w:body", NS)
    assert body is not None
    records: dict[int, dict[str, etree._Element]] = {}
    for container in list(body):
        maths = container.xpath(".//m:oMath", namespaces=NS)
        if not maths:
            continue
        match = re.search(r"\((\d+)\)\s*$", node_text(container))
        if not match:
            continue
        number = int(match.group(1))
        math = maths[0]
        paragraph = next((ancestor for ancestor in math.iterancestors(qn(W, "p"))), None)
        assert paragraph is not None
        records[number] = {"container": container, "paragraph": paragraph, "math": math}
    assert set(records) == set(range(1, 28)), sorted(records)

    retained: set[etree._Element] = set()
    for group in GROUPS:
        target_number = TARGET_OVERRIDE.get(group[0], group[0])
        record = records[target_number]
        target_container = record["container"]
        assert target_container.tag == qn(W, "p")
        group_maths = [copy.deepcopy(records[number]["math"]) for number in group]
        if set(group) == {26, 27}:
            for math in group_maths:
                for text_node in math.xpath(".//m:t", namespaces=NS):
                    if text_node.text == "q":
                        text_node.text = "π"
        new_paragraph = centred_equation_paragraph(
            record["paragraph"], group_maths
        )
        body.replace(target_container, new_paragraph)
        retained.add(new_paragraph)

    source_containers = {record["container"] for record in records.values()}
    for container in list(body):
        if container in source_containers:
            body.remove(container)

    replacements_en = {
        "S in Equation 16": "S in the Ledoit-Wolf covariance expression",
        "q_j is the proportion": "π_j is the proportion",
        "rank cutoff q in Equation 5": "rank cutoff q in the CAHit@q definition",
        "Equations 22 and 24 divide": "The paired normalized gain and cross-fitted-gap expressions divide",
    }
    replacements_zh = {
        "公式（16）中的 S": "Ledoit-Wolf 协方差表达式中的 S",
        "此处 q_j 为": "此处 π_j 为",
        "与公式（5）的排序截断 q 不同": "与 CAHit@q 定义中的排序截断 q 不同",
        "公式（22）和（24）先在": "配对归一化增益与交叉拟合差距表达式先在",
    }
    replace_text(tree, replacements_en if language == "en" else replacements_zh)
    final_count = len(tree.xpath(".//m:oMath", namespaces=NS))
    equation_tables = len(tree.xpath(".//w:body/w:tbl[.//m:oMath]", namespaces=NS))
    assert final_count == len(GROUPS) and equation_tables == 0, (final_count, equation_tables)
    return final_count, equation_tables


def border(parent: etree._Element, edge: str, value: str, size: str = "0") -> None:
    element = etree.SubElement(parent, qn(W, edge))
    element.set(qn(W, "val"), value)
    if value != "nil":
        element.set(qn(W, "sz"), size)
        element.set(qn(W, "space"), "0")
        element.set(qn(W, "color"), "000000")


def set_paragraph_alignment(paragraph: etree._Element, value: str) -> None:
    ppr = paragraph.find("w:pPr", NS)
    if ppr is None:
        ppr = etree.Element(qn(W, "pPr"))
        paragraph.insert(0, ppr)
    old = ppr.find("w:jc", NS)
    if old is not None:
        ppr.remove(old)
    jc = etree.SubElement(ppr, qn(W, "jc"))
    jc.set(qn(W, "val"), value)
    spacing = ppr.find("w:spacing", NS)
    if spacing is None:
        spacing = etree.SubElement(ppr, qn(W, "spacing"))
    spacing.set(qn(W, "before"), "0")
    spacing.set(qn(W, "after"), "0")
    spacing.set(qn(W, "line"), "240")
    spacing.set(qn(W, "lineRule"), "auto")


def format_three_line_tables(tree: etree._Element) -> int:
    tables = tree.xpath(".//w:body/w:tbl[not(.//m:oMath)]", namespaces=NS)
    for table in tables:
        rows = table.xpath("./w:tr", namespaces=NS)
        if len(rows) < 2:
            continue
        tblpr = table.find("w:tblPr", NS)
        if tblpr is None:
            tblpr = etree.Element(qn(W, "tblPr"))
            table.insert(0, tblpr)
        style = tblpr.find("w:tblStyle", NS)
        if style is not None:
            tblpr.remove(style)
        old_borders = tblpr.find("w:tblBorders", NS)
        if old_borders is not None:
            tblpr.remove(old_borders)
        borders = etree.SubElement(tblpr, qn(W, "tblBorders"))
        border(borders, "top", "single", "10")
        border(borders, "left", "nil")
        border(borders, "bottom", "single", "10")
        border(borders, "right", "nil")
        border(borders, "insideH", "nil")
        border(borders, "insideV", "nil")
        alignment = tblpr.find("w:jc", NS)
        if alignment is None:
            alignment = etree.SubElement(tblpr, qn(W, "jc"))
        alignment.set(qn(W, "val"), "center")

        header = rows[0]
        trpr = header.find("w:trPr", NS)
        if trpr is None:
            trpr = etree.Element(qn(W, "trPr"))
            header.insert(0, trpr)
        if trpr.find("w:tblHeader", NS) is None:
            etree.SubElement(trpr, qn(W, "tblHeader"))

        headers = [node_text(cell).strip() for cell in header.xpath("./w:tc", namespaces=NS)]
        for row_index, row in enumerate(rows):
            cells = row.xpath("./w:tc", namespaces=NS)
            for col_index, cell in enumerate(cells):
                tcpr = cell.find("w:tcPr", NS)
                if tcpr is None:
                    tcpr = etree.Element(qn(W, "tcPr"))
                    cell.insert(0, tcpr)
                for tag in ["tcBorders", "shd"]:
                    old = tcpr.find(f"w:{tag}", NS)
                    if old is not None:
                        tcpr.remove(old)
                if row_index == 0:
                    cell_borders = etree.SubElement(tcpr, qn(W, "tcBorders"))
                    border(cell_borders, "bottom", "single", "6")
                valign = tcpr.find("w:vAlign", NS)
                if valign is None:
                    valign = etree.SubElement(tcpr, qn(W, "vAlign"))
                valign.set(qn(W, "val"), "center")

                content = node_text(cell).strip()
                numeric = bool(re.fullmatch(r"[\d\s.,%()\-+/:]+", content))
                centre_column = col_index < len(headers) and headers[col_index] in {"n", "Direction", "方向"}
                align = "center" if row_index == 0 or numeric or centre_column else "left"
                for paragraph in cell.xpath("./w:p", namespaces=NS):
                    set_paragraph_alignment(paragraph, align)
                    if row_index == 0:
                        for run in paragraph.xpath(".//w:r", namespaces=NS):
                            rpr = run.find("w:rPr", NS)
                            if rpr is None:
                                rpr = etree.Element(qn(W, "rPr"))
                                run.insert(0, rpr)
                            if rpr.find("w:b", NS) is None:
                                etree.SubElement(rpr, qn(W, "b"))
        # Keep rows intact where possible; long tables may still split naturally between rows.
        for row in rows:
            trpr = row.find("w:trPr", NS)
            if trpr is None:
                trpr = etree.Element(qn(W, "trPr"))
                row.insert(0, trpr)
            if trpr.find("w:cantSplit", NS) is None:
                etree.SubElement(trpr, qn(W, "cantSplit"))
    return len([t for t in tables if len(t.xpath("./w:tr", namespaces=NS)) >= 2])


def pack_dir(source: Path, destination: Path) -> None:
    with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source).as_posix())


def process(source: Path, destination: Path, language: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="paper32_docx_") as tmp:
        unpacked = Path(tmp)
        with ZipFile(source) as archive:
            archive.extractall(unpacked)
        xml_path = unpacked / "word" / "document.xml"
        parser = etree.XMLParser(remove_blank_text=False)
        tree = etree.parse(str(xml_path), parser)
        equations, equation_tables = merge_equations(tree.getroot(), language)
        data_tables = format_three_line_tables(tree.getroot())
        tree.write(str(xml_path), encoding="UTF-8", xml_declaration=True, standalone=True)
        pack_dir(unpacked, destination)
    return {
        "source": str(source),
        "output": str(destination),
        "displayed_equation_blocks": equations,
        "equation_layout_tables": equation_tables,
        "three_line_data_tables": data_tables,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    english = SOURCE / "Candidate_pool_expansion_Journal_of_Cheminformatics_manuscript(7).docx"
    chinese = next(
        path for path in SOURCE.glob("*.docx")
        if not path.name.startswith(("Candidate", "Reviewer"))
    )
    results = [
        process(
            english,
            OUT / "Candidate_pool_expansion_Journal_of_Cheminformatics_equations_tables_formatted.docx",
            "en",
        ),
        process(chinese, OUT / "Chinese_manuscript_equations_tables_formatted.docx", "zh"),
    ]
    (OUT / "Equation_and_three_line_table_formatting_audit.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    main()
