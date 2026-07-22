from __future__ import annotations

import importlib.util
from pathlib import Path


BASE = Path(r"D:\fzyc\scripts\audit_paper32_figure_fonts_20260718.py")
spec = importlib.util.spec_from_file_location("figure_font_audit", BASE)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

module.ROOT = Path(r"D:\fzyc\output\paper33_final_minor_revision_20260718")
module.SOURCE_ROOT = module.ROOT / "main_figures"
module.DOCS = [
    module.ROOT / "Candidate_pool_expansion_Journal_of_Cheminformatics_FINAL_CLEAN.docx",
    module.ROOT / "候选池扩张与模型选择损失_中文终稿.docx",
]
module.SOURCES = [module.SOURCE_ROOT / f"Figure{i}.svg" for i in range(1, 8)]


if __name__ == "__main__":
    module.main()
