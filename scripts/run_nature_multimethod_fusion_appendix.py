from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import sys
import time
import warnings
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRegressor
from rdkit import Chem, RDLogger
from rdkit.Chem import Fragments, MACCSkeys, rdFingerprintGenerator, rdMolDescriptors
from sklearn.decomposition import PCA
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor, RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import QuantileTransformer, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import load_dataset
from fzyc_mol.evaluate import compute_metrics
from fzyc_mol.features import (
    atom_pair_fingerprint,
    descriptor_vector,
    maccs_fingerprint,
    mol_from_smiles,
    morgan_feature_fingerprint,
    morgan_fingerprint,
    rdkit_topological_fingerprint,
    torsion_fingerprint,
)
from fzyc_mol.splits import make_split


RDLogger.DisableLog("rdApp.*")
warnings.filterwarnings("ignore", category=UserWarning)

OUT_DIR = ROOT / "reports" / "nature_multimethod_fusion_appendix"
TABLE_DIR = ROOT / "reports" / "manuscript_tables"
FIG_DIR = ROOT / "reports" / "manuscript_figures_polished"
CURRENT_TABLE = TABLE_DIR / "table27_moleculenet_targeted_rebuild_retained_best.csv"
TABLE29_PATH = TABLE_DIR / "table29_nature_multimethod_fusion_retained_best.csv"
TABLE30_PATH = TABLE_DIR / "table30_nature_multimethod_fusion_candidate_families.csv"
TABLE31_PATH = TABLE_DIR / "table31_nature_method_alignment_matrix.csv"
TABLE44_PATH = TABLE_DIR / "table44_strong_tabpfn_moleculenet_retained_best.csv"
TABLE45_PATH = TABLE_DIR / "table45_strong_tabpfn_moleculenet_candidate_families.csv"
TABLE46_PATH = TABLE_DIR / "table46_strong_tabpfn_method_alignment_matrix.csv"
DEFAULT_DATASETS = ["esol", "freesolv", "lipo", "bbbp", "bace", "clintox"]
EMBEDDING_ROOT = ROOT / "data" / "processed" / "pretrained_embeddings"
EMBEDDING_MODELS = {
    "chemberta_mtr": "DeepChem_ChemBERTa-77M-MTR",
    "chemberta_mlm": "DeepChem_ChemBERTa-77M-MLM",
    "molformer": "ibm_MoLFormer-XL-both-10pct",
}


FRAGMENT_FUNCS = [
    (name, getattr(Fragments, name))
    for name in sorted(dir(Fragments))
    if name.startswith("fr_") and callable(getattr(Fragments, name))
]


def optional_dependency_status() -> dict[str, bool]:
    tabpfn_installed = importlib.util.find_spec("tabpfn") is not None
    return {
        "xgboost": importlib.util.find_spec("xgboost") is not None,
        "catboost": importlib.util.find_spec("catboost") is not None,
        "tabpfn": tabpfn_installed,
        "tabpfn_ready": tabpfn_installed and tabpfn_runtime_ready(),
    }


def manuscript_table_paths(output_dir: Path) -> tuple[Path, Path, Path, bool]:
    """Use separate appendix table numbers for pilot/custom output directories."""
    is_default = output_dir.resolve() == OUT_DIR.resolve()
    if is_default:
        return TABLE29_PATH, TABLE30_PATH, TABLE31_PATH, True
    return TABLE44_PATH, TABLE45_PATH, TABLE46_PATH, False


def tabpfn_runtime_ready() -> bool:
    if os.environ.get("TABPFN_TOKEN"):
        return True
    token_paths = [
        Path(os.environ.get("APPDATA", "")) / "tabpfn" / "auth_token",
        Path.home() / ".tabpfn" / "token",
    ]
    if any(path.exists() and path.stat().st_size > 0 for path in token_paths):
        return True
    cache_root = Path(os.environ.get("APPDATA", "")) / "tabpfn"
    if cache_root.exists():
        model_suffixes = {".ckpt", ".pt", ".pth", ".safetensors"}
        return any(path.suffix.lower() in model_suffixes for path in cache_root.rglob("*") if path.is_file())
    return False


def bitvect_to_array(bitvect, n_bits: int) -> np.ndarray:
    arr = np.zeros((n_bits,), dtype=np.int8)
    from rdkit import DataStructs

    DataStructs.ConvertToNumpyArray(bitvect, arr)
    return arr.astype(np.float32)


def safe_float(value: float) -> float:
    try:
        value = float(value)
    except Exception:
        return 0.0
    return value if math.isfinite(value) else 0.0


def fragment_motif_vector(smiles: str) -> np.ndarray:
    mol = mol_from_smiles(smiles)
    if mol is None:
        return np.zeros(len(FRAGMENT_FUNCS) + 18, dtype=np.float32)
    values: list[float] = []
    for _, fn in FRAGMENT_FUNCS:
        try:
            values.append(safe_float(fn(mol)))
        except Exception:
            values.append(0.0)
    ring_info = mol.GetRingInfo()
    atom_rings = ring_info.AtomRings()
    aromatic_atoms = sum(1 for atom in mol.GetAtoms() if atom.GetIsAromatic())
    hetero_atoms = sum(1 for atom in mol.GetAtoms() if atom.GetAtomicNum() not in {1, 6})
    charged_atoms = sum(1 for atom in mol.GetAtoms() if atom.GetFormalCharge() != 0)
    halogens = sum(1 for atom in mol.GetAtoms() if atom.GetAtomicNum() in {9, 17, 35, 53})
    values.extend(
        [
            mol.GetNumAtoms(),
            mol.GetNumHeavyAtoms(),
            mol.GetNumBonds(),
            len(atom_rings),
            float(any(len(ring) <= 4 for ring in atom_rings)),
            float(any(len(ring) >= 7 for ring in atom_rings)),
            aromatic_atoms,
            hetero_atoms,
            charged_atoms,
            halogens,
            aromatic_atoms / max(1, mol.GetNumAtoms()),
            hetero_atoms / max(1, mol.GetNumAtoms()),
            charged_atoms / max(1, mol.GetNumAtoms()),
            halogens / max(1, mol.GetNumAtoms()),
            rdMolDescriptors.CalcNumBridgeheadAtoms(mol),
            rdMolDescriptors.CalcNumSpiroAtoms(mol),
            rdMolDescriptors.CalcNumAtomStereoCenters(mol),
            rdMolDescriptors.CalcNumUnspecifiedAtomStereoCenters(mol),
        ]
    )
    return np.asarray([safe_float(v) for v in values], dtype=np.float32)


