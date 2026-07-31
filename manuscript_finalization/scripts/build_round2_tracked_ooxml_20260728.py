from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import shutil
import zipfile

from lxml import etree

ROOT = Path(r"D:\fzyc\output\paper43_jcheminform_completion_20260726\author_review")
WORK = Path(r"D:\fzyc\work\round2_tracked_ooxml_20260728")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NS = {"w": W, "m": M}
Q = lambda ns, name: f"{{{ns}}}{name}"
STAMP = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def plain(node): return "".join(node.xpath(".//w:t/text()", namespaces=NS))
def full(node): return "".join(node.xpath(".//w:t/text() | .//m:t/text()", namespaces=NS))


def run(value, deleted=False):
    node = etree.Element(Q(W, "r")); props = etree.SubElement(node, Q(W, "rPr")); fonts = etree.SubElement(props, Q(W, "rFonts"))
    for key, font in (("ascii", "Times New Roman"), ("hAnsi", "Times New Roman"), ("eastAsia", "宋体"), ("cs", "Times New Roman")):
        fonts.set(Q(W, key), font)
    text = etree.SubElement(node, Q(W, "delText" if deleted else "t")); text.text = value
    return node


def revision(tag, revision_id, children):
    node = etree.Element(Q(W, tag)); node.set(Q(W, "id"), str(revision_id)); node.set(Q(W, "author"), "OpenAI Codex"); node.set(Q(W, "date"), STAMP)
    for child in children: node.append(child)
    return node


def mark_replacement(paragraph, old_text, revision_id):
    children = [deepcopy(child) for child in paragraph if child.tag != Q(W, "pPr")]
    for child in list(paragraph):
        if child.tag != Q(W, "pPr"): paragraph.remove(child)
    paragraph.append(revision("del", revision_id, [run(old_text, True)]))
    paragraph.append(revision("ins", revision_id + 1, children))
    return revision_id + 2


def mark_insertion(paragraph, revision_id):
    children = [deepcopy(child) for child in paragraph if child.tag != Q(W, "pPr")]
    for child in list(paragraph):
        if child.tag != Q(W, "pPr"): paragraph.remove(child)
    paragraph.append(revision("ins", revision_id, children))
    return revision_id + 1


def find(root, starts):
    return next(p for p in root.xpath("//w:p", namespaces=NS) if plain(p).startswith(starts))


