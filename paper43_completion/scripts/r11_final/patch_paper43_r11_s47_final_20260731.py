from pathlib import Path
import shutil
import zipfile
from lxml import etree

ROOT = Path(r"D:\fzyc")
REVIEW = ROOT / "output" / "paper43_jcheminform_completion_20260726" / "author_review"
WORK = ROOT / "work" / "r11_s47_final_ooxml_20260731"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}

EN = REVIEW / "Main_manuscript_Journal_of_Cheminformatics_R11_STRUCTURAL_TECHNICAL_CANDIDATE_CONFLICT_HOLD_WORD_RESAVED_v2.docx"
ZH = next(p for p in REVIEW.glob("*R11*WORD_RESAVED_v2.docx") if not p.name.startswith(("Main_", "Additional_")))
SUPP = REVIEW / "Additional_file_1_Supplementary_Methods_and_Results_R11_STRUCTURAL_TECHNICAL_CANDIDATE_CONFLICT_HOLD_WORD_RESAVED_v2.docx"
FILES = [
    (EN, REVIEW / "Main_manuscript_Journal_of_Cheminformatics_R11_STRUCTURAL_TECHNICAL_CANDIDATE_CONFLICT_HOLD_FINAL.docx"),
    (ZH, REVIEW / "候选池扩张_有限验证下的机会与选择稳定性_中文稿_R11_结构技术候选版_CONFLICT_HOLD_FINAL.docx"),
    (SUPP, REVIEW / "Additional_file_1_Supplementary_Methods_and_Results_R11_STRUCTURAL_TECHNICAL_CANDIDATE_CONFLICT_HOLD_FINAL.docx"),
]

for index, (src, out) in enumerate(FILES):
    work = WORK / str(index)
    if work.exists(): shutil.rmtree(work)
    work.mkdir(parents=True)
    with zipfile.ZipFile(src) as z: z.extractall(work)
    dp = work / "word" / "document.xml"
    parser = etree.XMLParser(remove_blank_text=False)
    doc = etree.parse(str(dp), parser)
    replacements = 0
    for t in doc.xpath("//w:t", namespaces=NS):
        if t.text and "S43" in t.text:
            t.text = t.text.replace("S43", "S47"); replacements += 1
        if index == 1 and t.text and "候选库" in t.text:
            t.text = t.text.replace("候选库", "候选池"); replacements += 1
    if replacements == 0:
        raise RuntimeError(f"No S43 references found in {src.name}")
    dp.write_bytes(etree.tostring(doc, xml_declaration=True, encoding="UTF-8", standalone="yes"))
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        for p in sorted(work.rglob("*")):
            if p.is_file(): z.write(p, p.relative_to(work).as_posix())
    print(out, replacements, out.stat().st_size)
