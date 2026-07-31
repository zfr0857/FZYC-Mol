from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
import shutil
import sys

from lxml import etree

sys.path.insert(0, r"D:\fzyc\scripts")
from revise_chinese_final_round_20260728 import formulae, fonts_rpr, text_run  # noqa: E402

ROOT = Path(r"D:\fzyc\work\english_final_round_20260728")
DOC = ROOT / "word" / "document.xml"
RELS = ROOT / "word" / "_rels" / "document.xml.rels"
FIGURE4 = Path(r"D:\fzyc\work\figure4_20260728\Figure4_600dpi.png")

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"w": W, "m": M, "wp": WP, "a": A, "r": R, "pr": PR}
Q = lambda ns, name: f"{{{ns}}}{name}"


def ptext(paragraph: etree._Element) -> str:
    return "".join(paragraph.xpath(".//w:t/text()", namespaces=NS))


def replace_text(paragraph: etree._Element, value: str) -> None:
    for child in list(paragraph):
        if child.tag != Q(W, "pPr"):
            paragraph.remove(child)
    paragraph.append(text_run(value))


def convert_simple_inline_math(document: etree._Element) -> int:
    symbol_table = document.xpath("//w:tbl", namespaces=NS)[2]
    count = 0
    for paragraph in document.xpath("//w:p[.//m:oMath]", namespaces=NS):
        if re.fullmatch(r"\(\d+\)", ptext(paragraph).strip()) or symbol_table in paragraph.iterancestors():
            continue
        for equation in list(paragraph.xpath(".//m:oMath", namespaces=NS)):
            compact = re.sub(r"\s+", "", "".join(equation.xpath(".//m:t/text()", namespaces=NS)))
            value = {"ε=10−12": "ε = 10^−12", "ε=10-12": "ε = 10^−12", "0log0:=0": "0 log 0 := 0"}.get(compact, compact)
            parent = equation.getparent(); position = parent.index(equation)
            parent.remove(equation); parent.insert(position, text_run(value)); count += 1
    return count


def rebuild_equations(document: etree._Element) -> None:
    replacements = formulae()
    for paragraph in document.xpath("//w:p[.//m:oMath]", namespaces=NS):
        match = re.fullmatch(r"\((\d+)\)", ptext(paragraph).strip())
        if not match:
            continue
        number = int(match.group(1))
        if number in replacements:
            current = paragraph.find("m:oMath", NS)
            paragraph.replace(current, replacements[number])


def insert_definition(document: etree._Element) -> None:
    paragraph = next(p for p in document.xpath("//w:p", namespaces=NS) if ptext(p).startswith("The reference-training set contains"))
    original = ptext(paragraph)
    prefix = "Let U_{−s} denote the outer audit units from seeds other than held-out seed s and define N_{−s} = |U_{−s}|. "
    if not original.startswith("Let U_{−s}"):
        replace_text(paragraph, prefix + original)


def insert_conclusion(document: etree._Element) -> None:
    body = document.find("w:body", NS)
    if any(ptext(p) == "5 Conclusions" for p in body.findall("w:p", NS)):
        return
    anchor = next(p for p in body.findall("w:p", NS) if ptext(p).startswith("Within the evaluated endpoints, candidate registries and split mechanisms"))
    template = next(p for p in body.findall("w:p", NS) if ptext(p) == "4 Discussion")
    heading = deepcopy(template)
    replace_text(heading, "5 Conclusions")
    anchor.addprevious(heading)


def revise_figure4_caption(document: etree._Element) -> None:
    paragraph = next(p for p in document.xpath("//w:p", namespaces=NS) if ptext(p).startswith("Figure 4. Selection-gap decomposition and winner optimism"))
    value = (
        "Figure 4. Selection-gap decomposition and winner optimism. Panels A and B compare observed audit-best and validation-selected gains for classification and regression. "
        "Panel C contrasts the same-fold finite-set opportunity gap with the K-dependent within-prefix cross-fitted gap as a secondary decomposition or sensitivity analysis; the primary K-invariant full-registry completion-gap estimate is shown in Figure 3C. "
        "For visualization across endpoints, panel C uses within-endpoint standardized effects; raw ROC-AUC and RMSE effects are listed separately. Panel D shows finite-audit winner optimism when candidate true utilities are equal."
    )
    replace_text(paragraph, value)


