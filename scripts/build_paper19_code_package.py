from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path("D:/fzyc").resolve()
OUT = (ROOT / "output").resolve()
STAGE = (OUT / "小论文-19_代码包").resolve()
ARCHIVE = (OUT / "小论文-19_代码包.zip").resolve()
META = ROOT / "packaging" / "paper19"


def safe_clean_stage() -> None:
    if STAGE.parent != OUT or STAGE == OUT:
        raise RuntimeError(f"Refusing to clean unexpected path: {STAGE}")
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def copy_tree(source: Path, destination: Path, include=None) -> None:
    if not source.exists():
        return
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {"__pycache__", ".pytest_cache", ".git"} for part in path.parts):
            continue
        if include is not None and not include(path):
            continue
        copy_file(path, destination / path.relative_to(source))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_data_manifest() -> None:
    registry_path = ROOT / "data" / "dataset_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    selected = [
        "esol",
        "freesolv",
        "lipo",
        "bbbp",
        "bace",
        "clintox",
        "tdc_caco2_wang",
        "tdc_hia_hou",
        "tdc_pgp_broccatelli",
    ]
    rows: list[dict[str, object]] = []
    for dataset in selected:
        item = registry[dataset]
        local = ROOT / "data" / "raw" / item["filename"]
        rows.append(
            {
                "dataset": dataset,
                "source": item["url"],
                "task_type": item["task_type"],
                "source_filename": item["filename"],
                "local_raw_present_at_packaging": local.exists(),
                "local_raw_size_bytes": local.stat().st_size if local.exists() else "",
                "local_raw_sha256": sha256(local) if local.exists() else "",
                "redistributed_in_package": False,
                "license_status": "verify original source terms before redistribution",
                "preprocessing": "RDKit parse/Cleanup, largest fragment, charge normalization where feasible; see source code",
            }
        )
    rows.extend(
        [
            {
                "dataset": "MoleculeACE",
                "source": "https://github.com/molML/MoleculeACE",
                "task_type": "regression boundary panel",
                "source_filename": "not redistributed",
                "local_raw_present_at_packaging": "",
                "local_raw_size_bytes": "",
                "local_raw_sha256": "",
                "redistributed_in_package": False,
                "license_status": "verify original source terms before redistribution",
                "preprocessing": "see MoleculeACE boundary scripts and source-data summaries",
            },
            {
                "dataset": "CycPept-PAMPA/LinPept bRo5",
                "source": "original public repositories cited in manuscript; verify access record before release",
                "task_type": "regression/classification boundary panel",
                "source_filename": "not redistributed",
                "local_raw_present_at_packaging": "",
                "local_raw_size_bytes": "",
                "local_raw_sha256": "",
                "redistributed_in_package": False,
                "license_status": "verify original source terms before redistribution",
                "preprocessing": "see bRo5 boundary scripts and source-data summaries",
            },
        ]
    )
    path = STAGE / "manifests" / "data_manifest.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build_endpoint_registry() -> None:
    rows = [
        ["esol", "regression", "RMSE", "lower", "scaffold_group", "confirmatory pressure; multiview; strong baseline"],
        ["freesolv", "regression", "RMSE", "lower", "scaffold_group", "confirmatory pressure; multiview; strong baseline"],
        ["lipo", "regression", "RMSE", "lower", "scaffold_group", "confirmatory pressure; multiview; strong baseline"],
        ["bbbp", "classification", "ROC-AUC", "higher", "stratified_scaffold_group", "confirmatory pressure; multiview; strong baseline"],
        ["bace", "classification", "ROC-AUC", "higher", "stratified_scaffold_group", "confirmatory pressure; multiview; strong baseline"],
        ["clintox", "classification", "ROC-AUC", "higher", "stratified_scaffold_group", "confirmatory pressure; minority-class negative result"],
        ["tdc_caco2_wang", "regression", "RMSE", "lower", "scaffold_group", "confirmatory pressure; multiview"],
        ["tdc_hia_hou", "classification", "ROC-AUC", "higher", "stratified_scaffold_group", "confirmatory pressure; multiview"],
        ["tdc_pgp_broccatelli", "classification", "ROC-AUC", "higher", "stratified_scaffold_group", "confirmatory pressure; multiview"],
    ]
    path = STAGE / "manifests" / "endpoint_registry.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["endpoint", "task_type", "primary_metric", "metric_direction", "outer_split", "evidence_role", "seeds", "outer_folds", "inner_folds"])
        for row in rows:
            writer.writerow(row + ["11;23;37;53;71", 3, 3])


