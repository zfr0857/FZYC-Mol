from __future__ import annotations

import csv
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
WORK = OUT / "paper14_work"
WORK.mkdir(parents=True, exist_ok=True)

DOCX = OUT / "小论文-13_Nature格式终审_图1题名更新.docx"

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}


def q(name: str) -> str:
    return f"{{{W}}}{name}"


def para_text(p: ET.Element) -> str:
    parts = []
    for node in p.iter():
        if node.tag in {q("t"), q("delText")}:
            parts.append(node.text or "")
        elif node.tag == q("tab"):
            parts.append("\t")
        elif node.tag == q("br"):
            parts.append("\n")
    return "".join(parts).strip()


def style_id(p: ET.Element) -> str:
    style = p.find("./w:pPr/w:pStyle", NS)
    return style.get(q("val"), "") if style is not None else ""


def table_text(tbl: ET.Element) -> str:
    rows = []
    for tr in tbl.findall("./w:tr", NS):
        cells = []
        for tc in tr.findall("./w:tc", NS):
            txt = " ".join(
                t for p in tc.findall(".//w:p", NS) if (t := para_text(p))
            )
            cells.append(txt)
        rows.append(" | ".join(cells))
    return "\n".join(rows)


def main() -> None:
    with zipfile.ZipFile(DOCX) as z:
        doc = ET.fromstring(z.read("word/document.xml"))

    body = doc.find("w:body", NS)
    if body is None:
        raise RuntimeError("No document body found")

    records = []
    table_records = []
    in_refs = False
    section = ""
    para_i = 0
    table_i = 0

    for child in body:
        if child.tag == q("p"):
            text = para_text(child)
            if not text:
                continue
            para_i += 1
            sid = style_id(child)
            is_heading = sid in {"1", "2", "3", "Heading1", "Heading2", "Heading3"}
            if is_heading:
                section = text
            if re.fullmatch(r"\s*(参考文献|References)\s*", text, flags=re.I):
                in_refs = True
                section = text
            records.append(
                {
                    "id": f"P{para_i:03d}",
                    "kind": "paragraph",
                    "style": sid,
                    "section": section,
                    "in_references": str(in_refs),
                    "text": text,
                }
            )
        elif child.tag == q("tbl"):
            table_i += 1
            table_records.append(
                {
                    "id": f"T{table_i:02d}",
                    "kind": "table",
                    "section": section,
                    "text": table_text(child),
                }
            )

    refs = [r for r in records if r["in_references"] == "True" and r["text"] != "参考文献"]

    with (WORK / "manuscript_paragraphs.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "kind", "style", "section", "in_references", "text"])
        writer.writeheader()
        writer.writerows(records)

    with (WORK / "manuscript_tables.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "kind", "section", "text"])
        writer.writeheader()
        writer.writerows(table_records)

    with (WORK / "references_extracted.txt").open("w", encoding="utf-8") as f:
        for r in refs:
            f.write(f"{r['id']}\t{r['text']}\n")

    with (WORK / "manuscript_outline.md").open("w", encoding="utf-8") as f:
        for r in records:
            marker = "REF" if r["in_references"] == "True" else r["style"] or "body"
            f.write(f"### {r['id']} [{marker}] {r['section']}\n\n{r['text']}\n\n")

    print(
        json.dumps(
            {
                "docx": str(DOCX),
                "paragraphs": len(records),
                "tables": len(table_records),
                "references": len(refs),
                "work": str(WORK),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
