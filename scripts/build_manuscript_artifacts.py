from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from rdkit import RDLogger

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fzyc_mol.datasets import DATASETS, load_dataset  # noqa: E402

RDLogger.DisableLog("rdApp.*")

TABLE_DIR = ROOT / "reports" / "manuscript_tables"
FIG_DIR = ROOT / "reports" / "manuscript_figures"
TABLE19_PATH = TABLE_DIR / "table19_moleculenet_rescue_integrated_selector.csv"
TABLE27_PATH = TABLE_DIR / "table27_moleculenet_targeted_rebuild_retained_best.csv"
TABLE29_PATH = TABLE_DIR / "table29_nature_multimethod_fusion_retained_best.csv"
TABLE32_PATH = TABLE_DIR / "table32_tdc_nature_multimethod_fusion_retained_best.csv"
MOLECULENET = ["esol", "freesolv", "lipo", "bbbp", "bace", "clintox"]
TDC_ADMET = [
    "tdc_caco2_wang",
    "tdc_hia_hou",
    "tdc_pgp_broccatelli",
    "tdc_bioavailability_ma",
    "tdc_bbb_martins",
    "tdc_cyp2c9_veith",
    "tdc_cyp2d6_veith",
    "tdc_cyp3a4_veith",
]


def ensure_dirs() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)


def read_multi_header_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, header=[0, 1])
    columns: list[str] = []
    for top, bottom in frame.columns:
        top = str(top).strip()
        bottom = str(bottom).strip()
        if top.startswith("Unnamed"):
            name = bottom
        elif bottom.startswith("Unnamed") or bottom in {"", "nan"}:
            name = top
        else:
            name = f"{top}_{bottom}"
        columns.append(name)
    frame.columns = columns
    return frame


def primary_metric(task_type: str) -> tuple[str, str]:
    if task_type == "regression":
        return "rmse", "lower"
    return "roc_auc", "higher"


def primary_from_row(row: pd.Series) -> tuple[float, float, str, str]:
    metric, direction = primary_metric(str(row["task_type"]))
    value = row.get(f"{metric}_mean", np.nan)
    std = row.get(f"{metric}_std", np.nan)
    return float(value), float(std) if pd.notna(std) else np.nan, metric, direction


def fmt_metric(value: float, std: float | None = None, digits: int = 4) -> str:
    if pd.isna(value):
        return ""
    if std is None or pd.isna(std):
        return f"{value:.{digits}f}"
    return f"{value:.{digits}f} +/- {std:.{digits}f}"


def best_row(frame: pd.DataFrame, dataset: str, mask: pd.Series) -> pd.Series | None:
    subset = frame[(frame["dataset"] == dataset) & mask].copy()
    if subset.empty:
        return None
    task_type = str(subset.iloc[0]["task_type"])
    metric, direction = primary_metric(task_type)
    col = f"{metric}_mean"
    subset = subset[pd.notna(subset[col])]
    if subset.empty:
        return None
    idx = subset[col].idxmin() if direction == "lower" else subset[col].idxmax()
    return subset.loc[idx]


def selector_summary(path: Path) -> pd.DataFrame:
    return read_multi_header_csv(path)


def build_table1_dataset_protocol() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for dataset in MOLECULENET + TDC_ADMET:
        frame, spec = load_dataset(dataset)
        source = "MoleculeNet" if dataset in MOLECULENET else "TDC ADMET"
        metric, _ = primary_metric(spec.task_type)
        positives = int(frame["y"].sum()) if spec.task_type == "classification" else ""
        positive_rate = float(frame["y"].mean()) if spec.task_type == "classification" else ""
        if dataset in MOLECULENET:
            splits = "scaffold; random; structure-separated; low-similarity hard subset"
            seeds = "5 main seeds"
            special = "selector, ablation, significance, uncertainty/AD, conformal, enrichment"
        else:
            splits = "strict scaffold selector; official PyTDC random/scaffold; structure-separated stress"
            seeds = "5 selector seeds; 3 official split seeds; 1 structure-stress seed"
            special = "ADMET transfer, official split, uncertainty/AD, enrichment"
        rows.append(
            {
                "dataset": dataset,
                "source": source,
                "task_type": spec.task_type,
                "n_molecules": len(frame),
                "n_positives": positives,
                "positive_rate": positive_rate,
                "primary_metric": metric.upper() if metric == "rmse" else "ROC-AUC",
                "splits": splits,
                "seeds": seeds,
                "special_evaluation": special,
            }
        )
    table = pd.DataFrame(rows)
    table.to_csv(TABLE_DIR / "table1_dataset_protocol.csv", index=False)
    return table


