from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
import shutil

from lxml import etree

BASE = Path(r"D:\fzyc\work")
ROOTS = {
    "zh": BASE / "round2b_zh_20260728",
    "en": BASE / "round2b_en_20260728",
    "supp": BASE / "round2b_supp_20260728",
}
FIGURE8 = Path(r"D:\fzyc\output\paper43_jcheminform_completion_20260726\main_figures_submission\Figure8_600dpi.png")
XSL = Path(r"C:\Program Files\Microsoft Office\root\Office16\MML2OMML.XSL")

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
XML = "http://www.w3.org/XML/1998/namespace"
NS = {"w": W, "m": M, "wp": WP, "a": A, "r": R, "pr": PR}
Q = lambda ns, name: f"{{{ns}}}{name}"


def ptext(node):
    return "".join(node.xpath(".//w:t/text()", namespaces=NS))


def all_text(node):
    return "".join(node.xpath(".//w:t/text() | .//m:t/text()", namespaces=NS))


def text_run(value, rpr=None):
    run = etree.Element(Q(W, "r"))
    if rpr is not None:
        run.append(deepcopy(rpr))
    else:
        props = etree.SubElement(run, Q(W, "rPr"))
        fonts = etree.SubElement(props, Q(W, "rFonts"))
        for key, font in (("ascii", "Times New Roman"), ("hAnsi", "Times New Roman"), ("eastAsia", "宋体"), ("cs", "Times New Roman")):
            fonts.set(Q(W, key), font)
    node = etree.SubElement(run, Q(W, "t"))
    if value[:1].isspace() or value[-1:].isspace():
        node.set(Q(XML, "space"), "preserve")
    node.text = value
    return run


def replace_para(paragraph, value):
    for child in list(paragraph):
        if child.tag != Q(W, "pPr"):
            paragraph.remove(child)
    paragraph.append(text_run(value))


def find_para(root, starts):
    return next(p for p in root.xpath("//w:p", namespaces=NS) if ptext(p).startswith(starts))


def mathml(content):
    source = etree.fromstring(f'<math xmlns="http://www.w3.org/1998/Math/MathML"><mrow>{content}</mrow></math>'.encode())
    result = etree.XSLT(etree.parse(str(XSL)))(source).getroot()
    for run in result.xpath(".//m:r", namespaces=NS):
        props = run.find("w:rPr", NS)
        if props is None:
            props = etree.SubElement(run, Q(W, "rPr"))
        fonts = props.find("w:rFonts", NS)
        if fonts is None:
            fonts = etree.SubElement(props, Q(W, "rFonts"))
        for key in ("ascii", "hAnsi", "cs"):
            fonts.set(Q(W, key), "Cambria Math")
    return result


def mi(v, variant=None):
    attr = f' mathvariant="{variant}"' if variant else ""
    return f"<mi{attr}>{v}</mi>"


def mn(v): return f"<mn>{v}</mn>"
def mo(v, attrs=""): return f"<mo{attrs}>{v}</mo>"
def mtext(v): return f"<mtext>{v}</mtext>"
def row(v): return f"<mrow>{v}</mrow>"
def sub(base, lower): return f"<msub>{base}{row(lower)}</msub>"
def sup(base, upper): return f"<msup>{base}{row(upper)}</msup>"
def subsup(base, lower, upper): return f"<msubsup>{base}{row(lower)}{row(upper)}</msubsup>"
def frac(a, b): return f"<mfrac>{row(a)}{row(b)}</mfrac>"
def par(v): return mo("(") + v + mo(")")


S_MAIN = sub(mi("S"), mtext("main"))
S_SECONDARY = sub(mi("S"), mtext("secondary"))
S_COV = sub(mi("S", "bold"), mtext("cov"))
C_K = sub(mi("C", "script"), mi("K"))
C_32 = sub(mi("C", "script"), mn("32"))
MINUS_S = mo("−") + mi("s")
U_MINUS_S = sub(mi("U"), MINUS_S)
N_MINUS_S = sub(mi("N"), MINUS_S)
J_HAT = sub('<mover accent="true">' + mi("j") + mo("^") + "</mover>", mi("u"))
J_BEST = sub(mi("j"), mtext("best") + mo(",") + mi("u"))
J_REF_INV = subsup(mi("j"), mtext("ref"), mtext("inv"))
J_REF_DEP = subsup(mi("j"), mtext("ref"), mtext("dep"))
G_INV = sub(mi("G"), mtext("inv"))
G_DEP = sub(mi("G"), mtext("dep"))
G_SAME = sub(mi("G"), mtext("same"))
G_AVAIL = sub(mi("G"), mtext("avail"))
DELTA_INV = sub(mi("Δ"), mtext("inv"))
EPS_NUM = sub(mi("ε"), mtext("num"))
TAU = mi("τ")
LAMBDA_I = sub(mi("λ"), mi("i"))
P_I = sub(mi("p"), mi("i"))
PI_J = sub(mi("π"), mi("j"))
GBAR = sub('<mover accent="true">' + mi("G") + mo("¯") + "</mover>", mtext("inv") + mo(",") + mi("e") + mo(",") + mi("s"))


