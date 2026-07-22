from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class ExperimentConfig:
    root: Path
    raw: dict[str, Any]

    @property
    def seeds(self) -> list[int]:
        return [int(v) for v in self.raw.get("seeds", [13, 17, 23, 29, 31])]

    @property
    def data_dir(self) -> Path:
        return self.root / str(self.raw.get("data_dir", "data"))

    @property
    def reports_dir(self) -> Path:
        return self.root / str(self.raw.get("reports_dir", "reports/experiment_update"))

    @property
    def manuscript_tables_dir(self) -> Path:
        return self.root / str(
            self.raw.get("manuscript_tables_dir", "reports/manuscript_tables/experiment_update")
        )

    def datasets(self, group: str) -> list[str]:
        return list(self.raw.get("datasets", {}).get(group, []))

    def ensure_dirs(self) -> None:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.manuscript_tables_dir.mkdir(parents=True, exist_ok=True)


def load_config(path: str | Path, root: str | Path | None = None) -> ExperimentConfig:
    config_path = Path(path)
    text = config_path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        raw = yaml.safe_load(text)
    except Exception:
        raw = json.loads(text)
    project_root = Path(root) if root is not None else config_path.resolve().parents[1]
    return ExperimentConfig(root=project_root.resolve(), raw=raw)


def write_csv(frame: pd.DataFrame, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out, index=False)
    return out


def append_missing_report(rows: list[dict[str, object]], path: str | Path) -> None:
    if not rows:
        return
    frame = pd.DataFrame(rows)
    write_csv(frame, path)


def output_manifest(paths: list[Path], path: str | Path) -> Path:
    rows = [{"artifact": str(p), "exists": p.exists(), "size_bytes": p.stat().st_size if p.exists() else 0} for p in paths]
    return write_csv(pd.DataFrame(rows), path)
