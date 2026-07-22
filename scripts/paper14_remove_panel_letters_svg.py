from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
WORK = OUT / "paper14_remove_panel_letters"
MANIFEST = WORK / "embedded_figures_manifest.json"
SRC_DOCX = OUT / "\u5c0f\u8bba\u6587-14.docx"
DST_DOCX = OUT / "\u5c0f\u8bba\u6587-14_\u53bb\u9664\u56fe\u4e2d\u5b57\u6bcd.docx"

CLEAN_SVG = WORK / "cleaned_svg"
CLEAN_PNG = WORK / "cleaned"
CONTACT = WORK / "panel_letters_removed_contact_sheet.png"
ZOOM = WORK / "panel_letters_removed_zoom_sheet.png"
REPORT = WORK / "panel_letter_removal_report.json"

FIG_SVGS = {
    2: "fig02_candidate_pool_controls.svg",
    3: "fig03_repeated_nested_selection.svg",
    4: "fig04_metric_calibration_meta_risk.svg",
    5: "fig05_multiview_confirmation.svg",
    6: "fig06_moleculenet_decisions.svg",
    7: "fig07_tdc_gate_audit.svg",
    8: "fig08_prediction_reliability_conformal.svg",
    9: "fig09_chemical_boundaries_decision_card.svg",
}

EXPECTED = {
    1: "abcde",
    2: "abcd",
    3: "abcd",
    4: "abcd",
    5: "abcd",
    6: "abcd",
    7: "ab",
    8: "abcdef",
    9: "abcde",
}

TEXT_RE = re.compile(r"<text\b(?P<attrs>[^>]*)>(?P<label>[a-f])</text>", re.S)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def locate_sources() -> dict[int, Path]:
    sources: dict[int, Path] = {}
    for d in OUT.iterdir():
        if not d.is_dir():
            continue
        fig1 = d / "fig01_fzyc_mol_redrawn.svg"
        if fig1.exists():
            sources[1] = fig1
        fig_dir = d / "figures"
        if "-8_" in d.name and fig_dir.exists():
            for fig, name in FIG_SVGS.items():
                p = fig_dir / name
                if p.exists():
                    sources[fig] = p
    missing = sorted(set(EXPECTED) - set(sources))
    if missing:
        raise FileNotFoundError(f"Missing source SVGs for figures: {missing}")
    return sources


def remove_panel_text(svg: str, expected: str) -> tuple[str, list[str]]:
    removed: list[str] = []

    def repl(match: re.Match[str]) -> str:
        attrs = match.group("attrs")
        style = re.search(r'style="([^"]+)"', attrs, re.S)
        if style and "font-weight: 700" in style.group(1):
            removed.append(match.group("label"))
            return ""
        return match.group(0)

    cleaned = TEXT_RE.sub(repl, svg)
    if "".join(removed) != expected:
        raise ValueError(f"Expected {expected}, removed {''.join(removed)}")
    return cleaned, removed


def render_png(svg_text: str, out_png: Path, width: int, height: int) -> None:
    cairosvg.svg2png(
        bytestring=svg_text.encode("utf-8"),
        write_to=str(out_png),
        output_width=width,
        output_height=height,
    )
    img = Image.open(out_png).convert("RGBA")
    if img.size != (width, height):
        raise ValueError(f"{out_png.name}: expected {(width, height)}, got {img.size}")
    white = Image.new("RGBA", img.size, (255, 255, 255, 255))
    white.alpha_composite(img)
    white.save(out_png)