def split_table3(document: etree._Element) -> None:
    body = document.find("w:body", NS)
    table = body.findall("w:tbl", NS)[2]
    if table.get(Q(W, "rsidR")) == "TABLE3_SPLIT":
        return
    rows = table.findall("w:tr", NS)
    second = deepcopy(table)
    for row in rows[12:]: table.remove(row)
    for row in second.findall("w:tr", NS)[1:12]: second.remove(row)
    table.set(Q(W, "rsidR"), "TABLE3_SPLIT"); second.set(Q(W, "rsidR"), "TABLE3_CONT")
    table.find("w:tblPr/w:tblBorders/w:bottom", NS).set(Q(W, "val"), "nil")
    original_caption = next(p for p in body.findall("w:p", NS) if ptext(p).startswith("Table 3. Mathematical notation"))
    caption = deepcopy(original_caption)
    replace_text(caption, "Table 3 (continued). Mathematical notation used in the audit estimands.")
    ppr = caption.find("w:pPr", NS)
    if ppr is None:
        ppr = etree.Element(Q(W, "pPr")); caption.insert(0, ppr)
    if ppr.find("w:keepNext", NS) is None: etree.SubElement(ppr, Q(W, "keepNext"))
    if ppr.find("w:pageBreakBefore", NS) is None: etree.SubElement(ppr, Q(W, "pageBreakBefore"))
    index = body.index(table); body.insert(index + 1, caption); body.insert(index + 2, second)


ALT_TEXT = [
    "Figure 1 maps the evidence hierarchy from candidate registration and repeated nested scaffold audit to decomposition and robustness reporting. It distinguishes K-invariant, K-dependent and same-fold quantities and links them to practical equivalence, selection stability, compute and chemical support.",
    "Figure 2 compares effective candidate diversity under four utility-matrix constructions in the ten-seed audit. Entropy rank, participation-ratio rank, candidate correlation and fixed-reference-relative estimates show that nominal candidate count is not equivalent to effective diversity.",
    "Figure 3 evaluates chance-adjusted ranking fidelity and the primary K-invariant full-registry completion-gap contrast. Recovery simulations and composition controls show heterogeneous endpoint directions as candidate count and registry composition change.",
    "Figure 4 separates observed opportunity, validation realization and finite-audit winner optimism. Panel C is a secondary sensitivity comparison of the same-fold finite-set opportunity gap and the K-dependent within-prefix gap; the primary K-invariant estimate is in Figure 3C.",
    "Figure 5 compares endpoint-specific gains from representation combinations at matched candidate counts. The panels cover all registered subsets, mutually exclusive composition classes, candidate-count ladders and standardized endpoint effects.",
    "Figure 6 summarizes predictive reliability near chemical-support boundaries. Correlation, error overlap, support-stratified risk and four-model trade-offs show that extrapolation reduces reliability and that performance and safety metrics need not move together.",
    "Figure 7 contrasts homogeneous Morgan, classical multiview and modern-augmented registries in opportunity, ranking fidelity, selection stability and downstream compute. Equal-K and equal-budget conditions retain negative results and show the empirical budget-benefit frontier.",
    "Figure 8 summarizes practical equivalence and metric-dependent selection in the ten-seed primary audit. Four panels show K-invariant, K-dependent and same-fold gaps, equivalence success, near-equivalent-set size, and candidate switching with held-out metric changes.",
]


def update_drawings(document: etree._Element, relationships: etree._Element) -> None:
    drawings = document.xpath("//wp:docPr", namespaces=NS)
    for number, (drawing, description) in enumerate(zip(drawings, ALT_TEXT), 1):
        drawing.set("name", f"Figure {number}"); drawing.set("title", f"Figure {number} alternative text"); drawing.set("descr", description)
    paragraph = document.xpath("//w:p[.//w:drawing]", namespaces=NS)[3]
    rid = paragraph.xpath(".//a:blip/@r:embed", namespaces=NS)[0]
    target = next(rel.get("Target") for rel in relationships.xpath("//pr:Relationship", namespaces=NS) if rel.get("Id") == rid)
    shutil.copy2(FIGURE4, ROOT / "word" / target.replace("/", "\\"))


def main() -> None:
    parser = etree.XMLParser(remove_blank_text=False)
    document = etree.parse(str(DOC), parser).getroot()
    relationships = etree.parse(str(RELS), parser).getroot()
    converted = convert_simple_inline_math(document)
    rebuild_equations(document)
    insert_definition(document)
    insert_conclusion(document)
    revise_figure4_caption(document)
    split_table3(document)
    update_drawings(document, relationships)
    DOC.write_bytes(etree.tostring(document, xml_declaration=True, encoding="UTF-8", standalone="yes"))
    print(f"simple_inline_math_to_text={converted}")
    print("equations_rebuilt=6,7,11; conclusion=yes; table3_split=yes; alt_texts=8")


if __name__ == "__main__":
    main()

