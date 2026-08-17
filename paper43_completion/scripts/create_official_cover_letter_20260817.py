from __future__ import annotations

from html import escape
from pathlib import Path

from scripts.document import Document


UNPACKED = Path(r"D:\fzyc\work\cover_letter_official_20260817_unpacked")


def run(text: str, *, bold: bool = False, italic: bool = False, size: int = 22) -> str:
    props = [
        '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="Times New Roman"/>',
        f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>',
        '<w:lang w:val="en-US" w:eastAsia="en-US"/>',
    ]
    if bold:
        props.append("<w:b/><w:bCs/>")
    if italic:
        props.append("<w:i/><w:iCs/>")
    return f'<w:r><w:rPr>{"".join(props)}</w:rPr><w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def paragraph(
    *runs: str,
    align: str = "left",
    before: int = 0,
    after: int = 80,
    line: int = 240,
    keep_next: bool = False,
) -> str:
    keep = "<w:keepNext/>" if keep_next else ""
    return (
        "<w:p><w:pPr>"
        f"{keep}<w:spacing w:before=\"{before}\" w:after=\"{after}\" "
        f"w:line=\"{line}\" w:lineRule=\"auto\"/><w:jc w:val=\"{align}\"/>"
        "</w:pPr>"
        + "".join(runs)
        + "</w:p>"
    )


def main() -> None:
    doc = Document(str(UNPACKED), author="OpenAI", initials="OA")
    editor = doc["word/document.xml"]
    body = editor.get_node(tag="w:body")
    section = body.getElementsByTagName("w:sectPr")[0].toxml()

    title = (
        "Candidate-pool opportunity and selection stability under finite validation in molecular "
        "property prediction: a repeated nested audit"
    )
    paragraphs = [
        paragraph(run("17 August 2026"), align="right", after=100),
        paragraph(run("Editors-in-Chief", bold=True), after=0, keep_next=True),
        paragraph(run("Journal of Cheminformatics", italic=True), after=100),
        paragraph(run("Re: Submission of a Research Article", bold=True), after=60, keep_next=True),
        paragraph(run(title, bold=True, italic=True), after=100),
        paragraph(run("Dear Editors-in-Chief,"), after=80),
        paragraph(
            run(
                "On behalf of all authors, we are pleased to submit the Research Article entitled “"
            ),
            run(title, italic=True),
            run("” for consideration in Journal of Cheminformatics."),
            align="left",
        ),
        paragraph(
            run(
                "This manuscript addresses a recurrent methodological problem in molecular property "
                "prediction. Expanding a candidate registry changes both the set of available models "
                "and the difficulty of selecting among them with finite validation data. Consequently, "
                "a smaller completion gap can be misinterpreted as improved selection stability even "
                "when the apparent change is driven primarily by newly available candidates."
            ),
            align="left",
        ),
        paragraph(
            run(
                "We introduce an exact decomposition of the full-registry completion gap into "
                "candidate-availability and within-prefix selection components. We evaluate this "
                "decomposition in a fixed 32-candidate registry across nine public molecular-property "
                "endpoints using ten split seeds and repeated 3 × 3 nested scaffold evaluation. "
                "Classification ROC-AUC and regression RMSE remain on their independent natural scales. "
                "The manuscript retains mixed and negative findings, including cases in which the two "
                "components move in opposite directions, and therefore avoids presenting candidate-pool "
                "expansion as uniformly beneficial."
            ),
            align="left",
        ),
        paragraph(
            run(
                "The work is well suited to Journal of Cheminformatics because it provides a reproducible "
                "evaluation framework for molecular machine learning, candidate selection, and chemical "
                "support auditing. The submission includes editable figures, machine-readable source "
                "tables, split assignments, inner- and outer-level outputs, executable code, environment "
                "metadata, and cryptographic checksums to support independent verification."
            ),
            align="left",
        ),
        paragraph(
            run(
                "We confirm that the manuscript is original, has not been published, and is not under "
                "consideration by another journal. All authors have reviewed and approved the submitted "
                "version and agree with its submission to Journal of Cheminformatics. The authors declare "
                "no competing interests. The study involved no human participants or animals. Any "
                "AI-assisted editorial or code-review support is disclosed in the manuscript, and the "
                "authors retain full responsibility for the scientific content and conclusions."
            ),
            align="left",
            after=80,
        ),
        paragraph(
            run(
                "Thank you for considering our manuscript. We believe that its distinction between "
                "candidate opportunity and selection realization will be useful to researchers designing "
                "and reviewing molecular-property prediction studies."
            ),
            align="left",
            after=100,
        ),
        paragraph(run("Sincerely,"), after=60),
        paragraph(run("Yongxia Yang", bold=True), after=0, line=240),
        paragraph(run("Primary corresponding author, on behalf of all authors"), after=0, line=240),
        paragraph(run("Email: yangyongxia@gdpu.edu.cn"), after=80, line=240),
        paragraph(run("Luonan Qiu", bold=True), after=0, line=240),
        paragraph(run("Co-corresponding author"), after=0, line=240),
        paragraph(run("Email: 532039615@qq.com"), after=80, line=240),
        paragraph(
            run(
                "College of Medical Information Engineering, Guangdong Pharmaceutical University, "
                "Guangzhou, Guangdong 510006, China"
            ),
            after=0,
            line=240,
        ),
        paragraph(
            run(
                "The First Affiliated Hospital of Guangdong Pharmaceutical University, Guangzhou, "
                "Guangdong 510080, China"
            ),
            after=0,
            line=240,
        ),
    ]

    replacement = "<w:body>" + "".join(paragraphs) + section + "</w:body>"
    editor.replace_node(body, replacement)
    doc.save()


if __name__ == "__main__":
    main()
