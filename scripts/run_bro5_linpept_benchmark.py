from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import AllChem
from scipy.stats import spearmanr
from sklearn.base import clone
from sklearn.decomposition import PCA
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    matthews_corrcoef,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.features import descriptor_vector, morgan_fingerprint
from fzyc_mol.splits import scaffold_split, random_split


RDLogger.DisableLog("rdApp.*")

EXTERNAL = ROOT / "work" / "external" / "Benchmark-ADMET-2025" / "data" / "origin_data"
OUT = ROOT / "reports" / "bro5_linpept_20260611"
FIG = OUT / "figures"
OUT.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

DATASETS = {
    "linpept_cellpen": ("LinPept_CellPen.csv", "LinPept_CellPen"),
    "linpept_nonfouling": ("LinPept_NonFouling.csv", "LinPept_NonFouling"),
}


def standardize_data() -> pd.DataFrame:
    status_rows = []
    bro5_dir = ROOT / "data" / "bro5"
    bro5_dir.mkdir(parents=True, exist_ok=True)
    for dataset, (filename, target_col) in DATASETS.items():
        src = EXTERNAL / filename
        if not src.exists():
            status_rows.append({"dataset": dataset, "status": "missing_data", "path": "", "reason": f"missing {src}"})
            continue
        df = pd.read_csv(src)
        if "smiles" not in df.columns or target_col not in df.columns:
            status_rows.append({"dataset": dataset, "status": "invalid_schema", "path": str(src), "reason": "requires smiles and target column"})
            continue
        out = df[["smiles", target_col]].rename(columns={target_col: "y"}).copy()
        out["y"] = pd.to_numeric(out["y"], errors="coerce")
        out = out.dropna(subset=["smiles", "y"]).drop_duplicates("smiles").reset_index(drop=True)
        valid = [Chem.MolFromSmiles(str(smi)) is not None for smi in out["smiles"]]
        out = out.loc[valid].reset_index(drop=True)
        out["y"] = out["y"].astype(int)
        path = bro5_dir / f"{dataset}.csv"
        out.to_csv(path, index=False)
        counts = out["y"].value_counts().to_dict()
        status_rows.append(
            {
                "dataset": dataset,
                "status": "available_and_run",
                "path": str(path),
                "n": len(out),
                "positive_rate": float(out["y"].mean()),
                "class_counts": json.dumps({str(k): int(v) for k, v in counts.items()}, ensure_ascii=False),
                "source_file": str(src),
            }
        )
    status = pd.DataFrame(status_rows)
    status.to_csv(OUT / "linpept_data_status.csv", index=False)
    return status


def feature_matrix(smiles: pd.Series) -> np.ndarray:
    rows = []
    for smi in smiles.astype(str):
        rows.append(np.hstack([morgan_fingerprint(smi, n_bits=2048, radius=2), descriptor_vector(smi, include_3d=False)]))
    return np.nan_to_num(np.vstack(rows).astype(np.float32), copy=False)


def bitvectors(smiles: pd.Series):
    fps = []
    for smi in smiles.astype(str):
        mol = Chem.MolFromSmiles(smi)
        fps.append(AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=2048))
    return fps


