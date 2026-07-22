from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "output" / "paper14_remove_panel_letters"
MANIFEST = WORK / "embedded_figures_manifest.json"
OUT = WORK / "panel_label_crop_sheet.png"


def main() -> None:
    records = json.loads(MANIFEST.read_text(encoding="utf-8"))
    crops = []
    for r in records:
        img = Image.open(r["extracted_path"]).convert("RGB")
        w, h = img.size
        # A grid of likely panel-label zones: top-left, top-middle, top-right,
        # middle-left, middle-middle, middle-right, lower-left, lower-middle, lower-right.
        anchors = [
            (0.00, 0.00), (0.47, 0.00), (0.72, 0.00),
            (0.00, 0.42), (0.47, 0.42), (0.72, 0.42),
            (0.00, 0.66), (0.47, 0.66), (0.72, 0.66),
        ]
        cw, ch = int(w * 0.22), int(h * 0.18)
        for j, (ax, ay) in enumerate(anchors, start=1):
            x, y = int(w * ax), int(h * ay)
            x = min(x, w - cw)
            y = min(y, h - ch)
            crop = img.crop((x, y, x + cw, y + ch))
            crop.thumbnail((320, 220), Image.LANCZOS)
            canvas = Image.new("RGB", (340, 260), "white")
            canvas.paste(crop, ((340 - crop.width) // 2, 34))
            d = ImageDraw.Draw(canvas)
            d.text((8, 8), f"F{r['figure']} zone{j} x{x} y{y}", fill=(0, 0, 0))
            crops.append(canvas)

    cols = 6
    rows = math.ceil(len(crops) / cols)
    sheet = Image.new("RGB", (cols * 340, rows * 260), "white")
    for i, crop in enumerate(crops):
        sheet.paste(crop, ((i % cols) * 340, (i // cols) * 260))
    sheet.save(OUT, dpi=(180, 180))
    print(OUT)


if __name__ == "__main__":
    main()
