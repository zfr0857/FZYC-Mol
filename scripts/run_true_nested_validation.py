from __future__ import annotations

import json
import warnings
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import AllChem
from scipy.stats import spearmanr
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor, RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
)
from sklearn.model_selection import KFold, StratifiedKFold


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "reports" / "remaining_missing_experiments_20260606" / "true_nested_validation"
OUT.mkdir(parents=True, exist_ok=True)

RDLogger.DisableLog("rdApp.*")
warnings.filterwarnings("ignore", category=UserWarning)


TASKS = [
    "bbbp",
    "bace",
    "clintox",
    "esol",
    "freesolv",
    "lipo",
    "tdc_caco2_wang",
    "tdc_hia_hou",
    "tdc_pgp_broccatelli",
]


def pick_column(df: pd.DataFrame, candidates: list[str]) -> str:
    for col in candidates:
        if col in df.columns:
            return col
    lower = {c.lower(): c for c in df.columns}
    for col in candidates:
        if col.lower() in lower:
            return lower[col.lower()]
    raise KeyError(f"None of {candidates} found in {list(df.columns)[:20]}")


def load_task(task: str, registry: dict) -> tuple[pd.DataFrame, str, str, str]:
    meta = registry[task]
    raw_path = DATA / "raw" / meta["filename"]
    if not raw_path.exists():
        raw_path = DATA / "tdc" / meta["filename"].replace(".csv", ".tab")
    df = pd.read_csv(raw_path, sep="\t" if raw_path.suffix == ".tab" else ",")
    smiles_col = pick_column(df, meta["smiles_candidates"])
    target_col = pick_column(df, meta["target_candidates"])
    frame = df[[smiles_col, target_col]].rename(columns={smiles_col: "smiles", target_col: "y"})
    frame = frame.dropna(subset=["smiles", "y"]).drop_duplicates(subset=["smiles"]).reset_index(drop=True)
    frame["y"] = pd.to_numeric(frame["y"], errors="coerce")
    frame = frame.dropna(subset=["y"]).reset_index(drop=True)
    if meta["task_type"] == "classification":
        frame["y"] = frame["y"].astype(int)
        counts = frame["y"].value_counts()
        if len(counts) < 2 or counts.min() < 10:
            raise ValueError(f"{task} has insufficient class balance for nested validation: {counts.to_dict()}")
    return frame, "smiles", "y", meta["task_type"]


def featurize(smiles: pd.Series, n_bits: int = 1024) -> tuple[np.ndarray, np.ndarray]:
    rows: list[np.ndarray] = []
    keep: list[bool] = []
    for smi in smiles.astype(str):
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            keep.append(False)
            continue
        arr = np.zeros((n_bits,), dtype=np.float32)
        fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=n_bits)
        DataStructs.ConvertToNumpyArray(fp, arr)
        rows.append(arr)
        keep.append(True)
    if not rows:
        raise ValueError("No valid molecules after RDKit featurization.")
    return np.vstack(rows), np.array(keep, dtype=bool)


def candidate_models(task_type: str, seed: int) -> dict[str, object]:
    if task_type == "classification":
        return {
            "logreg_l2_c0.3": LogisticRegression(C=0.3, max_iter=3000, class_weight="balanced", solver="liblinear"),
            "logreg_l2_c1": LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced", solver="liblinear"),
            "rf_balanced": RandomForestClassifier(
                n_estimators=160,
                max_features="sqrt",
                min_samples_leaf=1,
                class_weight="balanced_subsample",
                random_state=seed,
                n_jobs=-1,
            ),
            "extratrees_balanced": ExtraTreesClassifier(
                n_estimators=220,
                max_features="sqrt",
                min_samples_leaf=1,
                class_weight="balanced",
                random_state=seed,
                n_jobs=-1,
            ),
        }
    return {
        "ridge_alpha1": Ridge(alpha=1.0, random_state=seed),
        "ridge_alpha10": Ridge(alpha=10.0, random_state=seed),
        "rf_reg": RandomForestRegressor(
            n_estimators=160,
            max_features="sqrt",
            min_samples_leaf=1,
            random_state=seed,
            n_jobs=-1,
        ),
        "extratrees_reg": ExtraTreesRegressor(
            n_estimators=220,
            max_features="sqrt",
            min_samples_leaf=1,
            random_state=seed,
            n_jobs=-1,
        ),
    }