def hierarchical_feature_matrix(smiles: list[str]) -> np.ndarray:
    rows = []
    for smi in smiles:
        rows.append(
            np.hstack(
                [
                    descriptor_vector(smi, include_3d=False),
                    fragment_motif_vector(smi),
                    maccs_fingerprint(smi),
                    morgan_feature_fingerprint(smi, n_bits=512),
                ]
            )
        )
    return np.nan_to_num(np.vstack(rows).astype(np.float32), copy=False)


def multifp_feature_matrix(smiles: list[str]) -> np.ndarray:
    rows = []
    for smi in smiles:
        rows.append(
            np.hstack(
                [
                    morgan_fingerprint(smi, n_bits=1024),
                    morgan_feature_fingerprint(smi, n_bits=512),
                    rdkit_topological_fingerprint(smi, n_bits=512),
                    atom_pair_fingerprint(smi, n_bits=512),
                    torsion_fingerprint(smi, n_bits=512),
                    maccs_fingerprint(smi),
                ]
            )
        )
    return np.nan_to_num(np.vstack(rows).astype(np.float32), copy=False)


def morgan_matrix(smiles: list[str], n_bits: int = 2048) -> np.ndarray:
    return np.nan_to_num(np.vstack([morgan_fingerprint(smi, n_bits=n_bits) for smi in smiles]).astype(np.float32), copy=False)


def load_embedding_matrix(dataset: str, smiles: list[str], model_dir_name: str) -> np.ndarray | None:
    path = EMBEDDING_ROOT / model_dir_name / f"{dataset}.npz"
    if not path.exists():
        return None
    payload = np.load(path, allow_pickle=True)
    emb_smiles = [str(s) for s in payload["smiles"].tolist()]
    emb = payload["embedding"].astype(np.float32)
    lookup = {smi: emb[idx] for idx, smi in enumerate(emb_smiles)}
    dim = emb.shape[1]
    rows = [lookup.get(smi, np.zeros(dim, dtype=np.float32)) for smi in smiles]
    return np.nan_to_num(np.vstack(rows).astype(np.float32), copy=False)


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


def tabpfn_train_indices(y: np.ndarray, task_type: str, seed: int, max_train: int) -> np.ndarray:
    y = np.asarray(y)
    if len(y) <= max_train:
        return np.arange(len(y))
    rng = np.random.default_rng(seed + 104729)
    if task_type == "classification" and len(np.unique(y)) == 2:
        idx_parts = []
        for label in [0, 1]:
            label_idx = np.flatnonzero(y == label)
            take = max(1, int(round(max_train * len(label_idx) / len(y))))
            take = min(take, len(label_idx))
            idx_parts.append(rng.choice(label_idx, size=take, replace=False))
        idx = np.concatenate(idx_parts)
        if len(idx) > max_train:
            idx = rng.choice(idx, size=max_train, replace=False)
        rng.shuffle(idx)
        return idx
    return np.sort(rng.choice(np.arange(len(y)), size=max_train, replace=False))


def make_tabpfn_model(task_type: str, seed: int, n_estimators: int):
    if task_type == "regression":
        from tabpfn import TabPFNRegressor

        return TabPFNRegressor(
            n_estimators=min(8, max(2, n_estimators)),
            device="cpu",
            ignore_pretraining_limits=True,
            fit_mode="low_memory",
            random_state=seed,
            n_preprocessing_jobs=1,
            show_progress_bar=False,
        )
    from tabpfn import TabPFNClassifier

    return TabPFNClassifier(
        n_estimators=min(8, max(2, n_estimators)),
        device="cpu",
        ignore_pretraining_limits=True,
        balance_probabilities=True,
        fit_mode="low_memory",
        random_state=seed,
        n_preprocessing_jobs=1,
        show_progress_bar=False,
    )


def primary_value(task_type: str, metrics: dict[str, float]) -> tuple[float, str, str]:
    if task_type == "regression":
        return float(metrics.get("rmse", np.nan)), "rmse", "lower"
    return float(metrics.get("roc_auc", np.nan)), "roc_auc", "higher"


def score_delta(direction: str, old_value: float, new_value: float) -> float:
    if not np.isfinite(old_value) or not np.isfinite(new_value):
        return float("nan")
    return old_value - new_value if direction == "lower" else new_value - old_value


