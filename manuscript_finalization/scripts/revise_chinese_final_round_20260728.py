from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
import shutil

from lxml import etree

ROOT = Path(r"D:\fzyc\work\chinese_final_round_20260728")
DOC = ROOT / "word" / "document.xml"
RELS = ROOT / "word" / "_rels" / "document.xml.rels"
FIGURE4 = Path(r"D:\fzyc\work\figure4_20260728\Figure4_600dpi.png")

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
XML = "http://www.w3.org/XML/1998/namespace"
NS = {"w": W, "m": M, "wp": WP, "a": A, "r": R, "pr": PR}
Q = lambda ns, name: f"{{{ns}}}{name}"


def ptext(paragraph: etree._Element) -> str:
    return "".join(paragraph.xpath(".//w:t/text()", namespaces=NS))


def style_id(paragraph: etree._Element) -> str:
    node = paragraph.find("w:pPr/w:pStyle", NS)
    return node.get(Q(W, "val"), "") if node is not None else ""


def fonts_rpr(math: bool = False) -> etree._Element:
    rpr = etree.Element(Q(W, "rPr"))
    fonts = etree.SubElement(rpr, Q(W, "rFonts"))
    latin = "Cambria Math" if math else "Times New Roman"
    fonts.set(Q(W, "ascii"), latin)
    fonts.set(Q(W, "hAnsi"), latin)
    fonts.set(Q(W, "eastAsia"), "宋体")
    fonts.set(Q(W, "cs"), latin)
    lang = etree.SubElement(rpr, Q(W, "lang"))
    lang.set(Q(W, "val"), "en-US")
    lang.set(Q(W, "eastAsia"), "zh-CN")
    return rpr


def text_run(text: str) -> etree._Element:
    run = etree.Element(Q(W, "r"))
    run.append(fonts_rpr())
    node = etree.SubElement(run, Q(W, "t"))
    if text[:1].isspace() or text[-1:].isspace():
        node.set(Q(XML, "space"), "preserve")
    node.text = text
    return run


def replace_paragraph_text(paragraph: etree._Element, text: str) -> None:
    for child in list(paragraph):
        if child.tag != Q(W, "pPr"):
            paragraph.remove(child)
    paragraph.append(text_run(text))


def compact_math(node: etree._Element) -> str:
    return re.sub(r"\s+", "", "".join(node.xpath(".//m:t/text()", namespaces=NS)))


def plain_math_text(node: etree._Element) -> str:
    raw = compact_math(node)
    direct = {
        "K=4": "K = 4", "K=8": "K = 8", "K=16": "K = 16", "K=32": "K = 32",
        "ε": "ε", "Smain=10": "S_main = 10", "Ssecondary": "S_secondary", "CK": "C_K",
        "ju(K)": "ĵ_u(K)", "jrefinv(−s)": "j_ref^inv(−s)", "jrefinv(-s)": "j_ref^inv(−s)",
        "jrefdep(−s,K)": "j_ref^dep(−s,K)", "jrefdep(-s,K)": "j_ref^dep(−s,K)",
        "Ginv(u,K)": "G_inv(u,K)", "Gdep(u,K)": "G_dep(u,K)", "Gsame(u,K)": "G_same(u,K)",
        "Gavail(u,K)": "G_avail(u,K)", "Ginv(u,K)=Gavail(u,K)+Gdep(u,K)": "G_inv(u,K) = G_avail(u,K) + G_dep(u,K)",
        "ru": "r_u", "pi": "p_i", "λi": "λ_i", "πj": "π_j", "Δinv(e)": "Δ_inv(e)",
        "ε=10-12": "ε = 10^−12", "ε=10−12": "ε = 10^−12", "0log0:=0": "0 log 0 := 0",
    }
    if raw in direct:
        return direct[raw]
    # Conservative fallback for short inline notation only; numbered equations are excluded.
    fallback = raw.replace("−", "−")
    fallback = re.sub(r"^Smain", "S_main", fallback)
    fallback = re.sub(r"^Ssecondary", "S_secondary", fallback)
    fallback = re.sub(r"^G(inv|dep|same|avail)", lambda m: f"G_{m.group(1)}", fallback)
    return fallback


