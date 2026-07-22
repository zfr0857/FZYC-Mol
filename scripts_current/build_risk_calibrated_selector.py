from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.metrics import brier_score_loss, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPT_DIR = ROOT / "scripts"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SCRIPT_DIR))

import build_validation_selector as selector
from fzyc_mol.datasets import DATASETS, load_dataset
from fzyc_mol.evaluate import compute_metrics

DEFAULT_SELECTOR_SPECS = [
    "moleculenet=reports/validation_selector_expanded",
    "tdc_admet=reports/validation_selector_tdc_admet",
    "structure=reports/structure_full_selector",
]


def parse_spec(text: str) -> tuple[str, Path]:
    if "=" not in text:
        path = Path(text)
        return path.name, ROOT / path
    name, path = text.split("=", 1)
    return name, ROOT / path


def selected_family(candidate: str) -> str:
    for prefix in ("consensus_", "stack_", "adaptive_"):
        if candidate.startswith(prefix):
            return candidate[len(prefix) :]
    raise ValueError(f"Cannot infer selected family from {candidate}")


def parse_prediction_path(path: Path) -> tuple[str, int] | None:
    match = re.match(r"(.+)_validation_selector_seed(\d+)_predictions\.csv$", path.name)
    if not match:
        return None
    return match.group(1), int(match.group(2))


def logit(prob: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(prob, dtype=float), 1e-7, 1.0 - 1e-7)
    return np.log(p / (1.0 - p)).reshape(-1, 1)


