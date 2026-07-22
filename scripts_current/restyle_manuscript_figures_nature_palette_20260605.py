from __future__ import annotations

import re
import shutil
from pathlib import Path

import cairosvg
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "reports" / "manuscript_figures_hires"
OUT = ROOT / "reports" / "manuscript_figures_nature_style"

PALETTE = {
    "text": "#272727",
    "text_mid": "#606060",
    "text_soft": "#8F8F8F",
    "grid": "#D8D8D8",
    "border": "#C9CDD4",
    "baseline_dark": "#484878",
    "baseline_mid": "#7884B4",
    "baseline_soft": "#B4C0E4",
    "ours_dark": "#9E5E73",
    "ours_mid": "#C990A4",
    "ours_soft": "#E4CCD8",
    "aqua": "#E0F0F0",
    "lilac": "#E0E0F0",
    "peach": "#F0E0D0",
    "teal": "#42949E",
    "green": "#2E9E44",
    "green_soft": "#DDF3DE",
    "red": "#B64342",
    "red_soft": "#F6CFCB",
    "gold": "#C08A3E",
}

EXPLICIT_MAP = {
    "#000000": PALETTE["text"],
    "#0F172A": PALETTE["text"],
    "#111827": PALETTE["text"],
    "#1F2937": PALETTE["text"],
    "#262626": PALETTE["text"],
    "#2F2F2F": PALETTE["text"],
    "#334155": PALETTE["text"],
    "#344054": PALETTE["text"],
    "#424242": PALETTE["text_mid"],
    "#434343": PALETTE["text_mid"],
    "#475569": PALETTE["text_mid"],
    "#4B5563": PALETTE["text_mid"],
    "#64748B": PALETTE["text_soft"],
    "#667085": PALETTE["text_soft"],
    "#94A3B8": PALETTE["text_soft"],
    "#B6C2CC": PALETTE["border"],
    "#CCCCCC": PALETTE["grid"],
    "#CBD5E1": PALETTE["border"],
    "#D1D5DB": PALETTE["grid"],
    "#D7DEE8": PALETTE["grid"],
    "#E2E8F0": "#EEF1F4",
    "#E5E7EB": "#EEF1F4",
    "#F8FAFC": "#FAFBFC",
    "#2F6FBB": PALETTE["baseline_dark"],
    "#2563EB": PALETTE["baseline_dark"],
    "#1F77B4": PALETTE["baseline_dark"],
    "#4C72B0": PALETTE["baseline_mid"],
    "#3E6CD2": PALETTE["baseline_mid"],
    "#2F6FED": PALETTE["baseline_mid"],
    "#1D4ED8": PALETTE["baseline_dark"],
    "#5B8DEF": PALETTE["baseline_mid"],
    "#3B518B": PALETTE["baseline_dark"],
    "#6C89B2": PALETTE["baseline_mid"],
    "#96A6C0": PALETTE["baseline_soft"],
    "#1B8A6B": PALETTE["teal"],
    "#0F766E": PALETTE["teal"],
    "#0891B2": PALETTE["teal"],
    "#168AAD": PALETTE["teal"],
    "#178462": PALETTE["teal"],
    "#1D849D": PALETTE["teal"],
    "#15803D": PALETTE["green"],
    "#14532D": "#1F7A3D",
    "#166534": "#1F7A3D",
    "#2CA02C": PALETTE["green"],
    "#55A868": PALETTE["green"],
    "#059669": PALETTE["green"],
    "#98C19F": "#A8D3A6",
    "#9BE28B": "#A8D3A6",
    "#BBF7D0": PALETTE["green_soft"],
    "#CAFFBF": PALETTE["green_soft"],
    "#EAF8EC": "#F2FAF3",
    "#C43B5D": PALETTE["ours_dark"],
    "#C44E52": PALETTE["red"],
    "#D62728": PALETTE["red"],
    "#DC2626": PALETTE["red"],
    "#BE123C": PALETTE["red"],
    "#E11D48": PALETTE["red"],
    "#FF4D4F": PALETTE["red"],
    "#FEE2E2": PALETTE["red_soft"],
    "#FECDD3": "#F4DDE5",
    "#F6CFCB": PALETTE["red_soft"],
    "#7C3AED": "#7C6CCF",
    "#8B5CF6": "#7C6CCF",
    "#9467BD": "#7C6CCF",
    "#7B61B8": "#7C6CCF",
    "#8250D7": "#7C6CCF",
    "#E377C2": PALETTE["ours_mid"],
    "#440154": "#5B527D",
    "#FF7F0E": PALETTE["gold"],
    "#D98C00": PALETTE["gold"],
    "#BF7520": PALETTE["gold"],
    "#B45309": PALETTE["gold"],
    "#FFB703": "#D6A84A",
    "#F4A261": "#D6A84A",
    "#8C564B": "#8A6A5A",
    "#FED7AA": PALETTE["peach"],
    "#FEE8D9": "#F2DFD4",
    "#FEEFD0": "#F3E6CC",
    "#FEF6C7": "#F3E6CC",
    "#C7D2FE": "#DDE2F2",
    "#BFDBFE": "#DCEBF1",
    "#BDE0FE": "#DCEBF1",
    "#A7D8FF": "#DCEBF1",
    "#E0F2FE": PALETTE["aqua"],
    "#EDE9FE": PALETTE["lilac"],
    "#DCFCE7": PALETTE["green_soft"],
    "#F1F5F9": "#F4F6F8",
    "#FEF3C7": "#F3E6CC",
}


