from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(r"D:\fzyc\output\paper33_final_minor_revision_20260718")
P31 = Path(r"D:\fzyc\output\paper31_submission_package_20260717")
DATA = Path(r"D:\fzyc\output\paper31_expanded_intervention_20260717")
AUDIT = ROOT / "audit_sources"
CODE = ROOT / "reproducibility_code"


def copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def main() -> None:
    sources = {
        P31 / "figure_source_data" / "Figure_7_source_data.xlsx": AUDIT / "figure7_source_data" / "Figure_7_source_data.xlsx",
        P31 / "figure_source_data" / "Figure_7_Panel_A_source.csv": AUDIT / "figure7_source_data" / "Figure_7_Panel_A_source.csv",
        P31 / "figure_source_data" / "Figure_7_Panel_B_source.csv": AUDIT / "figure7_source_data" / "Figure_7_Panel_B_source.csv",
        P31 / "figure_source_data" / "Figure_7_Panel_C_source.csv": AUDIT / "figure7_source_data" / "Figure_7_Panel_C_source.csv",
        P31 / "figure_source_data" / "Figure_7_Panel_D_source.csv": AUDIT / "figure7_source_data" / "Figure_7_Panel_D_source.csv",
        DATA / "Paper31_selection_units.csv": AUDIT / "computational_exposure" / "Paper31_selection_units.csv",
        DATA / "Paper31_equal_budget_units.csv": AUDIT / "computational_exposure" / "Paper31_equal_budget_units.csv",
        DATA / "Paper31_expanded_intervention_audit.json": AUDIT / "computational_exposure" / "Paper31_expanded_intervention_audit.json",
        DATA / "composition_split_loop" / "Paper31_similarity_split_manifest.csv": AUDIT / "split_manifests" / "Paper31_similarity_split_manifest.csv",
        DATA / "composition_split_loop" / "Paper31_composition_split_units.csv": AUDIT / "split_manifests" / "Paper31_composition_split_units.csv",
        DATA / "Paper31_source_availability_audit.csv": AUDIT / "source_hashes" / "Paper31_source_availability_audit.csv",
        P31 / "SHA256SUMS.txt": AUDIT / "source_hashes" / "Paper31_SHA256SUMS.txt",
        P31 / "Package_manifest.json": AUDIT / "source_hashes" / "Paper31_Package_manifest.json",
    }
    for source, destination in sources.items():
        copy(source, destination)

    if CODE.exists():
        shutil.rmtree(CODE)
    shutil.copytree(P31 / "reproducibility_code", CODE / "paper31_analysis")
    final_scripts = [
        "build_paper33_final_minor_revision_manuscripts_20260718.py",
        "build_paper32_figure7_large_text_20260718.py",
        "embed_paper33_tnr_figures_20260718.py",
        "finalize_paper33_equations_and_mapping_20260718.py",
        "build_paper33_supplementary_package_20260718.py",
        "update_paper33_supplementary_methods_20260718.py",
        "build_paper33_consistency_reports_20260718.py",
        "qc_paper33_figure7_20260718.py",
        "audit_paper33_manuscripts_20260718.py",
        "audit_paper33_figure_fonts_20260718.py",
        "export_paper33_revision_extracts_20260718.py",
        "validate_paper33_final_submission_20260718.py",
        "assemble_paper33_audit_sources_and_manifest_20260718.py",
    ]
    for name in final_scripts:
        copy(Path(r"D:\fzyc\scripts") / name, CODE / "paper33_finalization" / name)

    files = sorted(
        path for path in ROOT.rglob("*")
        if path.is_file() and path.name not in {"SHA256SUMS.txt", "Final_output_manifest.json"}
    )
    manifest = []
    for path in files:
        manifest.append({
            "path": path.relative_to(ROOT).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        })
    (ROOT / "Final_output_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"{item['sha256']}  {item['path']}" for item in manifest]
    (ROOT / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"files_hashed": len(manifest), "audit_sources": len(sources), "finalization_scripts": len(final_scripts)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
