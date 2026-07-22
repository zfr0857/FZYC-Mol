from __future__ import annotations

import json
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
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.features import descriptor_vector, morgan_fingerprint, scaffold_from_smiles
from fzyc_mol.splits import scaffold_split, random_split


RDLogger.DisableLog("rdApp.*")

DATA = ROOT / "data" / "bro5" / "cycpeptmp_peptide_used.csv"
OUT = ROOT / "reports" / "bro5_cycpept_pampa_20260611"
FIG = OUT / "figures"
OUT.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)


def load_optional_models(seed: int, n_estimators: int) -> dict[str, object]:
    models: dict[str, object] = {
        "ridge_morgan_desc": Pipeline(
            [
                ("scale", StandardScaler(with_mean=False)),
                ("ridge", RidgeCV(alphas=np.logspace(-4, 4, 17))),
            ]
        ),
        "rf_morgan_desc": RandomForestRegressor(
            n_estimators=n_estimators,
            max_features="sqrt",
            min_samples_leaf=1,
            random_state=seed,
            n_jobs=-1,
        ),
        "extratrees_morgan_desc": ExtraTreesRegressor(
            n_estimators=n_estimators,
            max_features="sqrt",
            min_samples_leaf=1,
            random_state=seed,
            n_jobs=-1,
        ),
    }
    try:
        from lightgbm import LGBMRegressor

        models["lgbm_morgan_desc"] = LGBMRegressor(
            n_estimators=n_estimators,
            learning_rate=0.035,
            num_leaves=31,
            subsample=0.85,
            colsample_bytree=0.75,
            reg_lambda=2.0,
            random_state=seed,
            n_jobs=4,
            verbose=-1,
        )
    except Exception:
        pass
    try:
        from xgboost import XGBRegressor

        models["xgb_morgan_desc"] = XGBRegressor(
            n_estimators=n_estimators,
            max_depth=4,
            learning_rate=0.035,
            subsample=0.85,
            colsample_bytree=0.75,
            reg_lambda=2.0,
            objective="reg:squarederror",
            random_state=seed,
            n_jobs=4,
        )
    except Exception:
        pass
    return models


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    y_true = np.asarray(y_true, dtype=float).reshape(-1)
    y_pred = np.asarray(y_pred, dtype=float).reshape(-1)
    return {
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "r2": float(r2_score(y_true, y_pred)),
        "spearman": float(spearmanr(y_true, y_pred).statistic) if len(np.unique(y_true)) > 1 else np.nan,
    }


def load_frame() -> pd.DataFrame:
    if not DATA.exists():
        raise FileNotFoundError(f"Missing {DATA}. Download cycpeptmp desc/peptide_used.csv first.")
    df = pd.read_csv(DATA)
    frame = df[["SMILES", "y", "PAMPA", "Set", "ID", "Year"]].rename(columns={"SMILES": "smiles"})
    frame["y"] = pd.to_numeric(frame["y"], errors="coerce")
    frame = frame.dropna(subset=["smiles", "y"]).drop_duplicates("smiles").reset_index(drop=True)
    valid = []
    for smi in frame["smiles"].astype(str):
        valid.append(Chem.MolFromSmiles(smi) is not None)
    frame = frame.loc[valid].reset_index(drop=True)
    frame[["smiles", "y"]].to_csv(ROOT / "data" / "bro5" / "cycpept_pampa.csv", index=False)
    return frame


def feature_matrix(smiles: pd.Series) -> np.ndarray:
    rows = []
    for smi in smiles.astype(str):
        rows.append(np.hstack([morgan_fingerprint(smi, n_bits=2048, radius=2), descriptor_vector(smi, include_3d=False)]))
    return np.nan_to_num(np.vstack(rows).astype(np.float32), copy=False)


def bitvectors(smiles: pd.Series):
    out = []
    for smi in smiles.astype(str):
        mol = Chem.MolFromSmiles(smi)
        out.append(AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=2048))
    return out


def perimeter_split_from_features(x: np.ndarray, seed: int) -> dict[str, np.ndarray]:
    pca = PCA(n_components=2, random_state=seed)
    score = pca.fit_transform(x)
    dist = np.linalg.norm(score - score.mean(axis=0, keepdims=True), axis=1)
    order = np.argsort(-dist)
    n = len(order)
    n_test = max(1, int(round(0.10 * n)))
    n_valid = max(1, int(round(0.10 * n)))
    test = np.sort(order[:n_test])
    valid = np.sort(order[n_test : n_test + n_valid])
    train = np.sort(order[n_test + n_valid :])
    return {"train": train, "valid": valid, "test": test}