def convert_inline_math(document: etree._Element) -> int:
    tables = document.xpath("//w:tbl", namespaces=NS)
    symbol_table = tables[2]
    converted = 0
    for paragraph in document.xpath("//w:p[.//m:oMath]", namespaces=NS):
        if style_id(paragraph) == "Equation" or symbol_table in paragraph.iterancestors():
            continue
        for equation in list(paragraph.xpath(".//m:oMath", namespaces=NS)):
            parent = equation.getparent()
            position = parent.index(equation)
            parent.remove(equation)
            parent.insert(position, text_run(plain_math_text(equation)))
            converted += 1
    return converted


def mathml(content: str) -> etree._Element:
    namespace = "http://www.w3.org/1998/Math/MathML"
    source = etree.fromstring(f'<math xmlns="{namespace}"><mrow>{content}</mrow></math>'.encode("utf-8"))
    xsl = etree.parse(r"C:\Program Files\Microsoft Office\root\Office16\MML2OMML.XSL")
    result = etree.XSLT(xsl)(source).getroot()
    for run in result.xpath(".//m:r", namespaces=NS):
        wpr = run.find("w:rPr", NS)
        if wpr is None:
            wpr = etree.SubElement(run, Q(W, "rPr"))
        fonts = wpr.find("w:rFonts", NS)
        if fonts is None:
            fonts = etree.SubElement(wpr, Q(W, "rFonts"))
        for key in ("ascii", "hAnsi", "cs"):
            fonts.set(Q(W, key), "Cambria Math")
    return result


def mi(value: str, variant: str | None = None) -> str:
    attr = f' mathvariant="{variant}"' if variant else ""
    return f"<mi{attr}>{value}</mi>"


def mn(value: str) -> str:
    return f"<mn>{value}</mn>"


def mo(value: str, attrs: str = "") -> str:
    return f"<mo{attrs}>{value}</mo>"


def sub(base: str, value: str) -> str:
    return f"<msub>{base}<mrow>{value}</mrow></msub>"


def sub_sup(base: str, lower: str, upper: str) -> str:
    return f"<msubsup>{base}<mtext>{lower}</mtext><mtext>{upper}</mtext></msubsup>"


def formulae() -> dict[int, etree._Element]:
    minus_s = mo("−") + mi("s")
    n_minus_s = sub(mi("N"), minus_s)
    u_minus_s = sub(mi("U"), minus_s)
    c32 = sub(mi("C", "script"), mn("32"))
    ck = sub(mi("C", "script"), mi("K"))
    jref_inv = sub_sup(mi("j"), "ref", "inv")
    jref_dep = sub_sup(mi("j"), "ref", "dep")
    argmax32 = f'<munder><mrow><mtext>arg max</mtext></mrow><mrow>{mi("j")}{mo("∈")}{c32}</mrow></munder>'
    argmaxk = f'<munder><mrow><mtext>arg max</mtext></mrow><mrow>{mi("j")}{mo("∈")}{ck}</mrow></munder>'
    summand = mi("A") + mo("(") + mi("u") + mo(",") + mi("j") + mo(")")
    summation = f'<munder>{mo("∑", " largeop=\"true\" movablelimits=\"true\"")}<mrow>{mi("u")}{mo("∈")}{u_minus_s}</mrow></munder>{summand}'
    f6 = jref_inv + mo("(") + minus_s + mo(")") + mo("=") + argmax32 + f"<mfrac>{mn('1')}{n_minus_s}</mfrac>" + summation
    f7 = jref_dep + mo("(") + minus_s + mo(",") + mi("K") + mo(")") + mo("=") + argmaxk + f"<mfrac>{mn('1')}{n_minus_s}</mfrac>" + summation

    s_main = sub(mi("S"), "<mtext>main</mtext>")
    delta_inv = sub(mi("Δ"), "<mtext>inv</mtext>")
    g_inv = sub(mi("G"), "<mtext>inv</mtext>")
    sum_s = f'<munderover>{mo("∑", " largeop=\"true\" movablelimits=\"true\"")}<mrow>{mi("s")}{mo("=")}{mn("1")}</mrow>{s_main}</munderover>'
    sum_f = f'<munderover>{mo("∑", " largeop=\"true\" movablelimits=\"true\"")}<mrow>{mi("f")}{mo("=")}{mn("1")}</mrow>{mi("F")}</munderover>'
    call32 = g_inv + mo("(") + mo("(") + mi("s") + mo(",") + mi("f") + mo(")") + mo(",") + mn("32") + mo(")")
    call4 = g_inv + mo("(") + mo("(") + mi("s") + mo(",") + mi("f") + mo(")") + mo(",") + mn("4") + mo(")")
    f11 = delta_inv + mo("(") + mi("e") + mo(")") + mo("=") + f"<mfrac>{mn('1')}<mrow>{s_main}{mi('F')}</mrow></mfrac>" + sum_s + sum_f + mo("[") + call32 + mo("−") + call4 + mo("]")
    return {6: mathml(f6), 7: mathml(f7), 11: mathml(f11)}