def call(base, args):
    return base + par(mo(",").join(args))


def argmax(condition):
    return f'<munder><mrow>{mtext("arg max")}</mrow><mrow>{condition}</mrow></munder>'


def sum_under(condition):
    return f'<munder>{mo("∑", " largeop=\"true\" movablelimits=\"false\"")}<mrow>{condition}</mrow></munder>'


def sum_over(lower, upper):
    return f'<munderover>{mo("∑", " largeop=\"true\" movablelimits=\"false\"")}<mrow>{lower}</mrow><mrow>{upper}</mrow></munderover>'


def formula1():
    return mathml(call(J_HAT, [mi("K")]) + mo("=") + argmax(mi("j") + mo("∈") + C_K) + call(mi("V"), [mi("u"), mi("j")]))


def formula2():
    return mathml(call(J_BEST, [mi("K")]) + mo("=") + argmax(mi("j") + mo("∈") + C_K) + call(mi("A"), [mi("u"), mi("j")]))


def formula3():
    loss = call(sub(mi("L"), mi("u")), [mi("K")])
    norm = call(sub('<mover accent="true">' + mi("L") + mo("~") + "</mover>", mi("u")), [mi("K")])
    a_best = call(mi("A"), [mi("u"), call(J_BEST, [mi("K")])])
    a_sel = call(mi("A"), [mi("u"), call(J_HAT, [mi("K")])])
    maximum = argmax(mi("j") + mo("∈") + C_K).replace(mtext("arg max"), mtext("max")) + call(mi("A"), [mi("u"), mi("j")])
    minimum = argmax(mi("j") + mo("∈") + C_K).replace(mtext("arg max"), mtext("min")) + call(mi("A"), [mi("u"), mi("j")])
    return mathml(loss + mo("=") + a_best + mo("−") + a_sel + mo(";") + norm + mo("=") + frac(loss, maximum + mo("−") + minimum + mo("+") + EPS_NUM))


def reference_formula(dependent):
    reference = J_REF_DEP if dependent else J_REF_INV
    candidates = C_K if dependent else C_32
    lhs_args = [MINUS_S, mi("K")] if dependent else [MINUS_S]
    mean = frac(mn("1"), N_MINUS_S) + '<mspace width="0.28em"/>' + sum_under(mi("u") + mo("∈") + U_MINUS_S) + call(mi("A"), [mi("u"), mi("j")])
    return mathml(call(reference, lhs_args) + mo("=") + argmax(mi("j") + mo("∈") + candidates) + '<mspace width="0.28em"/>' + mean)


def seed_mean_formula():
    rhs = frac(mn("1"), mi("F")) + '<mspace width="0.22em"/>' + sum_over(mi("f") + mo("=") + mn("1"), mi("F")) + call(sub(G_INV, mi("e")), [par(mi("s") + mo(",") + mi("f")), mi("K")])
    return mathml(call(GBAR, [mi("K")]) + mo("=") + rhs)


def endpoint_formula():
    contrast = mo("[") + call(GBAR, [mn("32")]) + mo("−") + call(GBAR, [mn("4")]) + mo("]")
    rhs = frac(mn("1"), S_MAIN) + '<mspace width="0.22em"/>' + sum_over(mi("s") + mo("=") + mn("1"), S_MAIN) + contrast
    return mathml(call(DELTA_INV, [mi("e")]) + mo("=") + rhs)


def set_equation(paragraph, equation, number):
    current = paragraph.find("m:oMath", NS)
    if current is None:
        current = paragraph.xpath(".//m:oMath", namespaces=NS)[0]
    current.getparent().replace(current, equation)
    number_nodes = [t for t in paragraph.xpath(".//w:t", namespaces=NS) if re.fullmatch(r"\(\d+\)", t.text or "")]
    if not number_nodes:
        raise RuntimeError(f"Equation number not found: {all_text(paragraph)}")
    number_nodes[-1].text = f"({number})"


def rebuild_numbered_equations(root):
    numbered = {}
    for paragraph in root.xpath("//w:p[.//m:oMath]", namespaces=NS):
        match = re.fullmatch(r"\((\d+)\)", ptext(paragraph).strip())
        if match:
            numbered[int(match.group(1))] = paragraph
    if sorted(numbered) != list(range(1, 20)):
        raise RuntimeError(f"Unexpected equation numbering: {sorted(numbered)}")
    old1 = numbered[1]
    set_equation(old1, formula1(), 1)
    second = deepcopy(old1); set_equation(second, formula2(), 2); old1.addnext(second)
    set_equation(numbered[2], formula3(), 3)
    for old in range(3, 11):
        new = old + 1
        equation = reference_formula(False) if old == 6 else reference_formula(True) if old == 7 else deepcopy(numbered[old].xpath(".//m:oMath", namespaces=NS)[0])
        set_equation(numbered[old], equation, new)
    set_equation(numbered[11], seed_mean_formula(), 12)
    endpoint = deepcopy(numbered[11]); set_equation(endpoint, endpoint_formula(), 13); numbered[11].addnext(endpoint)
    for old in range(12, 20):
        set_equation(numbered[old], deepcopy(numbered[old].xpath(".//m:oMath", namespaces=NS)[0]), old + 2)


