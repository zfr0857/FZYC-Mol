from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "reports"

CONFIGS = [
    ROOT / "configs" / "full_moleculenet.json",
    ROOT / "configs" / "strict_core_experts.json",
    ROOT / "configs" / "strict_core_fast.json",
    ROOT / "configs" / "strict_multifp_fast.json",
    ROOT / "configs" / "strict_tdc_admet_multifp.json",
]


def audit_config(path: Path) -> dict[str, object]:
    config = json.loads(path.read_text(encoding="utf-8"))
    output_dir = ROOT / config["output_dir"]
    metrics_path = output_dir / "metrics_raw.csv"
    expected = {
        (dataset, model, int(seed))
        for dataset in config["datasets"]
        for model in config["models"]
        for seed in config["seeds"]
    }
    actual: set[tuple[str, str, int]] = set()
    if metrics_path.exists():
        frame = pd.read_csv(metrics_path)
        if {"dataset", "model", "seed"}.issubset(frame.columns):
            actual = {
                (str(row.dataset), str(row.model), int(row.seed))
                for row in frame.itertuples(index=False)
            }
    missing = expected - actual
    return {
        "config": str(path.relative_to(ROOT)),
        "output_dir": config["output_dir"],
        "metrics_exists": metrics_path.exists(),
        "expected_runs": len(expected),
        "completed_runs": len(actual & expected),
        "missing_runs": len(missing),
        "status": "complete" if len(missing) == 0 else "incomplete",
        "missing_preview": "; ".join(f"{d}/{m}/seed{s}" for d, m, s in sorted(missing)[:12]),
    }


def audit_partial_directory() -> dict[str, object]:
    partial = ROOT / "reports" / "full_moleculenet_batchnorm_partial_20260524_134248"
    metrics = partial / "metrics_raw.csv"
    row_count = len(pd.read_csv(metrics)) if metrics.exists() else 0
    return {
        "config": "legacy partial run",
        "output_dir": str(partial.relative_to(ROOT)),
        "metrics_exists": metrics.exists(),
        "expected_runs": "",
        "completed_runs": row_count,
        "missing_runs": "",
        "status": "superseded",
        "missing_preview": "Stopped by old BatchNorm singleton-batch error; superseded by reports/full_moleculenet after LayerNorm fix.",
    }


def write_readme(audit: pd.DataFrame) -> None:
    lines = [
        "# Experiment completion audit",
        "",
        "This audit checks major config-driven experiment reports against their planned dataset/model/seed grids.",
        "",
        audit.to_markdown(index=False),
        "",
        "Interpretation:",
        "",
        "- `complete`: planned grid is present in `metrics_raw.csv`.",
        "- `superseded`: a legacy partial run exists but has been replaced by a later completed report.",
        "- If an incomplete row appears, rerun `py scripts\\run_experiment.py --config <config>`; config-level resume will skip finished runs.",
        "",
    ]
    (OUT_DIR / "experiment_completion_audit_20260529.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    rows = [audit_config(path) for path in CONFIGS]
    rows.append(audit_partial_directory())
    audit = pd.DataFrame(rows)
    audit.to_csv(OUT_DIR / "experiment_completion_audit_20260529.csv", index=False)
    write_readme(audit)
    print(audit.to_string(index=False))


if __name__ == "__main__":
    main()