def build_table2_moleculenet_main() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary = pd.read_csv(ROOT / "reports" / "combined_model_summary.csv")
    selector = selector_summary(ROOT / "reports" / "validation_selector_expanded" / "metrics_summary.csv")
    ranking = pd.read_csv(ROOT / "reports" / "combined_primary_ranking.csv")
    rescue_integrated = pd.read_csv(TABLE19_PATH) if TABLE19_PATH.exists() else pd.DataFrame()
    targeted_rebuild = pd.read_csv(TABLE27_PATH) if TABLE27_PATH.exists() else pd.DataFrame()
    nature_fusion = pd.read_csv(TABLE29_PATH) if TABLE29_PATH.exists() else pd.DataFrame()

    categories = {
        "Classical Morgan": lambda df: (df["source"].eq("strict_core_fast"))
        & df["model"].isin(["rf_morgan", "xgb_morgan", "lgbm_morgan"]),
        "Graph / D-MPNN core": lambda df: (df["source"].eq("strict_core_fast"))
        & df["model"].isin(["gin", "dmpnn", "fzyc_mol_static"]),
        "Chemprop": lambda df: df["source"].eq("chemprop_baseline"),
        "Frozen pretrained": lambda df: df["source"].str.startswith("pretrained_", na=False),
        "Multi-fingerprint": lambda df: df["source"].isin(["strict_multifp_fast", "strict_multifp"]),
        "Descriptor / motif": lambda df: df["source"].eq("descriptor_motif_baselines"),
    }

    rows: list[dict[str, object]] = []
    for dataset in MOLECULENET:
        task_type = DATASETS[dataset].task_type
        metric, direction = primary_metric(task_type)
        for category, mask_fn in categories.items():
            row = best_row(summary, dataset, mask_fn(summary))
            if row is None:
                continue
            value = float(row[f"{metric}_mean"])
            std = float(row[f"{metric}_std"]) if pd.notna(row.get(f"{metric}_std")) else np.nan
            rows.append(
                {
                    "dataset": dataset,
                    "task_type": task_type,
                    "primary_metric": metric,
                    "direction": direction,
                    "category": category,
                    "model": row["model"],
                    "source": row["source"],
                    "value": value,
                    "std": std,
                    "formatted": fmt_metric(value, std),
                }
            )
        selector_row = selector[selector["dataset"].eq(dataset)].iloc[0]
        sel_value, sel_std, metric, direction = primary_from_row(selector_row)
        rows.append(
            {
                "dataset": dataset,
                "task_type": task_type,
                "primary_metric": metric,
                "direction": direction,
                "category": "FZYC-Mol validation selector",
                "model": "validation_selector",
                "source": "validation_selector_expanded",
                "value": sel_value,
                "std": sel_std,
                "formatted": fmt_metric(sel_value, sel_std),
            }
        )
        targeted_value = sel_value
        targeted_std = sel_std
        targeted_model = "validation_selector"
        targeted_source = "validation_selector_expanded"
        rescue_row = rescue_integrated[rescue_integrated["dataset"].eq(dataset)]
        if not rescue_row.empty and str(rescue_row.iloc[0].get("integration_better_than_current", False)).lower() == "true":
            rrow = rescue_row.iloc[0]
            targeted_value = float(rrow["integrated_primary_mean"])
            targeted_std = float(rrow["integrated_primary_std"]) if pd.notna(rrow.get("integrated_primary_std")) else np.nan
            targeted_model = str(rrow.get("selected_model_counts", "rescue_integrated_selector")).split(":")[0]
            targeted_source = "validation_selector_rescue_integration"
        rows.append(
            {
                "dataset": dataset,
                "task_type": task_type,
                "primary_metric": metric,
                "direction": direction,
                "category": "FZYC-Mol targeted rescue selector",
                "model": targeted_model,
                "source": targeted_source,
                "value": targeted_value,
                "std": targeted_std,
                "formatted": fmt_metric(targeted_value, targeted_std),
            }
        )
        final_value = targeted_value
        final_std = targeted_std
        final_model = targeted_model
        final_source = targeted_source
        rebuild_row = targeted_rebuild[targeted_rebuild["dataset"].eq(dataset)]
        if not rebuild_row.empty:
            rebuild_row = rebuild_row.iloc[0]
            final_value = float(rebuild_row["retained_primary_mean"])
            final_std = (
                float(rebuild_row["retained_primary_std"])
                if pd.notna(rebuild_row.get("retained_primary_std"))
                else np.nan
            )
            final_model = str(rebuild_row.get("retained_model", final_model))
            final_source = str(rebuild_row.get("retained_source", final_source))
        fusion_row = nature_fusion[nature_fusion["dataset"].eq(dataset)]
        if not fusion_row.empty:
            fusion_row = fusion_row.iloc[0]
            final_value = float(fusion_row["retained_primary_mean"])
            final_std = (
                float(fusion_row["retained_primary_std"])
                if pd.notna(fusion_row.get("retained_primary_std"))
                else np.nan
            )
            final_model = str(fusion_row.get("retained_model", final_model))
            final_source = str(fusion_row.get("retained_source", final_source))
        rows.append(
            {
                "dataset": dataset,
                "task_type": task_type,
                "primary_metric": metric,
                "direction": direction,
                "category": "FZYC-Mol final retained-best",
                "model": final_model,
                "source": final_source,
                "value": final_value,
                "std": final_std,
                "formatted": fmt_metric(final_value, final_std),
            }
        )
        best = ranking[(ranking["dataset"].eq(dataset)) & (ranking["rank"].eq(1))]
        if not best.empty:
            brow = best.iloc[0]
            best_value = float(brow["value"])
            best_std = float(brow["std"]) if pd.notna(brow.get("std")) else np.nan
            best_model = brow["model"]
            best_source = brow["source"]
            if (direction == "lower" and final_value < best_value) or (
                direction == "higher" and final_value > best_value
            ):
                best_value = final_value
                best_std = final_std
                best_model = final_model
                best_source = final_source
            rows.append(
                {
                    "dataset": dataset,
                    "task_type": task_type,
                    "primary_metric": metric,
                    "direction": direction,
                    "category": "Best observed candidate",
                    "model": best_model,
                    "source": best_source,
                    "value": best_value,
                    "std": best_std,
                    "formatted": fmt_metric(best_value, best_std),
                }
            )

    table = pd.DataFrame(rows)
    table.to_csv(TABLE_DIR / "table2_moleculenet_main_long.csv", index=False)
    wide = table.pivot_table(
        index=["dataset", "task_type", "primary_metric"],
        columns="category",
        values="formatted",
        aggfunc="first",
    ).reset_index()
    wide.to_csv(TABLE_DIR / "table2_moleculenet_main.csv", index=False)
    return table, wide


