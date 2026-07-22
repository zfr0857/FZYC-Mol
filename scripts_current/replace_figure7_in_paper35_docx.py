from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import hashlib
import os
import tempfile

from lxml import etree


PACKAGE = Path(r"D:\fzyc\output\paper35_submission_ready_20260718")
SVG = PACKAGE / "main_figures" / "Figure7.svg"
PNG = PACKAGE / "main_figures" / "Figure7_600dpi.png"


def replace(path: Path) -> None:
    ns = {"r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    with ZipFile(path) as archive:
        document = etree.fromstring(archive.read("word/document.xml"))
        rels = etree.fromstring(archive.read("word/_rels/document.xml.rels"))
        blips = document.xpath(
            "//*[local-name()='docPr' and @name='图形 1']"
            "/ancestor::*[local-name()='drawing'][1]//*[@r:embed]",
            namespaces=ns,
        )
        rids = {node.get(f"{{{ns['r']}}}embed") for node in blips}
        targets = {
            f"word/{node.get('Target')}": Path(node.get("Target")).suffix.lower()
            for node in rels
            if node.get("Id") in rids and node.get("Target")
        }
    if not targets:
        raise RuntimeError(f"Could not locate registered Figure 7 in {path.name}")
    replacements = {
        member: SVG.read_bytes() if suffix == ".svg" else PNG.read_bytes()
        for member, suffix in targets.items()
        if suffix in {".svg", ".png"}
    }
    if len(replacements) != len(targets):
        raise RuntimeError(f"Unsupported Figure 7 media type in {path.name}")

    fd, temp_name = tempfile.mkstemp(suffix=".docx", dir=path.parent)
    os.close(fd)
    temp = Path(temp_name)
    try:
        with ZipFile(path) as source, ZipFile(temp,"w",ZIP_DEFLATED) as output:
            replaced = set()
            for item in source.infolist():
                data = source.read(item.filename)
                if item.filename in replacements:
                    data = replacements[item.filename]
                    replaced.add(item.filename)
                output.writestr(item,data)
        if replaced != set(replacements):
            raise RuntimeError(f"Incomplete Figure 7 replacement in {path.name}")
        os.replace(temp,path)
    finally:
        temp.unlink(missing_ok=True)

    with ZipFile(path) as archive:
        for member, expected in replacements.items():
            if hashlib.sha256(archive.read(member)).digest() != hashlib.sha256(expected).digest():
                raise RuntimeError(f"Embedded Figure 7 hash mismatch in {path.name}")


def main() -> None:
    documents = [
        PACKAGE / "Candidate_pool_expansion_Journal_of_Cheminformatics_FINAL_CLEAN.docx",
        PACKAGE / "Candidate_pool_expansion_Journal_of_Cheminformatics_FINAL_TRACK_CHANGES.docx",
        next(path for path in PACKAGE.glob("*.docx") if not path.name.startswith(("Candidate","~$"))),
    ]
    for path in documents:
        replace(path)


if __name__ == "__main__":
    main()