def models(seed: int) -> dict[str, object]:
    out: dict[str, object] = {
        "logreg_balanced": Pipeline(
            [
                ("scale", StandardScaler(with_mean=False)),
                ("model", LogisticRegression(max_iter=3000, class_weight="balanced", solver="liblinear", random_state=seed)),
            ]
        ),
        "rf_balanced": RandomForestClassifier(
            n_estimators=180,
            max_features="sqrt",
            min_samples_leaf=1,
            class_weight="balanced_subsample",
            random_state=seed,
            n_jobs=-1,
        ),
        "extratrees_balanced": ExtraTreesClassifier(
            n_estimators=240,
            max_features="sqrt",
            min_samples_leaf=1,
            class_weight="balanced",
            random_state=seed,
            n_jobs=-1,
        ),
    }
    try:
        from lightgbm import LGBMClassifier

        out["lgbm_balanced"] = LGBMClassifier(
            n_estimators=180,
            learning_rate=0.035,
            num_leaves=31,
            subsample=0.85,
            colsample_bytree=0.75,
            reg_lambda=2.0,
            class_weight="balanced",
            random_state=seed,
            n_jobs=4,
            verbose=-1,
        )
    except Exception:
        pass
    try:
        from xgboost import XGBClassifier

        out["xgb_balanced"] = XGBClassifier(
            n_estimators=180,
            max_depth=4,
            learning_rate=0.035,
            subsample=0.85,
            colsample_bytree=0.75,
            reg_lambda=2.0,
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=seed,
            n_jobs=4,
        )
    except Exception:
        pass
    return out


def perimeter_split(x: np.ndarray, seed: int) -> dict[str, np.ndarray]:
    pca = PCA(n_components=2, random_state=seed)
    z = pca.fit_transform(x)
    dist = np.linalg.norm(z - z.mean(axis=0, keepdims=True), axis=1)
    order = np.argsort(-dist)
    n = len(order)
    n_test = max(1, int(round(0.10 * n)))
    n_valid = max(1, int(round(0.10 * n)))
    return {
        "test": np.sort(order[:n_test]),
        "valid": np.sort(order[n_test : n_test + n_valid]),
        "train": np.sort(order[n_test + n_valid :]),
    }


def make_split(frame: pd.DataFrame, x: np.ndarray, split: str, seed: int) -> dict[str, np.ndarray]:
    if split == "random":
        s = random_split(frame, seed)
        return {"train": s.train, "valid": s.valid, "test": s.test}
    if split == "scaffold":
        s = scaffold_split(frame, seed)
        return {"train": s.train, "valid": s.valid, "test": s.test}
    if split == "perimeter":
        return perimeter_split(x, seed)
    raise ValueError(split)


def predict_prob(model, x: np.ndarray) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        return model.predict_proba(x)[:, 1]
    if hasattr(model[-1], "predict_proba"):
        return model.predict_proba(x)[:, 1]
    raw = model.decision_function(x)
    return 1 / (1 + np.exp(-np.clip(raw, -60, 60)))


def recall_at_fixed_precision(y: np.ndarray, scores: np.ndarray, min_precision: float) -> float:
    precision, recall, _ = precision_recall_curve(y, scores)
    mask = precision >= min_precision
    return float(np.nanmax(recall[mask])) if np.any(mask) else 0.0


