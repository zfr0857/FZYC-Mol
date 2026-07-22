from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from rdkit import RDLogger
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.analysis import max_train_similarity
from fzyc_mol.datasets import DATASETS, load_dataset
from fzyc_mol.evaluate import compute_metrics
from fzyc_mol.splits import make_split


RDLogger.DisableLog("rdApp.*")

SEEDS = [13, 17, 23, 29, 31]
SIMILARITY_CACHE: dict[tuple[str, int], pd.Series] = {}

MEMBER_SETS = {
    "multifp_only": [
        ("reports/strict_multifp", "rf_multifp"),
        ("reports/strict_multifp", "xgb_multifp"),
        ("reports/strict_multifp", "lgbm_multifp"),
        ("reports/strict_multifp", "extratrees_multifp"),
    ],
    "strict_core": [
        ("reports/strict_core", "rf_morgan"),
        ("reports/strict_core", "xgb_morgan"),
        ("reports/strict_core", "lgbm_morgan"),
        ("reports/strict_core", "gin"),
        ("reports/strict_core", "dmpnn"),
        ("reports/strict_core", "fzyc_mol_static"),
    ],
    "strict_graph": [
        ("reports/strict_core", "rf_morgan"),
        ("reports/strict_core", "xgb_morgan"),
        ("reports/strict_core", "lgbm_morgan"),
        ("reports/strict_core", "gin"),
        ("reports/strict_core", "dmpnn"),
        ("reports/strict_core", "fzyc_mol_static"),
        ("reports/strict_core", "fzyc_mol_gt"),
    ],
    "strict_core_chemberta": [
        ("reports/strict_core", "rf_morgan"),
        ("reports/strict_core", "xgb_morgan"),
        ("reports/strict_core", "lgbm_morgan"),
        ("reports/strict_core", "gin"),
        ("reports/strict_core", "dmpnn"),
        ("reports/strict_core", "fzyc_mol_static"),
        ("reports/pretrained_frozen", "DeepChem_ChemBERTa-77M-MTR_frozen_head"),
    ],
    "strict_core_chemberta_rdkit": [
        ("reports/strict_core", "rf_morgan"),
        ("reports/strict_core", "xgb_morgan"),
        ("reports/strict_core", "lgbm_morgan"),
        ("reports/strict_core", "gin"),
        ("reports/strict_core", "dmpnn"),
        ("reports/strict_core", "fzyc_mol_static"),
        ("reports/pretrained_rdkit", "DeepChem_ChemBERTa-77M-MTR_rdkit_head"),
    ],
    "strict_core_multifp": [
        ("reports/strict_core", "rf_morgan"),
        ("reports/strict_core", "xgb_morgan"),
        ("reports/strict_core", "lgbm_morgan"),
        ("reports/strict_core", "gin"),
        ("reports/strict_core", "dmpnn"),
        ("reports/strict_core", "fzyc_mol_static"),
        ("reports/strict_multifp", "rf_multifp"),
        ("reports/strict_multifp", "xgb_multifp"),
        ("reports/strict_multifp", "lgbm_multifp"),
        ("reports/strict_multifp", "extratrees_multifp"),
    ],
    "strict_core_multifp_chemprop": [
        ("reports/strict_core", "rf_morgan"),
        ("reports/strict_core", "xgb_morgan"),
        ("reports/strict_core", "lgbm_morgan"),
        ("reports/strict_core", "gin"),
        ("reports/strict_core", "dmpnn"),
        ("reports/strict_core", "fzyc_mol_static"),
        ("reports/strict_multifp", "rf_multifp"),
        ("reports/strict_multifp", "xgb_multifp"),
        ("reports/strict_multifp", "lgbm_multifp"),
        ("reports/strict_multifp", "extratrees_multifp"),
        ("reports/chemprop_baseline", "chemprop_dmpnn_ens3"),
        ("reports/chemprop_baseline", "chemprop_rdkit_ens3"),
    ],
    "strict_core_multifp_pretrained": [
        ("reports/strict_core", "rf_morgan"),
        ("reports/strict_core", "xgb_morgan"),
        ("reports/strict_core", "lgbm_morgan"),
        ("reports/strict_core", "gin"),
        ("reports/strict_core", "dmpnn"),
        ("reports/strict_core", "fzyc_mol_static"),
        ("reports/strict_multifp", "rf_multifp"),
        ("reports/strict_multifp", "xgb_multifp"),
        ("reports/strict_multifp", "lgbm_multifp"),
        ("reports/strict_multifp", "extratrees_multifp"),
        ("reports/pretrained_frozen", "DeepChem_ChemBERTa-77M-MTR_frozen_head"),
        ("reports/pretrained_rdkit", "DeepChem_ChemBERTa-77M-MTR_rdkit_head"),
        ("reports/pretrained_frozen_mlm", "DeepChem_ChemBERTa-77M-MLM_frozen_head"),
        ("reports/pretrained_rdkit_mlm", "DeepChem_ChemBERTa-77M-MLM_rdkit_head"),
        ("reports/pretrained_frozen_molformer", "ibm_MoLFormer-XL-both-10pct_frozen_head"),
        ("reports/pretrained_rdkit_molformer", "ibm_MoLFormer-XL-both-10pct_rdkit_head"),
    ],
    "strict_core_q1_all": [
        ("reports/strict_core", "rf_morgan"),
        ("reports/strict_core", "xgb_morgan"),
        ("reports/strict_core", "lgbm_morgan"),
        ("reports/strict_core", "gin"),
        ("reports/strict_core", "dmpnn"),
        ("reports/strict_core", "fzyc_mol_static"),
        ("reports/strict_multifp", "rf_multifp"),
        ("reports/strict_multifp", "xgb_multifp"),
        ("reports/strict_multifp", "lgbm_multifp"),
        ("reports/strict_multifp", "extratrees_multifp"),
        ("reports/chemprop_baseline", "chemprop_dmpnn_ens3"),
        ("reports/chemprop_baseline", "chemprop_rdkit_ens3"),
        ("reports/pretrained_frozen", "DeepChem_ChemBERTa-77M-MTR_frozen_head"),
        ("reports/pretrained_rdkit", "DeepChem_ChemBERTa-77M-MTR_rdkit_head"),
        ("reports/pretrained_frozen_mlm", "DeepChem_ChemBERTa-77M-MLM_frozen_head"),
        ("reports/pretrained_rdkit_mlm", "DeepChem_ChemBERTa-77M-MLM_rdkit_head"),
        ("reports/pretrained_frozen_molformer", "ibm_MoLFormer-XL-both-10pct_frozen_head"),
        ("reports/pretrained_rdkit_molformer", "ibm_MoLFormer-XL-both-10pct_rdkit_head"),
    ],
    "q1_no_core": [
        ("reports/strict_multifp", "rf_multifp"),
        ("reports/strict_multifp", "xgb_multifp"),
        ("reports/strict_multifp", "lgbm_multifp"),
        ("reports/strict_multifp", "extratrees_multifp"),
        ("reports/chemprop_baseline", "chemprop_dmpnn_ens3"),
        ("reports/chemprop_baseline", "chemprop_rdkit_ens3"),
        ("reports/pretrained_frozen", "DeepChem_ChemBERTa-77M-MTR_frozen_head"),
        ("reports/pretrained_rdkit", "DeepChem_ChemBERTa-77M-MTR_rdkit_head"),
        ("reports/pretrained_frozen_mlm", "DeepChem_ChemBERTa-77M-MLM_frozen_head"),
        ("reports/pretrained_rdkit_mlm", "DeepChem_ChemBERTa-77M-MLM_rdkit_head"),
        ("reports/pretrained_frozen_molformer", "ibm_MoLFormer-XL-both-10pct_frozen_head"),
        ("reports/pretrained_rdkit_molformer", "ibm_MoLFormer-XL-both-10pct_rdkit_head"),
    ],
    "q1_no_multifp": [
        ("reports/strict_core", "rf_morgan"),
        ("reports/strict_core", "xgb_morgan"),
        ("reports/strict_core", "lgbm_morgan"),
        ("reports/strict_core", "gin"),
        ("reports/strict_core", "dmpnn"),
        ("reports/strict_core", "fzyc_mol_static"),
        ("reports/chemprop_baseline", "chemprop_dmpnn_ens3"),
        ("reports/chemprop_baseline", "chemprop_rdkit_ens3"),
        ("reports/pretrained_frozen", "DeepChem_ChemBERTa-77M-MTR_frozen_head"),
        ("reports/pretrained_rdkit", "DeepChem_ChemBERTa-77M-MTR_rdkit_head"),
        ("reports/pretrained_frozen_mlm", "DeepChem_ChemBERTa-77M-MLM_frozen_head"),
        ("reports/pretrained_rdkit_mlm", "DeepChem_ChemBERTa-77M-MLM_rdkit_head"),
        ("reports/pretrained_frozen_molformer", "ibm_MoLFormer-XL-both-10pct_frozen_head"),
        ("reports/pretrained_rdkit_molformer", "ibm_MoLFormer-XL-both-10pct_rdkit_head"),
    ],
    "q1_no_chemprop": [
        ("reports/strict_core", "rf_morgan"),
        ("reports/strict_core", "xgb_morgan"),
        ("reports/strict_core", "lgbm_morgan"),
        ("reports/strict_core", "gin"),
        ("reports/strict_core", "dmpnn"),
        ("reports/strict_core", "fzyc_mol_static"),
        ("reports/strict_multifp", "rf_multifp"),
        ("reports/strict_multifp", "xgb_multifp"),
        ("reports/strict_multifp", "lgbm_multifp"),
        ("reports/strict_multifp", "extratrees_multifp"),
        ("reports/pretrained_frozen", "DeepChem_ChemBERTa-77M-MTR_frozen_head"),
        ("reports/pretrained_rdkit", "DeepChem_ChemBERTa-77M-MTR_rdkit_head"),
        ("reports/pretrained_frozen_mlm", "DeepChem_ChemBERTa-77M-MLM_frozen_head"),
        ("reports/pretrained_rdkit_mlm", "DeepChem_ChemBERTa-77M-MLM_rdkit_head"),
        ("reports/pretrained_frozen_molformer", "ibm_MoLFormer-XL-both-10pct_frozen_head"),
        ("reports/pretrained_rdkit_molformer", "ibm_MoLFormer-XL-both-10pct_rdkit_head"),
    ],
    "q1_no_pretrained": [
        ("reports/strict_core", "rf_morgan"),
        ("reports/strict_core", "xgb_morgan"),
        ("reports/strict_core", "lgbm_morgan"),
        ("reports/strict_core", "gin"),
        ("reports/strict_core", "dmpnn"),
        ("reports/strict_core", "fzyc_mol_static"),
        ("reports/strict_multifp", "rf_multifp"),
        ("reports/strict_multifp", "xgb_multifp"),
        ("reports/strict_multifp", "lgbm_multifp"),
        ("reports/strict_multifp", "extratrees_multifp"),
        ("reports/chemprop_baseline", "chemprop_dmpnn_ens3"),
        ("reports/chemprop_baseline", "chemprop_rdkit_ens3"),
    ],
    "chemprop_only": [
        ("reports/chemprop_baseline", "chemprop_dmpnn_ens3"),
        ("reports/chemprop_baseline", "chemprop_rdkit_ens3"),
    ],
    "pretrained_only": [
        ("reports/pretrained_frozen", "DeepChem_ChemBERTa-77M-MTR_frozen_head"),
        ("reports/pretrained_rdkit", "DeepChem_ChemBERTa-77M-MTR_rdkit_head"),
        ("reports/pretrained_frozen_mlm", "DeepChem_ChemBERTa-77M-MLM_frozen_head"),
        ("reports/pretrained_rdkit_mlm", "DeepChem_ChemBERTa-77M-MLM_rdkit_head"),
        ("reports/pretrained_frozen_molformer", "ibm_MoLFormer-XL-both-10pct_frozen_head"),
        ("reports/pretrained_rdkit_molformer", "ibm_MoLFormer-XL-both-10pct_rdkit_head"),
    ],
    "strict_chemberta": [
        ("reports/strict_core", "rf_morgan"),
        ("reports/strict_core", "xgb_morgan"),
        ("reports/strict_core", "lgbm_morgan"),
        ("reports/strict_core", "gin"),
        ("reports/strict_core", "dmpnn"),
        ("reports/strict_core", "fzyc_mol_static"),
        ("reports/strict_core", "fzyc_mol_gt"),
        ("reports/pretrained_frozen", "DeepChem_ChemBERTa-77M-MTR_frozen_head"),
    ],
    "strict_chemberta_rdkit": [
        ("reports/strict_core", "rf_morgan"),
        ("reports/strict_core", "xgb_morgan"),
        ("reports/strict_core", "lgbm_morgan"),
        ("reports/strict_core", "gin"),
        ("reports/strict_core", "dmpnn"),
        ("reports/strict_core", "fzyc_mol_static"),
        ("reports/strict_core", "fzyc_mol_gt"),
        ("reports/pretrained_rdkit", "DeepChem_ChemBERTa-77M-MTR_rdkit_head"),
    ],
    "strict_all_experts": [
        ("reports/strict_core", "rf_morgan"),
        ("reports/strict_core", "xgb_morgan"),
        ("reports/strict_core", "lgbm_morgan"),
        ("reports/strict_core", "gin"),
        ("reports/strict_core", "dmpnn"),
        ("reports/strict_core", "fzyc_mol_static"),
        ("reports/strict_core", "fzyc_mol_gt"),
        ("reports/pretrained_frozen", "DeepChem_ChemBERTa-77M-MTR_frozen_head"),
        ("reports/pretrained_rdkit", "DeepChem_ChemBERTa-77M-MTR_rdkit_head"),
    ],
}

