from __future__ import annotations

import shutil
from pathlib import Path

import cairosvg
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "reports" / "manuscript_figures_polished"
OUT = ROOT / "reports" / "manuscript_figures_hires"

PRIORITY_STEMS = [
    "fig1_framework_overview_polished",
    "fig23_fzyc_mol_model_structure",
    "fig2_moleculenet_rank_heatmap_polished",
    "fig3_moleculenet_performance_dots",
    "fig17_moleculenet_targeted_rebuild_decision",
    "fig18_nature_multimethod_fusion_decision",
    "fig5_tdc_official_split_delta",
    "fig19_tdc_nature_multimethod_fusion_decision",
    "fig15_external_appendix_retained_delta",
    "fig4_split_realism_polished",
    "fig6_reliability_summary_polished",
    "fig20_3d_roughness_regression_gate",
    "fig22_formal_fixed_selector_integration",
    "fig24_strong_baseline_selector_governance",
    "fig16_external_candidate_rank_cd",
    "fig11_motif_fragment_interpretation",
]


def figure_sort_key(path: Path) -> tuple[int, str]:
    stem = path.stem
    prefix = "fig"
    number = ""
    for char in stem[len(prefix) :]:
        if char.isdigit():
            number += char
        else:
            break
    return (int(number) if number else 10_000, stem)


def all_figure_stems() -> list[str]:
    ordered: dict[str, None] = {}
    for stem in PRIORITY_STEMS:
        ordered[stem] = None
    for svg in sorted(SRC.glob("fig*.svg"), key=figure_sort_key):
        ordered[svg.stem] = None
    return list(ordered)


def target_width(stem: str) -> int:
    if stem in {"fig1_framework_overview_polished", "fig23_fzyc_mol_model_structure"}:
        return 8200
    if stem in {"fig11_motif_fragment_interpretation", "fig4_split_realism_polished"}:
        return 7600
    return 7200


def sharpen_png(path: Path) -> None:
    image = Image.open(path).convert("RGB")
    image = image.filter(ImageFilter.UnsharpMask(radius=0.7, percent=115, threshold=3))
    image.save(path, format="PNG", optimize=True, compress_level=4, dpi=(600, 600))


def export_one(stem: str) -> tuple[str, tuple[int, int]]:
    svg = SRC / f"{stem}.svg"
    png = SRC / f"{stem}.png"
    out_svg = OUT / f"{stem}.svg"
    out_png = OUT / f"{stem}.png"
    if svg.exists():
        shutil.copy2(svg, out_svg)
        cairosvg.svg2png(
            url=str(svg),
            write_to=str(out_png),
            output_width=target_width(stem),
            background_color="white",
        )
        sharpen_png(out_png)
    elif png.exists():
        image = Image.open(png).convert("RGB")
        width = target_width(stem)
        height = round(image.height * width / image.width)
        image = image.resize((width, height), Image.Resampling.LANCZOS)
        image = image.filter(ImageFilter.UnsharpMask(radius=0.8, percent=110, threshold=3))
        image.save(out_png, format="PNG", optimize=True, compress_level=4, dpi=(600, 600))
    else:
        raise FileNotFoundError(stem)
    with Image.open(out_png) as image:
        size = image.size
    return stem, size


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for stem in all_figure_stems():
        rows.append(export_one(stem))
    readme = [
        "# High-resolution manuscript figures",
        "",
        "Generated from vector SVG sources where available. PNG files are exported at 600 dpi metadata and 7200-8200 px width for clean DOCX rendering.",
        "",
        "| figure | pixels |",
        "| --- | --- |",
    ]
    for stem, (width, height) in rows:
        readme.append(f"| {stem}.png | {width} x {height} |")
    (OUT / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    print(f"exported {len(rows)} figures to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
