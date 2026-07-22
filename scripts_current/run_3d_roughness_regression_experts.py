from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import time
import warnings
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from rdkit import RDLogger
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import QuantileTransformer


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import canonicalize_smiles, load_dataset
from fzyc_mol.evaluate import compute_metrics
from fzyc_mol.features import descriptor_vector, morgan_fingerprint
from fzyc_mol.splits import make_split


RDLogger.DisableLog("rdApp.*")
warnings.filterwarnings("ignore", message="X does not have valid feature names.*")

OUT_DIR = ROOT / "reports" / "three_d_roughness_regression_experts_20260603"
TABLE_DIR = ROOT / "reports" / "manuscript_tables"
FIG_DIR = ROOT / "reports" / "manuscript_figures_polished"

TABLE35_PATH = TABLE_DIR / "table35_3d_roughness_regression_retained_best.csv"
TABLE36_PATH = TABLE_DIR / "table36_3d_roughness_candidate_families.csv"
TABLE37_PATH = TABLE_DIR / "table37_3d_roughness_oracle_audit.csv"
FIG20_PATH = FIG_DIR / "fig20_3d_roughness_regression_gate"

MOLECULENET_DEFAULT = ["esol", "freesolv", "lipo"]
TDC_DEFAULT = [
    "caco2_wang",
    "clearance_hepatocyte_az",
    "clearance_microsome_az",
    "half_life_obach",
    "ppbr_az",
    "vdss_lombardo",
    "lipophilicity_astrazeneca",
]


class TargetTransform:
    def __init__(self, name: str, seed: int):
        self.name = name
        self.seed = seed
        self.low_: float | None = None
        self.high_: float | None = None
        self.quantile_: QuantileTransformer | None = None

    def available(self, y: np.ndarray) -> bool:
        y = np.asarray(y, dtype=float).reshape(-1)
        if self.name == "identity":
            return True
        if self.name == "log1p":
            return bool(np.nanmin(y) >= 0.0)
        if self.name in {"winsor", "quantile_normal"}:
            return len(np.unique(y)) > 5
        return False

    def fit(self, y: np.ndarray) -> "TargetTransform":
        y = np.asarray(y, dtype=float).reshape(-1)
        if self.name == "winsor":
            self.low_, self.high_ = np.nanquantile(y, [0.01, 0.99])
        elif self.name == "quantile_normal":
            n_quantiles = max(10, min(200, len(y)))
            self.quantile_ = QuantileTransformer(
                n_quantiles=n_quantiles,
                output_distribution="normal",
                random_state=self.seed,
            )
            self.quantile_.fit(y.reshape(-1, 1))
        return self

    def transform(self, y: np.ndarray) -> np.ndarray:
        y = np.asarray(y, dtype=float).reshape(-1)
        if self.name == "identity":
            return y
        if self.name == "log1p":
            return np.log1p(np.clip(y, 0.0, None))
        if self.name == "winsor":
            return np.clip(y, float(self.low_), float(self.high_))
        if self.name == "quantile_normal":
            return self.quantile_.transform(y.reshape(-1, 1)).reshape(-1)
        raise ValueError(self.name)

    def inverse(self, y: np.ndarray) -> np.ndarray:
        y = np.asarray(y, dtype=float).reshape(-1)
        if self.name in {"identity", "winsor"}:
            return y
        if self.name == "log1p":
            return np.expm1(y)
        if self.name == "quantile_normal":
            return self.quantile_.inverse_transform(y.reshape(-1, 1)).reshape(-1)
        raise ValueError(self.name)


def optional_dependency_status() -> dict[str, bool]:
    return {
        "xgboost": importlib.util.find_spec("xgboost") is not None,
        "catboost": importlib.util.find_spec("catboost") is not None,
    }


def parse_formatted_mean(value: object) -> float:
    match = re.search(r"[-+]?\d+(?:\.\d+)?", str(value))
    if not match:
        return float("nan")
    return float(match.group(0))


def parse_formatted_std(value: object) -> float:
    text = str(value)
    if "+/-" not in text:
        return float("nan")
    return parse_formatted_mean(text.split("+/-", 1)[1])