def copy_repository_code() -> None:
    for name in [
        "pyproject.toml",
        "requirements.txt",
        "requirements.lock",
        "requirements-pretrained.txt",
        "environment.yml",
        "Dockerfile",
        "LICENSE",
        "CITATION.cff",
        "pytest.ini",
        "machine_inventory.json",
    ]:
        source = ROOT / name
        if source.exists():
            copy_file(source, STAGE / name)
    for name in ["README.md", "RUNBOOK.md", "REPRODUCTION_STATUS.md"]:
        copy_file(META / name, STAGE / name)
    copy_tree(ROOT / "src", STAGE / "src")
    copy_tree(ROOT / "tests", STAGE / "tests", include=lambda p: p.suffix in {".py", ".json", ".yaml", ".yml", ".csv"})
    copy_tree(ROOT / "configs", STAGE / "configs")
    copy_tree(ROOT / "scripts", STAGE / "scripts", include=lambda p: p.suffix in {".py", ".ps1"})
    copy_tree(ROOT / ".github", STAGE / ".github")
    for name in ["reproducibility.md", "resource_gap_report.md", "repository_audit.md", "methods_protocol.md"]:
        source = ROOT / "docs" / name
        if source.exists():
            copy_file(source, STAGE / "docs" / name)
    copy_file(ROOT / "data" / "dataset_registry.json", STAGE / "manifests" / "dataset_registry.json")


def copy_artifacts() -> None:
    copy_tree(
        OUT / "paper19_rejection_driven_experiments_20260712",
        STAGE / "artifacts" / "paper19_experiments",
    )
    copy_tree(
        OUT / "paper19_jcheminformatics_revision_20260712",
        STAGE / "artifacts" / "journal_of_cheminformatics_revision",
    )
    copy_tree(OUT / "sci1_hardening_20260707", STAGE / "artifacts" / "strong_baseline")
    copy_tree(
        OUT / "sci1_mechanism_uq_decision_20260707",
        STAGE / "artifacts" / "mechanism_uq_decision",
    )
    copy_tree(
        ROOT / "results" / "reviewer_core_20260624" / "multiview_nested",
        STAGE / "artifacts" / "multiview_nested",
    )
    copy_tree(OUT / "小论文-19_图表与源数据", STAGE / "artifacts" / "main_figures")
    for source, target in [
        (OUT / "小论文-19.docx", STAGE / "manuscript" / "小论文-19.docx"),
        (OUT / "小论文-19_审阅版.pdf", STAGE / "manuscript" / "小论文-19_审阅版.pdf"),
        (OUT / "小论文-19_修改与实验审计报告.md", STAGE / "manuscript" / "修改与实验审计报告.md"),
        (OUT / "小论文-19_修改与实验审计.json", STAGE / "manuscript" / "修改与实验审计.json"),
        (OUT / "paper19_reference_verification.md", STAGE / "manuscript" / "reference_verification.md"),
        (OUT / "小论文-19_逐段修改说明.md", STAGE / "manuscript" / "逐段修改说明.md"),
        (OUT / "小论文-19_图表重组与投稿核查.md", STAGE / "manuscript" / "图表重组与投稿核查.md"),
        (OUT / "小论文-19_Journal_of_Cheminformatics重构审计.json", STAGE / "manuscript" / "Journal_of_Cheminformatics重构审计.json"),
    ]:
        copy_file(source, target)


def build_content_manifest() -> tuple[int, int]:
    excluded = {
        "SHA256SUMS",
        "manifests/PACKAGE_CONTENTS.csv",
        "manifests/PACKAGE_AUDIT.json",
    }
    rows: list[dict[str, object]] = []
    for path in sorted(p for p in STAGE.rglob("*") if p.is_file()):
        rel = path.relative_to(STAGE).as_posix()
        if rel in excluded:
            continue
        rows.append(
            {
                "relative_path": rel,
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    manifest = STAGE / "manifests" / "PACKAGE_CONTENTS.csv"
    with manifest.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["relative_path", "size_bytes", "sha256"])
        writer.writeheader()
        writer.writerows(rows)
    sums = STAGE / "SHA256SUMS"
    sums.write_text("\n".join(f"{row['sha256']}  {row['relative_path']}" for row in rows) + "\n", encoding="utf-8")
    return len(rows), sum(int(row["size_bytes"]) for row in rows)


def build_archive() -> str:
    if ARCHIVE.exists():
        ARCHIVE.unlink()
    with ZipFile(ARCHIVE, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(p for p in STAGE.rglob("*") if p.is_file()):
            archive.write(path, Path("paper19_code_package") / path.relative_to(STAGE))
    return sha256(ARCHIVE)


def main() -> None:
    safe_clean_stage()
    copy_repository_code()
    copy_artifacts()
    build_data_manifest()
    build_endpoint_registry()
    file_count, total_bytes = build_content_manifest()
    audit = {
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": str(STAGE),
        "archive": str(ARCHIVE),
        "file_count_excluding_manifest_files": file_count,
        "total_bytes_excluding_manifest_files": total_bytes,
        "raw_data_redistributed": False,
        "independent_confirmation_completed": False,
        "third_party_cold_start_completed": False,
        "public_doi_available": False,
    }
    audit_path = STAGE / "manifests" / "PACKAGE_AUDIT.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    final_hash = build_archive()
    external_audit = dict(audit)
    external_audit["archive_size_bytes"] = ARCHIVE.stat().st_size
    external_audit["archive_sha256"] = final_hash
    external_audit_path = OUT / "小论文-19_代码包_校验.json"
    external_audit_path.write_text(json.dumps(external_audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "stage": str(STAGE),
                "archive": str(ARCHIVE),
                "file_count": file_count,
                "stage_bytes": total_bytes,
                "archive_bytes": ARCHIVE.stat().st_size,
                "archive_sha256": final_hash,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