def stratified_half_split(y: np.ndarray, task_type: str, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed + 20260528)
    fit: list[int] = []
    select: list[int] = []
    y = np.asarray(y)
    if task_type == "classification" and len(np.unique(y.astype(int))) == 2:
        for label in sorted(np.unique(y.astype(int))):
            idx = np.flatnonzero(y.astype(int) == label)
            rng.shuffle(idx)
            cut = max(1, len(idx) // 2)
            fit.extend(idx[:cut].tolist())
            select.extend(idx[cut:].tolist())
    else:
        idx = np.arange(len(y))
        rng.shuffle(idx)
        cut = max(1, len(idx) // 2)
        fit = idx[:cut].tolist()
        select = idx[cut:].tolist()
    if not select:
        select = fit.copy()
    return np.asarray(sorted(fit), dtype=int), np.asarray(sorted(select), dtype=int)


def fit_classification_calibrator(valid_y: np.ndarray, valid_pred: np.ndarray, seed: int):
    valid_y = np.asarray(valid_y, dtype=int)
    valid_pred = np.clip(np.asarray(valid_pred, dtype=float), 1e-7, 1.0 - 1e-7)
    if len(valid_y) < 8 or len(np.unique(valid_y)) < 2:
        return "uncalibrated", lambda p: np.clip(np.asarray(p, dtype=float), 1e-7, 1.0 - 1e-7)
    fit_idx, select_idx = stratified_half_split(valid_y, "classification", seed)
    candidates: list[tuple[str, float, object]] = [("uncalibrated", brier_score_loss(valid_y[select_idx], valid_pred[select_idx]), None)]
    if len(np.unique(valid_y[fit_idx])) == 2:
        platt = LogisticRegression(C=1e6, solver="lbfgs", max_iter=1000)
        platt.fit(logit(valid_pred[fit_idx]), valid_y[fit_idx])
        platt_select = platt.predict_proba(logit(valid_pred[select_idx]))[:, 1]
        candidates.append(("platt", brier_score_loss(valid_y[select_idx], platt_select), platt))
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        iso.fit(valid_pred[fit_idx], valid_y[fit_idx])
        iso_select = np.clip(iso.predict(valid_pred[select_idx]), 1e-7, 1.0 - 1e-7)
        candidates.append(("isotonic", brier_score_loss(valid_y[select_idx], iso_select), iso))
    chosen = min(candidates, key=lambda row: row[1])[0]
    if chosen == "uncalibrated":
        return chosen, lambda p: np.clip(np.asarray(p, dtype=float), 1e-7, 1.0 - 1e-7)
    if chosen == "platt":
        final = LogisticRegression(C=1e6, solver="lbfgs", max_iter=1000)
        final.fit(logit(valid_pred), valid_y)
        return chosen, lambda p: np.clip(final.predict_proba(logit(p))[:, 1], 1e-7, 1.0 - 1e-7)
    final_iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    final_iso.fit(valid_pred, valid_y)
    return chosen, lambda p: np.clip(final_iso.predict(np.clip(np.asarray(p, dtype=float), 1e-7, 1.0 - 1e-7)), 1e-7, 1.0 - 1e-7)


def fit_regression_calibrator(valid_y: np.ndarray, valid_pred: np.ndarray, seed: int):
    valid_y = np.asarray(valid_y, dtype=float)
    valid_pred = np.asarray(valid_pred, dtype=float)
    if len(valid_y) < 8:
        return "uncalibrated", lambda p: np.asarray(p, dtype=float)
    fit_idx, select_idx = stratified_half_split(valid_y, "regression", seed)
    candidates: list[tuple[str, float, object]] = [
        ("uncalibrated", float(np.sqrt(mean_squared_error(valid_y[select_idx], valid_pred[select_idx]))), None)
    ]
    model = Pipeline([("scaler", StandardScaler()), ("ridge", RidgeCV(alphas=np.logspace(-4, 4, 17)))])
    model.fit(valid_pred[fit_idx].reshape(-1, 1), valid_y[fit_idx])
    pred_select = model.predict(valid_pred[select_idx].reshape(-1, 1))
    candidates.append(("linear", float(np.sqrt(mean_squared_error(valid_y[select_idx], pred_select))), model))
    chosen = min(candidates, key=lambda row: row[1])[0]
    if chosen == "uncalibrated":
        return chosen, lambda p: np.asarray(p, dtype=float)
    final = Pipeline([("scaler", StandardScaler()), ("ridge", RidgeCV(alphas=np.logspace(-4, 4, 17)))])
    final.fit(valid_pred.reshape(-1, 1), valid_y)
    return chosen, lambda p: final.predict(np.asarray(p, dtype=float).reshape(-1, 1))


def normalized(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    finite = np.isfinite(values)
    if not finite.any():
        return np.zeros_like(values, dtype=float)
    lo = float(np.nanmin(values[finite]))
    hi = float(np.nanmax(values[finite]))
    if hi - lo <= 1e-12:
        return np.zeros_like(values, dtype=float)
    return np.nan_to_num((values - lo) / (hi - lo), nan=0.0, posinf=1.0, neginf=0.0)


def merge_weights(pred: pd.DataFrame, weights: pd.DataFrame | None) -> pd.DataFrame:
    out = pred.copy()
    if weights is None or weights.empty:
        return out
    merged = out.merge(weights, on="smiles", how="left", suffixes=("", "_w"))
    return merged


def feature_table(table: pd.DataFrame, task_type: str, valid_center: float) -> pd.DataFrame:
    out = pd.DataFrame(index=table.index)
    pred = pd.to_numeric(table["y_pred_uncalibrated"], errors="coerce").to_numpy(dtype=float)
    out["pred_value"] = pred
    for col in ("ensemble_std", "ensemble_range", "scaffold_distance", "max_train_tanimoto"):
        out[col] = pd.to_numeric(table[col], errors="coerce") if col in table else np.nan
    out["inverse_tanimoto"] = 1.0 - pd.to_numeric(out["max_train_tanimoto"], errors="coerce")
    if task_type == "classification":
        out["confidence_uncertainty"] = 1.0 - np.abs(np.clip(pred, 0.0, 1.0) - 0.5) * 2.0
    else:
        out["prediction_deviation"] = np.abs(pred - valid_center)
    for col in table.columns:
        if col.startswith("weight_"):
            out[col] = pd.to_numeric(table[col], errors="coerce")
    return out.replace([np.inf, -np.inf], np.nan)


def error_values(y_true: np.ndarray, y_pred: np.ndarray, task_type: str) -> np.ndarray:
    if task_type == "classification":
        return np.abs(np.asarray(y_true, dtype=float) - np.clip(np.asarray(y_pred, dtype=float), 1e-7, 1 - 1e-7))
    return np.abs(np.asarray(y_true, dtype=float) - np.asarray(y_pred, dtype=float))


def fit_error_model(x: pd.DataFrame, errors: np.ndarray, seed: int):
    leaf = max(1, min(8, len(x) // 20))
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("model", RandomForestRegressor(n_estimators=240, min_samples_leaf=leaf, random_state=7019 + seed, n_jobs=-1)),
        ]
    ).fit(x, errors)


def risk_scores(valid: pd.DataFrame, test: pd.DataFrame, task_type: str, seed: int) -> tuple[np.ndarray, np.ndarray, pd.DataFrame, pd.DataFrame]:
    valid_center = float(pd.to_numeric(valid["y_pred_uncalibrated"], errors="coerce").mean())
    x_valid = feature_table(valid, task_type, valid_center)
    x_test = feature_table(test, task_type, valid_center).reindex(columns=x_valid.columns, fill_value=np.nan)
    err = error_values(valid["y_true"].to_numpy(), valid["y_pred_uncalibrated"].to_numpy(), task_type)
    model = fit_error_model(x_valid, err, seed)
    valid_error_model = model.predict(x_valid)
    test_error_model = model.predict(x_test)
    test_ensemble = pd.to_numeric(test.get("ensemble_std", pd.Series(np.nan, index=test.index)), errors="coerce").to_numpy(dtype=float)
    test_scaffold = pd.to_numeric(test.get("scaffold_distance", pd.Series(np.nan, index=test.index)), errors="coerce").to_numpy(dtype=float)
    if task_type == "classification":
        p = pd.to_numeric(test["y_pred_calibrated"], errors="coerce").to_numpy(dtype=float)
        test_conf = 1.0 - np.abs(np.clip(p, 0.0, 1.0) - 0.5) * 2.0
    else:
        p = pd.to_numeric(test["y_pred_calibrated"], errors="coerce").to_numpy(dtype=float)
        test_conf = np.abs(p - valid_center)
    hybrid = (
        normalized(test_error_model)
        + normalized(test_ensemble)
        + normalized(test_scaffold)
        + normalized(test_conf)
    ) / 4.0
    valid_hybrid = normalized(valid_error_model)
    return hybrid, test_error_model, x_valid, x_test


def retained_metrics(source: str, dataset: str, seed: int, task_type: str, pred: pd.DataFrame, risk: np.ndarray) -> list[dict]:
    rows = []
    order = np.argsort(risk)
    y = pred["y_true"].to_numpy()
    y_cal = pred["y_pred_calibrated"].to_numpy()
    y_uncal = pred["y_pred_uncalibrated"].to_numpy()
    full_uncal = compute_metrics(task_type, y, y_uncal)
    full_cal = compute_metrics(task_type, y, y_cal)
    rows.append({"source": source, "dataset": dataset, "seed": seed, "variant": "uncalibrated_full", "coverage": 1.0, "retained_n": len(y), "task_type": task_type, **full_uncal})
    rows.append({"source": source, "dataset": dataset, "seed": seed, "variant": "risk_calibrated_full", "coverage": 1.0, "retained_n": len(y), "task_type": task_type, **full_cal})
    for coverage in (0.9, 0.8, 0.7, 0.6, 0.5):
        keep = order[: max(1, int(round(len(order) * coverage)))]
        rows.append(
            {
                "source": source,
                "dataset": dataset,
                "seed": seed,
                "variant": "risk_calibrated_retained",
                "coverage": coverage,
                "retained_n": int(len(keep)),
                "task_type": task_type,
                **compute_metrics(task_type, y[keep], y_cal[keep]),
            }
        )
    return rows


def load_existing_valid_test(selector_dir: Path, dataset: str, seed: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None] | None:
    test_path = selector_dir / f"{dataset}_validation_selector_seed{seed}_predictions.csv"
    valid_path = selector_dir / f"{dataset}_validation_selector_seed{seed}_valid_predictions.csv"
    test_weight_path = selector_dir / f"{dataset}_validation_selector_seed{seed}_weights.csv"
    valid_weight_path = selector_dir / f"{dataset}_validation_selector_seed{seed}_valid_weights.csv"
    if not test_path.exists() or not valid_path.exists():
        return None
    test = pd.read_csv(test_path)
    valid = pd.read_csv(valid_path)
    test_w = pd.read_csv(test_weight_path) if test_weight_path.exists() else None
    valid_w = pd.read_csv(valid_weight_path) if valid_weight_path.exists() else None
    return valid, test, valid_w, test_w


def rebuild_valid_test(selector_dir: Path, dataset: str, seed: int, source: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None] | None:
    selected_path = selector_dir / "selected_candidates.csv"
    if not selected_path.exists():
        return None
    chosen = pd.read_csv(selected_path)
    row = chosen[chosen["dataset"].eq(dataset)]
    if row.empty:
        return None
    candidate = str(row.iloc[0]["selected_candidate"])
    family = selected_family(candidate)
    if family not in selector.MEMBER_SETS:
        return None
    if source.lower().startswith("tdc"):
        replacements = {"reports/strict_multifp": "reports/tdc_admet_multifp"}
    else:
        replacements = {
            "reports/strict_core": "reports/strict_core_fast",
            "reports/strict_multifp": "reports/strict_multifp_fast",
            "reports/descriptor_motif_baselines": "reports/descriptor_motif_baselines",
        }
    members = [(replacements.get(report_dir, report_dir), model) for report_dir, model in selector.MEMBER_SETS[family]]
    frame, spec = load_dataset(dataset, data_dir=ROOT / "data")
    candidates = selector.build_candidate_predictions(dataset, seed, family, members, spec.task_type, frame)
    matches = [item for item in candidates if item["candidate"] == candidate]
    if not matches:
        return None
    item = matches[0]
    return item["valid_select"], item["test"], item["valid_diagnostics"], item["test_diagnostics"]


def process_selector(source: str, selector_dir: Path) -> tuple[list[dict], list[dict]]:
    metric_rows: list[dict] = []
    compound_rows: list[dict] = []
    if not selector_dir.exists():
        return metric_rows, compound_rows
    pred_paths = sorted(selector_dir.glob("*_validation_selector_seed*_predictions.csv"))
    for pred_path in pred_paths:
        parsed = parse_prediction_path(pred_path)
        if parsed is None:
            continue
        dataset, seed = parsed
        if dataset not in DATASETS:
            continue
        frame, spec = load_dataset(dataset, data_dir=ROOT / "data")
        loaded = load_existing_valid_test(selector_dir, dataset, seed)
        if loaded is None:
            loaded = rebuild_valid_test(selector_dir, dataset, seed, source)
        if loaded is None:
            print(f"skip source={source} dataset={dataset} seed={seed}: no validation predictions", flush=True)
            continue
        valid_pred, test_pred, valid_w, test_w = loaded
        valid = merge_weights(valid_pred.rename(columns={"y_pred": "y_pred_uncalibrated"}), valid_w)
        test = merge_weights(test_pred.rename(columns={"y_pred": "y_pred_uncalibrated"}), test_w)
        if spec.task_type == "classification":
            calibrator, transform = fit_classification_calibrator(valid["y_true"].to_numpy(), valid["y_pred_uncalibrated"].to_numpy(), seed)
        else:
            calibrator, transform = fit_regression_calibrator(valid["y_true"].to_numpy(), valid["y_pred_uncalibrated"].to_numpy(), seed)
        valid["y_pred_calibrated"] = transform(valid["y_pred_uncalibrated"].to_numpy())
        test["y_pred_calibrated"] = transform(test["y_pred_uncalibrated"].to_numpy())
        risk, error_model_score, _x_valid, _x_test = risk_scores(valid, test, spec.task_type, seed)
        test["risk_score"] = risk
        test["error_model_score"] = error_model_score
        test["risk_percentile"] = pd.Series(risk).rank(method="average", pct=True).to_numpy()
        test["calibrator"] = calibrator
        rows = retained_metrics(source, dataset, seed, spec.task_type, test, risk)
        valid_error = error_values(valid["y_true"].to_numpy(), valid["y_pred_uncalibrated"].to_numpy(), spec.task_type)
        test_error = error_values(test["y_true"].to_numpy(), test["y_pred_uncalibrated"].to_numpy(), spec.task_type)
        rho = spearmanr(risk, test_error).statistic if len(test_error) >= 3 else np.nan
        for row in rows:
            row["calibrator"] = calibrator
            row["risk_abs_error_spearman"] = float(rho) if np.isfinite(rho) else np.nan
        metric_rows.extend(rows)
        dump = test[["smiles", "y_true", "y_pred_uncalibrated", "y_pred_calibrated", "risk_score", "error_model_score", "risk_percentile", "calibrator"]].copy()
        dump.insert(0, "seed", seed)
        dump.insert(0, "dataset", dataset)
        dump.insert(0, "source", source)
        compound_rows.extend(dump.to_dict("records"))
    return metric_rows, compound_rows


def summarize(raw: pd.DataFrame, output_dir: Path) -> None:
    raw.to_csv(output_dir / "metrics_raw.csv", index=False)
    id_cols = {"source", "dataset", "seed", "variant", "coverage", "retained_n", "task_type", "calibrator"}
    metric_cols = [c for c in raw.columns if c not in id_cols and pd.api.types.is_numeric_dtype(raw[c])]
    summary = raw.groupby(["source", "dataset", "variant", "coverage", "task_type"], dropna=False)[metric_cols].agg(["mean", "std"]).reset_index()
    summary.to_csv(output_dir / "metrics_summary.csv", index=False)

    full = raw[raw["coverage"].eq(1.0)].copy()
    uncal = full[full["variant"].eq("uncalibrated_full")]
    cal = full[full["variant"].eq("risk_calibrated_full")]
    compare = cal.merge(uncal, on=["source", "dataset", "seed", "task_type"], suffixes=("_cal", "_uncal"))
    rows = []
    for row in compare.itertuples(index=False):
        task_type = row.task_type
        out = {"source": row.source, "dataset": row.dataset, "seed": row.seed, "task_type": task_type}
        if task_type == "regression":
            out["delta_rmse_positive"] = getattr(row, "rmse_uncal", np.nan) - getattr(row, "rmse_cal", np.nan)
            out["delta_mae_positive"] = getattr(row, "mae_uncal", np.nan) - getattr(row, "mae_cal", np.nan)
        else:
            out["delta_brier_positive"] = getattr(row, "brier_uncal", np.nan) - getattr(row, "brier_cal", np.nan)
            out["delta_ece_positive"] = getattr(row, "ece_uncal", np.nan) - getattr(row, "ece_cal", np.nan)
            out["delta_roc_auc"] = getattr(row, "roc_auc_cal", np.nan) - getattr(row, "roc_auc_uncal", np.nan)
            out["delta_pr_auc"] = getattr(row, "pr_auc_cal", np.nan) - getattr(row, "pr_auc_uncal", np.nan)
        rows.append(out)
    pd.DataFrame(rows).to_csv(output_dir / "calibrated_vs_uncalibrated.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build risk-calibrated validation selector outputs.")
    parser.add_argument("--selector-specs", nargs="*", default=DEFAULT_SELECTOR_SPECS)
    parser.add_argument("--output-dir", default=str(ROOT / "reports" / "risk_calibrated_selector"))
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    metric_rows: list[dict] = []
    compound_rows: list[dict] = []
    for spec_text in args.selector_specs:
        source, selector_dir = parse_spec(spec_text)
        print(f"process risk-calibrated selector source={source} dir={selector_dir}", flush=True)
        rows, compounds = process_selector(source, selector_dir)
        metric_rows.extend(rows)
        compound_rows.extend(compounds)
    metrics = pd.DataFrame(metric_rows)
    compounds = pd.DataFrame(compound_rows)
    if metrics.empty:
        raise SystemExit("No risk-calibrated rows were built.")
    summarize(metrics, output_dir)
    compounds.to_csv(output_dir / "compound_risk_predictions.csv", index=False)
    calibrators = (
        metrics[metrics["variant"].eq("risk_calibrated_full")]
        .groupby(["source", "dataset", "calibrator"], dropna=False)
        .size()
        .reset_index(name="n_runs")
    )
    calibrators.to_csv(output_dir / "selected_calibrators.csv", index=False)
    print(metrics.tail(40).to_string(index=False))


if __name__ == "__main__":
    main()