def clean_tdc_dataset(name: str) -> str:
    text = str(name)
    for token in ["tdc_"]:
        text = text.replace(token, "")
    return text


def metric_direction(metric: str) -> str:
    return "lower" if metric in {"rmse", "mae"} else "higher"


def positive_delta(direction: str, previous: float, current: float) -> float:
    return previous - current if direction == "lower" else current - previous


def feature_matrix(smiles: list[str], mode: str) -> np.ndarray:
    rows: list[np.ndarray] = []
    for smi in smiles:
        if mode == "morgan2d":
            rows.append(np.hstack([morgan_fingerprint(smi), descriptor_vector(smi, include_3d=False)]))
        elif mode == "morgan3d":
            rows.append(np.hstack([morgan_fingerprint(smi), descriptor_vector(smi, include_3d=True)]))
        elif mode == "desc2d":
            rows.append(descriptor_vector(smi, include_3d=False))
        elif mode == "desc3d":
            rows.append(descriptor_vector(smi, include_3d=True))
        else:
            raise ValueError(f"unknown feature mode {mode}")
    return np.nan_to_num(np.vstack(rows).astype(np.float32), copy=False)


def make_regressor(name: str, seed: int, n_estimators: int):
    if name == "lgbm":
        return LGBMRegressor(
            n_estimators=n_estimators,
            learning_rate=0.035,
            num_leaves=31,
            subsample=0.9,
            colsample_bytree=0.8,
            reg_lambda=2.0,
            random_state=seed,
            n_jobs=-1,
            verbose=-1,
        )
    if name == "lgbm_huber":
        return LGBMRegressor(
            objective="huber",
            alpha=0.9,
            n_estimators=n_estimators,
            learning_rate=0.035,
            num_leaves=31,
            subsample=0.9,
            colsample_bytree=0.8,
            reg_lambda=2.0,
            random_state=seed,
            n_jobs=-1,
            verbose=-1,
        )
    if name == "rf":
        return RandomForestRegressor(
            n_estimators=n_estimators,
            max_features="sqrt",
            min_samples_leaf=1,
            random_state=seed,
            n_jobs=-1,
        )
    if name == "extratrees":
        return ExtraTreesRegressor(
            n_estimators=n_estimators,
            max_features="sqrt",
            min_samples_leaf=1,
            random_state=seed,
            n_jobs=-1,
        )
    if name == "xgb":
        from xgboost import XGBRegressor

        return XGBRegressor(
            n_estimators=n_estimators,
            max_depth=5,
            learning_rate=0.04,
            subsample=0.9,
            colsample_bytree=0.8,
            reg_lambda=2.0,
            objective="reg:squarederror",
            tree_method="hist",
            random_state=seed,
            n_jobs=-1,
        )
    if name == "xgb_huber":
        from xgboost import XGBRegressor

        return XGBRegressor(
            n_estimators=n_estimators,
            max_depth=5,
            learning_rate=0.04,
            subsample=0.9,
            colsample_bytree=0.8,
            reg_lambda=2.0,
            objective="reg:pseudohubererror",
            tree_method="hist",
            random_state=seed,
            n_jobs=-1,
        )
    if name == "catboost":
        from catboost import CatBoostRegressor

        return CatBoostRegressor(
            iterations=n_estimators,
            learning_rate=0.04,
            depth=6,
            loss_function="RMSE",
            random_seed=seed,
            verbose=False,
            allow_writing_files=False,
        )
    raise ValueError(name)


def roughness_weights(smiles: list[str], y: np.ndarray, alpha: float) -> np.ndarray:
    y = np.asarray(y, dtype=float).reshape(-1)
    if alpha <= 0 or len(y) < 3:
        return np.ones(len(y), dtype=np.float32)
    fps = np.vstack([morgan_fingerprint(smi).astype(bool) for smi in smiles])
    nbrs = NearestNeighbors(n_neighbors=2, metric="jaccard", algorithm="brute", n_jobs=-1)
    nbrs.fit(fps)
    dist, idx = nbrs.kneighbors(fps)
    nn_idx = idx[:, 1]
    sim = np.clip(1.0 - dist[:, 1], 0.0, 1.0)
    iqr = float(np.nanquantile(y, 0.75) - np.nanquantile(y, 0.25))
    scale = iqr if iqr > 1e-8 else float(np.nanstd(y))
    if scale <= 1e-8:
        return np.ones(len(y), dtype=np.float32)
    jump = np.abs(y - y[nn_idx]) / scale
    rough = sim * np.clip(jump, 0.0, 5.0)
    if float(np.nanmean(rough)) > 1e-8:
        rough = rough / float(np.nanmean(rough))
    weights = 1.0 + alpha * rough
    weights = np.clip(weights, 0.25, 8.0)
    weights = weights / float(np.nanmean(weights))
    return weights.astype(np.float32)


