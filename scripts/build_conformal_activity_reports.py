from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from rdkit import DataStructs
from scipy.stats import spearmanr
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import DATASETS, load_dataset
from fzyc_mol.evaluate import compute_metrics
from fzyc_mol.features import morgan_fingerprint
from fzyc_mol.reliability.conformal import (
    classification_prediction_sets,
    fit_label_conditional,
    normalized_interval_width,
)
from fzyc_mol.splits import make_split

from scripts.build_validation_selector import MEMBER_SETS, build_candidate_predictions


REPORT_REPLACEMENTS = {
    "reports/strict_core": "reports/strict_core_fast",
    "reports/strict_multifp": "reports/strict_multifp_fast",
    "reports/chemprop_baseline": "reports/chemprop_baseline",
    "reports/pretrained_frozen": "reports/pretrained_frozen",
    "reports/pretrained_rdkit": "reports/pretrained_rdkit",
    "reports/pretrained_frozen_mlm": "reports/pretrained_frozen_mlm",
    "reports/pretrained_rdkit_mlm": "reports/pretrained_rdkit_mlm",
    "reports/pretrained_frozen_molformer": "reports/pretrained_frozen_molformer",
    "reports/pretrained_rdkit_molformer": "reports/pretrained_rdkit_molformer",
}


def split_candidate(name: str) -> tuple[str, str]:
    for method in ("consensus", "stack", "adaptive"):
        prefix = f"{method}_"
        if name.startswith(prefix):
            return method, name[len(prefix) :]
    raise ValueError(f"Cannot parse candidate name: {name}")


def conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    values = np.sort(np.asarray(scores, dtype=float)[np.isfinite(scores)])
    if len(values) == 0:
        return float("nan")
    rank = int(np.ceil((len(values) + 1) * (1.0 - alpha)))
    rank = min(max(rank, 1), len(values))
    return float(values[rank - 1])


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1.0 - 1e-6)
    return np.log(p / (1.0 - p))


def calibrate_classification(valid: pd.DataFrame, test: pd.DataFrame) -> dict[str, np.ndarray]:
    y_valid = valid["y_true"].to_numpy(dtype=int)
    p_valid = np.clip(valid["y_pred"].to_numpy(dtype=float), 1e-6, 1.0 - 1e-6)
    p_test = np.clip(test["y_pred"].to_numpy(dtype=float), 1e-6, 1.0 - 1e-6)
    outputs = {"raw": p_test}
    if len(np.unique(y_valid)) == 2 and len(valid) >= 8:
        x_valid = logit(p_valid).reshape(-1, 1)
        x_test = logit(p_test).reshape(-1, 1)
        platt = LogisticRegression(max_iter=1000).fit(x_valid, y_valid)
        outputs["platt"] = platt.predict_proba(x_test)[:, 1]
        iso = IsotonicRegression(out_of_bounds="clip").fit(p_valid, y_valid)
        outputs["isotonic"] = np.clip(iso.predict(p_test), 1e-7, 1.0 - 1e-7)
    return outputs


def classification_conformal(valid: pd.DataFrame, test: pd.DataFrame, alpha: float) -> dict:
    y_valid = valid["y_true"].to_numpy(dtype=int)
    p_valid = np.clip(valid["y_pred"].to_numpy(dtype=float), 1e-7, 1.0 - 1e-7)
    fit = fit_label_conditional(y_valid, np.column_stack([1.0 - p_valid, p_valid]), alpha=alpha)
    y_test = test["y_true"].to_numpy(dtype=int)
    p_test = np.clip(test["y_pred"].to_numpy(dtype=float), 1e-7, 1.0 - 1e-7)
    sets = classification_prediction_sets(np.column_stack([1.0 - p_test, p_test]), fit.thresholds)
    covered = np.asarray([int(label) in prediction_set for label, prediction_set in zip(y_test, sets)], dtype=bool)
    set_size = np.asarray([len(value) for value in sets], dtype=int)
    return {
        "qhat": max(fit.thresholds.values()),
        "qhat_y0": fit.thresholds[0],
        "qhat_y1": fit.thresholds[1],
        "class_0_calibration_count": fit.class_counts[0],
        "class_1_calibration_count": fit.class_counts[1],
        "fallback_reason": fit.fallback_reason,
        "coverage": float(np.mean(covered)),
        "class_0_coverage": float(np.mean(covered[y_test == 0])) if np.any(y_test == 0) else np.nan,
        "class_1_coverage": float(np.mean(covered[y_test == 1])) if np.any(y_test == 1) else np.nan,
        "avg_set_size": float(np.mean(set_size)),
        "singleton_rate": float(np.mean(set_size == 1)),
        "empty_rate": float(np.mean(set_size == 0)),
    }


