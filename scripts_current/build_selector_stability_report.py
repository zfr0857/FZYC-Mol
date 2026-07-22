from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import DATASETS  # noqa: E402

SOURCES = {
    "moleculenet_selector": ROOT / "reports" / "validation_selector_expanded",
    "tdc_admet_selector": ROOT / "reports" / "validation_selector_tdc_admet",
}
OUTPUT_DIR = ROOT / "reports" / "selector_stability"


def strategy(candidate: str) -> str:
    candidate = str(candidate)
    if candidate.startswith("stack"):
        return "stacking"
    if candidate.startswith("adaptive"):
        return "adaptive"
    if candidate.startswith("consensus"):
        return "consensus"
    return "best_expert"


def candidate_family(candidate: str) -> str:
    c = str(candidate).lower()
    if "multifp" in c:
        return "multi_fingerprint"
    if "chemprop" in c:
        return "chemprop"
    if "chemberta" in c or "molformer" in c:
        return "pretrained"
    if "q1_all" in c:
        return "all_experts"
    return "core"


def weight_family(column: str) -> str:
    c = column.replace("weight_", "").lower()
    if "multifp" in c:
        return "multi_fingerprint"
    if "chemprop" in c:
        return "chemprop"
    if "chemberta" in c or "molformer" in c:
        return "pretrained"
    if c in {"gin", "dmpnn", "fzyc_mol_static"}:
        return "graph_core"
    if c in {"rf_morgan", "xgb_morgan", "lgbm_morgan"}:
        return "morgan_tree"
    return "other"


def parse_weight_name(path: Path) -> tuple[str, int] | None:
    match = re.match(r"(.+)_validation_selector_seed(\d+)_weights\.csv$", path.name)
    if not match:
        return None
    dataset, seed = match.groups()
    if dataset not in DATASETS:
        return None
    return dataset, int(seed)


def entropy(weights: np.ndarray) -> float:
    w = np.asarray(weights, dtype=float)
    w = w[np.isfinite(w)]
    w = w[w > 0]
    if len(w) == 0:
        return float("nan")
    w = w / w.sum()
    return float(-(w * np.log(w)).sum())


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    selection_rows: list[pd.DataFrame] = []
    weight_rows: list[dict[str, object]] = []
    for source, directory in SOURCES.items():
        selected_path = directory / "selected_candidates.csv"
        if selected_path.exists():
            selected = pd.read_csv(selected_path)
            selected["source"] = source
            selected["strategy"] = selected["selected_candidate"].map(strategy)
            selected["candidate_family"] = selected["selected_candidate"].map(candidate_family)
            selection_rows.append(selected)
        for weight_path in directory.glob("*_validation_selector_seed*_weights.csv"):
            parsed = parse_weight_name(weight_path)
            if parsed is None:
                continue
            dataset, seed = parsed
            frame = pd.read_csv(weight_path)
            weight_cols = [c for c in frame.columns if c.startswith("weight_")]
            if not weight_cols:
                continue
            family_values: dict[str, float] = {}
            for family in sorted({weight_family(c) for c in weight_cols}):
                cols = [c for c in weight_cols if weight_family(c) == family]
                family_values[f"family_weight_{family}"] = float(frame[cols].sum(axis=1).mean())
            matrix = frame[weight_cols].to_numpy(dtype=float)
            entropies = np.apply_along_axis(entropy, 1, matrix)
            effective = np.exp(entropies)
            top_cols = frame[weight_cols].idxmax(axis=1).str.replace("weight_", "", regex=False)
            top_family = top_cols.map(lambda c: weight_family(f"weight_{c}")).mode()
            row: dict[str, object] = {
                "source": source,
                "dataset": dataset,
                "seed": seed,
                "task_type": DATASETS[dataset].task_type,
                "n_compounds": len(frame),
                "mean_entropy": float(np.nanmean(entropies)),
                "mean_effective_experts": float(np.nanmean(effective)),
                "dominant_family": top_family.iloc[0] if not top_family.empty else "",
            }
            row.update(family_values)
            weight_rows.append(row)

    if selection_rows:
        selected_all = pd.concat(selection_rows, ignore_index=True)
        selected_all.to_csv(OUTPUT_DIR / "selected_candidate_stability.csv", index=False)
        selected_counts = (
            selected_all.groupby(["source", "strategy", "candidate_family"], dropna=False)
            .size()
            .reset_index(name="n_datasets")
        )
        selected_counts.to_csv(OUTPUT_DIR / "selected_strategy_counts.csv", index=False)
    weights = pd.DataFrame(weight_rows)
    weights.to_csv(OUTPUT_DIR / "selector_family_weights_raw.csv", index=False)
    numeric_cols = [c for c in weights.columns if c.startswith("family_weight_") or c in {"mean_entropy", "mean_effective_experts"}]
    summary = (
        weights.groupby(["source", "dataset", "task_type"], dropna=False)[numeric_cols]
        .agg(["mean", "std"])
        .reset_index()
    )
    summary.to_csv(OUTPUT_DIR / "selector_family_weights_summary.csv", index=False)
    print(f"wrote selector stability report to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
