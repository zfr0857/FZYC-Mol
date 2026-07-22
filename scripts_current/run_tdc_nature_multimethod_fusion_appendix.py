from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "scripts"))

from run_nature_multimethod_fusion_appendix import (  # noqa: E402
    FIG_DIR,
    TABLE_DIR,
    append_rows,
    build_alignment_matrix,
    optional_dependency_status,
    run_one,
    score_delta,
)


OUT_DIR = ROOT / "reports" / "tdc_nature_multimethod_fusion_appendix"
TDC_TABLE = TABLE_DIR / "table3_tdc_official_admet.csv"
TABLE32_PATH = TABLE_DIR / "table32_tdc_nature_multimethod_fusion_retained_best.csv"
TABLE33_PATH = TABLE_DIR / "table33_tdc_nature_multimethod_fusion_candidate_families.csv"
TABLE34_PATH = TABLE_DIR / "table34_tdc_nature_method_alignment_matrix.csv"
DEFAULT_DATASETS = [
    "tdc_caco2_wang",
    "tdc_hia_hou",
    "tdc_pgp_broccatelli",
    "tdc_bioavailability_ma",
    "tdc_bbb_martins",
    "tdc_cyp2c9_veith",
    "tdc_cyp2d6_veith",
    "tdc_cyp3a4_veith",
]


