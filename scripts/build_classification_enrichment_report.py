from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import DATASETS
from fzyc_mol.evaluate import compute_metrics


DATASET_NAMES = sorted(DATASETS, key=len, reverse=True)


def parse_prediction_path(path: Path) -> tuple[str, str, int] | None:
    selector = re.match(r"(.+)_validation_selector_seed(\d+)_predictions\.csv$", path.name)
    if selector:
        return selector.group(1), "validation_selector", int(selector.group(2))
    for dataset in DATASET_NAMES:
        prefix = f"{dataset}_"
        if not path.name.startswith(prefix):
            continue
        rest = path.name[len(prefix) :]
        match = re.match(r"(.+)_seed(\d+)_predictions\.csv$", rest)
        if match:
            return dataset, match.group(1), int(match.group(2))
    return None


def normalized_prob(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64).reshape(-1)
    if np.nanmin(values) >= 0.0 and np.nanmax(values) <= 1.0:
        return np.clip(values, 1e-7, 1.0 - 1e-7)
    return 1.0 / (1.0 + np.exp(-np.clip(values, -60.0, 60.0)))


def process_file(path: Path, source: str) -> list[dict]:
    parsed = parse_prediction_path(path)
    if parsed is None:
        return []
    dataset, parsed_model, seed = parsed
    table = pd.read_csv(path)
    if "y_true" not in table:
        return []
    y_true = pd.to_numeric(table["y_true"], errors="coerce").to_numpy()
    mask = np.isfinite(y_true)
    y_true = y_true[mask].astype(int)
    if len(y_true) == 0 or not set(np.unique(y_true)).issubset({0, 1}) or len(np.unique(y_true)) < 2:
        return []
    pred_cols = ["y_pred"] if "y_pred" in table else []
    pred_cols += [col for col in table.columns if col.startswith("pred_")]
    rows = []
    for col in dict.fromkeys(pred_cols):
        scores = pd.to_numeric(table[col], errors="coerce").to_numpy()[mask]
        finite = np.isfinite(scores)
        if finite.sum() < 2:
            continue
        y = y_true[finite]
        p = normalized_prob(scores[finite])
        if len(np.unique(y)) < 2:
            continue
        model = parsed_model if col == "y_pred" else col.removeprefix("pred_")
        rows.append(
            {
                "source": source,
                "dataset": dataset,
                "model": model,
                "seed": seed,
                "n": len(y),
                "positives": int(y.sum()),
                **compute_metrics("classification", y, p),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute EF/BEDROC/top-k recall for classification predictions.")
    parser.add_argument(
        "--prediction-dirs",
        nargs="*",
        default=[
            str(ROOT / "reports" / "validation_selector_expanded"),
            str(ROOT / "reports" / "validation_selector_tdc_admet"),
            str(ROOT / "reports" / "strict_core_fast"),
            str(ROOT / "reports" / "strict_multifp_fast"),
            str(ROOT / "reports" / "chemprop_baseline"),
            str(ROOT / "reports" / "descriptor_motif_baselines"),
        ],
    )
    parser.add_argument("--output-dir", default=str(ROOT / "reports" / "classification_enrichment"))
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for directory in args.prediction_dirs:
        pred_dir = Path(directory)
        if not pred_dir.exists():
            continue
        for path in pred_dir.glob("*_predictions.csv"):
            rows.extend(process_file(path, pred_dir.name))
    raw = pd.DataFrame(rows)
    raw.to_csv(output_dir / "classification_enrichment_raw.csv", index=False)
    if not raw.empty:
        metric_cols = [
            col
            for col in raw.columns
            if col not in {"source", "dataset", "model", "seed"}
            and pd.api.types.is_numeric_dtype(raw[col])
        ]
        summary = (
            raw.groupby(["source", "dataset", "model"], dropna=False)[metric_cols]
            .agg(["mean", "std"])
            .reset_index()
        )
        summary.to_csv(output_dir / "classification_enrichment_summary.csv", index=False)
    print(raw.tail(40).to_string(index=False) if not raw.empty else "No classification predictions found.")


if __name__ == "__main__":
    main()