DESCRIPTOR_MOTIF_MEMBERS = [
    ("reports/descriptor_motif_baselines", "descriptor_mlp"),
    ("reports/descriptor_motif_baselines", "rf_motif"),
    ("reports/descriptor_motif_baselines", "xgb_motif"),
    ("reports/descriptor_motif_baselines", "lgbm_motif"),
    ("reports/descriptor_motif_baselines", "extratrees_motif"),
]

MEMBER_SETS.update(
    {
        "descriptor_mlp_only": [("reports/descriptor_motif_baselines", "descriptor_mlp")],
        "motif_only": DESCRIPTOR_MOTIF_MEMBERS[1:],
        "q1_plus_descriptor_motif": MEMBER_SETS["strict_core_q1_all"] + DESCRIPTOR_MOTIF_MEMBERS,
    }
)


class ConstantProbability:
    def __init__(self, value: float) -> None:
        self.value = float(np.clip(value, 1e-7, 1.0 - 1e-7))

    def predict_proba(self, x):
        prob = np.full((len(x),), self.value, dtype=np.float64)
        return np.column_stack([1.0 - prob, prob])


class ConstantRegressor:
    def __init__(self, value: float) -> None:
        self.value = float(value)

    def predict(self, x):
        return np.full((len(x),), self.value, dtype=np.float64)