def fit_candidate(
    model_name: str,
    transform_name: str,
    x_fit: np.ndarray,
    y_fit: np.ndarray,
    x_valid: np.ndarray,
    x_test: np.ndarray,
    seed: int,
    n_estimators: int,
    sample_weight: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, float]:
    transform = TargetTransform(transform_name, seed)
    if not transform.available(y_fit):
        raise ValueError(f"target transform {transform_name} unavailable")
    transform.fit(y_fit)
    y_trans = transform.transform(y_fit)
    model = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("model", make_regressor(model_name, seed, n_estimators)),
        ]
    )
    fit_kwargs = {}
    if sample_weight is not None:
        fit_kwargs["model__sample_weight"] = sample_weight
    start = time.perf_counter()
    model.fit(x_fit, y_trans, **fit_kwargs)
    fit_seconds = time.perf_counter() - start
    valid_pred = transform.inverse(model.predict(x_valid))
    test_pred = transform.inverse(model.predict(x_test))
    return valid_pred, test_pred, fit_seconds


def candidate_specs(deps: dict[str, bool], include_catboost: bool, transforms: list[str], alphas: list[float]) -> list[dict[str, object]]:
    tree_models = ["lgbm", "lgbm_huber", "extratrees", "rf"]
    if deps["xgboost"]:
        tree_models += ["xgb", "xgb_huber"]
    if deps["catboost"] and include_catboost:
        tree_models += ["catboost"]

    specs: list[dict[str, object]] = []
    for feature_mode in ["morgan3d", "desc3d"]:
        for model_name in tree_models:
            for transform in transforms:
                specs.append(
                    {
                        "candidate_family": "3d_lite",
                        "feature_mode": feature_mode,
                        "model_name": model_name,
                        "transform": transform,
                        "roughness_alpha": 0.0,
                    }
                )

    weighted_models = [name for name in ["lgbm", "lgbm_huber", "extratrees", "xgb", "xgb_huber"] if name in tree_models]
    for feature_mode in ["morgan2d", "morgan3d"]:
        for model_name in weighted_models:
            for transform in transforms:
                for alpha in alphas:
                    specs.append(
                        {
                            "candidate_family": "roughness_weighted",
                            "feature_mode": feature_mode,
                            "model_name": model_name,
                            "transform": transform,
                            "roughness_alpha": float(alpha),
                        }
                    )
    return specs


def make_candidate_row(
    source: str,
    dataset: str,
    family: str,
    seed: int,
    primary_metric: str,
    spec: dict[str, object],
    y_valid: np.ndarray,
    valid_pred: np.ndarray,
    y_test: np.ndarray,
    test_pred: np.ndarray,
    fit_seconds: float,
) -> dict[str, object]:
    valid_metrics = compute_metrics("regression", y_valid, valid_pred)
    test_metrics = compute_metrics("regression", y_test, test_pred)
    model = (
        f"{spec['candidate_family']}|{spec['feature_mode']}|{spec['model_name']}|"
        f"{spec['transform']}|a={float(spec['roughness_alpha']):.2f}"
    )
    return {
        "source": source,
        "dataset": dataset,
        "family": family,
        "task_type": "regression",
        "seed": int(seed),
        "primary_metric": primary_metric,
        "primary_direction": metric_direction(primary_metric),
        "candidate_family": spec["candidate_family"],
        "feature_mode": spec["feature_mode"],
        "model_name": spec["model_name"],
        "transform": spec["transform"],
        "roughness_alpha": float(spec["roughness_alpha"]),
        "model": model,
        "validation_primary": valid_metrics[primary_metric],
        "primary_value": test_metrics[primary_metric],
        "rmse": test_metrics["rmse"],
        "mae": test_metrics["mae"],
        "spearman": test_metrics["spearman"],
        "pearson": test_metrics["pearson"],
        "fit_seconds": float(fit_seconds),
    }


