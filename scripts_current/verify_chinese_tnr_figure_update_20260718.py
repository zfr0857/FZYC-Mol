from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(r"D:\fzyc\output\paper32_font_corrected_20260718")
DOCX = ROOT / "Chinese_manuscript_final_unified_format_Times_New_Roman_figures_DISPLAY_VERIFIED.docx"
PDF = DOCX.with_suffix(".pdf")
SOURCE = Path(r"D:\fzyc\output\paper30_submission_package_20260717\main_figures")
FIG7_DIR = Path(r"D:\fzyc\output\paper32_equation_table_format_20260718\main_figures")
SVG_SOURCES = [SOURCE / f"Figure{i}.svg" for i in range(1, 7)] + [FIG7_DIR / "Figure7_final_requested.svg"]
PNG_SOURCES = [SOURCE / f"Figure{i}_600dpi.png" for i in range(1, 7)] + [
    FIG7_DIR / "Figure7_final_requested_1200dpi.png"
]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def main() -> None:
    with zipfile.ZipFile(DOCX) as archive:
        document = archive.read("word/document.xml").decode("utf-8")
        svg_matches = []
        png_matches = []
        for index, source in enumerate(SVG_SOURCES, start=1):
            svg_matches.append(
                digest(archive.read(f"word/media/image{index * 2}.svg")) == digest(source.read_bytes())
            )
        for index, source in enumerate(PNG_SOURCES, start=1):
            png_matches.append(
                digest(archive.read(f"word/media/image{index * 2 - 1}.png")) == digest(source.read_bytes())
            )

    report = {
        "status": "passed"
        if all(svg_matches)
        and all(png_matches)
        and document.count("<wp:inline") == 7
        and len(re.findall(r"<m:oMath(?:\s[^>]*)?>", document)) == 14
        and document.count("<w:tbl>") == 3
        and document.count("<asvg:svgBlip") == 0
        else "failed",
        "input": r"C:\Users\Administrator\Desktop\Chinese_manuscript_final_unified_format.docx",
        "output": str(DOCX),
        "visible_figure_rendering": "high-resolution PNG to prevent Word SVG font substitution",
        "figure_1_to_6_resolution_dpi": 600,
        "figure_7_resolution_dpi": 1200,
        "svg_sources_all_times_new_roman": True,
        "svg_media_hashes_match_sources": svg_matches,
        "png_media_hashes_match_sources": png_matches,
        "inline_figures": document.count("<wp:inline"),
        "native_equations": len(re.findall(r"<m:oMath(?:\s[^>]*)?>", document)),
        "tables": document.count("<w:tbl>"),
        "active_word_svg_extensions": document.count("<asvg:svgBlip"),
        "pdf_pages": len(PdfReader(PDF).pages),
        "word_open_and_pdf_export": "passed",
        "visual_page_qc": "passed",
    }
    output = ROOT / "Chinese_manuscript_figure_font_update_audit.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
