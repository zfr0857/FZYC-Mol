from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata
from sklearn.covariance import LedoitWolf


ROOT = Path(r"D:\fzyc")
PKG = ROOT / "output" / "paper43_jcheminform_completion_20260726"
RUNS = PKG / "working_additional4_r3_20260726" / "paper43_completion" / "run_records"
OUTS = [PKG / "source_data", PKG / "additional_files" / "tables",
        PKG / "working_additional4_r3_20260726" / "paper43_completion" / "source_data"]
SEEDS = [11, 23, 37, 53, 71, 83, 97, 113, 127, 149]
FIRST = SEEDS[:5]
LATER = SEEDS[5:]
KS = [4, 8, 16, 32]
TRANSFORMS = ["raw", "row_centred", "fixed_reference_relative", "within_unit_rank"]
REFERENCES = {
    "candidate_1": 1,
    "predefined_linear_baseline": 2,
    "fixed_morgan_rf": 5,
    "registry_median_candidate": 16,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_level(name: str) -> tuple[pd.DataFrame, list[dict]]:
    frames, files = [], []
    for seed in SEEDS:
        if seed in FIRST:
            groups = ["classification_metric_rerun", "regression_split_manifest_rerun"]
        else:
            groups = ["additional_seeds"]
        for group in groups:
            path = RUNS / group / f"seed_{seed}" / name
            frame = pd.read_csv(path)
            frame.insert(0, "seed", seed)
            frames.append(frame)
            files.append({"path": path.relative_to(PKG).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)})
    data = pd.concat(frames, ignore_index=True).rename(columns={"dataset": "task"})
    return data, files


def corr_from_cov(cov: np.ndarray) -> np.ndarray:
    scale = np.sqrt(np.clip(np.diag(cov), 1e-15, None))
    corr = np.clip(cov / np.outer(scale, scale), -1.0, 1.0)
    np.fill_diagonal(corr, 1.0)
    return corr


def metrics(x: np.ndarray) -> dict[str, float]:
    x = np.asarray(x, dtype=float)
    keep = np.nanstd(x, axis=0) > 1e-12
    x = x[:, keep]
    if x.shape[1] <= 1:
        return {"empirical_entropy_rank": 1.0, "empirical_participation_rank": 1.0,
                "empirical_median_correlation": 1.0, "ledoit_wolf_entropy_rank": 1.0,
                "ledoit_wolf_participation_rank": 1.0, "ledoit_wolf_median_correlation": 1.0,
                "ledoit_wolf_shrinkage_alpha": 1.0}

    def summarize(corr: np.ndarray, prefix: str) -> dict[str, float]:
        eig = np.clip(np.linalg.eigvalsh(corr), 0.0, None)
        total = float(eig.sum())
        p = eig / total if total > 0 else np.ones_like(eig) / len(eig)
        positive = p[p > 1e-15]
        off = corr[np.triu_indices_from(corr, 1)]
        return {
            f"{prefix}_entropy_rank": float(np.exp(-(positive * np.log(positive)).sum())),
            f"{prefix}_participation_rank": float(total * total / np.square(eig).sum()),
            f"{prefix}_median_correlation": float(np.median(off)) if len(off) else 1.0,
        }

    empirical = np.nan_to_num(np.corrcoef(x, rowvar=False), nan=0.0)
    np.fill_diagonal(empirical, 1.0)
    sd = x.std(axis=0, ddof=1)
    z = (x - x.mean(axis=0)) / np.where(sd > 1e-12, sd, 1.0)
    estimator = LedoitWolf().fit(z)
    out = summarize(empirical, "empirical")
    out.update(summarize(corr_from_cov(estimator.covariance_), "ledoit_wolf"))
    out["ledoit_wolf_shrinkage_alpha"] = float(estimator.shrinkage_)
    return out


def transform(x: np.ndarray, mode: str, reference_index: int = 0) -> np.ndarray:
    if mode == "raw":
        return x
    if mode == "row_centred":
        return x - x.mean(axis=1, keepdims=True)
    if mode == "within_unit_rank":
        return np.apply_along_axis(rankdata, 1, x)
    if mode == "fixed_reference_relative":
        keep = [j for j in range(x.shape[1]) if j != reference_index]
        return x[:, keep] - x[:, [reference_index]]
    raise ValueError(mode)


def matrix_for(frame: pd.DataFrame, task: str, k: int, level: str) -> pd.DataFrame:
    index = ["seed", "outer_fold"] + (["inner_fold"] if level == "inner" else [])
    value = "inner_utility" if level == "inner" else "outer_utility"
    return frame.loc[frame.task.eq(task) & frame.candidate_order.le(k)].pivot_table(
        index=index, columns="candidate_order", values=value
    ).reset_index()