def rebuild_equations(document: etree._Element) -> None:
    equations = document.xpath("//w:p[w:pPr/w:pStyle[@w:val='Equation']]", namespaces=NS)
    replacements = formulae()
    for number, equation in replacements.items():
        paragraph = equations[number - 1]
        current = paragraph.find("m:oMath", NS)
        paragraph.replace(current, equation)


def insert_definition(document: etree._Element) -> None:
    for paragraph in document.xpath("//w:p", namespaces=NS):
        text = ptext(paragraph)
        if text.startswith("参考训练集包含除留出种子"):
            prefix = "记 U_{−s} 为除留出种子 s 以外的全部外层审计单元，并定义 N_{−s} = |U_{−s}|。"
            if not text.startswith("记 U_{−s}"):
                replace_paragraph_text(paragraph, prefix + text)
            return
    for paragraph in document.xpath("//w:p", namespaces=NS):
        text = ptext(paragraph)
        if text.startswith("令外层审计单元u = (s,f)"):
            replacement = text.replace("令外层审计单元u = (s,f)。", "令外层审计单元 u = (s, f)，并定义 N_{−s} = |U_{−s}|。")
            replace_paragraph_text(paragraph, replacement)
            return
    raise RuntimeError("Definition paragraph not found")


def insert_conclusion(document: etree._Element) -> None:
    body = document.find("w:body", NS)
    if any(ptext(p).strip() == "5 结论" for p in body.findall("w:p", NS)):
        return
    anchor = next(p for p in body.findall("w:p", NS) if ptext(p).startswith("在已评估的端点、候选登记表和切分机制中"))
    heading = etree.Element(Q(W, "p"))
    ppr = etree.SubElement(heading, Q(W, "pPr"))
    pstyle = etree.SubElement(ppr, Q(W, "pStyle")); pstyle.set(Q(W, "val"), "1")
    keep = etree.SubElement(ppr, Q(W, "keepNext"))
    heading.append(text_run("5 结论"))
    anchor.addprevious(heading)


def revise_figure4_caption(document: etree._Element) -> None:
    target = next(p for p in document.xpath("//w:p", namespaces=NS) if ptext(p).startswith("图4. 选择差距分解与赢家乐观偏差"))
    text = (
        "图4. 选择差距分解与赢家乐观偏差。A和B比较分类与回归的观测审计最佳收益和验证所选收益。"
        "C展示同折有限集合机会差距与K依赖前缀内交叉拟合差距，属于次要分解或敏感性分析；主要K不变完整候选库完成差距估计见图3C。"
        "为便于端点间可视化比较，C使用端点内标准化效应，原始ROC-AUC与RMSE效应另行列示。D显示候选真实效用相同时的有限审计赢家乐观偏差。"
    )
    replace_paragraph_text(target, text)


