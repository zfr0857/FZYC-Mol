from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
import shutil
import zipfile

from lxml import etree
from PIL import Image


ROOT = Path(r"D:\fzyc")
REVIEW = ROOT / "output" / "paper43_jcheminform_completion_20260726" / "author_review"
WORK = ROOT / "work" / "r11_manuscript_ooxml_20260731"
FIG = ROOT / "work" / "r11_structural_figures_20260731"

EN_SOURCE = REVIEW / "Main_manuscript_Journal_of_Cheminformatics_R10_TECHNICAL_CANDIDATE_CONFLICT_HOLD.docx"
ZH_SOURCE = min(
    (p for p in REVIEW.glob("*R10*CONFLICT_HOLD.docx") if not p.name.startswith("Main_") and p.stat().st_size > 5_000_000),
    key=lambda p: p.stat().st_size,
)
SUPP_SOURCE = REVIEW / "Additional_file_1_Supplementary_Methods_and_Results_FINAL.docx"

EN_OUT = REVIEW / "Main_manuscript_Journal_of_Cheminformatics_R11_STRUCTURAL_TECHNICAL_CANDIDATE_CONFLICT_HOLD.docx"
ZH_OUT = REVIEW / "候选池扩张_有限验证下的机会与选择稳定性_中文稿_R11_结构技术候选版_CONFLICT_HOLD.docx"
SUPP_OUT = REVIEW / "Additional_file_1_Supplementary_Methods_and_Results_R11_STRUCTURAL_TECHNICAL_CANDIDATE_CONFLICT_HOLD.docx"

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"w": W, "m": M, "a": A, "wp": WP, "r": R, "pr": PR}
Q = lambda ns, name: f"{{{ns}}}{name}"


CAPTIONS = {
    "en": {
        1: "Figure 1. Candidate-pool opportunity and selection stability under finite validation. Panels follow a continuous left-to-right, top-to-bottom sequence: (A) task and data registration; (B) fixed-prefix candidate-pool expansion; (C) repeated nested scaffold audit; (D) utility-pattern diversity; (E) chance-adjusted ranking; (F) reference and gap decomposition; (G) split-regime transfer; (H) equal-size candidate-pool composition; (I) finite-audit winner optimism; (J) support-aware reliability; (K) four-model error audit; and (L) auditable evidence record. The primary audit used 10 split seeds, three outer folds and three inner folds, whereas explicitly labelled secondary analyses used five seeds. Candidate-pool expansion changes available opportunity and selection stability; effects remain endpoint-, registry- and support-dependent.",
        3: "Figure 3. Primary K-invariant completion-gap contrasts and secondary calibration analyses. (A) The primary ten-seed endpoint-specific K = 32 minus K = 4 completion-gap contrasts against the fixed K-invariant full-registry reference; classification ROC-AUC and regression RMSE use independent axes, and filled markers denote split-seed sensitivity intervals excluding zero. Panel A uses exactly the estimates and interval limits in Table 4. (B) Five-seed chance-adjusted top-rank recovery with a permutation 95% envelope. (C) Five-seed signal-recovery calibration across injected validation–audit signal levels. (D) Five-seed candidate-composition controls. Panels B–D are secondary calibration or sensitivity analyses and are not pooled with panel A.",
        7: "Figure 7. Expanded candidate-pool composition intervention. (A) At K = 32, normalized selected gain and finite-audit-best opportunity are shown for six prespecified endpoints. (B) Composition-by-K ladders are shown separately for classification and regression. (C) Ranking fidelity reports CAHit@3 for every endpoint, pool and K combination; negative values are retained, a blank separator distinguishes task strata, and normalized selection entropy is reported in Figure S20 rather than duplicated in the main figure. H denotes homogeneous Morgan, MV classical multiview and M modern-augmented. (D) Normalized selected gain and downstream fitting/prediction time are compared under equal-K circles and equal-downstream-budget diamonds. This is an explicitly labelled five-seed secondary analysis.",
        8: "Figure 8. Practical equivalence and metric-dependent selection in the ten-seed primary audit. (A) Classification ROC-AUC and regression RMSE gaps are shown on independent stacked axes. (B) Cross-fitted practical-equivalence success is shown at the retrospectively locked middle tolerances. (C) Mean cross-fitted near-equivalent set size is shown on one axis. (D1) Candidate-switching frequencies for PR-AUC and recall-rule selection and (D2) the corresponding outer performance changes are displayed as separate heat maps with independent numerical scales; colour intensity must not be compared between D1 and D2. Negative minority-recall changes are retained.",
    },
    "zh": {
        1: "图1. 有限验证下的候选池机会与选择稳定性。各面板按从左到右、从上到下连续编号：A，任务与数据登记；B，固定前缀候选池扩张；C，重复嵌套骨架审计；D，效用模式多样性；E，机会校正排序；F，参考与差距分解；G，切分机制迁移；H，等规模候选池组成；I，有限审计赢家乐观性；J，支持感知可靠性；K，四模型误差审计；L，可审计证据记录。主要审计使用10个划分种子、3个外层折和3个内层折；明确标注的次要分析使用5个种子。候选池扩张会改变可获得机会和选择稳定性，其影响仍取决于端点、候选登记表与化学支持。",
        3: "图3. 主要K不变完成差距对比与次要校准分析。A，十种子主要结果：各端点K = 32减K = 4相对于固定K不变完整候选池参考的完成差距对比；分类ROC-AUC与回归RMSE使用独立坐标轴，实心标记表示划分种子敏感性区间不含0。A中的估计值和区间界限与表4完全一致。B，五种子机会校正首位恢复及置换95%包络。C，五种子注入验证—审计信号恢复校准。D，五种子候选组成对照。B–D均为次要校准或敏感性分析，不与A合并。",
        7: "图7. 扩展候选池组成干预。A，K = 32时展示6个预设端点的归一化选择增益与有限审计最佳机会。B，分类与回归分别展示候选池组成随K变化的阶梯。C，报告每个“端点×候选池×K”组合的CAHit@3，保留负值，并以空白行分隔分类和回归端点；标准化选择熵移至图S20，不在主图重复。H表示同质Morgan，MV表示经典多表征，M表示现代增强。D，比较等K圆点与等下游预算菱形条件下的归一化选择增益和下游拟合/预测时间。本图为明确标注的五种子次要分析。",
        8: "图8. 十种子主要审计中的实用等价与指标依赖选择。A，分类ROC-AUC与回归RMSE差距采用相互独立的上下坐标轴。B，展示回顾性锁定中间容差下的交叉拟合实用等价成功率。C，展示交叉拟合近等价候选集的平均大小。D1，展示PR-AUC规则与召回规则的候选切换频率；D2，展示相应的外层性能变化。D1与D2为两张独立热图并使用独立数值尺度，不得跨热图比较颜色深浅；少数类召回负变化完整保留。",
    },
}