TOKEN_EXPR = {
    "ε_num = 10^−12": EPS_NUM + mo("=") + sup(mn("10"), mo("−") + mn("12")),
    "ε_num = 10^−12": EPS_NUM + mo("=") + sup(mn("10"), mo("−") + mn("12")),
    "0 log 0 := 0": mn("0") + mtext("log") + mn("0") + mo(":=") + mn("0"),
    "j_ref^dep(−s,K)": call(J_REF_DEP, [MINUS_S, mi("K")]),
    "j_ref^inv(−s)": call(J_REF_INV, [MINUS_S]),
    "j_ref^dep(-s,K)": call(J_REF_DEP, [MINUS_S, mi("K")]),
    "j_ref^inv(-s)": call(J_REF_INV, [MINUS_S]),
    "G_inv(u,K)": call(G_INV, [mi("u"), mi("K")]),
    "G_dep(u,K)": call(G_DEP, [mi("u"), mi("K")]),
    "G_same(u,K)": call(G_SAME, [mi("u"), mi("K")]),
    "G_avail(u,K)": call(G_AVAIL, [mi("u"), mi("K")]),
    "G_inv(u,32)": call(G_INV, [mi("u"), mn("32")]),
    "G_inv(u,4)": call(G_INV, [mi("u"), mn("4")]),
    "Delta_inv(e)": call(DELTA_INV, [mi("e")]),
    "Δ_inv(e)": call(DELTA_INV, [mi("e")]),
    "Gbar_inv,e,s(K)": call(GBAR, [mi("K")]),
    "S_secondary": S_SECONDARY,
    "S_main": S_MAIN,
    "S_cov": S_COV,
    "C_K": C_K,
    "U_{−s}": U_MINUS_S,
    "N_{−s}": N_MINUS_S,
    "U₋ₛ": U_MINUS_S,
    "N₋ₛ": N_MINUS_S,
    "j_ref^inv": J_REF_INV,
    "j_ref^dep": J_REF_DEP,
    "G_inv": G_INV,
    "G_dep": G_DEP,
    "G_same": G_SAME,
    "G_avail": G_AVAIL,
    "Delta_inv": DELTA_INV,
    "Δ_inv": DELTA_INV,
    "lambda_i": LAMBDA_I,
    "λ_i": LAMBDA_I,
    "p_i": P_I,
    "pi_j": PI_J,
    "π_j": PI_J,
    "epsilon_num": EPS_NUM,
    "ε_num": EPS_NUM,
    "tau": TAU,
    "τ": TAU,
}
TOKEN_RE = re.compile("|".join(re.escape(k) for k in sorted(TOKEN_EXPR, key=len, reverse=True)))


def native_inline_math(root):
    converted = 0
    for node in list(root.xpath("//w:t[not(ancestor::m:oMath)]", namespaces=NS)):
        value = node.text or ""
        if not TOKEN_RE.search(value):
            continue
        run = node.getparent()
        if run.tag != Q(W, "r") or len(run.xpath("./w:t", namespaces=NS)) != 1 or run.xpath("./w:drawing|./w:tab|./w:br", namespaces=NS):
            continue
        paragraph = run
        while paragraph is not None and paragraph.tag != Q(W, "p"):
            paragraph = paragraph.getparent()
        if paragraph is None or re.fullmatch(r"\(\d+\)", ptext(paragraph).strip()):
            continue
        container = run.getparent(); pos = container.index(run); rpr = run.find("w:rPr", NS)
        cursor = 0; inserts = []
        for match in TOKEN_RE.finditer(value):
            if match.start() > cursor:
                inserts.append(text_run(value[cursor:match.start()], rpr))
            inserts.append(mathml(TOKEN_EXPR[match.group(0)]))
            cursor = match.end()
        if cursor < len(value):
            inserts.append(text_run(value[cursor:], rpr))
        container.remove(run)
        for item in inserts:
            container.insert(pos, item); pos += 1
        converted += 1
    return converted