def build_table3_tdc_official_admet() -> pd.DataFrame:
    selector = selector_summary(ROOT / "reports" / "validation_selector_tdc_admet" / "metrics_summary.csv")
    official = read_multi_header_csv(ROOT / "reports" / "tdc_official_admet_splits" / "metrics_summary.csv")
    tdc_fusion = pd.read_csv(TABLE32_PATH) if TABLE32_PATH.exists() else pd.DataFrame()
    rows: list[dict[str, object]] = []
    for dataset in TDC_ADMET:
        task_type = DATASETS[dataset].task_type
        metric, direction = primary_metric(task_type)
        srow = selector[selector["dataset"].eq(dataset)].iloc[0]
        selector_value, selector_std, _, _ = primary_from_row(srow)
        out: dict[str, object] = {
            "dataset": dataset,
            "task_type": task_type,
            "primary_metric": metric,
            "direction": direction,
            "selector_value": selector_value,
            "selector_std": selector_std,
            "selector_formatted": fmt_metric(selector_value, selector_std),
        }
        fusion_row = tdc_fusion[tdc_fusion["dataset"].eq(dataset)]
        if not fusion_row.empty:
            fusion_row = fusion_row.iloc[0]
            out["tdc_final_retained_value"] = float(fusion_row["retained_primary_mean"])
            out["tdc_final_retained_std"] = (
                float(fusion_row["retained_primary_std"])
                if pd.notna(fusion_row.get("retained_primary_std"))
                else np.nan
            )
            out["tdc_final_retained_formatted"] = fmt_metric(
                out["tdc_final_retained_value"],
                out["tdc_final_retained_std"],
            )
            out["tdc_final_retained_source"] = fusion_row["retained_source"]
            out["tdc_fusion_delta_vs_selector"] = fusion_row["delta_vs_tdc_selector"]
        else:
            out["tdc_final_retained_value"] = selector_value
            out["tdc_final_retained_std"] = selector_std
            out["tdc_final_retained_formatted"] = fmt_metric(selector_value, selector_std)
            out["tdc_final_retained_source"] = "tdc_validation_selector"
            out["tdc_fusion_delta_vs_selector"] = 0.0
        sub = official[official["dataset"].eq(dataset)]
        for model in ["lgbm_morgan", "rf_morgan"]:
            for split in ["random", "scaffold"]:
                m = sub[(sub["model"].eq(model)) & (sub["split_method"].eq(split))]
                if m.empty:
                    continue
                row = m.iloc[0]
                out[f"{model}_{split}_value"] = row[f"{metric}_mean"]
                out[f"{model}_{split}_std"] = row[f"{metric}_std"]
                out[f"{model}_{split}"] = fmt_metric(row[f"{metric}_mean"], row[f"{metric}_std"])
            if f"{model}_random_value" in out and f"{model}_scaffold_value" in out:
                if direction == "lower":
                    delta = float(out[f"{model}_scaffold_value"]) - float(out[f"{model}_random_value"])
                else:
                    delta = float(out[f"{model}_random_value"]) - float(out[f"{model}_scaffold_value"])
                out[f"{model}_random_to_scaffold_drop"] = delta
        rows.append(out)
    table = pd.DataFrame(rows)
    table.to_csv(TABLE_DIR / "table3_tdc_official_admet.csv", index=False)
    return table