def select_seed(candidates: list[dict[str, object]], primary_metric: str) -> dict[str, object]:
    direction = metric_direction(primary_metric)
    reverse = direction == "higher"
    return sorted(candidates, key=lambda row: float(row["validation_primary"]), reverse=reverse)[0]


def load_tdc_task_metadata() -> pd.DataFrame:
    from tdc.metadata import admet_benchmark, admet_metrics, admet_splits

    rows = []
    for family, names in admet_benchmark.items():
        for name in names:
            metric = admet_metrics[name]
            if metric in {"roc-auc", "pr-auc"}:
                continue
            rows.append(
                {
                    "dataset": name,
                    "family": family,
                    "tdc_name": name,
                    "primary_metric": metric,
                    "official_split": admet_splits.get(name, "scaffold"),
                }
            )
    return pd.DataFrame(rows)


def normalize_tdc(raw: pd.DataFrame) -> pd.DataFrame:
    smiles_col = "Drug" if "Drug" in raw.columns else "smiles"
    target_col = "Y" if "Y" in raw.columns else "y"
    frame = raw[[smiles_col, target_col]].rename(columns={smiles_col: "smiles", target_col: "y"}).copy()
    frame["smiles"] = frame["smiles"].map(canonicalize_smiles)
    frame["y"] = pd.to_numeric(frame["y"], errors="coerce")
    return frame.dropna(subset=["smiles", "y"]).drop_duplicates("smiles").reset_index(drop=True)


def load_tdc_split(family: str, name: str, cache_dir: Path, split_method: str, seed: int):
    from tdc.single_pred import ADME, Tox

    loader = ADME if family == "ADME" else Tox
    data = loader(name=name, path=str(cache_dir))
    return data.get_split(method=split_method, seed=seed)


