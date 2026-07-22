from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scipy.stats import binomtest, wilcoxon
except Exception:  # pragma: no cover - optional dependency guard
    binomtest = None
    wilcoxon = None

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "reports" / "experiment_thickening_stats"


def safe_wilcoxon_greater(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    values = values[np.abs(values) > 1e-12]
    if wilcoxon is None or len(values) < 2:
        return np.nan
    try:
        return float(wilcoxon(values, alternative="greater").pvalue)
    except ValueError:
        return np.nan


def safe_sign_test_greater(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    values = values[np.abs(values) > 1e-12]
    if binomtest is None or len(values) == 0:
        return np.nan
    positives = int((values > 0).sum())
    return float(binomtest(positives, len(values), p=0.5, alternative="greater").pvalue)


def summarize_delta(frame: pd.DataFrame, group_cols: list[str], metric_cols: list[str], analysis: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    usable_cols = [col for col in metric_cols if col in frame.columns]
    for keys, sub in frame.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        key_dict = dict(zip(group_cols, keys))
        for col in usable_cols:
            values = pd.to_numeric(sub[col], errors="coerce").dropna().to_numpy(dtype=float)
            if len(values) == 0:
                continue
            rows.append(
                {
                    "analysis": analysis,
                    **key_dict,
                    "metric": col,
                    "n": int(len(values)),
                    "mean_delta": float(np.mean(values)),
                    "median_delta": float(np.median(values)),
                    "std_delta": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
                    "positive_n": int((values > 0).sum()),
                    "positive_fraction": float((values > 0).mean()),
                    "wilcoxon_p_greater": safe_wilcoxon_greater(values),
                    "sign_test_p_greater": safe_sign_test_greater(values),
                }
            )
    return pd.DataFrame(rows)


def calibration_stats() -> pd.DataFrame:
    path = ROOT / "reports" / "validation_calibration" / "selected_vs_uncalibrated.csv"
    frame = pd.read_csv(path)
    metric_cols = ["delta_brier_positive", "delta_ece_positive", "delta_roc_auc", "delta_pr_auc"]
    return summarize_delta(frame, ["source", "dataset"], metric_cols, "validation_calibration")


def ad_gated_stats() -> pd.DataFrame:
    path = ROOT / "reports" / "ad_gated_selector" / "ad_gated_vs_full.csv"
    frame = pd.read_csv(path)
    metric_cols = [
        "delta_rmse_positive",
        "delta_roc_auc_positive",
        "delta_pr_auc_positive",
        "delta_brier_positive",
        "delta_ece_positive",
    ]
    return summarize_delta(frame, ["source", "task_type", "risk_score", "coverage"], metric_cols, "ad_gated_selector")


def split_realism_stats() -> pd.DataFrame:
    path = ROOT / "reports" / "split_realism_tdc_lgbm_seed3" / "metrics_raw.csv"
    frame = pd.read_csv(path)
    rows: list[dict[str, object]] = []
    for dataset, sub in frame.groupby("dataset"):
        task_type = str(sub["task_type"].iloc[0])
        if task_type == "classification":
            metric = "roc_auc"
            wide = sub.pivot_table(index="seed", columns="split_method", values=metric, aggfunc="mean")
            if {"random", "structure"}.issubset(wide.columns):
                values = (wide["random"] - wide["structure"]).dropna().to_numpy(dtype=float)
                direction = "random_minus_structure_auc"
            else:
                continue
        else:
            metric = "rmse"
            wide = sub.pivot_table(index="seed", columns="split_method", values=metric, aggfunc="mean")
            if {"random", "structure"}.issubset(wide.columns):
                values = (wide["structure"] - wide["random"]).dropna().to_numpy(dtype=float)
                direction = "structure_minus_random_rmse"
            else:
                continue
        if len(values) == 0:
            continue
        rows.append(
            {
                "analysis": "tdc_split_realism_seed3",
                "source": "split_realism_tdc_lgbm_seed3",
                "dataset": dataset,
                "task_type": task_type,
                "risk_score": "",
                "coverage": "",
                "metric": direction,
                "n": int(len(values)),
                "mean_delta": float(np.mean(values)),
                "median_delta": float(np.median(values)),
                "std_delta": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
                "positive_n": int((values > 0).sum()),
                "positive_fraction": float((values > 0).mean()),
                "wilcoxon_p_greater": safe_wilcoxon_greater(values),
                "sign_test_p_greater": safe_sign_test_greater(values),
            }
        )
    return pd.DataFrame(rows)


def write_readme(summary: pd.DataFrame) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    strongest = summary.sort_values(["positive_fraction", "mean_delta"], ascending=[False, False]).head(20)
    lines = [
        "# Experiment thickening statistical tests",
        "",
        "All tests are computed from completed experiment outputs. Positive deltas are defined as favorable movement.",
        "",
        "- Wilcoxon p-values are one-sided tests for median delta > 0.",
        "- Sign-test p-values are one-sided binomial tests for more positive than negative deltas.",
        "- Small groups should be read as descriptive evidence, not as definitive hypothesis tests.",
        "",
        "Top favorable rows:",
        "",
        strongest.to_markdown(index=False),
        "",
    ]
    (OUT_DIR / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    frames = [calibration_stats(), ad_gated_stats(), split_realism_stats()]
    summary = pd.concat(frames, ignore_index=True, sort=False)
    summary.to_csv(OUT_DIR / "thickening_paired_tests.csv", index=False)

    by_analysis = (
        summary.groupby(["analysis", "metric"], dropna=False)
        .agg(
            n_groups=("metric", "size"),
            mean_of_mean_deltas=("mean_delta", "mean"),
            median_positive_fraction=("positive_fraction", "median"),
            groups_all_positive=("positive_fraction", lambda x: int((x >= 1.0).sum())),
        )
        .reset_index()
    )
    by_analysis.to_csv(OUT_DIR / "thickening_paired_tests_overview.csv", index=False)
    write_readme(summary)
    print(f"Wrote statistical summaries to {OUT_DIR}")


if __name__ == "__main__":
    main()
