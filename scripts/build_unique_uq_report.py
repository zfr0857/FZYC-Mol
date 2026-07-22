from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_squared_error
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPT_DIR = ROOT / "scripts"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SCRIPT_DIR))

import build_validation_selector as selector
from fzyc_mol.datasets import load_dataset


def selected_family(candidate: str) -> str:
    for prefix in ("consensus_", "stack_", "adaptive_"):
        if candidate.startswith(prefix):
            return candidate[len(prefix) :]
    raise ValueError(f"Cannot infer family from candidate={candidate}")


def numeric_feature_table(table: pd.DataFrame, task_type: str, valid_mean: float | None = None) -> pd.DataFrame:
    out = table.copy()
    pred = pd.to_numeric(out["y_pred"], errors="coerce").astype(float)
    out["pred_value"] = pred
    if task_type == "classification":
        out["confidence_uncertainty"] = 1.0 - np.abs(np.clip(pred, 0.0, 1.0) - 0.5) * 2.0
    else:
        center = float(valid_mean if valid_mean is not None else pred.mean())
        out["prediction_deviation"] = np.abs(pred - center)
    for col in ("ensemble_std", "scaffold_distance", "max_train_tanimoto"):
        if col not in out:
            out[col] = np.nan
    out["inverse_tanimoto"] = 1.0 - pd.to_numeric(out["max_train_tanimoto"], errors="coerce").astype(float)
    feature_cols = [
        "pred_value",
        "ensemble_std",
        "scaffold_distance",
        "inverse_tanimoto",
    ]
    if task_type == "classification":
        feature_cols.append("confidence_uncertainty")
    else:
        feature_cols.append("prediction_deviation")
    feature_cols += [col for col in out.columns if col.startswith("weight_")]
    return out[feature_cols].replace([np.inf, -np.inf], np.nan)


def error_values(table: pd.DataFrame, task_type: str) -> np.ndarray:
    y = pd.to_numeric(table["y_true"], errors="coerce").to_numpy(dtype=float)
    pred = pd.to_numeric(table["y_pred"], errors="coerce").to_numpy(dtype=float)
    if task_type == "classification":
        pred = np.clip(pred, 1e-7, 1.0 - 1e-7)
        return np.abs(y - pred)
    return np.abs(y - pred)


def fit_error_model(x: pd.DataFrame, y_error: np.ndarray, seed: int):
    leaf = max(1, min(8, len(x) // 20))
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            (
                "model",
                RandomForestRegressor(
                    n_estimators=220,
                    min_samples_leaf=leaf,
                    random_state=7001 + seed,
                    n_jobs=-1,
                ),
            ),
        ]
    ).fit(x, y_error)


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


def risk_coverage_rows(
    dataset: str,
    seed: int,
    score_name: str,
    uncertainty: np.ndarray,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    task_type: str,
) -> list[dict]:
    order = np.argsort(uncertainty)
    rows = []
    for coverage in np.linspace(0.1, 1.0, 10):
        keep = order[: max(1, int(round(len(order) * coverage)))]
        if task_type == "classification":
            risk = float(((y_pred[keep] >= 0.5).astype(int) != y_true[keep].astype(int)).mean())
            risk_metric = "error_rate"
        else:
            risk = float(np.sqrt(mean_squared_error(y_true[keep], y_pred[keep])))
            risk_metric = "rmse"
        rows.append(
            {
                "dataset": dataset,
                "seed": seed,
                "uq_score": score_name,
                "coverage": float(coverage),
                "risk_metric": risk_metric,
                "risk": risk,
            }
        )
    return rows