def run_candidate_pool(
    source: str,
    dataset: str,
    family: str,
    seed: int,
    primary_metric: str,
    train_smiles: list[str],
    valid_smiles: list[str],
    test_smiles: list[str],
    y_train: np.ndarray,
    y_valid: np.ndarray,
    y_test: np.ndarray,
    specs: list[dict[str, object]],
    n_estimators: int,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    feature_modes = sorted({str(spec["feature_mode"]) for spec in specs})
    x_cache = {
        mode: (
            feature_matrix(train_smiles, mode),
            feature_matrix(valid_smiles, mode),
            feature_matrix(test_smiles, mode),
        )
        for mode in feature_modes
    }
    alpha_cache = {
        float(alpha): roughness_weights(train_smiles, y_train, float(alpha))
        for alpha in sorted({float(spec["roughness_alpha"]) for spec in specs if float(spec["roughness_alpha"]) > 0})
    }
    rows: list[dict[str, object]] = []
    for spec in specs:
        mode = str(spec["feature_mode"])
        x_train, x_valid, x_test = x_cache[mode]
        alpha = float(spec["roughness_alpha"])
        sample_weight = alpha_cache.get(alpha)
        try:
            valid_pred, test_pred, fit_seconds = fit_candidate(
                str(spec["model_name"]),
                str(spec["transform"]),
                x_train,
                y_train,
                x_valid,
                x_test,
                seed,
                n_estimators,
                sample_weight=sample_weight,
            )
        except Exception as exc:
            print(
                f"candidate_error source={source} dataset={dataset} seed={seed} "
                f"model={spec['model_name']} feature={mode} transform={spec['transform']} "
                f"alpha={alpha}: {exc}",
                flush=True,
            )
            continue
        rows.append(
            make_candidate_row(
                source,
                dataset,
                family,
                seed,
                primary_metric,
                spec,
                y_valid,
                valid_pred,
                y_test,
                test_pred,
                fit_seconds,
            )
        )
    if not rows:
        raise RuntimeError(f"no candidate completed for {source}:{dataset}:{seed}")
    return rows, select_seed(rows, primary_metric)


def run_moleculenet_one(dataset: str, seed: int, specs: list[dict[str, object]], n_estimators: int):
    frame, _ = load_dataset(dataset, ROOT / "data")
    split = make_split(frame, "scaffold", seed)
    train = frame.iloc[split.train].reset_index(drop=True)
    valid = frame.iloc[split.valid].reset_index(drop=True)
    test = frame.iloc[split.test].reset_index(drop=True)
    return run_candidate_pool(
        "MoleculeNet",
        dataset,
        "MoleculeNet",
        seed,
        "rmse",
        train["smiles"].tolist(),
        valid["smiles"].tolist(),
        test["smiles"].tolist(),
        train["y"].to_numpy(dtype=float),
        valid["y"].to_numpy(dtype=float),
        test["y"].to_numpy(dtype=float),
        specs,
        n_estimators,
    )


def run_tdc_one(task: pd.Series, seed: int, cache_dir: Path, specs: list[dict[str, object]], n_estimators: int):
    split = load_tdc_split(str(task.family), str(task.tdc_name), cache_dir, str(task.official_split), seed)
    train = normalize_tdc(split["train"])
    valid = normalize_tdc(split["valid"])
    test = normalize_tdc(split["test"])
    return run_candidate_pool(
        "TDC",
        str(task.dataset),
        str(task.family),
        seed,
        str(task.primary_metric),
        train["smiles"].tolist(),
        valid["smiles"].tolist(),
        test["smiles"].tolist(),
        train["y"].to_numpy(dtype=float),
        valid["y"].to_numpy(dtype=float),
        test["y"].to_numpy(dtype=float),
        specs,
        n_estimators,
    )


def append_rows(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    header = not path.exists()
    frame.to_csv(path, mode="a", index=False, header=header)


def load_previous_lookup() -> dict[tuple[str, str], dict[str, object]]:
    previous: dict[tuple[str, str], dict[str, object]] = {}
    mn_path = TABLE_DIR / "table2_moleculenet_main.csv"
    if mn_path.exists():
        mn = pd.read_csv(mn_path)
        for _, row in mn[mn["task_type"].eq("regression")].iterrows():
            formatted = row["FZYC-Mol final retained-best"]
            previous[("MoleculeNet", str(row["dataset"]))] = {
                "previous_primary_mean": parse_formatted_mean(formatted),
                "previous_primary_std": parse_formatted_std(formatted),
                "previous_model": "FZYC-Mol final retained-best",
                "previous_source": "current_table2",
            }
    tdc_path = TABLE_DIR / "table15_tdc_performance_mode_retained_best.csv"
    if tdc_path.exists():
        tdc = pd.read_csv(tdc_path)
        for row in tdc[tdc["task_type"].eq("regression")].itertuples(index=False):
            previous[("TDC", str(row.dataset))] = {
                "previous_primary_mean": float(row.retained_primary_mean),
                "previous_primary_std": float(row.previous_primary_std) if not pd.isna(row.previous_primary_std) else np.nan,
                "previous_model": str(row.retained_model),
                "previous_source": str(row.retained_source),
            }
    return previous


def summarize(output_dir: Path) -> pd.DataFrame:
    selected_path = output_dir / "selected_metrics_raw.csv"
    candidate_path = output_dir / "candidate_metrics_raw.csv"
    if not selected_path.exists():
        raise FileNotFoundError(selected_path)
    selected = pd.read_csv(selected_path)
    candidates = pd.read_csv(candidate_path)
    previous = load_previous_lookup()

    summary_rows = []
    for (source, dataset), sub in selected.groupby(["source", "dataset"], sort=False):
        metric = str(sub["primary_metric"].iloc[0])
        direction = metric_direction(metric)
        mean = float(sub["primary_value"].mean())
        std = float(sub["primary_value"].std(ddof=1)) if len(sub) > 1 else np.nan
        validation_mean = float(sub["validation_primary"].mean())
        key = (str(source), str(dataset))
        previous_row = previous.get(key, {})
        prev_mean = float(previous_row.get("previous_primary_mean", np.nan))
        delta = positive_delta(direction, prev_mean, mean) if np.isfinite(prev_mean) else np.nan
        retained_source = "3d_roughness_regression_expert" if np.isfinite(delta) and delta > 0 else "previous_retained"
        retained_mean = mean if retained_source == "3d_roughness_regression_expert" else prev_mean
        counts = Counter(sub["model"].astype(str))
        family_counts = Counter(sub["candidate_family"].astype(str))
        summary_rows.append(
            {
                "source": source,
                "dataset": dataset,
                "family": sub["family"].iloc[0],
                "task_type": "regression",
                "primary_metric": metric,
                "primary_direction": direction,
                "n_seeds": int(sub["seed"].nunique()),
                "selected_model_counts": "; ".join(f"{k}:{v}" for k, v in counts.items()),
                "selected_family_counts": "; ".join(f"{k}:{v}" for k, v in family_counts.items()),
                "new_primary_mean": mean,
                "new_primary_std": std,
                "new_validation_primary_mean": validation_mean,
                "previous_primary_mean": prev_mean,
                "previous_primary_std": previous_row.get("previous_primary_std", np.nan),
                "previous_model": previous_row.get("previous_model", ""),
                "previous_source": previous_row.get("previous_source", ""),
                "delta_vs_previous": delta,
                "retained_source": retained_source,
                "retained_primary_mean": retained_mean,
                "retained_model": "; ".join(f"{k}:{v}" for k, v in counts.items()) if retained_source != "previous_retained" else previous_row.get("previous_model", ""),
            }
        )
    summary = pd.DataFrame(summary_rows).sort_values(["source", "dataset"]).reset_index(drop=True)
    TABLE35_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(TABLE35_PATH, index=False)
    summary.to_csv(output_dir / "retained_best_summary.csv", index=False)

    selected_keys = set(zip(selected["source"], selected["dataset"], selected["seed"], selected["model"]))
    candidates = candidates.copy()
    candidates["selected_seed"] = [
        (row.source, row.dataset, row.seed, row.model) in selected_keys for row in candidates.itertuples(index=False)
    ]
    group_cols = ["source", "dataset", "candidate_family", "feature_mode", "model_name", "transform", "roughness_alpha"]
    family_rows = []
    for keys, sub in candidates.groupby(group_cols, sort=False):
        family_rows.append(
            {
                **dict(zip(group_cols, keys)),
                "n_rows": int(len(sub)),
                "n_selected_seed": int(sub["selected_seed"].sum()),
                "validation_primary_mean": float(sub["validation_primary"].mean()),
                "primary_value_mean": float(sub["primary_value"].mean()),
                "primary_value_std": float(sub["primary_value"].std(ddof=1)) if len(sub) > 1 else np.nan,
                "rmse_mean": float(sub["rmse"].mean()),
                "mae_mean": float(sub["mae"].mean()),
                "spearman_mean": float(sub["spearman"].mean()),
                "fit_seconds_mean": float(sub["fit_seconds"].mean()),
            }
        )
    family_summary = pd.DataFrame(family_rows).sort_values(["source", "dataset", "n_selected_seed"], ascending=[True, True, False])
    family_summary.to_csv(TABLE36_PATH, index=False)
    family_summary.to_csv(output_dir / "candidate_family_summary.csv", index=False)
    oracle_rows = []
    for row in summary.itertuples(index=False):
        sub = candidates[(candidates["source"].eq(row.source)) & (candidates["dataset"].eq(row.dataset))].copy()
        if sub.empty:
            continue
        if row.primary_direction == "lower":
            best = sub.sort_values("primary_value", ascending=True).iloc[0]
        else:
            best = sub.sort_values("primary_value", ascending=False).iloc[0]
        oracle_delta = positive_delta(str(row.primary_direction), float(row.previous_primary_mean), float(best["primary_value"]))
        oracle_rows.append(
            {
                "source": row.source,
                "dataset": row.dataset,
                "primary_metric": row.primary_metric,
                "primary_direction": row.primary_direction,
                "previous_primary_mean": row.previous_primary_mean,
                "validation_selected_primary_mean": row.new_primary_mean,
                "validation_selected_delta_vs_previous": row.delta_vs_previous,
                "oracle_best_primary_value": float(best["primary_value"]),
                "oracle_delta_vs_previous": oracle_delta,
                "oracle_model": best["model"],
                "oracle_candidate_family": best["candidate_family"],
                "manuscript_use": "diagnostic only; not eligible for retained-best because selection would use test labels",
            }
        )
    oracle = pd.DataFrame(oracle_rows)
    oracle.to_csv(TABLE37_PATH, index=False)
    oracle.to_csv(output_dir / "oracle_audit.csv", index=False)
    write_readme(output_dir, summary)
    plot_decision(summary)
    return summary


def plot_decision(summary: pd.DataFrame) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    plot = summary.copy().sort_values("delta_vs_previous")
    labels = [f"{row.source}\n{row.dataset}\n{row.primary_metric.upper()}" for row in plot.itertuples(index=False)]
    deltas = plot["delta_vs_previous"].astype(float).to_numpy()
    colors = ["#1b8a6b" if value > 0 else "#d7dee8" for value in deltas]

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "figure.dpi": 180,
            "savefig.dpi": 320,
            "axes.edgecolor": "#cbd5e1",
            "axes.labelcolor": "#0f172a",
            "xtick.color": "#334155",
            "ytick.color": "#334155",
        }
    )
    fig, ax = plt.subplots(figsize=(10.2, 6.2))
    y_pos = np.arange(len(plot))
    ax.barh(y_pos, deltas, color=colors, edgecolor="white", height=0.58, linewidth=0.8)
    ax.axvline(0, color="#334155", lw=0.9)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=8.2)
    ax.set_xlabel("Positive delta vs current retained-best")
    ax.set_title("3D-lite and roughness-weighted regression gate", loc="left", fontsize=12.5, fontweight="bold", pad=12)
    ax.grid(axis="x", color="#e5e7eb", linewidth=0.65, alpha=0.85)
    ax.set_axisbelow(True)
    span = max(0.02, float(np.nanmax(np.abs(deltas))) * 0.13) if len(deltas) else 0.02
    for y, row, delta in zip(y_pos, plot.itertuples(index=False), deltas):
        text = f"{delta:+.3f} | {'promote' if delta > 0 else 'keep previous'}"
        x = delta + span * 0.25
        ax.text(x, y, text, ha="left", va="center", fontsize=8.4, color="#14532d" if delta > 0 else "#475569", fontweight="bold")
    max_abs = max(0.08, float(np.nanmax(np.abs(deltas))) + span) if len(deltas) else 0.08
    ax.set_xlim(-max_abs, max_abs)
    fig.text(
        0.125,
        0.03,
        "Green bars are promoted; gray bars keep the current retained-best. Lower RMSE/MAE and higher Spearman are converted to positive gain.",
        fontsize=8.3,
        color="#475569",
        ha="left",
        va="center",
    )
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color("#e2e8f0")
    ax.spines["bottom"].set_color("#e2e8f0")
    fig.tight_layout(rect=[0, 0.06, 1, 1])
    for ext in ["png", "svg"]:
        fig.savefig(FIG20_PATH.with_suffix(f".{ext}"), bbox_inches="tight")
    plt.close(fig)