def build_table4_split_realism() -> pd.DataFrame:
    frames = []
    for source, path in [
        ("MoleculeNet", ROOT / "reports" / "split_realism_lgbm" / "split_realism_slope.csv"),
        ("TDC ADMET", ROOT / "reports" / "split_realism_tdc_lgbm" / "split_realism_slope.csv"),
    ]:
        frame = pd.read_csv(path)
        frame.insert(0, "source", source)
        frames.append(frame)
    table = pd.concat(frames, ignore_index=True)
    value_cols = []
    for split in ["random", "scaffold", "structure"]:
        col = f"{split}_value"
        table[col] = np.where(
            table["metric"].eq("rmse"),
            table[f"{split}_rmse"],
            table[f"{split}_roc_auc"],
        )
        value_cols.append(col)
    table = table[
        [
            "source",
            "dataset",
            "task_type",
            "metric",
            *value_cols,
            "random_to_scaffold_drop",
            "scaffold_to_structure_drop",
        ]
    ]
    table.to_csv(TABLE_DIR / "table4_split_realism.csv", index=False)
    return table


def build_table5_ablation_significance() -> pd.DataFrame:
    ablation = pd.read_csv(ROOT / "reports" / "selector_ablation" / "family_ablation_aggregate.csv")
    sig = pd.read_csv(ROOT / "reports" / "significance_selector" / "significance_tests.csv")
    wtl = pd.read_csv(ROOT / "reports" / "significance_selector" / "win_tie_loss.csv")

    rows: list[dict[str, object]] = []
    for _, row in ablation.iterrows():
        rows.append(
            {
                "section": "family_ablation",
                "comparison": row["ablation"],
                "mean_positive_delta": row["mean_positive_delta"],
                "wins": row["full_better"],
                "ties": row["ties"],
                "losses": row["ablation_better"],
                "median_bootstrap_p": "",
                "median_wilcoxon_p": "",
                "decision_summary": "full selector vs ablated candidate family",
            }
        )

    grouped = (
        sig.groupby(["baseline_source", "baseline_model"], dropna=False)
        .agg(
            mean_positive_delta=("mean_positive_delta", "mean"),
            median_bootstrap_p=("bootstrap_p_two_sided", "median"),
            median_wilcoxon_p=("wilcoxon_p_two_sided", "median"),
        )
        .reset_index()
    )
    merged = wtl.merge(grouped, on=["baseline_source", "baseline_model"], how="left")
    merged = merged.sort_values(["net_win", "win"], ascending=False)
    for _, row in merged.head(20).iterrows():
        rows.append(
            {
                "section": "selector_vs_baseline",
                "comparison": f"{row['baseline_source']}::{row['baseline_model']}",
                "mean_positive_delta": row["mean_positive_delta"],
                "wins": row["win"],
                "ties": row["tie"],
                "losses": row["loss"],
                "median_bootstrap_p": row["median_bootstrap_p"],
                "median_wilcoxon_p": row["median_wilcoxon_p"],
                "decision_summary": f"net_win={row['net_win']}",
            }
        )
    table = pd.DataFrame(rows)
    table.to_csv(TABLE_DIR / "table5_ablation_significance.csv", index=False)
    return table