def positive_score(task_type: str, y_true: np.ndarray, pred: np.ndarray) -> float:
    if task_type == "classification":
        if len(np.unique(y_true)) < 2:
            return np.nan
        return float(roc_auc_score(y_true, pred))
    return -rmse(y_true, pred)


def rmse(y_true: np.ndarray, pred: np.ndarray) -> float:
    return float(np.sqrt(mean_squared_error(y_true, pred)))


def predict_score_vector(model, x: np.ndarray, task_type: str) -> np.ndarray:
    if task_type == "classification":
        if hasattr(model, "predict_proba"):
            return model.predict_proba(x)[:, 1]
        raw = model.decision_function(x)
        return 1.0 / (1.0 + np.exp(-raw))
    return model.predict(x)


def choose_candidate(
    x: np.ndarray,
    y: np.ndarray,
    task_type: str,
    train_idx: np.ndarray,
    seed: int,
    n_inner: int = 3,
) -> tuple[str, float, dict[str, float]]:
    models = candidate_models(task_type, seed)
    if task_type == "classification":
        inner_cv = StratifiedKFold(n_splits=n_inner, shuffle=True, random_state=seed + 100)
        split_iter = inner_cv.split(x[train_idx], y[train_idx])
    else:
        inner_cv = KFold(n_splits=n_inner, shuffle=True, random_state=seed + 100)
        split_iter = inner_cv.split(x[train_idx])

    scores: dict[str, list[float]] = {name: [] for name in models}
    train_local = np.arange(len(train_idx))
    for inner_train_local, inner_valid_local in split_iter:
        inner_train = train_idx[train_local[inner_train_local]]
        inner_valid = train_idx[train_local[inner_valid_local]]
        for name, template in models.items():
            model = clone(template)
            model.fit(x[inner_train], y[inner_train])
            pred = predict_score_vector(model, x[inner_valid], task_type)
            score = positive_score(task_type, y[inner_valid], pred)
            scores[name].append(score)

    mean_scores = {name: float(np.nanmean(vals)) for name, vals in scores.items()}
    selected = max(mean_scores, key=lambda k: mean_scores[k])
    return selected, mean_scores[selected], mean_scores


def evaluate_outer(task: str, task_type: str, x: np.ndarray, y: np.ndarray, seed: int = 20260606) -> tuple[pd.DataFrame, pd.DataFrame]:
    n_outer = 3
    if task_type == "classification":
        outer_cv = StratifiedKFold(n_splits=n_outer, shuffle=True, random_state=seed)
        split_iter = outer_cv.split(x, y)
    else:
        outer_cv = KFold(n_splits=n_outer, shuffle=True, random_state=seed)
        split_iter = outer_cv.split(x)

    detail_rows: list[dict] = []
    inner_rows: list[dict] = []
    for outer_fold, (train_idx, test_idx) in enumerate(split_iter, start=1):
        selected, inner_score, all_inner = choose_candidate(x, y, task_type, train_idx, seed + outer_fold)
        for model_name, score in all_inner.items():
            inner_rows.append(
                {
                    "dataset": task,
                    "task_type": task_type,
                    "outer_fold": outer_fold,
                    "candidate": model_name,
                    "inner_cv_score": score,
                    "selected": model_name == selected,
                }
            )
        model = clone(candidate_models(task_type, seed + outer_fold)[selected])
        model.fit(x[train_idx], y[train_idx])
        pred = predict_score_vector(model, x[test_idx], task_type)
        row = {
            "dataset": task,
            "task_type": task_type,
            "outer_fold": outer_fold,
            "n_train": len(train_idx),
            "n_test": len(test_idx),
            "selected_candidate": selected,
            "inner_cv_score": inner_score,
        }
        if task_type == "classification":
            y_label = (pred >= 0.5).astype(int)
            row.update(
                {
                    "roc_auc": roc_auc_score(y[test_idx], pred) if len(np.unique(y[test_idx])) > 1 else np.nan,
                    "pr_auc": average_precision_score(y[test_idx], pred) if len(np.unique(y[test_idx])) > 1 else np.nan,
                    "balanced_accuracy": balanced_accuracy_score(y[test_idx], y_label),
                    "brier": brier_score_loss(y[test_idx], pred),
                }
            )
        else:
            rho = spearmanr(y[test_idx], pred).correlation
            row.update(
                {
                    "rmse": rmse(y[test_idx], pred),
                    "mae": mean_absolute_error(y[test_idx], pred),
                    "r2": r2_score(y[test_idx], pred),
                    "spearman": float(rho) if not np.isnan(rho) else np.nan,
                }
            )
        detail_rows.append(row)
    return pd.DataFrame(detail_rows), pd.DataFrame(inner_rows)