def split_table3(document: etree._Element) -> None:
    body = document.find("w:body", NS)
    tables = body.findall("w:tbl", NS)
    table = tables[2]
    if table.get(Q(W, "rsidR")) == "TABLE3_SPLIT":
        return
    rows = table.findall("w:tr", NS)
    second = deepcopy(table)
    for row in rows[12:]:
        table.remove(row)
    second_rows = second.findall("w:tr", NS)
    for row in second_rows[1:12]:
        second.remove(row)
    table.set(Q(W, "rsidR"), "TABLE3_SPLIT")
    second.set(Q(W, "rsidR"), "TABLE3_CONT")
    first_bottom = table.find("w:tblPr/w:tblBorders/w:bottom", NS)
    first_bottom.set(Q(W, "val"), "nil")

    caption = etree.Element(Q(W, "p"))
    ppr = etree.SubElement(caption, Q(W, "pPr"))
    pstyle = etree.SubElement(ppr, Q(W, "pStyle")); pstyle.set(Q(W, "val"), "TableCaption")
    etree.SubElement(ppr, Q(W, "keepNext"))
    etree.SubElement(ppr, Q(W, "pageBreakBefore"))
    caption.append(text_run("表3（续）. 审计估计量使用的数学符号。"))
    index = body.index(table)
    body.insert(index + 1, caption)
    body.insert(index + 2, second)


ALT_TEXT = [
    "图1概述从候选登记、重复嵌套骨架审计到差距分解和稳健性报告的证据层级。流程强调K不变参考、K依赖参考与同折机会界的区别，并连接实用等价、选择稳定性、计算暴露和化学支持分析。",
    "图2比较十种子审计中四种候选效用矩阵构造得到的有效多样性。各面板展示谱熵秩、参与率秩、候选相关以及固定参照相对估计，说明名义候选数并不等同于有效多样性。",
    "图3评估机会校正排序保真度，并给出主要K不变完整候选库完成差距对比。恢复模拟和组成对照显示结果随候选数量和登记组成变化，但端点方向具有异质性。",
    "图4分解观测机会、验证兑现和有限审计赢家乐观偏差。C面板仅比较同折有限集合机会差距与K依赖前缀内差距，作为次要敏感性分析；主要K不变估计见图3C。",
    "图5比较固定候选数量下不同表征组合的终点特异性收益。面板覆盖全部登记子集、互斥组成类别、候选数量阶梯及标准化森林图，显示多视图收益依赖具体端点。",
    "图6描述化学支持边界附近的预测可靠性。相关、错误重叠、风险矩阵、新骨架变化和四模型权衡共同表明，化学分布外推会降低可靠性且不同指标并不同步。",
    "图7比较同质Morgan、多表征经典和现代增强候选池在机会、排序保真度、选择稳定性与下游预算上的差异。A至D面板同时保留负结果，并显示等K与等预算条件下的经验Pareto前沿。",
    "图8汇总十种子主要审计中的实用等价和指标依赖选择。四个面板分别展示K不变/K依赖/同折差距、实用等价成功率、近等价集合大小以及候选切换和外层指标变化。",
]


def update_drawings(document: etree._Element, relationships: etree._Element) -> None:
    drawings = document.xpath("//wp:docPr", namespaces=NS)
    if len(drawings) != 8:
        raise RuntimeError(f"Expected 8 drawings, found {len(drawings)}")
    for number, (drawing, alt) in enumerate(zip(drawings, ALT_TEXT), 1):
        drawing.set("name", f"Figure {number}")
        drawing.set("title", f"Figure {number} alternative text")
        drawing.set("descr", alt)
    figure4_paragraph = document.xpath("//w:p[.//w:drawing]", namespaces=NS)[3]
    rid = figure4_paragraph.xpath(".//a:blip/@r:embed", namespaces=NS)[0]
    target = next(rel.get("Target") for rel in relationships.xpath("//pr:Relationship", namespaces=NS) if rel.get("Id") == rid)
    shutil.copy2(FIGURE4, ROOT / "word" / target.replace("/", "\\"))


def main() -> None:
    parser = etree.XMLParser(remove_blank_text=False)
    document = etree.parse(str(DOC), parser).getroot()
    relationships = etree.parse(str(RELS), parser).getroot()
    converted = convert_inline_math(document)
    insert_definition(document)
    rebuild_equations(document)
    insert_conclusion(document)
    revise_figure4_caption(document)
    split_table3(document)
    update_drawings(document, relationships)
    DOC.write_bytes(etree.tostring(document, xml_declaration=True, encoding="UTF-8", standalone="yes"))
    print(f"inline_math_to_text={converted}")
    print("equations_rebuilt=6,7,11")
    print("conclusion_added=yes")
    print("table3_split=yes")
    print("alt_texts=8")


if __name__ == "__main__":
    main()