def replace_result_311(root, lang):
    if lang == "zh":
        old = find_para(root, "固定K = 32交叉拟合参考身份")
        first = "固定K = 32交叉拟合参考身份可避免随K改变比较对象。K = 32时，分类在ROC-AUC容差0.005、0.010和0.020下的τ成功率分别为62.7%、80.0%和86.0%；回归在RMSE容差0.025、0.050和0.100下分别为73.3%、79.2%和82.5%。任务匹配中间容差的合并描述性成功率为79.6%，平均交叉拟合近等价集合大小为10.17，所选候选属于该集合的比例为85.9%，验证集与交叉拟合集合的平均Jaccard重叠为0.490。这些均为回顾性锁定的报告容差，不是临床或药理学阈值。"
        second = "K = 32时，PR-AUC规则在52.7%的单元中改变ROC-AUC所选候选，并使外层PR-AUC、ROC-AUC、少数类召回、多数类召回和少数类漏检率平均变化+0.0018、−0.0026、−0.0002、−0.0136和+0.0002。少数类召回约束规则在66.0%的单元中改变候选，并使上述指标平均变化+0.0007、−0.0008、−0.0094、+0.0059和+0.0094。K = 32时100.0%的单元存在内层合资格候选，但冻结规则仅在62.0%的外层单元达到少数类召回≥0.80；负的平均召回变化被完整保留，不解释为约束可自动迁移（表S38–S40）。"
    else:
        old = find_para(root, "Holding the K = 32 cross-fitted reference identity")
        first = "Holding the K = 32 cross-fitted reference identity fixed across K removed comparator drift. At K = 32, classification τ-success was 62.7%, 80.0% and 86.0% across the 0.005/0.010/0.020 ROC-AUC grid; regression τ-success was 73.3%, 79.2% and 82.5% across the 0.025/0.050/0.100 RMSE grid. The pooled task-appropriate working-middle-threshold success rate was 79.6%; the mean cross-fitted set size was 10.17, the selected-in-set rate was 85.9% and mean validation–cross-fit set Jaccard overlap was 0.490. These are retrospectively locked reporting tolerances, not clinical or pharmacological thresholds."
        second = "At K = 32, PR-AUC selection changed the ROC-AUC-selected candidate in 52.7% of units and changed outer PR-AUC, ROC-AUC, minority recall, majority recall and false-negative rate by +0.0018, −0.0026, −0.0002, −0.0136 and +0.0002, respectively. The minority-recall-constrained selector changed candidates in 66.0% of units and changed the same outcomes by +0.0007, −0.0008, −0.0094, +0.0059 and +0.0094. An inner-eligible candidate existed in 100.0% of K = 32 units, whereas the frozen rule achieved outer minority recall ≥0.80 in 62.0%; the negative mean recall change was retained rather than interpreted as automatic constraint transfer (Tables S38–S40)."
    replace_para(old, first)
    new = deepcopy(old); replace_para(new, second); old.addnext(new)


def update_ranges(root, lang):
    replacements = (
        (("公式（1）–（4）", "公式（1）–（5）"), ("公式（5）–（11）", "公式（6）–（13）"), ("公式（12）–（15）", "公式（14）–（17）"), ("公式（16）–（19）", "公式（18）–（21）"), ("公式（19）", "公式（21）"))
        if lang == "zh" else
        (("Equations (1)–(4)", "Equations (1)–(5)"), ("Equations (5)–(11)", "Equations (6)–(13)"), ("Equations (12)–(15)", "Equations (14)–(17)"), ("Equations (16)–(19)", "Equations (18)–(21)"), ("Equation (19)", "Equation (21)"))
    )
    for paragraph in root.xpath("//w:p[not(.//m:oMath)]", namespaces=NS):
        value = ptext(paragraph); changed = value
        for old, new in replacements:
            changed = changed.replace(old, new)
        if lang == "zh":
            changed = changed.replace("端点层Δ_inv(e)对10个种子和每种子的3个外层折求配对平均", "先以每个种子的3个外层折定义Gbar_inv,e,s(K)，再由端点层Delta_inv(e)以10个种子为区组求配对平均")
        else:
            changed = changed.replace("The endpoint contrast Δ_inv(e) averages paired G_inv differences over ten seeds and three outer folds", "The seed-level mean Gbar_inv,e,s(K) first averages the three outer folds, and the endpoint contrast Delta_inv(e) then averages paired differences over the ten seed blocks")
        if changed != value:
            replace_para(paragraph, changed)