def build(clean, old, output, lang):
    work = WORK / lang
    if work.exists(): shutil.rmtree(work)
    work.mkdir(parents=True)
    with zipfile.ZipFile(clean) as archive: archive.extractall(work)
    with zipfile.ZipFile(old) as archive: old_root = etree.fromstring(archive.read("word/document.xml"))
    doc_path = work / "word" / "document.xml"; settings_path = work / "word" / "settings.xml"
    parser = etree.XMLParser(remove_blank_text=False); document = etree.parse(str(doc_path), parser); settings = etree.parse(str(settings_path), parser)
    root = document.getroot(); revision_id = 1

    pairs = [
        ("结果：相对于K不变完整候选库参考", "结果：相对于K不变完整候选库参考"),
        ("数值稳定常数取", "数值稳定常数取"),
        ("分类任务回顾性锁定的ROC-AUC容差网格", "分类任务回顾性锁定的ROC-AUC实用等价容差"),
        ("固定K = 32交叉拟合参考身份", "固定K = 32交叉拟合参考身份"),
        ("图8. 十种子主要审计中的实用等价", "图8. 十种子主要审计中的实用等价"),
        ("实用等价集合可将注意力", "实用等价集合可将注意力"),
        ("ε容差是回顾性锁定", "实用等价容差"),
        ("本研究所用公开数据源见", "本研究所用公开数据源列于"),
    ] if lang == "zh" else [
        ("Results: Against the K-invariant full-registry reference", "Results: Against the K-invariant full-registry reference"),
        ("We used the numerical-stability constant", "We used the numerical-stability constant"),
        ("Retrospectively locked sensitivity grids", "Retrospectively locked practical-equivalence tolerance"),
        ("Holding the K = 32 cross-fitted reference identity", "Holding the K = 32 cross-fitted reference identity"),
        ("Figure 8. Practical equivalence and metric-dependent selection", "Figure 8. Practical equivalence and metric-dependent selection"),
        ("Near-equivalent sets prevent negligible", "Near-equivalent sets prevent negligible"),
        ("The ε tolerances are retrospectively locked", "The practical-equivalence tolerances"),
        ("The datasets supporting this article are public", "The datasets supporting this article are public"),
    ]
    for old_start, new_start in pairs:
        revision_id = mark_replacement(find(root, new_start), full(find(old_root, old_start)), revision_id)

    heading = "3.11 实用等价" if lang == "zh" else "3.11 Practical equivalence"
    body = root.find("w:body", NS); paras = body.findall("w:p", NS); h = next(i for i, p in enumerate(paras) if plain(p).startswith(heading))
    revision_id = mark_insertion(paras[h + 2], revision_id)

    availability_start = "本研究所用公开数据源列于" if lang == "zh" else "The datasets supporting this article are public"
    first_avail = find(root, availability_start); node = first_avail.getnext()
    for _ in range(4):
        revision_id = mark_insertion(node, revision_id); node = node.getnext()

    old_numbered = {}
    for p in old_root.xpath("//w:p[.//m:oMath]", namespaces=NS):
        number = plain(p).strip()
        if number.startswith("(") and number.endswith(")"):
            try: old_numbered[int(number[1:-1])] = p
            except ValueError: pass
    new_numbered = {}
    for p in root.xpath("//w:p[.//m:oMath]", namespaces=NS):
        number = plain(p).strip()
        if number.startswith("(") and number.endswith(")"):
            try: new_numbered[int(number[1:-1])] = p
            except ValueError: pass
    mapping = {1: 1, **{old_n: old_n + 1 for old_n in range(2, 12)}, **{old_n: old_n + 2 for old_n in range(12, 20)}}
    for old_n, new_n in mapping.items():
        revision_id = mark_replacement(new_numbered[new_n], f"{full(old_numbered[old_n])} ({old_n})", revision_id)
    revision_id = mark_insertion(new_numbered[2], revision_id)
    revision_id = mark_insertion(new_numbered[13], revision_id)

    table3 = root.xpath("//w:body/w:tbl", namespaces=NS)[2:4]
    for table in table3:
        for row in table.findall("w:tr", NS)[1:]:
            trpr = row.find("w:trPr", NS)
            if trpr is None: trpr = etree.Element(Q(W, "trPr")); row.insert(0, trpr)
            ins = etree.Element(Q(W, "ins")); ins.set(Q(W, "id"), str(revision_id)); ins.set(Q(W, "author"), "OpenAI Codex"); ins.set(Q(W, "date"), STAMP); trpr.insert(0, ins); revision_id += 1

    settings_root = settings.getroot()
    if settings_root.find("w:trackRevisions", NS) is None:
        proof = settings_root.find("w:proofState", NS); marker = etree.Element(Q(W, "trackRevisions"))
        settings_root.insert(settings_root.index(proof) + 1 if proof is not None else 0, marker)
    doc_path.write_bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes"))
    settings_path.write_bytes(etree.tostring(settings_root, xml_declaration=True, encoding="UTF-8", standalone="yes"))
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
        for path in sorted(work.rglob("*")):
            if path.is_file(): archive.write(path, path.relative_to(work).as_posix())
    print(lang, "revision_elements", revision_id - 1, output)


build(
    ROOT / "候选池扩张_有限验证下的机会与选择稳定性_中文最终修订稿_R2_CONFLICT_HOLD.docx",
    ROOT / "候选池扩张_有限验证下的机会与选择稳定性_中文最终修订稿_CONFLICT_HOLD.docx",
    ROOT / "候选池扩张_有限验证下的机会与选择稳定性_中文最终修订痕迹稿_R2_CONFLICT_HOLD.docx",
    "zh",
)
build(
    ROOT / "Main_manuscript_Journal_of_Cheminformatics_FINAL_REVISED_R2_CONFLICT_HOLD.docx",
    ROOT / "Main_manuscript_Journal_of_Cheminformatics_FINAL_REVISED_CONFLICT_HOLD.docx",
    ROOT / "Main_manuscript_Journal_of_Cheminformatics_FINAL_REVISED_TRACK_CHANGES_R2_CONFLICT_HOLD.docx",
    "en",
)

