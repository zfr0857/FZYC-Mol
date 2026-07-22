from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "output" / "paper14_remove_panel_letters"
MANIFEST = WORK / "embedded_figures_manifest.json"
PREVIEW = WORK / "panel_letter_removal_box_preview.png"


# Pixel coordinates in each embedded image: (x0, y0, x1, y1).
# Boxes are intentionally small and target only subplot letters or Figure 1 panel badges.
BOXES = {
    1: [
        (300, 850, 520, 1070),
        (2160, 850, 2380, 1070),
        (4030, 850, 4250, 1070),
        (5900, 850, 6120, 1070),
        (7770, 850, 7990, 1070),
    ],
    2: [
        (485, 170, 560, 245),
        (1680, 170, 1760, 245),
        (50, 1115, 125, 1190),
        (1680, 1115, 1760, 1190),
    ],
    3: [
        (450, 160, 530, 240),
        (1660, 160, 1740, 240),
        (450, 1110, 530, 1190),
        (1660, 1110, 1740, 1190),
    ],
    4: [
        (200, 210, 280, 290),
        (1795, 210, 1880, 290),
        (200, 1465, 280, 1545),
        (1795, 1465, 1880, 1545),
    ],
    5: [
        (180, 200, 260, 280),
        (1650, 200, 1735, 280),
        (180, 1520, 260, 1600),
        (1650, 1520, 1735, 1600),
    ],
    6: [
        (430, 470, 510, 550),
        (1590, 470, 1675, 550),
        (430, 1340, 510, 1420),
        (1590, 1340, 1675, 1420),
    ],
    7: [
        (270, 170, 350, 250),
        (1460, 170, 1540, 250),
    ],
    8: [
        (360, 190, 440, 270),
        (1800, 190, 1880, 270),
        (3210, 190, 3295, 270),
        (360, 1425, 440, 1510),
        (1800, 1425, 1880, 1510),
        (3210, 1425, 3295, 1510),
    ],
    9: [
        (230, 190, 310, 270),
        (1565, 190, 1645, 270),
        (2680, 190, 2765, 270),
        (230, 1325, 310, 1410),
        (1565, 1325, 1645, 1410),
    ],
}


def make_preview() -> None:
    records = json.loads(MANIFEST.read_text(encoding="utf-8"))
    thumbs = []
    for r in records:
        img = Image.open(r["extracted_path"]).convert("RGB")
        d = ImageDraw.Draw(img)
        for box in BOXES.get(r["figure"], []):
            d.rectangle(box, outline=(220, 0, 0), width=max(8, img.width // 450))
        img.thumbnail((760, 500), Image.LANCZOS)
        canvas = Image.new("RGB", (800, 560), "white")
        canvas.paste(img, ((800 - img.width) // 2, 40))
        d = ImageDraw.Draw(canvas)
        d.text((12, 12), f"Figure {r['figure']} proposed removal boxes", fill=(0, 0, 0))
        thumbs.append(canvas)
    sheet = Image.new("RGB", (2400, 1680), "white")
    for i, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((i % 3) * 800, (i // 3) * 560))
    sheet.save(PREVIEW, dpi=(180, 180))
    print(PREVIEW)


if __name__ == "__main__":
    make_preview()
