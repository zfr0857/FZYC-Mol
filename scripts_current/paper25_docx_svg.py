from __future__ import annotations

import re
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree


A = "http://schemas.openxmlformats.org/drawingml/2006/main"
ASVG = "http://schemas.microsoft.com/office/drawing/2016/SVG/main"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
SVG_EXTENSION_URI = "{96DAC541-7B7A-43D3-8B79-37D633B846F1}"


def _next_relationship_id(relationships: etree._Element) -> str:
    numbers = []
    for relationship in relationships:
        match = re.fullmatch(r"rId(\d+)", relationship.get("Id", ""))
        if match:
            numbers.append(int(match.group(1)))
    return f"rId{max(numbers, default=0) + 1}"


def embed_svg_figures(docx_path: Path | str, figure_dir: Path | str) -> list[str]:
    """Attach SVG sources to Word drawings while retaining their PNG fallbacks."""
    docx_path = Path(docx_path)
    figure_dir = Path(figure_dir)
    with ZipFile(docx_path) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}

    document = etree.fromstring(members["word/document.xml"])
    relationships = etree.fromstring(members["word/_rels/document.xml.rels"])
    content_types = etree.fromstring(members["[Content_Types].xml"])
    namespaces = {"a": A, "asvg": ASVG, "pic": PIC, "r": R}
    relationship_targets = {
        relationship.get("Target"): relationship.get("Id")
        for relationship in relationships
    }
    embedded: list[str] = []

    for picture in document.xpath(".//pic:pic", namespaces=namespaces):
        names = picture.xpath(".//pic:cNvPr/@name", namespaces=namespaces)
        if not names or Path(names[0]).suffix.lower() != ".png":
            continue
        svg = figure_dir / Path(names[0]).with_suffix(".svg").name
        if not svg.exists():
            continue
        blips = picture.xpath(".//a:blip", namespaces=namespaces)
        if not blips:
            continue
        blip = blips[0]
        existing = blip.xpath("./a:extLst/a:ext/asvg:svgBlip", namespaces=namespaces)
        if existing:
            continue

        media_name = svg.name
        target = f"media/{media_name}"
        relationship_id = relationship_targets.get(target)
        if relationship_id is None:
            relationship_id = _next_relationship_id(relationships)
            relationship = etree.SubElement(relationships, f"{{{PR}}}Relationship")
            relationship.set("Id", relationship_id)
            relationship.set(
                "Type",
                "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
            )
            relationship.set("Target", target)
            relationship_targets[target] = relationship_id

        extension_list = etree.SubElement(blip, f"{{{A}}}extLst")
        extension = etree.SubElement(extension_list, f"{{{A}}}ext")
        extension.set("uri", SVG_EXTENSION_URI)
        svg_blip = etree.SubElement(extension, f"{{{ASVG}}}svgBlip")
        svg_blip.set(f"{{{R}}}embed", relationship_id)
        members[f"word/media/{media_name}"] = svg.read_bytes()
        embedded.append(svg.stem)

    has_svg_type = content_types.xpath(
        './ct:Default[translate(@Extension,"SVG","svg")="svg"]',
        namespaces={"ct": CT},
    )
    if embedded and not has_svg_type:
        default = etree.SubElement(content_types, f"{{{CT}}}Default")
        default.set("Extension", "svg")
        default.set("ContentType", "image/svg+xml")

    if not embedded:
        return embedded

    etree.register_namespace("asvg", ASVG)
    members["word/document.xml"] = etree.tostring(
        document, encoding="UTF-8", xml_declaration=True, standalone=True
    )
    members["word/_rels/document.xml.rels"] = etree.tostring(
        relationships, encoding="UTF-8", xml_declaration=True, standalone=True
    )
    members["[Content_Types].xml"] = etree.tostring(
        content_types, encoding="UTF-8", xml_declaration=True, standalone=True
    )

    with tempfile.NamedTemporaryFile(
        suffix=".docx", dir=docx_path.parent, delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with ZipFile(temporary_path, "w", ZIP_DEFLATED) as archive:
            for name, payload in members.items():
                archive.writestr(name, payload)
        temporary_path.replace(docx_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return embedded
