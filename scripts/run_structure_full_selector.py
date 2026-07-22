from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRegressor
from rdkit import RDLogger
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor, RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler, StandardScaler
from xgboost import XGBClassifier, XGBRegressor

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPT_DIR = ROOT / "scripts"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SCRIPT_DIR))

import build_validation_selector as selector
import run_descriptor_motif_baselines as motif_baselines
from fzyc_mol.analysis import max_train_similarity
from fzyc_mol.datasets import DATASETS, load_dataset
from fzyc_mol.evaluate import compute_metrics
from fzyc_mol.features import descriptor_vector, morgan_fingerprint, multi_fingerprint_vector
from run_pretrained_frozen_heads import load_embedding_matrix, rdkit_matrix
from run_split_realism_benchmark import structure_separated_split

RDLogger.DisableLog("rdApp.*")

DEFAULT_DATASETS = ["bace", "bbbp", "clintox", "tdc_pgp_broccatelli", "tdc_caco2_wang"]
PRETRAINED_ENCODERS = [
    ("chemberta_mtr", "DeepChem_ChemBERTa-77M-MTR"),
    ("chemberta_mlm", "DeepChem_ChemBERTa-77M-MLM"),
    ("molformer", "ibm_MoLFormer-XL-both-10pct"),
]


class ConstantEstimator:
    def __init__(self, value: float, task_type: str) -> None:
        self.value = float(value)
        self.task_type = task_type

    def fit(self, x, y):
        return self

    def predict(self, x):
        return np.full(len(x), self.value, dtype=float)

    def predict_proba(self, x):
        prob = np.clip(np.full(len(x), self.value, dtype=float), 1e-7, 1 - 1e-7)
        return np.column_stack([1.0 - prob, prob])


def safe_encoder_id(name: str) -> str:
    return name.replace("/", "_")


def feature_matrix(dataset: str, frame: pd.DataFrame, feature_set: str) -> np.ndarray:
    smiles = frame["smiles"].tolist()
    if feature_set == "morgan_rdkit":
        return np.vstack([np.hstack([morgan_fingerprint(smi), descriptor_vector(smi, include_3d=False)]) for smi in smiles]).astype(np.float32)
    if feature_set == "multifp":
        return np.vstack([multi_fingerprint_vector(smi) for smi in smiles]).astype(np.float32)
    if feature_set == "descriptor":
        return np.vstack([motif_baselines.rdkit_descriptor_vector(smi) for smi in smiles]).astype(np.float32)
    if feature_set == "motif":
        return np.vstack([motif_baselines.motif_vector(smi) for smi in smiles]).astype(np.float32)
    if feature_set.startswith("pretrained:"):
        encoder = feature_set.split(":", 1)[1]
        path = ROOT / "data" / "processed" / "pretrained_embeddings" / encoder / f"{dataset}.npz"
        x = load_embedding_matrix(path, smiles)
        if feature_set.endswith("+rdkit"):
            x = np.hstack([x, rdkit_matrix(dataset, smiles)]).astype(np.float32)
        return x
    raise ValueError(feature_set)


def available_experts(dataset: str) -> dict[str, str]:
    experts = {
        "rf_morgan": "morgan_rdkit",
        "xgb_morgan": "morgan_rdkit",
        "lgbm_morgan": "morgan_rdkit",
        "extratrees_morgan": "morgan_rdkit",
        "rf_multifp": "multifp",
        "xgb_multifp": "multifp",
        "lgbm_multifp": "multifp",
        "extratrees_multifp": "multifp",
        "descriptor_mlp": "descriptor",
        "rf_motif": "motif",
        "lgbm_motif": "motif",
        "extratrees_motif": "motif",
    }
    for short, encoder in PRETRAINED_ENCODERS:
        path = ROOT / "data" / "processed" / "pretrained_embeddings" / encoder / f"{dataset}.npz"
        if path.exists():
            experts[f"{short}_frozen_head"] = f"pretrained:{encoder}"
            experts[f"{short}_rdkit_head"] = f"pretrained:{encoder}+rdkit"
    return experts


