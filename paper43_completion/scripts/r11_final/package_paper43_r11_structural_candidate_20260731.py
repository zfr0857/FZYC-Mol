from pathlib import Path
import hashlib
import shutil
import zipfile

ROOT = Path(r"D:\fzyc")
BASE = ROOT / "output" / "paper43_jcheminform_completion_20260726"
REVIEW = BASE / "author_review"
OLD = BASE / "JoC_R10_TECHNICAL_CANDIDATE_CONFLICT_HOLD_20260731"
PKG = BASE / "JoC_R11_STRUCTURAL_TECHNICAL_CANDIDATE_CONFLICT_HOLD_20260731"
FIGNEW = ROOT / "work" / "r11_structural_figures_20260731"
LO = ROOT / "work" / "r11_libreoffice_final_20260731"

if PKG.exists(): shutil.rmtree(PKG)
for folder in ["01_Manuscripts", "02_Title_Page_and_Declarations", "03_Main_Figures", "04_Additional_Files", "05_Source_Data", "06_Quality_Control", "07_Compatibility", "08_Reproducibility_Scripts", "09_Repository_Metadata"]:
    (PKG/folder).mkdir(parents=True, exist_ok=True)

manuscripts = [
    "Main_manuscript_Journal_of_Cheminformatics_R11_STRUCTURAL_TECHNICAL_CANDIDATE_CONFLICT_HOLD_FINAL.docx",
    "Main_manuscript_Journal_of_Cheminformatics_R11_STRUCTURAL_TECHNICAL_CANDIDATE_TRACK_CHANGES_CONFLICT_HOLD.docx",
    "Main_manuscript_Journal_of_Cheminformatics_R11_STRUCTURAL_TECHNICAL_CANDIDATE_CONFLICT_HOLD_FINAL_WPS.pdf",
    "候选池扩张_有限验证下的机会与选择稳定性_中文稿_R11_结构技术候选版_CONFLICT_HOLD_FINAL.docx",
    "候选池扩张_有限验证下的机会与选择稳定性_中文修订痕迹稿_R11_结构技术候选版_CONFLICT_HOLD.docx",
    "候选池扩张_有限验证下的机会与选择稳定性_中文稿_R11_结构技术候选版_CONFLICT_HOLD_FINAL_WPS.pdf",
]
for name in manuscripts: shutil.copy2(REVIEW/name, PKG/"01_Manuscripts"/name)

for p in (OLD/"02_Title_Page_and_Declarations").glob("*"): shutil.copy2(p, PKG/"02_Title_Page_and_Declarations"/p.name)

for n in range(1,9):
    source_dir = FIGNEW if n in {1,3,7,8} else OLD/"03_Main_Figures"
    for suffix in [".pdf", ".svg", "_600dpi.png"]:
        src = source_dir/f"Figure{n}{suffix}"
        shutil.copy2(src, PKG/"03_Main_Figures"/src.name)

additional = [
    (REVIEW/"Additional_file_1_Supplementary_Methods_and_Results_R11_STRUCTURAL_TECHNICAL_CANDIDATE_CONFLICT_HOLD_FINAL.docx", "Additional_file_1_Supplementary_Methods_and_Results_R11_FINAL.docx"),
    (REVIEW/"Additional_file_1_Supplementary_Methods_and_Results_R11_STRUCTURAL_TECHNICAL_CANDIDATE_CONFLICT_HOLD_FINAL_WPS.pdf", "Additional_file_1_Supplementary_Methods_and_Results_R11_FINAL.pdf"),
    (REVIEW/"Additional_file_2_Machine_readable_Supplementary_Tables_S1-S47_R11.xlsx", "Additional_file_2_Machine_readable_Supplementary_Tables_S1-S47_R11.xlsx"),
    (OLD/"05_Additional_Files"/"Additional_file_3_Supplementary_Figures_S1-S25.pdf", "Additional_file_3_Supplementary_Figures_S1-S25.pdf"),
    (OLD/"05_Additional_Files"/"Additional_file_4_Code_and_reproducibility_package_r3_CONFLICT_HOLD.zip", "Additional_file_4_Code_and_reproducibility_package_r3_CONFLICT_HOLD.zip"),
]
for src,name in additional: shutil.copy2(src, PKG/"04_Additional_Files"/name)

