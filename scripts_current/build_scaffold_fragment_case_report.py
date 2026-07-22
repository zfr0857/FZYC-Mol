from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from rdkit.Chem import BRICS

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import load_dataset
from fzyc_mol.features import mol_from_smiles, scaffold_from_smiles


def brics_tokens(smiles: str) -> list[str]:
    mol = mol_from_smiles(smiles)
    if mol is None:
        return []
    try:
        return sorted(BRICS.BRICSDecompose(mol))
    except Exception:
        return []


def infer_task_type(y: pd.Series) -> str:
    values = set(pd.unique(y.dropna()))
    return "classification" if values.issubset({0, 1}) else "regression"


def summarize_group(dataset: str, name: str, kind: str, values: list[float], baseline: float, task_type: str) -> dict:
    arr = np.asarray(values, dtype=float)
    row = {
        "dataset": dataset,
        "kind": kind,
        "feature": name,
        "n": int(len(arr)),
        "mean_y": float(np.mean(arr)),
        "baseline_mean_y": baseline,
        "delta_mean_y": float(np.mean(arr) - baseline),
    }
    if task_type == "classification":
        row["positive_rate"] = float(np.mean(arr))
        row["enrichment_ratio"] = float(np.mean(arr) / baseline) if baseline > 0 else np.nan
    else:
        row["std_y"] = float(np.std(arr))
    return row


def dataset_feature_summary(dataset: str, min_n: int) -> pd.DataFrame:
    frame, _spec = load_dataset(dataset, data_dir=ROOT / "data")
    task_type = infer_task_type(frame["y"])
    baseline = float(frame["y"].mean())
    scaffolds: dict[str, list[float]] = defaultdict(list)
    fragments: dict[str, list[float]] = defaultdict(list)
    for row in frame.itertuples(index=False):
        scaffolds[scaffold_from_smiles(row.smiles)].append(float(row.y))
        for token in set(brics_tokens(row.smiles)):
            fragments[token].append(float(row.y))
    rows = []
    for scaffold, values in scaffolds.items():
        if scaffold and len(values) >= min_n:
            rows.append(summarize_group(dataset, scaffold, "murcko_scaffold", values, baseline, task_type))
    for token, values in fragments.items():
        if len(values) >= min_n:
            rows.append(summarize_group(dataset, token, "brics_fragment", values, baseline, task_type))
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["task_type"] = task_type
    out["abs_delta_mean_y"] = out["delta_mean_y"].abs()
    return out.sort_values(["kind", "abs_delta_mean_y", "n"], ascending=[True, False, False])


def parse_selector(path: Path) -> tuple[str, int] | None:
    match = re.match(r"(.+)_validation_selector_seed(\d+)_predictions\.csv$", path.name)
    if not match:
        return None
    return match.group(1), int(match.group(2))


def high_error_cases(selector_dir: Path, datasets: list[str], top_k: int) -> pd.DataFrame:
    rows = []
    for path in selector_dir.glob("*_validation_selector_seed*_predictions.csv"):
        parsed = parse_selector(path)
        if parsed is None:
            continue
        dataset, seed = parsed
        if dataset not in datasets:
            continue
        table = pd.read_csv(path)
        y = table["y_true"].to_numpy(dtype=float)
        pred = table["y_pred"].to_numpy(dtype=float)
        if set(np.unique(y)).issubset({0, 1}):
            error = np.abs(y - np.clip(pred, 1e-7, 1 - 1e-7))
        else:
            error = np.abs(y - pred)
        table = table.copy()
        table["abs_error"] = error
        table["scaffold"] = table["smiles"].map(scaffold_from_smiles)
        table["brics_fragments"] = table["smiles"].map(lambda s: "|".join(brics_tokens(s)))
        top = table.sort_values("abs_error", ascending=False).head(top_k)
        top.insert(0, "seed", seed)
        top.insert(0, "dataset", dataset)
        rows.append(top)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build scaffold/BRICS case-study summaries.")
    parser.add_argument("--datasets", nargs="*", default=["bbbp", "bace", "clintox"])
    parser.add_argument("--selector-dir", default=str(ROOT / "reports" / "validation_selector_plus_descriptor_motif"))
    parser.add_argument("--output-dir", default=str(ROOT / "reports" / "scaffold_fragment_cases"))
    parser.add_argument("--min-n", type=int, default=4)
    parser.add_argument("--top-k-errors", type=int, default=15)
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    feature_rows = [dataset_feature_summary(dataset, args.min_n) for dataset in args.datasets]
    features = pd.concat([x for x in feature_rows if not x.empty], ignore_index=True) if feature_rows else pd.DataFrame()
    errors = high_error_cases(Path(args.selector_dir), args.datasets, args.top_k_errors)
    features.to_csv(output_dir / "scaffold_fragment_label_enrichment.csv", index=False)
    errors.to_csv(output_dir / "selector_high_error_cases.csv", index=False)
    print(features.head(80).to_string(index=False) if not features.empty else "No feature rows.")


if __name__ == "__main__":
    main()
