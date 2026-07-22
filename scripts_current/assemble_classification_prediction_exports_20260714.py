from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pandas as pd


ROOT = Path("D:/fzyc")
INPUT = Path(
    os.environ.get(
        "FZYC_CLASS_PRED_BASE",
        ROOT / "results" / "classification_predictions_20260714" / "prefix32",
    )
)
OUTPUT = Path(
    os.environ.get(
        "FZYC_CLASS_EXPORT_OUT",
        ROOT / "output" / "paper24_final_minor_revision_20260714" / "experiment_exports",
    )
)
LOCKED = Path(
    os.environ.get(
        "FZYC_LOCKED_CLASS_BASE",
        ROOT / "results" / "nested_selection" / "repeated_nested",
    )
)
SEEDS = (11, 23, 37, 53, 71)
TASKS = ("bbbp", "bace", "clintox", "tdc_hia_hou", "tdc_pgp_broccatelli")
KEY_COLUMNS = ["dataset", "seed", "candidate", "sample_index"]
REQUIRED_COLUMNS = {
    "dataset",
    "task_type",
    "seed",
    "outer_fold",
    "outer_split_hash",
    "candidate_order",
    "candidate",
    "sample_index",
    "smiles",
    "scaffold",
    "y_true",
    "y_pred",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def compare_metric_frames(
    locked: pd.DataFrame,
    rerun: pd.DataFrame,
    keys: list[str],
    numeric_columns: list[str],
) -> dict[str, object]:
    locked_sorted = locked.sort_values(keys, kind="stable").reset_index(drop=True)
    rerun_sorted = rerun.sort_values(keys, kind="stable").reset_index(drop=True)
    rows_equal = len(locked_sorted) == len(rerun_sorted)
    keys_equal = rows_equal and locked_sorted[keys].equals(rerun_sorted[keys])
    if not keys_equal:
        max_difference = float("nan")
    else:
        differences = []
        for column in numeric_columns:
            left = pd.to_numeric(locked_sorted[column], errors="coerce")
            right = pd.to_numeric(rerun_sorted[column], errors="coerce")
            differences.append(float((left - right).abs().fillna(0.0).max()))
        max_difference = round(max(differences, default=0.0), 15)
    return {
        "rows_equal": rows_equal,
        "keys_equal": keys_equal,
        "max_absolute_difference": max_difference,
    }


def validate_task_export(task_dir: Path, expected_seed: int) -> tuple[pd.DataFrame, dict[str, object]]:
    marker_path = task_dir / "complete.json"
    prediction_path = task_dir / "outer_predictions.csv.gz"
    if not marker_path.exists() or not prediction_path.exists():
        raise FileNotFoundError(f"Incomplete prediction export: {task_dir}")
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    frame = pd.read_csv(prediction_path)
    missing_columns = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing_columns:
        raise ValueError(f"Missing prediction columns in {prediction_path}: {missing_columns}")
    expected_rows = int(marker["n"]) * int(marker["candidate_count"])
    duplicate_keys = int(frame.duplicated(KEY_COLUMNS).sum())
    checks = {
        "row_count": len(frame) == expected_rows,
        "task": set(frame["dataset"].astype(str)) == {str(marker["dataset"])},
        "task_type": set(frame["task_type"].astype(str)) == {"classification"},
        "seed": set(frame["seed"].astype(int)) == {int(expected_seed)},
        "outer_folds": frame["outer_fold"].nunique() == int(marker["outer_folds"]),
        "candidates": frame["candidate"].nunique() == int(marker["candidate_count"]),
        "samples": frame["sample_index"].nunique() == int(marker["n"]),
        "unique_prediction_keys": duplicate_keys == 0,
        "binary_truth": set(frame["y_true"].dropna().astype(float).unique()).issubset({0.0, 1.0}),
        "probability_range": bool(frame["y_pred"].between(0.0, 1.0, inclusive="both").all()),
        "split_hashes_present": bool(frame["outer_split_hash"].notna().all()),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError(f"Prediction export validation failed for {task_dir}: {failed}")
    audit = {
        "task": marker["dataset"],
        "seed": int(expected_seed),
        "n_samples": int(marker["n"]),
        "candidate_count": int(marker["candidate_count"]),
        "outer_folds": int(marker["outer_folds"]),
        "prediction_rows": len(frame),
        "expected_rows": expected_rows,
        "duplicate_prediction_keys": duplicate_keys,
        "source_file": str(prediction_path),
        "source_sha256": sha256(prediction_path),
        "status": "complete",
    }
    return frame, audit


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    audits: list[dict[str, object]] = []
    drift_rows: list[dict[str, object]] = []
    export_files: list[Path] = []
    for seed in SEEDS:
        frames: list[pd.DataFrame] = []
        for task in TASKS:
            rerun_task = INPUT / f"seed_{seed}" / "tasks" / task
            locked_task = LOCKED / f"seed_{seed}" / "tasks" / task
            frame, audit = validate_task_export(rerun_task, seed)
            frames.append(frame)
            audits.append(audit)
            comparisons = (
                (
                    "inner_scores.csv",
                    ["dataset", "outer_fold", "inner_fold", "candidate"],
                    ["inner_utility"],
                ),
                (
                    "outer_candidate_scores.csv",
                    ["dataset", "outer_fold", "candidate"],
                    ["outer_utility", "roc_auc", "pr_auc", "brier"],
                ),
                (
                    "policy_detail.csv",
                    ["dataset", "outer_fold", "pool_size", "policy"],
                    ["outer_utility", "test_regret", "normalized_test_regret", "top3_hit"],
                ),
            )
            for filename, keys, numeric_columns in comparisons:
                locked_frame = pd.read_csv(locked_task / filename)
                rerun_frame = pd.read_csv(rerun_task / filename)
                comparison = compare_metric_frames(locked_frame, rerun_frame, keys, numeric_columns)
                selection_changes = 0
                if filename == "policy_detail.csv" and comparison["keys_equal"]:
                    locked_ordered = locked_frame.sort_values(keys, kind="stable").reset_index(drop=True)
                    rerun_ordered = rerun_frame.sort_values(keys, kind="stable").reset_index(drop=True)
                    selection_changes = int(
                        locked_ordered["selected_candidate"].astype(str).ne(
                            rerun_ordered["selected_candidate"].astype(str)
                        ).sum()
                    )
                drift_rows.append(
                    {
                        "task": task,
                        "seed": seed,
                        "file": filename,
                        **comparison,
                        "selected_candidate_changes": selection_changes,
                        "locked_metrics_replaced": False,
                    }
                )
        combined = pd.concat(frames, ignore_index=True)
        export = OUTPUT / f"classification_outer_predictions_seed_{seed}.csv.gz"
        combined.to_csv(export, index=False, compression="gzip")
        export_files.append(export)

    verification = pd.DataFrame(audits)
    verification_path = OUTPUT / "classification_prediction_export_verification.csv"
    verification.to_csv(verification_path, index=False, encoding="utf-8-sig")
    drift = pd.DataFrame(drift_rows)
    drift_path = OUTPUT / "classification_refit_drift_verification.csv"
    drift.to_csv(drift_path, index=False, encoding="utf-8-sig")
    outer_drift = drift.loc[drift["file"].eq("outer_candidate_scores.csv"), "max_absolute_difference"]
    audit = {
        "status": "complete",
        "scope": "five classification endpoints, five seeded scaffold partitions, 32 registered candidates",
        "seeds": list(SEEDS),
        "tasks": list(TASKS),
        "task_seed_units": len(verification),
        "prediction_rows": int(verification["prediction_rows"].sum()),
        "duplicate_prediction_keys": int(verification["duplicate_prediction_keys"].sum()),
        "all_unit_checks_complete": bool(verification["status"].eq("complete").all()),
        "locked_primary_metrics_replaced": False,
        "metric_refit_drift_detected": bool(drift["max_absolute_difference"].fillna(0.0).gt(0.0).any()),
        "maximum_outer_candidate_metric_refit_difference": float(outer_drift.max()),
        "selected_candidate_changes": int(drift["selected_candidate_changes"].sum()),
        "prediction_export_use": "post-hoc traceability export only; locked primary metrics remain the source of record",
        "exports": [
            {"file": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in export_files
        ],
        "verification_file": verification_path.name,
        "verification_sha256": sha256(verification_path),
        "refit_drift_file": drift_path.name,
        "refit_drift_sha256": sha256(drift_path),
    }
    audit_path = OUTPUT / "classification_prediction_export_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), **audit}, indent=2))


if __name__ == "__main__":
    main()