def make_contact(records: list[dict]) -> None:
    thumbs = []
    for r in records:
        img = Image.open(r["cleaned_path"]).convert("RGB")
        img.thumbnail((760, 500), Image.LANCZOS)
        canvas = Image.new("RGB", (800, 560), "white")
        canvas.paste(img, ((800 - img.width) // 2, 42))
        d = ImageDraw.Draw(canvas)
        d.text((12, 12), f"Figure {r['figure']} panel letters removed", fill=(0, 0, 0))
        thumbs.append(canvas)

    sheet = Image.new("RGB", (2400, 1680), "white")
    for i, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((i % 3) * 800, (i // 3) * 560))
    sheet.save(CONTACT, dpi=(180, 180))


def make_zoom_sheet(records: list[dict]) -> None:
    crops = []
    anchors = [
        (0.00, 0.00), (0.47, 0.00), (0.72, 0.00),
        (0.00, 0.42), (0.47, 0.42), (0.72, 0.42),
        (0.00, 0.66), (0.47, 0.66), (0.72, 0.66),
    ]
    for r in records:
        img = Image.open(r["cleaned_path"]).convert("RGB")
        w, h = img.size
        cw, ch = int(w * 0.22), int(h * 0.18)
        for j, (ax, ay) in enumerate(anchors, start=1):
            x = min(int(w * ax), w - cw)
            y = min(int(h * ay), h - ch)
            crop = img.crop((x, y, x + cw, y + ch))
            crop.thumbnail((320, 220), Image.LANCZOS)
            canvas = Image.new("RGB", (340, 260), "white")
            canvas.paste(crop, ((340 - crop.width) // 2, 34))
            d = ImageDraw.Draw(canvas)
            d.text((8, 8), f"F{r['figure']} zone{j} x{x} y{y}", fill=(0, 0, 0))
            crops.append(canvas)

    cols = 6
    rows = (len(crops) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 340, rows * 260), "white")
    for i, crop in enumerate(crops):
        sheet.paste(crop, ((i % cols) * 340, (i // cols) * 260))
    sheet.save(ZOOM, dpi=(180, 180))


def replace_docx_media(records: list[dict]) -> list[str]:
    repl = {r["media_path"]: Path(r["cleaned_path"]).read_bytes() for r in records}
    tmp = DST_DOCX.with_suffix(".tmp.docx")
    changed: list[str] = []
    with zipfile.ZipFile(SRC_DOCX, "r") as zin, zipfile.ZipFile(tmp, "w") as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename in repl:
                data = repl[info.filename]
                changed.append(info.filename)
            zout.writestr(info, data)
    with zipfile.ZipFile(tmp, "r") as z:
        bad = z.testzip()
        if bad:
            raise zipfile.BadZipFile(f"Corrupt entry after replacement: {bad}")
    tmp.replace(DST_DOCX)
    return changed


def main() -> None:
    CLEAN_SVG.mkdir(parents=True, exist_ok=True)
    CLEAN_PNG.mkdir(parents=True, exist_ok=True)
    sources = locate_sources()
    records = json.loads(MANIFEST.read_text(encoding="utf-8"))

    rendered: list[dict] = []
    for r in records:
        fig = int(r["figure"])
        source = sources[fig]
        svg = source.read_text(encoding="utf-8", errors="ignore")
        cleaned, labels = remove_panel_text(svg, EXPECTED[fig])
        svg_out = CLEAN_SVG / f"figure_{fig:02d}_no_panel_letters.svg"
        png_out = CLEAN_PNG / f"figure_{fig:02d}_{r['rid']}_no_panel_letters.png"
        svg_out.write_text(cleaned, encoding="utf-8")
        render_png(cleaned, png_out, int(r["width"]), int(r["height"]))
        png_bytes = png_out.read_bytes()
        rendered.append({
            **r,
            "source_svg": str(source),
            "cleaned_svg": str(svg_out),
            "cleaned_path": str(png_out),
            "removed_labels": labels,
            "cleaned_sha256": sha256(png_bytes),
        })

    make_contact(rendered)
    make_zoom_sheet(rendered)
    changed = replace_docx_media(rendered)

    with zipfile.ZipFile(SRC_DOCX, "r") as src, zipfile.ZipFile(DST_DOCX, "r") as dst:
        src_hash = {i.filename: sha256(src.read(i.filename)) for i in src.infolist()}
        dst_hash = {i.filename: sha256(dst.read(i.filename)) for i in dst.infolist()}
    diff = sorted(k for k in dst_hash if src_hash.get(k) != dst_hash[k])
    if diff != sorted(changed):
        raise ValueError(f"Unexpected changed entries: {diff}; expected {changed}")

    report = {
        "source_docx": str(SRC_DOCX),
        "output_docx": str(DST_DOCX),
        "changed_entries": changed,
        "changed_entry_count": len(changed),
        "contact_sheet": str(CONTACT),
        "zoom_sheet": str(ZOOM),
        "figures": rendered,
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "output_docx": str(DST_DOCX),
        "changed_entry_count": len(changed),
        "contact_sheet": str(CONTACT),
        "zoom_sheet": str(ZOOM),
        "report": str(REPORT),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