def metrics(y: np.ndarray, scores: np.ndarray) -> dict[str, float]:
    scores = np.clip(np.asarray(scores, dtype=float), 1e-7, 1 - 1e-7)
    y = np.asarray(y, dtype=int)
    pred = (scores >= 0.5).astype(int)
    if len(np.unique(y)) < 2:
        return {k: np.nan for k in ["roc_auc", "pr_auc", "brier", "balanced_accuracy", "f1", "mcc", "recall_at_p80", "recall_at_p90"]}
    return {
        "roc_auc": float(roc_auc_score(y, scores)),
        "pr_auc": float(average_precision_score(y, scores)),
        "brier": float(brier_score_loss(y, scores)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "mcc": float(matthews_corrcoef(y, pred)),
        "recall_at_p80": recall_at_fixed_precision(y, scores, 0.80),
        "recall_at_p90": recall_at_fixed_precision(y, scores, 0.90),
    }


def nearest_tanimoto(test_fps, reference_fps) -> np.ndarray:
    vals = []
    for fp in test_fps:
        sims = DataStructs.BulkTanimotoSimilarity(fp, reference_fps)
        vals.append(max(sims) if sims else np.nan)
    return np.asarray(vals, dtype=float)


def tanimoto_bin(v: float) -> str:
    if v > 0.7:
        return ">0.7"
    if v >= 0.5:
        return "0.5-0.7"
    return "<0.5"


def risk_enrichment(y: np.ndarray, scores: np.ndarray, risk: np.ndarray, top_frac: float = 0.10) -> float:
    pred = (scores >= 0.5).astype(int)
    errors = pred != y
    if errors.mean() == 0 or len(errors) < 5:
        return np.nan
    k = max(1, int(np.ceil(len(errors) * top_frac)))
    top = np.argsort(-risk)[:k]
    return float(errors[top].mean() / errors.mean())


def run_dataset(dataset: str, seeds: list[int], splits: list[str]) -> tuple[list[dict], list[dict], list[pd.DataFrame]]:
    frame = pd.read_csv(ROOT / "data" / "bro5" / f"{dataset}.csv")
    x = feature_matrix(frame["smiles"])
    fps = bitvectors(frame["smiles"])
    y = frame["y"].to_numpy(int)
    candidate_rows = []
    selected_rows = []
    details = []
    for split_name in splits:
        for seed in seeds:
            print(f"run dataset={dataset} split={split_name} seed={seed}", flush=True)
            idx = make_split(frame, x, split_name, seed)
            model_dict = models(seed)
            pred_by_model: dict[str, np.ndarray] = {}
            for model_name, template in model_dict.items():
                model = clone(template)
                model.fit(x[idx["train"]], y[idx["train"]])
                valid_score = predict_prob(model, x[idx["valid"]])
                test_score = predict_prob(model, x[idx["test"]])
                pred_by_model[model_name] = test_score
                row = {
                    "dataset": dataset,
                    "split": split_name,
                    "seed": seed,
                    "model": model_name,
                    "n_train": len(idx["train"]),
                    "n_valid": len(idx["valid"]),
                    "n_test": len(idx["test"]),
                    "positive_rate_train": float(y[idx["train"]].mean()),
                    "positive_rate_valid": float(y[idx["valid"]].mean()),
                    "positive_rate_test": float(y[idx["test"]].mean()),
                }
                row.update({f"valid_{k}": v for k, v in metrics(y[idx["valid"]], valid_score).items()})
                row.update({f"test_{k}": v for k, v in metrics(y[idx["test"]], test_score).items()})
                candidate_rows.append(row)
            candidates = pd.DataFrame([r for r in candidate_rows if r["dataset"] == dataset and r["split"] == split_name and r["seed"] == seed])
            selected = candidates.sort_values("valid_roc_auc", ascending=False).iloc[0].to_dict()
            selected_name = selected["model"]
            reference_fps = [fps[i] for i in np.concatenate([idx["train"], idx["valid"]])]
            test_fps = [fps[i] for i in idx["test"]]
            max_sim = nearest_tanimoto(test_fps, reference_fps)
            all_scores = np.vstack([pred_by_model[k] for k in sorted(pred_by_model)])
            uncertainty = all_scores.std(axis=0)
            selected_score = pred_by_model[selected_name]
            risk = uncertainty + (1 - np.nan_to_num(max_sim, nan=0))
            selected["mean_test_nn_tanimoto"] = float(np.nanmean(max_sim))
            selected["error_enrichment_top10_risk"] = risk_enrichment(y[idx["test"]], selected_score, risk)
            selected_rows.append(selected)
            details.append(
                pd.DataFrame(
                    {
                        "dataset": dataset,
                        "split": split_name,
                        "seed": seed,
                        "selected_model": selected_name,
                        "smiles": frame.iloc[idx["test"]]["smiles"].to_numpy(),
                        "y_true": y[idx["test"]],
                        "y_score": selected_score,
                        "max_train_valid_tanimoto": max_sim,
                        "tanimoto_bin": [tanimoto_bin(v) for v in max_sim],
                        "ensemble_std": uncertainty,
                        "risk_score": risk,
                    }
                )
            )
    return candidate_rows, selected_rows, details


def summarize_bins(detail: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for keys, g in detail.groupby(["dataset", "split", "seed", "tanimoto_bin"], dropna=False):
        dataset, split, seed, bin_name = keys
        m = metrics(g["y_true"].to_numpy(), g["y_score"].to_numpy())
        rows.append(
            {
                "dataset": dataset,
                "split": split,
                "seed": seed,
                "tanimoto_bin": bin_name,
                "n": len(g),
                "positive_rate": float(g["y_true"].mean()) if len(g) else np.nan,
                "mean_nn_tanimoto": float(g["max_train_valid_tanimoto"].mean()),
                "mean_ensemble_std": float(g["ensemble_std"].mean()),
                **m,
            }
        )
    return pd.DataFrame(rows)


def plot_summary(selected: pd.DataFrame) -> None:
    agg = selected.groupby(["dataset", "split"], dropna=False)["test_roc_auc"].agg(["mean", "std"]).reset_index()
    fig, ax = plt.subplots(figsize=(7.2, 4.1))
    labels = [f"{r.dataset}\n{r.split}" for r in agg.itertuples(index=False)]
    ax.bar(np.arange(len(agg)), agg["mean"], yerr=agg["std"], color="#0f766e", edgecolor="white", linewidth=0.7)
    ax.set_xticks(np.arange(len(agg)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("Test ROC-AUC")
    ax.set_title("LinPept bRo5 validation-selected baselines", loc="left", fontweight="bold")
    ax.grid(axis="y", color="#e5e7eb", linewidth=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(FIG / "linpept_selected_roc_auc.png", dpi=320, bbox_inches="tight")
    fig.savefig(FIG / "linpept_selected_roc_auc.svg", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    status = standardize_data()
    candidate_rows = []
    selected_rows = []
    details = []
    for dataset in DATASETS:
        if not (ROOT / "data" / "bro5" / f"{dataset}.csv").exists():
            continue
        rows, selected, detail = run_dataset(dataset, seeds=[13, 17, 23], splits=["random", "scaffold", "perimeter"])
        candidate_rows.extend(rows)
        selected_rows.extend(selected)
        details.extend(detail)
    candidates = pd.DataFrame(candidate_rows)
    selected = pd.DataFrame(selected_rows)
    detail = pd.concat(details, ignore_index=True) if details else pd.DataFrame()
    bins = summarize_bins(detail) if not detail.empty else pd.DataFrame()
    candidates.to_csv(OUT / "candidate_metrics_raw.csv", index=False)
    selected.to_csv(OUT / "validation_selected_results.csv", index=False)
    detail.to_csv(OUT / "test_predictions_with_ad.csv", index=False)
    bins.to_csv(OUT / "tanimoto_bins_summary.csv", index=False)
    plot_summary(selected)
    manifest = {
        "source": "DonghaiZHAO-ZJU/Benchmark-ADMET-2025 data/origin_data",
        "datasets": list(DATASETS),
        "splits": ["random", "scaffold", "perimeter"],
        "seeds": [13, 17, 23],
        "selection_rule": "highest validation ROC-AUC per dataset/split/seed",
    }
    (OUT / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (OUT / "README.md").write_text(
        "# LinPept bRo5 benchmark\n\n"
        "LinPept CellPen and LinPept NonFouling were downloaded from the public Benchmark-ADMET-2025 repository. "
        "Models are selected by validation ROC-AUC and evaluated once on the frozen test split.\n",
        encoding="utf-8",
    )
    status.to_csv(OUT / "linpept_data_status.csv", index=False)
    print(f"Wrote LinPept outputs to {OUT}", flush=True)
    print(selected[["dataset", "split", "seed", "model", "test_roc_auc", "test_pr_auc", "recall_at_p80" if "recall_at_p80" in selected.columns else "test_recall_at_p80"]].head().to_string(index=False))


if __name__ == "__main__":
    main()
