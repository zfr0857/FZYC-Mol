from __future__ import annotations

from io import BytesIO
from pathlib import Path
import hashlib
import json
import re
import shutil

import cairosvg
from lxml import etree
from PIL import Image


ROOT = Path(r"D:\fzyc")
PACKAGE = ROOT / "output" / "paper35_submission_ready_20260718"
BACKUP = ROOT / "output" / "paper35_working_backups_20260722_figure4" / "Figure4.svg"
FIG = PACKAGE / "main_figures"


def main() -> None:
    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(str(BACKUP), parser)
    root = tree.getroot()

    attenuation = root.xpath("//*[@id='text_106']")
    if len(attenuation) != 1:
        raise RuntimeError(f"Expected one attenuation annotation, found {len(attenuation)}")
    attenuation[0].getparent().remove(attenuation[0])

    lower_legend = root.xpath("//*[@id='legend_2']")
    if len(lower_legend) != 1:
        raise RuntimeError(f"Expected one lower legend, found {len(lower_legend)}")
    lower_legend[0].set("transform", "translate(76 -202)")

    for node in root.xpath("//*[local-name()='text']"):
        style = node.get("style", "")
        if "font-family:" in style:
            style = re.sub(r"font-family:\s*[^;]+", "font-family: 'Times New Roman'", style)
        else:
            style = f"{style}; font-family: 'Times New Roman'".lstrip("; ")
        node.set("style", style)

    svg_bytes = etree.tostring(tree, encoding="utf-8", xml_declaration=True)
    for name in ["Figure4.svg", "Figure_4_selection_gap_and_winner_optimism.svg"]:
        (FIG / name).write_bytes(svg_bytes)

    pdf_bytes = cairosvg.svg2pdf(bytestring=svg_bytes)
    for name in ["Figure4.pdf", "Figure_4_selection_gap_and_winner_optimism.pdf"]:
        (FIG / name).write_bytes(pdf_bytes)

    png_bytes = cairosvg.svg2png(bytestring=svg_bytes, output_width=4512, output_height=3656)
    with Image.open(BytesIO(png_bytes)) as image:
        image = image.convert("RGB")
        for name in ["Figure4_600dpi.png", "Figure_4_selection_gap_and_winner_optimism.png"]:
            image.save(FIG / name, dpi=(600, 600), optimize=True)

    locked_source = ROOT / "output" / "paper30_final_minor_revision_20260717" / "figure_source_data" / "Figure_4C_integrated_forest_source.csv"
    current_source = PACKAGE / "figure_source_data" / locked_source.name
    shutil.copy2(locked_source, current_source)
    locked_source_hash = hashlib.sha256(locked_source.read_bytes()).hexdigest()
    current_source_hash = hashlib.sha256(current_source.read_bytes()).hexdigest()

    svg_text = svg_bytes.decode("utf-8")
    font_families = {
        value.strip() for value in re.findall(r"font-family:\s*([^;\"]+)", svg_text)
    }
    checks = {
        "status": "pass",
        "source_svg": str(BACKUP),
        "data_values_changed": current_source_hash != locked_source_hash,
        "locked_source_sha256": locked_source_hash,
        "panel_c_d_x_label_y": 398.8785,
        "lower_legend_moved_to_top": "translate(76 -202)" in svg_text,
        "median_attenuation_removed": "Median attenuation" not in svg_text,
        "times_new_roman_only": font_families == {"'Times New Roman'"},
        "png_pixels": [4512, 3656],
        "png_dpi": 600,
    }
    reports = PACKAGE / "reports"
    reports.mkdir(exist_ok=True)
    (reports / "Figure4_QC_report.json").write_text(
        json.dumps(checks, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if checks["data_values_changed"] or not all(
        checks[key]
        for key in [
            "lower_legend_moved_to_top",
            "median_attenuation_removed",
            "times_new_roman_only",
        ]
    ):
        raise RuntimeError("Figure 4 QC failed")


if __name__ == "__main__":
    main()
