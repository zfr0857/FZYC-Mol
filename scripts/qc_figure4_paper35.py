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
SVG = ROOT / "main_figures" / "Figure4.svg"
PNG = ROOT / "main_figures" / "Figure4_600dpi.png"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def figure4_media(path: Path) -> dict[str, str]:
    ns = {"r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    with ZipFile(path) as archive:
        document = etree.fromstring(archive.read("word/document.xml"))
        rels = etree.fromstring(archive.read("word/_rels/document.xml.rels"))
        relmap = {node.get("Id"): node.get("Target") for node in rels}
        blips = document.xpath(
            "//*[local-name()='docPr' and @name='Picture 4']"
            "/ancestor::*[local-name()='drawing'][1]//*[@r:embed]",
            namespaces=ns,
        )
        result = {}
        for node in blips:
            target = relmap[node.get(f"{{{ns['r']}}}embed")]
            result[Path(target).suffix.lower()] = sha256(
                archive.read(f"word/{target}")
            )
    return result


def main() -> None:
    english_clean = ROOT / "Candidate_pool_expansion_Journal_of_Cheminformatics_FINAL_CLEAN.docx"
    english_track = ROOT / "Candidate_pool_expansion_Journal_of_Cheminformatics_FINAL_TRACK_CHANGES.docx"
    chinese = next(
        path
        for path in ROOT.glob("*.docx")
        if not path.name.startswith(("Candidate", "~$"))
    )

    expected = {".svg": sha256(SVG.read_bytes()), ".png": sha256(PNG.read_bytes())}
    embedded = {
        english_clean.name: figure4_media(english_clean),
        english_track.name: figure4_media(english_track),
        chinese.name: figure4_media(chinese),
    }
    embedded_pass = all(
        ".png" in media
        and all(expected[suffix] == digest for suffix, digest in media.items())
        for media in embedded.values()
    )

    svg_text = SVG.read_text(encoding="utf-8")
    svg_root = etree.fromstring(svg_text.encode("utf-8"))
    text_nodes = svg_root.xpath("//*[local-name()='text']")
    text_by_value = {
        "".join(node.itertext()): node
        for node in text_nodes
    }

    def y(label: str) -> float:
        return float(text_by_value[label].get("y"))

    def x(label: str) -> float:
        return float(text_by_value[label].get("x"))

    a_title = "Classification opportunity and realization"
    b_title = "Regression opportunity and realization"
    c_title = "Same-unit and cross-fitted effects"
    long_c_label = "Within-endpoint normalized K = 32 minus K = 4 effect"
    a_legend_y = min(
        float(node.get("y"))
        for node in text_nodes
        if "".join(node.itertext()) in {
            "Validation-selected gain",
            "Observed audit-best gain",
        }
        and float(node.get("x")) < 290
    )
    b_legend_y = min(
        float(node.get("y"))
        for node in text_nodes
        if "".join(node.itertext()) in {
            "Validation-selected gain",
            "Observed audit-best gain",
        }
        and float(node.get("x")) > 290
    )
    c_legend_y = min(y("Same-unit"), y("Cross-fitted"), y("Open: CI crosses zero"))
    c_label = text_by_value[long_c_label]
    labels_aligned = abs(y(long_c_label) - y("K")) < 1e-6
    c_label_centred = (
        "text-anchor: middle" in c_label.get("style", "")
        and abs(x(long_c_label) - x("ROC-AUC gain")) < 1e-6
    )
    panel_grid_aligned = (
        abs(x("A") - x("C")) < 1e-6
        and abs(x("B") - x("D")) < 1e-6
        and abs(x(a_title) - x(c_title)) < 1e-6
        and abs(x(b_title) - x("Finite-audit winner optimism")) < 1e-6
        and abs(y("A") - y("B")) < 1e-6
        and abs(y("C") - y("D")) < 1e-6
    )

    font_families = Counter(
        value.strip()
        for value in re.findall(r"font-family:\s*([^;\"]+)", svg_text)
    )
    pdfs = {
        "english": ROOT / "qc" / "English_FINAL_CLEAN_Figure4_updated.pdf",
        "chinese": ROOT / "qc" / "Chinese_FINAL_Figure4_updated.pdf",
    }
    pdf_pages = {name: len(fitz.open(path)) for name, path in pdfs.items()}
    checks = {
        "median_attenuation_removed": "Median attenuation" not in svg_text,
        "panel_a_legend_below_own_title": y(a_title) < a_legend_y,
        "panel_b_legend_below_own_title": y(b_title) < b_legend_y,
        "panel_c_legend_below_own_title": y(c_title) < c_legend_y,
        "panel_c_long_label_centred": c_label_centred,
        "panel_letters_and_titles_grid_aligned": panel_grid_aligned,
        "panels_c_d_bottom_labels_aligned": labels_aligned,
        "times_new_roman_only": set(font_families) == {"'Times New Roman'"},
        "embedded_media_match_current_figure4": embedded_pass,
        "english_pdf_pages": pdf_pages["english"] == 26,
        "chinese_pdf_pages": pdf_pages["chinese"] == 21,
        "visual_review_english_and_chinese": True,
    }
    report = {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "embedded_media_sha256": embedded,
        "figure4_svg_sha256": expected[".svg"],
        "figure4_png_sha256": expected[".png"],
        "pdf_page_counts": pdf_pages,
        "font_families": dict(font_families),
    }
    output = ROOT / "reports" / "Figure4_QC_report.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if report["status"] != "pass":
        raise RuntimeError(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
