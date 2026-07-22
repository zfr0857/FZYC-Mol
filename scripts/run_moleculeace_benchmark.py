from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from datasets import get_dataset_config_names, load_dataset as hf_load_dataset
from lightgbm import LGBMRegressor
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import canonicalize_smiles
from fzyc_mol.features import (
    descriptor_vector,
    maccs_fingerprint,
    morgan_feature_fingerprint,
    morgan_fingerprint,
    rdkit_topological_fingerprint,
)
from fzyc_mol.splits import make_split


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "r2": float(r2_score(y_true, y_pred)),
    }


def normalize_split(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame[["smiles", "y", "cliff_mol", "task"]].copy()
    out["smiles"] = out["smiles"].map(canonicalize_smiles)
    out["y"] = pd.to_numeric(out["y"], errors="coerce")
    out["cliff_mol"] = pd.to_numeric(out["cliff_mol"], errors="coerce").fillna(0).astype(int)
    out = out.dropna(subset=["smiles", "y"]).drop_duplicates("smiles").reset_index(drop=True)
    return out


def feature_matrix(frame: pd.DataFrame) -> np.ndarray:
    rows = []
    for smiles in frame["smiles"]:
        rows.append(
            np.hstack(
                [
                    morgan_fingerprint(smiles, radius=2),
                    morgan_feature_fingerprint(smiles, n_bits=1024, radius=2),
                    rdkit_topological_fingerprint(smiles, n_bits=1024),
                    maccs_fingerprint(smiles),
                    descriptor_vector(smiles, include_3d=False),
                ]
            )
        )
    return np.vstack(rows).astype(np.float32)


def _base_models(seed: int, n_estimators: int) -> dict[str, object]:
    return {
        "rf_multifp": RandomForestRegressor(
            n_estimators=n_estimators,
            random_state=seed,
            n_jobs=-1,
            max_features="sqrt",
            min_samples_leaf=1,
        ),
        "extratrees_multifp": ExtraTreesRegressor(
            n_estimators=n_estimators,
            random_state=seed,
            n_jobs=-1,
            max_features="sqrt",
            min_samples_leaf=1,
        ),
        "xgb_multifp": XGBRegressor(
            n_estimators=n_estimators,
            max_depth=3,
            learning_rate=0.04,
            subsample=0.85,
            colsample_bytree=0.65,
            reg_lambda=2.0,
            objective="reg:squarederror",
            random_state=seed,
            n_jobs=4,
        ),
        "lgbm_multifp": LGBMRegressor(
            n_estimators=n_estimators,
            learning_rate=0.035,
            num_leaves=31,
            subsample=0.85,
            colsample_bytree=0.65,
            reg_lambda=2.0,
            min_child_samples=10,
            random_state=seed,
            n_jobs=4,
            verbose=-1,
        ),
    }


def build_models(seed: int, n_estimators: int, include_cliff_weighted: bool) -> dict[str, tuple[object, bool]]:
    models = {name: (model, False) for name, model in _base_models(seed, n_estimators).items()}
    if include_cliff_weighted:
        for name, model in _base_models(seed + 104729, n_estimators).items():
            models[f"{name}_cliffw"] = (model, True)
    return models


def validation_indices(train_frame: pd.DataFrame, seed: int) -> tuple[np.ndarray, np.ndarray]:
    split = make_split(train_frame, "scaffold", seed)
    fit_idx = np.sort(np.concatenate([split.train, split.test]))
    valid_idx = split.valid
    if len(valid_idx) < 8:
        rng = np.random.default_rng(seed)
        idx = np.arange(len(train_frame))
        rng.shuffle(idx)
        cut = max(8, int(round(0.15 * len(idx))))
        valid_idx = np.sort(idx[:cut])
        fit_idx = np.sort(idx[cut:])
    return fit_idx, valid_idx


def stack_predictions(valid_preds: np.ndarray, y_valid: np.ndarray, test_preds: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray]:
    model = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("ridge", RidgeCV(alphas=np.logspace(-4, 4, 17))),
        ]
    )
    if len(y_valid) >= 10:
        cv = KFold(n_splits=min(5, len(y_valid)), shuffle=True, random_state=seed)
        valid_stack = cross_val_predict(model, valid_preds, y_valid, cv=cv)
    else:
        valid_stack = np.mean(valid_preds, axis=1)
    model.fit(valid_preds, y_valid)
    return valid_stack, model.predict(test_preds)


