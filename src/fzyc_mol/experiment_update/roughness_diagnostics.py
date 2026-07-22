from __future__ import annotations

import numpy as np
import pandas as pd
from rdkit import DataStructs
from scipy.stats import spearmanr

from fzyc_mol.datasets import load_dataset
from fzyc_mol.features import morgan_fingerprint

from .io import ExperimentConfig, write_csv


def _bitvect(smiles: str):
    arr = morgan_fingerprint(smiles)
    bv = DataStructs.ExplicitBitVect(int(arr.shape[0]))
    for bit in np.flatnonzero(arr > 0):
        bv.SetBit(int(bit))
    return bv


def _roughness_for_frame(frame: pd.DataFrame, task_type: str) -> dict[str, float]:
    fps = [_bitvect(s) for s in frame["smiles"].tolist()]
    y = frame["y"].to_numpy(dtype=float)
    jumps = []
    similarities = []
    mixed = []
    for i in range(len(frame)):
        sims = np.asarray(DataStructs.BulkTanimotoSimilarity(fps[i], fps), dtype=float)
        sims[i] = -1.0
        j = int(np.argmax(sims))
        similarities.append(float(sims[j]))
        jumps.append(float(abs(y[i] - y[j])))
        if task_type == "classification":
            mixed.append(float(y[i] != y[j]))
    jumps_arr = np.asarray(jumps, dtype=float)
    sim_arr = np.asarray(similarities, dtype=float)
    denom = np.clip(1.0 - sim_arr, 1e-3, None)
    rogi_proxy = float(np.nanmean(jumps_arr / denom))
    sari_proxy = float(np.nanmean(jumps_arr[sim_arr >= 0.7])) if np.any(sim_arr >= 0.7) else float("nan")
    modi_proxy = float(np.nanmean(mixed)) if mixed else float("nan")
    return {
        "rogi_proxy": rogi_proxy,
        "modi_proxy": modi_proxy,
        "sari_proxy": sari_proxy,
        "mean_nearest_tanimoto": float(np.mean(sim_arr)),
        "mean_nearest_label_jump": float(np.mean(jumps_arr)),
        "low_similarity_fraction": float(np.mean(sim_arr < 0.5)),
    }


def run_roughness_diagnostics(config: ExperimentConfig, datasets: list[str] | None = None) -> pd.DataFrame:
    names = datasets or sorted(set(config.datasets("moleculenet") + config.datasets("tdc_admet")))
    rows = []
    missing = []
    for dataset in names:
        try:
            frame, spec = load_dataset(dataset, config.data_dir)
        except Exception as exc:
            missing.append({"module": "roughness_diagnostics", "dataset": dataset, "status": "missing_data", "reason": str(exc)})
            continue
        rows.append({"dataset": dataset, "task_type": spec.task_type, **_roughness_for_frame(frame, spec.task_type)})
    out = pd.DataFrame(rows)
    write_csv(out, config.reports_dir / "roughness_diagnostics.csv")
    if missing:
        write_csv(pd.DataFrame(missing), config.reports_dir / "missing_data_report.csv")
    return out


def correlate_roughness_with_selector(config: ExperimentConfig) -> pd.DataFrame:
    rough_path = config.reports_dir / "roughness_diagnostics.csv"
    audit_path = config.reports_dir / "selector_audit.csv"
    if not rough_path.exists() or not audit_path.exists():
        return pd.DataFrame()
    rough = pd.read_csv(rough_path)
    audit = pd.read_csv(audit_path)
    merged = audit.merge(rough, on=["dataset", "task_type"], how="left")
    rows = []
    for metric in ["regret", "optimism_gap", "test_rank"]:
        if metric not in merged.columns:
            continue
        for rough_metric in ["rogi_proxy", "modi_proxy", "sari_proxy", "low_similarity_fraction"]:
            valid = merged[[metric, rough_metric]].dropna()
            corr = spearmanr(valid[metric], valid[rough_metric]).statistic if len(valid) >= 4 else np.nan
            rows.append({"selector_metric": metric, "roughness_metric": rough_metric, "spearman": corr, "n": len(valid)})
    out = pd.DataFrame(rows)
    write_csv(out, config.reports_dir / "roughness_selector_risk_correlation.csv")
    return out