def family_sets(experts: dict[str, str]) -> dict[str, list[str]]:
    names = set(experts)
    families: dict[str, list[str]] = {
        "morgan_tree": [n for n in ["rf_morgan", "xgb_morgan", "lgbm_morgan", "extratrees_morgan"] if n in names],
        "multi_fingerprint": [n for n in ["rf_multifp", "xgb_multifp", "lgbm_multifp", "extratrees_multifp"] if n in names],
        "descriptor_motif": [n for n in ["descriptor_mlp", "rf_motif", "lgbm_motif", "extratrees_motif"] if n in names],
        "no_pretrained": [n for n in names if "head" not in n],
        "full": list(experts),
    }
    pretrained = [n for n in names if "head" in n]
    if pretrained:
        families["pretrained"] = pretrained
        families["full_plus_pretrained"] = list(experts)
    return {k: sorted(v) for k, v in families.items() if len(v) >= 1}


def build_estimator(model_name: str, task_type: str, seed: int, y_train: np.ndarray):
    if task_type == "classification" and len(np.unique(y_train.astype(int))) < 2:
        return ConstantEstimator(float(np.mean(y_train)), task_type)
    if task_type == "regression" and len(y_train) < 3:
        return ConstantEstimator(float(np.mean(y_train)), task_type)

    if "head" in model_name:
        if task_type == "regression":
            return Pipeline([("scaler", StandardScaler()), ("model", RidgeCV(alphas=np.logspace(-4, 4, 17)))])
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                ("model", LogisticRegression(max_iter=2000, class_weight="balanced", random_state=seed)),
            ]
        )

    if model_name == "descriptor_mlp":
        if task_type == "regression":
            model = MLPRegressor(
                hidden_layer_sizes=(128, 64),
                activation="tanh",
                alpha=1e-2,
                learning_rate_init=1e-4,
                early_stopping=True,
                n_iter_no_change=15,
                max_iter=300,
                random_state=seed,
            )
        else:
            model = MLPClassifier(
                hidden_layer_sizes=(128, 64),
                activation="tanh",
                alpha=1e-2,
                learning_rate_init=1e-4,
                early_stopping=True,
                n_iter_no_change=15,
                max_iter=300,
                random_state=seed,
            )
        return Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", RobustScaler()), ("model", model)])

    is_motif = "motif" in model_name
    if task_type == "regression":
        if model_name.startswith("rf_"):
            model = RandomForestRegressor(n_estimators=260 if is_motif else 320, max_features="sqrt", random_state=seed, n_jobs=-1)
        elif model_name.startswith("extratrees_"):
            model = ExtraTreesRegressor(n_estimators=320 if is_motif else 360, max_features="sqrt", random_state=seed, n_jobs=-1)
        elif model_name.startswith("xgb_"):
            model = XGBRegressor(
                n_estimators=260,
                max_depth=3,
                learning_rate=0.04,
                subsample=0.85,
                colsample_bytree=0.7,
                reg_lambda=2.0,
                objective="reg:squarederror",
                tree_method="hist",
                random_state=seed,
                n_jobs=4,
            )
        elif model_name.startswith("lgbm_"):
            model = LGBMRegressor(
                n_estimators=300,
                learning_rate=0.035,
                num_leaves=31,
                subsample=0.88,
                colsample_bytree=0.75,
                reg_lambda=2.0,
                random_state=seed,
                n_jobs=4,
                verbose=-1,
            )
        else:
            raise ValueError(model_name)
    else:
        positives = float((y_train == 1).sum())
        negatives = float((y_train == 0).sum())
        scale_pos_weight = negatives / positives if positives > 0 else 1.0
        if model_name.startswith("rf_"):
            model = RandomForestClassifier(n_estimators=260 if is_motif else 320, max_features="sqrt", class_weight="balanced_subsample", random_state=seed, n_jobs=-1)
        elif model_name.startswith("extratrees_"):
            model = ExtraTreesClassifier(n_estimators=320 if is_motif else 360, max_features="sqrt", class_weight="balanced", random_state=seed, n_jobs=-1)
        elif model_name.startswith("xgb_"):
            model = XGBClassifier(
                n_estimators=260,
                max_depth=3,
                learning_rate=0.04,
                subsample=0.85,
                colsample_bytree=0.7,
                reg_lambda=2.0,
                objective="binary:logistic",
                eval_metric="logloss",
                tree_method="hist",
                scale_pos_weight=scale_pos_weight,
                random_state=seed,
                n_jobs=4,
            )
        elif model_name.startswith("lgbm_"):
            model = LGBMClassifier(
                n_estimators=300,
                learning_rate=0.035,
                num_leaves=31,
                subsample=0.88,
                colsample_bytree=0.75,
                reg_lambda=2.0,
                class_weight="balanced",
                random_state=seed,
                n_jobs=4,
                verbose=-1,
            )
        else:
            raise ValueError(model_name)
    return Pipeline([("imputer", SimpleImputer(strategy="median")), ("model", model)])


