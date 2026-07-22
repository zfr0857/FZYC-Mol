from __future__ import annotations

import hashlib
import posixpath
import re
import zipfile
from copy import copy
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
DOCX_IN = OUT / "小论文-13_Nature格式终审.docx"
FIG = OUT / "小论文-13_图1重绘" / "fig01_fzyc_mol_redrawn.png"
DOCX_OUT = OUT / "小论文-13_Nature格式终审_图1更新.docx"


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def first_image_relation(doc_xml: bytes, rels_xml: bytes) -> tuple[str, str]:
    doc = ET.fromstring(doc_xml)
    rels = ET.fromstring(rels_xml)
    rid = None
    for blip in doc.findall(".//a:blip", NS):
        rid = blip.get(f"{{{NS['r']}}}embed")
        if rid:
            break
    if not rid:
        raise RuntimeError("No embedded image relationship was found in document.xml")

    for rel in rels.findall(f"{{{NS['pr']}}}Relationship"):
        if rel.get("Id") == rid:
            rel_type = rel.get("Type", "")
            if not rel_type.endswith("/image"):
                raise RuntimeError(f"First embed {rid} is not an image relationship: {rel_type}")
            return rid, rel.get("Target", "")

    raise RuntimeError(f"Relationship target not found for {rid}")


def update_first_drawing_extent(xml: str, rid: str, ratio: float) -> tuple[str, int, int]:
    drawing_re = re.compile(
        r"(<w:drawing\b.*?</w:drawing>)",
        flags=re.DOTALL,
    )
    for match in drawing_re.finditer(xml):
        block = match.group(1)
        if f'r:embed="{rid}"' not in block:
            continue

        wp_extent = re.search(r'<wp:extent cx="(\d+)" cy="(\d+)"/>', block)
        if not wp_extent:
            raise RuntimeError("The first Figure 1 drawing has no wp:extent element")
        cx = int(wp_extent.group(1))
        cy = int(round(cx / ratio))

        block = re.sub(
            r'<wp:extent cx="\d+" cy="\d+"/>',
            f'<wp:extent cx="{cx}" cy="{cy}"/>',
            block,
            count=1,
        )
        block = re.sub(
            r'<a:ext cx="\d+" cy="\d+"/>',
            f'<a:ext cx="{cx}" cy="{cy}"/>',
            block,
            count=1,
        )
        block = re.sub(
            r'name="[^"]*fig01[^"]*"',
            'name="fig01_fzyc_mol_redrawn.png"',
            block,
            count=1,
        )
        return xml[: match.start(1)] + block + xml[match.end(1) :], cx, cy

    raise RuntimeError(f"No drawing block was found for {rid}")


def main() -> None:
    fig_bytes = FIG.read_bytes()
    with Image.open(FIG) as img:
        ratio = img.width / img.height

    with zipfile.ZipFile(DOCX_IN, "r") as zin:
        doc_xml = zin.read("word/document.xml")
        rels_xml = zin.read("word/_rels/document.xml.rels")
        rid, target = first_image_relation(doc_xml, rels_xml)
        media_path = posixpath.normpath(posixpath.join("word", target))
        updated_doc_xml, cx, cy = update_first_drawing_extent(
            doc_xml.decode("utf-8"), rid, ratio
        )

        with zipfile.ZipFile(DOCX_OUT, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                item = copy(info)
                data = zin.read(info.filename)
                if info.filename == "word/document.xml":
                    data = updated_doc_xml.encode("utf-8")
                elif info.filename == media_path:
                    data = fig_bytes
                zout.writestr(item, data)

    with zipfile.ZipFile(DOCX_OUT, "r") as z:
        bad = z.testzip()
        if bad:
            raise RuntimeError(f"Corrupt ZIP member after write: {bad}")
        ET.fromstring(z.read("word/document.xml"))
        replaced = z.read(media_path)

    if sha256(replaced) != sha256(fig_bytes):
        raise RuntimeError("Embedded Figure 1 bytes do not match the redrawn PNG")

    print(f"output={DOCX_OUT}")
    print(f"relationship={rid}")
    print(f"media={media_path}")
    print(f"extent_cx={cx}")
    print(f"extent_cy={cy}")
    print(f"display_ratio={cx / cy:.4f}")
    print(f"image_ratio={ratio:.4f}")


if __name__ == "__main__":
    main()
