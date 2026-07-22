from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = ROOT / "reports" / "openadmet_expansionrx_fast_benchmark"
TABLE_DIR = ROOT / "reports" / "manuscript_tables"
OUT_TABLE = TABLE_DIR / "table13_openadmet_expansionrx_fast_external_benchmark.csv"
OUT_NOTE = BENCHMARK_DIR / "appendix_benchmark_summary.md"

ENDPOINT_ORDER = [
    "LogD",
    "KSOL",
    "HLM CLint",
    "MLM CLint",
    "Caco-2 Permeability Papp A>B",
    "Caco-2 Permeability Efflux",
    "MPPB",
    "MBPB",
    "MGMB",
]

METRIC_COLUMNS = [
    "valid_mae",
    "test_mae",
    "test_rmse",
    "test_r2",
    "test_spearman",
    "test_pearson",
]


def strategy_profile(values: pd.Series) -> str:
    counts = values.value_counts()
    total = int(counts.sum())
    parts = [f"{name} ({int(count)}/{total})" for name, count in counts.items()]
    return "; ".join(parts)


def rounded(value: float) -> float:
    if pd.isna(value):
        return np.nan
    return round(float(value), 4)


def main() -> None:
    metrics_path = BENCHMARK_DIR / "metrics_raw.csv"
    choices_path = BENCHMARK_DIR / "selector_choices.csv"
    if not metrics_path.exists():
        raise FileNotFoundError(metrics_path)
    if not choices_path.exists():
        raise FileNotFoundError(choices_path)

    metrics = pd.read_csv(metrics_path)
    choices = pd.read_csv(choices_path)
    selected = metrics[metrics["selected"].astype(str).str.lower() == "true"].copy()
    if selected.empty:
        raise ValueError("No selected rows found in metrics_raw.csv")

    rows = []
    for endpoint in ENDPOINT_ORDER:
        endpoint_rows = selected[selected["endpoint"] == endpoint].copy()
        if endpoint_rows.empty:
            continue
        endpoint_choices = choices[choices["endpoint"] == endpoint]
        row = {
            "benchmark": "OpenADMET-ExpansionRx",
            "endpoint": endpoint,
            "n_train_labeled": int((endpoint_rows["n_train_fit"] + endpoint_rows["n_valid"]).median()),
            "n_valid": int(endpoint_rows["n_valid"].median()),
            "n_test_labeled": int(endpoint_rows["n_test"].median()),
            "n_seeds": int(endpoint_rows["seed"].nunique()),
            "selected_strategy_profile": strategy_profile(endpoint_choices["selected_strategy"]),
        }
        for column in METRIC_COLUMNS:
            row[f"{column}_mean"] = rounded(endpoint_rows[column].mean())
            row[f"{column}_std"] = rounded(endpoint_rows[column].std(ddof=1))
        rows.append(row)

    table = pd.DataFrame(rows)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT_TABLE, index=False)

    markdown = table.to_markdown(index=False)
    note = f"""# OpenADMET-ExpansionRx Fast External Appendix Benchmark

Source table: `{OUT_TABLE.relative_to(ROOT)}`

This appendix benchmark uses the released OpenADMET-ExpansionRx train/test files and keeps the test labels untouched until final evaluation. The selector is chosen by scaffold validation MAE inside the released training set. Metrics are reported in each endpoint's native label units, so MAE/RMSE should not be averaged across endpoints.

{markdown}

Manuscript placement: Supplementary or appendix external benchmark. The result supports external feasibility and reliability framing, but should not be merged into the main MoleculeNet/TDC aggregate tables.
"""
    OUT_NOTE.write_text(note, encoding="utf-8")
    print(f"Wrote {OUT_TABLE}")
    print(f"Wrote {OUT_NOTE}")


if __name__ == "__main__":
    main()