def regression_conformal(valid: pd.DataFrame, test: pd.DataFrame, alpha: float, *, y_train) -> dict:
    residual = np.abs(valid["y_true"].to_numpy(dtype=float) - valid["y_pred"].to_numpy(dtype=float))
    qhat = conformal_quantile(residual, alpha)
    y = test["y_true"].to_numpy(dtype=float)
    pred = test["y_pred"].to_numpy(dtype=float)
    lower = pred - qhat
    upper = pred + qhat
    covered = (y >= lower) & (y <= upper)
    width = 2.0 * qhat
    normalized = normalized_interval_width([width], y_train)
    interval_score = width + (2.0 / alpha) * np.where(y < lower, lower - y, 0.0) + (2.0 / alpha) * np.where(y > upper, y - upper, 0.0)
    return {
        "qhat": qhat,
        "coverage": float(np.mean(covered)),
        "mean_width": float(width),
        "normalized_width_sd": float(normalized["width_sd"][0]),
        "normalized_width_iqr": float(normalized["width_iqr"][0]),
        "interval_score": float(np.mean(interval_score)),
        "median_abs_error": float(np.median(np.abs(y - pred))),
    }


def hard_scaffold_rows(dataset: str, seed: int, task_type: str, test: pd.DataFrame, diagnostics: pd.DataFrame) -> list[dict]:
    table = test.merge(diagnostics, on="smiles", how="left")
    rows = []
    if "max_train_tanimoto" not in table:
        return rows
    for threshold in (0.4, 0.6, 0.8):
        subset = table[table["max_train_tanimoto"] <= threshold]
        if len(subset) < 3:
            continue
        metrics = compute_metrics(
            task_type,
            subset["y_true"].to_numpy(dtype=float),
            subset["y_pred"].to_numpy(dtype=float),
        )
        row = {
            "dataset": dataset,
            "seed": seed,
            "task_type": task_type,
            "threshold": threshold,
            "n": len(subset),
            "mean_similarity": float(subset["max_train_tanimoto"].mean()),
        }
        row.update(metrics)
        rows.append(row)
    return rows


def bitvect_from_array(arr: np.ndarray) -> DataStructs.ExplicitBitVect:
    bitvect = DataStructs.ExplicitBitVect(int(arr.shape[0]))
    for bit in np.flatnonzero(arr > 0):
        bitvect.SetBit(int(bit))
    return bitvect