def update_core_text(root, lang):
    if lang == "zh":
        abstract = find_para(root, "结果：相对于K不变完整候选库参考")
        replace_para(abstract, ptext(abstract).replace("K = 32时，任务匹配中间容差下的交叉拟合ε成功率为79.6%。", "K = 32时，任务匹配中间容差下的交叉拟合成功率为79.6%。"))
        replace_para(find_para(root, "数值稳定常数取"), "数值稳定常数取 ε_num = 10^−12。Ledoit–Wolf收缩采用缩放单位阵目标及scikit-learn的解析收缩系数估计；特征分解前将收缩协方差重新缩放为相关矩阵R，仅因浮点误差产生的微小负特征值裁剪为0，并约定 0 log 0 := 0。配对归一化增益与交叉拟合差距先在配对外层审计单元内计算，随后在每个种子内平均3个外层折，再以种子为区组进行端点内汇总；绝对分母不超过 ε_num 的单元记为缺失并单独报告。")
        replace_para(find_para(root, "分类任务回顾性锁定的ROC-AUC容差网格"), "分类任务回顾性锁定的ROC-AUC实用等价容差τ网格为0.005、0.010和0.020，回归任务RMSE容差τ网格为0.025、0.050和0.100。若所选候选与交叉拟合参考的差距不超过τ，则记为τ成功；同时报告交叉拟合近等价候选集大小。所有阈值分析均作为敏感性描述，不作为事后显著性检验。")
        replace_para(find_para(root, "图8. 十种子主要审计中的实用等价"), "图8. 十种子主要审计中的实用等价与指标依赖选择。A面板上下排列分类ROC-AUC和回归RMSE差距，使用独立纵轴并共享候选数K横轴；圆点/实线、方块/虚线和三角/点线分别表示K不变、K依赖和同折估计量，使灰度打印时仍可区分。B展示回顾性锁定中间实用等价容差τ下各K的交叉拟合τ成功率。C在单一纵轴上展示交叉拟合近等价集合的平均大小，B中的分类/回归图例同时适用于C。D明确标示五个分类端点的PR-AUC候选切换、召回规则候选切换、ΔPR-AUC和Δ少数类召回；少数类召回负结果完整保留。A–D按2 × 2四联图排列。")
        replace_para(find_para(root, "实用等价集合可将注意力"), "实用等价集合可将注意力从不稳定的单一冠军转向在预先声明容差τ内可互换的候选，但τ具有任务尺度，必须在看到结果前锁定。PR-AUC或少数类召回规则只改变选择目标，并不保证外层泛化约束被满足。")
        replace_para(find_para(root, "ε容差是回顾性锁定"), "实用等价容差τ是回顾性锁定的报告容差，不是临床、药理或工业最小重要差异。PR-AUC和由训练数据定义的少数类召回规则改变了内层目标，但相应外层约束并未稳定迁移。")
    else:
        abstract = find_para(root, "Results: Against the K-invariant full-registry reference")
        replace_para(abstract, ptext(abstract).replace("At K = 32, 79.6% of selections were ε-successes at the retrospectively locked middle reporting tolerance.", "At K = 32, 79.6% of selections met the retrospectively locked task-matched middle practical-equivalence tolerance."))
        replace_para(find_para(root, "We used the numerical-stability constant"), "We used the numerical-stability constant ε_num = 10^−12. Ledoit–Wolf shrinkage used the scaled-identity target and the analytic coefficient implemented in scikit-learn. The shrinkage covariance was rescaled to a correlation matrix R before eigenanalysis. Correlation eigenvalues below zero only because of floating-point error were clipped to zero, with the convention 0 log 0 := 0. Paired normalized gains and cross-fitted gaps were computed within paired outer units, averaged over the three outer folds within each seed, and then summarized within endpoint using seed as the block; units with an absolute denominator at or below ε_num were reported as missing.")
        replace_para(find_para(root, "Retrospectively locked sensitivity grids"), "Retrospectively locked practical-equivalence tolerance τ grids were 0.005, 0.010 and 0.020 ROC-AUC for classification and 0.025, 0.050 and 0.100 RMSE for regression. The middle values were working thresholds, not clinical or pharmacological minimum important differences. We reported τ-regret, τ-success, validation- and cross-fitted near-equivalent set sizes, set Jaccard overlap and whether the selected candidate belonged to the cross-fitted set.")
        replace_para(find_para(root, "Figure 8. Practical equivalence and metric-dependent selection"), "Figure 8. Practical equivalence and metric-dependent selection in the ten-seed primary audit. (A) Classification ROC-AUC and regression RMSE gaps are shown on separate stacked axes sharing candidate count K; circles/solid lines, squares/dashed lines and triangles/dotted lines denote K-invariant, K-dependent and same-fold estimands, respectively, so estimands remain distinguishable in greyscale. (B) Cross-fitted τ-success is shown across K at the retrospectively locked middle practical-equivalence tolerances τ. (C) Mean cross-fitted near-equivalent set size is shown on one axis; the classification/regression legend in panel B also applies to panel C. (D) Candidate switching and outer changes are shown for the five classification endpoints, with PR-AUC switch, recall-rule switch, ΔPR-AUC and Δminority recall labelled explicitly; negative minority-recall changes are retained. Panels A–D are arranged in a 2 × 2 layout.")
        replace_para(find_para(root, "Near-equivalent sets prevent negligible"), "Near-equivalent sets prevent negligible candidate differences from being interpreted as severe selection failures. However, the working τ values were retrospectively locked practical-equivalence reporting tolerances rather than endpoint-specific clinical or pharmacological thresholds. PR-AUC and minority-recall-constrained selection exposed genuine candidate-switching and safety-performance trade-offs, but the 0.80 target is a study rule and must be redefined for deployment costs.")
        replace_para(find_para(root, "The ε tolerances are retrospectively locked"), "The practical-equivalence tolerances τ are retrospectively locked reporting tolerances rather than clinical, pharmacological or industrial minimum important differences. PR-AUC and training-defined minority-recall rules changed the inner objective, but the corresponding outer-fold constraints did not transfer reliably.")


