from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from torch import nn
from torch_geometric.loader import DataLoader
from tqdm import tqdm

from .datasets import DatasetSpec, load_dataset
from .evaluate import compute_metrics
from .features import (
    descriptor_vector,
    feature_dimensions,
    morgan_fingerprint,
    multi_fingerprint_vector,
    smiles_to_graph,
)
from .models import DMPNNModel, FZYCMolModel, GraphOnlyModel, GraphTransformerModel, contrastive_alignment_loss
from .splits import make_split


@dataclass
class RunResult:
    dataset: str
    model: str
    seed: int
    split: str
    task_type: str
    metrics: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "model": self.model,
            "seed": self.seed,
            "split": self.split,
            "task_type": self.task_type,
            **self.metrics,
        }


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(False)


def _feature_matrix(frame: pd.DataFrame) -> np.ndarray:
    fps = np.vstack([morgan_fingerprint(smiles) for smiles in frame["smiles"]])
    desc = np.vstack([descriptor_vector(smiles) for smiles in frame["smiles"]])
    return np.hstack([fps, desc]).astype(np.float32)


def _multi_feature_matrix(frame: pd.DataFrame) -> np.ndarray:
    return np.vstack([multi_fingerprint_vector(smiles) for smiles in frame["smiles"]]).astype(np.float32)


def _feature_matrix_from_graphs(graphs: list) -> np.ndarray:
    fps = np.vstack([graph.fp.view(-1).numpy() for graph in graphs])
    desc = np.vstack([graph.desc.view(-1).numpy() for graph in graphs])
    return np.hstack([fps, desc]).astype(np.float32)


def _feature_matrix_for_model(model_name: str, frame: pd.DataFrame, graphs: list | None = None) -> np.ndarray:
    if model_name.endswith("_multifp"):
        return _multi_feature_matrix(frame)
    if graphs is not None:
        return _feature_matrix_from_graphs(graphs)
    return _feature_matrix(frame)


def _feature_cache_key(model_name: str) -> str:
    return "multifp" if model_name.endswith("_multifp") else "morgan_desc"


def _xgboost_estimator(model_name: str, task_type: str, seed: int, y_train: np.ndarray):
    try:
        from xgboost import XGBClassifier, XGBRegressor
    except ImportError as exc:
        raise ImportError("Install xgboost to use xgb_morgan.") from exc
    if task_type == "regression":
        n_estimators = 250 if model_name.endswith("_multifp") else 600
        max_depth = 3 if model_name.endswith("_multifp") else 4
        return XGBRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=0.035,
            subsample=0.9,
            colsample_bytree=0.8,
            reg_alpha=0.0,
            reg_lambda=2.0,
            objective="reg:squarederror",
            tree_method="hist",
            random_state=seed,
            n_jobs=-1,
        )
    positives = float((y_train == 1).sum())
    negatives = float((y_train == 0).sum())
    scale_pos_weight = negatives / positives if positives > 0 else 1.0
    return XGBClassifier(
        n_estimators=250 if model_name.endswith("_multifp") else 600,
        max_depth=3 if model_name.endswith("_multifp") else 4,
        learning_rate=0.035,
        subsample=0.9,
        colsample_bytree=0.8,
        reg_alpha=0.0,
        reg_lambda=2.0,
        objective="binary:logistic",
        eval_metric="logloss",
        tree_method="hist",
        scale_pos_weight=scale_pos_weight,
        random_state=seed,
        n_jobs=-1,
    )


def _lightgbm_estimator(model_name: str, task_type: str, seed: int):
    try:
        from lightgbm import LGBMClassifier, LGBMRegressor
    except ImportError as exc:
        raise ImportError("Install lightgbm to use lgbm_morgan.") from exc
    if task_type == "regression":
        return LGBMRegressor(
            n_estimators=300 if model_name.endswith("_multifp") else 800,
            learning_rate=0.03,
            num_leaves=31,
            subsample=0.9,
            colsample_bytree=0.8,
            reg_lambda=2.0,
            random_state=seed,
            n_jobs=-1,
            verbosity=-1,
        )
    return LGBMClassifier(
        n_estimators=300 if model_name.endswith("_multifp") else 800,
        learning_rate=0.03,
        num_leaves=31,
        subsample=0.9,
        colsample_bytree=0.8,
        reg_lambda=2.0,
        class_weight="balanced",
        random_state=seed,
        n_jobs=-1,
        verbosity=-1,
    )


