from __future__ import annotations

import hashlib
import os
import posixpath
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(r"D:\fzyc\output\paper32_equation_table_format_20260718")
ORIGINAL = ROOT / "main_figures" / "Figure7_original.svg"
DOCS = [
    ROOT / "Candidate_pool_expansion_Journal_of_Cheminformatics_final_unified_format.docx",
    ROOT / "Chinese_manuscript_final_unified_format.docx",
]

NS = {
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def figure7_svg_entry(archive: zipfile.ZipFile) -> str:
    document = ET.fromstring(archive.read("word/document.xml"))
    inlines = document.findall(".//wp:inline", NS)
    if len(inlines) != 7:
        raise RuntimeError(f"Expected 7 inline figures, found {len(inlines)}")

    svg_relationship_id = None
    for element in inlines[-1].iter():
        if element.tag.endswith("}svgBlip"):
            svg_relationship_id = element.get(f"{{{NS['r']}}}embed")
            break
    if not svg_relationship_id:
        raise RuntimeError("Figure 7 has no SVG relationship")

    relationships = ET.fromstring(archive.read("word/_rels/document.xml.rels"))
    target = None
    for relationship in relationships.findall("rel:Relationship", NS):
        if relationship.get("Id") == svg_relationship_id:
            target = relationship.get("Target")
            break
    if not target:
        raise RuntimeError(f"Missing relationship target for {svg_relationship_id}")

    entry = posixpath.normpath(posixpath.join("word", target))
    if not entry.lower().endswith(".svg"):
        raise RuntimeError(f"Figure 7 relationship is not SVG: {entry}")
    return entry


def replace_entry(docx: Path, original: bytes) -> tuple[str, str]:
    with zipfile.ZipFile(docx, "r") as source:
        target = figure7_svg_entry(source)
        entries = source.infolist()
        payloads = {entry.filename: source.read(entry.filename) for entry in entries}

    payloads[target] = original
    fd, temporary_name = tempfile.mkstemp(suffix=".docx", dir=docx.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w") as destination:
            for entry in entries:
                destination.writestr(entry, payloads[entry.filename])
        os.replace(temporary, docx)
    finally:
        if temporary.exists():
            temporary.unlink()

    with zipfile.ZipFile(docx, "r") as check:
        embedded_hash = sha256(check.read(target))
    return target, embedded_hash


def main() -> None:
    original = ORIGINAL.read_bytes()
    original_hash = sha256(original)
    for docx in DOCS:
        target, embedded_hash = replace_entry(docx, original)
        if embedded_hash != original_hash:
            raise RuntimeError(f"Exact SVG verification failed for {docx}")
        print(f"{docx.name}: {target} = {embedded_hash}")
    print(f"original: {original_hash}")


if __name__ == "__main__":
    main()
