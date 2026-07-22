from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "output" / "\u5c0f\u8bba\u6587-12_\u4e25\u683c\u8865\u5b9e\u9a8c"
AUDIT_PATH = EXP / "paper12_core_addon_audit.json"


def read_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(EXP / name)


def to_float(value: object) -> float | None:
    if pd.isna(value):
        return None
    return float(value)


def combine_inner_scores() -> pd.DataFrame:
    strong = read_csv("strong_baseline_inner_scores.csv")
    chem = read_csv("chemprop_inner_scores.csv")
    cols = sorted(set(strong.columns).union(chem.columns))
    frames = []
    for frame in (strong, chem):
        expanded = frame.copy()
        for col in cols:
            if col not in expanded.columns:
                expanded[col] = np.nan
        frames.append(expanded[cols])
    combined = pd.concat(frames, ignore_index=True)
    combined.to_csv(EXP / "combined_strong_baseline_inner_scores.csv", index=False)
    summary = (
        combined.groupby(["candidate", "family", "task_type"], dropna=False)
        .agg(
            n_inner_units=("inner_utility", "size"),
            n_tasks=("task", "nunique"),
            inner_utility_mean=("inner_utility", "mean"),
            inner_utility_sd=("inner_utility", "std"),
            roc_auc_mean=("roc_auc", "mean"),
            pr_auc_mean=("pr_auc", "mean"),
            rmse_mean=("rmse", "mean"),
        )
        .reset_index()
    )
    summary.to_csv(EXP / "combined_strong_baseline_inner_summary.csv", index=False)
    return combined


def combine_outer_scores_with_inner_means() -> pd.DataFrame:
    outer = read_csv("strong_baseline_outer_scores.csv")
    chem_outer = read_csv("chemprop_outer_scores.csv")
    chem_inner = read_csv("chemprop_inner_scores.csv")
    chem_inner_summary = (
        chem_inner.groupby(["task", "task_type", "seed", "outer_fold", "candidate", "family"], dropna=False)
        .agg(
            inner_mean=("inner_utility", "mean"),
            inner_sd=("inner_utility", "std"),
            n_inner_folds=("inner_fold", "nunique"),
            inner_fit_predict_seconds=("fit_predict_seconds", "sum"),
        )
        .reset_index()
    )
    chem_outer = chem_outer.merge(
        chem_inner_summary,
        on=["task", "task_type", "seed", "outer_fold", "candidate", "family"],
        how="left",
        validate="one_to_one",
    )
    chem_outer["candidate_order"] = 5
    chem_outer["validation_scheme"] = (
        "outer test predictions from same frozen outer folds; selection score from all three inner retrains"
    )

    cols = sorted(set(outer.columns).union(chem_outer.columns))
    frames = []
    for frame in (outer, chem_outer):
        expanded = frame.copy()
        for col in cols:
            if col not in expanded.columns:
                expanded[col] = np.nan
        frames.append(expanded[cols])
    combined = pd.concat(frames, ignore_index=True)
    combined.to_csv(EXP / "combined_strong_baseline_outer_scores.csv", index=False)
    summary = (
        combined.groupby(["candidate", "family", "task_type"], dropna=False)
        .agg(
            n_outer_units=("outer_utility", "size"),
            n_tasks=("task", "nunique"),
            outer_utility_mean=("outer_utility", "mean"),
            outer_utility_sd=("outer_utility", "std"),
            inner_utility_mean=("inner_mean", "mean"),
            roc_auc_mean=("roc_auc", "mean"),
            pr_auc_mean=("pr_auc", "mean"),
            rmse_mean=("rmse", "mean"),
        )
        .reset_index()
    )
    summary.to_csv(EXP / "combined_strong_baseline_summary.csv", index=False)
    return combined


def rank_corr(group: pd.DataFrame) -> float | None:
    if len(group) < 3:
        return None
    inner_rank = group["inner_mean"].rank(method="average")
    outer_rank = group["outer_utility"].rank(method="average")
    corr = inner_rank.corr(outer_rank)
    if pd.isna(corr):
        return None
    return float(corr)


