from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import DATASETS  # noqa: E402
from fzyc_mol.evaluate import compute_metrics  # noqa: E402

REPORT_SOURCES = {
    "strict_core_fast": ROOT / "reports" / "strict_core_fast",
    "strict_multifp_fast": ROOT / "reports" / "strict_multifp_fast",
    "chemprop_baseline": ROOT / "reports" / "chemprop_baseline",
    "descriptor_motif_baselines": ROOT / "reports" / "descriptor_motif_baselines",
    "tdc_admet_multifp": ROOT / "reports" / "tdc_admet_multifp",
}

OUTPUT_DIR = ROOT / "reports" / "validation_calibration"
CLASSIFICATION_DATASETS = [name for name, spec in DATASETS.items() if spec.task_type == "classification"]
DATASET_ORDER = sorted(CLASSIFICATION_DATASETS, key=len, reverse=True)


def parse_prediction_name(path: Path) -> tuple[str, str, int] | None:
    name = path.name
    if not name.endswith("_valid_predictions.csv"):
        return None
    stem = name[: -len("_valid_predictions.csv")]
    match = re.match(r"(.+)_seed(\d+)$", stem)
    if not match:
        return None
    prefix, seed_text = match.groups()
    for dataset in DATASET_ORDER:
        token = f"{dataset}_"
        if prefix.startswith(token):
            model = prefix[len(token) :]
            return dataset, model, int(seed_text)
    return None


def clip_prob(values: np.ndarray) -> np.ndarray:
    return np.clip(np.asarray(values, dtype=float).reshape(-1), 1e-6, 1.0 - 1e-6)


def logit(values: np.ndarray) -> np.ndarray:
    p = clip_prob(values)
    return np.log(p / (1.0 - p)).reshape(-1, 1)


def calibrate_platt(valid_pred: np.ndarray, valid_y: np.ndarray, test_pred: np.ndarray) -> np.ndarray | None:
    if len(np.unique(valid_y)) < 2:
        return None
    model = LogisticRegression(C=1e6, solver="lbfgs", max_iter=1000)
    model.fit(logit(valid_pred), valid_y.astype(int))
    return model.predict_proba(logit(test_pred))[:, 1]


def calibrate_isotonic(valid_pred: np.ndarray, valid_y: np.ndarray, test_pred: np.ndarray) -> np.ndarray | None:
    if len(np.unique(valid_y)) < 2:
        return None
    model = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    model.fit(clip_prob(valid_pred), valid_y.astype(int))
    return clip_prob(model.predict(clip_prob(test_pred)))