def score_metrics(dataset: str, seed: int, score_name: str, uncertainty: np.ndarray, error: np.ndarray, curves: pd.DataFrame) -> dict:
    finite = np.isfinite(uncertainty) & np.isfinite(error)
    rho = spearmanr(uncertainty[finite], error[finite]).statistic if finite.sum() >= 3 else np.nan
    curve = curves[(curves["dataset"] == dataset) & (curves["seed"] == seed) & (curves["uq_score"] == score_name)]
    risk_auc = float(np.trapezoid(curve["risk"].to_numpy(), curve["coverage"].to_numpy())) if not curve.empty else np.nan
    high_cut = np.quantile(error[finite], 0.90) if finite.any() else np.nan
    high_error = error >= high_cut
    top_k = max(1, int(np.ceil(0.10 * len(error))))
    top_uncertain = np.argsort(-np.nan_to_num(uncertainty, nan=-np.inf))[:top_k]
    prevalence = float(high_error.mean()) if len(high_error) else np.nan
    hit_rate = float(high_error[top_uncertain].mean()) if len(top_uncertain) else np.nan
    enrichment = hit_rate / prevalence if prevalence and np.isfinite(prevalence) else np.nan
    risk80 = curve.loc[np.isclose(curve["coverage"], 0.8), "risk"]
    return {
        "dataset": dataset,
        "seed": seed,
        "uq_score": score_name,
        "spearman_abs_error": float(rho) if np.isfinite(rho) else np.nan,
        "risk_coverage_auc": risk_auc,
        "risk_at_80pct_coverage": float(risk80.iloc[0]) if not risk80.empty else np.nan,
        "top10pct_high_error_enrichment": float(enrichment) if np.isfinite(enrichment) else np.nan,
    }


