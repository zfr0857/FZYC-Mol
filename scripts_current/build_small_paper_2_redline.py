from __future__ import annotations

import copy
import difflib
import re
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "output" / "初稿-10_比较副本.docx"
REVISED = ROOT / "output" / "小论文-2.docx"
OUTPUT = ROOT / "output" / "小论文-2_修订痕迹.docx"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
Q = lambda name: f"{{{W}}}{name}"


class Tracker:
    def __init__(self) -> None:
        self.identifier = 1
        self.date = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def change(self, tag: str) -> etree._Element:
        node = etree.Element(Q(tag))
        node.set(Q("id"), str(self.identifier))
        node.set(Q("author"), "Codex")
        node.set(Q("date"), self.date)
        self.identifier += 1
        return node


def paragraph_text(paragraph: etree._Element) -> str:
    return "".join(paragraph.xpath(".//w:t/text() | .//w:delText/text()", namespaces=NS))


def direct_paragraphs(root: etree._Element) -> list[etree._Element]:
    body = root.find("w:body", NS)
    assert body is not None
    return [child for child in body if child.tag == Q("p")]


def run_properties(paragraph: etree._Element) -> etree._Element | None:
    rpr = paragraph.find(".//w:r/w:rPr", NS)
    return copy.deepcopy(rpr) if rpr is not None else None


def deleted_run(text: str, paragraph: etree._Element, tracker: Tracker) -> etree._Element:
    deletion = tracker.change("del")
    run = etree.SubElement(deletion, Q("r"))
    rpr = run_properties(paragraph)
    if rpr is not None:
        run.append(rpr)
    node = etree.SubElement(run, Q("delText"))
    if text.startswith(" ") or text.endswith(" "):
        node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    node.text = text
    return deletion


def track_replacement(paragraph: etree._Element, old_text: str, tracker: Tracker) -> None:
    children = [child for child in list(paragraph) if child.tag != Q("pPr")]
    for child in children:
        paragraph.remove(child)
    paragraph.append(deleted_run(old_text, paragraph, tracker))
    insertion = tracker.change("ins")
    for child in children:
        insertion.append(child)
    paragraph.append(insertion)


def track_insertion(paragraph: etree._Element, tracker: Tracker) -> None:
    children = [child for child in list(paragraph) if child.tag != Q("pPr")]
    for child in children:
        paragraph.remove(child)
    insertion = tracker.change("ins")
    for child in children:
        insertion.append(child)
    paragraph.append(insertion)


def deletion_paragraph(original: etree._Element, tracker: Tracker) -> etree._Element:
    paragraph = etree.Element(Q("p"), nsmap=original.nsmap)
    ppr = original.find("w:pPr", NS)
    if ppr is not None:
        paragraph.append(copy.deepcopy(ppr))
    paragraph.append(deleted_run(paragraph_text(original), original, tracker))
    return paragraph


def track_main_paragraphs(original_root: etree._Element, revised_root: etree._Element, tracker: Tracker) -> None:
    original = direct_paragraphs(original_root)
    revised = direct_paragraphs(revised_root)
    old_text = [paragraph_text(paragraph) for paragraph in original]
    new_text = [paragraph_text(paragraph) for paragraph in revised]
    matcher = difflib.SequenceMatcher(a=old_text, b=new_text, autojunk=False)
    body = revised_root.find("w:body", NS)
    assert body is not None
    for tag, i1, i2, j1, j2 in reversed(matcher.get_opcodes()):
        if tag == "equal":
            continue
        current = direct_paragraphs(revised_root)
        if tag == "insert":
            for paragraph in current[j1:j2]:
                track_insertion(paragraph, tracker)
            continue
        if tag == "delete":
            anchor = current[j1] if j1 < len(current) else revised_root.find("w:body/w:sectPr", NS)
            for paragraph in original[i1:i2]:
                created = deletion_paragraph(paragraph, tracker)
                if anchor is None:
                    body.append(created)
                else:
                    anchor.addprevious(created)
            continue
        paired = min(i2 - i1, j2 - j1)
        for offset in range(paired):
            track_replacement(current[j1 + offset], old_text[i1 + offset], tracker)
        if j2 - j1 > paired:
            for paragraph in current[j1 + paired : j2]:
                track_insertion(paragraph, tracker)
        if i2 - i1 > paired:
            current = direct_paragraphs(revised_root)
            anchor_index = j1 + paired
            anchor = current[anchor_index] if anchor_index < len(current) else revised_root.find("w:body/w:sectPr", NS)
            for paragraph in original[i1 + paired : i2]:
                created = deletion_paragraph(paragraph, tracker)
                if anchor is None:
                    body.append(created)
                else:
                    anchor.addprevious(created)


def track_tables(original_root: etree._Element, revised_root: etree._Element, tracker: Tracker) -> None:
    old_cells = original_root.xpath(".//w:tbl//w:tc", namespaces=NS)
    new_cells = revised_root.xpath(".//w:tbl//w:tc", namespaces=NS)
    for old_cell, new_cell in zip(old_cells, new_cells, strict=True):
        old_text = "\n".join(paragraph_text(p) for p in old_cell.xpath("./w:p", namespaces=NS))
        new_text = "\n".join(paragraph_text(p) for p in new_cell.xpath("./w:p", namespaces=NS))
        if old_text == new_text:
            continue
        paragraph = new_cell.find("w:p", NS)
        if paragraph is not None:
            track_replacement(paragraph, old_text, tracker)


def enable_tracking(settings: etree._Element) -> None:
    for node in settings.findall("w:trackRevisions", NS):
        settings.remove(node)
    track = etree.Element(Q("trackRevisions"))
    proof = settings.find("w:proofState", NS)
    if proof is None:
        settings.insert(0, track)
    else:
        proof.addnext(track)


def build() -> Path:
    parser = etree.XMLParser(remove_blank_text=False)
    with ZipFile(ORIGINAL) as archive:
        original_xml = etree.fromstring(archive.read("word/document.xml"), parser)
    with ZipFile(REVISED) as archive:
        revised_xml = etree.fromstring(archive.read("word/document.xml"), parser)
        settings_xml = etree.fromstring(archive.read("word/settings.xml"), parser)
        members = {name: archive.read(name) for name in archive.namelist()}

    tracker = Tracker()
    track_main_paragraphs(original_xml, revised_xml, tracker)
    track_tables(original_xml, revised_xml, tracker)
    enable_tracking(settings_xml)
    members["word/document.xml"] = etree.tostring(revised_xml, xml_declaration=True, encoding="UTF-8", standalone="yes")
    members["word/settings.xml"] = etree.tostring(settings_xml, xml_declaration=True, encoding="UTF-8", standalone="yes")
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    with ZipFile(OUTPUT) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("tracked DOCX ZIP validation failed")
        document = archive.read("word/document.xml")
        if not re.search(br"<w:ins(?:\s|>)", document) or not re.search(br"<w:del(?:\s|>)", document):
            raise RuntimeError("tracked DOCX contains no revisions")
    return OUTPUT


if __name__ == "__main__":
    print(build())