def add_cliff_metrics(row: dict, y_true: np.ndarray, pred: np.ndarray, frame: pd.DataFrame) -> dict:
    if frame["cliff_mol"].sum() >= 3 and (frame["cliff_mol"].eq(0).sum() >= 3):
        cliff = frame["cliff_mol"].to_numpy(dtype=bool)
        row.update({f"cliff_{k}": v for k, v in regression_metrics(y_true[cliff], pred[cliff]).items()})
        row.update({f"noncliff_{k}": v for k, v in regression_metrics(y_true[~cliff], pred[~cliff]).items()})
    return row


def selection_score(y_valid: np.ndarray, valid_pred: np.ndarray, valid_frame: pd.DataFrame, objective: str) -> float:
    overall = regression_metrics(y_valid, valid_pred)["rmse"]
    if objective == "overall":
        return overall
    cliff = valid_frame["cliff_mol"].to_numpy(dtype=bool)
    if cliff.sum() < 3:
        return overall
    cliff_rmse = regression_metrics(y_valid[cliff], valid_pred[cliff])["rmse"]
    if objective == "cliff":
        return cliff_rmse
    if objective == "balanced":
        return 0.5 * overall + 0.5 * cliff_rmse
    raise ValueError(f"Unknown selection objective: {objective}")


def evaluate_task(task: str, seed: int, n_estimators: int, output_dir: Path, cliff_weight: float, selection_objective: str) -> list[dict]:
    dataset = hf_load_dataset("karina-zadorozhny/moleculeace", task)
    train = normalize_split(dataset["train"].to_pandas())
    test = normalize_split(dataset["test"].to_pandas())
    fit_idx, valid_idx = validation_indices(train, seed)
    train_x = feature_matrix(train)
    test_x = feature_matrix(test)
    y = train["y"].to_numpy(dtype=float)
    y_test = test["y"].to_numpy(dtype=float)
    rows: list[dict] = []
    valid_pred_cols = []
    test_pred_cols = []
    pred_output = test[["smiles", "y", "cliff_mol", "task"]].rename(columns={"y": "y_true"}).copy()
    models = build_models(seed, n_estimators, include_cliff_weighted=cliff_weight > 0.0)
    sample_weight = 1.0 + float(cliff_weight) * train["cliff_mol"].to_numpy(dtype=float)
    for model_name, (model, use_cliff_weight) in models.items():
        fit_kwargs = {"sample_weight": sample_weight[fit_idx]} if use_cliff_weight else {}
        try:
            model.fit(train_x[fit_idx], y[fit_idx], **fit_kwargs)
        except TypeError:
            model.fit(train_x[fit_idx], y[fit_idx])
        valid_pred = model.predict(train_x[valid_idx])
        test_pred = model.predict(test_x)
        valid_pred_cols.append(valid_pred)
        test_pred_cols.append(test_pred)
        pred_output[f"pred_{model_name}"] = test_pred
        for split_name, y_true, pred, frame in [
            ("valid", y[valid_idx], valid_pred, train.iloc[valid_idx]),
            ("test", y_test, test_pred, test),
        ]:
            metrics = regression_metrics(y_true, pred)
            row = {
                "task": task,
                "seed": seed,
                "model": model_name,
                "selection_objective": selection_objective,
                "split": split_name,
                "n": len(y_true),
                "n_cliff": int(frame["cliff_mol"].sum()),
                **metrics,
            }
            rows.append(add_cliff_metrics(row, y_true, pred, frame))

    valid_matrix = np.column_stack(valid_pred_cols)
    test_matrix = np.column_stack(test_pred_cols)
    model_names = list(models)
    valid_rmse = np.sqrt(np.mean((valid_matrix - y[valid_idx, None]) ** 2, axis=0))
    best_idx = int(np.argmin(valid_rmse))
    candidates = {
        f"best_single_{model_names[best_idx]}": (valid_matrix[:, best_idx], test_matrix[:, best_idx]),
        "consensus_multifp": (valid_matrix.mean(axis=1), test_matrix.mean(axis=1)),
    }
    stack_valid, stack_test = stack_predictions(valid_matrix, y[valid_idx], test_matrix, seed)
    candidates["stack_multifp"] = (stack_valid, stack_test)
    candidate_valid_score = {
        name: selection_score(y[valid_idx], pred[0], train.iloc[valid_idx], selection_objective)
        for name, pred in candidates.items()
    }
    selected_name = min(candidate_valid_score, key=candidate_valid_score.get)
    for name, (valid_pred, test_pred) in candidates.items():
        pred_output[f"pred_{name}"] = test_pred
        for split_name, y_true, pred, frame in [
            ("valid", y[valid_idx], valid_pred, train.iloc[valid_idx]),
            ("test", y_test, test_pred, test),
        ]:
            metrics = regression_metrics(y_true, pred)
            row = {
                "task": task,
                "seed": seed,
                "model": name,
                "selection_objective": selection_objective,
                "validation_selection_score": candidate_valid_score[name],
                "selected_by_validation": int(name == selected_name),
                "split": split_name,
                "n": len(y_true),
                "n_cliff": int(frame["cliff_mol"].sum()),
                **metrics,
            }
            rows.append(add_cliff_metrics(row, y_true, pred, frame))
    pred_output["selected_model"] = selected_name
    pred_output["y_pred"] = pred_output[f"pred_{selected_name}"]
    pred_output.to_csv(output_dir / f"{task}_seed{seed}_predictions.csv", index=False)
    return rows