def run_sklearn_model(
    model_name: str,
    frame: pd.DataFrame,
    spec: DatasetSpec,
    split_name: str,
    seed: int,
    output_dir: str | Path | None = None,
    feature_matrix: np.ndarray | None = None,
) -> RunResult:
    split = make_split(frame, split_name, seed)
    x = feature_matrix if feature_matrix is not None else _feature_matrix(frame)
    y = frame["y"].to_numpy()
    if spec.task_type == "regression":
        if model_name == "rf_morgan":
            estimator = RandomForestRegressor(n_estimators=300, random_state=seed, n_jobs=-1)
        elif model_name == "rf_multifp":
            estimator = RandomForestRegressor(n_estimators=300, random_state=seed, n_jobs=-1)
        elif model_name == "extratrees_multifp":
            estimator = ExtraTreesRegressor(n_estimators=300, random_state=seed, n_jobs=-1)
        elif model_name == "xgb_morgan":
            estimator = _xgboost_estimator(model_name, spec.task_type, seed, y[split.train])
        elif model_name == "xgb_multifp":
            estimator = _xgboost_estimator(model_name, spec.task_type, seed, y[split.train])
        elif model_name == "lgbm_morgan":
            estimator = _lightgbm_estimator(model_name, spec.task_type, seed)
        elif model_name == "lgbm_multifp":
            estimator = _lightgbm_estimator(model_name, spec.task_type, seed)
        else:
            estimator = MLPRegressor(
                hidden_layer_sizes=(256, 128),
                activation="relu",
                alpha=1e-4,
                learning_rate_init=1e-3,
                max_iter=300,
                random_state=seed,
                early_stopping=True,
            )
    else:
        if model_name == "rf_morgan":
            estimator = RandomForestClassifier(
                n_estimators=300,
                random_state=seed,
                n_jobs=-1,
                class_weight="balanced_subsample",
            )
        elif model_name == "rf_multifp":
            estimator = RandomForestClassifier(
                n_estimators=300,
                random_state=seed,
                n_jobs=-1,
                class_weight="balanced_subsample",
            )
        elif model_name == "extratrees_multifp":
            estimator = ExtraTreesClassifier(
                n_estimators=300,
                random_state=seed,
                n_jobs=-1,
                class_weight="balanced",
            )
        elif model_name == "xgb_morgan":
            estimator = _xgboost_estimator(model_name, spec.task_type, seed, y[split.train])
        elif model_name == "xgb_multifp":
            estimator = _xgboost_estimator(model_name, spec.task_type, seed, y[split.train])
        elif model_name == "lgbm_morgan":
            estimator = _lightgbm_estimator(model_name, spec.task_type, seed)
        elif model_name == "lgbm_multifp":
            estimator = _lightgbm_estimator(model_name, spec.task_type, seed)
        else:
            estimator = MLPClassifier(
                hidden_layer_sizes=(256, 128),
                activation="relu",
                alpha=1e-4,
                learning_rate_init=1e-3,
                max_iter=300,
                random_state=seed,
                early_stopping=True,
            )
    steps = [("imputer", SimpleImputer(strategy="median"))]
    if model_name in {"rf_morgan", "rf_multifp", "extratrees_multifp", "mlp_descriptor"}:
        steps.append(("scaler", StandardScaler(with_mean=False)))
    steps.append(("model", estimator))
    pipeline = Pipeline(steps)
    pipeline.fit(x[split.train], y[split.train])
    if spec.task_type == "classification" and hasattr(pipeline[-1], "predict_proba"):
        valid_pred = pipeline.predict_proba(x[split.valid])[:, 1]
        pred = pipeline.predict_proba(x[split.test])[:, 1]
    else:
        valid_pred = pipeline.predict(x[split.valid])
        pred = pipeline.predict(x[split.test])
    metrics = compute_metrics(spec.task_type, y[split.test], pred)
    if output_dir is not None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        pred_frame = pd.DataFrame(
            {
                "smiles": frame.iloc[split.test]["smiles"].to_numpy(),
                "y_true": y[split.test],
                "y_pred": pred,
            }
        )
        pred_frame.to_csv(out / f"{spec.name}_{model_name}_seed{seed}_predictions.csv", index=False)
        valid_frame = pd.DataFrame(
            {
                "smiles": frame.iloc[split.valid]["smiles"].to_numpy(),
                "y_true": y[split.valid],
                "y_pred": valid_pred,
            }
        )
        valid_frame.to_csv(out / f"{spec.name}_{model_name}_seed{seed}_valid_predictions.csv", index=False)
    return RunResult(spec.name, model_name, seed, split_name, spec.task_type, metrics)