def build_table6_reliability_ad() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    recon = pd.read_csv(ROOT / "reports" / "reconstruction_ood" / "reconstruction_ood_metrics.csv")
    for score, sub in recon.groupby("score"):
        rows.append(
            {
                "family": "reconstruction_unfamiliarity",
                "score": score,
                "n_rows": len(sub),
                "mean_spearman_abs_error": sub["spearman_abs_error"].mean(),
                "mean_risk_coverage_auc": sub["risk_coverage_auc"].mean(),
                "mean_top10pct_high_error_enrichment": sub["top10pct_high_error_enrichment"].mean(),
            }
        )
    uq = pd.read_csv(ROOT / "reports" / "unique_uq_plus_descriptor_motif" / "uq_score_metrics.csv")
    for score, sub in uq.groupby("uq_score"):
        rows.append(
            {
                "family": "unique_style_uq",
                "score": score,
                "n_rows": len(sub),
                "mean_spearman_abs_error": sub["spearman_abs_error"].mean(),
                "mean_risk_coverage_auc": sub["risk_coverage_auc"].mean(),
                "mean_top10pct_high_error_enrichment": sub["top10pct_high_error_enrichment"].mean(),
            }
        )
    conformal = pd.read_csv(ROOT / "reports" / "conformal_activity" / "conformal_summary.csv")
    for task_type, sub in conformal.groupby("task_type"):
        rows.append(
            {
                "family": "conformal_prediction",
                "score": f"{task_type}_coverage",
                "n_rows": len(sub),
                "mean_spearman_abs_error": "",
                "mean_risk_coverage_auc": sub["coverage"].mean(),
                "mean_top10pct_high_error_enrichment": sub["avg_set_size"].mean()
                if task_type == "classification"
                else sub["mean_width"].mean(),
            }
        )
    table = pd.DataFrame(rows)
    table.to_csv(TABLE_DIR / "table6_reliability_ad.csv", index=False)
    return table


def build_table7_efficiency() -> pd.DataFrame:
    table = pd.read_csv(ROOT / "reports" / "efficiency" / "efficiency_compact.csv")
    table.to_csv(TABLE_DIR / "table7_efficiency.csv", index=False)
    return table