source_old = OLD/"05_Additional_Files"/"Source_Data"
if source_old.exists():
    for p in source_old.rglob("*"):
        if p.is_file():
            dst=PKG/"05_Source_Data"/p.relative_to(source_old); dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(p,dst)
for p in [FIGNEW/"Figure_3A_primary_ten_seed_source.csv", FIGNEW/"figure_source_data"]:
    if p.is_file(): shutil.copy2(p,PKG/"05_Source_Data"/p.name)
    elif p.is_dir(): shutil.copytree(p,PKG/"05_Source_Data"/p.name,dirs_exist_ok=True)

for p in LO.glob("*.pdf"): shutil.copy2(p, PKG/"07_Compatibility"/("LibreOffice_"+p.name))
for src,name in [
    (REVIEW/"Main_manuscript_Journal_of_Cheminformatics_R11_STRUCTURAL_TECHNICAL_CANDIDATE_CONFLICT_HOLD_FINAL_WPS.pdf","WPS_English_clean.pdf"),
    (REVIEW/"候选池扩张_有限验证下的机会与选择稳定性_中文稿_R11_结构技术候选版_CONFLICT_HOLD_FINAL_WPS.pdf","WPS_Chinese_clean.pdf"),
    (REVIEW/"Additional_file_1_Supplementary_Methods_and_Results_R11_STRUCTURAL_TECHNICAL_CANDIDATE_CONFLICT_HOLD_FINAL_WPS.pdf","WPS_Supplementary_Methods.pdf"),
]: shutil.copy2(src,PKG/"07_Compatibility"/name)

scripts = [
    "build_paper43_r11_structural_figures_20260731.py", "build_paper43_r11_manuscripts_20260731.py",
    "patch_paper43_r11_s47_final_20260731.py", "build_paper43_r11_tracked_ooxml_20260731.py",
    "build_paper43_r11_s47_workbook_20260731.py", "package_paper43_r11_structural_candidate_20260731.py",
    "audit_paper43_r11_structural_20260731.py",
    "build_paper21_final_figures.py",
]
for name in scripts: shutil.copy2(ROOT/"scripts"/name,PKG/"08_Reproducibility_Scripts"/name)
for p in (OLD/"07_Repository_Metadata").glob("*"): shutil.copy2(p,PKG/"09_Repository_Metadata"/p.name)

(PKG/"README.md").write_text("""# Journal of Cheminformatics R11 structural technical candidate

Status: **CONFLICT_HOLD**. The technical manuscript, Chinese manuscript, main figures, equations, core notation table and supplementary notation Table S47 are synchronized. This package is not a truthful public submission release because real author/title-page/declaration metadata and an authorized public repository release were not supplied.

Primary deliverables are in `01_Manuscripts`; all Figures 1–8 are supplied as editable SVG, PDF and 600 dpi PNG in `03_Main_Figures`; Additional files are in `04_Additional_Files`; compatibility renders are in `07_Compatibility`.
""",encoding="utf-8")
(PKG/"09_Repository_Metadata"/"VERSION").write_text("R11-STRUCTURAL-TECHNICAL-CANDIDATE-CONFLICT-HOLD-2026-07-31\n",encoding="utf-8")
(PKG/"09_Repository_Metadata"/"RELEASE_BLOCKERS_R11.md").write_text("""# Release blockers

1. Real author names, order, affiliations, correspondence address, email and ORCID are absent.
2. Funding, CRediT contributions, competing interests and acknowledgements are not author-confirmed.
3. No authorization was supplied to publish a new public repository release or immutable DOI/tag.
4. Submission-portal PDF conversion cannot be tested without portal access.

No item above was fabricated or represented as complete.
""",encoding="utf-8")

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
rows=[]
for p in sorted(PKG.rglob("*")):
    if p.is_file(): rows.append(f"{sha(p)},{p.relative_to(PKG).as_posix()},{p.stat().st_size}")
(PKG/"SHA256SUMS.csv").write_text("sha256,path,bytes\n"+"\n".join(rows)+"\n",encoding="utf-8")

zip_path=PKG.with_suffix(".zip")
with zipfile.ZipFile(zip_path,"w",zipfile.ZIP_DEFLATED,allowZip64=True) as z:
    for p in sorted(PKG.rglob("*")):
        if p.is_file(): z.write(p,(PKG.name/p.relative_to(PKG)).as_posix())
print(PKG,zip_path,zip_path.stat().st_size)