def summarize(output_dir: Path) -> None:
    selected_path = output_dir / "selected_metrics_raw.csv"
    if not selected_path.exists():
        return
    raw = pd.read_csv(selected_path).drop_duplicates(["dataset", "seed"], keep="last")
    raw.to_csv(selected_path, index=False)

    summary_rows = []
    for dataset, group in raw.groupby("dataset", dropna=False):
        counts = Counter(group["model"].astype(str))
        nature_counts = Counter(group["nature_inspiration"].astype(str))
        row: dict[str, object] = {
            "dataset": dataset,
            "task_type": str(group["task_type"].iloc[0]),
            "primary_metric": str(group["primary_metric"].iloc[0]),
            "primary_direction": str(group["primary_direction"].iloc[0]),
            "n_seeds": int(group["seed"].nunique()),
            "fusion_model_counts": "; ".join(f"{key}:{value}" for key, value in counts.most_common()),
            "nature_inspiration_counts": "; ".join(f"{key}:{value}" for key, value in nature_counts.most_common()),
            "fusion_primary_mean": float(group["primary_value"].mean()),
            "fusion_primary_std": float(group["primary_value"].std(ddof=1)),
            "fusion_validation_primary_mean": float(group["validation_primary"].mean()),
            "fit_seconds_mean": float(group["fit_seconds"].mean()),
        }
        for metric in ["rmse", "mae", "roc_auc", "pr_auc", "brier", "ece", "ef1", "ef5"]:
            col = f"test_{metric}"
            row[f"{metric}_mean"] = float(group[col].mean()) if col in group else np.nan
            row[f"{metric}_std"] = float(group[col].std(ddof=1)) if col in group else np.nan
        summary_rows.append(row)
    summary = pd.DataFrame(summary_rows).sort_values("dataset")
    summary.to_csv(output_dir / "selected_metrics_summary.csv", index=False)

    previous = pd.read_csv(TDC_TABLE)
    previous = previous[
        [
            "dataset",
            "task_type",
            "primary_metric",
            "direction",
            "selector_value",
            "selector_std",
            "selector_formatted",
        ]
    ].rename(
        columns={
            "direction": "primary_direction",
            "selector_value": "previous_selector_primary_mean",
            "selector_std": "previous_selector_primary_std",
        }
    )
    combined = previous.merge(summary, on=["dataset", "task_type", "primary_metric", "primary_direction"], how="right")
    combined["delta_vs_tdc_selector"] = combined.apply(
        lambda row: score_delta(
            str(row["primary_direction"]),
            float(row["previous_selector_primary_mean"]),
            float(row["fusion_primary_mean"]),
        ),
        axis=1,
    )
    combined["retained_source"] = np.where(
        combined["delta_vs_tdc_selector"] > 0.0,
        "tdc_nature_multimethod_fusion",
        "tdc_validation_selector",
    )
    combined["retained_primary_mean"] = np.where(
        combined["delta_vs_tdc_selector"] > 0.0,
        combined["fusion_primary_mean"],
        combined["previous_selector_primary_mean"],
    )
    combined["retained_primary_std"] = np.where(
        combined["delta_vs_tdc_selector"] > 0.0,
        combined["fusion_primary_std"],
        combined["previous_selector_primary_std"],
    )
    combined["retained_model"] = np.where(
        combined["delta_vs_tdc_selector"] > 0.0,
        combined["fusion_model_counts"],
        "validation_selector_tdc_admet",
    )
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    combined.sort_values("dataset").to_csv(TABLE32_PATH, index=False)

    candidates_path = output_dir / "candidate_metrics_raw.csv"
    family_rows = []
    if candidates_path.exists():
        candidates = pd.read_csv(candidates_path)
        candidates = candidates.drop_duplicates(["dataset", "seed", "model", "candidate_type"], keep="last")
        for (dataset, candidate_type, nature), group in candidates.groupby(["dataset", "candidate_type", "nature_inspiration"], dropna=False):
            family_rows.append(
                {
                    "dataset": dataset,
                    "candidate_type": candidate_type,
                    "nature_inspiration": nature,
                    "n_candidates": int(len(group)),
                    "validation_primary_mean": float(group["validation_primary"].mean()),
                    "test_primary_mean": float(group["primary_value"].mean()),
                }
            )
    pd.DataFrame(family_rows).sort_values(["dataset", "candidate_type", "nature_inspiration"]).to_csv(TABLE33_PATH, index=False)
    build_alignment_matrix().to_csv(TABLE34_PATH, index=False)
    plot_decision_figure(combined)

    readme_lines = [
        "# TDC Nature-Inspired Multimethod Fusion Appendix",
        "",
        "This external appendix applies the Nature-inspired fusion candidate pool to the official TDC ADMET panel already used in the manuscript.",
        "It compares the fusion candidates against the existing TDC validation selector and retains fusion only when validation-selected seed-level results improve the primary metric.",
        "",
        f"- Candidate metrics: `{(output_dir / 'candidate_metrics_raw.csv').resolve().relative_to(ROOT)}`",
        f"- Selected metrics: `{(output_dir / 'selected_metrics_raw.csv').resolve().relative_to(ROOT)}`",
        f"- Selected summary: `{(output_dir / 'selected_metrics_summary.csv').resolve().relative_to(ROOT)}`",
        "- Retained-best table: `reports/manuscript_tables/table32_tdc_nature_multimethod_fusion_retained_best.csv`",
        "- Candidate-family table: `reports/manuscript_tables/table33_tdc_nature_multimethod_fusion_candidate_families.csv`",
        "",
        "## Retained-Best Outcome",
        "",
    ]
    for row in combined.sort_values("dataset").itertuples(index=False):
        readme_lines.append(
            f"- `{row.dataset}`: selector={row.previous_selector_primary_mean:.4f}, "
            f"fusion={row.fusion_primary_mean:.4f}, "
            f"delta={row.delta_vs_tdc_selector:+.4f}, retained=`{row.retained_source}`."
        )
    readme_lines.append("")
    readme_lines.append("All decisions are made by validation primary metrics only; test labels are used only after selection.")
    (output_dir / "README.md").write_text("\n".join(readme_lines), encoding="utf-8")