def candidate_row(
    dataset: str,
    task_type: str,
    seed: int,
    model: str,
    candidate_type: str,
    nature_inspiration: str,
    valid_y: np.ndarray,
    valid_pred: np.ndarray,
    test_y: np.ndarray,
    test_pred: np.ndarray,
    fit_seconds: float,
) -> dict[str, object]:
    valid_metrics = compute_metrics(task_type, valid_y, valid_pred)
    test_metrics = compute_metrics(task_type, test_y, test_pred)
    valid_primary, primary_metric, direction = primary_value(task_type, valid_metrics)
    test_primary, _, _ = primary_value(task_type, test_metrics)
    return {
        "dataset": dataset,
        "task_type": task_type,
        "seed": seed,
        "split": "scaffold",
        "model": model,
        "candidate_type": candidate_type,
        "nature_inspiration": nature_inspiration,
        "primary_metric": primary_metric,
        "primary_direction": direction,
        "validation_primary": valid_primary,
        "primary_value": test_primary,
        "fit_seconds": fit_seconds,
        **{f"valid_{key}": value for key, value in valid_metrics.items()},
        **{f"test_{key}": value for key, value in test_metrics.items()},
    }


def make_tree_model(task_type: str, name: str, seed: int, n_estimators: int, y_train: np.ndarray):
    if task_type == "regression":
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
        if name == "rf":
            return RandomForestRegressor(n_estimators=n_estimators, max_features="sqrt", random_state=seed, n_jobs=-1)
        if name == "extratrees":
            return ExtraTreesRegressor(n_estimators=n_estimators, max_features="sqrt", random_state=seed, n_jobs=-1)
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
    else:
        pos = max(1, int(np.sum(y_train == 1)))
        neg = max(1, int(np.sum(y_train == 0)))
        if name == "lgbm":
            return LGBMClassifier(
                n_estimators=n_estimators,
                learning_rate=0.035,
                num_leaves=31,
                subsample=0.9,
                colsample_bytree=0.8,
                reg_lambda=2.0,
                class_weight="balanced",
                random_state=seed,
                n_jobs=-1,
                verbose=-1,
            )
        if name == "rf":
            return RandomForestClassifier(
                n_estimators=n_estimators,
                max_features="sqrt",
                class_weight="balanced_subsample",
                random_state=seed,
                n_jobs=-1,
            )
        if name == "extratrees":
            return ExtraTreesClassifier(
                n_estimators=n_estimators,
                max_features="sqrt",
                class_weight="balanced",
                random_state=seed,
                n_jobs=-1,
            )
        if name == "xgb":
            from xgboost import XGBClassifier

            return XGBClassifier(
                n_estimators=n_estimators,
                max_depth=5,
                learning_rate=0.04,
                subsample=0.9,
                colsample_bytree=0.8,
                reg_lambda=2.0,
                objective="binary:logistic",
                eval_metric="logloss",
                scale_pos_weight=neg / pos,
                tree_method="hist",
                random_state=seed,
                n_jobs=-1,
            )
        if name == "catboost":
            from catboost import CatBoostClassifier

            return CatBoostClassifier(
                iterations=n_estimators,
                learning_rate=0.04,
                depth=6,
                loss_function="Logloss",
                auto_class_weights="Balanced",
                random_seed=seed,
                verbose=False,
                allow_writing_files=False,
            )
    raise ValueError(f"Unsupported model {task_type}/{name}")


def predict_scores(model: Pipeline, x: np.ndarray, task_type: str) -> np.ndarray:
    if task_type == "classification":
        estimator = model[-1]
        if hasattr(estimator, "predict_proba"):
            return model.predict_proba(x)[:, 1]
    return model.predict(x)


def fit_tree_candidate(
    task_type: str,
    model_name: str,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_valid: np.ndarray,
    x_test: np.ndarray,
    seed: int,
    n_estimators: int,
    transform_name: str = "identity",
) -> tuple[np.ndarray, np.ndarray, float]:
    transformer = TargetTransform(transform_name, seed)
    if task_type == "regression":
        if not transformer.available(y_train):
            raise ValueError(f"target transform {transform_name} unavailable")
        transformer.fit(y_train)
        target = transformer.transform(y_train)
    else:
        target = y_train
    model = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("model", make_tree_model(task_type, model_name, seed, n_estimators, y_train)),
        ]
    )
    start = time.perf_counter()
    model.fit(x_train, target)
    fit_seconds = time.perf_counter() - start
    valid_pred = predict_scores(model, x_valid, task_type)
    test_pred = predict_scores(model, x_test, task_type)
    if task_type == "regression":
        valid_pred = transformer.inverse(valid_pred)
        test_pred = transformer.inverse(test_pred)
    return valid_pred, test_pred, fit_seconds


def fit_embedding_candidate(
    task_type: str,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_valid: np.ndarray,
    x_test: np.ndarray,
    seed: int,
    pca_components: int,
) -> tuple[np.ndarray, np.ndarray, float]:
    n_components = max(2, min(pca_components, x_train.shape[0] - 1, x_train.shape[1]))
    if task_type == "regression":
        estimator = RidgeCV(alphas=np.logspace(-4, 4, 13))
    else:
        estimator = LogisticRegression(max_iter=1500, class_weight="balanced", random_state=seed)
    model = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("pca", PCA(n_components=n_components, random_state=seed)),
            ("model", estimator),
        ]
    )
    start = time.perf_counter()
    model.fit(x_train, y_train)
    fit_seconds = time.perf_counter() - start
    return predict_scores(model, x_valid, task_type), predict_scores(model, x_test, task_type), fit_seconds


def fit_tabpfn_candidate(
    task_type: str,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_valid: np.ndarray,
    x_test: np.ndarray,
    seed: int,
    n_estimators: int,
    pca_components: int,
) -> tuple[np.ndarray, np.ndarray, float]:
    n_components = max(2, min(pca_components, x_train.shape[0] - 1, x_train.shape[1]))
    steps = [
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ]
    if n_components < x_train.shape[1]:
        steps.append(("pca", PCA(n_components=n_components, random_state=seed)))
    steps.append(("model", make_tabpfn_model(task_type, seed, n_estimators)))
    model = Pipeline(steps)
    start = time.perf_counter()
    model.fit(x_train, y_train)
    fit_seconds = time.perf_counter() - start
    return predict_scores(model, x_valid, task_type), predict_scores(model, x_test, task_type), fit_seconds


