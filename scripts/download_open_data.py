from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import DATASETS, available_datasets


def download(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        print(f"exists {path}")
        return
    print(f"download {url}")
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read()
    path.write_bytes(data)
    print(f"wrote {path} ({path.stat().st_size} bytes)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download public molecular benchmark datasets.")
    parser.add_argument("--dataset", default="all", help=f"One of: all, {', '.join(available_datasets())}")
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    args = parser.parse_args()

    names = available_datasets() if args.dataset == "all" else [args.dataset]
    unknown = [name for name in names if name not in DATASETS]
    if unknown:
        raise SystemExit(f"Unknown dataset(s): {unknown}. Available: {available_datasets()}")

    data_dir = Path(args.data_dir)
    for name in names:
        spec = DATASETS[name]
        download(spec.url, data_dir / "raw" / spec.filename)

    registry = {
        name: {
            "url": spec.url,
            "filename": spec.filename,
            "task_type": spec.task_type,
            "smiles_candidates": spec.smiles_candidates,
            "target_candidates": spec.target_candidates,
        }
        for name, spec in DATASETS.items()
    }
    (data_dir / "dataset_registry.json").write_text(json.dumps(registry, indent=2), encoding="utf-8")
    print(f"registry {data_dir / 'dataset_registry.json'}")


if __name__ == "__main__":
    main()
