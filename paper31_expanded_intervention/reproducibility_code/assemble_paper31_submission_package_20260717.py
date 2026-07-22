from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "output" / "paper31_expanded_intervention_20260717"
PACKAGE = ROOT / "output" / "paper31_submission_package_20260717"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def copy(path: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)


def main() -> None:
    PACKAGE.mkdir(parents=True, exist_ok=True)
    for folder in ["main_figures", "supplementary_figures", "supplementary_tables", "figure_source_data", "equation_assets", "experiment_exports", "reproducibility_code", "verification"]:
        (PACKAGE / folder).mkdir(parents=True, exist_ok=True)

    for path in (DATA / "figures").glob("*"):
        copy(path, PACKAGE / "main_figures" / path.name)
    for path in (DATA / "supplementary_figures").glob("*"):
        copy(path, PACKAGE / "supplementary_figures" / path.name)
    for path in (DATA / "supplementary_tables").glob("*"):
        copy(path, PACKAGE / "supplementary_tables" / path.name)
    for path in (DATA / "figure_source_data").glob("*"):
        copy(path, PACKAGE / "figure_source_data" / path.name)
    for path in (DATA / "equation_assets").glob("*"):
        if path.is_file():
            copy(path, PACKAGE / "equation_assets" / path.name)

    export_patterns = [
        "Paper31_*.csv", "Paper31_*.csv.gz", "Paper31_*.json",
    ]
    for pattern in export_patterns:
        for path in DATA.glob(pattern):
            copy(path, PACKAGE / "experiment_exports" / path.name)
    split_root = DATA / "composition_split_loop"
    for path in split_root.glob("*"):
        if path.is_file():
            copy(path, PACKAGE / "experiment_exports" / "composition_split_loop" / path.name)

    scripts = [
        "audit_paper31_source_availability_20260717.py",
        "run_paper31_expansion_training_20260717.py",
        "run_paper31_similarity_composition_20260717.py",
        "continue_paper31_chemprop_pipeline_20260717.ps1",
        "continue_paper31_analysis_pipeline_20260717.ps1",
        "analyze_paper31_expanded_intervention_20260717.py",
        "analyze_paper31_composition_split_loop_20260717.py",
        "build_paper31_figures_20260717.py",
        "build_paper31_supplementary_tables_20260717.py",
        "build_paper31_equation_assets_20260717.py",
        "build_paper31_manuscripts_20260717.py",
        "insert_paper31_native_equations_20260717.ps1",
        "insert_paper31_vector_figure7_20260717.ps1",
        "export_paper31_manuscript_pdfs_20260717.ps1",
        "verify_paper31_submission_package_20260717.py",
        "assemble_paper31_submission_package_20260717.py",
    ]
    for name in scripts:
        copy(ROOT / "scripts" / name, PACKAGE / "reproducibility_code" / name)

    for path in (DATA / "logs").glob("*"):
        if path.is_file():
            copy(path, PACKAGE / "verification" / "training_logs" / path.name)
    for name in [
        "Paper31_source_availability_audit.csv", "Paper31_frozen_analysis_plan.json",
        "Paper31_expanded_intervention_audit.json", "Paper31_manuscript_build_audit.json",
    ]:
        path = DATA / name
        if path.exists():
            copy(path, PACKAGE / "verification" / name)

    readme = """Paper31 expanded candidate-pool intervention submission package

Primary additions
- Six prespecified endpoints: ClinTox, BACE, BBBP, ESOL, Lipophilicity and Caco2_Wang.
- Three exact-prefix candidate pools at K = 4, 8, 16 and 32.
- Fixed-K ChemBERTa, MoLFormer, D-MPNN and full-modern component ablations.
- Equal-downstream-budget, anchor, normalization and selection-stability sensitivity analyses.
- Full candidate-composition loop across scaffold and Tanimoto-component splits on ClinTox, BACE and ESOL.
- Figure 7, Figures S16-S21 and Tables S32-S36 with editable source data.
- Twenty-seven native Microsoft Word equations and an equation-to-code mapping.

Statistical unit
Outer-fold effects are averaged within each repeat seed; the five repeat seeds are the resampling blocks. Endpoint-pool-K cells and overlapping registries are not treated as independent experiments.

Cost scope
Downstream time includes nested fit/predict wall time. Pretrained-encoder acquisition, encoder pretraining and cached embedding extraction are excluded and are never described as total end-to-end cost.

Source note
The requested manuscript(6)(2).docx was not present in the workspace. The latest discoverable Paper30 manuscript(6).docx and its Chinese counterpart were used as the source documents.
"""
    (PACKAGE / "README_Paper31_submission_package.txt").write_text(readme, encoding="utf-8")

    files = []
    for path in sorted(PACKAGE.rglob("*")):
        if path.is_file() and path.name not in {"Package_manifest.json", "SHA256SUMS.txt"}:
            files.append({
                "path": str(path.relative_to(PACKAGE)).replace("\\", "/"),
                "bytes": path.stat().st_size, "sha256": sha256(path),
            })
    manifest = {"status": "complete", "file_count": len(files), "files": files}
    (PACKAGE / "Package_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (PACKAGE / "SHA256SUMS.txt").write_text(
        "\n".join(f"{item['sha256']}  {item['path']}" for item in files) + "\n", encoding="utf-8"
    )
    print(json.dumps({"package": str(PACKAGE), "file_count": len(files)}, indent=2))


if __name__ == "__main__":
    main()
