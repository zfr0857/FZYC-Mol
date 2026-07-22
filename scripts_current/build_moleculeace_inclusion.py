from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from datasets import get_dataset_config_names, load_dataset


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fzyc_mol.benchmarks.moleculeace import summarize_moleculeace_task  # noqa: E402


def main() -> None:
    rows = []
    for task in get_dataset_config_names("karina-zadorozhny/moleculeace"):
        try:
            dataset = load_dataset("karina-zadorozhny/moleculeace", task)
            rows.append(summarize_moleculeace_task(task, dataset["train"].to_pandas(), dataset["test"].to_pandas()))
        except Exception as exc:
            rows.append(
                {
                    "task": task,
                    "status": "failed",
                    "exclusion_reason": f"{type(exc).__name__}: {exc}",
                    "n_train": 0,
                    "n_train_unique_molecules": 0,
                    "n_test": 0,
                    "n_test_unique_molecules": 0,
                    "n_cliff_molecules": 0,
                    "n_cliff_train": 0,
                    "n_cliff_test": 0,
                }
            )
    output = ROOT / "results" / "external_panels" / "moleculeace_inclusion.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output, index=False)
    print(output)


if __name__ == "__main__":
    main()