def predict_estimator(model, x: np.ndarray, task_type: str) -> np.ndarray:
    if task_type == "classification" and hasattr(model, "predict_proba"):
        return np.clip(model.predict_proba(x)[:, 1], 1e-7, 1 - 1e-7)
    pred = model.predict(x)
    if task_type == "classification":
        return np.clip(1.0 / (1.0 + np.exp(-np.clip(pred, -60, 60))), 1e-7, 1 - 1e-7)
    return np.asarray(pred, dtype=float)


def add_ad_features(table: pd.DataFrame, pred_cols: list[str], train_smiles: list[str]) -> pd.DataFrame:
    out = table.copy()
    pred_matrix = out[pred_cols].to_numpy(dtype=float)
    out["ensemble_mean"] = pred_matrix.mean(axis=1)
    out["ensemble_std"] = pred_matrix.std(axis=1)
    out["ensemble_range"] = pred_matrix.max(axis=1) - pred_matrix.min(axis=1)
    out["max_train_tanimoto"] = max_train_similarity(train_smiles, out["smiles"].tolist())
    out["scaffold_distance"] = 1.0 - out["max_train_tanimoto"]
    return out


def build_candidate(dataset: str, seed: int, family: str, names: list[str], task_type: str, y_valid: np.ndarray, valid: pd.DataFrame, test: pd.DataFrame) -> list[dict]:
    pred_cols = [f"pred_{name}" for name in names]
    fit_idx, select_idx = selector.stratified_meta_split(valid, task_type, seed)
    meta_fit = valid.loc[fit_idx].copy()
    meta_select = valid.loc[select_idx].copy()
    bounds = selector.regression_clip_bounds(meta_fit["y_true"].to_numpy()) if task_type == "regression" else None
    candidates = []
    for method in ("consensus", "stack", "adaptive"):
        candidate_name = f"{method}_{family}"
        if method == "consensus":
            select_pred, select_diag = selector.consensus_predict(meta_select, pred_cols)
            test_pred, test_diag = selector.consensus_predict(test, pred_cols)
        elif method == "stack":
            select_model = selector.fit_stacker(task_type, meta_fit, pred_cols)
            select_pred = selector.predict_stacker(select_model, task_type, meta_select, pred_cols)
            final_model = selector.fit_stacker(task_type, valid, pred_cols)
            test_pred = selector.predict_stacker(final_model, task_type, test, pred_cols)
            select_diag = meta_select[["smiles", "max_train_tanimoto", "scaffold_distance", "ensemble_std"]].copy()
            test_diag = test[["smiles", "max_train_tanimoto", "scaffold_distance", "ensemble_std"]].copy()
        else:
            select_pred, select_diag = selector.adaptive_predict(task_type, meta_fit, meta_select, pred_cols)
            test_pred, test_diag = selector.adaptive_predict(task_type, valid, test, pred_cols)
        select_pred = selector.finalize_predictions(task_type, select_pred, bounds)
        test_pred = selector.finalize_predictions(task_type, test_pred, bounds)
        select_metrics = compute_metrics(task_type, meta_select["y_true"].to_numpy(), select_pred)
        test_metrics = compute_metrics(task_type, test["y_true"].to_numpy(), test_pred)
        metric, value, direction = selector.primary_value(task_type, select_metrics)
        candidates.append(
            {
                "dataset": dataset,
                "seed": seed,
                "family": family,
                "candidate": candidate_name,
                "method": method,
                "task_type": task_type,
                "selection_metric": metric,
                "selection_direction": direction,
                "selection_value": value,
                "valid_select": pd.DataFrame({"smiles": meta_select["smiles"].to_numpy(), "y_true": meta_select["y_true"].to_numpy(), "y_pred": select_pred}),
                "test": pd.DataFrame({"smiles": test["smiles"].to_numpy(), "y_true": test["y_true"].to_numpy(), "y_pred": test_pred}),
                "valid_diagnostics": select_diag,
                "test_diagnostics": test_diag,
                "valid_metrics": select_metrics,
                "test_metrics": test_metrics,
            }
        )
    return candidates


