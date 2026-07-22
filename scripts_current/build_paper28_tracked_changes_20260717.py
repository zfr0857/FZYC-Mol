from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(r"D:\fzyc")
SOURCE = ROOT / "output" / "paper27_equal_size_registry_composition_revision_20260716" / "Candidate_pool_expansion_Journal_of_Cheminformatics_manuscript.docx"
REVISION_DIR = ROOT / "output" / "paper28_pre_submission_minor_revision_20260717"
REVISED = REVISION_DIR / "Candidate_pool_expansion_Journal_of_Cheminformatics_manuscript.docx"
OUT = REVISION_DIR / "Candidate_pool_expansion_Journal_of_Cheminformatics_manuscript_tracked_changes.docx"
UNPACKED = REVISION_DIR / "tracked_unpacked"
SKILL = Path(r"C:\Users\Administrator\.codex\plugins\cache\antigravity-awesome-skills\agyb-aas-documents-presentations\12.6.0\skills\docx-official")
UNPACK = SKILL / "ooxml" / "scripts" / "unpack.py"
PACK = SKILL / "ooxml" / "scripts" / "pack.py"
COMPARE = ROOT / "scripts" / "compare_paper27_documents_20260716.ps1"
sys.path.insert(0, str(SKILL))
from scripts.document import Document  # noqa: E402


def main() -> None:
    if OUT.exists():
        OUT.unlink()
    subprocess.run([
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(COMPARE),
        "-Original", str(SOURCE), "-Revised", str(REVISED), "-Output", str(OUT),
    ], check=True)
    if UNPACKED.exists():
        shutil.rmtree(UNPACKED)
    subprocess.run([sys.executable, str(UNPACK), str(OUT), str(UNPACKED)], check=True)
    document = Document(str(UNPACKED), author="OpenAI Codex", initials="OC", track_revisions=True)
    document.save(validate=False)
    validated = OUT.with_name(OUT.stem + ".validated.docx")
    subprocess.run([sys.executable, str(PACK), str(UNPACKED), str(validated)], check=True)
    validated.replace(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