def write_readme(output_dir: Path, summary: pd.DataFrame) -> None:
    lines = [
        "# 3D-lite and roughness-weighted regression experts",
        "",
        "This targeted appendix adds low-cost conformation-aware and roughness-weighted tree experts for low-score or high-roughness regression endpoints.",
        "",
        "Selection rule: candidates are selected by validation primary metric only. Test labels are used only after the seed-level validation choice is fixed.",
        "",
        "Outputs:",
        f"- Candidate raw metrics: `{output_dir / 'candidate_metrics_raw.csv'}`",
        f"- Selected raw metrics: `{output_dir / 'selected_metrics_raw.csv'}`",
        f"- Retained-best table: `{TABLE35_PATH}`",
        f"- Candidate-family table: `{TABLE36_PATH}`",
        f"- Oracle audit table: `{TABLE37_PATH}`",
        f"- Decision figure: `{FIG20_PATH.with_suffix('.png')}`",
        "",
        "Retained-best decisions:",
    ]
    for row in summary.itertuples(index=False):
        lines.append(
            f"- `{row.source}:{row.dataset}`: previous={row.previous_primary_mean:.4f}, "
            f"new={row.new_primary_mean:.4f}, delta={row.delta_vs_previous:+.4f}, "
            f"retained=`{row.retained_source}`."
        )
    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run targeted 3D-lite and roughness-weighted regression experts.")
    parser.add_argument("--moleculenet-datasets", nargs="*", default=MOLECULENET_DEFAULT)
    parser.add_argument("--tdc-datasets", nargs="*", default=TDC_DEFAULT)
    parser.add_argument("--moleculenet-seeds", nargs="*", type=int, default=[13, 17, 23, 29, 31])
    parser.add_argument("--tdc-seeds", nargs="*", type=int, default=[13, 17, 23])
    parser.add_argument("--tdc-cache-dir", default=str(ROOT / "data" / "tdc"))
    parser.add_argument("--output-dir", default=str(OUT_DIR))
    parser.add_argument("--n-estimators", type=int, default=140)
    parser.add_argument("--transforms", nargs="*", default=["identity", "winsor", "quantile_normal"])
    parser.add_argument("--roughness-alphas", nargs="*", type=float, default=[0.75, 1.5])
    parser.add_argument("--include-catboost", action="store_true")
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--no-resume", action="store_false", dest="resume")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    deps = optional_dependency_status()
    (output_dir / "dependency_status.json").write_text(json.dumps(deps, indent=2), encoding="utf-8")
    specs = candidate_specs(deps, args.include_catboost, args.transforms, args.roughness_alphas)
    moleculenet_datasets = [str(item) for item in args.moleculenet_datasets]
    tdc_datasets = [str(item) for item in args.tdc_datasets]
    if any(item.lower() in {"none", "skip", "-"} for item in moleculenet_datasets):
        moleculenet_datasets = []
    if any(item.lower() in {"none", "skip", "-"} for item in tdc_datasets):
        tdc_datasets = []

    selected_path = output_dir / "selected_metrics_raw.csv"
    if args.resume and selected_path.exists():
        existing = pd.read_csv(selected_path)
        done = {(str(row["source"]), str(row["dataset"]), int(row["seed"])) for row in existing.to_dict("records")}
    else:
        done = set()

    for dataset in moleculenet_datasets:
        for seed in args.moleculenet_seeds:
            key = ("MoleculeNet", str(dataset), int(seed))
            if key in done:
                print(f"skip source=MoleculeNet dataset={dataset} seed={seed}", flush=True)
                continue
            print(f"run source=MoleculeNet dataset={dataset} seed={seed}", flush=True)
            candidates, selected = run_moleculenet_one(str(dataset), int(seed), specs, args.n_estimators)
            append_rows(output_dir / "candidate_metrics_raw.csv", candidates)
            append_rows(selected_path, [selected])
            summarize(output_dir)

    tdc_tasks = load_tdc_task_metadata()
    if tdc_datasets:
        unknown = sorted(set(tdc_datasets) - set(tdc_tasks["dataset"]))
        if unknown:
            raise SystemExit(f"Unknown TDC regression dataset(s): {unknown}")
        tdc_tasks = tdc_tasks[tdc_tasks["dataset"].isin(tdc_datasets)].reset_index(drop=True)
    else:
        tdc_tasks = tdc_tasks.iloc[0:0].reset_index(drop=True)
    for task_tuple in tdc_tasks.itertuples(index=False):
        task = pd.Series(task_tuple._asdict())
        for seed in args.tdc_seeds:
            key = ("TDC", str(task.dataset), int(seed))
            if key in done:
                print(f"skip source=TDC dataset={task.dataset} seed={seed}", flush=True)
                continue
            print(f"run source=TDC dataset={task.dataset} seed={seed}", flush=True)
            candidates, selected = run_tdc_one(task, int(seed), Path(args.tdc_cache_dir), specs, args.n_estimators)
            append_rows(output_dir / "candidate_metrics_raw.csv", candidates)
            append_rows(selected_path, [selected])
            summarize(output_dir)

    summarize(output_dir)
    print(f"wrote {output_dir}", flush=True)


if __name__ == "__main__":
    main()