def run_dataset_seed(dataset: str, seed: int, output_dir: Path) -> tuple[list[dict], list[dict], list[dict]]:
    frame, spec = load_dataset(dataset, data_dir=ROOT / "data")
    split = structure_separated_split(frame, seed)
    y = frame["y"].to_numpy()
    experts = available_experts(dataset)
    feature_cache: dict[str, np.ndarray] = {}
    valid_base = pd.DataFrame({"smiles": frame.iloc[split.valid]["smiles"].to_numpy(), "y_true": y[split.valid]})
    test_base = pd.DataFrame({"smiles": frame.iloc[split.test]["smiles"].to_numpy(), "y_true": y[split.test]})
    member_rows = []
    valid = valid_base.copy()
    test = test_base.copy()
    train_smiles = frame.iloc[split.train]["smiles"].tolist()

    for expert_name, feature_set in experts.items():
        if feature_set not in feature_cache:
            try:
                feature_cache[feature_set] = feature_matrix(dataset, frame, feature_set)
            except (FileNotFoundError, KeyError):
                continue
        x = feature_cache[feature_set]
        est = build_estimator(expert_name, spec.task_type, seed, y[split.train])
        start = time.perf_counter()
        est.fit(x[split.train], y[split.train])
        fit_seconds = time.perf_counter() - start
        valid_pred = predict_estimator(est, x[split.valid], spec.task_type)
        test_pred = predict_estimator(est, x[split.test], spec.task_type)
        valid[f"pred_{expert_name}"] = valid_pred
        test[f"pred_{expert_name}"] = test_pred
        member_rows.append(
            {
                "dataset": dataset,
                "seed": seed,
                "model": expert_name,
                "feature_set": feature_set,
                "split": "structure",
                "task_type": spec.task_type,
                "n_train": int(len(split.train)),
                "n_valid": int(len(split.valid)),
                "n_test": int(len(split.test)),
                "fit_seconds": fit_seconds,
                **{f"valid_{k}": v for k, v in compute_metrics(spec.task_type, y[split.valid], valid_pred).items()},
                **{f"test_{k}": v for k, v in compute_metrics(spec.task_type, y[split.test], test_pred).items()},
            }
        )

    pred_cols = [col for col in valid.columns if col.startswith("pred_")]
    valid = add_ad_features(valid, pred_cols, train_smiles)
    test = add_ad_features(test, pred_cols, train_smiles)

    candidate_rows = []
    candidate_objects = []
    for family, names in family_sets({name: fs for name, fs in experts.items() if f"pred_{name}" in valid.columns}).items():
        candidates = build_candidate(dataset, seed, family, names, spec.task_type, y[split.valid], valid, test)
        candidate_objects.extend(candidates)
        for item in candidates:
            candidate_rows.append(
                {
                    "dataset": dataset,
                    "seed": seed,
                    "model": item["candidate"],
                    "family": item["family"],
                    "method": item["method"],
                    "split": "structure",
                    "task_type": spec.task_type,
                    "selection_metric": item["selection_metric"],
                    "selection_direction": item["selection_direction"],
                    "selection_value": item["selection_value"],
                    **{f"valid_{k}": v for k, v in item["valid_metrics"].items()},
                    **{f"test_{k}": v for k, v in item["test_metrics"].items()},
                }
            )
    return member_rows, candidate_rows, candidate_objects