def plot_decision_figure(combined: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    plot = combined.copy().sort_values("delta_vs_tdc_selector")
    labels = [f"{row.dataset.replace('tdc_', '')}\n{row.primary_metric.upper()}" for row in plot.itertuples(index=False)]
    deltas = plot["delta_vs_tdc_selector"].astype(float).to_numpy()
    colors = ["#1b8a6b" if value > 0 else "#d7dee8" for value in deltas]
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.edgecolor": "#cbd5e1",
            "axes.labelcolor": "#0f172a",
            "xtick.color": "#334155",
            "ytick.color": "#334155",
            "figure.dpi": 180,
            "savefig.dpi": 320,
        }
    )
    fig, ax = plt.subplots(figsize=(9.8, 5.65))
    y_pos = np.arange(len(plot))
    ax.barh(y_pos, deltas, color=colors, alpha=0.96, height=0.58, edgecolor="white", linewidth=0.8)
    ax.axvline(0, color="#334155", linewidth=0.9)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Validation-normalized gain vs TDC validation selector")
    ax.set_title("External TDC fusion gate", loc="left", pad=12, fontsize=12.5, fontweight="bold")
    ax.grid(axis="x", color="#e5e7eb", linewidth=0.65, alpha=0.85)
    ax.set_axisbelow(True)
    span = max(0.02, float(np.nanmax(np.abs(deltas))) * 0.13)
    for y, row, delta in zip(y_pos, plot.itertuples(index=False), deltas):
        source = "promote fusion" if delta > 0 else "keep selector"
        text = f"{delta:+.3f} | {source}"
        if delta > 0:
            x = delta + span * 0.25
            ha = "left"
            color = "#14532d"
        else:
            x = delta + span * 0.25
            ha = "left"
            color = "#475569"
        ax.text(x, y, text, va="center", ha=ha, fontsize=8.7, color=color, fontweight="bold")
    max_abs = max(0.08, float(np.nanmax(np.abs(deltas))) + span)
    ax.set_xlim(-max_abs, max_abs)
    fig.text(
        0.125,
        0.03,
        "Green bars are promoted; gray bars keep the TDC validation selector. Lower RMSE and higher ROC-AUC are both converted to positive-delta gain.",
        fontsize=8.3,
        color="#475569",
        ha="left",
        va="center",
    )
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color("#e2e8f0")
    ax.spines["bottom"].set_color("#e2e8f0")
    fig.tight_layout(rect=[0, 0.06, 1, 1])
    for ext in ["png", "svg"]:
        fig.savefig(FIG_DIR / f"fig19_tdc_nature_multimethod_fusion_decision.{ext}", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run TDC Nature-inspired multimethod fusion appendix.")
    parser.add_argument("--datasets", nargs="*", default=DEFAULT_DATASETS)
    parser.add_argument("--seeds", nargs="*", type=int, default=[13, 17, 23])
    parser.add_argument("--output-dir", default=str(OUT_DIR))
    parser.add_argument("--n-estimators", type=int, default=120)
    parser.add_argument("--embedding-pca", type=int, default=64)
    parser.add_argument("--undersampling-bags", type=int, default=5)
    parser.add_argument("--include-catboost", action="store_true")
    parser.add_argument("--include-xgb", action="store_true")
    parser.add_argument("--regression-transforms", nargs="*", default=["identity", "winsor", "quantile_normal"])
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--no-resume", action="store_false", dest="resume")
    args = parser.parse_args()

    deps = optional_dependency_status()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "dependency_status.json").write_text(json.dumps(deps, indent=2), encoding="utf-8")

    selected_path = output_dir / "selected_metrics_raw.csv"
    if args.resume and selected_path.exists():
        existing = pd.read_csv(selected_path)
        done = {(str(row["dataset"]), int(row["seed"])) for row in existing.to_dict("records")}
    else:
        done = set()

    for dataset in args.datasets:
        for seed in args.seeds:
            key = (dataset, int(seed))
            if key in done:
                print(f"skip dataset={dataset} seed={seed}", flush=True)
                continue
            print(f"run dataset={dataset} seed={seed}", flush=True)
            candidates, selected = run_one(dataset, seed, args, deps)
            append_rows(output_dir / "candidate_metrics_raw.csv", candidates)
            append_rows(selected_path, [selected])
            summarize(output_dir)

    summarize(output_dir)
    print(f"wrote {output_dir}", flush=True)


if __name__ == "__main__":
    main()