def build_for_selector(selector_dir: Path, output_dir: Path, replacements: dict[str, str], seeds: list[int] | None) -> None:
    chosen = pd.read_csv(selector_dir / "selected_candidates.csv")
    metric_rows: list[dict] = []
    curve_rows: list[dict] = []
    score_dump_rows: list[dict] = []
    for row in chosen.itertuples(index=False):
        dataset = str(row.dataset)
        candidate = str(row.selected_candidate)
        family = selected_family(candidate)
        if family not in selector.MEMBER_SETS:
            print(f"skip dataset={dataset} unknown family={family}", flush=True)
            continue
        frame, spec = load_dataset(dataset, data_dir=ROOT / "data")
        run_seeds = seeds or sorted(
            int(path.name.split("_seed")[-1].split("_")[0])
            for path in selector_dir.glob(f"{dataset}_validation_selector_seed*_predictions.csv")
        )
        members = [(replacements.get(report_dir, report_dir), model) for report_dir, model in selector.MEMBER_SETS[family]]
        for seed in run_seeds:
            candidates = selector.build_candidate_predictions(dataset, seed, family, members, spec.task_type, frame)
            matches = [item for item in candidates if item["candidate"] == candidate]
            if not matches:
                continue
            item = matches[0]
            valid = item["valid_select"].merge(item["valid_diagnostics"], on="smiles", how="left")
            test = item["test"].merge(item["test_diagnostics"], on="smiles", how="left")
            valid_error = error_values(valid, spec.task_type)
            test_error = error_values(test, spec.task_type)
            valid_mean = float(pd.to_numeric(valid["y_pred"], errors="coerce").mean())
            x_valid = numeric_feature_table(valid, spec.task_type, valid_mean=valid_mean)
            x_test = numeric_feature_table(test, spec.task_type, valid_mean=valid_mean)
            x_test = x_test.reindex(columns=x_valid.columns, fill_value=np.nan)
            error_model = fit_error_model(x_valid, valid_error, seed)
            scores = {
                "error_model": error_model.predict(x_test),
                "ensemble_std": pd.to_numeric(test["ensemble_std"], errors="coerce").to_numpy(dtype=float),
                "scaffold_distance": pd.to_numeric(test["scaffold_distance"], errors="coerce").to_numpy(dtype=float),
                "inverse_tanimoto": 1.0 - pd.to_numeric(test["max_train_tanimoto"], errors="coerce").to_numpy(dtype=float),
            }
            if spec.task_type == "classification":
                p = pd.to_numeric(test["y_pred"], errors="coerce").to_numpy(dtype=float)
                scores["confidence_uncertainty"] = 1.0 - np.abs(np.clip(p, 0.0, 1.0) - 0.5) * 2.0
            else:
                p = pd.to_numeric(test["y_pred"], errors="coerce").to_numpy(dtype=float)
                scores["prediction_deviation"] = np.abs(p - valid_mean)
            scores["hybrid_error_ad"] = (
                normalized(scores["error_model"])
                + normalized(scores["ensemble_std"])
                + normalized(scores["scaffold_distance"])
            ) / 3.0
            y_true = pd.to_numeric(test["y_true"], errors="coerce").to_numpy(dtype=float)
            y_pred = pd.to_numeric(test["y_pred"], errors="coerce").to_numpy(dtype=float)
            for name, values in scores.items():
                rows = risk_coverage_rows(dataset, seed, name, values, y_true, y_pred, spec.task_type)
                curve_rows.extend(rows)
                curves_now = pd.DataFrame(rows)
                metric_rows.append(score_metrics(dataset, seed, name, values, test_error, curves_now))
            dump = test[["smiles", "y_true", "y_pred"]].copy()
            dump.insert(0, "seed", seed)
            dump.insert(0, "dataset", dataset)
            for name, values in scores.items():
                dump[f"uq_{name}"] = values
            dump["abs_error"] = test_error
            score_dump_rows.extend(dump.to_dict("records"))
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics = pd.DataFrame(metric_rows)
    curves = pd.DataFrame(curve_rows)
    dumps = pd.DataFrame(score_dump_rows)
    metrics.to_csv(output_dir / "uq_score_metrics.csv", index=False)
    curves.to_csv(output_dir / "risk_coverage_curves.csv", index=False)
    dumps.to_csv(output_dir / "uq_scores_by_compound.csv", index=False)
    if not metrics.empty:
        summary = (
            metrics.groupby(["dataset", "uq_score"], dropna=False)
            .agg(["mean", "std"])
            .reset_index()
        )
        summary.to_csv(output_dir / "uq_score_summary.csv", index=False)
        fig_dir = output_dir / "figures"
        fig_dir.mkdir(exist_ok=True)
        for dataset, group in metrics.groupby("dataset"):
            plot_data = group.groupby("uq_score", as_index=False)["spearman_abs_error"].mean()
            plt.figure(figsize=(7.0, 3.8))
            plt.bar(plot_data["uq_score"], plot_data["spearman_abs_error"])
            plt.xticks(rotation=30, ha="right")
            plt.ylabel("Spearman with absolute error")
            plt.title(f"{dataset} UQ ranking")
            plt.tight_layout()
            plt.savefig(fig_dir / f"{dataset}_uq_spearman.png", dpi=220)
            plt.close()
    print(metrics.to_string(index=False) if not metrics.empty else "No UQ rows built.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build UNIQUE-style uncertainty/error-model reports.")
    parser.add_argument("--selector-dir", default=str(ROOT / "reports" / "validation_selector_expanded"))
    parser.add_argument("--output-dir", default=str(ROOT / "reports" / "unique_uq_expanded"))
    parser.add_argument("--core-report-dir", default="reports/strict_core_fast")
    parser.add_argument("--multifp-report-dir", default="reports/strict_multifp_fast")
    parser.add_argument("--chemprop-report-dir", default="reports/chemprop_baseline")
    parser.add_argument("--descriptor-motif-dir", default="reports/descriptor_motif_baselines")
    parser.add_argument("--seeds", nargs="*", type=int, default=None)
    args = parser.parse_args()
    replacements = {
        "reports/strict_core": args.core_report_dir,
        "reports/strict_multifp": args.multifp_report_dir,
        "reports/chemprop_baseline": args.chemprop_report_dir,
        "reports/descriptor_motif_baselines": args.descriptor_motif_dir,
    }
    build_for_selector(Path(args.selector_dir), Path(args.output_dir), replacements, args.seeds)


if __name__ == "__main__":
    main()