def draw_framework() -> None:
    fig, ax = plt.subplots(figsize=(13.5, 7.2))
    ax.axis("off")
    boxes = [
        (0.03, 0.55, 0.16, 0.22, "Molecular input\nSMILES / graph"),
        (0.27, 0.62, 0.20, 0.16, "Representation views\nFingerprints\nRDKit descriptors\nMolecular graphs"),
        (0.27, 0.36, 0.20, 0.16, "Frozen encoders\nChemBERTa-MLM\nMoLFormer"),
        (0.55, 0.68, 0.18, 0.13, "Expert pool\nRF/XGB/LGBM/ET"),
        (0.55, 0.51, 0.18, 0.13, "Neural experts\nGIN / D-MPNN\nChemprop"),
        (0.55, 0.34, 0.18, 0.13, "Motif experts\nBRICS / Murcko\nFunctional groups"),
        (0.80, 0.57, 0.16, 0.18, "Validation-only\nselector\nstack / adaptive /\nconsensus"),
        (0.80, 0.28, 0.16, 0.18, "Reliability output\nuncertainty\nAD / unfamiliarity\nmotif attribution"),
    ]
    for x, y, w, h, label in boxes:
        ax.add_patch(plt.Rectangle((x, y), w, h, fill=False, linewidth=1.7, edgecolor="#1f2937"))
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontsize=10)
    arrows = [
        ((0.19, 0.66), (0.27, 0.70)),
        ((0.19, 0.62), (0.27, 0.44)),
        ((0.47, 0.70), (0.55, 0.74)),
        ((0.47, 0.44), (0.55, 0.57)),
        ((0.47, 0.44), (0.55, 0.40)),
        ((0.73, 0.74), (0.80, 0.66)),
        ((0.73, 0.57), (0.80, 0.66)),
        ((0.73, 0.40), (0.80, 0.66)),
        ((0.88, 0.57), (0.88, 0.46)),
    ]
    for start, end in arrows:
        ax.annotate("", xy=end, xytext=start, arrowprops=dict(arrowstyle="->", lw=1.4, color="#374151"))
    ax.text(
        0.5,
        0.08,
        "Evaluation: MoleculeNet + TDC ADMET + official splits + random/scaffold/structure-separated splits + "
        "low-similarity subsets + MoleculeACE activity cliffs",
        ha="center",
        fontsize=10,
    )
    ax.set_title("Figure 1. FZYC-Mol validation-selected reliability framework", fontsize=14, pad=12)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig1_framework_overview.png", dpi=300)
    fig.savefig(FIG_DIR / "fig1_framework_overview.svg")
    plt.close(fig)


def draw_main_performance_heatmap(table2_long: pd.DataFrame) -> None:
    frame = table2_long[~table2_long["category"].eq("Best observed candidate")].copy()
    ranks = []
    for dataset, sub in frame.groupby("dataset"):
        direction = sub["direction"].iloc[0]
        ascending = direction == "lower"
        sub = sub.copy()
        sub["rank"] = sub["value"].rank(method="min", ascending=ascending)
        ranks.append(sub)
    ranked = pd.concat(ranks, ignore_index=True)
    pivot = ranked.pivot_table(index="dataset", columns="category", values="rank", aggfunc="min")
    fig, ax = plt.subplots(figsize=(12, 5.8))
    im = ax.imshow(pivot.values, cmap="viridis_r", aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=35, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            val = pivot.iloc[i, j]
            if pd.notna(val):
                ax.text(j, i, f"{val:.0f}", ha="center", va="center", color="white" if val <= 3 else "black")
    ax.set_title("Figure 2. Model-family rank across MoleculeNet endpoints")
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Rank (1 = best within row)")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig2_main_performance_heatmap.png", dpi=300)
    fig.savefig(FIG_DIR / "fig2_main_performance_heatmap.svg")
    plt.close(fig)


