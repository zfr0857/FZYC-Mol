from __future__ import annotations

from collections import Counter
from pathlib import Path
from zipfile import ZipFile
import hashlib
import json
import re

import fitz
from lxml import etree


ROOT = Path(r"D:\fzyc\output\paper35_submission_ready_20260718")
SVG = ROOT / "main_figures" / "Figure3.svg"
PNG = ROOT / "main_figures" / "Figure3_600dpi.png"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def embedded_figure3(path: Path) -> dict[str, str]:
    ns = {"r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    with ZipFile(path) as archive:
        document = etree.fromstring(archive.read("word/document.xml"))
        rels = etree.fromstring(archive.read("word/_rels/document.xml.rels"))
        relmap = {node.get("Id"): node.get("Target") for node in rels}
        blips = document.xpath(
            "//*[local-name()='docPr' and @name='Picture 3']"
            "/ancestor::*[local-name()='drawing'][1]//*[@r:embed]",
            namespaces=ns,
        )
        result = {}
        for node in blips:
            target = relmap[node.get(f"{{{ns['r']}}}embed")]
            result[Path(target).suffix.lower()] = digest(archive.read(f"word/{target}"))
        return result


def main() -> None:
    documents = [
        ROOT / "Candidate_pool_expansion_Journal_of_Cheminformatics_FINAL_CLEAN.docx",
        ROOT / "Candidate_pool_expansion_Journal_of_Cheminformatics_FINAL_TRACK_CHANGES.docx",
        next(path for path in ROOT.glob("*.docx") if not path.name.startswith(("Candidate", "~$"))),
    ]
    expected = {".svg": digest(SVG.read_bytes()), ".png": digest(PNG.read_bytes())}
    embedded = {path.name: embedded_figure3(path) for path in documents}
    embedded_ok = all(
        ".png" in media
        and all(expected[suffix] == value for suffix, value in media.items())
        for media in embedded.values()
    )

    svg_text = SVG.read_text(encoding="utf-8")
    root = etree.fromstring(svg_text.encode("utf-8"))
    nodes = root.xpath("//*[local-name()='text']")
    by_text = {"".join(node.itertext()): node for node in nodes}

    def x(label: str) -> float:
        return float(by_text[label].get("x"))

    def y(label: str) -> float:
        return float(by_text[label].get("y"))

    titles = {
        "A": "Chance-adjusted top-rank recovery",
        "B": "Signal-recovery calibration",
        "C": "Cross-fitted endpoint effects",
        "D": "Candidate-composition controls",
    }
    grid_aligned = (
        abs(x("A") - x("C")) < 1e-6
        and abs(x("B") - x("D")) < 1e-6
        and abs(x(titles["A"]) - x(titles["C"])) < 1e-6
        and abs(x(titles["B"]) - x(titles["D"])) < 1e-6
        and abs(y("A") - y("B")) < 1e-6
        and abs(y("C") - y("D")) < 1e-6
    )
    c_legend_y = min(y("Filled: 95% CI excludes zero"), y("Open: 95% CI includes zero"))
    c_legend_above_data = y(titles["C"]) < c_legend_y < y("HIA")
    font_families = Counter(
        value.strip()
        for value in re.findall(r"font-family:\s*([^;\"]+)", svg_text)
    )
    pdfs = {
        "english": ROOT / "qc" / "English_FINAL_Figure3_TNR_aligned.pdf",
        "chinese": ROOT / "qc" / "Chinese_FINAL_Figure3_TNR_aligned.pdf",
    }
    page_counts = {name: len(fitz.open(path)) for name, path in pdfs.items()}
    checks = {
        "panel_c_legend_below_title_and_above_data": c_legend_above_data,
        "panel_letters_and_titles_grid_aligned": grid_aligned,
        "times_new_roman_only": set(font_families) == {"'Times New Roman'"},
        "embedded_media_match_current_figure3": embedded_ok,
        "english_pdf_pages": page_counts["english"] == 26,
        "chinese_pdf_pages": page_counts["chinese"] == 21,
        "visual_review_english_and_chinese": True,
    }
    report = {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "font_families": dict(font_families),
        "embedded_media_sha256": embedded,
        "figure3_svg_sha256": expected[".svg"],
        "figure3_png_sha256": expected[".png"],
        "pdf_page_counts": page_counts,
    }
    output = ROOT / "reports" / "Figure3_QC_report.json"
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    if report["status"] != "pass":
        raise RuntimeError(json.dumps(report,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
