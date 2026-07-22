from __future__ import annotations

import argparse
import zlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon
from sklearn.metrics import mean_squared_error, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import DATASETS


DEFAULT_BASELINES = [
    ("reports/strict_core_fast", "rf_morgan"),
    ("reports/strict_core_fast", "xgb_morgan"),
    ("reports/strict_core_fast", "lgbm_morgan"),
    ("reports/strict_core_fast", "gin"),
    ("reports/strict_core_fast", "dmpnn"),
    ("reports/strict_core_fast", "fzyc_mol_static"),
    ("reports/strict_multifp_fast", "rf_multifp"),
    ("reports/strict_multifp_fast", "xgb_multifp"),
    ("reports/strict_multifp_fast", "lgbm_multifp"),
    ("reports/strict_multifp_fast", "extratrees_multifp"),
    ("reports/chemprop_baseline", "chemprop_dmpnn_ens3"),
    ("reports/chemprop_baseline", "chemprop_rdkit_ens3"),
    ("reports/pretrained_frozen", "DeepChem_ChemBERTa-77M-MTR_frozen_head"),
    ("reports/pretrained_rdkit", "DeepChem_ChemBERTa-77M-MTR_rdkit_head"),
    ("reports/pretrained_frozen_mlm", "DeepChem_ChemBERTa-77M-MLM_frozen_head"),
    ("reports/pretrained_rdkit_mlm", "DeepChem_ChemBERTa-77M-MLM_rdkit_head"),
    ("reports/pretrained_frozen_molformer", "ibm_MoLFormer-XL-both-10pct_frozen_head"),
    ("reports/pretrained_rdkit_molformer", "ibm_MoLFormer-XL-both-10pct_rdkit_head"),
]


def primary_metric(task_type: str, y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if task_type == "regression":
        return float(np.sqrt(mean_squared_error(y_true, y_pred)))
    y = y_true.astype(int)
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, np.clip(y_pred, 1e-7, 1.0 - 1e-7)))


def positive_delta(task_type: str, selector_metric: float, baseline_metric: float) -> float:
    if not np.isfinite(selector_metric) or not np.isfinite(baseline_metric):
        return float("nan")
    if task_type == "regression":
        return baseline_metric - selector_metric
    return selector_metric - baseline_metric


def prediction_path(report_dir: Path, dataset: str, model: str, seed: int) -> Path:
    return report_dir / f"{dataset}_{model}_seed{seed}_predictions.csv"


def selector_path(selector_dir: Path, dataset: str, seed: int) -> Path:
    return selector_dir / f"{dataset}_validation_selector_seed{seed}_predictions.csv"


def paired_table(selector_dir: Path, report_dir: Path, dataset: str, model: str, seed: int) -> pd.DataFrame | None:
    left_path = selector_path(selector_dir, dataset, seed)
    right_path = prediction_path(report_dir, dataset, model, seed)
    if not left_path.exists() or not right_path.exists():
        return None
    left = pd.read_csv(left_path)[["smiles", "y_true", "y_pred"]].rename(columns={"y_pred": "selector_pred"})
    right = pd.read_csv(right_path)[["smiles", "y_pred"]].rename(columns={"y_pred": "baseline_pred"})
    table = left.merge(right, on="smiles", how="inner")
    if table.empty:
        return None
    return table


