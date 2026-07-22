from __future__ import annotations

import copy
import difflib
import re
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "output" / "小论文-2.docx"
REVISED = ROOT / "output" / "小论文-3.docx"
OUTPUT = ROOT / "output" / "小论文-3_修订痕迹.docx"
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


def first_rpr(paragraph: etree._Element):
    rpr = paragraph.find(".//w:r/w:rPr", NS)
    return copy.deepcopy(rpr) if rpr is not None else None


def text_node(tag: str, text: str) -> etree._Element:
    node = etree.Element(Q(tag))
    if text.startswith(" ") or text.endswith(" ") or "\n" in text:
        node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    node.text = text
    return node


def plain_run(text: str, rpr=None, deleted: bool = False) -> etree._Element:
    run = etree.Element(Q("r"))
    if rpr is not None:
        run.append(copy.deepcopy(rpr))
    run.append(text_node("delText" if deleted else "t", text))
    return run


def tracked_text(tag: str, text: str, tracker: Tracker, rpr=None) -> etree._Element:
    change = tracker.change(tag)
    change.append(plain_run(text, rpr, deleted=tag == "del"))
    return change


def track_replacement(paragraph: etree._Element, old_text: str, tracker: Tracker) -> None:
    new_text = paragraph_text(paragraph)
    rpr = first_rpr(paragraph)
    for child in list(paragraph):
        if child.tag != Q("pPr"):
            paragraph.remove(child)
    matcher = difflib.SequenceMatcher(a=list(old_text), b=list(new_text), autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            if j2 > j1:
                paragraph.append(plain_run(new_text[j1:j2], rpr))
        elif tag == "delete":
            paragraph.append(tracked_text("del", old_text[i1:i2], tracker, rpr))
        elif tag == "insert":
            paragraph.append(tracked_text("ins", new_text[j1:j2], tracker, rpr))
        else:
            paragraph.append(tracked_text("del", old_text[i1:i2], tracker, rpr))
            paragraph.append(tracked_text("ins", new_text[j1:j2], tracker, rpr))


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
    paragraph.append(tracked_text("del", paragraph_text(original), tracker, first_rpr(original)))
    return paragraph


def track_document(original_root: etree._Element, revised_root: etree._Element, tracker: Tracker) -> None:
    original = direct_paragraphs(original_root)
    revised = direct_paragraphs(revised_root)
    old_text = [paragraph_text(p) for p in original]
    new_text = [paragraph_text(p) for p in revised]
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
        elif tag == "delete":
            anchor = current[j1] if j1 < len(current) else revised_root.find("w:body/w:sectPr", NS)
            for paragraph in original[i1:i2]:
                created = deletion_paragraph(paragraph, tracker)
                body.append(created) if anchor is None else anchor.addprevious(created)
        else:
            paired = min(i2 - i1, j2 - j1)
            for offset in range(paired):
                track_replacement(current[j1 + offset], old_text[i1 + offset], tracker)
            for paragraph in current[j1 + paired:j2]:
                track_insertion(paragraph, tracker)
            if i2 - i1 > paired:
                current = direct_paragraphs(revised_root)
                anchor_index = j1 + paired
                anchor = current[anchor_index] if anchor_index < len(current) else revised_root.find("w:body/w:sectPr", NS)
                for paragraph in original[i1 + paired:i2]:
                    created = deletion_paragraph(paragraph, tracker)
                    body.append(created) if anchor is None else anchor.addprevious(created)


def enable_tracking(settings: etree._Element) -> None:
    for node in settings.findall("w:trackRevisions", NS):
        settings.remove(node)
    track = etree.Element(Q("trackRevisions"))
    proof = settings.find("w:proofState", NS)
    settings.insert(0, track) if proof is None else proof.addnext(track)


def build() -> Path:
    parser = etree.XMLParser(remove_blank_text=False)
    with ZipFile(ORIGINAL) as archive:
        original_xml = etree.fromstring(archive.read("word/document.xml"), parser)
    with ZipFile(REVISED) as archive:
        revised_xml = etree.fromstring(archive.read("word/document.xml"), parser)
        settings_xml = etree.fromstring(archive.read("word/settings.xml"), parser)
        members = {name: archive.read(name) for name in archive.namelist()}
    tracker = Tracker()
    track_document(original_xml, revised_xml, tracker)
    enable_tracking(settings_xml)
    members["word/document.xml"] = etree.tostring(revised_xml, xml_declaration=True, encoding="UTF-8", standalone="yes")
    members["word/settings.xml"] = etree.tostring(settings_xml, xml_declaration=True, encoding="UTF-8", standalone="yes")
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    with ZipFile(OUTPUT) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("tracked DOCX ZIP validation failed")
        xml = archive.read("word/document.xml")
        if not re.search(br"<w:ins(?:\s|>)", xml) or not re.search(br"<w:del(?:\s|>)", xml):
            raise RuntimeError("tracked DOCX contains no revisions")
    return OUTPUT


if __name__ == "__main__":
    print(build())