def _build_graphs(frame: pd.DataFrame, spec: DatasetSpec) -> list:
    return [
        smiles_to_graph(row.smiles, row.y, task_type=spec.task_type)
        for row in tqdm(frame.itertuples(index=False), total=len(frame), desc=f"featurize:{spec.name}")
    ]


def _load_or_build_graphs(
    frame: pd.DataFrame,
    spec: DatasetSpec,
    data_dir: str | Path,
    max_rows: int | None,
    cache_graphs: bool = True,
) -> list:
    if not cache_graphs:
        return _build_graphs(frame, spec)
    cache_dir = Path(data_dir) / "processed"
    cache_dir.mkdir(parents=True, exist_ok=True)
    size_tag = f"n{max_rows}" if max_rows is not None else "all"
    cache_path = cache_dir / f"{spec.name}_{size_tag}_graphs.pt"
    if cache_path.exists():
        print(f"load_graph_cache dataset={spec.name} path={cache_path}", flush=True)
        return torch.load(cache_path, weights_only=False)
    graphs = _build_graphs(frame, spec)
    torch.save(graphs, cache_path)
    print(f"save_graph_cache dataset={spec.name} path={cache_path}", flush=True)
    return graphs


def _clone_graphs(graphs: list) -> list:
    return [graph.clone() for graph in graphs]


def _apply_descriptor_scaler(graphs: list, train_idx: np.ndarray) -> None:
    train_desc = torch.cat([graphs[i].desc for i in train_idx], dim=0).numpy()
    scaler = StandardScaler()
    scaler.fit(train_desc)
    for graph in graphs:
        scaled = scaler.transform(graph.desc.numpy())
        graph.desc = torch.tensor(scaled, dtype=torch.float32)


def _target_scaler(graphs: list, train_idx: np.ndarray, task_type: str):
    if task_type != "regression":
        return None
    y_train = torch.stack([graphs[i].y for i in train_idx]).view(-1).numpy()
    mean = float(y_train.mean())
    std = float(y_train.std() if y_train.std() > 1e-8 else 1.0)
    for graph in graphs:
        graph.y_raw = graph.y.clone()
        graph.y = (graph.y - mean) / std
    return mean, std


def _unscale(values: np.ndarray, scaler):
    if scaler is None:
        return values
    mean, std = scaler
    return values * std + mean


def _loss_fn(task_type: str, graphs: list, train_idx: np.ndarray, device: torch.device):
    if task_type == "regression":
        return nn.MSELoss()
    y_train = torch.stack([graphs[i].y for i in train_idx]).view(-1).float()
    positives = float((y_train == 1).sum().item())
    negatives = float((y_train == 0).sum().item())
    if positives > 0 and negatives > 0:
        pos_weight = torch.tensor([negatives / positives], dtype=torch.float32, device=device)
        return nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    return nn.BCEWithLogitsLoss()


