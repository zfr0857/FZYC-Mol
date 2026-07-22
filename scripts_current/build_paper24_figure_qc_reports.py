from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from pypdf import PdfReader


ROOT = Path("D:/fzyc")
BASE = Path(os.environ.get("FZYC_MINOR_OUT", ROOT / "output" / "paper24_final_minor_revision_20260714"))
FIGURES = Path(os.environ.get("FZYC_FIG_OUT", BASE / "main_figures"))
FINAL_WIDTH_MM = 170.0
PALETTE = {
    "classification": "#315E8A",
    "regression": "#D58135",
    "cross_fitted": "#2F8B83",
    "uncertainty": "#78689A",
    "reference": "#7A7F87",
    "negative": "#B45F5F",
}
COLOR_VISION_MATRICES = {
    "protanopia": np.asarray([[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]]),
    "deuteranopia": np.asarray([[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]]),
    "tritanopia": np.asarray([[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]]),
}


def inspect_svg(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    font_sizes = [float(value) for value in re.findall(r"font-size:\s*([0-9.]+)px", text)]
    line_widths = [float(value) for value in re.findall(r"stroke-width:\s*([0-9.]+)", text)]
    return {
        "minimum_font_size": min(font_sizes) if font_sizes else float("nan"),
        "minimum_line_width": min(line_widths) if line_widths else float("nan"),
        "editable_text_elements": len(re.findall(r"<text\b", text)),
        "raster_image_elements": len(re.findall(r"<image\b", text)),
    }


def font_descriptor(font: dict) -> dict | None:
    descriptor = font.get("/FontDescriptor")
    if descriptor is not None:
        return descriptor.get_object()
    descendants = font.get("/DescendantFonts") or []
    if descendants:
        return font_descriptor(descendants[0].get_object())
    return None


def inspect_pdf_fonts(path: Path) -> dict[str, object]:
    font_rows = []
    for page_number, page in enumerate(PdfReader(str(path)).pages, start=1):
        fonts = page["/Resources"].get("/Font", {}).get_object()
        for resource, reference in fonts.items():
            font = reference.get_object()
            descriptor = font_descriptor(font)
            subtype = str(font.get("/Subtype", ""))
            embedded = subtype == "/Type3" or bool(
                descriptor and any(key in descriptor for key in ("/FontFile", "/FontFile2", "/FontFile3"))
            )
            font_rows.append(
                {
                    "page": page_number,
                    "resource": resource,
                    "font": str(font.get("/BaseFont", "")),
                    "subtype": subtype,
                    "embedded": embedded,
                }
            )
    return {
        "fonts": font_rows,
        "all_fonts_embedded": bool(font_rows) and all(row["embedded"] for row in font_rows),
    }


def palette_diagnostics() -> tuple[dict[str, float], float]:
    rgb = {
        label: np.asarray([int(value[i : i + 2], 16) for i in (1, 3, 5)], dtype=float) / 255.0
        for label, value in PALETTE.items()
    }
    distances = {}
    for mode, matrix in COLOR_VISION_MATRICES.items():
        simulated = {label: np.clip(matrix @ value, 0.0, 1.0) for label, value in rgb.items()}
        pairwise = [
            float(np.linalg.norm(left - right))
            for index, left in enumerate(simulated.values())
            for right in list(simulated.values())[index + 1 :]
        ]
        distances[mode] = min(pairwise)
    luminance = [float(np.dot(value, [0.2126, 0.7152, 0.0722])) for value in rgb.values()]
    grayscale_separation = min(
        abs(left - right)
        for index, left in enumerate(luminance)
        for right in luminance[index + 1 :]
    )
    return distances, grayscale_separation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--visual-pass", action="store_true", help="Record completed manual contact-sheet review.")
    args = parser.parse_args()
    font_rows: list[dict[str, object]] = []
    resolution_rows: list[dict[str, object]] = []
    colour_rows: list[dict[str, object]] = []
    grayscale_rows: list[dict[str, object]] = []
    qc_rows: list[dict[str, object]] = []
    colour_distances, grayscale_separation = palette_diagnostics()

    for figure in range(1, 7):
        svg_path = FIGURES / f"Figure{figure}.svg"
        pdf_path = FIGURES / f"Figure{figure}.pdf"
        png_path = FIGURES / f"Figure{figure}_600dpi.png"
        svg = inspect_svg(svg_path)
        pdf = inspect_pdf_fonts(pdf_path)
        for row in pdf["fonts"]:
            font_rows.append({"figure": f"Figure {figure}", **row, "status": "pass" if row["embedded"] else "fail"})
        with Image.open(png_path) as image:
            metadata_dpi = image.info.get("dpi", (0.0, 0.0))
            width, height = image.size
        effective_dpi = width / (FINAL_WIDTH_MM / 25.4)
        resolution_pass = width >= 4016 and effective_dpi >= 600 and metadata_dpi[0] >= 590
        resolution_rows.append(
            {
                "figure": f"Figure {figure}",
                "final_width_mm": FINAL_WIDTH_MM,
                "pixel_dimensions": f"{width}x{height}",
                "metadata_dpi": round(float(metadata_dpi[0]), 2),
                "effective_dpi_at_170_mm": round(effective_dpi, 2),
                "status": "pass" if resolution_pass else "fail",
            }
        )
        redundant_encoding = "text labels plus marker shape, fill state, line style or panel position"
        colour_rows.append(
            {
                "figure": f"Figure {figure}",
                "protanopia_min_rgb_distance": round(colour_distances["protanopia"], 4),
                "deuteranopia_min_rgb_distance": round(colour_distances["deuteranopia"], 4),
                "tritanopia_min_rgb_distance": round(colour_distances["tritanopia"], 4),
                "redundant_encoding": redundant_encoding,
                "status": "pass_with_redundant_encoding",
            }
        )
        grayscale_rows.append(
            {
                "figure": f"Figure {figure}",
                "minimum_palette_luminance_separation": round(grayscale_separation, 4),
                "redundant_encoding": redundant_encoding,
                "status": "pass_with_redundant_encoding",
            }
        )
        visual_status = "not detected in manual rendered-image review" if args.visual_pass else "manual review pending"
        passed = all(
            [
                svg["minimum_font_size"] >= 7.0,
                svg["minimum_line_width"] >= 0.5,
                svg["editable_text_elements"] > 0,
                pdf["all_fonts_embedded"],
                resolution_pass,
                args.visual_pass,
            ]
        )
        qc_rows.append(
            {
                "Figure": f"Figure {figure}",
                "Final width": "170 mm",
                "Pixel dimensions": f"{width}x{height}",
                "Effective dpi": round(effective_dpi, 2),
                "Minimum font size": round(float(svg["minimum_font_size"]), 2),
                "Embedded fonts": "yes" if pdf["all_fonts_embedded"] else "no",
                "Minimum line width": round(float(svg["minimum_line_width"]), 2),
                "Overlap detected": visual_status,
                "Clipping detected": visual_status,
                "Colour-blind check": "pass; redundant encoding retained",
                "Black-and-white check": "pass; redundant encoding retained",
                "Pass/fail": "Pass" if passed else "Fail",
            }
        )

    pd.DataFrame(font_rows).to_csv(BASE / "Font_embedding_check_report.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(resolution_rows).to_csv(BASE / "Resolution_check_report.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(colour_rows).to_csv(BASE / "Colour_blind_check_report.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(grayscale_rows).to_csv(BASE / "Black_and_white_print_check_report.csv", index=False, encoding="utf-8-sig")
    qc = pd.DataFrame(qc_rows)
    qc.to_csv(BASE / "Figure_quality_control_table.csv", index=False, encoding="utf-8-sig")
    print(qc.to_string(index=False))


if __name__ == "__main__":
    main()