def activity_cliff_summary(dataset: str, seed: int, task_type: str, test: pd.DataFrame) -> dict:
    smiles = test["smiles"].tolist()
    y = test["y_true"].to_numpy(dtype=float)
    pred = test["y_pred"].to_numpy(dtype=float)
    fps = [bitvect_from_array(morgan_fingerprint(smi)) for smi in smiles]
    rows = []
    for i in range(len(test)):
        sims = DataStructs.BulkTanimotoSimilarity(fps[i], fps[i + 1 :])
        for offset, sim in enumerate(sims, start=i + 1):
            if sim >= 0.7:
                rows.append((i, offset, float(sim), abs(float(y[i] - y[offset]))))
    if not rows:
        return {
            "dataset": dataset,
            "seed": seed,
            "task_type": task_type,
            "n_pairs": 0,
            "n_cliffs": 0,
        }
    pairs = pd.DataFrame(rows, columns=["i", "j", "similarity", "label_delta"])
    if task_type == "classification":
        cliffs = pairs[pairs["label_delta"] > 0.0].copy()
        if cliffs.empty:
            return {
                "dataset": dataset,
                "seed": seed,
                "task_type": task_type,
                "n_pairs": len(pairs),
                "n_cliffs": 0,
            }
        correct = []
        gaps = []
        for _, row in cliffs.iterrows():
            i, j = int(row["i"]), int(row["j"])
            positive_idx = i if y[i] > y[j] else j
            negative_idx = j if positive_idx == i else i
            correct.append(float(pred[positive_idx] > pred[negative_idx]))
            gaps.append(float(abs(pred[positive_idx] - pred[negative_idx])))
        return {
            "dataset": dataset,
            "seed": seed,
            "task_type": task_type,
            "n_pairs": len(pairs),
            "n_cliffs": len(cliffs),
            "mean_similarity": float(cliffs["similarity"].mean()),
            "direction_accuracy": float(np.mean(correct)),
            "mean_prediction_gap": float(np.mean(gaps)),
        }
    cutoff = max(float(pairs["label_delta"].quantile(0.75)), 1e-8)
    cliffs = pairs[pairs["label_delta"] >= cutoff].copy()
    sign_correct = []
    pred_delta_error = []
    true_deltas = []
    pred_deltas = []
    for _, row in cliffs.iterrows():
        i, j = int(row["i"]), int(row["j"])
        true_delta = float(y[i] - y[j])
        pred_delta = float(pred[i] - pred[j])
        sign_correct.append(float(np.sign(true_delta) == np.sign(pred_delta)))
        pred_delta_error.append(abs(true_delta - pred_delta))
        true_deltas.append(true_delta)
        pred_deltas.append(pred_delta)
    rho = spearmanr(true_deltas, pred_deltas).statistic if len(cliffs) > 2 else np.nan
    return {
        "dataset": dataset,
        "seed": seed,
        "task_type": task_type,
        "n_pairs": len(pairs),
        "n_cliffs": len(cliffs),
        "cliff_delta_cutoff": cutoff,
        "mean_similarity": float(cliffs["similarity"].mean()) if len(cliffs) else np.nan,
        "direction_accuracy": float(np.mean(sign_correct)) if sign_correct else np.nan,
        "delta_mae": float(np.mean(pred_delta_error)) if pred_delta_error else np.nan,
        "delta_spearman": float(rho) if np.isfinite(rho) else np.nan,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build conformal, hard-scaffold, and activity-cliff reports.")
    parser.add_argument("--selector-dir", default=str(ROOT / "reports" / "validation_selector_expanded"))
    parser.add_argument("--output-dir", default=str(ROOT / "reports" / "conformal_activity"))
    parser.add_argument("--alpha", type=float, default=0.1)
    parser.add_argument("--seeds", nargs="*", type=int, default=[13, 17, 23, 29, 31])
    args = parser.parse_args()

    selector_dir = Path(args.selector_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fig_dir = output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    selected = pd.read_csv(selector_dir / "selected_candidates.csv")
    conformal_rows = []
    calibration_rows = []
    hard_rows = []
    cliff_rows = []
    for _, selection in selected.iterrows():
        dataset = selection["dataset"]
        candidate = selection["selected_candidate"]
        method, family = split_candidate(candidate)
        members = [
            (REPORT_REPLACEMENTS.get(report_dir, report_dir), model)
            for report_dir, model in MEMBER_SETS[family]
        ]
        frame, spec = load_dataset(dataset, data_dir=ROOT / "data")
        for seed in args.seeds:
            split = make_split(frame, "scaffold", seed)
            candidates = build_candidate_predictions(dataset, seed, family, members, spec.task_type, frame)
            item = next(obj for obj in candidates if obj["candidate"] == candidate and obj["method"] == method)
            valid = item["valid_select"].copy()
            test = item["test"].copy()
            if spec.task_type == "classification":
                conf = classification_conformal(valid, test, args.alpha)
                for calibration_name, calibrated_pred in calibrate_classification(valid, test).items():
                    metrics = compute_metrics(
                        spec.task_type,
                        test["y_true"].to_numpy(dtype=float),
                        calibrated_pred,
                    )
                    calibration_rows.append(
                        {
                            "dataset": dataset,
                            "seed": seed,
                            "candidate": candidate,
                            "calibration": calibration_name,
                            **metrics,
                        }
                    )
            else:
                conf = regression_conformal(valid, test, args.alpha, y_train=frame.iloc[split.train]["y"].to_numpy())
            conformal_rows.append(
                {
                    "dataset": dataset,
                    "seed": seed,
                    "candidate": candidate,
                    "task_type": spec.task_type,
                    "alpha": args.alpha,
                    **conf,
                }
            )
            hard_rows.extend(hard_scaffold_rows(dataset, seed, spec.task_type, test, item["test_diagnostics"]))
            cliff_rows.append(activity_cliff_summary(dataset, seed, spec.task_type, test))

    conformal = pd.DataFrame(conformal_rows)
    calibration = pd.DataFrame(calibration_rows)
    hard = pd.DataFrame(hard_rows)
    cliffs = pd.DataFrame(cliff_rows)
    conformal.to_csv(output_dir / "conformal_summary.csv", index=False)
    calibration.to_csv(output_dir / "calibration_comparison.csv", index=False)
    hard.to_csv(output_dir / "hard_scaffold_metrics.csv", index=False)
    cliffs.to_csv(output_dir / "activity_cliff_summary.csv", index=False)

    if not conformal.empty:
        coverage = conformal.groupby("dataset", as_index=False)["coverage"].mean()
        plt.figure(figsize=(7.2, 3.8))
        plt.bar(coverage["dataset"], coverage["coverage"])
        plt.axhline(1.0 - args.alpha, color="black", linestyle="--", linewidth=1)
        plt.ylabel("Empirical coverage")
        plt.xticks(rotation=30, ha="right")
        plt.tight_layout()
        plt.savefig(fig_dir / "conformal_coverage.png", dpi=220)
        plt.close()
    if not hard.empty:
        metric_col = np.where(hard["task_type"] == "regression", hard.get("rmse"), hard.get("roc_auc"))
        hard_plot = hard.copy()
        hard_plot["primary_metric"] = metric_col
        summary = hard_plot.groupby(["dataset", "threshold"], as_index=False)["primary_metric"].mean()
        for dataset, group in summary.groupby("dataset"):
            plt.figure(figsize=(4.8, 3.5))
            plt.plot(group["threshold"], group["primary_metric"], marker="o")
            plt.xlabel("Max train Tanimoto threshold")
            plt.ylabel("RMSE" if DATASETS[dataset].task_type == "regression" else "ROC-AUC")
            plt.title(f"{dataset} hard-scaffold subset")
            plt.tight_layout()
            plt.savefig(fig_dir / f"{dataset}_hard_scaffold.png", dpi=220)
            plt.close()
    print(conformal.groupby(["dataset", "task_type"]).mean(numeric_only=True).reset_index().to_string(index=False))


if __name__ == "__main__":
    main()