def balanced_subsample_indices(y: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    y = np.asarray(y, dtype=int)
    pos = np.flatnonzero(y == 1)
    neg = np.flatnonzero(y == 0)
    if len(pos) == 0 or len(neg) == 0:
        return np.arange(len(y))
    minority, majority = (pos, neg) if len(pos) <= len(neg) else (neg, pos)
    sampled_majority = rng.choice(majority, size=len(minority), replace=False)
    idx = np.concatenate([minority, sampled_majority])
    rng.shuffle(idx)
    return idx


def fit_underbag_candidate(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_valid: np.ndarray,
    x_test: np.ndarray,
    seed: int,
    n_estimators: int,
    n_bags: int,
) -> tuple[np.ndarray, np.ndarray, float]:
    rng = np.random.default_rng(seed + 104729)
    valid_preds = []
    test_preds = []
    start = time.perf_counter()
    for bag in range(n_bags):
        idx = balanced_subsample_indices(y_train, rng)
        model = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "model",
                    LGBMClassifier(
                        n_estimators=max(80, n_estimators // 2),
                        learning_rate=0.04,
                        num_leaves=31,
                        subsample=0.9,
                        colsample_bytree=0.8,
                        reg_lambda=2.0,
                        random_state=seed + bag,
                        n_jobs=-1,
                        verbose=-1,
                    ),
                ),
            ]
        )
        model.fit(x_train[idx], y_train[idx])
        valid_preds.append(predict_scores(model, x_valid, "classification"))
        test_preds.append(predict_scores(model, x_test, "classification"))
    fit_seconds = time.perf_counter() - start
    return np.mean(valid_preds, axis=0), np.mean(test_preds, axis=0), fit_seconds


def max_tanimoto(query: np.ndarray, ref: np.ndarray, chunk_size: int = 192) -> np.ndarray:
    query = query.astype(np.float32, copy=False)
    ref = ref.astype(np.float32, copy=False)
    ref_sum = ref.sum(axis=1)
    out = np.zeros(query.shape[0], dtype=np.float32)
    for start in range(0, query.shape[0], chunk_size):
        q = query[start : start + chunk_size]
        inter = q @ ref.T
        denom = q.sum(axis=1, keepdims=True) + ref_sum.reshape(1, -1) - inter
        sim = np.divide(inter, np.maximum(denom, 1e-6))
        out[start : start + chunk_size] = sim.max(axis=1)
    return out


def rank_average(matrix: np.ndarray) -> np.ndarray:
    ranks = []
    for col in range(matrix.shape[1]):
        order = np.argsort(matrix[:, col])
        r = np.empty_like(order, dtype=float)
        r[order] = np.linspace(0.0, 1.0, len(order))
        ranks.append(r)
    return np.mean(np.column_stack(ranks), axis=1)


def add_fusion_candidates(
    dataset: str,
    task_type: str,
    seed: int,
    base_rows: list[dict[str, object]],
    valid_y: np.ndarray,
    test_y: np.ndarray,
    valid_ad: np.ndarray,
    test_ad: np.ndarray,
) -> list[dict[str, object]]:
    if not base_rows:
        return []
    direction = str(base_rows[0]["primary_direction"])
    reverse = direction == "higher"
    valid_base = [row for row in base_rows if np.isfinite(float(row["validation_primary"]))]
    valid_base = sorted(valid_base, key=lambda row: float(row["validation_primary"]), reverse=reverse)
    rows: list[dict[str, object]] = []
    for k in [3, 5, 8]:
        selected = valid_base[: min(k, len(valid_base))]
        if len(selected) < 2:
            continue
        valid_matrix = np.column_stack([row["_valid_pred"] for row in selected])
        test_matrix = np.column_stack([row["_test_pred"] for row in selected])
        member_names = ";".join(str(row["model"]) for row in selected)

        pred_pairs: list[tuple[str, str, np.ndarray, np.ndarray]] = []
        pred_pairs.append((f"top{k}_mean", "attention_style_prediction_fusion", np.mean(valid_matrix, axis=1), np.mean(test_matrix, axis=1)))
        errors = []
        for idx, row in enumerate(selected):
            if task_type == "regression":
                errors.append(float(np.mean(np.abs(valid_y - valid_matrix[:, idx]))))
            else:
                errors.append(float(np.mean((valid_y.astype(float) - np.clip(valid_matrix[:, idx], 1e-5, 1 - 1e-5)) ** 2)))
        weights = 1.0 / (np.asarray(errors) + 1e-6)
        weights = weights / weights.sum()
        pred_pairs.append(
            (
                f"weighted_top{k}",
                "uncertainty_weighted_multiview_fusion",
                valid_matrix @ weights,
                test_matrix @ weights,
            )
        )
        if task_type == "classification":
            pred_pairs.append((f"rank_top{k}", "rank_fusion_for_screening", rank_average(valid_matrix), rank_average(test_matrix)))
            if len(np.unique(valid_y)) == 2:
                stacker = LogisticRegression(max_iter=1500, class_weight="balanced", random_state=seed)
                stacker.fit(valid_matrix, valid_y.astype(int))
                pred_pairs.append(
                    (
                        f"stack_top{k}",
                        "validation_logistic_stacking",
                        stacker.predict_proba(valid_matrix)[:, 1],
                        stacker.predict_proba(test_matrix)[:, 1],
                    )
                )
        else:
            stacker = RidgeCV(alphas=np.logspace(-4, 4, 13))
            stacker.fit(valid_matrix, valid_y.astype(float))
            pred_pairs.append(
                (
                    f"stack_top{k}",
                    "validation_ridge_stacking",
                    stacker.predict(valid_matrix),
                    stacker.predict(test_matrix),
                )
            )

        best_valid = valid_matrix[:, 0]
        best_test = test_matrix[:, 0]
        mean_valid = np.mean(valid_matrix, axis=1)
        mean_test = np.mean(test_matrix, axis=1)
        for threshold in [0.35, 0.50, 0.65]:
            pred_pairs.append(
                (
                    f"ad_gate{k}_{threshold:.2f}",
                    "applicability_domain_gated_fusion",
                    np.where(valid_ad < threshold, mean_valid, best_valid),
                    np.where(test_ad < threshold, mean_test, best_test),
                )
            )

        for model_name, inspiration, valid_pred, test_pred in pred_pairs:
            row = candidate_row(
                dataset,
                task_type,
                seed,
                model_name,
                "prediction_level_fusion",
                inspiration,
                valid_y,
                valid_pred,
                test_y,
                test_pred,
                0.0,
            )
            row["_valid_pred"] = valid_pred
            row["_test_pred"] = test_pred
            row["fusion_members"] = member_names
            rows.append(row)
    return rows