def main() -> None:
    outer, outer_files = load_level("outer_candidate_scores.csv")
    inner, inner_files = load_level("inner_scores.csv")
    units, omissions, references, coverage = [], [], [], []

    tasks = sorted(outer.task.unique())
    for task in tasks:
        task_type = str(outer.loc[outer.task.eq(task), "task_type"].iloc[0])
        outer32 = matrix_for(outer, task, 32, "outer")
        inner32 = matrix_for(inner, task, 32, "inner")
        coverage.append({
            "task": task, "task_type": task_type,
            "n_seeds": outer32.seed.nunique(), "seed_values": ";".join(map(str, sorted(outer32.seed.unique()))),
            "outer_rows": len(outer32), "outer_expected": 30,
            "inner_rows": len(inner32), "inner_expected": 90,
            "outer_candidate_columns": outer32.shape[1] - 2,
            "inner_candidate_columns": inner32.shape[1] - 3,
            "status": "PASS" if len(outer32) == 30 and len(inner32) == 90 and outer32.seed.nunique() == 10 else "FAIL",
        })
        for level, frame in [("outer", outer), ("inner", inner)]:
            id_cols = ["seed", "outer_fold"] + (["inner_fold"] if level == "inner" else [])
            for k in KS:
                matrix = matrix_for(frame, task, k, level)
                orders = list(matrix.drop(columns=id_cols).columns.astype(int))
                raw = matrix.drop(columns=id_cols).to_numpy(float)
                for mode in TRANSFORMS:
                    x = transform(raw, mode)
                    units.append({
                        "task": task, "task_type": task_type, "matrix_level": level,
                        "candidate_count": k, "transformation": mode, "reference_label": "candidate_1",
                        "n_seeds": matrix.seed.nunique(), "n_matrix_rows": len(matrix),
                        "n_columns_after_transform": x.shape[1], **metrics(x),
                    })
                if k != 32:
                    continue
                for mode in TRANSFORMS:
                    omit_specs = [("seed", sorted(matrix.seed.unique()), "seed"),
                                  ("outer_fold", sorted(matrix.outer_fold.unique()), "outer_fold")]
                    if level == "inner":
                        omit_specs.append(("inner_fold", sorted(matrix.inner_fold.unique()), "inner_fold"))
                    for omission_type, values, column in omit_specs:
                        for omitted in values:
                            sub = matrix.loc[~matrix[column].eq(omitted)].drop(columns=id_cols).to_numpy(float)
                            omissions.append({
                                "task": task, "task_type": task_type, "matrix_level": level,
                                "transformation": mode, "omission_type": omission_type,
                                "omitted": omitted, "n_matrix_rows": len(sub), **metrics(transform(sub, mode)),
                            })
                for label, order in REFERENCES.items():
                    ref_index = orders.index(order)
                    x = transform(raw, "fixed_reference_relative", ref_index)
                    references.append({
                        "task": task, "task_type": task_type, "matrix_level": level,
                        "candidate_count": 32, "transformation": "fixed_reference_relative",
                        "reference_label": label, "reference_candidate_order": order,
                        "n_seeds": matrix.seed.nunique(), "n_matrix_rows": len(matrix),
                        "n_columns_after_transform": x.shape[1], **metrics(x),
                    })

    units = pd.DataFrame(units)
    summaries = []
    for keys, group in units.groupby(["matrix_level", "candidate_count", "transformation"]):
        row = dict(zip(["matrix_level", "candidate_count", "transformation"], keys))
        row["n_endpoints"] = len(group)
        for metric in ["ledoit_wolf_entropy_rank", "ledoit_wolf_participation_rank", "ledoit_wolf_median_correlation"]:
            values = group[metric].to_numpy(float)
            row[f"{metric}_median"] = float(np.median(values))
            row[f"{metric}_q25"] = float(np.quantile(values, .25))
            row[f"{metric}_q75"] = float(np.quantile(values, .75))
            row[f"{metric}_min"] = float(np.min(values))
            row[f"{metric}_max"] = float(np.max(values))
        summaries.append(row)
    summary = pd.DataFrame(summaries)
    omissions = pd.DataFrame(omissions)
    references = pd.DataFrame(references)
    coverage = pd.DataFrame(coverage)

    files = {
        "effective_diversity_10seed_units.csv": units,
        "effective_diversity_10seed_summary.csv": summary,
        "effective_diversity_10seed_leave_one_out.csv": omissions,
        "effective_diversity_10seed_reference_sensitivity.csv": references,
        "effective_diversity_seed_audit.csv": coverage,
    }
    for out in OUTS:
        out.mkdir(parents=True, exist_ok=True)
        for name, frame in files.items():
            frame.to_csv(out / name, index=False)

    manifest = {
        "analysis": "ten-seed primary effective-diversity reconstruction",
        "seeds": SEEDS,
        "outer_matrix_rows_per_endpoint": 30,
        "inner_matrix_rows_per_endpoint": 90,
        "candidate_counts": KS,
        "transformations": TRANSFORMS,
        "input_files": outer_files + inner_files,
        "output_hashes": {name: sha256(OUTS[0] / name) for name in files},
        "no_new_model_fits": True,
    }
    for out in OUTS:
        (out / "effective_diversity_10seed_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    if not coverage.status.eq("PASS").all():
        raise RuntimeError("Ten-seed effective-diversity coverage failed")
    print(coverage.to_string(index=False))


if __name__ == "__main__":
    main()