def move_figure1(root):
    body = root.find("w:body", NS)
    figure = root.xpath("//w:p[.//w:drawing]", namespaces=NS)[0]
    caption = figure.getnext()
    while caption is not None and not ptext(caption).startswith(("Figure 1.", "图1.")):
        caption = caption.getnext()
    if caption is None:
        raise RuntimeError("Figure 1 caption not found")
    body.remove(figure); body.remove(caption)
    heading2 = next(p for p in body.findall("w:p", NS) if ptext(p).startswith(("2.2 ", "2.2　")))
    position = body.index(heading2)
    body.insert(position, figure); body.insert(position + 1, caption)
    for paragraph, keep_next in ((figure, True), (caption, False)):
        ppr = paragraph.find("w:pPr", NS)
        if ppr is None:
            ppr = etree.Element(Q(W, "pPr")); paragraph.insert(0, ppr)
        insert_at = 1 if ppr.find("w:pStyle", NS) is not None else 0
        if keep_next and ppr.find("w:keepNext", NS) is None:
            ppr.insert(insert_at, etree.Element(Q(W, "keepNext"))); insert_at += 1
        if ppr.find("w:keepLines", NS) is None:
            ppr.insert(insert_at, etree.Element(Q(W, "keepLines")))
    extent = figure.find(".//wp:extent", NS)
    shape_extent = figure.find(".//a:xfrm/a:ext", NS)
    if extent is not None:
        cx, cy = int(extent.get("cx")), int(extent.get("cy"))
        max_width = int(5.9 * 914400)
        if cx > max_width:
            new_cy = int(cy * max_width / cx)
            extent.set("cx", str(max_width)); extent.set("cy", str(new_cy))
            if shape_extent is not None:
                shape_extent.set("cx", str(max_width)); shape_extent.set("cy", str(new_cy))


def title_style(root, styles, lang):
    title = root.find("w:body/w:p", NS)
    style_id = "Title" if lang == "zh" else "aa"
    ppr = etree.Element(Q(W, "pPr"))
    pstyle = etree.SubElement(ppr, Q(W, "pStyle")); pstyle.set(Q(W, "val"), style_id)
    etree.SubElement(ppr, Q(W, "keepNext")); etree.SubElement(ppr, Q(W, "keepLines"))
    spacing = etree.SubElement(ppr, Q(W, "spacing")); spacing.set(Q(W, "before"), "0"); spacing.set(Q(W, "after"), "240"); spacing.set(Q(W, "line"), "240"); spacing.set(Q(W, "lineRule"), "auto")
    jc = etree.SubElement(ppr, Q(W, "jc")); jc.set(Q(W, "val"), "center")
    old = title.find("w:pPr", NS)
    if old is not None: title.replace(old, ppr)
    else: title.insert(0, ppr)
    for run in title.xpath("./w:r", namespaces=NS):
        rpr = run.find("w:rPr", NS)
        if rpr is None: rpr = etree.Element(Q(W, "rPr")); run.insert(0, rpr)
        fonts = rpr.find("w:rFonts", NS)
        if fonts is None: fonts = etree.SubElement(rpr, Q(W, "rFonts"))
        for key, font in (("ascii", "Times New Roman"), ("hAnsi", "Times New Roman"), ("eastAsia", "宋体"), ("cs", "Times New Roman")):
            fonts.set(Q(W, key), font)
        if rpr.find("w:b", NS) is None: etree.SubElement(rpr, Q(W, "b"))
        for key in ("sz", "szCs"):
            node = rpr.find(f"w:{key}", NS)
            if node is None: node = etree.SubElement(rpr, Q(W, key))
            node.set(Q(W, "val"), "32")
    style = styles.find(f"w:style[@w:styleId='{style_id}']", NS)
    if style is not None:
        style_ppr = style.find("w:pPr", NS)
        if style_ppr is None: style_ppr = etree.SubElement(style, Q(W, "pPr"))
        for child in list(style_ppr): style_ppr.remove(child)
        for child in list(ppr)[1:]: style_ppr.append(deepcopy(child))