def summarize(detail: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for (dataset, task_type), dfg in detail.groupby(["dataset", "task_type"], sort=False):
        selected_counts = Counter(dfg["selected_candidate"])
        row = {
            "dataset": dataset,
            "task_type": task_type,
            "n_outer": len(dfg),
            "selected_candidate_count": "; ".join(f"{k}:{v}" for k, v in selected_counts.items()),
            "inner_cv_score_mean": dfg["inner_cv_score"].mean(),
        }
        if task_type == "classification":
            row.update(
                {
                    "roc_auc_mean": dfg["roc_auc"].mean(),
                    "roc_auc_sd": dfg["roc_auc"].std(ddof=1),
                    "pr_auc_mean": dfg["pr_auc"].mean(),
                    "balanced_accuracy_mean": dfg["balanced_accuracy"].mean(),
                    "brier_mean": dfg["brier"].mean(),
                }
            )
        else:
            row.update(
                {
                    "rmse_mean": dfg["rmse"].mean(),
                    "rmse_sd": dfg["rmse"].std(ddof=1),
                    "mae_mean": dfg["mae"].mean(),
                    "r2_mean": dfg["r2"].mean(),
                    "spearman_mean": dfg["spearman"].mean(),
                }
            )
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    registry = json.loads((DATA / "dataset_registry.json").read_text(encoding="utf-8"))
    details: list[pd.DataFrame] = []
    inners: list[pd.DataFrame] = []
    dropped_rows: list[dict] = []
    for task in TASKS:
        frame, smiles_col, target_col, task_type = load_task(task, registry)
        x, keep = featurize(frame[smiles_col])
        y = frame.loc[keep, target_col].to_numpy()
        if keep.sum() != len(frame):
            dropped_rows.append({"dataset": task, "dropped_invalid_smiles": int((~keep).sum())})
        detail, inner = evaluate_outer(task, task_type, x, y)
        details.append(detail)
        inners.append(inner)
        print(f"{task}: {task_type}, n={len(y)}, outer folds={len(detail)}")

    detail_all = pd.concat(details, ignore_index=True)
    inner_all = pd.concat(inners, ignore_index=True)
    summary = summarize(detail_all)
    detail_all.to_csv(OUT / "true_nested_validation_detail.csv", index=False)
    inner_all.to_csv(OUT / "true_nested_validation_inner_scores.csv", index=False)
    summary.to_csv(OUT / "true_nested_validation_summary.csv", index=False)
    pd.DataFrame(dropped_rows).to_csv(OUT / "true_nested_validation_dropped_smiles.csv", index=False)

    completion = OUT.parent / "completion_audit_after_full_run.csv"
    if completion.exists():
        audit = pd.read_csv(completion)
        mask = audit["item"].astype(str).str.contains("Nested validation", case=False, na=False)
        if mask.any():
            audit.loc[mask, "status"] = "completed: true 3x3 nested validation on representative endpoints plus seed-nested selector audit"
            audit.loc[mask, "evidence"] = "true_nested_validation/true_nested_validation_summary.csv; nested_seed_validation_summary.csv"
        audit.to_csv(completion, index=False)

    print(f"Wrote true nested validation outputs to {OUT}")


if __name__ == "__main__":
    main()