def normalize_hex(color: str) -> str:
    return color.upper()


def map_color(color: str) -> str:
    color = normalize_hex(color)
    return EXPLICIT_MAP.get(color, color)


def restyle_svg(src: Path, dst: Path) -> None:
    text = src.read_text(encoding="utf-8", errors="ignore")

    def repl(match: re.Match[str]) -> str:
        return map_color(match.group(0))

    text = re.sub(r"#[0-9A-Fa-f]{6}", repl, text)
    text = text.replace("font-family:DejaVu Sans", "font-family:Arial, DejaVu Sans, sans-serif")
    text = text.replace("font-family:DejaVuSans", "font-family:Arial, DejaVu Sans, sans-serif")
    dst.write_text(text, encoding="utf-8")


def target_width(stem: str) -> int:
    if stem in {"fig1_framework_overview_polished", "fig23_fzyc_mol_model_structure"}:
        return 8200
    if stem in {"fig11_motif_fragment_interpretation", "fig4_split_realism_polished"}:
        return 7600
    return 7200


def sharpen_png(path: Path) -> None:
    image = Image.open(path).convert("RGB")
    image = image.filter(ImageFilter.UnsharpMask(radius=0.65, percent=110, threshold=3))
    image.save(path, format="PNG", optimize=True, compress_level=4, dpi=(600, 600))


def export_png(svg: Path, png: Path) -> tuple[int, int]:
    cairosvg.svg2png(
        url=str(svg),
        write_to=str(png),
        output_width=target_width(svg.stem),
        background_color="white",
    )
    sharpen_png(png)
    with Image.open(png) as image:
        return image.size


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for src_svg in sorted(SRC.glob("fig*.svg")):
        dst_svg = OUT / src_svg.name
        dst_png = OUT / f"{src_svg.stem}.png"
        restyle_svg(src_svg, dst_svg)
        rows.append((dst_png.name, export_png(dst_svg, dst_png)))
    readme = [
        "# Nature-style manuscript figures",
        "",
        "Restyled from high-resolution SVG sources using a unified low-saturation Nature/NMI-style palette.",
        "SVG files remain the editable source; PNG files are exported at 600 dpi metadata and 7200-8200 px width.",
        "",
        "Figure contract: validation-governed multi-expert molecular prediction, with restrained palette and directional colors reserved for gains/drops.",
        "",
        "| figure | pixels |",
        "| --- | --- |",
    ]
    for name, (width, height) in rows:
        readme.append(f"| {name} | {width} x {height} |")
    (OUT / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    print(f"restyled {len(rows)} figures to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