def availability(root, lang):
    if lang == "zh":
        current = find_para(root, "本研究所用公开数据源见")
        lines = [
            "本研究所用公开数据源列于Additional file 2的Table S1。处理后的审计表和复现材料包含在Additional files 1–4中。",
            "当前可核验的公开release为：https://github.com/zfr0857/FZYC-Mol/releases/tag/paper-release-2026-07-r9。",
            "固定commit为：9635a902fa3cc7bb7b71a234c1b2bbbe415193f0。",
            "Additional file 4包含该公开基础及发布后新增的paper43十种子完成层。由于该完成层尚未出现在可核验的公开r10 tag中，仓库同步仍是投稿阻断项。",
            "本轮审阅时没有可用的独立归档DOI。",
        ]
    else:
        current = find_para(root, "The datasets supporting this article are public")
        lines = [
            "The datasets supporting this article are public; source details are listed in Additional file 2, Table S1. Processed audit tables and reproducibility materials are included in Additional files 1–4.",
            "Verified public release: https://github.com/zfr0857/FZYC-Mol/releases/tag/paper-release-2026-07-r9.",
            "Immutable commit: 9635a902fa3cc7bb7b71a234c1b2bbbe415193f0.",
            "Additional file 4 contains that portable base plus the post-release paper43 ten-seed completion overlay. Because the overlay is not present in a verified public r10 tag, repository synchronization remains a submission blocker.",
            "No separate archival DOI was available at the time of this review.",
        ]
    replace_para(current, lines[0]); anchor = current
    for value in lines[1:]:
        new = deepcopy(current); replace_para(new, value); anchor.addnext(new); anchor = new
    for paragraph in [current] + [current.getnext() for _ in []]:
        pass
    node = current
    for _ in lines:
        ppr = node.find("w:pPr", NS)
        if ppr is None: ppr = etree.Element(Q(W, "pPr")); node.insert(0, ppr)
        for child in list(ppr):
            if child.tag in {Q(W, "spacing"), Q(W, "ind"), Q(W, "jc")}:
                ppr.remove(child)
        spacing = etree.SubElement(ppr, Q(W, "spacing")); spacing.set(Q(W, "after"), "120"); spacing.set(Q(W, "line"), "276"); spacing.set(Q(W, "lineRule"), "auto")
        indent = etree.SubElement(ppr, Q(W, "ind")); indent.set(Q(W, "left"), "0"); indent.set(Q(W, "right"), "0"); indent.set(Q(W, "firstLine"), "0")
        jc = etree.SubElement(ppr, Q(W, "jc")); jc.set(Q(W, "val"), "left")
        node = node.getnext()


def table3(root, lang):
    body = root.find("w:body", NS); tables = body.findall("w:tbl", NS)
    first, second = tables[2], tables[3]
    header = deepcopy(first.find("w:tr", NS)); row_template = deepcopy(first.findall("w:tr", NS)[1])
    defs_en = [
        (S_MAIN, "number of primary split seeds (10)"), (S_SECONDARY, "number of seeds in explicitly labelled secondary analyses (5)"),
        (mi("s"), "split seed"), (mi("F"), "number of outer folds per seed (3)"), (mi("f"), "outer fold"),
        (mi("u") + mo("=") + par(mi("s") + mo(",") + mi("f")), "outer audit unit"), (U_MINUS_S, "outer audit units from seeds other than held-out seed s"),
        (N_MINUS_S, "number of units in U_-s; N_-s = |U_-s|"), (mi("j"), "candidate"), (mi("K"), "candidate count"),
        (C_K, "eligible registered candidate prefix at size K"), (call(mi("V"), [mi("u"), mi("j")]), "inner-validation utility"),
        (call(mi("A"), [mi("u"), mi("j")]), "outer-audit utility (negative RMSE direction for regression)"), (TAU, "practical-equivalence reporting tolerance"),
        (EPS_NUM, "numerical-stability constant, fixed at 10^-12"), (call(J_HAT, [mi("K")]), "validation-selected candidate at size K"),
        (call(J_REF_INV, [MINUS_S]), "K-invariant full-registry reference selected without seed s"), (call(J_REF_DEP, [MINUS_S, mi("K")]), "K-dependent eligible-prefix reference selected without seed s"),
        (call(G_INV, [mi("u"), mi("K")]), "K-invariant full-registry completion gap"), (call(G_DEP, [mi("u"), mi("K")]), "K-dependent within-prefix selection gap"),
        (call(G_SAME, [mi("u"), mi("K")]), "same-fold finite-set opportunity gap"), (call(G_AVAIL, [mi("u"), mi("K")]), "availability component; G_inv = G_avail + G_dep"),
        (call(GBAR, [mi("K")]), "seed-level mean of G_inv across the three outer folds"), (call(DELTA_INV, [mi("e")]), "endpoint-level K=32 minus K=4 contrast averaged over seed blocks"),
        (S_COV, "sample covariance matrix in Ledoit-Wolf shrinkage"), (LAMBDA_I, "non-negative shrinkage-correlation eigenvalue"),
        (P_I, "unit-sum eigenvalue proportion"), (PI_J, "selection proportion for candidate j"),
    ]
    defs_zh = [
        (expr, value) for expr, value in defs_en
    ]
    translations = [
        "主要分析的划分种子数（10）", "明确标注的次要分析所用种子数（5）", "划分种子", "每个种子的外层折数（3）", "外层折", "外层审计单元",
        "除留出种子s以外的外层审计单元集合", "U_-s中的审计单元数；N_-s = |U_-s|", "候选", "候选数量", "规模K下符合资格的预注册候选前缀",
        "内层验证效用", "外层审计效用（回归使用负RMSE方向）", "实用等价报告容差", "数值稳定常数，固定为10^-12", "规模K下由内层验证选择的候选",
        "不使用种子s选出的K不变完整候选库参考", "不使用种子s、在合资格前缀内选出的K依赖参考", "K不变完整候选库完成差距",
        "K依赖合资格前缀选择差距", "同折有限集合机会差距", "可用性分量；G_inv = G_avail + G_dep", "每个种子内3个外层折的G_inv均值",
        "以种子为区组的端点层K=32减K=4对比", "Ledoit-Wolf收缩中的样本协方差矩阵", "收缩相关矩阵的非负特征值", "和为1的特征值比例", "候选j的选择比例",
    ]
    if lang == "zh": defs = [(expr, translations[i]) for i, (expr, _) in enumerate(defs_zh)]
    else: defs = defs_en

    def make_row(expr, definition):
        row_node = deepcopy(row_template); cells = row_node.findall("w:tc", NS)
        for cell, content, is_math in ((cells[0], expr, True), (cells[1], definition, False)):
            for child in list(cell):
                if child.tag != Q(W, "tcPr"): cell.remove(child)
            p = etree.SubElement(cell, Q(W, "p"))
            if is_math: p.append(mathml(content))
            else: p.append(text_run(content))
        return row_node

    rows = [make_row(expr, definition) for expr, definition in defs]
    for table, subset in ((first, rows[:14]), (second, rows[14:])):
        for row_node in table.findall("w:tr", NS): table.remove(row_node)
        table.append(deepcopy(header))
        for row_node in subset: table.append(row_node)