def selection_analyses(outer: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    keys = ["task", "task_type", "seed", "outer_fold"]
    for unit, group in outer.groupby(keys, sort=True):
        task, task_type, seed, outer_fold = unit
        group = group.dropna(subset=["inner_mean", "outer_utility"]).copy()
        if group.empty:
            continue
        group = group.sort_values(["inner_mean", "candidate"], ascending=[False, True])
        selected = group.iloc[0]
        oracle = group.sort_values(["outer_utility", "candidate"], ascending=[False, True]).iloc[0]
        worst = group.sort_values(["outer_utility", "candidate"], ascending=[True, True]).iloc[0]
        baseline = group[group["candidate"].eq("rdkit_rf")]
        baseline_utility = float(baseline.iloc[0]["outer_utility"]) if len(baseline) else np.nan
        selected_outer = float(selected["outer_utility"])
        oracle_outer = float(oracle["outer_utility"])
        worst_outer = float(worst["outer_utility"])
        candidate_range = oracle_outer - worst_outer
        selection_loss = oracle_outer - selected_outer
        attainable_gain = oracle_outer - baseline_utility if not pd.isna(baseline_utility) else np.nan
        realized_gain = selected_outer - baseline_utility if not pd.isna(baseline_utility) else np.nan
        eta = realized_gain / attainable_gain if attainable_gain and attainable_gain > 0 else np.nan
        selected_outer_rank = int((group["outer_utility"] > selected_outer + 1e-12).sum() + 1)
        rows.append(
            {
                "task": task,
                "task_type": task_type,
                "seed": int(seed),
                "outer_fold": int(outer_fold),
                "n_candidates": int(group["candidate"].nunique()),
                "selected_candidate": selected["candidate"],
                "selected_inner_mean": float(selected["inner_mean"]),
                "selected_outer_utility": selected_outer,
                "oracle_candidate": oracle["candidate"],
                "oracle_outer_utility": oracle_outer,
                "worst_candidate": worst["candidate"],
                "worst_outer_utility": worst_outer,
                "rdkit_outer_utility": baseline_utility,
                "candidate_outer_range": candidate_range,
                "selection_loss": selection_loss,
                "range_normalized_selection_loss": selection_loss / candidate_range if candidate_range > 1e-12 else 0.0,
                "realized_gain_vs_rdkit": realized_gain,
                "attainable_gain_vs_rdkit": attainable_gain,
                "realized_to_attainable_ratio": eta,
                "outer_top1_hit": selected["candidate"] == oracle["candidate"],
                "selected_outer_rank": selected_outer_rank,
                "inner_outer_spearman": rank_corr(group),
            }
        )
    detail = pd.DataFrame(rows)
    detail.to_csv(EXP / "combined_strong_selection_detail.csv", index=False)
    summary = (
        detail.groupby(["task", "task_type"], dropna=False)
        .agg(
            n_units=("selection_loss", "size"),
            mean_candidates=("n_candidates", "mean"),
            outer_top1_hit_rate=("outer_top1_hit", "mean"),
            mean_selection_loss=("selection_loss", "mean"),
            median_selection_loss=("selection_loss", "median"),
            mean_range_normalized_selection_loss=("range_normalized_selection_loss", "mean"),
            mean_realized_gain_vs_rdkit=("realized_gain_vs_rdkit", "mean"),
            mean_attainable_gain_vs_rdkit=("attainable_gain_vs_rdkit", "mean"),
            mean_realized_to_attainable_ratio=("realized_to_attainable_ratio", "mean"),
            mean_inner_outer_spearman=("inner_outer_spearman", "mean"),
        )
        .reset_index()
    )
    overall = pd.DataFrame(
        [
            {
                "task": "__overall__",
                "task_type": "mixed",
                "n_units": int(len(detail)),
                "mean_candidates": float(detail["n_candidates"].mean()),
                "outer_top1_hit_rate": float(detail["outer_top1_hit"].mean()),
                "mean_selection_loss": float(detail["selection_loss"].mean()),
                "median_selection_loss": float(detail["selection_loss"].median()),
                "mean_range_normalized_selection_loss": float(detail["range_normalized_selection_loss"].mean()),
                "mean_realized_gain_vs_rdkit": float(detail["realized_gain_vs_rdkit"].mean()),
                "mean_attainable_gain_vs_rdkit": float(detail["attainable_gain_vs_rdkit"].mean()),
                "mean_realized_to_attainable_ratio": float(detail["realized_to_attainable_ratio"].mean(skipna=True)),
                "mean_inner_outer_spearman": float(detail["inner_outer_spearman"].mean(skipna=True)),
            }
        ]
    )
    summary = pd.concat([summary, overall], ignore_index=True)
    summary.to_csv(EXP / "combined_strong_selection_summary.csv", index=False)
    counts = (
        detail.groupby(["task", "selected_candidate"], dropna=False)
        .size()
        .reset_index(name="n_selected_units")
        .sort_values(["task", "n_selected_units", "selected_candidate"], ascending=[True, False, True])
    )
    counts.to_csv(EXP / "combined_strong_selected_candidate_counts.csv", index=False)
    return detail, summary


def paired_endpoint_effects(outer: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    idx = ["task", "task_type", "seed", "outer_fold"]
    wide = outer.pivot_table(index=idx, columns="candidate", values="outer_utility", aggfunc="mean")
    if "rdkit_rf" not in wide.columns:
        raise RuntimeError("rdkit_rf baseline is missing from combined outer scores")
    rows = []
    for candidate in sorted(c for c in wide.columns if c != "rdkit_rf"):
        sub = wide[["rdkit_rf", candidate]].dropna()
        for unit, values in sub.iterrows():
            task, task_type, seed, outer_fold = unit
            delta = float(values[candidate] - values["rdkit_rf"])
            rows.append(
                {
                    "task": task,
                    "task_type": task_type,
                    "seed": int(seed),
                    "outer_fold": int(outer_fold),
                    "candidate": candidate,
                    "baseline": "rdkit_rf",
                    "candidate_outer_utility": float(values[candidate]),
                    "baseline_outer_utility": float(values["rdkit_rf"]),
                    "delta_vs_rdkit": delta,
                    "beats_rdkit": delta > 0,
                }
            )
    detail = pd.DataFrame(rows)
    detail.to_csv(EXP / "combined_strong_candidate_paired_effect_detail.csv", index=False)
    by_task = (
        detail.groupby(["candidate", "task", "task_type"], dropna=False)
        .agg(
            n_units=("delta_vs_rdkit", "size"),
            mean_delta_vs_rdkit=("delta_vs_rdkit", "mean"),
            median_delta_vs_rdkit=("delta_vs_rdkit", "median"),
            win_rate_vs_rdkit=("beats_rdkit", "mean"),
        )
        .reset_index()
    )
    overall = (
        detail.groupby(["candidate"], dropna=False)
        .agg(
            n_units=("delta_vs_rdkit", "size"),
            n_tasks=("task", "nunique"),
            mean_delta_vs_rdkit=("delta_vs_rdkit", "mean"),
            median_delta_vs_rdkit=("delta_vs_rdkit", "median"),
            win_rate_vs_rdkit=("beats_rdkit", "mean"),
        )
        .reset_index()
    )
    overall["task"] = "__overall__"
    overall["task_type"] = "mixed"
    summary = pd.concat([by_task, overall[by_task.columns]], ignore_index=True)
    summary.to_csv(EXP / "combined_strong_candidate_paired_effects.csv", index=False)
    return detail, summary


def write_runtime_status(outer: pd.DataFrame, chem_inner_audit: dict[str, object]) -> dict[str, object]:
    status = read_csv("strong_baseline_runtime_status.csv")
    tab_row = status[status["candidate"].eq("tabpfn_rdkit")]
    tab = tab_row.iloc[0].to_dict() if len(tab_row) else {}
    rows = []
    for candidate in sorted(outer["candidate"].dropna().unique()):
        if candidate == "chemprop_dmpnn":
            rows.append(
                {
                    "candidate": candidate,
                    "status": "completed_same_split_outer_inner",
                    "reason": (
                        f"45 outer test units and {int(chem_inner_audit['inner_rows'])} "
                        "inner-fold retraining units completed in Chemprop scripts."
                    ),
                }
            )
        else:
            rows.append(
                {
                    "candidate": candidate,
                    "status": "completed_same_split_outer_inner",
                    "reason": "Representative strict 3x3x5 panel completed in the shared frozen split protocol.",
                }
            )
    if tab:
        rows.append(
            {
                "candidate": "tabpfn_rdkit",
                "status": tab.get("status"),
                "reason": tab.get("reason"),
            }
        )
    combined_status = pd.DataFrame(rows)
    combined_status.to_csv(EXP / "combined_strong_runtime_status.csv", index=False)
    return tab


def update_combined_audit(audit: dict[str, object]) -> None:
    combined_path = EXP / "paper12_combined_gap_audit.json"
    if combined_path.exists():
        combined = json.loads(combined_path.read_text(encoding="utf-8"))
    else:
        combined = {}
    combined.update(audit)
    combined["passed"] = bool(combined.get("passed", True) and audit["passed"])
    combined_path.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    inner = combine_inner_scores()
    outer = combine_outer_scores_with_inner_means()
    selection_detail, selection_summary = selection_analyses(outer)
    paired_detail, paired_summary = paired_endpoint_effects(outer)
    chem_inner_audit = json.loads((EXP / "chemprop_inner_audit.json").read_text(encoding="utf-8"))
    tab = write_runtime_status(outer, chem_inner_audit)
    overall_selection = selection_summary[selection_summary["task"].eq("__overall__")].iloc[0]
    audit = {
        "combined_inner_score_rows": int(len(inner)),
        "combined_outer_score_rows": int(len(outer)),
        "combined_candidates": sorted(outer["candidate"].dropna().unique().tolist()),
        "chemprop_inner_rows": int(chem_inner_audit["inner_rows"]),
        "chemprop_inner_prediction_rows": int(chem_inner_audit["prediction_rows"]),
        "chemprop_inner_complete": bool(chem_inner_audit["passed"]),
        "chemprop_inner_expected_rows": 3 * 5 * 3 * 3,
        "strong_selection_units": int(len(selection_detail)),
        "strong_selection_mean_loss": to_float(overall_selection["mean_selection_loss"]),
        "strong_selection_mean_range_normalized_loss": to_float(
            overall_selection["mean_range_normalized_selection_loss"]
        ),
        "strong_selection_top1_hit_rate": to_float(overall_selection["outer_top1_hit_rate"]),
        "strong_selection_mean_inner_outer_spearman": to_float(
            overall_selection["mean_inner_outer_spearman"]
        ),
        "paired_effect_rows": int(len(paired_detail)),
        "paired_effect_summary_rows": int(len(paired_summary)),
        "tabpfn_status": tab.get("status"),
        "tabpfn_reason": tab.get("reason"),
    }
    audit["passed"] = (
        audit["chemprop_inner_complete"]
        and audit["chemprop_inner_rows"] == audit["chemprop_inner_expected_rows"]
        and audit["combined_inner_score_rows"] == 675
        and audit["combined_outer_score_rows"] == 225
        and audit["strong_selection_units"] == 45
        and set(audit["combined_candidates"])
        == {
            "chemberta_mtr_linear_probe",
            "chemprop_dmpnn",
            "gnn_gcn",
            "molformer_linear_probe",
            "rdkit_rf",
        }
    )
    AUDIT_PATH.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    update_combined_audit(audit)
    if not audit["passed"]:
        raise SystemExit(json.dumps(audit, ensure_ascii=False, indent=2))
    print(AUDIT_PATH)


if __name__ == "__main__":
    main()
