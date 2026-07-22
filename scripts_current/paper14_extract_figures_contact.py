from __future__ import annotations

import json
import math
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
WORK = OUT / "paper14_remove_panel_letters"
EXTRACTED = WORK / "extracted"
WORK.mkdir(parents=True, exist_ok=True)
EXTRACTED.mkdir(parents=True, exist_ok=True)
DOCX = OUT / "小论文-14.docx"
CONTACT = WORK / "figure_contact_sheet.png"
MANIFEST = WORK / "embedded_figures_manifest.json"

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def image_targets() -> list[tuple[str, str]]:
    with zipfile.ZipFile(DOCX) as z:
        doc = ET.fromstring(z.read("word/document.xml"))
        rels = ET.fromstring(z.read("word/_rels/document.xml.rels"))
        rid_order = []
        for blip in doc.findall(".//a:blip", NS):
            rid = blip.get(f"{{{NS['r']}}}embed")
            if rid and rid not in rid_order:
                rid_order.append(rid)
        rel_map = {}
        for rel in rels.findall(f"{{{NS['pr']}}}Relationship"):
            if rel.get("Type", "").endswith("/image"):
                rel_map[rel.get("Id")] = "word/" + rel.get("Target")
        return [(rid, rel_map[rid]) for rid in rid_order if rid in rel_map]


def main() -> None:
    records = []
    with zipfile.ZipFile(DOCX) as z:
        for i, (rid, path) in enumerate(image_targets(), start=1):
            data = z.read(path)
            ext = Path(path).suffix or ".png"
            out = EXTRACTED / f"figure_{i:02d}_{rid}{ext}"
            out.write_bytes(data)
            with Image.open(out) as img:
                records.append(
                    {
                        "figure": i,
                        "rid": rid,
                        "media_path": path,
                        "extracted_path": str(out),
                        "width": img.width,
                        "height": img.height,
                        "mode": img.mode,
                    }
                )

    thumbs = []
    for r in records:
        img = Image.open(r["extracted_path"]).convert("RGB")
        img.thumbnail((720, 420), Image.LANCZOS)
        canvas = Image.new("RGB", (760, 470), "white")
        canvas.paste(img, ((760 - img.width) // 2, 36))
        d = ImageDraw.Draw(canvas)
        d.text((12, 10), f"Figure {r['figure']}  {r['width']}x{r['height']}  {r['media_path']}", fill=(20, 20, 20))
        thumbs.append(canvas)

    cols = 3
    rows = math.ceil(len(thumbs) / cols)
    sheet = Image.new("RGB", (cols * 760, rows * 470), "white")
    for i, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((i % cols) * 760, (i // cols) * 470))
    sheet.save(CONTACT, dpi=(180, 180))

    MANIFEST.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"figures": len(records), "contact": str(CONTACT), "manifest": str(MANIFEST)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