def _as_probability(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    if values.min() >= 0.0 and values.max() <= 1.0:
        return np.clip(values, 1e-7, 1.0 - 1e-7)
    return 1.0 / (1.0 + np.exp(-np.clip(values, -60.0, 60.0)))


def regression_clip_bounds(y_true: np.ndarray) -> tuple[float, float]:
    values = np.asarray(y_true, dtype=np.float64)
    values = values[np.isfinite(values)]
    lower = float(np.min(values))
    upper = float(np.max(values))
    span = max(upper - lower, 1e-6)
    q1, q3 = np.quantile(values, [0.25, 0.75])
    iqr = max(float(q3 - q1), 1e-6)
    margin = max(0.25 * span, 1.5 * iqr)
    return lower - margin, upper + margin


def clip_regression_columns(
    table: pd.DataFrame,
    pred_cols: list[str],
    bounds: tuple[float, float],
) -> tuple[pd.DataFrame, int]:
    lower, upper = bounds
    out = table.copy()
    clipped = 0
    fallback = 0.5 * (lower + upper)
    for col in pred_cols:
        values = pd.to_numeric(out[col], errors="coerce").to_numpy(dtype=np.float64)
        finite = np.nan_to_num(values, nan=fallback, posinf=upper, neginf=lower)
        clipped += int(np.sum((finite < lower) | (finite > upper) | ~np.isfinite(values)))
        out[col] = np.clip(finite, lower, upper)
    return out, clipped


def finalize_predictions(
    task_type: str,
    values: np.ndarray,
    bounds: tuple[float, float] | None,
) -> np.ndarray:
    pred = np.asarray(values, dtype=np.float64)
    if task_type == "classification":
        return np.clip(_as_probability(pred), 1e-7, 1.0 - 1e-7)
    if bounds is None:
        fallback = float(np.nanmean(pred))
        return np.nan_to_num(pred, nan=fallback)
    lower, upper = bounds
    fallback = 0.5 * (lower + upper)
    pred = np.nan_to_num(pred, nan=fallback, posinf=upper, neginf=lower)
    return np.clip(pred, lower, upper)


def _prediction_path(report_dir: Path, dataset: str, model: str, seed: int, split_tag: str) -> Path:
    suffix = "_valid_predictions.csv" if split_tag == "valid" else "_predictions.csv"
    return report_dir / f"{dataset}_{model}_seed{seed}{suffix}"


def load_member_predictions(
    dataset: str,
    seed: int,
    members: list[tuple[str, str]],
    task_type: str,
    split_tag: str,
) -> tuple[pd.DataFrame, list[str]]:
    merged: pd.DataFrame | None = None
    pred_cols: list[str] = []
    for report_dir, model in members:
        path = _prediction_path(ROOT / report_dir, dataset, model, seed, split_tag)
        if not path.exists():
            raise FileNotFoundError(path)
        frame = pd.read_csv(path)[["smiles", "y_true", "y_pred"]].copy()
        if task_type == "classification":
            frame["y_pred"] = _as_probability(frame["y_pred"].to_numpy())
        col = f"pred_{model}"
        frame = frame.rename(columns={"y_pred": col})
        pred_cols.append(col)
        if merged is None:
            merged = frame
        else:
            merged = merged.merge(frame[["smiles", col]], on="smiles", how="inner")
    if merged is None:
        raise ValueError("No members provided.")
    return merged, pred_cols


def add_applicability_features(
    dataset: str,
    table: pd.DataFrame,
    frame: pd.DataFrame,
    seed: int,
    pred_cols: list[str],
) -> pd.DataFrame:
    key = (dataset, seed)
    if key not in SIMILARITY_CACHE:
        split = make_split(frame, "scaffold", seed)
        train_smiles = frame.iloc[split.train]["smiles"].tolist()
        sims = max_train_similarity(train_smiles, frame["smiles"].tolist())
        SIMILARITY_CACHE[key] = pd.Series(sims, index=frame["smiles"].tolist())
    out = table.copy()
    pred_matrix = out[pred_cols].to_numpy(dtype=np.float64)
    out["ensemble_mean"] = pred_matrix.mean(axis=1)
    out["ensemble_std"] = pred_matrix.std(axis=1)
    out["ensemble_range"] = pred_matrix.max(axis=1) - pred_matrix.min(axis=1)
    out["max_train_tanimoto"] = out["smiles"].map(SIMILARITY_CACHE[key]).fillna(0.0).astype(float)
    out["scaffold_distance"] = 1.0 - out["max_train_tanimoto"]
    return out


def feature_columns(pred_cols: list[str]) -> list[str]:
    return pred_cols + [
        "ensemble_mean",
        "ensemble_std",
        "ensemble_range",
        "max_train_tanimoto",
        "scaffold_distance",
    ]


def stratified_meta_split(valid: pd.DataFrame, task_type: str, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed + 20260525)
    fit: list[int] = []
    select: list[int] = []
    if task_type == "classification" and valid["y_true"].nunique() == 2:
        for _, group in valid.groupby("y_true"):
            idx = group.index.to_numpy()
            rng.shuffle(idx)
            cut = max(1, len(idx) // 2)
            fit.extend(idx[:cut].tolist())
            select.extend(idx[cut:].tolist())
    else:
        idx = valid.index.to_numpy()
        rng.shuffle(idx)
        cut = max(1, len(idx) // 2)
        fit.extend(idx[:cut].tolist())
        select.extend(idx[cut:].tolist())
    if not select:
        select = fit.copy()
    return np.asarray(sorted(fit), dtype=int), np.asarray(sorted(select), dtype=int)


def fit_stacker(task_type: str, train: pd.DataFrame, pred_cols: list[str]):
    x = train[feature_columns(pred_cols)].to_numpy(dtype=np.float64)
    y = train["y_true"].to_numpy(dtype=np.float64)
    if task_type == "regression":
        if len(train) < 3:
            return ConstantRegressor(float(np.mean(y)))
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                ("model", RidgeCV(alphas=np.logspace(-4, 4, 17))),
            ]
        ).fit(x, y)
    if len(np.unique(y.astype(int))) < 2:
        return ConstantProbability(float(np.mean(y)))
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced",
                    random_state=61453,
                ),
            ),
        ]
    ).fit(x, y.astype(int))