def make_splits(frame: pd.DataFrame, x: np.ndarray, split: str, seed: int) -> dict[str, np.ndarray]:
    if split == "random":
        s = random_split(frame.rename(columns={"SMILES": "smiles"}), seed)
        return {"train": s.train, "valid": s.valid, "test": s.test}
    if split == "scaffold":
        s = scaffold_split(frame.rename(columns={"SMILES": "smiles"}), seed)
        return {"train": s.train, "valid": s.valid, "test": s.test}
    if split == "perimeter":
        return perimeter_split_from_features(x, seed)
    if split == "time":
        ordered = frame.assign(_row=np.arange(len(frame))).sort_values(["Year", "_row"], ascending=True)["_row"].to_numpy()
        n = len(ordered)
        n_train = int(round(0.80 * n))
        n_valid = int(round(0.10 * n))
        train = np.sort(ordered[:n_train])
        valid = np.sort(ordered[n_train : n_train + n_valid])
        test = np.sort(ordered[n_train + n_valid :])
        return {"train": train, "valid": valid, "test": test}
    raise ValueError(split)


def nearest_tanimoto(test_fps, reference_fps) -> np.ndarray:
    values = []
    for fp in test_fps:
        sims = DataStructs.BulkTanimotoSimilarity(fp, reference_fps)
        values.append(max(sims) if sims else np.nan)
    return np.asarray(values, dtype=float)


def tanimoto_bin(value: float) -> str:
    if value > 0.7:
        return ">0.7"
    if value >= 0.5:
        return "0.5-0.7"
    return "<0.5"


def high_error_enrichment(abs_error: np.ndarray, risk: np.ndarray, top_frac: float = 0.10) -> float:
    if len(abs_error) < 5:
        return np.nan
    error_cut = np.quantile(abs_error, 0.80)
    high_error = abs_error >= error_cut
    k = max(1, int(np.ceil(len(risk) * top_frac)))
    top = np.argsort(-risk)[:k]
    base = float(high_error.mean())
    return float(high_error[top].mean() / base) if base > 0 else np.nan


def evaluate_split(frame: pd.DataFrame, x: np.ndarray, fps: list, split: str, seed: int, n_estimators: int) -> tuple[list[dict], dict, pd.DataFrame]:
    idx = make_splits(frame, x, split, seed)
    y = frame["y"].to_numpy(dtype=float)
    models = load_optional_models(seed, n_estimators)
    rows = []
    predictions = {}
    for name, template in models.items():
        model = clone(template)
        model.fit(x[idx["train"]], y[idx["train"]])
        valid_pred = model.predict(x[idx["valid"]])
        test_pred = model.predict(x[idx["test"]])
        valid = regression_metrics(y[idx["valid"]], valid_pred)
        test = regression_metrics(y[idx["test"]], test_pred)
        row = {
            "dataset": "cycpept_pampa",
            "source": "CycPeptMPDB/CycPeptMP",
            "split": split,
            "seed": seed,
            "model": name,
            "n_train": len(idx["train"]),
            "n_valid": len(idx["valid"]),
            "n_test": len(idx["test"]),
        }
        row.update({f"valid_{k}": v for k, v in valid.items()})
        row.update({f"test_{k}": v for k, v in test.items()})
        rows.append(row)
        predictions[name] = test_pred

    candidate = pd.DataFrame(rows)
    selected = candidate.sort_values("valid_rmse", ascending=True).iloc[0].to_dict()
    selected_name = str(selected["model"])
    reference_fps = [fps[i] for i in np.concatenate([idx["train"], idx["valid"]])]
    test_fps = [fps[i] for i in idx["test"]]
    max_sim = nearest_tanimoto(test_fps, reference_fps)
    selected_pred = predictions[selected_name]
    all_pred = np.vstack([predictions[name] for name in sorted(predictions)])
    uncertainty = all_pred.std(axis=0)
    abs_error = np.abs(y[idx["test"]] - selected_pred)
    detail = pd.DataFrame(
        {
            "dataset": "cycpept_pampa",
            "split": split,
            "seed": seed,
            "selected_model": selected_name,
            "smiles": frame.iloc[idx["test"]]["smiles"].to_numpy(),
            "y_true": y[idx["test"]],
            "y_pred": selected_pred,
            "abs_error": abs_error,
            "max_train_valid_tanimoto": max_sim,
            "tanimoto_bin": [tanimoto_bin(v) for v in max_sim],
            "ensemble_std": uncertainty,
            "risk_score": uncertainty + (1.0 - np.nan_to_num(max_sim, nan=0.0)),
        }
    )
    selected["test_high_error_enrichment_top10_risk"] = high_error_enrichment(detail["abs_error"].to_numpy(), detail["risk_score"].to_numpy())
    selected["mean_test_nn_tanimoto"] = float(np.nanmean(max_sim))
    return rows, selected, detail


