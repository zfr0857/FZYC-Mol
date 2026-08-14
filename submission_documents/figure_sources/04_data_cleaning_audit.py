from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fzyc_mol.data.run_identity import build_run_id  # noqa: E402
from fzyc_mol.data.standardize import audit_cleaning_frame  # noqa: E402
from fzyc_mol.datasets import DATASETS, _first_existing, load_raw_dataset  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_outputs(root: Path = ROOT) -> dict[str, Path]:
    output = root / "results" / "audits"
    output.mkdir(parents=True, exist_ok=True)
    config_path = root / "configs" / "data_cleaning.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    code_path = root / "src" / "fzyc_mol" / "data" / "standardize.py"
    code_hash = _sha256(code_path)
    summary_rows: list[dict[str, object]] = []
    event_frames: list[pd.DataFrame] = []

    for endpoint, spec in DATASETS.items():
        raw = load_raw_dataset(endpoint, root / "data")
        smiles_col = _first_existing(raw.columns, spec.smiles_candidates, "SMILES")
        target_col = _first_existing(raw.columns, spec.target_candidates, "target")
        _, events, summary = audit_cleaning_frame(
            raw,
            smiles_col=smiles_col,
            target_col=target_col,
            task_type=spec.task_type,
        )
        data_hash = str(summary["data_hash"])
        run_id = build_run_id(
            config={"endpoint": endpoint, "task_type": spec.task_type, **config},
            data_hash=data_hash,
            split_hash="not_applicable_pre_split_cleaning",
            seed=0,
            code_hash=code_hash,
            prediction_hash="not_applicable_pre_modeling",
        )
        summary_rows.append(
            {
                "endpoint": endpoint,
                "task_type": spec.task_type,
                "raw_file": str((root / "data" / "raw" / spec.filename).relative_to(root)),
                **summary,
                "run_id": run_id,
                "duplicate_group_id": data_hash,
                "identity_status": "verified_cleaning_run",
            }
        )
        removed_or_merged = events.loc[events["action"] != "retained"].copy()
        removed_or_merged.insert(0, "endpoint", endpoint)
        event_frames.append(removed_or_merged)

    summary_frame = pd.DataFrame(summary_rows)
    group_sizes = summary_frame.groupby("duplicate_group_id")["run_id"].transform("size")
    summary_frame["duplicate_group_size"] = group_sizes.astype(int)
    events_frame = pd.concat(event_frames, ignore_index=True) if event_frames else pd.DataFrame()
    paths = {
        "summary": output / "data_cleaning_flow.csv",
        "events": output / "data_cleaning_events.csv",
        "identity": output / "run_identity_groups.csv",
    }
    summary_frame.to_csv(paths["summary"], index=False)
    events_frame.to_csv(paths["events"], index=False)
    summary_frame[
        ["endpoint", "run_id", "duplicate_group_id", "duplicate_group_size", "identity_status", "data_hash"]
    ].to_csv(paths["identity"], index=False)
    return paths


def main() -> None:
    for name, path in build_outputs().items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