def predict_stacker(model, task_type: str, table: pd.DataFrame, pred_cols: list[str]) -> np.ndarray:
    x = table[feature_columns(pred_cols)].to_numpy(dtype=np.float64)
    if task_type == "classification":
        return model.predict_proba(x)[:, 1]
    return model.predict(x)


def fit_error_models(task_type: str, train: pd.DataFrame, pred_cols: list[str]) -> list[RandomForestRegressor]:
    x = train[feature_columns(pred_cols)].to_numpy(dtype=np.float64)
    y = train["y_true"].to_numpy(dtype=np.float64)
    models: list[RandomForestRegressor] = []
    for i, col in enumerate(pred_cols):
        pred = train[col].to_numpy(dtype=np.float64)
        target = np.abs(y - pred)
        model = RandomForestRegressor(
            n_estimators=80,
            min_samples_leaf=max(1, min(6, len(train) // 20)),
            random_state=9013 + i,
            n_jobs=-1,
        )
        model.fit(x, target)
        models.append(model)
    return models


def adaptive_predict(
    task_type: str,
    train: pd.DataFrame,
    table: pd.DataFrame,
    pred_cols: list[str],
) -> tuple[np.ndarray, pd.DataFrame]:
    if len(train) < max(5, len(pred_cols) + 2):
        weights = np.full((len(table), len(pred_cols)), 1.0 / len(pred_cols), dtype=np.float64)
        preds = table[pred_cols].to_numpy(dtype=np.float64)
        diagnostics = table[["smiles", "max_train_tanimoto", "scaffold_distance", "ensemble_std"]].copy()
        return (weights * preds).sum(axis=1), diagnostics
    models = fit_error_models(task_type, train, pred_cols)
    x = table[feature_columns(pred_cols)].to_numpy(dtype=np.float64)
    expected = np.column_stack([np.clip(model.predict(x), 1e-6, None) for model in models])
    weights = 1.0 / expected
    weights = weights / weights.sum(axis=1, keepdims=True)
    preds = table[pred_cols].to_numpy(dtype=np.float64)
    y_pred = (weights * preds).sum(axis=1)
    diagnostics = table[["smiles", "max_train_tanimoto", "scaffold_distance", "ensemble_std"]].copy()
    for col, values in zip(pred_cols, weights.T):
        diagnostics[f"weight_{col.replace('pred_', '')}"] = values
    return y_pred, diagnostics


def consensus_predict(table: pd.DataFrame, pred_cols: list[str]) -> tuple[np.ndarray, pd.DataFrame]:
    preds = table[pred_cols].to_numpy(dtype=np.float64)
    diagnostics = table[["smiles", "max_train_tanimoto", "scaffold_distance", "ensemble_std"]].copy()
    return preds.mean(axis=1), diagnostics


def primary_value(task_type: str, metrics: dict[str, float]) -> tuple[str, float, str]:
    if task_type == "regression":
        return "rmse", metrics["rmse"], "lower"
    for metric in ("roc_auc", "pr_auc", "accuracy", "f1"):
        value = float(metrics.get(metric, float("nan")))
        if np.isfinite(value):
            return metric, value, "higher"
    return "accuracy", float("nan"), "higher"


def is_better(task_type: str, lhs: float, rhs: float) -> bool:
    if task_type == "regression":
        return lhs < rhs
    return lhs > rhs


def build_candidate_predictions(
    dataset: str,
    seed: int,
    family: str,
    members: list[tuple[str, str]],
    task_type: str,
    frame: pd.DataFrame,
) -> list[dict]:
    valid, pred_cols = load_member_predictions(dataset, seed, members, task_type, "valid")
    test, _ = load_member_predictions(dataset, seed, members, task_type, "test")
    bounds: tuple[float, float] | None = None
    valid_clip_count = 0
    test_clip_count = 0
    if task_type == "regression":
        bounds = regression_clip_bounds(valid["y_true"].to_numpy())
        valid, valid_clip_count = clip_regression_columns(valid, pred_cols, bounds)
        test, test_clip_count = clip_regression_columns(test, pred_cols, bounds)
    valid = add_applicability_features(dataset, valid, frame, seed, pred_cols)
    test = add_applicability_features(dataset, test, frame, seed, pred_cols)
    fit_idx, select_idx = stratified_meta_split(valid, task_type, seed)
    meta_fit = valid.loc[fit_idx].copy()
    meta_select = valid.loc[select_idx].copy()
    candidates: list[dict] = []
    for method in ("consensus", "stack", "adaptive"):
        candidate = f"{method}_{family}"
        if method == "consensus":
            select_pred, select_diag = consensus_predict(meta_select, pred_cols)
            test_pred, test_diag = consensus_predict(test, pred_cols)
        elif method == "stack":
            select_model = fit_stacker(task_type, meta_fit, pred_cols)
            select_pred = predict_stacker(select_model, task_type, meta_select, pred_cols)
            final_model = fit_stacker(task_type, valid, pred_cols)
            test_pred = predict_stacker(final_model, task_type, test, pred_cols)
            select_diag = meta_select[["smiles", "max_train_tanimoto", "scaffold_distance", "ensemble_std"]].copy()
            test_diag = test[["smiles", "max_train_tanimoto", "scaffold_distance", "ensemble_std"]].copy()
        else:
            select_pred, select_diag = adaptive_predict(task_type, meta_fit, meta_select, pred_cols)
            test_pred, test_diag = adaptive_predict(task_type, valid, test, pred_cols)
        select_pred = finalize_predictions(task_type, select_pred, bounds)
        test_pred = finalize_predictions(task_type, test_pred, bounds)
        select_metrics = compute_metrics(task_type, meta_select["y_true"].to_numpy(), select_pred)
        test_metrics = compute_metrics(task_type, test["y_true"].to_numpy(), test_pred)
        metric, value, direction = primary_value(task_type, select_metrics)
        candidates.append(
            {
                "dataset": dataset,
                "seed": seed,
                "family": family,
                "candidate": candidate,
                "method": method,
                "task_type": task_type,
                "selection_metric": metric,
                "selection_direction": direction,
                "selection_value": value,
                "clip_lower": bounds[0] if bounds else np.nan,
                "clip_upper": bounds[1] if bounds else np.nan,
                "valid_member_clip_count": valid_clip_count,
                "test_member_clip_count": test_clip_count,
                "valid_select": pd.DataFrame(
                    {
                        "smiles": meta_select["smiles"].to_numpy(),
                        "y_true": meta_select["y_true"].to_numpy(),
                        "y_pred": select_pred,
                    }
                ),
                "test": pd.DataFrame(
                    {
                        "smiles": test["smiles"].to_numpy(),
                        "y_true": test["y_true"].to_numpy(),
                        "y_pred": test_pred,
                    }
                ),
                "valid_diagnostics": select_diag,
                "test_diagnostics": test_diag,
                "select_metrics": select_metrics,
                "test_metrics": test_metrics,
            }
        )
    return candidates


def summarize(metrics: pd.DataFrame, output_dir: Path, filename: str = "metrics_summary.csv") -> None:
    id_cols = {"dataset", "model", "task_type", "seed", "split", "selected_candidate"}
    metric_cols = [
        col for col in metrics.columns if col not in id_cols and pd.api.types.is_numeric_dtype(metrics[col])
    ]
    summary = (
        metrics.groupby(["dataset", "model", "task_type"], dropna=False)[metric_cols]
        .agg(["mean", "std"])
        .reset_index()
    )
    summary.to_csv(output_dir / filename, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Select ensemble strategy using validation only, then evaluate test.")
    parser.add_argument("--output-dir", default=str(ROOT / "reports" / "validation_selector"))
    parser.add_argument("--core-report-dir", default="reports/strict_core")
    parser.add_argument("--multifp-report-dir", default="reports/strict_multifp")
    parser.add_argument("--chemprop-report-dir", default="reports/chemprop_baseline")
    parser.add_argument("--pretrained-frozen-dir", default="reports/pretrained_frozen")
    parser.add_argument("--pretrained-rdkit-dir", default="reports/pretrained_rdkit")
    parser.add_argument("--pretrained-frozen-mlm-dir", default="reports/pretrained_frozen_mlm")
    parser.add_argument("--pretrained-rdkit-mlm-dir", default="reports/pretrained_rdkit_mlm")
    parser.add_argument("--pretrained-frozen-molformer-dir", default="reports/pretrained_frozen_molformer")
    parser.add_argument("--pretrained-rdkit-molformer-dir", default="reports/pretrained_rdkit_molformer")
    parser.add_argument("--descriptor-motif-dir", default="reports/descriptor_motif_baselines")
    parser.add_argument("--datasets", nargs="*", default=list(DATASETS))
    parser.add_argument("--seeds", nargs="*", type=int, default=SEEDS)
    parser.add_argument("--families", nargs="*", default=None)
    args = parser.parse_args()
    report_replacements = {
        "reports/strict_core": args.core_report_dir,
        "reports/strict_multifp": args.multifp_report_dir,
        "reports/chemprop_baseline": args.chemprop_report_dir,
        "reports/pretrained_frozen": args.pretrained_frozen_dir,
        "reports/pretrained_rdkit": args.pretrained_rdkit_dir,
        "reports/pretrained_frozen_mlm": args.pretrained_frozen_mlm_dir,
        "reports/pretrained_rdkit_mlm": args.pretrained_rdkit_mlm_dir,
        "reports/pretrained_frozen_molformer": args.pretrained_frozen_molformer_dir,
        "reports/pretrained_rdkit_molformer": args.pretrained_rdkit_molformer_dir,
        "reports/descriptor_motif_baselines": args.descriptor_motif_dir,
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_metric_rows: list[dict] = []
    candidate_objects: list[dict] = []
    selected_families = set(args.families) if args.families else None

    for dataset in args.datasets:
        frame, spec = load_dataset(dataset, data_dir=ROOT / "data")
        for seed in args.seeds:
            for family, members in MEMBER_SETS.items():
                if selected_families is not None and family not in selected_families:
                    continue
                members = [
                    (report_replacements.get(report_dir, report_dir), model)
                    for report_dir, model in members
                ]
                try:
                    candidates = build_candidate_predictions(dataset, seed, family, members, spec.task_type, frame)
                except FileNotFoundError:
                    continue
                candidate_objects.extend(candidates)
                for item in candidates:
                    candidate_metric_rows.append(
                        {
                            "dataset": dataset,
                            "model": item["candidate"],
                            "seed": seed,
                            "split": "scaffold",
                            "task_type": spec.task_type,
                            "selection_metric": item["selection_metric"],
                            "selection_direction": item["selection_direction"],
                            "selection_value": item["selection_value"],
                            "clip_lower": item["clip_lower"],
                            "clip_upper": item["clip_upper"],
                            "valid_member_clip_count": item["valid_member_clip_count"],
                            "test_member_clip_count": item["test_member_clip_count"],
                            **{f"valid_{k}": v for k, v in item["select_metrics"].items()},
                            **{f"test_{k}": v for k, v in item["test_metrics"].items()},
                        }
                    )

    if not candidate_metric_rows:
        raise SystemExit("No candidate ensembles could be built. Run strict core predictions first.")

    candidate_metrics = pd.DataFrame(candidate_metric_rows)
    candidate_metrics.to_csv(output_dir / "candidate_metrics_raw.csv", index=False)
    chosen_rows: list[dict] = []
    selected_metric_rows: list[dict] = []
    for dataset, group in candidate_metrics.groupby("dataset"):
        task_type = group["task_type"].iloc[0]
        metric = "valid_rmse" if task_type == "regression" else "valid_roc_auc"
        if metric not in group or group[metric].isna().all():
            metric = "selection_value"
        validation_rank = (
            group.groupby("model")[metric]
            .mean()
            .reset_index(name="validation_score")
        )
        validation_rank = validation_rank.dropna(subset=["validation_score"])
        validation_rank = validation_rank.sort_values(
            "validation_score",
            ascending=task_type == "regression",
        )
        selected = validation_rank.iloc[0]["model"]
        chosen_rows.append(
            {
                "dataset": dataset,
                "selected_candidate": selected,
                "selection_metric": metric,
                "validation_score": float(validation_rank.iloc[0]["validation_score"]),
            }
        )
        for item in candidate_objects:
            if item["dataset"] != dataset or item["candidate"] != selected:
                continue
            pred_path = output_dir / f"{dataset}_validation_selector_seed{item['seed']}_predictions.csv"
            weight_path = output_dir / f"{dataset}_validation_selector_seed{item['seed']}_weights.csv"
            item["test"].to_csv(pred_path, index=False)
            item["test_diagnostics"].to_csv(weight_path, index=False)
            selected_metric_rows.append(
                {
                    "dataset": dataset,
                    "model": "validation_selector",
                    "selected_candidate": selected,
                    "seed": item["seed"],
                    "split": "scaffold",
                    "task_type": item["task_type"],
                    **item["test_metrics"],
                }
            )

    chosen = pd.DataFrame(chosen_rows)
    chosen.to_csv(output_dir / "selected_candidates.csv", index=False)
    selected_metrics = pd.DataFrame(selected_metric_rows)
    selected_metrics.to_csv(output_dir / "metrics_raw.csv", index=False)
    summarize(selected_metrics, output_dir)
    print(chosen.to_string(index=False))
    print(selected_metrics.to_string(index=False))


if __name__ == "__main__":
    main()
