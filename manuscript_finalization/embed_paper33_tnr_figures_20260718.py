from __future__ import annotations

import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(r"D:\fzyc\output\paper34_submission_ready_20260718")
SOURCE = Path(r"D:\fzyc\output\paper30_submission_package_20260717\main_figures")
FINAL_FIGURES = ROOT / "main_figures"
DOCS = [
    ROOT / "Candidate_pool_expansion_Journal_of_Cheminformatics_FINAL_CLEAN.docx",
    ROOT / "候选池扩张与模型选择损失_中文终稿.docx",
]
TRACKED = ROOT / "Candidate_pool_expansion_Journal_of_Cheminformatics_FINAL_TRACK_CHANGES.docx"

NS = {
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}


def stage_assets() -> None:
    FINAL_FIGURES.mkdir(parents=True, exist_ok=True)
    for figure in range(1, 7):
        for suffix in ("svg", "pdf"):
            shutil.copy2(SOURCE / f"Figure{figure}.{suffix}", FINAL_FIGURES / f"Figure{figure}.{suffix}")
        shutil.copy2(SOURCE / f"Figure{figure}_600dpi.png", FINAL_FIGURES / f"Figure{figure}_600dpi.png")


def revised_document_xml(data: bytes) -> bytes:
    ET.register_namespace("w", "http://schemas.openxmlformats.org/wordprocessingml/2006/main")
    ET.register_namespace("wp", NS["wp"])
    ET.register_namespace("a", NS["a"])
    root = ET.fromstring(data)
    inlines = root.findall(".//wp:inline", NS)
    if len(inlines) != 7:
        raise RuntimeError(f"Expected seven inline figures, found {len(inlines)}")
    final = inlines[6]
    extent = final.find("wp:extent", NS)
    if extent is None:
        raise RuntimeError("Figure 7 wp:extent not found")
    cx = int(extent.get("cx"))
    cy = round(cx * 200 / 170)
    extent.set("cy", str(cy))
    xfrm_extent = final.find(".//a:xfrm/a:ext", NS)
    if xfrm_extent is not None:
        xfrm_extent.set("cx", str(cx))
        xfrm_extent.set("cy", str(cy))
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def embed(path: Path) -> None:
    replacements: dict[str, bytes] = {}
    for figure in range(1, 7):
        replacements[f"word/media/image{2 * figure}.svg"] = (FINAL_FIGURES / f"Figure{figure}.svg").read_bytes()
        replacements[f"word/media/image{2 * figure - 1}.png"] = (FINAL_FIGURES / f"Figure{figure}_600dpi.png").read_bytes()
    replacements["word/media/image14.svg"] = (FINAL_FIGURES / "Figure7.svg").read_bytes()
    replacements["word/media/image13.png"] = (FINAL_FIGURES / "Figure7_600dpi.png").read_bytes()

    fd, temporary_name = tempfile.mkstemp(suffix=".docx", dir=path.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(path, "r") as source, zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as target:
            names = set(source.namelist())
            missing = sorted(set(replacements) - names)
            if missing:
                raise RuntimeError(f"Missing media entries in {path.name}: {missing}")
            for item in source.infolist():
                # Preserve document.xml byte-for-byte so Word Equation Editor
                # namespaces, compatibility prefixes and revision metadata are
                # not rewritten. The existing Figure 7 frame already matches
                # the journal-width portrait layout.
                data = replacements.get(item.filename, source.read(item.filename))
                target.writestr(item, data)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def embed_tracked(path: Path) -> None:
    """Replace both compared versions of every tracked figure with TNR sources."""
    replacements: dict[str, bytes] = {}
    for figure in range(1, 7):
        svg = (FINAL_FIGURES / f"Figure{figure}.svg").read_bytes()
        png = (FINAL_FIGURES / f"Figure{figure}_600dpi.png").read_bytes()
        replacements[f"word/media/image{4 * figure - 2}.svg"] = svg
        replacements[f"word/media/image{4 * figure}.svg"] = svg
        replacements[f"word/media/image{4 * figure - 3}.png"] = png
        replacements[f"word/media/image{4 * figure - 1}.png"] = png
    old_figure7 = Path(r"D:\fzyc\output\paper32_equation_table_format_20260718\main_figures\Figure7_final_requested.svg")
    old_figure7_png = Path(r"D:\fzyc\output\paper32_equation_table_format_20260718\main_figures\Figure7_final_requested_1200dpi.png")
    replacements["word/media/image26.svg"] = old_figure7.read_bytes()
    replacements["word/media/image25.png"] = old_figure7_png.read_bytes()
    replacements["word/media/image28.svg"] = (FINAL_FIGURES / "Figure7.svg").read_bytes()
    replacements["word/media/image27.png"] = (FINAL_FIGURES / "Figure7_600dpi.png").read_bytes()

    fd, temporary_name = tempfile.mkstemp(suffix=".docx", dir=path.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(path, "r") as source, zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as target:
            missing = sorted(set(replacements) - set(source.namelist()))
            if missing:
                raise RuntimeError(f"Missing tracked media entries: {missing}")
            for item in source.infolist():
                target.writestr(item, replacements.get(item.filename, source.read(item.filename)))
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> None:
    stage_assets()
    for path in DOCS:
        embed(path)
        print(path)
    if TRACKED.exists():
        embed_tracked(TRACKED)
        print(TRACKED)


if __name__ == "__main__":
    main()