def summarize(frame: pd.DataFrame, output_dir: Path, filename: str, group_cols: list[str]) -> None:
    if frame.empty:
        return
    metric_cols = [c for c in frame.columns if c not in set(group_cols + ["seed"]) and pd.api.types.is_numeric_dtype(frame[c])]
    summary = frame.groupby(group_cols, dropna=False)[metric_cols].agg(["mean", "std"]).reset_index()
    summary.to_csv(output_dir / filename, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run validation-selected full expert selector under structure-separated split.")
    parser.add_argument("--datasets", nargs="*", default=DEFAULT_DATASETS)
    parser.add_argument("--seeds", nargs="*", type=int, default=[13, 17, 23])
    parser.add_argument("--output-dir", default=str(ROOT / "reports" / "structure_full_selector"))
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    member_path = output_dir / "member_metrics_raw.csv"
    candidate_path = output_dir / "candidate_metrics_raw.csv"
    member_rows = pd.read_csv(member_path).to_dict("records") if args.resume and member_path.exists() else []
    candidate_rows = pd.read_csv(candidate_path).to_dict("records") if args.resume and candidate_path.exists() else []
    candidate_objects: list[dict] = []
    done = {(r["dataset"], int(r["seed"])) for r in candidate_rows} if args.resume and candidate_rows else set()

    for dataset in args.datasets:
        if dataset not in DATASETS:
            raise KeyError(dataset)
        for seed in args.seeds:
            if (dataset, seed) in done:
                print(f"skip dataset={dataset} seed={seed}", flush=True)
                continue
            print(f"start structure full selector dataset={dataset} seed={seed}", flush=True)
            m_rows, c_rows, c_objs = run_dataset_seed(dataset, seed, output_dir)
            member_rows.extend(m_rows)
            candidate_rows.extend(c_rows)
            candidate_objects.extend(c_objs)
            pd.DataFrame(member_rows).to_csv(member_path, index=False)
            pd.DataFrame(candidate_rows).to_csv(candidate_path, index=False)
            print(f"done dataset={dataset} seed={seed} candidates={len(c_rows)} experts={len(m_rows)}", flush=True)

    member_metrics = pd.DataFrame(member_rows)
    candidate_metrics = pd.DataFrame(candidate_rows)
    if candidate_metrics.empty:
        raise SystemExit("No candidate rows were produced.")
    summarize(member_metrics, output_dir, "member_metrics_summary.csv", ["dataset", "model", "feature_set", "split", "task_type"])
    summarize(candidate_metrics, output_dir, "candidate_metrics_summary.csv", ["dataset", "model", "family", "method", "split", "task_type"])

    chosen_rows = []
    selected_rows = []
    for dataset, group in candidate_metrics.groupby("dataset"):
        task_type = str(group["task_type"].iloc[0])
        metric = "valid_rmse" if task_type == "regression" else "valid_roc_auc"
        if metric not in group or group[metric].isna().all():
            metric = "selection_value"
        rank = group.groupby("model", as_index=False)[metric].mean().dropna(subset=[metric])
        rank = rank.sort_values(metric, ascending=task_type == "regression")
        selected = str(rank.iloc[0]["model"])
        chosen_rows.append({"dataset": dataset, "selected_candidate": selected, "selection_metric": metric, "validation_score": float(rank.iloc[0][metric])})
        selected_group = group[group["model"].eq(selected)].copy()
        selected_group = selected_group.rename(columns={"model": "selected_candidate"})
        selected_group.insert(2, "model", "structure_validation_selector")
        selected_rows.extend(selected_group.to_dict("records"))

    pd.DataFrame(chosen_rows).to_csv(output_dir / "selected_candidates.csv", index=False)
    selected_metrics = pd.DataFrame(selected_rows)
    selected_metrics.to_csv(output_dir / "metrics_raw.csv", index=False)
    summarize(selected_metrics, output_dir, "metrics_summary.csv", ["dataset", "model", "selected_candidate", "split", "task_type"])

    # Rebuild candidate objects if resumed so selected prediction files exist.
    if args.resume and not candidate_objects:
        print("resume mode has metrics only; rebuilding selected prediction files", flush=True)
        for dataset in args.datasets:
            for seed in args.seeds:
                _m_rows, _c_rows, c_objs = run_dataset_seed(dataset, seed, output_dir)
                candidate_objects.extend(c_objs)

    chosen_map = {row["dataset"]: row["selected_candidate"] for row in chosen_rows}
    for item in candidate_objects:
        if chosen_map.get(item["dataset"]) != item["candidate"]:
            continue
        prefix = f"{item['dataset']}_validation_selector_seed{item['seed']}"
        item["valid_select"].to_csv(output_dir / f"{prefix}_valid_predictions.csv", index=False)
        item["valid_diagnostics"].to_csv(output_dir / f"{prefix}_valid_weights.csv", index=False)
        item["test"].to_csv(output_dir / f"{prefix}_predictions.csv", index=False)
        item["test_diagnostics"].to_csv(output_dir / f"{prefix}_weights.csv", index=False)

    print(pd.DataFrame(chosen_rows).to_string(index=False))
    print(selected_metrics.to_string(index=False))


if __name__ == "__main__":
    main()