def summarize(metrics: pd.DataFrame, output_dir: Path) -> None:
    metrics.to_csv(output_dir / "metrics_raw.csv", index=False)
    numeric_cols = [col for col in metrics.columns if pd.api.types.is_numeric_dtype(metrics[col])]
    id_cols = {"seed", "selected_by_validation"}
    metric_cols = [col for col in numeric_cols if col not in id_cols]
    summary = (
        metrics[metrics["split"] == "test"]
        .groupby(["task", "model"], dropna=False)[metric_cols]
        .agg(["mean", "std"])
        .reset_index()
    )
    summary.to_csv(output_dir / "metrics_summary.csv", index=False)
    selected = metrics[(metrics["split"] == "test") & (metrics.get("selected_by_validation", 0) == 1)]
    if not selected.empty:
        selected_summary = selected.groupby("task")[metric_cols].agg(["mean", "std"]).reset_index()
        selected_summary.to_csv(output_dir / "selected_summary.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a lightweight MoleculeACE activity-cliff benchmark.")
    parser.add_argument("--tasks", nargs="*", default=None)
    parser.add_argument("--max-tasks", type=int, default=None)
    parser.add_argument("--seeds", nargs="*", type=int, default=[13, 17, 23])
    parser.add_argument("--n-estimators", type=int, default=150)
    parser.add_argument("--cliff-weight", type=float, default=0.0)
    parser.add_argument("--selection-objective", choices=["overall", "cliff", "balanced"], default="overall")
    parser.add_argument("--output-dir", default=str(ROOT / "reports" / "moleculeace_multifp"))
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tasks = args.tasks or get_dataset_config_names("karina-zadorozhny/moleculeace")
    tasks = sorted(tasks)
    if args.max_tasks is not None:
        tasks = tasks[: args.max_tasks]
    rows: list[dict] = []
    for task in tasks:
        for seed in args.seeds:
            print(f"start task={task} seed={seed}", flush=True)
            rows.extend(evaluate_task(task, seed, args.n_estimators, output_dir, args.cliff_weight, args.selection_objective))
            summarize(pd.DataFrame(rows), output_dir)
    metrics = pd.DataFrame(rows)
    summarize(metrics, output_dir)
    print(metrics[metrics["split"] == "test"].tail(30).to_string(index=False))


if __name__ == "__main__":
    main()
