from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "results" / "audits"
DOCS_DIR = ROOT / "docs"
INVENTORY_PATH = AUDIT_DIR / "file_inventory.csv"
LINEAGE_PATH = AUDIT_DIR / "result_lineage.csv"
HITS_PATH = AUDIT_DIR / "key_number_hits.csv"
REPORT_PATH = DOCS_DIR / "repository_audit.md"
MACHINE_PATH = ROOT / "machine_inventory.json"
GENERATED_ARTIFACTS = {
    INVENTORY_PATH.resolve(),
    LINEAGE_PATH.resolve(),
    HITS_PATH.resolve(),
    REPORT_PATH.resolve(),
    MACHINE_PATH.resolve(),
}

EVIDENCE_EXTENSIONS = {
    ".py", ".yaml", ".yml", ".json", ".csv", ".parquet", ".pt", ".pkl",
    ".png", ".svg", ".docx", ".md", ".txt", ".pdf", ".toml", ".lock",
    ".ckpt", ".tab", ".tsv", ".log", ".sh",
}
TEXT_EXTENSIONS = {".py", ".yaml", ".yml", ".json", ".csv", ".md", ".txt"}
EXCLUDED_TOP_LEVEL = {".git", ".venv-autogluon", "nature-skills", "work"}
EXCLUDED_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache"}
EXTERNAL_INPUTS = [
    Path(os.environ.get("FZYC_TASK_DOC", r"C:\Users\Administrator\Downloads\FZYC-Mol_Codex实施说明与技术任务书.docx")),
    Path(os.environ.get("FZYC_MANUSCRIPT", r"C:\Users\Administrator\Desktop\修改\初稿-10.docx")),
]

