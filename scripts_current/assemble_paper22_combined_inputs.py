from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd


ROOT = Path("D:/fzyc")
SEEDS = [11, 23, 37, 53, 71]
CLASS_TASKS = ["bbbp", "bace", "clintox", "tdc_hia_hou", "tdc_pgp_broccatelli"]
REG_TASKS = ["esol", "freesolv", "lipo", "tdc_caco2_wang"]
OLD_PREFIX = ROOT / "results" / "nested_selection" / "repeated_nested"
NEW_PREFIX = ROOT / "results" / "regression_seeded_scaffold_20260713" / "prefix32"
OLD_MULTI = ROOT / "results" / "reviewer_core_20260624" / "multiview_nested"
NEW_MULTI = ROOT / "results" / "regression_seeded_scaffold_20260713" / "multiview12"
COMBINED = ROOT / "results" / "paper22_combined_nested_20260713"
PREFIX_OUT = COMBINED / "prefix32"
MULTI_OUT = COMBINED / "multiview12"


def classification_rows(path: Path, task_column: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    return frame.loc[frame[task_column].isin(CLASS_TASKS)].copy()


def merge_prefix() -> None:
    names = ["candidate_registry.csv", "inner_scores.csv", "outer_candidate_scores.csv", "policy_detail.csv"]
    all_splits = []
    all_predictions = []
    for seed in SEEDS:
        destination = PREFIX_OUT / f"seed_{seed}"
        destination.mkdir(parents=True, exist_ok=True)
        source_new = NEW_PREFIX / f"seed_{seed}"
        if not (source_new / "run_manifest.json").exists():
            raise FileNotFoundError(source_new / "run_manifest.json")
        for name in names:
            old = classification_rows(OLD_PREFIX / f"seed_{seed}" / name, "dataset")
            new = pd.read_csv(source_new / name)
            pd.concat([old, new], ignore_index=True, sort=False).to_csv(destination / name, index=False)
        split = pd.read_csv(source_new / "split_manifest.csv")
        all_splits.append(split)
        prediction = pd.read_csv(source_new / "outer_predictions.csv.gz")
        all_predictions.append(prediction)
        prediction.to_csv(destination / "outer_predictions_regression.csv.gz", index=False, compression="gzip")
        split.to_csv(destination / "split_manifest_regression.csv", index=False)
        manifest = json.loads((source_new / "run_manifest.json").read_text(encoding="utf-8"))
        manifest.update(
            {
                "tasks": CLASS_TASKS + REG_TASKS,
                "classification_source": str(OLD_PREFIX / f"seed_{seed}"),
                "regression_source": str(source_new),
                "split_status": "five distinct seeded scaffold partitions for both classification and regression endpoints",
            }
        )
        (destination / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    PREFIX_OUT.mkdir(parents=True, exist_ok=True)
    pd.concat(all_splits, ignore_index=True).to_csv(PREFIX_OUT / "regression_split_manifest.csv", index=False)
    pd.concat(all_predictions, ignore_index=True).to_csv(
        PREFIX_OUT / "regression_outer_predictions_all_candidates.csv.gz", index=False, compression="gzip"
    )


def merge_multiview() -> None:
    names = [
        "candidate_registry.csv",
        "inner_scores.csv",
        "outer_candidate_scores.csv",
        "policy_detail.csv",
        "ranking_metrics.csv",
    ]
    MULTI_OUT.mkdir(parents=True, exist_ok=True)
    for name in names:
        old = classification_rows(OLD_MULTI / name, "task")
        new = pd.read_csv(NEW_MULTI / name)
        pd.concat([old, new], ignore_index=True, sort=False).to_csv(MULTI_OUT / name, index=False)
    shutil.copy2(NEW_MULTI / "split_manifest.csv", MULTI_OUT / "regression_split_manifest.csv")
    shutil.copy2(NEW_MULTI / "outer_predictions.csv.gz", MULTI_OUT / "regression_outer_predictions_all_candidates.csv.gz")
    manifest = json.loads((NEW_MULTI / "run_manifest.json").read_text(encoding="utf-8"))
    manifest.update(
        {
            "tasks": CLASS_TASKS + REG_TASKS,
            "classification_source": str(OLD_MULTI),
            "regression_source": str(NEW_MULTI),
            "split_status": "five distinct seeded scaffold partitions for both classification and regression endpoints",
        }
    )
    (MULTI_OUT / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> None:
    merge_prefix()
    merge_multiview()
    print(COMBINED)


if __name__ == "__main__":
    main()