def run_one(dataset: str, seed: int, args: argparse.Namespace, deps: dict[str, bool]) -> tuple[list[dict[str, object]], dict[str, object]]:
    frame, spec = load_dataset(dataset, data_dir=ROOT / "data")
    smiles = frame["smiles"].tolist()
    y = frame["y"].to_numpy()
    split = make_split(frame, "scaffold", seed)
    views: dict[str, tuple[np.ndarray, str]] = {
        "morgan": (morgan_matrix(smiles), "fingerprint_baseline"),
        "multifp": (multifp_feature_matrix(smiles), "multi_fingerprint_similarity_fusion"),
        "hier_motif": (hierarchical_feature_matrix(smiles), "himnet_style_atom_motif_global_features"),
    }
    for label, model_dir in EMBEDDING_MODELS.items():
        emb = load_embedding_matrix(dataset, smiles, model_dir)
        if emb is not None:
            views[label] = (emb, "molecular_language_embedding_fusion")

    candidate_rows: list[dict[str, object]] = []
    tree_models = ["lgbm", "rf", "extratrees"]
    if args.include_xgb and deps["xgboost"]:
        tree_models.append("xgb")
    use_tabpfn = bool(deps["tabpfn"] and deps.get("tabpfn_ready", False) and getattr(args, "include_tabpfn", False))
    tabpfn_views = set(getattr(args, "tabpfn_views", ["hier_motif", "morgan", "chemberta_mtr", "molformer"]))

    for view_name, (x, inspiration) in views.items():
        x_train, x_valid, x_test = x[split.train], x[split.valid], x[split.test]
        y_train, y_valid, y_test = y[split.train], y[split.valid], y[split.test]
        if view_name in EMBEDDING_MODELS:
            try:
                valid_pred, test_pred, fit_seconds = fit_embedding_candidate(
                    spec.task_type,
                    x_train,
                    y_train,
                    x_valid,
                    x_test,
                    seed,
                    args.embedding_pca,
                )
                row = candidate_row(
                    dataset,
                    spec.task_type,
                    seed,
                    f"{view_name}_linear_pca",
                    "embedding_head",
                    inspiration,
                    y_valid,
                    valid_pred,
                    y_test,
                    test_pred,
                    fit_seconds,
                )
                row["_valid_pred"] = valid_pred
                row["_test_pred"] = test_pred
                candidate_rows.append(row)
            except Exception as exc:
                print(f"candidate_error dataset={dataset} seed={seed} view={view_name} model=linear_pca: {exc}", flush=True)
            if view_name == "molformer":
                model_names = ["lgbm"]
            else:
                model_names = []
        elif view_name == "hier_motif":
            model_names = tree_models + (["catboost"] if args.include_catboost and deps["catboost"] else [])
        elif view_name == "multifp":
            model_names = ["lgbm", "extratrees"] + (["xgb"] if args.include_xgb and deps["xgboost"] else [])
        else:
            model_names = ["lgbm"]
        for model_name in model_names:
            transforms = args.regression_transforms if spec.task_type == "regression" else ["identity"]
            for transform_name in transforms:
                name = f"{view_name}_{model_name}" if transform_name == "identity" else f"{view_name}_{model_name}_{transform_name}"
                try:
                    valid_pred, test_pred, fit_seconds = fit_tree_candidate(
                        spec.task_type,
                        model_name,
                        x_train,
                        y_train,
                        x_valid,
                        x_test,
                        seed,
                        args.n_estimators,
                        transform_name,
                    )
                except Exception as exc:
                    print(f"candidate_error dataset={dataset} seed={seed} model={name}: {exc}", flush=True)
                    continue
                row = candidate_row(
                    dataset,
                    spec.task_type,
                    seed,
                    name,
                    "single_view_expert",
                    inspiration,
                    y_valid,
                    valid_pred,
                    y_test,
                    test_pred,
                    fit_seconds,
                )
                row["_valid_pred"] = valid_pred
                row["_test_pred"] = test_pred
                candidate_rows.append(row)
        if use_tabpfn and view_name in tabpfn_views:
            try:
                idx = tabpfn_train_indices(y_train, spec.task_type, seed, getattr(args, "tabpfn_max_train", 2048))
                valid_pred, test_pred, fit_seconds = fit_tabpfn_candidate(
                    spec.task_type,
                    x_train[idx],
                    y_train[idx],
                    x_valid,
                    x_test,
                    seed,
                    getattr(args, "tabpfn_estimators", 4),
                    getattr(args, "tabpfn_pca", args.embedding_pca),
                )
                row = candidate_row(
                    dataset,
                    spec.task_type,
                    seed,
                    f"{view_name}_tabpfn_pca{getattr(args, 'tabpfn_pca', args.embedding_pca)}",
                    "foundation_embedding_tabpfn" if view_name in EMBEDDING_MODELS else "tabular_foundation_model",
                    "tabpfn_descriptor_morgan_embedding_benchmark",
                    y_valid,
                    valid_pred,
                    y_test,
                    test_pred,
                    fit_seconds,
                )
                row["_valid_pred"] = valid_pred
                row["_test_pred"] = test_pred
                candidate_rows.append(row)
            except Exception as exc:
                print(f"candidate_error dataset={dataset} seed={seed} view={view_name} model=tabpfn: {exc}", flush=True)

    if spec.task_type == "classification" and args.undersampling_bags > 0:
        x = views["hier_motif"][0]
        x_train, x_valid, x_test = x[split.train], x[split.valid], x[split.test]
        y_train, y_valid, y_test = y[split.train], y[split.valid], y[split.test]
        try:
            valid_pred, test_pred, fit_seconds = fit_underbag_candidate(
                x_train,
                y_train,
                x_valid,
                x_test,
                seed,
                args.n_estimators,
                args.undersampling_bags,
            )
            row = candidate_row(
                dataset,
                spec.task_type,
                seed,
                f"hier_motif_lgbm_underbag{args.undersampling_bags}",
                "undersampling_ensemble",
                "openadmet_reliability_imbalance_strategy",
                y_valid,
                valid_pred,
                y_test,
                test_pred,
                fit_seconds,
            )
            row["_valid_pred"] = valid_pred
            row["_test_pred"] = test_pred
            candidate_rows.append(row)
        except Exception as exc:
            print(f"candidate_error dataset={dataset} seed={seed} model=underbag: {exc}", flush=True)

    y_valid, y_test = y[split.valid], y[split.test]
    morgan = views["morgan"][0]
    valid_ad = max_tanimoto(morgan[split.valid], morgan[split.train])
    test_ad = max_tanimoto(morgan[split.test], morgan[np.concatenate([split.train, split.valid])])
    candidate_rows.extend(add_fusion_candidates(dataset, spec.task_type, seed, candidate_rows, y_valid, y_test, valid_ad, test_ad))

    valid_candidates = [row for row in candidate_rows if np.isfinite(float(row["validation_primary"]))]
    if not valid_candidates:
        raise RuntimeError(f"No valid candidates for {dataset} seed={seed}.")
    direction = str(valid_candidates[0]["primary_direction"])
    selected = sorted(
        valid_candidates,
        key=lambda row: float(row["validation_primary"]),
        reverse=(direction == "higher"),
    )[0]
    clean_candidates = [{key: value for key, value in row.items() if not key.startswith("_")} for row in candidate_rows]
    clean_selected = {key: value for key, value in selected.items() if not key.startswith("_")}
    clean_selected["selected_by"] = "validation_primary"
    clean_selected["n_train"] = len(split.train)
    clean_selected["n_valid"] = len(split.valid)
    clean_selected["n_test"] = len(split.test)
    return clean_candidates, clean_selected


