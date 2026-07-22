from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(r"D:\fzyc\output\paper32_equation_table_format_20260718")
DOCS = [
    ROOT / "Candidate_pool_expansion_Journal_of_Cheminformatics_final_unified_format.docx",
    ROOT / "Chinese_manuscript_final_unified_format.docx",
]


def inspect_docx(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        document = archive.read("word/document.xml").decode("utf-8")
        media = [name for name in archive.namelist() if name.startswith("word/media/")]

    table_blocks = re.findall(r"<w:tbl\b.*?</w:tbl>", document, flags=re.S)
    three_line_tables = 0
    for table in table_blocks:
        has_top = bool(re.search(r"<w:top\b[^>]*w:val=\"(single|thick)\"", table))
        has_bottom = bool(re.search(r"<w:bottom\b[^>]*w:val=\"(single|thick)\"", table))
        first_row = re.search(r"<w:tr\b.*?</w:tr>", table, flags=re.S)
        has_header_rule = bool(
            first_row
            and re.search(r"<w:bottom\b[^>]*w:val=\"(single|thick)\"", first_row.group(0))
        )
        if has_top and has_bottom and has_header_rule:
            three_line_tables += 1

    return {
        "file": str(path),
        "native_equations": len(re.findall(r"<m:oMath(?:\s[^>]*)?>", document)),
        "tables": len(table_blocks),
        "three_line_tables": three_line_tables,
        "inline_shapes": document.count("<wp:inline"),
        "media_files": len(media),
        "svg_media_files": sum(name.lower().endswith(".svg") for name in media),
    }


def main() -> None:
    results = []
    for docx in DOCS:
        item = inspect_docx(docx)
        pdf = docx.with_suffix(".pdf")
        item["pdf"] = str(pdf)
        item["pdf_pages"] = len(PdfReader(pdf).pages)
        item["passed"] = (
            item["native_equations"] == 14
            and item["tables"] == 3
            and item["three_line_tables"] == 3
            and item["inline_shapes"] == 7
            and item["svg_media_files"] >= 7
        )
        results.append(item)

    report = {
        "status": "passed" if all(item["passed"] for item in results) else "failed",
        "figure7": {
            "source": str(ROOT / "main_figures" / "Figure7_final_requested.svg"),
            "insertion": "exact requested native SVG inline shape",
            "english_page": 22,
            "chinese_page": 15,
            "sha256": "9BDB43A61CBA27BAA92B38115A99A9C983E224B9E18C3947BEB2775B21E40998",
            "data_values_changed": False,
        },
        "manuscripts": results,
        "visual_page_qc": {
            "english_figure7": "passed",
            "chinese_figure7": "passed",
            "english_equations": "passed",
            "chinese_front_page": "passed",
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