FIG_ALT = {
    1: "Continuous A–L map of candidate-pool opportunity and selection stability under finite validation.",
    3: "Four-panel figure with the primary ten-seed K-invariant result in panel A and five-seed secondary analyses in panels B–D.",
    7: "Four-panel candidate-pool composition analysis with CAHit@3 only in panel C; entropy is reported in Figure S20.",
    8: "Four-panel practical-equivalence analysis with separate D1 switching and D2 outer-change heat maps.",
}


def ptext(node):
    return "".join(node.xpath(".//w:t/text() | .//m:t/text()", namespaces=NS))


def wtext(node):
    return "".join(node.xpath(".//w:t/text()", namespaces=NS))


def unzip_docx(path: Path, dest: Path):
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with zipfile.ZipFile(path) as z:
        z.extractall(dest)


def zip_docx(src: Path, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        for p in sorted(src.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(src).as_posix())


def set_paragraph_text(p, text: str):
    rpr = p.find(".//w:rPr", NS)
    for child in list(p):
        if child.tag != Q(W, "pPr"):
            p.remove(child)
    r = etree.SubElement(p, Q(W, "r"))
    if rpr is not None:
        r.append(deepcopy(rpr))
    t = etree.SubElement(r, Q(W, "t"))
    if text.startswith(" ") or text.endswith(" "):
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text


def find_caption(doc, index: int, lang: str):
    drawing_p = doc.xpath("//w:body/w:p[.//w:drawing]", namespaces=NS)[index - 1]
    prefix = f"Figure {index}." if lang == "en" else f"图{index}."
    n = drawing_p.getnext()
    while n is not None:
        if n.tag == Q(W, "p") and ptext(n).startswith(prefix):
            return n
        n = n.getnext()
    raise RuntimeError(f"caption not found: {prefix}")


def replace_figure(root_dir: Path, doc, rels, index: int, source: Path):
    blip = doc.xpath("//a:blip", namespaces=NS)[index - 1]
    rid = blip.get(Q(R, "embed"))
    target = rels.xpath(f"string(//pr:Relationship[@Id='{rid}']/@Target)", namespaces=NS)
    media = root_dir / "word" / target.replace("/", "\\")
    shutil.copy2(source, media)
    fill = blip.getparent()
    crop = fill.find("a:srcRect", NS)
    if crop is not None:
        fill.remove(crop)
    drawing = blip.xpath("ancestor::w:drawing[1]", namespaces=NS)[0]
    extent = drawing.find(".//wp:extent", NS)
    cx = int(extent.get("cx"))
    with Image.open(source) as image:
        cy = round(cx * image.height / image.width)
    extent.set("cy", str(cy))
    for ext in drawing.xpath(".//a:xfrm/a:ext", namespaces=NS):
        ext.set("cx", str(cx)); ext.set("cy", str(cy))
    props = drawing.find(".//wp:docPr", NS)
    props.set("name", f"Figure {index}")
    props.set("title", f"Figure {index}")
    props.set("descr", FIG_ALT[index])


def equation_paragraphs(doc):
    result = {}
    for p in doc.xpath("//w:p[.//m:oMath]", namespaces=NS):
        label = wtext(p).strip()
        if re.fullmatch(r"\(\d+\)", label):
            result[int(label[1:-1])] = p
    return result


def set_equation_label(p, label: str):
    texts = p.xpath(".//w:t", namespaces=NS)
    if not texts:
        raise RuntimeError("equation label missing")
    texts[-1].text = label


def split_direct(p, cut: int, labels: tuple[str, str]):
    p1, p2 = deepcopy(p), deepcopy(p)
    for clone, keep in ((p1, range(0, cut)), (p2, range(cut, 999))):
        om = clone.find(".//m:oMath", NS)
        for i, child in reversed(list(enumerate(list(om)))):
            if i not in keep:
                om.remove(child)
    set_equation_label(p1, labels[0]); set_equation_label(p2, labels[1])
    # A semicolon joined the two original definitions; remove it after splitting.
    if labels == ("(3)", "(4)"):
        first_math = p1.find(".//m:oMath", NS)
        for mt in first_math.xpath(".//m:t", namespaces=NS):
            if mt.text:
                mt.text = mt.text.rstrip(";")
    parent = p.getparent(); idx = parent.index(p)
    parent.remove(p); parent.insert(idx, p1); parent.insert(idx + 1, p2)


def split_eqarr(p, labels: tuple[str, str]):
    p1, p2 = deepcopy(p), deepcopy(p)
    for clone, keep_idx in ((p1, 0), (p2, 1)):
        eq = clone.find(".//m:eqArr", NS)
        es = eq.findall("m:e", NS)
        for i, e in reversed(list(enumerate(es))):
            if i != keep_idx:
                eq.remove(e)
    set_equation_label(p1, labels[0]); set_equation_label(p2, labels[1])
    parent = p.getparent(); idx = parent.index(p)
    parent.remove(p); parent.insert(idx, p1); parent.insert(idx + 1, p2)


def renumber_and_split_equations(doc):
    eq = equation_paragraphs(doc)
    expected = set(range(1, 22))
    if set(eq) != expected:
        raise RuntimeError(f"unexpected equation labels: {sorted(eq)}")
    split_direct(eq[3], 6, ("(3)", "(4)"))
    split_eqarr(eq[9], ("(10a)", "(10b)"))
    split_eqarr(eq[11], ("(12a)", "(12b)"))
    split_eqarr(eq[18], ("(19a)", "(19b)"))
    split_eqarr(eq[19], ("(20a)", "(20b)"))
    split_direct(eq[21], 5, ("(22a)", "(22b)"))
    mapping = {1:"(1)",2:"(2)",4:"(5)",5:"(6)",6:"(7)",7:"(8)",8:"(9)",10:"(11)",12:"(13)",13:"(14)",14:"(15)",15:"(16)",16:"(17)",17:"(18)",20:"(21)"}
    for old, new in mapping.items():
        set_equation_label(eq[old], new)


def synchronize_equation_references(doc, lang: str):
    pairs = (
        [("Equations (1)–(5)", "Equations (1)–(6)"), ("Equations (6)–(13)", "Equations (7)–(14)"),
         ("Equations (14)–(17)", "Equations (15)–(18)"), ("Equations (18)–(21)", "Equations (19a)–(22b)"),
         ("Equation (21)", "Equations (22a)–(22b)"),
         ("Equations (22a)–(22b) defines", "Equations (22a)–(22b) define")]
        if lang == "en" else
        [("公式（1）–（5）", "公式（1）–（6）"), ("公式（6）–（13）", "公式（7）–（14）"),
         ("公式（14）–（17）", "公式（15）–（18）"), ("公式（18）–（21）", "公式（19a）–（22b）"),
         ("公式（21）", "公式（22a）–（22b）")]
    )
    for p in doc.xpath("//w:body/w:p[not(.//w:drawing)]", namespaces=NS):
        old = ptext(p); new = old
        for a, b in pairs:
            new = new.replace(a, b)
        if new != old:
            set_paragraph_text(p, new)


def update_body_cross_references(doc, lang: str):
    pairs = (
        [("Figure 3A–B", "Figure 3B–C"), ("Figure 3C and Table 4", "Figure 3A and Table 4"),
         ("shown in Figure 3C", "shown in Figure 3A"),
         ("Figure 3C; Table 4", "Figure 3A; Table 4")]
        if lang == "en" else
        [("图3A–B", "图3B–C"), ("图3C、表4", "图3A、表4"), ("见图3C", "见图3A")]
    )
    for p in doc.xpath("//w:body/w:p[not(.//w:drawing)]", namespaces=NS):
        old = ptext(p); new = old
        for a, b in pairs:
            new = new.replace(a, b)
        if new != old:
            set_paragraph_text(p, new)


def normalize_chinese(doc):
    pairs = [
        ("留一seed交叉拟合", "留一种子（leave-one-seed-out）交叉拟合"),
        ("留一seed", "留一种子"), ("同一折", "同折"), ("same-fold", "同折"),
        ("候选库", "候选池"), ("划分种子", "切分种子"),
        ("reference = 1", "参考值为1"), ("切分哈希", "切分哈希值"),
        ("Morgan-only", "仅Morgan候选池"),
        ("十种子", "10个种子"), ("五种子", "5个种子"),
    ]
    for p in doc.xpath("//w:body/w:p[not(.//w:drawing)]", namespaces=NS):
        old = ptext(p); new = old
        for a, b in pairs:
            new = new.replace(a, b)
        new = new.replace("Tanimoto≥0.70", "Tanimoto ≥ 0.70")
        new = new.replace("少数类召回≥0.80", "少数类召回 ≥ 0.80")
        if new != old:
            set_paragraph_text(p, new)


def core_table3(doc):
    table = doc.xpath("//w:body/w:tbl", namespaces=NS)[2]
    full = deepcopy(table)
    keep = {"Smain","Ssecondary","u=(s,f)","CK","V(u,j)","A(u,j)","jrefinv(−s)","jrefdep(−s,K)","Ginv(u,K)","Gdep(u,K)","Gsame(u,K)","Δinv(e)"}
    rows = table.findall("w:tr", NS)
    kept = 0
    for row in rows[1:]:
        symbol = ptext(row.findall("w:tc", NS)[0]).replace(" ", "")
        if symbol in keep:
            kept += 1
        else:
            table.remove(row)
    if kept != 12:
        raise RuntimeError(f"core Table 3 retained {kept} rather than 12 rows")
    return full


def revise_table3_caption_and_note(doc, lang: str):
    table = doc.xpath("//w:body/w:tbl", namespaces=NS)[2]
    body = table.getparent()
    prev = table.getprevious()
    while prev is not None and prev.tag != Q(W, "p"):
        prev = prev.getprevious()
    if prev is None:
        raise RuntimeError("Table 3 caption not found")
    caption = ("Table 3. Core notation required to interpret the primary audit estimands."
               if lang == "en" else "表3. 解释主要审计估计量所需的12个核心符号。")
    note = ("Note: The complete notation table, including secondary symbols and the numerical-stability constant, is provided in Supplementary Methods, Table S47."
            if lang == "en" else "注：包含次要符号和数值稳定常数的完整符号表见补充方法表S47。")
    set_paragraph_text(prev, caption)
    idx = body.index(table) + 1
    body.insert(idx, make_paragraph(note))


def make_paragraph(text: str, style: str | None = None):
    p = etree.Element(Q(W, "p"))
    if style:
        ppr = etree.SubElement(p, Q(W, "pPr")); ps = etree.SubElement(ppr, Q(W, "pStyle")); ps.set(Q(W, "val"), style)
    r = etree.SubElement(p, Q(W, "r")); t = etree.SubElement(r, Q(W, "t")); t.text = text
    return p


def native_power_10_minus_12():
    om = etree.Element(Q(M, "oMath")); ss = etree.SubElement(om, Q(M, "sSup"))
    e = etree.SubElement(ss, Q(M, "e")); r1 = etree.SubElement(e, Q(M, "r")); etree.SubElement(r1, Q(M, "t")).text = "10"
    sup = etree.SubElement(ss, Q(M, "sup")); r2 = etree.SubElement(sup, Q(M, "r")); etree.SubElement(r2, Q(M, "t")).text = "−12"
    return om


def fix_epsilon_native(table):
    for row in table.findall("w:tr", NS)[1:]:
        cells = row.findall("w:tc", NS)
        if cells and ptext(cells[0]).replace(" ", "") == "εnum":
            cell = cells[1]
            for c in list(cell):
                if c.tag != Q(W, "tcPr"):
                    cell.remove(c)
            p = etree.SubElement(cell, Q(W, "p")); r = etree.SubElement(p, Q(W, "r")); etree.SubElement(r, Q(W, "t")).text = "numerical-stability constant, fixed at "
            p.append(native_power_10_minus_12())
            return
    raise RuntimeError("epsilon row not found")


def append_full_notation_to_supp(doc, full_table):
    fix_epsilon_native(full_table)
    body = doc.find(".//w:body", NS); sect = body.find("w:sectPr", NS); idx = body.index(sect) if sect is not None else len(body)
    nodes = [
        make_paragraph("S22.6 Full notation table", "4"),
        make_paragraph("The main manuscript retains the 12 symbols needed for direct interpretation. This complete table preserves all secondary notation and the native mathematical form of the numerical-stability constant."),
        make_paragraph("Table S47. Complete notation used in the main and supplementary analyses.", "TableCaption"),
        full_table,
    ]
    for node in nodes:
        body.insert(idx, node); idx += 1


def modify_main(source: Path, out: Path, lang: str):
    work = WORK / ("en" if lang == "en" else "zh")
    unzip_docx(source, work)
    parser = etree.XMLParser(remove_blank_text=False)
    dp = work / "word" / "document.xml"; rp = work / "word" / "_rels" / "document.xml.rels"
    doc = etree.parse(str(dp), parser); rels = etree.parse(str(rp), parser)
    full_table = core_table3(doc)
    revise_table3_caption_and_note(doc, lang)
    for idx in (1, 3, 7, 8):
        replace_figure(work, doc, rels, idx, FIG / f"Figure{idx}_600dpi.png")
        set_paragraph_text(find_caption(doc, idx, lang), CAPTIONS[lang][idx])
    update_body_cross_references(doc, lang)
    renumber_and_split_equations(doc)
    synchronize_equation_references(doc, lang)
    if lang == "zh":
        normalize_chinese(doc)
    dp.write_bytes(etree.tostring(doc, xml_declaration=True, encoding="UTF-8", standalone="yes"))
    rp.write_bytes(etree.tostring(rels, xml_declaration=True, encoding="UTF-8", standalone="yes"))
    zip_docx(work, out)
    return full_table


def modify_supp(source: Path, out: Path, full_table):
    work = WORK / "supp"
    unzip_docx(source, work)
    parser = etree.XMLParser(remove_blank_text=False)
    dp = work / "word" / "document.xml"; doc = etree.parse(str(dp), parser)
    append_full_notation_to_supp(doc, deepcopy(full_table))
    synchronize_equation_references(doc, "en")
    dp.write_bytes(etree.tostring(doc, xml_declaration=True, encoding="UTF-8", standalone="yes"))
    zip_docx(work, out)


if __name__ == "__main__":
    WORK.mkdir(parents=True, exist_ok=True)
    full = modify_main(EN_SOURCE, EN_OUT, "en")
    modify_main(ZH_SOURCE, ZH_OUT, "zh")
    modify_supp(SUPP_SOURCE, SUPP_OUT, full)
    for p in (EN_OUT, ZH_OUT, SUPP_OUT):
        print(p, p.stat().st_size)
