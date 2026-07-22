from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "小论文-12_严格补实验"


def error_overlap(preds: pd.DataFrame, prefix: str) -> dict[str, object]:
    rows = []
    for unit, group in preds.groupby(["task", "task_type", "seed", "outer_fold"], sort=True):
        task, task_type, seed, outer_fold = unit
        if task_type == "classification":
            group = group.assign(error_flag=(group["y_pred"] >= 0.5).astype(int) != group["y_true"].astype(int))
        else:
            abs_err = (group["y_pred"] - group["y_true"]).abs()
            group = group.assign(error_flag=abs_err >= float(abs_err.quantile(0.75)))
        pivot = group.pivot_table(index="sample_index", columns="candidate", values="error_flag", aggfunc="max")
        pivot = pivot.dropna(axis=1, how="any").astype(bool)
        candidates = list(pivot.columns)
        for i, a in enumerate(candidates):
            for b in candidates[i + 1 :]:
                aa = pivot[a].to_numpy(bool)
                bb = pivot[b].to_numpy(bool)
                union = int(np.logical_or(aa, bb).sum())
                inter = int(np.logical_and(aa, bb).sum())
                rows.append(
                    {
                        "task": task,
                        "task_type": task_type,
                        "seed": int(seed),
                        "outer_fold": int(outer_fold),
                        "candidate_a": a,
                        "candidate_b": b,
                        "n_samples": int(len(pivot)),
                        "errors_a": int(aa.sum()),
                        "errors_b": int(bb.sum()),
                        "error_intersection": inter,
                        "error_union": union,
                        "jaccard_error_overlap": float(inter / union) if union else np.nan,
                    }
                )
    detail = pd.DataFrame(rows)
    detail.to_csv(OUT / f"{prefix}_error_overlap_pairwise_detail.csv", index=False)
    summary = (
        detail.groupby(["candidate_a", "candidate_b"], dropna=False)
        .agg(
            n_units=("jaccard_error_overlap", "size"),
            mean_jaccard_error_overlap=("jaccard_error_overlap", "mean"),
            median_jaccard_error_overlap=("jaccard_error_overlap", "median"),
        )
        .reset_index()
    )
    summary.to_csv(OUT / f"{prefix}_error_overlap_pairwise_summary.csv", index=False)
    return {
        f"{prefix}_error_overlap_rows": int(len(detail)),
        f"{prefix}_error_overlap_pairs": int(len(summary)),
        f"{prefix}_error_overlap_mean": float(detail["jaccard_error_overlap"].mean()) if len(detail) else None,
    }


def main() -> None:
    strong = pd.read_csv(OUT / "strong_baseline_outer_predictions.csv")
    chemprop_path = OUT / "chemprop_outer_predictions.csv"
    if chemprop_path.exists():
        chem = pd.read_csv(chemprop_path)
        common = ["task", "task_type", "seed", "outer_fold", "sample_index", "smiles", "y_true", "candidate", "family", "y_pred"]
        combined = pd.concat([strong[common], chem[common]], ignore_index=True)
    else:
        combined = strong
    combined.to_csv(OUT / "combined_strong_baseline_outer_predictions.csv", index=False)
    audit = {
        "combined_prediction_rows": int(len(combined)),
        "combined_candidates": sorted(combined["candidate"].dropna().unique().tolist()),
    }
    audit.update(error_overlap(combined, "combined_strong"))

    outer = pd.read_csv(OUT / "strong_baseline_outer_scores.csv")
    if (OUT / "chemprop_outer_scores.csv").exists():
        chem_scores = pd.read_csv(OUT / "chemprop_outer_scores.csv")
        cols = sorted(set(outer.columns).union(chem_scores.columns))
        for frame in (outer, chem_scores):
            for col in cols:
                if col not in frame.columns:
                    frame[col] = np.nan
        combined_scores = pd.concat([outer[cols], chem_scores[cols]], ignore_index=True)
    else:
        combined_scores = outer
    combined_scores.to_csv(OUT / "combined_strong_baseline_outer_scores.csv", index=False)
    summary = (
        combined_scores.groupby(["candidate", "family", "task_type"], dropna=False)
        .agg(
            n_outer_units=("outer_utility", "size"),
            n_tasks=("task", "nunique"),
            outer_utility_mean=("outer_utility", "mean"),
            roc_auc_mean=("roc_auc", "mean"),
            pr_auc_mean=("pr_auc", "mean"),
            rmse_mean=("rmse", "mean"),
        )
        .reset_index()
    )
    summary.to_csv(OUT / "combined_strong_baseline_summary.csv", index=False)
    audit["combined_score_rows"] = int(len(combined_scores))
    audit["combined_summary_rows"] = int(len(summary))
    audit["passed"] = audit["combined_prediction_rows"] > 0 and audit["combined_strong_error_overlap_rows"] > 0
    (OUT / "paper12_combined_gap_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUT / "paper12_combined_gap_audit.json")


if __name__ == "__main__":
    main()
