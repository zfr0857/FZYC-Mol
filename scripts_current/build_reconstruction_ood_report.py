from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.decomposition import PCA
from sklearn.metrics import mean_squared_error
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.analysis import max_train_similarity
from fzyc_mol.datasets import load_dataset
from fzyc_mol.features import descriptor_vector, morgan_fingerprint
from fzyc_mol.splits import make_split


def parse_selector_path(path: Path) -> tuple[str, int] | None:
    match = re.match(r"(.+)_validation_selector_seed(\d+)_predictions\.csv$", path.name)
    if not match:
        return None
    return match.group(1), int(match.group(2))


def feature_matrix(smiles_list: list[str]) -> np.ndarray:
    rows = []
    for smiles in smiles_list:
        rows.append(np.hstack([morgan_fingerprint(smiles), descriptor_vector(smiles, include_3d=False)]))
    return np.vstack(rows).astype(np.float32)


def task_type_from_predictions(table: pd.DataFrame) -> str:
    y = table["y_true"].to_numpy()
    pred = table["y_pred"].to_numpy()
    if set(np.unique(y)).issubset({0, 1}) and np.nanmin(pred) >= 0.0 and np.nanmax(pred) <= 1.0:
        return "classification"
    return "regression"


def abs_error(table: pd.DataFrame, task_type: str) -> np.ndarray:
    y = table["y_true"].to_numpy(dtype=float)
    pred = table["y_pred"].to_numpy(dtype=float)
    if task_type == "classification":
        return np.abs(y - np.clip(pred, 1e-7, 1 - 1e-7))
    return np.abs(y - pred)


def risk_coverage(dataset: str, seed: int, score_name: str, score: np.ndarray, table: pd.DataFrame, task_type: str) -> pd.DataFrame:
    order = np.argsort(score)
    y = table["y_true"].to_numpy(dtype=float)
    pred = table["y_pred"].to_numpy(dtype=float)
    rows = []
    for coverage in np.linspace(0.1, 1.0, 10):
        keep = order[: max(1, int(round(len(order) * coverage)))]
        if task_type == "classification":
            risk = float(((pred[keep] >= 0.5).astype(int) != y[keep].astype(int)).mean())
            metric = "error_rate"
        else:
            risk = float(np.sqrt(mean_squared_error(y[keep], pred[keep])))
            metric = "rmse"
        rows.append(
            {
                "dataset": dataset,
                "seed": seed,
                "score": score_name,
                "coverage": float(coverage),
                "risk_metric": metric,
                "risk": risk,
            }
        )
    return pd.DataFrame(rows)


