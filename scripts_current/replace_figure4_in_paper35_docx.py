from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import hashlib
import os
import shutil
import tempfile

from lxml import etree


PACKAGE = Path(r"D:\fzyc\output\paper35_submission_ready_20260718")
FIGURE = PACKAGE / "main_figures" / "Figure4.svg"
FIGURE_PNG = PACKAGE / "main_figures" / "Figure4_600dpi.png"


def replace_media(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source != destination:
        shutil.copy2(source, destination)

    fd, temp_name = tempfile.mkstemp(suffix=".docx", dir=destination.parent)
    os.close(fd)
    temp = Path(temp_name)
    unique_png = source != destination
    try:
        with ZipFile(destination, "r") as zin:
            document_xml = etree.fromstring(zin.read("word/document.xml"))
            rels_xml = etree.fromstring(zin.read("word/_rels/document.xml.rels"))
            ns = {"r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
            figure_blips = document_xml.xpath(
                "//*[local-name()='docPr' and @name='Picture 4']"
                "/ancestor::*[local-name()='drawing'][1]//*[@r:embed]",
                namespaces=ns,
            )
            figure_rids = {node.get(f"{{{ns['r']}}}embed") for node in figure_blips}
            relationships = {
                node.get("Id"): node
                for node in rels_xml
                if node.get("Id") in figure_rids
            }
            if not relationships:
                raise RuntimeError(f"Could not locate the registered Figure 4 in {destination.name}")

            target_members: dict[str, tuple[str, bytes]] = {}
            for rid, relationship in relationships.items():
                target = relationship.get("Target")
                if not target:
                    raise RuntimeError(f"Missing Figure 4 target for {rid}")
                member = f"word/{target}"
                suffix = Path(target).suffix.lower()
                if suffix == ".svg":
                    replacement = FIGURE.read_bytes()
                    output_member = member
                elif suffix == ".png":
                    replacement = FIGURE_PNG.read_bytes()
                    if unique_png:
                        relationship.set("Target", "media/Figure4_updated.png")
                        output_member = "word/media/Figure4_updated.png"
                    else:
                        output_member = member
                else:
                    raise RuntimeError(f"Unsupported Figure 4 media type: {target}")
                target_members[member] = (output_member, replacement)

            rels_bytes = etree.tostring(rels_xml, encoding="utf-8", xml_declaration=True)

        with ZipFile(destination, "r") as zin, ZipFile(temp, "w", ZIP_DEFLATED) as zout:
            replaced_svg = 0
            replaced_png = 0
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "word/_rels/document.xml.rels":
                    data = rels_bytes
                if item.filename in target_members:
                    output_member, data = target_members[item.filename]
                    item.filename = output_member
                    replaced_svg += int(output_member.endswith(".svg"))
                    replaced_png += int(output_member.endswith(".png"))
                zout.writestr(item, data)
            expected_svg = sum(1 for output, _ in target_members.values() if output.endswith(".svg"))
            expected_png_count = sum(1 for output, _ in target_members.values() if output.endswith(".png"))
            if replaced_svg != expected_svg or replaced_png != expected_png_count:
                raise RuntimeError(
                    f"Expected the registered Figure 4 media replacement in {destination.name}"
                )
        os.replace(temp, destination)
    finally:
        temp.unlink(missing_ok=True)

    with ZipFile(destination) as z:
        for _, (member, replacement) in target_members.items():
            actual = hashlib.sha256(z.read(member)).hexdigest()
            expected = hashlib.sha256(replacement).hexdigest()
            if actual != expected:
                raise RuntimeError(f"Embedded Figure 4 hash mismatch in {destination.name}")


def main() -> None:
    english = [
        PACKAGE / "Candidate_pool_expansion_Journal_of_Cheminformatics_FINAL_CLEAN.docx",
        PACKAGE / "Candidate_pool_expansion_Journal_of_Cheminformatics_FINAL_TRACK_CHANGES.docx",
    ]
    for path in english:
        replace_media(path, path)

    chinese = next(
        path
        for path in PACKAGE.glob("*.docx")
        if not path.name.startswith(("~$", "Candidate_")) and "Figure4" not in path.name
    )
    updated_chinese = chinese.with_name(f"{chinese.stem}_Figure4更新版.docx")
    replace_media(chinese, chinese)


if __name__ == "__main__":
    main()