def _evaluate_neural(model, loader, task_type: str, y_scaler, device: torch.device) -> tuple[dict[str, float], np.ndarray, np.ndarray, np.ndarray]:
    model.eval()
    preds: list[np.ndarray] = []
    trues: list[np.ndarray] = []
    gates: list[np.ndarray] = []
    with torch.no_grad():
        for batch in loader:
            batch = batch.to(device)
            pred, aux = model(batch, return_aux=True)
            preds.append(pred.detach().cpu().numpy())
            if hasattr(batch, "y_raw"):
                trues.append(batch.y_raw.view(-1).detach().cpu().numpy())
            else:
                trues.append(batch.y.view(-1).detach().cpu().numpy())
            if "gate" in aux:
                gates.append(aux["gate"].detach().cpu().numpy())
    y_pred = np.concatenate(preds)
    y_true = np.concatenate(trues)
    y_pred_eval = _unscale(y_pred, y_scaler)
    metrics = compute_metrics(task_type, y_true, y_pred_eval)
    gate_arr = np.concatenate(gates, axis=0) if gates else np.empty((0, 3))
    return metrics, y_true, y_pred_eval, gate_arr


def run_neural_model(
    model_name: str,
    frame: pd.DataFrame,
    spec: DatasetSpec,
    split_name: str,
    seed: int,
    epochs: int,
    batch_size: int,
    hidden_dim: int,
    layers: int,
    lr: float,
    weight_decay: float,
    contrastive_weight: float,
    num_workers: int,
    output_dir: str | Path,
    base_graphs: list | None = None,
    patience: int | None = None,
) -> RunResult:
    set_seed(seed)
    split = make_split(frame, split_name, seed)
    graphs = _clone_graphs(base_graphs) if base_graphs is not None else _build_graphs(frame, spec)
    _apply_descriptor_scaler(graphs, split.train)
    y_scaler = _target_scaler(graphs, split.train, spec.task_type)

    train_loader = DataLoader([graphs[i] for i in split.train], batch_size=batch_size, shuffle=True, num_workers=num_workers)
    valid_loader = DataLoader([graphs[i] for i in split.valid], batch_size=batch_size, shuffle=False, num_workers=num_workers)
    test_loader = DataLoader([graphs[i] for i in split.test], batch_size=batch_size, shuffle=False, num_workers=num_workers)

    atom_dim, bond_dim, desc_dim = feature_dimensions()
    fp_dim = int(graphs[0].fp.shape[-1])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model_contrastive_weight = contrastive_weight
    if model_name == "gin":
        model = GraphOnlyModel(atom_dim, bond_dim, hidden_dim, layers)
    elif model_name == "dmpnn":
        model = DMPNNModel(atom_dim, bond_dim, hidden_dim, layers)
    elif model_name == "graph_transformer":
        model = GraphTransformerModel(atom_dim, bond_dim, hidden_dim, layers)
    elif model_name in {"fzyc_mol", "fzyc_mol_no_contrast"}:
        model = FZYCMolModel(atom_dim, bond_dim, fp_dim, desc_dim, hidden_dim, layers)
        if model_name == "fzyc_mol_no_contrast":
            model_contrastive_weight = 0.0
    elif model_name == "fzyc_mol_gt":
        model = FZYCMolModel(
            atom_dim,
            bond_dim,
            fp_dim,
            desc_dim,
            hidden_dim,
            layers,
            graph_encoder="transformer",
        )
    elif model_name == "fzyc_mol_no_fp":
        model = FZYCMolModel(atom_dim, bond_dim, fp_dim, desc_dim, hidden_dim, layers, use_fp=False)
    elif model_name == "fzyc_mol_no_desc":
        model = FZYCMolModel(atom_dim, bond_dim, fp_dim, desc_dim, hidden_dim, layers, use_desc=False)
    elif model_name == "fzyc_mol_static":
        model = FZYCMolModel(atom_dim, bond_dim, fp_dim, desc_dim, hidden_dim, layers, fusion="mean")
    else:
        raise ValueError(f"Unknown neural model '{model_name}'")
    model = model.to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    criterion = _loss_fn(spec.task_type, graphs, split.train, device)
    best_valid = float("inf") if spec.task_type == "regression" else -float("inf")
    best_state = None
    epochs_without_improvement = 0
    primary_metric = "rmse" if spec.task_type == "regression" else "roc_auc"
    print(
        f"start dataset={spec.name} model={model_name} seed={seed} "
        f"epochs={epochs} device={device}",
        flush=True,
    )

    for _epoch in range(1, epochs + 1):
        model.train()
        for batch in train_loader:
            batch = batch.to(device)
            optimizer.zero_grad()
            pred, aux = model(batch, return_aux=True)
            target = batch.y.view(-1).float()
            loss = criterion(pred, target)
            if "fzyc_mol" in model_name and model_contrastive_weight > 0:
                align = pred.new_tensor(0.0)
                if "fp" in aux:
                    align = align + contrastive_alignment_loss(aux["graph"], aux["fp"])
                if "desc" in aux:
                    align = align + contrastive_alignment_loss(aux["graph"], aux["desc"])
                loss = loss + model_contrastive_weight * align
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()

        valid_metrics, _, _, _ = _evaluate_neural(model, valid_loader, spec.task_type, y_scaler, device)
        score = valid_metrics.get(primary_metric, float("nan"))
        if spec.task_type == "classification" and not np.isfinite(score):
            for fallback_metric in ("pr_auc", "accuracy", "f1"):
                fallback_score = valid_metrics.get(fallback_metric, float("nan"))
                if np.isfinite(fallback_score):
                    score = fallback_score
                    break
        is_better = score < best_valid if spec.task_type == "regression" else score > best_valid
        if is_better or best_state is None:
            best_valid = score
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
        if patience is not None and patience > 0 and epochs_without_improvement >= patience:
            print(
                f"early_stop dataset={spec.name} model={model_name} seed={seed} "
                f"epoch={_epoch} best_{primary_metric}={best_valid:.6g}",
                flush=True,
            )
            break

    if best_state is not None:
        model.load_state_dict(best_state)
    valid_metrics, y_valid, pred_valid, valid_gates = _evaluate_neural(
        model,
        valid_loader,
        spec.task_type,
        y_scaler,
        device,
    )
    metrics, y_true, y_pred, gates = _evaluate_neural(model, test_loader, spec.task_type, y_scaler, device)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    pred_frame = pd.DataFrame(
        {
            "smiles": frame.iloc[split.test]["smiles"].to_numpy(),
            "y_true": y_true,
            "y_pred": y_pred,
        }
    )
    pred_frame.to_csv(out / f"{spec.name}_{model_name}_seed{seed}_predictions.csv", index=False)
    valid_frame = pd.DataFrame(
        {
            "smiles": frame.iloc[split.valid]["smiles"].to_numpy(),
            "y_true": y_valid,
            "y_pred": pred_valid,
        }
    )
    valid_frame.to_csv(out / f"{spec.name}_{model_name}_seed{seed}_valid_predictions.csv", index=False)
    if gates.size:
        gate_names = getattr(model, "expert_names", [str(i) for i in range(gates.shape[1])])
        gate_frame = pd.DataFrame(gates, columns=[f"gate_{name}" for name in gate_names])
        gate_frame.to_csv(out / f"{spec.name}_{model_name}_seed{seed}_gates.csv", index=False)
    if valid_gates.size:
        gate_names = getattr(model, "expert_names", [str(i) for i in range(valid_gates.shape[1])])
        valid_gate_frame = pd.DataFrame(valid_gates, columns=[f"gate_{name}" for name in gate_names])
        valid_gate_frame.to_csv(out / f"{spec.name}_{model_name}_seed{seed}_valid_gates.csv", index=False)
    metric_text = " ".join(f"{key}={value:.6g}" for key, value in metrics.items())
    print(f"done dataset={spec.name} model={model_name} seed={seed} {metric_text}", flush=True)

    return RunResult(spec.name, model_name, seed, split_name, spec.task_type, metrics)


