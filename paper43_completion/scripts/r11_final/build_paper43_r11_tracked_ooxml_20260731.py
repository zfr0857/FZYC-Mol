from __future__ import annotations

from copy import deepcopy
from difflib import SequenceMatcher
from pathlib import Path
from datetime import datetime, timezone
import re
import shutil
import zipfile

from lxml import etree


ROOT = Path(r"D:\fzyc")
REVIEW = ROOT / "output" / "paper43_jcheminform_completion_20260726" / "author_review"
WORK = ROOT / "work" / "r11_tracked_ooxml_20260731"

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NS = {"w": W, "m": M}
Q = lambda ns, name: f"{{{ns}}}{name}"
STAMP = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


EN_OLD = REVIEW / "Main_manuscript_Journal_of_Cheminformatics_R10_TECHNICAL_CANDIDATE_CONFLICT_HOLD.docx"
EN_NEW = REVIEW / "Main_manuscript_Journal_of_Cheminformatics_R11_STRUCTURAL_TECHNICAL_CANDIDATE_CONFLICT_HOLD_FINAL.docx"
EN_OUT = REVIEW / "Main_manuscript_Journal_of_Cheminformatics_R11_STRUCTURAL_TECHNICAL_CANDIDATE_TRACK_CHANGES_CONFLICT_HOLD.docx"

ZH_OLD = min((p for p in REVIEW.glob("*R10*CONFLICT_HOLD.docx") if not p.name.startswith("Main_") and p.stat().st_size > 5_000_000), key=lambda p:p.stat().st_size)
ZH_NEW = REVIEW / "候选池扩张_有限验证下的机会与选择稳定性_中文稿_R11_结构技术候选版_CONFLICT_HOLD_FINAL.docx"
ZH_OUT = REVIEW / "候选池扩张_有限验证下的机会与选择稳定性_中文修订痕迹稿_R11_结构技术候选版_CONFLICT_HOLD.docx"


def ptext(p):
    return "".join(p.xpath(".//w:t/text() | .//m:t/text()", namespaces=NS))


def unzip_docx(path: Path, dest: Path):
    if dest.exists(): shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with zipfile.ZipFile(path) as z: z.extractall(dest)


def zip_docx(src: Path, dest: Path):
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        for p in sorted(src.rglob("*")):
            if p.is_file(): z.write(p, p.relative_to(src).as_posix())


def deleted_run(text: str):
    r = etree.Element(Q(W, "r")); t = etree.SubElement(r, Q(W, "delText"))
    if text.startswith(" ") or text.endswith(" "): t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text
    return r


def revision(tag: str, rid: int):
    x = etree.Element(Q(W, tag)); x.set(Q(W, "id"), str(rid)); x.set(Q(W, "author"), "OpenAI Codex"); x.set(Q(W, "date"), STAMP); return x


def next_id(root):
    vals = [int(v) for v in root.xpath("//@w:id", namespaces=NS) if str(v).isdigit()]
    return max(vals, default=0) + 1


def track_replace(p, old_text: str, rid: int):
    children = [deepcopy(c) for c in list(p) if c.tag != Q(W, "pPr")]
    for c in list(p):
        if c.tag != Q(W, "pPr"): p.remove(c)
    d = revision("del", rid); d.append(deleted_run(old_text)); p.append(d)
    ins = revision("ins", rid + 1)
    for c in children: ins.append(c)
    p.append(ins)


def track_insert(p, rid: int):
    children = [deepcopy(c) for c in list(p) if c.tag != Q(W, "pPr")]
    for c in list(p):
        if c.tag != Q(W, "pPr"): p.remove(c)
    ins = revision("ins", rid)
    for c in children: ins.append(c)
    p.append(ins)


def simple_paragraph(text: str):
    p = etree.Element(Q(W, "p")); r = etree.Element(Q(W, "r")); t = etree.SubElement(r, Q(W, "t")); t.text = text; r.append(t) if False else None
    # t is already a child of r; add r to p.
    p.append(r); return p


def marked(text: str, lang: str):
    common = ["Figure 1.", "Figure 3.", "Figure 7.", "Figure 8.", "Table 3.", "Table S47", "Equations (1)–(6)",
              "Figure 3B–C", "Figure 3A and Table 4", "shown in Figure 3A"]
    zh = ["图1.", "图3.", "图7.", "图8.", "表3.", "表S47", "公式（1）–（6）", "图3B–C", "图3A、表4",
          "10个种子", "5个种子", "留一种子（leave-one-seed-out）", "参考值为1"]
    if any(x in text for x in (common if lang == "en" else zh)): return True
    label = re.fullmatch(r"\(\d+[ab]?\)", text.strip())
    if label:
        n = int(re.match(r"\((\d+)", text).group(1)); return n >= 3
    return False


def build(old_path: Path, new_path: Path, out_path: Path, lang: str):
    dest = WORK / lang; unzip_docx(new_path, dest)
    with zipfile.ZipFile(old_path) as z: old_doc = etree.fromstring(z.read("word/document.xml"))
    parser = etree.XMLParser(remove_blank_text=False)
    dp = dest / "word" / "document.xml"; doc = etree.parse(str(dp), parser); root = doc.getroot()
    old_ps = old_doc.xpath("//w:body/w:p", namespaces=NS); new_ps = root.xpath("//w:body/w:p", namespaces=NS)
    old_texts = [ptext(p) for p in old_ps]
    rid = next_id(root); changed = 0
    for p in new_ps:
        text = ptext(p)
        # Keep native OMML outside revision wrappers for maximum Word/WPS compatibility.
        if p.xpath(".//m:oMath", namespaces=NS):
            continue
        if not text or not marked(text, lang): continue
        best = max(old_texts, key=lambda x: SequenceMatcher(None, x, text).ratio()) if old_texts else ""
        ratio = SequenceMatcher(None, best, text).ratio() if best else 0
        if ratio > 0.55 and best != text:
            track_replace(p, best, rid); rid += 2
        elif best != text:
            track_insert(p, rid); rid += 1
        else:
            continue
        changed += 1
    body = root.find(".//w:body", NS)
    summary = simple_paragraph(
        "R11 tracked revision summary: Figures 1, 3, 7 and 8, equation numbering and split definitions, the 12-symbol core Table 3, and the Supplementary Methods Table S47 cross-reference were revised."
        if lang == "en" else
        "R11修订摘要：更新图1、图3、图7和图8，拆分并重编号公式，将正文表3精简为12个核心符号，并同步补充方法表S47。"
    )
    track_insert(summary, rid); rid += 1
    body.insert(1, summary)
    settings_path = dest / "word" / "settings.xml"; settings = etree.parse(str(settings_path), parser); sr = settings.getroot()
    if sr.find("w:trackRevisions", NS) is None: sr.insert(0, etree.Element(Q(W, "trackRevisions")))
    dp.write_bytes(etree.tostring(doc, xml_declaration=True, encoding="UTF-8", standalone="yes"))
    settings_path.write_bytes(etree.tostring(settings, xml_declaration=True, encoding="UTF-8", standalone="yes"))
    zip_docx(dest, out_path)
    return changed


if __name__ == "__main__":
    WORK.mkdir(parents=True, exist_ok=True)
    print("English tracked paragraphs", build(EN_OLD, EN_NEW, EN_OUT, "en"), EN_OUT)
    print("Chinese tracked paragraphs", build(ZH_OLD, ZH_NEW, ZH_OUT, "zh"), ZH_OUT)