def append_rows(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    frame = pd.DataFrame(rows)
    if path.exists():
        old = pd.read_csv(path)
        frame = pd.concat([old, frame], ignore_index=True)
    frame.to_csv(path, index=False)


def summarize(output_dir: Path) -> None:
    selected_path = output_dir / "selected_metrics_raw.csv"
    if not selected_path.exists():
        return
    raw = pd.read_csv(selected_path).drop_duplicates(["dataset", "seed"], keep="last")
    raw.to_csv(selected_path, index=False)

    summary_rows = []
    for dataset, group in raw.groupby("dataset", dropna=False):
        counts = Counter(group["model"].astype(str))
        nature_counts = Counter(group["nature_inspiration"].astype(str))
        row: dict[str, object] = {
            "dataset": dataset,
            "task_type": str(group["task_type"].iloc[0]),
            "primary_metric": str(group["primary_metric"].iloc[0]),
            "primary_direction": str(group["primary_direction"].iloc[0]),
            "n_seeds": int(group["seed"].nunique()),
            "fusion_model_counts": "; ".join(f"{key}:{value}" for key, value in counts.most_common()),
            "nature_inspiration_counts": "; ".join(f"{key}:{value}" for key, value in nature_counts.most_common()),
            "fusion_primary_mean": float(group["primary_value"].mean()),
            "fusion_primary_std": float(group["primary_value"].std(ddof=1)),
            "fusion_validation_primary_mean": float(group["validation_primary"].mean()),
            "fit_seconds_mean": float(group["fit_seconds"].mean()),
        }
        for metric in ["rmse", "mae", "roc_auc", "pr_auc", "brier", "ece", "ef1", "ef5"]:
            col = f"test_{metric}"
            row[f"{metric}_mean"] = float(group[col].mean()) if col in group else np.nan
            row[f"{metric}_std"] = float(group[col].std(ddof=1)) if col in group else np.nan
        summary_rows.append(row)
    summary = pd.DataFrame(summary_rows).sort_values("dataset")
    summary.to_csv(output_dir / "selected_metrics_summary.csv", index=False)

    retained_table_path, family_table_path, alignment_table_path, is_default_output = manuscript_table_paths(output_dir)
    if CURRENT_TABLE.exists():
        current = pd.read_csv(CURRENT_TABLE)
        current = current[
            [
                "dataset",
                "task_type",
                "primary_metric",
                "primary_direction",
                "retained_primary_mean",
                "retained_primary_std",
                "retained_model",
                "retained_source",
            ]
        ].rename(
            columns={
                "retained_primary_mean": "previous_retained_primary_mean",
                "retained_primary_std": "previous_retained_primary_std",
                "retained_model": "previous_retained_model",
                "retained_source": "previous_retained_source",
            }
        )
        combined = current.merge(summary, on=["dataset", "task_type", "primary_metric", "primary_direction"], how="right")
        combined["delta_vs_previous_retained"] = combined.apply(
            lambda row: score_delta(
                str(row["primary_direction"]),
                float(row["previous_retained_primary_mean"]),
                float(row["fusion_primary_mean"]),
            ),
            axis=1,
        )
        combined["retained_source"] = np.where(
            combined["delta_vs_previous_retained"] > 0.0,
            "nature_multimethod_fusion",
            combined["previous_retained_source"],
        )
        combined["retained_primary_mean"] = np.where(
            combined["delta_vs_previous_retained"] > 0.0,
            combined["fusion_primary_mean"],
            combined["previous_retained_primary_mean"],
        )
        combined["retained_primary_std"] = np.where(
            combined["delta_vs_previous_retained"] > 0.0,
            combined["fusion_primary_std"],
            combined["previous_retained_primary_std"],
        )
        combined["retained_model"] = np.where(
            combined["delta_vs_previous_retained"] > 0.0,
            combined["fusion_model_counts"],
            combined["previous_retained_model"],
        )
        TABLE_DIR.mkdir(parents=True, exist_ok=True)
        combined.sort_values("dataset").to_csv(retained_table_path, index=False)

        family_rows = []
        candidates_path = output_dir / "candidate_metrics_raw.csv"
        if candidates_path.exists():
            candidates = pd.read_csv(candidates_path)
            candidates = candidates.drop_duplicates(["dataset", "seed", "model", "candidate_type"], keep="last")
            for (dataset, candidate_type, nature), group in candidates.groupby(["dataset", "candidate_type", "nature_inspiration"], dropna=False):
                family_rows.append(
                    {
                        "dataset": dataset,
                        "candidate_type": candidate_type,
                        "nature_inspiration": nature,
                        "n_candidates": int(len(group)),
                        "validation_primary_mean": float(group["validation_primary"].mean()),
                        "test_primary_mean": float(group["primary_value"].mean()),
                    }
                )
        pd.DataFrame(family_rows).sort_values(["dataset", "candidate_type", "nature_inspiration"]).to_csv(family_table_path, index=False)
        build_alignment_matrix().to_csv(alignment_table_path, index=False)
        if is_default_output:
            plot_decision_figure(combined)

    readme_lines = [
        "# Nature-Inspired Multimethod Fusion Appendix",
        "",
        "This appendix translates recent Nature-family molecular prediction ideas into a low-cost validation-only candidate pool.",
        "It adds hierarchical motif/fingerprint features, molecular language embedding heads, multi-fingerprint experts,",
        "TabPFN descriptor/Morgan/embedding experts, prediction-level attention-style fusion,",
        "uncertainty-weighted fusion, rank fusion, and AD-similarity gated fusion.",
        "",
        f"- Candidate metrics: `{(output_dir / 'candidate_metrics_raw.csv').resolve().relative_to(ROOT)}`",
        f"- Selected metrics: `{(output_dir / 'selected_metrics_raw.csv').resolve().relative_to(ROOT)}`",
        f"- Selected summary: `{(output_dir / 'selected_metrics_summary.csv').resolve().relative_to(ROOT)}`",
        f"- Retained-best table: `{retained_table_path.resolve().relative_to(ROOT)}`",
        f"- Candidate-family table: `{family_table_path.resolve().relative_to(ROOT)}`",
        f"- Literature-method alignment: `{alignment_table_path.resolve().relative_to(ROOT)}`",
        "",
    ]
    deps_file = output_dir / "dependency_status.json"
    deps_status = json.loads(deps_file.read_text(encoding="utf-8")) if deps_file.exists() else {}
    if deps_status.get("tabpfn") and not deps_status.get("tabpfn_ready"):
        readme_lines.extend(
            [
                "TabPFN package is installed but its local model license/token/cache is not ready,",
                "so TabPFN candidates were skipped to avoid non-interactive login hangs.",
                "",
            ]
        )
    if retained_table_path.exists():
        retained = pd.read_csv(retained_table_path)
        readme_lines.extend(["## Retained-Best Outcome", ""])
        for row in retained.itertuples(index=False):
            readme_lines.append(
                f"- `{row.dataset}`: previous={row.previous_retained_primary_mean:.4f}, "
                f"fusion={row.fusion_primary_mean:.4f}, "
                f"delta={row.delta_vs_previous_retained:+.4f}, retained=`{row.retained_source}`."
            )
    readme_lines.append("")
    readme_lines.append("All decisions are made by validation primary metrics only; test labels are used only after selection.")
    (output_dir / "README.md").write_text("\n".join(readme_lines), encoding="utf-8")


def build_alignment_matrix() -> pd.DataFrame:
    rows = [
        {
            "literature_signal": "HimNet / Communications Chemistry 2026",
            "borrowed_idea": "atom-, motif-, fingerprint-, and global-level fusion",
            "implemented_candidate": "hier_motif view + multifp view + prediction-level fusion",
            "claim_boundary": "Appendix-level approximation, not a new graph-attention architecture.",
        },
        {
            "literature_signal": "OpenADMET avoid-ome / Nature Communications 2026",
            "borrowed_idea": "external reliability, safety-risk framing, and imbalance-aware candidates",
            "implemented_candidate": "AD-gated fusion, undersampling ensemble, PR-AUC/Brier/ECE outputs",
            "claim_boundary": "No new wet assay or official blind challenge submission.",
        },
        {
            "literature_signal": "TabPFN / Nature 2025 and tabular foundation model MPP 2026",
            "borrowed_idea": "small-data tabular prediction from descriptors and embeddings",
            "implemented_candidate": "optional TabPFN heads over descriptor/motif, Morgan, ChemBERTa, and MoLFormer views",
            "claim_boundary": "Validation-only appendix baseline; no claim of molecular foundation fine-tuning.",
        },
        {
            "literature_signal": "MoLFormer / Nature Machine Intelligence",
            "borrowed_idea": "chemical language representation as complementary molecular view",
            "implemented_candidate": "frozen ChemBERTa/MoLFormer embedding heads and fusion",
            "claim_boundary": "Frozen embeddings only; no large-scale fine-tuning restart.",
        },
        {
            "literature_signal": "UQ under data shifts / JCIM 2026",
            "borrowed_idea": "combine model uncertainty and data-shift indicators",
            "implemented_candidate": "uncertainty-weighted and AD-similarity gated prediction fusion",
            "claim_boundary": "Uses scaffold validation and Tanimoto AD, not prospective deployment data.",
        },
    ]
    return pd.DataFrame(rows)


def plot_decision_figure(combined: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    plot = combined.copy().sort_values("delta_vs_previous_retained")
    labels = [f"{row.dataset}\n{row.primary_metric.upper()}" for row in plot.itertuples(index=False)]
    deltas = plot["delta_vs_previous_retained"].astype(float).to_numpy()
    colors = ["#1b8a6b" if value > 0 else "#d7dee8" for value in deltas]
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.edgecolor": "#cbd5e1",
            "axes.labelcolor": "#0f172a",
            "xtick.color": "#334155",
            "ytick.color": "#334155",
            "figure.dpi": 180,
            "savefig.dpi": 320,
        }
    )
    fig, ax = plt.subplots(figsize=(9.4, 4.75))
    y_pos = np.arange(len(plot))
    ax.barh(y_pos, deltas, color=colors, alpha=0.96, height=0.58, edgecolor="white", linewidth=0.8)
    ax.axvline(0, color="#334155", linewidth=0.9)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Validation-normalized gain vs previous retained-best")
    ax.set_title("Multimethod fusion gate on MoleculeNet", loc="left", pad=12, fontsize=12.5, fontweight="bold")
    ax.grid(axis="x", color="#e5e7eb", linewidth=0.65, alpha=0.85)
    ax.set_axisbelow(True)
    span = max(0.02, float(np.nanmax(np.abs(deltas))) * 0.15)
    for y, row, delta in zip(y_pos, plot.itertuples(index=False), deltas):
        source = "promote fusion" if delta > 0 else "keep retained"
        text = f"{delta:+.3f} | {source}"
        if delta > 0:
            x = delta + span * 0.25
            ha = "left"
            color = "#14532d"
        else:
            x = delta + span * 0.25
            ha = "left"
            color = "#475569"
        ax.text(x, y, text, va="center", ha=ha, fontsize=8.8, color=color, fontweight="bold")
    max_abs = max(0.08, float(np.nanmax(np.abs(deltas))) + span)
    ax.set_xlim(-max_abs, max_abs)
    fig.text(
        0.125,
        0.03,
        "Green bars are promoted; gray bars keep the previous retained result. Lower RMSE and higher ROC-AUC are both converted to positive-delta gain.",
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
        fig.savefig(FIG_DIR / f"fig18_nature_multimethod_fusion_decision.{ext}", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Nature-inspired multimethod fusion appendix.")
    parser.add_argument("--datasets", nargs="*", default=DEFAULT_DATASETS)
    parser.add_argument("--seeds", nargs="*", type=int, default=[13, 17, 23, 29, 31])
    parser.add_argument("--output-dir", default=str(OUT_DIR))
    parser.add_argument("--n-estimators", type=int, default=160)
    parser.add_argument("--embedding-pca", type=int, default=96)
    parser.add_argument("--undersampling-bags", type=int, default=7)
    parser.add_argument("--include-catboost", action="store_true")
    parser.add_argument("--include-xgb", action="store_true")
    parser.add_argument("--include-tabpfn", action="store_true")
    parser.add_argument("--tabpfn-estimators", type=int, default=4)
    parser.add_argument("--tabpfn-max-train", type=int, default=2048)
    parser.add_argument("--tabpfn-pca", type=int, default=96)
    parser.add_argument("--tabpfn-views", nargs="*", default=["hier_motif", "morgan", "chemberta_mtr", "molformer"])
    parser.add_argument("--regression-transforms", nargs="*", default=["identity", "winsor", "quantile_normal"])
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--no-resume", action="store_false", dest="resume")
    args = parser.parse_args()

    deps = optional_dependency_status()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "dependency_status.json").write_text(json.dumps(deps, indent=2), encoding="utf-8")
    if args.include_tabpfn and deps["tabpfn"] and not deps.get("tabpfn_ready", False):
        print("skip TabPFN candidates: package installed but model license/token/cache is not ready.", flush=True)

    selected_path = output_dir / "selected_metrics_raw.csv"
    if args.resume and selected_path.exists():
        existing = pd.read_csv(selected_path)
        done = {(str(row["dataset"]), int(row["seed"])) for row in existing.to_dict("records")}
    else:
        done = set()

    for dataset in args.datasets:
        for seed in args.seeds:
            key = (dataset, int(seed))
            if key in done:
                print(f"skip dataset={dataset} seed={seed}", flush=True)
                continue
            print(f"run dataset={dataset} seed={seed}", flush=True)
            candidates, selected = run_one(dataset, seed, args, deps)
            append_rows(output_dir / "candidate_metrics_raw.csv", candidates)
            append_rows(selected_path, [selected])
            summarize(output_dir)

    summarize(output_dir)
    print(f"wrote {output_dir}", flush=True)


if __name__ == "__main__":
    main()
