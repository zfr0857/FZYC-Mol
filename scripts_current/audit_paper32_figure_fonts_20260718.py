from __future__ import annotations

import hashlib
import json
import posixpath
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(r"D:\fzyc\output\paper32_equation_table_format_20260718")
SOURCE_ROOT = Path(r"D:\fzyc\output\paper30_submission_package_20260717\main_figures")
DOCS = [
    ROOT / "Candidate_pool_expansion_Journal_of_Cheminformatics_final_unified_format.docx",
    ROOT / "Chinese_manuscript_final_unified_format.docx",
]
SOURCES = [SOURCE_ROOT / f"Figure{i}.svg" for i in range(1, 7)] + [
    ROOT / "main_figures" / "Figure7_final_requested.svg"
]

NS = {
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}
FAMILY_RE = re.compile(
    r"font-family\s*:\s*([^;\"}]+)|font-family\s*=\s*[\"']([^\"']+)",
    flags=re.I,
)
SHORTHAND_RE = re.compile(r"(?:^|[;\"]\s*)font\s*:\s*[^;]*?[\"']([^\"']+)[\"']", flags=re.I)
SUSPECT_FONTS = ["Arial", "Calibri", "Helvetica", "DejaVu", "Liberation", "sans-serif"]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def inspect_svg(data: bytes) -> dict:
    text = data.decode("utf-8", errors="replace")
    families = []
    for match in FAMILY_RE.finditer(text):
        family = (match.group(1) or match.group(2)).strip().strip("'\"")
        if family not in families:
            families.append(family)
    for match in SHORTHAND_RE.finditer(text):
        family = match.group(1).strip()
        if family not in families:
            families.append(family)
    suspect = [font for font in SUSPECT_FONTS if re.search(re.escape(font), text, flags=re.I)]
    return {
        "sha256": sha256(data),
        "font_families": families,
        "all_explicit_text_times_new_roman": bool(families)
        and all(family.casefold() == "times new roman" for family in families),
        "suspect_font_tokens": suspect,
        "text_nodes": len(re.findall(r"<text\b", text)),
        "path_nodes": len(re.findall(r"<path\b", text)),
        "embedded_raster_images": len(re.findall(r"<image\b", text)),
    }


def inspect_docx(path: Path) -> list[dict]:
    with zipfile.ZipFile(path) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))
        relationships = ET.fromstring(archive.read("word/_rels/document.xml.rels"))
        relationship_targets = {
            rel.get("Id"): rel.get("Target")
            for rel in relationships.findall("rel:Relationship", NS)
        }
        svg_entries = sorted(
            [name for name in archive.namelist() if name.lower().endswith(".svg")],
            key=lambda name: int(re.search(r"(\d+)\.svg$", name).group(1)),
        )
        results = []
        for index, inline in enumerate(document.findall(".//wp:inline", NS), start=1):
            relationship_id = None
            for element in inline.iter():
                if element.tag.endswith("}svgBlip"):
                    relationship_id = element.get(f"{{{NS['r']}}}embed")
                    break
            if not relationship_id:
                if index - 1 >= len(svg_entries):
                    results.append(
                        {
                            "figure": index,
                            "error": "No SVG relationship or SVG media entry; raster fallback only",
                            "font_metadata_auditable": False,
                        }
                    )
                    continue
                entry = svg_entries[index - 1]
            else:
                target = relationship_targets[relationship_id]
                entry = posixpath.normpath(posixpath.join("word", target))
            item = {"figure": index, "embedded_entry": entry}
            item.update(inspect_svg(archive.read(entry)))
            results.append(item)
        return results


def main() -> None:
    sources = []
    for index, path in enumerate(SOURCES, start=1):
        item = {"figure": index, "file": str(path)}
        item.update(inspect_svg(path.read_bytes()))
        sources.append(item)

    documents = {path.name: inspect_docx(path) for path in DOCS}
    embedded_pairs_match = all(
        documents[DOCS[0].name][i].get("sha256")
        == documents[DOCS[1].name][i].get("sha256")
        for i in range(7)
    )
    all_source_vector_text_compliant = all(
        item["all_explicit_text_times_new_roman"] and not item["suspect_font_tokens"]
        for item in sources
    )
    all_embedded_vector_text_compliant = all(
        item.get("all_explicit_text_times_new_roman", False)
        and not item.get("suspect_font_tokens", [])
        for items in documents.values()
        for item in items
    )
    report = {
        "status": "passed" if all_embedded_vector_text_compliant else "review_required",
        "scope": "Figure 1-7 source SVGs and SVGs actually embedded in both final DOCX manuscripts",
        "source_svg_conclusion": "All explicit English vector text in the source SVGs uses Times New Roman."
        if all_source_vector_text_compliant
        else "At least one source SVG contains a non-Times New Roman font.",
        "final_docx_conclusion": "All embedded SVG text uses Times New Roman."
        if all_embedded_vector_text_compliant
        else "The final DOCX files are not uniformly Times New Roman: Figures 1-6 are normalized to Arial by Word; English Figure 7 remains Times New Roman, and Chinese Figure 7 is currently represented by a raster fallback without auditable font metadata.",
        "embedded_svg_assets_identical_between_manuscripts": embedded_pairs_match,
        "limitation": "Font metadata cannot prove the font of text baked into embedded raster image nodes.",
        "source_svgs": sources,
        "embedded_svgs": documents,
    }
    output = ROOT / "Figure_1-7_font_audit.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