def draw_split_realism(table4: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), sharex=True)
    panels = [
        ("MoleculeNet", "regression", axes[0, 0]),
        ("MoleculeNet", "classification", axes[0, 1]),
        ("TDC ADMET", "regression", axes[1, 0]),
        ("TDC ADMET", "classification", axes[1, 1]),
    ]
    x = np.arange(3)
    labels = ["random", "scaffold", "structure"]
    for source, task_type, ax in panels:
        sub = table4[(table4["source"].eq(source)) & (table4["task_type"].eq(task_type))]
        for _, row in sub.iterrows():
            y = [row["random_value"], row["scaffold_value"], row["structure_value"]]
            ax.plot(x, y, marker="o", label=row["dataset"])
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        metric = "RMSE" if task_type == "regression" else "ROC-AUC"
        ax.set_ylabel(metric)
        ax.set_title(f"{source} {task_type}")
        ax.grid(True, alpha=0.25)
        if not sub.empty:
            ax.legend(fontsize=7)
    fig.suptitle("Figure 3. Split-realism degradation from random to structure-separated splits", y=1.02)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig3_split_realism_slope.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIG_DIR / "fig3_split_realism_slope.svg", bbox_inches="tight")
    plt.close(fig)


def draw_uncertainty_ad(table6: pd.DataFrame) -> None:
    subset = table6[table6["family"].isin(["reconstruction_unfamiliarity", "unique_style_uq"])].copy()
    subset = subset[pd.to_numeric(subset["mean_spearman_abs_error"], errors="coerce").notna()]
    subset["mean_spearman_abs_error"] = subset["mean_spearman_abs_error"].astype(float)
    subset = subset.sort_values("mean_spearman_abs_error", ascending=False).head(12)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))
    axes[0].barh(subset["score"], subset["mean_spearman_abs_error"], color="#2563eb")
    axes[0].invert_yaxis()
    axes[0].set_xlabel("Mean Spearman with absolute error")
    axes[0].set_title("Error-risk ranking")
    axes[1].barh(subset["score"], subset["mean_top10pct_high_error_enrichment"].astype(float), color="#059669")
    axes[1].invert_yaxis()
    axes[1].set_xlabel("Top-10% high-error enrichment")
    axes[1].set_title("High-error enrichment")
    fig.suptitle("Figure 4. Uncertainty and applicability-domain reliability signals", y=1.03)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig4_uncertainty_ad_reliability.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIG_DIR / "fig4_uncertainty_ad_reliability.svg", bbox_inches="tight")
    plt.close(fig)


def draw_cliff_enrichment() -> None:
    cliff = pd.read_csv(ROOT / "reports" / "conformal_activity" / "activity_cliff_summary.csv")
    enrich = pd.read_csv(ROOT / "reports" / "classification_enrichment" / "classification_enrichment_raw.csv")
    enrich = enrich[enrich["source"].eq("validation_selector_expanded")]
    enrich_summary = enrich.groupby("dataset", as_index=False)[["ef1", "ef5", "bedroc20"]].mean()
    cliff_summary = cliff.groupby("dataset", as_index=False).agg(
        direction_accuracy=("direction_accuracy", "mean"),
        delta_mae=("delta_mae", "mean"),
        n_cliffs=("n_cliffs", "sum"),
    )
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    enrich_summary.set_index("dataset")[["ef1", "ef5"]].plot(kind="bar", ax=axes[0])
    axes[0].set_ylabel("Enrichment factor")
    axes[0].set_title("Early recognition")
    axes[0].tick_params(axis="x", rotation=35)
    cliff_plot = cliff_summary[cliff_summary["n_cliffs"] > 0].set_index("dataset")
    if not cliff_plot.empty:
        cliff_plot[["direction_accuracy"]].plot(kind="bar", ax=axes[1], legend=False, color="#dc2626")
    axes[1].set_ylim(0, 1.05)
    axes[1].set_ylabel("Direction accuracy")
    axes[1].set_title("Activity-cliff pair direction")
    axes[1].tick_params(axis="x", rotation=35)
    fig.suptitle("Figure 5. Screening enrichment and activity-cliff behavior", y=1.03)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig5_cliff_enrichment.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIG_DIR / "fig5_cliff_enrichment.svg", bbox_inches="tight")
    plt.close(fig)