def build_one(dataset: str, seed: int, pred_path: Path, n_components: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    frame, _spec = load_dataset(dataset, data_dir=ROOT / "data")
    split = make_split(frame, "scaffold", seed)
    predictions = pd.read_csv(pred_path)
    task_type = task_type_from_predictions(predictions)
    train_smiles = frame.iloc[split.train]["smiles"].tolist()
    x_train = feature_matrix(train_smiles)
    x_test = feature_matrix(predictions["smiles"].tolist())
    scaler = StandardScaler(with_mean=False)
    x_train_s = scaler.fit_transform(x_train)
    x_test_s = scaler.transform(x_test)
    comps = max(2, min(n_components, x_train_s.shape[0] - 1, x_train_s.shape[1] - 1))
    pca = PCA(n_components=comps, svd_solver="randomized", random_state=seed)
    z_train = pca.fit_transform(x_train_s)
    recon_train = pca.inverse_transform(z_train)
    z_test = pca.transform(x_test_s)
    recon_test = pca.inverse_transform(z_test)
    train_error = np.mean((x_train_s - recon_train) ** 2, axis=1)
    recon_error = np.mean((x_test_s - recon_test) ** 2, axis=1)
    similarity = max_train_similarity(train_smiles, predictions["smiles"].tolist())
    err = abs_error(predictions, task_type)
    scores = {
        "reconstruction_error": recon_error,
        "inverse_tanimoto": 1.0 - similarity,
        "hybrid_recon_ad": (rank01(recon_error) + rank01(1.0 - similarity)) / 2.0,
    }
    metric_rows = []
    curve_rows = []
    for name, values in scores.items():
        rho = spearmanr(values, err, nan_policy="omit").statistic if len(values) >= 3 else np.nan
        curve = risk_coverage(dataset, seed, name, values, predictions, task_type)
        curve_rows.append(curve)
        risk_auc = float(np.trapezoid(curve["risk"].to_numpy(), curve["coverage"].to_numpy()))
        high_cut = np.quantile(err, 0.90)
        high = err >= high_cut
        top = np.argsort(-values)[: max(1, int(np.ceil(0.10 * len(values))))]
        enrichment = float(high[top].mean() / high.mean()) if high.mean() > 0 else np.nan
        metric_rows.append(
            {
                "dataset": dataset,
                "seed": seed,
                "task_type": task_type,
                "score": name,
                "n_components": comps,
                "train_reconstruction_error_mean": float(np.mean(train_error)),
                "test_reconstruction_error_mean": float(np.mean(recon_error)),
                "spearman_abs_error": float(rho) if np.isfinite(rho) else np.nan,
                "risk_coverage_auc": risk_auc,
                "top10pct_high_error_enrichment": enrichment,
            }
        )
    dump = predictions.copy()
    dump.insert(0, "seed", seed)
    dump.insert(0, "dataset", dataset)
    dump["reconstruction_error"] = recon_error
    dump["max_train_tanimoto"] = similarity
    dump["abs_error"] = err
    return pd.DataFrame(metric_rows), pd.concat(curve_rows, ignore_index=True), dump


def rank01(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.linspace(0.0, 1.0, len(values))
    return ranks


def plot_summary(metrics: pd.DataFrame, output_dir: Path) -> None:
    fig_dir = output_dir / "figures"
    fig_dir.mkdir(exist_ok=True)
    if metrics.empty:
        return
    for dataset, group in metrics.groupby("dataset"):
        plot = group.groupby("score", as_index=False)["spearman_abs_error"].mean()
        plt.figure(figsize=(5.8, 3.5))
        plt.bar(plot["score"], plot["spearman_abs_error"])
        plt.xticks(rotation=25, ha="right")
        plt.ylabel("Spearman with absolute error")
        plt.title(f"{dataset} reconstruction OOD")
        plt.tight_layout()
        plt.savefig(fig_dir / f"{dataset}_reconstruction_ood.png", dpi=220)
        plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build reconstruction-based unfamiliarity/OOD report.")
    parser.add_argument("--selector-dir", default=str(ROOT / "reports" / "validation_selector_plus_descriptor_motif"))
    parser.add_argument("--output-dir", default=str(ROOT / "reports" / "reconstruction_ood"))
    parser.add_argument("--n-components", type=int, default=64)
    args = parser.parse_args()
    selector_dir = Path(args.selector_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics = []
    curves = []
    dumps = []
    for path in selector_dir.glob("*_validation_selector_seed*_predictions.csv"):
        parsed = parse_selector_path(path)
        if parsed is None:
            continue
        dataset, seed = parsed
        print(f"start dataset={dataset} seed={seed}", flush=True)
        metric, curve, dump = build_one(dataset, seed, path, args.n_components)
        metrics.append(metric)
        curves.append(curve)
        dumps.append(dump)
    metric_df = pd.concat(metrics, ignore_index=True) if metrics else pd.DataFrame()
    curve_df = pd.concat(curves, ignore_index=True) if curves else pd.DataFrame()
    dump_df = pd.concat(dumps, ignore_index=True) if dumps else pd.DataFrame()
    metric_df.to_csv(output_dir / "reconstruction_ood_metrics.csv", index=False)
    curve_df.to_csv(output_dir / "reconstruction_ood_risk_coverage.csv", index=False)
    dump_df.to_csv(output_dir / "reconstruction_ood_by_compound.csv", index=False)
    if not metric_df.empty:
        id_cols = {"dataset", "score", "task_type"}
        metric_cols = [
            col
            for col in metric_df.columns
            if col not in id_cols and pd.api.types.is_numeric_dtype(metric_df[col])
        ]
        summary = (
            metric_df.groupby(["dataset", "score"], dropna=False)[metric_cols]
            .agg(["mean", "std"])
            .reset_index()
        )
        summary.to_csv(output_dir / "reconstruction_ood_summary.csv", index=False)
        plot_summary(metric_df, output_dir)
    print(metric_df.to_string(index=False) if not metric_df.empty else "No selector predictions found.")


if __name__ == "__main__":
    main()