def evaluate_calibrators(valid: pd.DataFrame, test: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    valid_y = valid["y_true"].to_numpy().astype(int)
    test_y = test["y_true"].to_numpy().astype(int)
    valid_pred = clip_prob(valid["y_pred"].to_numpy())
    test_pred = clip_prob(test["y_pred"].to_numpy())

    candidates: dict[str, tuple[np.ndarray, np.ndarray]] = {
        "uncalibrated": (valid_pred, test_pred),
    }
    platt_test = calibrate_platt(valid_pred, valid_y, test_pred)
    if platt_test is not None:
        platt_valid = calibrate_platt(valid_pred, valid_y, valid_pred)
        if platt_valid is not None:
            candidates["platt"] = (platt_valid, platt_test)
    iso_test = calibrate_isotonic(valid_pred, valid_y, test_pred)
    if iso_test is not None:
        iso_valid = calibrate_isotonic(valid_pred, valid_y, valid_pred)
        if iso_valid is not None:
            candidates["isotonic"] = (iso_valid, iso_test)

    rows: list[dict[str, float | str]] = []
    for name, (valid_scores, test_scores) in candidates.items():
        valid_metrics = compute_metrics("classification", valid_y, valid_scores)
        test_metrics = compute_metrics("classification", test_y, test_scores)
        row: dict[str, float | str] = {"calibrator": name}
        row.update({f"valid_{k}": v for k, v in valid_metrics.items()})
        row.update({f"test_{k}": v for k, v in test_metrics.items()})
        rows.append(row)
    metrics = pd.DataFrame(rows)
    selected = metrics.sort_values(["valid_brier", "valid_ece"], ascending=[True, True]).head(1).copy()
    selected["selection_metric"] = "valid_brier"
    return metrics, selected


def summarize(raw: pd.DataFrame, selected: pd.DataFrame) -> None:
    metric_cols = [
        col
        for col in raw.columns
        if col.startswith("test_") or col.startswith("valid_")
    ]
    summary = (
        raw.groupby(["source", "dataset", "model", "calibrator"], dropna=False)[metric_cols]
        .agg(["mean", "std"])
        .reset_index()
    )
    summary.to_csv(OUTPUT_DIR / "calibration_metrics_summary.csv", index=False)

    selected_summary = (
        selected.groupby(["source", "dataset", "model", "calibrator"], dropna=False)[metric_cols]
        .agg(["mean", "std"])
        .reset_index()
    )
    selected_summary.to_csv(OUTPUT_DIR / "selected_calibration_summary.csv", index=False)

    base = raw[raw["calibrator"].eq("uncalibrated")]
    chosen = selected.copy()
    merged = chosen.merge(
        base[
            [
                "source",
                "dataset",
                "model",
                "seed",
                "test_brier",
                "test_ece",
                "test_roc_auc",
                "test_pr_auc",
            ]
        ],
        on=["source", "dataset", "model", "seed"],
        suffixes=("", "_uncalibrated"),
        how="left",
    )
    merged["delta_brier_positive"] = merged["test_brier_uncalibrated"] - merged["test_brier"]
    merged["delta_ece_positive"] = merged["test_ece_uncalibrated"] - merged["test_ece"]
    merged["delta_roc_auc"] = merged["test_roc_auc"] - merged["test_roc_auc_uncalibrated"]
    merged["delta_pr_auc"] = merged["test_pr_auc"] - merged["test_pr_auc_uncalibrated"]
    merged.to_csv(OUTPUT_DIR / "selected_vs_uncalibrated.csv", index=False)

    aggregate = (
        merged.groupby(["source", "dataset"], dropna=False)
        .agg(
            n_runs=("seed", "count"),
            selected_platt=("calibrator", lambda x: int((x == "platt").sum())),
            selected_isotonic=("calibrator", lambda x: int((x == "isotonic").sum())),
            selected_uncalibrated=("calibrator", lambda x: int((x == "uncalibrated").sum())),
            mean_delta_brier_positive=("delta_brier_positive", "mean"),
            mean_delta_ece_positive=("delta_ece_positive", "mean"),
            mean_delta_roc_auc=("delta_roc_auc", "mean"),
            mean_delta_pr_auc=("delta_pr_auc", "mean"),
        )
        .reset_index()
    )
    aggregate.to_csv(OUTPUT_DIR / "calibration_improvement_by_dataset.csv", index=False)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_rows: list[pd.DataFrame] = []
    selected_rows: list[pd.DataFrame] = []
    for source, directory in REPORT_SOURCES.items():
        if not directory.exists():
            continue
        for valid_path in directory.glob("*_valid_predictions.csv"):
            parsed = parse_prediction_name(valid_path)
            if parsed is None:
                continue
            dataset, model, seed = parsed
            if DATASETS[dataset].task_type != "classification":
                continue
            test_path = directory / f"{dataset}_{model}_seed{seed}_predictions.csv"
            if not test_path.exists():
                continue
            valid = pd.read_csv(valid_path)
            test = pd.read_csv(test_path)
            if len(np.unique(valid["y_true"].astype(int))) < 2 or len(np.unique(test["y_true"].astype(int))) < 2:
                continue
            metrics, selected = evaluate_calibrators(valid, test)
            for frame in (metrics, selected):
                frame.insert(0, "seed", seed)
                frame.insert(0, "model", model)
                frame.insert(0, "dataset", dataset)
                frame.insert(0, "source", source)
            raw_rows.append(metrics)
            selected_rows.append(selected)

    if not raw_rows:
        raise RuntimeError("No calibration inputs found.")
    raw = pd.concat(raw_rows, ignore_index=True)
    selected = pd.concat(selected_rows, ignore_index=True)
    raw.to_csv(OUTPUT_DIR / "calibration_metrics_raw.csv", index=False)
    selected.to_csv(OUTPUT_DIR / "selected_calibrators_raw.csv", index=False)
    summarize(raw, selected)
    print(f"wrote calibration report to {OUTPUT_DIR}")
    print(selected["calibrator"].value_counts().to_string())


if __name__ == "__main__":
    main()