def bootstrap_delta(task_type: str, tables: list[pd.DataFrame], n_boot: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(n_boot):
        deltas = []
        for table in tables:
            idx = rng.integers(0, len(table), size=len(table))
            sample = table.iloc[idx]
            y = sample["y_true"].to_numpy(dtype=float)
            selector_pred = sample["selector_pred"].to_numpy(dtype=float)
            baseline_pred = sample["baseline_pred"].to_numpy(dtype=float)
            selector_metric = primary_metric(task_type, y, selector_pred)
            baseline_metric = primary_metric(task_type, y, baseline_pred)
            delta = positive_delta(task_type, selector_metric, baseline_metric)
            if np.isfinite(delta):
                deltas.append(delta)
        if deltas:
            values.append(float(np.mean(deltas)))
    return np.asarray(values, dtype=float)


def safe_wilcoxon(deltas: np.ndarray) -> float:
    deltas = deltas[np.isfinite(deltas)]
    if len(deltas) < 2 or np.allclose(deltas, 0.0):
        return float("nan")
    try:
        return float(wilcoxon(deltas, alternative="two-sided").pvalue)
    except ValueError:
        return float("nan")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build paired significance tests for the validation selector.")
    parser.add_argument("--selector-dir", default=str(ROOT / "reports" / "validation_selector_expanded"))
    parser.add_argument("--output-dir", default=str(ROOT / "reports" / "significance_selector"))
    parser.add_argument("--datasets", nargs="*", default=["esol", "freesolv", "lipo", "bbbp", "bace", "clintox"])
    parser.add_argument("--seeds", nargs="*", type=int, default=[13, 17, 23, 29, 31])
    parser.add_argument("--n-boot", type=int, default=2000)
    parser.add_argument("--random-seed", type=int, default=20260526)
    args = parser.parse_args()

    selector_dir = Path(args.selector_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    seed_rows = []
    test_rows = []
    for dataset in args.datasets:
        task_type = DATASETS[dataset].task_type
        for report_text, model in DEFAULT_BASELINES:
            report_dir = ROOT / report_text
            per_seed_tables = []
            per_seed_deltas = []
            for seed in args.seeds:
                table = paired_table(selector_dir, report_dir, dataset, model, seed)
                if table is None:
                    continue
                y = table["y_true"].to_numpy(dtype=float)
                selector_metric = primary_metric(task_type, y, table["selector_pred"].to_numpy(dtype=float))
                baseline_metric = primary_metric(task_type, y, table["baseline_pred"].to_numpy(dtype=float))
                delta = positive_delta(task_type, selector_metric, baseline_metric)
                seed_rows.append(
                    {
                        "dataset": dataset,
                        "task_type": task_type,
                        "baseline_source": report_dir.name,
                        "baseline_model": model,
                        "seed": seed,
                        "n": len(table),
                        "metric": "rmse" if task_type == "regression" else "roc_auc",
                        "selector_metric": selector_metric,
                        "baseline_metric": baseline_metric,
                        "positive_delta": delta,
                    }
                )
                if np.isfinite(delta):
                    per_seed_tables.append(table)
                    per_seed_deltas.append(delta)
            if not per_seed_deltas:
                continue
            deltas = np.asarray(per_seed_deltas, dtype=float)
            boot = bootstrap_delta(
                task_type,
                per_seed_tables,
                args.n_boot,
                args.random_seed + zlib.crc32(f"{dataset}/{model}".encode("utf-8")) % 100000,
            )
            mean_delta = float(np.mean(deltas))
            p_wilcoxon = safe_wilcoxon(deltas)
            if len(boot):
                ci_low, ci_high = np.percentile(boot, [2.5, 97.5])
                win_probability = float(np.mean(boot > 0.0))
                p_boot = float(2.0 * min(np.mean(boot <= 0.0), np.mean(boot >= 0.0)))
            else:
                ci_low = ci_high = win_probability = p_boot = float("nan")
            if np.isfinite(p_boot) and p_boot < 0.05 and mean_delta > 0:
                decision = "win"
            elif np.isfinite(p_boot) and p_boot < 0.05 and mean_delta < 0:
                decision = "loss"
            else:
                decision = "tie"
            test_rows.append(
                {
                    "dataset": dataset,
                    "task_type": task_type,
                    "baseline_source": report_dir.name,
                    "baseline_model": model,
                    "n_seeds": len(deltas),
                    "metric": "rmse" if task_type == "regression" else "roc_auc",
                    "mean_positive_delta": mean_delta,
                    "std_positive_delta": float(np.std(deltas, ddof=1)) if len(deltas) > 1 else 0.0,
                    "bootstrap_ci_low": float(ci_low),
                    "bootstrap_ci_high": float(ci_high),
                    "bootstrap_win_probability": win_probability,
                    "bootstrap_p_two_sided": p_boot,
                    "wilcoxon_p_two_sided": p_wilcoxon,
                    "decision": decision,
                }
            )

    seed_df = pd.DataFrame(seed_rows)
    tests = pd.DataFrame(test_rows)
    seed_df.to_csv(output_dir / "seed_differences.csv", index=False)
    tests.to_csv(output_dir / "significance_tests.csv", index=False)
    if not tests.empty:
        wtl = (
            tests.groupby(["baseline_source", "baseline_model", "decision"])
            .size()
            .unstack(fill_value=0)
            .reset_index()
        )
        for col in ["win", "tie", "loss"]:
            if col not in wtl:
                wtl[col] = 0
        wtl["net_win"] = wtl["win"] - wtl["loss"]
        wtl.sort_values(["net_win", "win"], ascending=False).to_csv(output_dir / "win_tie_loss.csv", index=False)
        print(tests.sort_values(["dataset", "decision", "mean_positive_delta"]).to_string(index=False))


if __name__ == "__main__":
    main()