def run_config(config: dict[str, Any], data_dir: str | Path = "data") -> pd.DataFrame:
    output_dir = Path(config.get("output_dir", "reports/run"))
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "metrics_raw.csv"
    if bool(config.get("resume", True)) and metrics_path.exists():
        existing = pd.read_csv(metrics_path)
        results: list[dict[str, Any]] = existing.to_dict("records")
        completed = {
            (str(row["dataset"]), str(row["model"]), int(row["seed"]))
            for row in results
            if {"dataset", "model", "seed"}.issubset(row.keys())
        }
    else:
        results = []
        completed = set()

    for dataset in config["datasets"]:
        model_names = list(config["models"])
        seeds = [int(seed) for seed in config["seeds"]]
        expected = {(dataset, model_name, seed) for seed in seeds for model_name in model_names}
        if expected.issubset(completed):
            print(f"skip dataset={dataset} all planned runs already complete", flush=True)
            continue
        frame, spec = load_dataset(dataset, data_dir=data_dir, max_rows=config.get("max_rows"))
        sklearn_model_names = {
            "rf_morgan",
            "mlp_descriptor",
            "xgb_morgan",
            "lgbm_morgan",
            "rf_multifp",
            "xgb_multifp",
            "lgbm_multifp",
            "extratrees_multifp",
        }
        base_graphs = (
            _load_or_build_graphs(
                frame,
                spec,
                data_dir=data_dir,
                max_rows=config.get("max_rows"),
                cache_graphs=bool(config.get("cache_graphs", True)),
            )
            if any(name not in sklearn_model_names for name in model_names)
            else None
        )
        feature_matrices: dict[str, np.ndarray] = {}
        for name in model_names:
            if name in sklearn_model_names:
                key = _feature_cache_key(name)
                if key not in feature_matrices:
                    feature_matrices[key] = _feature_matrix_for_model(name, frame, base_graphs)
        stats = {
            "dataset": dataset,
            "rows": len(frame),
            "task_type": spec.task_type,
            "positives": int(frame["y"].sum()) if spec.task_type == "classification" else None,
        }
        stats_path = output_dir / "dataset_stats.jsonl"
        if not stats_path.exists() or not bool(config.get("resume", True)):
            stats_path.open("a", encoding="utf-8").write(json.dumps(stats) + "\n")
        for seed in seeds:
            for model_name in model_names:
                if (dataset, model_name, int(seed)) in completed:
                    print(f"skip dataset={dataset} model={model_name} seed={seed}", flush=True)
                    continue
                if model_name in sklearn_model_names:
                    result = run_sklearn_model(
                        model_name,
                        frame,
                        spec,
                        config.get("split", "scaffold"),
                        seed,
                        output_dir=output_dir,
                        feature_matrix=feature_matrices[_feature_cache_key(model_name)],
                    )
                else:
                    result = run_neural_model(
                        model_name=model_name,
                        frame=frame,
                        spec=spec,
                        split_name=config.get("split", "scaffold"),
                        seed=seed,
                        epochs=int(config.get("epochs", 60)),
                        batch_size=int(config.get("batch_size", 64)),
                        hidden_dim=int(config.get("hidden_dim", 128)),
                        layers=int(config.get("layers", 4)),
                        lr=float(config.get("lr", 1e-3)),
                        weight_decay=float(config.get("weight_decay", 1e-5)),
                        contrastive_weight=float(config.get("contrastive_weight", 0.1)),
                        num_workers=int(config.get("num_workers", 0)),
                        output_dir=output_dir,
                        base_graphs=base_graphs,
                        patience=config.get("patience"),
                    )
                results.append(result.to_dict())
                completed.add((dataset, model_name, int(seed)))
                pd.DataFrame(results).to_csv(output_dir / "metrics_raw.csv", index=False)

    metrics = pd.DataFrame(results)
    metrics.to_csv(output_dir / "metrics_raw.csv", index=False)
    id_cols = {"dataset", "model", "task_type", "seed", "split"}
    metric_cols = [
        column
        for column in metrics.columns
        if column not in id_cols and pd.api.types.is_numeric_dtype(metrics[column])
    ]
    summary = (
        metrics.groupby(["dataset", "model", "task_type"], dropna=False)[metric_cols]
        .agg(["mean", "std"])
        .reset_index()
    )
    summary.to_csv(output_dir / "metrics_summary.csv", index=False)
    return metrics