def summarize_bins(detail: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (split, seed, bin_name), group in detail.groupby(["split", "seed", "tanimoto_bin"], dropna=False):
        m = regression_metrics(group["y_true"].to_numpy(), group["y_pred"].to_numpy()) if len(group) >= 2 else {}
        rows.append(
            {
                "dataset": "cycpept_pampa",
                "split": split,
                "seed": seed,
                "tanimoto_bin": bin_name,
                "n": len(group),
                "mean_nn_tanimoto": group["max_train_valid_tanimoto"].mean(),
                "mean_ensemble_std": group["ensemble_std"].mean(),
                "mean_abs_error": group["abs_error"].mean(),
                **m,
            }
        )
    return pd.DataFrame(rows)


def plot_selected(summary: pd.DataFrame) -> None:
    plot = summary.copy()
    labels = [f"{r.split}\nseed {r.seed}\n{r.model}" for r in plot.itertuples(index=False)]
    values = plot["test_rmse"].to_numpy(float)
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    ax.bar(np.arange(len(values)), values, color="#2563eb", edgecolor="white", linewidth=0.7)
    ax.set_xticks(np.arange(len(values)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("Test RMSE")
    ax.set_title("CycPept-PAMPA bRo5 validation-selected baselines", loc="left", fontweight="bold")
    ax.grid(axis="y", color="#e5e7eb", linewidth=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(FIG / "cycpept_pampa_selected_rmse.png", dpi=320, bbox_inches="tight")
    fig.savefig(FIG / "cycpept_pampa_selected_rmse.svg", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    frame = load_frame()
    x = feature_matrix(frame["smiles"])
    fps = bitvectors(frame["smiles"])
    seeds = [13, 17, 23]
    splits = ["random", "scaffold", "perimeter", "time"]
    candidate_rows: list[dict] = []
    selected_rows: list[dict] = []
    detail_frames: list[pd.DataFrame] = []
    for split in splits:
        for seed in seeds:
            print(f"run dataset=cycpept_pampa split={split} seed={seed}", flush=True)
            rows, selected, detail = evaluate_split(frame, x, fps, split, seed, n_estimators=120)
            candidate_rows.extend(rows)
            selected_rows.append(selected)
            detail_frames.append(detail)

    candidates = pd.DataFrame(candidate_rows)
    selected = pd.DataFrame(selected_rows)
    detail = pd.concat(detail_frames, ignore_index=True)
    bins = summarize_bins(detail)

    data_status = pd.DataFrame(
        [
            {
                "dataset": "cycpept_pampa",
                "status": "available_and_run",
                "n": len(frame),
                "source": "akiyamalab/cycpeptmp desc/peptide_used.csv; derived from CycPeptMPDB",
                "local_path": str(DATA),
                "standardized_path": str(ROOT / "data" / "bro5" / "cycpept_pampa.csv"),
            },
            {
                "dataset": "linpept_nonfouling",
                "status": "missing_data",
                "n": 0,
                "source": "",
                "local_path": "",
                "standardized_path": "",
            },
            {
                "dataset": "linpept_cellpen",
                "status": "missing_data",
                "n": 0,
                "source": "",
                "local_path": "",
                "standardized_path": "",
            },
        ]
    )

    candidates.to_csv(OUT / "candidate_metrics_raw.csv", index=False)
    selected.to_csv(OUT / "validation_selected_results.csv", index=False)
    detail.to_csv(OUT / "test_predictions_with_ad.csv", index=False)
    bins.to_csv(OUT / "tanimoto_bins_summary.csv", index=False)
    data_status.to_csv(OUT / "bro5_data_status.csv", index=False)
    plot_selected(selected)
    readme = {
        "dataset": "cycpept_pampa",
        "n": len(frame),
        "splits": splits,
        "seeds": seeds,
        "models": sorted(candidates["model"].unique().tolist()),
        "selection_rule": "lowest validation RMSE per split/seed; test labels used once after selection",
        "outputs": [
            "candidate_metrics_raw.csv",
            "validation_selected_results.csv",
            "test_predictions_with_ad.csv",
            "tanimoto_bins_summary.csv",
            "bro5_data_status.csv",
        ],
    }
    (OUT / "run_manifest.json").write_text(json.dumps(readme, indent=2), encoding="utf-8")
    (OUT / "README.md").write_text(
        "# CycPept-PAMPA bRo5 benchmark\n\n"
        "This run converts the public CycPeptMP/CycPeptMPDB PAMPA subset into a validation-gated bRo5 stress test. "
        "Only CycPept-PAMPA is marked as run; LinPept-NonFouling and LinPept-CellPen remain missing_data until matching public CSV/TSV files with SMILES and labels are provided.\n\n"
        "Selection rule: the best candidate is selected by validation RMSE within each split and seed. Test labels are evaluated once after this choice is fixed.\n",
        encoding="utf-8",
    )
    print(f"Wrote bRo5 CycPept-PAMPA outputs to {OUT}", flush=True)


if __name__ == "__main__":
    main()