def update_figure8_media(root_path, document, relationships):
    drawing = document.xpath("//w:p[.//w:drawing]", namespaces=NS)[7]
    rid = drawing.xpath(".//a:blip/@r:embed", namespaces=NS)[0]
    target = next(rel.get("Target") for rel in relationships.xpath("//pr:Relationship", namespaces=NS) if rel.get("Id") == rid)
    shutil.copy2(FIGURE8, root_path / "word" / target.replace("/", "\\"))


def revise_main(lang):
    root_path = ROOTS[lang]; parser = etree.XMLParser(remove_blank_text=False)
    doc_path = root_path / "word" / "document.xml"; styles_path = root_path / "word" / "styles.xml"; rels_path = root_path / "word" / "_rels" / "document.xml.rels"
    document = etree.parse(str(doc_path), parser); styles = etree.parse(str(styles_path), parser); rels = etree.parse(str(rels_path), parser)
    root = document.getroot()
    rebuild_numbered_equations(root)
    update_ranges(root, lang); update_core_text(root, lang); replace_result_311(root, lang)
    move_figure1(root); availability(root, lang); table3(root, lang); title_style(root, styles.getroot(), lang)
    inline_count = native_inline_math(root); update_figure8_media(root_path, root, rels.getroot())
    doc_path.write_bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes"))
    styles_path.write_bytes(etree.tostring(styles.getroot(), xml_declaration=True, encoding="UTF-8", standalone="yes"))
    print(lang, "inline_native", inline_count)


def revise_supplement():
    root_path = ROOTS["supp"]; path = root_path / "word" / "document.xml"; parser = etree.XMLParser(remove_blank_text=False)
    document = etree.parse(str(path), parser); root = document.getroot()
    paragraph = find_para(root, "For each held-out seed")
    replace_para(paragraph, "For each held-out seed s, j_ref^inv(−s) was selected once from all 32 candidates using the other nine seeds; j_ref^dep(−s,K) was selected analogously within C_K. For u = (s,f), G_inv and G_dep subtract the utility of j-hat_u(K) from the respective reference utility, G_same subtracts it from the same-fold eligible maximum, and G_avail is the K-invariant reference utility minus the K-dependent reference utility. Thus G_inv = G_avail + G_dep exactly. The seed-level mean Gbar_inv,e,s(K) first averages G_inv over the three outer folds. Delta_inv(e) then averages Gbar_inv,e,s(32) − Gbar_inv,e,s(4) over the ten seed blocks; negative values favour the smaller full-registry completion gap at K = 32. Practical-equivalence tolerance τ grids were 0.005/0.010/0.020 ROC-AUC and 0.025/0.050/0.100 RMSE and remain retrospective reporting tolerances rather than minimum important differences. The distinct numerical-stability constant ε_num = 10^−12 is used only for floating-point stabilization and small-denominator missingness.")
    count = native_inline_math(root)
    path.write_bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes"))
    print("supp inline_native", count)


if __name__ == "__main__":
    revise_main("zh")
    revise_main("en")
    revise_supplement()