def draw_motif_attribution() -> None:
    motif = pd.read_csv(ROOT / "reports" / "motif_attribution" / "motif_feature_importance.csv")
    avg = (
        motif.groupby(["dataset", "feature", "feature_family"], as_index=False)
        .agg(importance=("importance", "mean"), direction=("direction", "mean"))
        .sort_values(["dataset", "importance"], ascending=[True, False])
    )
    datasets = ["bbbp", "bace", "clintox"]
    fig, axes = plt.subplots(1, 3, figsize=(16, 6))
    for ax, dataset in zip(axes, datasets):
        sub = avg[avg["dataset"].eq(dataset)].head(10).copy()
        labels = sub["feature"].str.replace("FG::", "", regex=False).str.replace("BRICS::", "", regex=False)
        colors = np.where(sub["direction"] >= 0, "#2563eb", "#dc2626")
        ax.barh(labels, sub["importance"], color=colors)
        ax.invert_yaxis()
        ax.set_title(dataset.upper())
        ax.set_xlabel("Mean importance")
    fig.suptitle("Figure 6. Motif attribution for representative classification endpoints", y=1.02)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig6_motif_attribution.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIG_DIR / "fig6_motif_attribution.svg", bbox_inches="tight")
    plt.close(fig)


def draw_efficiency(table7: pd.DataFrame) -> None:
    plot = table7.copy()
    plot["mean_fit_seconds"] = pd.to_numeric(plot["mean_fit_seconds"], errors="coerce")
    plot["mean_predict_seconds"] = pd.to_numeric(plot["mean_predict_seconds"], errors="coerce")
    plot = plot.dropna(subset=["mean_fit_seconds", "mean_predict_seconds"])
    labels = plot["report"] + "\n" + plot["model_family"].str.replace(" baseline", "", regex=False)
    x = np.arange(len(plot))
    width = 0.38
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(x - width / 2, plot["mean_fit_seconds"], width, label="Fit seconds", color="#7c3aed")
    ax.bar(x + width / 2, plot["mean_predict_seconds"], width, label="Predict seconds", color="#0891b2")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Seconds")
    ax.set_title("Figure 7. CPU efficiency of practical baseline families")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig7_efficiency.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIG_DIR / "fig7_efficiency.svg", bbox_inches="tight")
    plt.close(fig)


def write_manifest(tables: dict[str, pd.DataFrame]) -> None:
    lines = ["# Manuscript Artifact Manifest", ""]
    lines.append("Generated tables:")
    for name, frame in tables.items():
        lines.append(f"- `{name}`: {len(frame)} rows x {len(frame.columns)} columns")
    lines.append("")
    lines.append("Generated figures:")
    for path in sorted(FIG_DIR.glob("fig*.png")):
        lines.append(f"- `{path.name}`")
    (ROOT / "reports" / "manuscript_artifacts_manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ensure_dirs()
    tables: dict[str, pd.DataFrame] = {}
    tables["table1_dataset_protocol.csv"] = build_table1_dataset_protocol()
    table2_long, table2_wide = build_table2_moleculenet_main()
    tables["table2_moleculenet_main_long.csv"] = table2_long
    tables["table2_moleculenet_main.csv"] = table2_wide
    tables["table3_tdc_official_admet.csv"] = build_table3_tdc_official_admet()
    tables["table4_split_realism.csv"] = build_table4_split_realism()
    tables["table5_ablation_significance.csv"] = build_table5_ablation_significance()
    tables["table6_reliability_ad.csv"] = build_table6_reliability_ad()
    tables["table7_efficiency.csv"] = build_table7_efficiency()

    draw_framework()
    draw_main_performance_heatmap(table2_long)
    draw_split_realism(tables["table4_split_realism.csv"])
    draw_uncertainty_ad(tables["table6_reliability_ad.csv"])
    draw_cliff_enrichment()
    draw_motif_attribution()
    draw_efficiency(tables["table7_efficiency.csv"])
    write_manifest(tables)
    print(f"Generated manuscript tables in {TABLE_DIR}")
    print(f"Generated manuscript figures in {FIG_DIR}")


if __name__ == "__main__":
    main()
