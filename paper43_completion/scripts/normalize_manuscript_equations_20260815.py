from __future__ import annotations

import os
import argparse
import shutil
import tempfile
import zipfile
from copy import deepcopy
from pathlib import Path

from lxml import etree


ROOT = Path(r"D:\fzyc")
PACKAGE = ROOT / "output" / "Journal_of_Cheminformatics_strict_submission_20260809"
MAIN = PACKAGE / "01_Submission" / "manuscript_revised_submission_ready.docx"
SUPPLEMENT = PACKAGE / "02_Additional_files" / "Additional_file_1_supplementary_methods.docx"
BACKUP = ROOT / "work" / "formula_audit_20260815"

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NS = {"w": W, "m": M}


def q(namespace: str, tag: str) -> etree.QName:
    return etree.QName(namespace, tag)


def nodes(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        result = []
        for item in value:
            result.extend(nodes(item))
        return result
    if isinstance(value, str):
        return [run(value)]
    return [value]


def slot(tag: str, value):
    element = etree.Element(q(M, tag))
    for child in nodes(value):
        element.append(deepcopy(child))
    return element


def run(text: str, plain: bool = False):
    element = etree.Element(q(M, "r"))
    if plain:
        properties = etree.SubElement(element, q(M, "rPr"))
        style = etree.SubElement(properties, q(M, "sty"))
        style.set(q(M, "val"), "p")
    word_properties = etree.SubElement(element, q(W, "rPr"))
    fonts = etree.SubElement(word_properties, q(W, "rFonts"))
    fonts.set(q(W, "ascii"), "Cambria Math")
    fonts.set(q(W, "hAnsi"), "Cambria Math")
    size = etree.SubElement(word_properties, q(W, "sz"))
    size.set(q(W, "val"), "22")
    text_element = etree.SubElement(element, q(M, "t"))
    text_element.text = text
    return element


def sub(base, lower, lower_plain: bool = False):
    element = etree.Element(q(M, "sSub"))
    element.append(slot("e", base))
    element.append(slot("sub", run(lower, lower_plain) if isinstance(lower, str) else lower))
    return element


def sup(base, upper, upper_plain: bool = False):
    element = etree.Element(q(M, "sSup"))
    element.append(slot("e", base))
    element.append(slot("sup", run(upper, upper_plain) if isinstance(upper, str) else upper))
    return element


def subsup(base, lower, upper, lower_plain: bool = False, upper_plain: bool = False):
    element = etree.Element(q(M, "sSubSup"))
    element.append(slot("e", base))
    element.append(slot("sub", run(lower, lower_plain) if isinstance(lower, str) else lower))
    element.append(slot("sup", run(upper, upper_plain) if isinstance(upper, str) else upper))
    return element


def accent(base, character: str):
    element = etree.Element(q(M, "acc"))
    properties = etree.SubElement(element, q(M, "accPr"))
    symbol = etree.SubElement(properties, q(M, "chr"))
    symbol.set(q(M, "val"), character)
    element.append(slot("e", base))
    return element


def fraction(numerator, denominator):
    element = etree.Element(q(M, "f"))
    element.append(slot("num", numerator))
    element.append(slot("den", denominator))
    return element


def nary(character: str, lower, upper, expression):
    element = etree.Element(q(M, "nary"))
    properties = etree.SubElement(element, q(M, "naryPr"))
    symbol = etree.SubElement(properties, q(M, "chr"))
    symbol.set(q(M, "val"), character)
    location = etree.SubElement(properties, q(M, "limLoc"))
    location.set(q(M, "val"), "undOvr")
    if upper is None:
        hide = etree.SubElement(properties, q(M, "supHide"))
        hide.set(q(M, "val"), "1")
    element.append(slot("sub", lower))
    element.append(slot("sup", "" if upper is None else upper))
    element.append(slot("e", expression))
    return element


def limit(operator: str, lower, expression):
    element = etree.Element(q(M, "limLow"))
    element.append(slot("e", run(operator, plain=True)))
    element.append(slot("lim", lower))
    return [element, expression]


def delimiter(begin: str, end: str, expression):
    element = etree.Element(q(M, "d"))
    properties = etree.SubElement(element, q(M, "dPr"))
    begin_element = etree.SubElement(properties, q(M, "begChr"))
    begin_element.set(q(M, "val"), begin)
    end_element = etree.SubElement(properties, q(M, "endChr"))
    end_element.set(q(M, "val"), end)
    element.append(slot("e", expression))
    return element


def math(value):
    element = etree.Element(q(M, "oMath"))
    for child in nodes(value):
        element.append(deepcopy(child))
    return element


def c(k="K"):
    return sub("C", k)


def g(kind: str):
    return sub("G", kind, lower_plain=True)


def jhat():
    return sub(accent("j", "̂"), "u")


def jref(kind: str):
    return subsup("j", "ref", kind, lower_plain=True, upper_plain=True)


def bar_g(q_value="q", endpoint="e", seed="s"):
    return sub(accent("G", "¯"), f"{q_value},{endpoint},{seed}")


def delta(kind="q"):
    return sub("Δ", kind, lower_plain=kind in {"inv", "avail", "dep"})


def selected_formula():
    return math([
        jhat(), "(K) = ",
        limit("arg max", ["j ∈ ", c("K")], run("V(u,j)")),
    ])


def reference_formula(kind: str):
    pool = "32" if kind == "inv" else "K"
    arguments = "(−s)" if kind == "inv" else "(−s,K)"
    summation = nary("∑", "u′: s(u′) ≠ s", None, "A(u′,j)")
    mean = fraction(summation, "|{u′: s(u′) ≠ s}|")
    return math([
        jref(kind), arguments, " = ",
        limit("arg max", ["j ∈ ", c(pool)], delimiter("[", "]", mean)),
    ])


def gap_formula(kind: str):
    reference = "inv" if kind == "inv" else "dep"
    args = "(−s)" if reference == "inv" else "(−s,K)"
    return math([
        g(kind), "(u,K) = A(u,", jref(reference), args,
        ") − A(u,", jhat(), "(K))",
    ])


def availability_formula():
    return math([
        g("avail"), "(u,K) = A(u,", jref("inv"), "(−s)) − A(u,",
        jref("dep"), "(−s,K))",
    ])


def identity_formula():
    return math([g("inv"), "(u,K) = ", g("avail"), "(u,K) + ", g("dep"), "(u,K)"])


def seed_mean_formula():
    numerator = nary("∑", "f=1", sub("F", "e,s"), [g("q"), "((s,f),K)"])
    return math([bar_g(), "(K) = ", fraction(numerator, sub("F", "e,s")), ",   q ∈ {inv, avail, dep}"])


def endpoint_contrast_formula():
    term = delimiter("[", "]", [bar_g(), "(32) − ", bar_g(), "(4)"])
    numerator = nary("∑", "s=1", sub("S", "e"), term)
    return math([delta(), "(e) = ", fraction(numerator, sub("S", "e"))])


def simple_selected(symbol):
    return math([symbol, " = ", limit("arg max", ["j ∈ ", c("K")], "V(u,j)")])


def supplement_formulas():
    j_best = sub("j", "best,u", lower_plain=True)
    loss = sub("L", "u")
    loss_tilde = sub(accent("L", "̃"), "u")
    rank = sub("r", "u")
    harmonic = sub("H", "K")
    mrr = sub(run("MRR", plain=True), "u")
    mrr_tilde = sub(accent(run("MRR", plain=True), "̃"), "u")
    indicator = run("I", plain=True)

    formulas = {
        "1": selected_formula(),
        "2": math([j_best, "(K) = ", limit("arg max", ["j ∈ ", c("K")], "A(u,j)")]),
        "3": math([loss, "(K) = A(u,", j_best, "(K)) − A(u,", jhat(), "(K))"]),
        "4": math([
            loss_tilde, "(K) = ",
            fraction(
                [loss, "(K)"],
                [limit("max", ["j ∈ ", c("K")], "A(u,j)"), " − ",
                 limit("min", ["j ∈ ", c("K")], "A(u,j)"), " + ", sub("ε", "num", lower_plain=True)],
            ),
        ]),
        "5a": math([
            sub(run("CAHit", plain=True), "q,u"), " = ",
            fraction([indicator, "(", rank, " ≤ q) − ", fraction("q", "K")], ["1 − ", fraction("q", "K")]),
            ",   q = 3",
        ]),
        "5b": math([mrr, " = ", fraction("1", rank)]),
        "6": math([
            sup(run("E", plain=True), "0"), "[", run("MRR", plain=True), "] = ", fraction(harmonic, "K"),
            ";   ", mrr_tilde, " = ",
            fraction([mrr, " − ", fraction(harmonic, "K")], ["1 − ", fraction(harmonic, "K")]),
        ]),
        "7": selected_formula(),
        "8": math([
            jref("inv"), "(−s) = ",
            limit("arg max", ["j ∈ ", c("32")],
                  [fraction("1", sub("N", "−s")), " ", nary("∑", ["u ∈ ", sub("U", "−s")], None, "A(u,j)")]),
        ]),
        "9": math([
            jref("dep"), "(−s,K) = ",
            limit("arg max", ["j ∈ ", c("K")],
                  [fraction("1", sub("N", "−s")), " ", nary("∑", ["u ∈ ", sub("U", "−s")], None, "A(u,j)")]),
        ]),
        "10a": gap_formula("inv"),
        "10b": gap_formula("dep"),
        "11": math([
            g("same"), "(u,K) = ", limit("max", ["j ∈ ", c("K")], "A(u,j)"),
            " − A(u,", jhat(), "(K))",
        ]),
        "12a": availability_formula(),
        "12b": identity_formula(),
        "13": math([
            sub(g("inv"), "e,s"), "(K) = ",
            fraction(nary("∑", "f=1", "F", [g("inv"), "((s,f),K)"]), "F"),
        ]),
        "14": math([
            delta("inv"), "(e) = ",
            fraction(
                nary("∑", "s=1", sub("S", "main", lower_plain=True),
                     delimiter("[", "]", [sub(g("inv"), "e,s"), "(32) − ", sub(g("inv"), "e,s"), "(4)"])),
                sub("S", "main", lower_plain=True),
            ),
        ]),
        "15": math([
            sub("X", "raw,u,j", lower_plain=True), " = A(u,j);   ",
            sub("X", "ctr,u,j", lower_plain=True), " = A(u,j) − ",
            fraction(nary("∑", "l=1", "K", "A(u,l)"), "K"),
        ]),
        "16": math([
            sub("X", "ref,u,j", lower_plain=True), " = A(u,j) − A(u,", sub("j", "0"), ");   ",
            sub("X", "rank,u,j", lower_plain=True), " = ", sub(run("rank", plain=True), "j"), "{A(u,j)}",
        ]),
        "17a": math([sub("Σ", "LW", lower_plain=True), " = (1 − α)", sub("S", "cov", lower_plain=True), " + αT"]),
        "17b": math([sub("p", "i"), " = ", fraction(sub("λ", "i"), nary("∑", "l", None, sub("λ", "l")))]),
        "18a": math([sub("r", "ent", lower_plain=True), " = ", run("exp", plain=True), "(", "−", nary("∑", "i", None, [sub("p", "i"), run("ln", plain=True), sub("p", "i")]), ")"]),
        "18b": math([sub("r", "PR", lower_plain=True), " = ", fraction(sup(delimiter("(", ")", nary("∑", "i", None, sub("λ", "i"))), "2"), nary("∑", "i", None, sup(sub("λ", "i"), "2"))), " = ", fraction("1", nary("∑", "i", None, sup(sub("p", "i"), "2")))]),
        "19a": math([sub("G", "best,u,p,K", lower_plain=True), " = ", limit("max", ["j ∈ ", sub("C", "p,K")], "A(u,j)"), " − A(u,a)"]),
        "19b": math([sub("G", "sel,u,p,K", lower_plain=True), " = A(u,", sub("j", "u,p,K"), ") − A(u,a)"]),
        "20a": math([
            sub(accent("G", "¯"), "sel,e,p,K", lower_plain=True), " = ",
            fraction(
                nary("∑", "s,f", None,
                     fraction(sub("G", "sel,s,f,p,K", lower_plain=True), sub("G", "best,s,f,hom,K", lower_plain=True))),
                "SF",
            ),
        ]),
        "20b": math([sub("d", "rel,e,p,K", lower_plain=True), " = ", fraction([sub("r", "ent", lower_plain=True), "(", sub("X", "e,p,K"), ")"], "K")]),
        "21": math([
            sub("L", "CF,e,p,K", lower_plain=True), " = ",
            fraction(
                nary("∑", "s,f", None,
                     fraction(["A(s,f,", jref("inv"), "(−s)) − A(s,f,", sub("j", "s,f"), ")"], sub("G", "best,s,f,hom,K", lower_plain=True))),
                "SF",
            ),
        ]),
        "22a": math([sub("H", "sel", lower_plain=True), " = −", nary("∑", "j", None, [sub("π", "j"), run("ln", plain=True), sub("π", "j")])]),
        "22b": math([sub("H", "sel,norm", lower_plain=True), " = ", fraction(sub("H", "sel", lower_plain=True), [run("ln", plain=True), " K"])]),
    }
    return formulas


def paragraph_text(paragraph) -> str:
    return "".join(paragraph.xpath(".//w:t/text() | .//m:t/text()", namespaces=NS))


def set_formula_paragraph(paragraph, formula, numbered: bool = False):
    properties = paragraph.find("w:pPr", NS)
    for child in list(paragraph):
        if child is not properties:
            paragraph.remove(child)
    if properties is None:
        properties = etree.Element(q(W, "pPr"))
        paragraph.insert(0, properties)
    for tag in ("w:jc", "w:spacing", "w:keepLines"):
        for old in properties.xpath(f"./{tag}", namespaces=NS):
            properties.remove(old)
    spacing = etree.SubElement(properties, q(W, "spacing"))
    spacing.set(q(W, "before"), "0")
    spacing.set(q(W, "after"), "0")
    spacing.set(q(W, "line"), "240")
    spacing.set(q(W, "lineRule"), "auto")
    if not numbered:
        alignment = etree.SubElement(properties, q(W, "jc"))
        alignment.set(q(W, "val"), "center")
        paragraph.append(formula)
        return
    tabs = properties.find("w:tabs", NS)
    if tabs is None:
        tabs = etree.SubElement(properties, q(W, "tabs"))
        for value, position in (("center", "4649"), ("right", "9298")):
            tab = etree.SubElement(tabs, q(W, "tab"))
            tab.set(q(W, "val"), value)
            tab.set(q(W, "pos"), position)
    left = etree.SubElement(paragraph, q(W, "r"))
    etree.SubElement(left, q(W, "tab"))
    paragraph.append(formula)
    right = etree.SubElement(paragraph, q(W, "r"))
    etree.SubElement(right, q(W, "tab"))


def replace_zip_member(path: Path, member: str, data: bytes):
    descriptor, temporary_name = tempfile.mkstemp(suffix=path.suffix, dir=path.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as target:
            for item in source.infolist():
                target.writestr(item, data if item.filename == member else source.read(item.filename))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def patch_main():
    with zipfile.ZipFile(MAIN) as archive:
        root = etree.fromstring(archive.read("word/document.xml"))
    body = root.find("w:body", NS)
    replacements = {
        "ĵu(K) =": selected_formula(),
        "jrefinv(−s) =": reference_formula("inv"),
        "jrefdep(−s, K) =": reference_formula("dep"),
        "Ginv(u, K) = A": gap_formula("inv"),
        "Gdep(u, K) = A": gap_formula("dep"),
        "Gavail(u, K) = A": availability_formula(),
        "Ginv(u, K) = Gavail": identity_formula(),
        "Ḡq,e,s(K) =": seed_mean_formula(),
        "Δq(e) =": endpoint_contrast_formula(),
    }
    found = set()
    for paragraph in body.xpath("./w:p", namespaces=NS):
        text = paragraph_text(paragraph).strip()
        for prefix, formula in replacements.items():
            if text.startswith(prefix):
                set_formula_paragraph(paragraph, formula)
                found.add(prefix)
                break
    if found != set(replacements):
        raise RuntimeError(f"Main formula targets missing: {sorted(set(replacements) - found)}")
    replace_zip_member(MAIN, "word/document.xml", etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes"))


def patch_supplement():
    with zipfile.ZipFile(SUPPLEMENT) as archive:
        root = etree.fromstring(archive.read("word/document.xml"))
    body = root.find("w:body", NS)
    formulas = supplement_formulas()
    found = set()
    for paragraph in body.xpath("./w:p[.//m:oMath]", namespaces=NS):
        number_text = "".join(paragraph.xpath("./w:r[last()]/w:t/text()", namespaces=NS)).strip()
        if not number_text.startswith("(") or not number_text.endswith(")"):
            continue
        number = number_text[1:-1]
        if number not in formulas:
            continue
        set_formula_paragraph(paragraph, formulas[number], numbered=True)
        number_run = etree.SubElement(paragraph, q(W, "r"))
        properties = etree.SubElement(number_run, q(W, "rPr"))
        fonts = etree.SubElement(properties, q(W, "rFonts"))
        fonts.set(q(W, "ascii"), "Times New Roman")
        fonts.set(q(W, "hAnsi"), "Times New Roman")
        size = etree.SubElement(properties, q(W, "sz"))
        size.set(q(W, "val"), "22")
        text = etree.SubElement(number_run, q(W, "t"))
        text.text = f"({number})"
        found.add(number)
    if found != set(formulas):
        missing = sorted(set(formulas) - found)
        raise RuntimeError(f"Supplement formula targets missing: {missing}")
    replace_zip_member(SUPPLEMENT, "word/document.xml", etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes"))


def main():
    global MAIN, SUPPLEMENT, BACKUP
    parser = argparse.ArgumentParser(description="Normalize manuscript and supplementary display equations to editable OMML.")
    parser.add_argument("main_docx", nargs="?", type=Path, default=MAIN)
    parser.add_argument("supplement_docx", nargs="?", type=Path, default=SUPPLEMENT)
    parser.add_argument("--backup-dir", type=Path, default=BACKUP)
    args = parser.parse_args()
    MAIN = args.main_docx
    SUPPLEMENT = args.supplement_docx
    BACKUP = args.backup_dir
    BACKUP.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MAIN, BACKUP / "manuscript_before_formula_normalization.docx")
    shutil.copy2(SUPPLEMENT, BACKUP / "additional_file_1_before_formula_normalization.docx")
    patch_main()
    patch_supplement()
    print(MAIN)
    print(SUPPLEMENT)


if __name__ == "__main__":
    main()