KEYS = {
    "clintox_roc_auc_0_9496": [b"0.9496"],
    "freesolv_rmse_1_0286": [b"1.0286"],
    "tdc_5_promoted_17_retained": [b"5/17/0", b"5 promoted", b"17 retained"],
    "nested_top3_k32_0_222": [b"0.2222222222222222", b"0.222"],
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_or_absolute(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def is_in_scope(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if rel.parts and rel.parts[0] in EXCLUDED_TOP_LEVEL:
        return False
    return not any(part in EXCLUDED_NAMES for part in rel.parts)


def iter_evidence_files() -> list[Path]:
    paths: list[Path] = []
    for current, directories, filenames in os.walk(ROOT, topdown=True, followlinks=False):
        current_path = Path(current)
        if current_path == ROOT:
            directories[:] = [name for name in directories if name not in EXCLUDED_TOP_LEVEL]
        directories[:] = [name for name in directories if name not in EXCLUDED_NAMES]
        for filename in filenames:
            path = current_path / filename
            if path.resolve() not in GENERATED_ARTIFACTS and path.suffix.lower() in EVIDENCE_EXTENSIONS:
                paths.append(path)
    paths.extend(path for path in EXTERNAL_INPUTS if path.is_file())
    return sorted(set(paths), key=lambda item: str(item).lower())


def classify_role(path: Path) -> str:
    rel = relative_or_absolute(path).lower()
    if rel.endswith(".docx"):
        return "manuscript_or_instruction"
    if rel.startswith("scripts/") or rel.startswith("src/"):
        return "code"
    if rel.startswith("configs/"):
        return "configuration"
    if rel.startswith("data/"):
        return "data"
    if rel.startswith("reports/") or rel.startswith("output/") or rel.startswith("results/"):
        return "result_or_report"
    if path.is_absolute() and not str(path.resolve()).lower().startswith(str(ROOT.resolve()).lower()):
        return "external_input"
    return "documentation_or_other"


def write_inventory(paths: list[Path]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, path in enumerate(paths, start=1):
        stat = path.stat()
        rows.append({
            "path": relative_or_absolute(path),
            "extension": path.suffix.lower(),
            "size_bytes": stat.st_size,
            "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            "sha256": sha256(path),
            "role": classify_role(path),
            "scope": "external_input" if path in EXTERNAL_INPUTS else "project_evidence",
        })
        if index % 500 == 0:
            print(f"hashed {index}/{len(paths)} files", flush=True)
    with INVENTORY_PATH.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def searchable_bytes(path: Path) -> bytes:
    if path.suffix.lower() == ".docx":
        try:
            with zipfile.ZipFile(path) as archive:
                return b"\n".join(
                    archive.read(name)
                    for name in archive.namelist()
                    if name.startswith("word/") and name.endswith(".xml")
                )
        except (OSError, zipfile.BadZipFile):
            return b""
    if path.suffix.lower() in TEXT_EXTENSIONS or path.suffix.lower() in {".svg"}:
        try:
            return path.read_bytes()
        except OSError:
            return b""
    return b""


def collect_key_hits(paths: list[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        if path.stat().st_size > 250 * 1024 * 1024:
            continue
        payload = searchable_bytes(path)
        if not payload:
            continue
        payload_lower = payload.lower()
        for key, patterns in KEYS.items():
            matches = [pattern.decode("ascii") for pattern in patterns if pattern.lower() in payload_lower]
            if matches:
                rows.append({
                    "claim_key": key,
                    "path": relative_or_absolute(path),
                    "matched_tokens": ";".join(matches),
                    "role": classify_role(path),
                })
    with HITS_PATH.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["claim_key", "path", "matched_tokens", "role"])
        writer.writeheader()
        writer.writerows(rows)
    return rows


def exists(rel: str) -> bool:
    return (ROOT / rel).exists()


def lineage_rows() -> list[dict[str, str]]:
    rows = [
        {
            "claim_id": "CLINT0X_RETAINED_BEST",
            "manuscript_value": "ClinTox ROC-AUC 0.9496",
            "source_file": "reports/manuscript_tables/table29_nature_multimethod_fusion_retained_best.csv",
            "generator_script": "scripts/run_nature_multimethod_fusion_appendix.py",
            "experiment_status": "completed" if exists("reports/manuscript_tables/table29_nature_multimethod_fusion_retained_best.csv") else "not_found",
            "notes": "Structured retained-best table exists; future manuscript update must recompute rather than copy prose.",
        },
        {
            "claim_id": "FREESOLV_RETAINED_BEST",
            "manuscript_value": "FreeSolv RMSE 1.0286",
            "source_file": "reports/manuscript_tables/table27_moleculenet_targeted_rebuild_retained_best.csv",
            "generator_script": "scripts/run_moleculenet_targeted_rebuilds.py",
            "experiment_status": "completed" if exists("reports/manuscript_tables/table27_moleculenet_targeted_rebuild_retained_best.csv") else "not_found",
            "notes": "Structured retained-best table exists; heterogeneous nested confirmation is still absent.",
        },
        {
            "claim_id": "TDC_GATE_5_17",
            "manuscript_value": "5 promoted / 17 retained (historically written 5/17/0)",
            "source_file": "reports/manuscript_tables/table15_tdc_performance_mode_retained_best.csv",
            "generator_script": "scripts/build_tdc_performance_mode_combined_retained_best.py",
            "experiment_status": "completed" if exists("reports/tdc_performance_mode_appendix_combined/selected_metrics_summary.csv") else "not_found",
            "notes": "Promotion counts exist, but the required gate confusion audit and rejected-candidate outcome table are not yet present.",
        },
        {
            "claim_id": "NESTED_TOP3_K32",
            "manuscript_value": "K=32 prospective Top-3 hit 0.222222...",
            "source_file": "reports/draft10_core_experiments_20260621/expanded_nested/policy_summary.csv",
            "generator_script": "scripts/run_expanded_nested_candidate_pool_20260621.py; scripts/generate_draft10_core_figure_20260621.py",
            "experiment_status": "completed" if exists("reports/draft10_core_experiments_20260621/expanded_nested/policy_summary.csv") else "not_found",
            "notes": "Fixed-order 3x3 evidence exists; chance correction, randomized order/subsets and repeated nested validation remain absent.",
        },
        {
            "claim_id": "AUTOGLUON_30S",
            "manuscript_value": "AutoGluon 30 s: endpoint comparison 7/0/2",
            "source_file": "reports/draft10_core_experiments_20260621/autogluon_nested/summary.csv",
            "generator_script": "scripts/run_autogluon_nested_wsl_20260621.py",
            "experiment_status": "partial",
            "notes": "Only the 30 s budget is documented; required 300 s and 1800 s budgets are not found.",
        },
        {
            "claim_id": "HETEROGENEOUS_NESTED_POOL",
            "manuscript_value": "Cross-family confirmation of candidate-pool governance",
            "source_file": "",
            "generator_script": "",
            "experiment_status": "not_found",
            "notes": "Historical heavy-model predictions exist, but no same-outer-split 8-12 candidate heterogeneous nested confirmation was located.",
        },
        {
            "claim_id": "OPEN_REPRODUCIBILITY",
            "manuscript_value": "License, locked environment, CI, cold start, release and Zenodo DOI",
            "source_file": "",
            "generator_script": "",
            "experiment_status": "not_found",
            "notes": "No project LICENSE, lock file, Dockerfile, CI workflow, cold-start log or Zenodo DOI was located in the primary project scope.",
        },
    ]
    with LINEAGE_PATH.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def command_output(command: list[str]) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
        return (result.stdout or result.stderr).strip()
    except (OSError, subprocess.SubprocessError):
        return "unavailable"


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not_installed"


def write_machine_inventory() -> dict[str, object]:
    memory_bytes = None
    try:
        import psutil

        memory_bytes = psutil.virtual_memory().total
    except ImportError:
        pass
    packages = {
        name: package_version(name)
        for name in ["numpy", "pandas", "scikit-learn", "scipy", "rdkit", "torch", "python-docx", "matplotlib", "autogluon"]
    }
    inventory = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "hostname": platform.node(),
        "processor": platform.processor(),
        "logical_cpu_count": os.cpu_count(),
        "memory_bytes": memory_bytes,
        "python_executable": sys.executable,
        "python_version": sys.version,
        "packages": packages,
        "gpu_inventory": command_output(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"]),
        "git_version": command_output(["git", "--version"]),
        "git_status": command_output(["git", "-C", str(ROOT), "status", "--short", "--branch"]),
        "git_metadata_valid": (ROOT / ".git" / "HEAD").exists(),
    }
    MACHINE_PATH.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    return inventory


def directory_stats(path: Path) -> tuple[int, int]:
    count = 0
    size = 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                count += 1
                size += item.stat().st_size
        except OSError:
            continue
    return count, size


def write_report(
    inventory: list[dict[str, object]],
    hits: list[dict[str, str]],
    lineage: list[dict[str, str]],
    machine: dict[str, object],
) -> None:
    ext_counts = Counter(str(row["extension"]) for row in inventory if row["scope"] == "project_evidence")
    role_counts = Counter(str(row["role"]) for row in inventory if row["scope"] == "project_evidence")
    status_counts = Counter(row["experiment_status"] for row in lineage)
    excluded = []
    for name in sorted(EXCLUDED_TOP_LEVEL):
        path = ROOT / name
        if path.exists():
            count, size = directory_stats(path)
            excluded.append((name, count, size))

    external_hashes = {
        Path(str(row["path"])).name: row["sha256"]
        for row in inventory if row["scope"] == "external_input"
    }
    root_draft = ROOT / "output" / "初稿-10.docx"
    desktop_draft = EXTERNAL_INPUTS[1]
    draft_comparison = "unavailable"
    if root_draft.exists() and desktop_draft.exists():
        draft_comparison = "identical" if sha256(root_draft) == sha256(desktop_draft) else "different"

    lines = [
        "# FZYC-Mol repository audit",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Audit boundary",
        "",
        "This is the required Stage A read-only evidence audit. Existing code, data and results were not deleted, renamed or overwritten. The only new artifacts are this report, the inventory/lineage CSV files, `machine_inventory.json`, and the audit script itself.",
        "",
        f"- Primary root: `{ROOT}`",
        f"- Evidence files inventoried and SHA-256 hashed: {sum(1 for row in inventory if row['scope'] == 'project_evidence')}",
        f"- External input files hashed: {sum(1 for row in inventory if row['scope'] == 'external_input')}",
        f"- Desktop manuscript versus `output/初稿-10.docx`: **{draft_comparison}**",
        f"- Git metadata: **{'valid' if machine['git_metadata_valid'] else 'invalid/empty'}**; no commit hash can currently be trusted.",
        "",
        "Tool/vendor trees were measured but excluded from the primary research-evidence inventory to avoid treating environments, skills and external repositories as FZYC-Mol evidence:",
        "",
        "| Directory | Files | Size (GiB) |",
        "|---|---:|---:|",
    ]
    lines.extend(f"| `{name}` | {count} | {size / 1024**3:.3f} |" for name, count, size in excluded)
    lines.extend([
        "",
        "## Inventory summary",
        "",
        "| Extension | Count |",
        "|---|---:|",
    ])
    lines.extend(f"| `{ext}` | {count} |" for ext, count in sorted(ext_counts.items()))
    lines.extend([
        "",
        "| Role | Count |",
        "|---|---:|",
    ])
    lines.extend(f"| {role} | {count} |" for role, count in sorted(role_counts.items()))
    lines.extend([
        "",
        "Detailed inventory: `results/audits/file_inventory.csv`.",
        "",
        "## Result lineage and experiment status",
        "",
        "| Claim | Status | Structured source | Generator | Audit conclusion |",
        "|---|---|---|---|---|",
    ])
    for row in lineage:
        lines.append(
            f"| {row['manuscript_value']} | {row['experiment_status']} | `{row['source_file'] or 'not found'}` | "
            f"`{row['generator_script'] or 'not found'}` | {row['notes']} |"
        )
    lines.extend([
        "",
        f"Status totals: {dict(status_counts)}. Full mapping: `results/audits/result_lineage.csv`.",
        "",
        "## Key findings",
        "",
        "1. The fixed-order 32-candidate, nine-endpoint 3×3 nested experiment and its K=32 Top-3 value are backed by structured outputs and generation scripts.",
        "2. The required chance-adjusted ranking metrics, full-32 fixed-denominator regret, random-order/random-subset/family-balanced audits, and five repeated 3×3 nested validation were not found as completed artifacts.",
        "3. AutoGluon 30-second evidence is present, but the required 300- and 1800-second budgets are absent.",
        "4. Historical graph/pretrained/fusion outputs exist, but a same-split heterogeneous 8–12-candidate nested confirmation was not located; the generality claim must remain restricted until this is run.",
        "5. The historical `5/17/0` TDC wording is traceable to retained-best summaries, but it is not yet a genuine gate confusion audit. It must later become `5 promoted / 17 retained` with outcomes for rejected candidates.",
        "6. No project release gate is complete: LICENSE, environment lock, Dockerfile, CI, cold-start log, SHA256SUMS/reproducibility manifest and Zenodo DOI are absent from the primary project scope.",
        f"7. The desktop manuscript and repository `output/初稿-10.docx` are {draft_comparison}; the desktop path named by the user remains the authoritative manuscript input for the eventual `初稿-11.docx`.",
        "",
        "## Conflicts and unverified boundaries",
        "",
        "- The repository contains many dated scripts and repeated manuscript/result exports. Identical metric text alone is not sufficient to deduplicate runs; prediction/config/split/seed/code hashes are not consistently available in historical outputs.",
        "- `.git` exists but contains no usable `HEAD`; historical `code_commit` provenance is currently unavailable.",
        "- Current manuscript claims can often be traced to summary CSVs, but there is no single frozen `manuscript_values.json` and no zero-difference verifier for all main-text numbers.",
        "- Independent temporal ADMET blind testing, full heavy-model outer retraining, third-party cold start and permanent archival were already acknowledged as incomplete and remain incomplete.",
        "",
        "## Resource and implementation gap",
        "",
        "The machine has sufficient local Python tooling for audit and lightweight CPU experiments. AutoGluon is isolated in `.venv-autogluon`; GPU availability is recorded in `machine_inventory.json`. Heavy heterogeneous retraining and 200× subset audits may require staged execution, but no missing result has been simulated.",
        "",
        "## Stage A gate decision",
        "",
        "**Stage A: partial, ready for user review.** Core historical claims have traceable sources, but several task-book deliverables are absent and some claims remain limited. Per the task book, no Stage B–G code, experiment or manuscript modification should begin until this audit is confirmed.",
        "",
        "## Generated artifacts",
        "",
        "- `docs/repository_audit.md`",
        "- `results/audits/file_inventory.csv`",
        "- `results/audits/result_lineage.csv`",
        "- `results/audits/key_number_hits.csv`",
        "- `machine_inventory.json`",
        "- `scripts/audit_repository.py`",
        "",
        f"Key-number hit rows: {len(hits)}. External hashes: {json.dumps(external_hashes, ensure_ascii=False)}.",
    ])
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    paths = iter_evidence_files()
    print(f"inventory candidates: {len(paths)}", flush=True)
    inventory = write_inventory(paths)
    hits = collect_key_hits(paths)
    lineage = lineage_rows()
    machine = write_machine_inventory()
    write_report(inventory, hits, lineage, machine)
    print(f"wrote {REPORT_PATH}")
    print(f"wrote {INVENTORY_PATH}")
    print(f"wrote {LINEAGE_PATH}")
    print(f"wrote {HITS_PATH}")
    print(f"wrote {MACHINE_PATH}")


if __name__ == "__main__":
    main()
