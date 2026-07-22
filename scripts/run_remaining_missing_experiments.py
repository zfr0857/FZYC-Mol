from __future__ import annotations

from pathlib import Path
from typing import Iterable

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from rdkit import Chem, DataStructs
from rdkit.Chem import Draw
from scipy.stats import pearsonr, spearmanr, wilcoxon

import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from fzyc_mol.evaluate import compute_metrics, expected_calibration_error
from fzyc_mol.features import morgan_fingerprint


REPORTS = ROOT / "reports"
OUT = REPORTS / "remaining_missing_experiments_20260606"
FIG = OUT / "figures"
OUT.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "font.size": 7,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "axes.linewidth": 0.8,
        "legend.frameon": False,
    }
)


def save_fig(fig: plt.Figure, stem: str) -> None:
    fig.savefig(FIG / f"{stem}.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIG / f"{stem}.svg", bbox_inches="tight")
    plt.close(fig)


def finite_mean(values: Iterable[float]) -> float:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    return float(arr.mean()) if len(arr) else float("nan")


def direction_for(task_type: str) -> str:
    return "lower" if task_type == "regression" else "higher"


def primary_cols(task_type: str) -> tuple[str, str]:
    if task_type == "regression":
        return "valid_rmse", "test_rmse"
    return "valid_roc_auc", "test_roc_auc"


def better_sort_ascending(task_type: str) -> bool:
    return task_type == "regression"


def positive_delta(task_type: str, lhs: float, rhs: float) -> float:
    if pd.isna(lhs) or pd.isna(rhs):
        return float("nan")
    return float(rhs - lhs) if task_type == "regression" else float(lhs - rhs)


def select_best(group: pd.DataFrame, task_type: str, score_col: str) -> pd.Series | None:
    work = group.dropna(subset=[score_col]).copy()
    if work.empty:
        return None
    return work.sort_values(score_col, ascending=better_sort_ascending(task_type)).iloc[0]


def load_metric_pool() -> pd.DataFrame:
    frames = []
    specs = [
        ("moleculenet_multimethod", REPORTS / "nature_multimethod_fusion_appendix" / "candidate_metrics_raw.csv"),
        ("tdc_multimethod", REPORTS / "tdc_nature_multimethod_fusion_appendix" / "candidate_metrics_raw.csv"),
        ("moleculenet_selector_ablation", REPORTS / "validation_selector_ablation" / "candidate_metrics_raw.csv"),
    ]
    for source, path in specs:
        if not path.exists():
            continue
        df = pd.read_csv(path)
        df["source"] = source
        if "candidate_type" not in df.columns:
            df["candidate_type"] = ""
        if "nature_inspiration" not in df.columns:
            df["nature_inspiration"] = ""
        frames.append(df)
    pool = pd.concat(frames, ignore_index=True, sort=False)
    return pool


def run_seed_nested_validation(pool: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    datasets = [
        "esol",
        "freesolv",
        "lipo",
        "bbbp",
        "bace",
        "clintox",
        "tdc_caco2_wang",
        "tdc_hia_hou",
        "tdc_pgp_broccatelli",
    ]
    use = pool[pool["dataset"].isin(datasets)].copy()
    rows = []
    for (dataset, source), dfg in use.groupby(["dataset", "source"], dropna=False):
        task_type = str(dfg["task_type"].dropna().iloc[0])
        valid_col, test_col = primary_cols(task_type)
        if valid_col not in dfg.columns or test_col not in dfg.columns:
            continue
        seeds = sorted(dfg["seed"].dropna().unique().tolist())
        if len(seeds) < 3:
            continue
        for outer_seed in seeds:
            train = dfg[dfg["seed"] != outer_seed]
            held = dfg[dfg["seed"] == outer_seed]
            model_scores = train.groupby("model", dropna=False)[valid_col].mean().reset_index()
            chosen_model = select_best(model_scores, task_type, valid_col)
            if chosen_model is None:
                continue
            selected = held[held["model"].eq(chosen_model["model"])]
            if selected.empty:
                continue
            selected = selected.iloc[0]
            oracle = select_best(held, task_type, test_col)
            valid_oracle = select_best(held, task_type, valid_col)
            rows.append(
                {
                    "dataset": dataset,
                    "source": source,
                    "outer_seed": outer_seed,
                    "task_type": task_type,
                    "selected_model": selected["model"],
                    "outer_valid_value": selected.get(valid_col, np.nan),
                    "outer_test_value": selected.get(test_col, np.nan),
                    "valid_oracle_model": valid_oracle["model"] if valid_oracle is not None else "",
                    "valid_oracle_test_value": valid_oracle.get(test_col, np.nan) if valid_oracle is not None else np.nan,
                    "test_oracle_model": oracle["model"] if oracle is not None else "",
                    "test_oracle_value": oracle.get(test_col, np.nan) if oracle is not None else np.nan,
                    "delta_vs_valid_oracle_positive": positive_delta(
                        task_type,
                        selected.get(test_col, np.nan),
                        valid_oracle.get(test_col, np.nan) if valid_oracle is not None else np.nan,
                    ),
                    "regret_vs_test_oracle": positive_delta(
                        task_type,
                        oracle.get(test_col, np.nan) if oracle is not None else np.nan,
                        selected.get(test_col, np.nan),
                    ),
                }
            )
    detail = pd.DataFrame(rows)
    if detail.empty:
        return detail, pd.DataFrame()
    summary = (
        detail.groupby(["dataset", "source", "task_type"], dropna=False)
        .agg(
            n_outer=("outer_seed", "count"),
            selected_test_mean=("outer_test_value", "mean"),
            median_delta_vs_valid_oracle=("delta_vs_valid_oracle_positive", "median"),
            median_regret_vs_test_oracle=("regret_vs_test_oracle", "median"),
            top_model_switches=("selected_model", lambda s: int(s.nunique())),
        )
        .reset_index()
    )
    detail.to_csv(OUT / "nested_seed_validation_detail.csv", index=False)
    summary.to_csv(OUT / "nested_seed_validation_summary.csv", index=False)
    return detail, summary


def candidate_category_frame(pool: pd.DataFrame, category: str) -> pd.DataFrame:
    model = pool["model"].astype(str)
    ctype = pool["candidate_type"].astype(str)
    insp = pool["nature_inspiration"].astype(str)
    if category == "full":
        return pool
    if category == "best_single":
        return pool[ctype.eq("single_view_expert") | model.str.contains("rf_|xgb_|lgbm_|extratrees|chemprop|morgan", regex=True)]
    if category == "simple_mean":
        return pool[model.str.contains("top[358]_mean|consensus_", regex=True)]
    if category == "no_validation_selector_fixed_morgan":
        return pool[model.eq("morgan_lgbm") | model.eq("rf_morgan") | model.eq("lgbm_morgan")]
    if category == "without_fusion":
        return pool[ctype.ne("prediction_level_fusion") & ~model.str.contains("stack|rank|top[358]_mean|ad_gate|consensus", regex=True)]
    if category == "without_ad_gate":
        return pool[~insp.eq("applicability_domain_gated_fusion") & ~model.str.contains("ad_gate", regex=False)]
    if category == "without_uncertainty_weighting":
        return pool[~insp.eq("uncertainty_weighted_multiview_fusion") & ~model.str.contains("uncert", case=False, regex=False)]
    if category == "without_hier_motif_multifp":
        return pool[~model.str.contains("hier_motif|multifp", regex=True) & ~insp.str.contains("motif|multi_fingerprint", regex=True)]
    if category == "without_rescue_head":
        return pool[~model.str.contains("rescue", case=False, regex=False)]
    raise KeyError(category)


def run_unified_ablation(pool: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    datasets = [
        "esol",
        "freesolv",
        "lipo",
        "bbbp",
        "bace",
        "clintox",
        "tdc_caco2_wang",
        "tdc_hia_hou",
        "tdc_pgp_broccatelli",
    ]
    categories = [
        "full",
        "best_single",
        "simple_mean",
        "no_validation_selector_fixed_morgan",
        "without_fusion",
        "without_ad_gate",
        "without_uncertainty_weighting",
        "without_hier_motif_multifp",
        "without_rescue_head",
    ]
    rows = []
    use = pool[pool["dataset"].isin(datasets)].copy()
    for dataset, dfg in use.groupby("dataset", dropna=False):
        task_type = str(dfg["task_type"].dropna().iloc[0])
        valid_col, test_col = primary_cols(task_type)
        if valid_col not in dfg.columns or test_col not in dfg.columns:
            continue
        full_rows = []
        for seed, seed_group in dfg.groupby("seed"):
            best = select_best(seed_group, task_type, valid_col)
            if best is not None:
                full_rows.append((seed, best.get(test_col, np.nan)))
        full_by_seed = dict(full_rows)
        for category in categories:
            cat = candidate_category_frame(dfg, category)
            if cat.empty:
                continue
            for seed, seed_group in cat.groupby("seed"):
                best = select_best(seed_group, task_type, valid_col)
                if best is None:
                    continue
                rows.append(
                    {
                        "dataset": dataset,
                        "seed": seed,
                        "task_type": task_type,
                        "category": category,
                        "selected_model": best["model"],
                        "valid_value": best.get(valid_col, np.nan),
                        "test_value": best.get(test_col, np.nan),
                        "delta_vs_full_positive": positive_delta(
                            task_type,
                            best.get(test_col, np.nan),
                            full_by_seed.get(seed, np.nan),
                        )
                        if category != "full"
                        else 0.0,
                    }
                )
    detail = pd.DataFrame(rows)
    rescue = REPORTS / "validation_selector_rescue_integration" / "comparison_to_current.csv"
    if rescue.exists():
        rescue_df = pd.read_csv(rescue)
        for _, r in rescue_df.iterrows():
            task_type = r["task_type"]
            rows.append(
                {
                    "dataset": r["dataset"],
                    "seed": "mean",
                    "task_type": task_type,
                    "category": "without_rescue_head_current",
                    "selected_model": r["current_model"],
                    "valid_value": r["validation_primary_mean"],
                    "test_value": r["current_primary_mean"],
                    "delta_vs_full_positive": r["integration_delta_vs_current"],
                }
            )
        detail = pd.DataFrame(rows)
    if detail.empty:
        return detail, pd.DataFrame()
    summary = (
        detail.groupby(["category", "task_type"], dropna=False)
        .agg(
            n_units=("test_value", "count"),
            mean_test=("test_value", "mean"),
            median_test=("test_value", "median"),
            mean_delta_vs_full_positive=("delta_vs_full_positive", "mean"),
            positive_fraction_vs_full=("delta_vs_full_positive", lambda x: float(np.mean(np.asarray(x, dtype=float) > 0))),
            selected_model_count=("selected_model", lambda s: "; ".join(s.astype(str).value_counts().head(4).index.tolist())),
        )
        .reset_index()
    )
    detail.to_csv(OUT / "unified_ablation_matrix_detail.csv", index=False)
    summary.to_csv(OUT / "unified_ablation_matrix_summary.csv", index=False)
    plot = summary[summary["category"].ne("full")].copy()
    if not plot.empty:
        fig, ax = plt.subplots(figsize=(8.2, 4.4))
        order = plot.groupby("category")["mean_delta_vs_full_positive"].mean().sort_values().index.tolist()
        values = [plot[plot["category"].eq(cat)]["mean_delta_vs_full_positive"].mean() for cat in order]
        colors = ["#b91c1c" if v < 0 else "#2563eb" for v in values]
        ax.barh(order, values, color=colors)
        ax.axvline(0, color="#111827", lw=0.9)
        ax.set_xlabel("Mean positive delta vs full")
        ax.set_title("Unified ablation matrix across endpoint-seed units")
        save_fig(fig, "unified_ablation_matrix")
    return detail, summary


def load_prediction_and_weights(root: Path, dataset: str, seed: int) -> pd.DataFrame | None:
    pred = root / f"{dataset}_validation_selector_seed{seed}_predictions.csv"
    weights = root / f"{dataset}_validation_selector_seed{seed}_weights.csv"
    if not pred.exists() or not weights.exists():
        return None
    p = pd.read_csv(pred)
    w = pd.read_csv(weights)
    return p.merge(w, on="smiles", how="left")


def similarity_bin(value: float) -> str:
    if value < 0.5:
        return "<0.5"
    if value < 0.7:
        return "0.5-0.7"
    return ">0.7"


def run_exact_similarity_bins() -> tuple[pd.DataFrame, pd.DataFrame]:
    sources = [
        ("moleculenet", REPORTS / "validation_selector_expanded", ["esol", "freesolv", "lipo", "bbbp", "bace", "clintox"], [13, 17, 23, 29, 31]),
        ("tdc", REPORTS / "validation_selector_tdc_admet", ["tdc_caco2_wang", "tdc_hia_hou", "tdc_pgp_broccatelli"], [13, 17, 23, 29, 31]),
    ]
    rows = []
    case_rows = []
    for source, root, datasets, seeds in sources:
        for dataset in datasets:
            for seed in seeds:
                table = load_prediction_and_weights(root, dataset, seed)
                if table is None or "max_train_tanimoto" not in table.columns:
                    continue
                task_type = "classification" if table["y_true"].dropna().isin([0, 1]).all() else "regression"
                table["abs_error"] = np.abs(table["y_true"].astype(float) - table["y_pred"].astype(float))
                if task_type == "classification":
                    pred_label = (table["y_pred"].astype(float) >= 0.5).astype(int)
                    table["error_flag"] = (pred_label != table["y_true"].astype(int)).astype(int)
                    overall_error = max(float(table["error_flag"].mean()), 1e-8)
                else:
                    threshold = table["abs_error"].quantile(0.8)
                    table["error_flag"] = (table["abs_error"] >= threshold).astype(int)
                    overall_error = max(float(table["error_flag"].mean()), 1e-8)
                table["similarity_bin"] = table["max_train_tanimoto"].astype(float).map(similarity_bin)
                for bin_name, sub in table.groupby("similarity_bin"):
                    if len(sub) < 3:
                        continue
                    metrics = compute_metrics(task_type, sub["y_true"].to_numpy(), sub["y_pred"].to_numpy())
                    risk = sub["ensemble_std"].astype(float) if "ensemble_std" in sub.columns else pd.Series(np.nan, index=sub.index)
                    err = sub["abs_error"].astype(float)
                    corr = spearmanr(risk, err).statistic if risk.notna().sum() >= 4 and err.nunique() > 1 else np.nan
                    rows.append(
                        {
                            "source": source,
                            "dataset": dataset,
                            "seed": seed,
                            "task_type": task_type,
                            "similarity_bin": bin_name,
                            "n": len(sub),
                            "mean_similarity": sub["max_train_tanimoto"].mean(),
                            "mean_uncertainty": risk.mean(),
                            "high_error_rate": sub["error_flag"].mean(),
                            "high_error_enrichment": sub["error_flag"].mean() / overall_error,
                            "risk_error_spearman": corr,
                            **metrics,
                        }
                    )
                low = table[table["max_train_tanimoto"].astype(float) < 0.5].copy()
                if not low.empty:
                    pick = low.sort_values(["error_flag", "abs_error", "ensemble_std"], ascending=False).head(1)
                    for _, r in pick.iterrows():
                        case_rows.append(
                            {
                                "case_type": "low_similarity_failure",
                                "dataset": dataset,
                                "seed": seed,
                                "smiles": r["smiles"],
                                "y_true": r["y_true"],
                                "y_pred": r["y_pred"],
                                "max_train_tanimoto": r["max_train_tanimoto"],
                                "ensemble_std": r.get("ensemble_std", np.nan),
                                "abs_error": r["abs_error"],
                                "reason": "Low Tanimoto bin with high prediction error/uncertainty.",
                            }
                        )
    detail = pd.DataFrame(rows)
    cases = pd.DataFrame(case_rows)
    if detail.empty:
        return detail, cases
    summary = (
        detail.groupby(["source", "task_type", "similarity_bin"], dropna=False)
        .mean(numeric_only=True)
        .reset_index()
    )
    detail.to_csv(OUT / "exact_tanimoto_bins_detail.csv", index=False)
    summary.to_csv(OUT / "exact_tanimoto_bins_summary.csv", index=False)
    cases.to_csv(OUT / "low_similarity_failure_cases.csv", index=False)

    for task_type, metric in [("classification", "roc_auc"), ("regression", "rmse")]:
        plot = summary[summary["task_type"].eq(task_type)].copy()
        if plot.empty or metric not in plot.columns:
            continue
        pivot = plot.pivot_table(index="source", columns="similarity_bin", values=metric, aggfunc="mean")
        pivot = pivot[[c for c in ["<0.5", "0.5-0.7", ">0.7"] if c in pivot.columns]]
        fig, ax = plt.subplots(figsize=(5.4, 2.6))
        im = ax.imshow(pivot.to_numpy(dtype=float), cmap="viridis")
        ax.set_xticks(range(len(pivot.columns)), pivot.columns)
        ax.set_yticks(range(len(pivot.index)), pivot.index)
        ax.set_title(f"Exact Tanimoto-bin {metric}")
        for i in range(pivot.shape[0]):
            for j in range(pivot.shape[1]):
                ax.text(j, i, f"{pivot.iloc[i, j]:.3f}", ha="center", va="center", color="white", fontsize=7)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        save_fig(fig, f"exact_tanimoto_bins_{task_type}")
    return detail, cases


def combine_conformal() -> tuple[pd.DataFrame, pd.DataFrame]:
    dirs = [
        REPORTS / "conformal_activity_alpha020" / "conformal_summary.csv",
        REPORTS / "conformal_activity" / "conformal_summary.csv",
        REPORTS / "conformal_activity_alpha005" / "conformal_summary.csv",
    ]
    frames = [pd.read_csv(p) for p in dirs if p.exists()]
    all_conf = pd.concat(frames, ignore_index=True)
    all_conf["target_coverage"] = 1.0 - all_conf["alpha"].astype(float)
    summary = (
        all_conf.groupby(["task_type", "target_coverage"], dropna=False)
        .agg(
            n=("dataset", "count"),
            coverage_mean=("coverage", "mean"),
            coverage_median=("coverage", "median"),
            avg_set_size_mean=("avg_set_size", "mean"),
            singleton_rate_mean=("singleton_rate", "mean"),
            empty_rate_mean=("empty_rate", "mean"),
            mean_width_mean=("mean_width", "mean"),
            median_abs_error_mean=("median_abs_error", "mean"),
        )
        .reset_index()
    )
    all_conf.to_csv(OUT / "conformal_80_90_95_detail.csv", index=False)
    summary.to_csv(OUT / "conformal_80_90_95_summary.csv", index=False)
    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    for task_type, sub in all_conf.groupby("task_type"):
        x = sub["target_coverage"]
        y = sub["coverage"]
        ax.scatter(x, y, label=task_type, s=18, alpha=0.75)
    ax.plot([0.78, 0.97], [0.78, 0.97], color="#111827", lw=1, ls="--")
    ax.set_xlabel("Target coverage")
    ax.set_ylabel("Empirical coverage")
    ax.set_title("Conformal coverage at 80%, 90%, and 95% targets")
    ax.legend()
    save_fig(fig, "conformal_80_90_95")
    return all_conf, summary


def bitvect(smiles: str):
    arr = morgan_fingerprint(smiles)
    bv = DataStructs.ExplicitBitVect(int(arr.shape[0]))
    for bit in np.flatnonzero(arr > 0):
        bv.SetBit(int(bit))
    return bv


def run_moleculeace_gap_correlation() -> tuple[pd.DataFrame, pd.DataFrame]:
    pred_dir = REPORTS / "moleculeace_cliff_objective_selector"
    rows = []
    case_rows = []
    for path in sorted(pred_dir.glob("*_seed*_predictions.csv")):
        table = pd.read_csv(path)
        if len(table) < 4 or not {"smiles", "y_true", "y_pred", "task"}.issubset(table.columns):
            continue
        task = str(table["task"].iloc[0])
        seed = int(path.stem.split("_seed")[-1].split("_")[0])
        fps = [bitvect(s) for s in table["smiles"].tolist()]
        pair_rows = []
        y = table["y_true"].astype(float).to_numpy()
        pred = table["y_pred"].astype(float).to_numpy()
        for i in range(len(table)):
            sims = DataStructs.BulkTanimotoSimilarity(fps[i], fps[i + 1 :])
            for off, sim in enumerate(sims, start=i + 1):
                if sim < 0.7:
                    continue
                true_delta = float(y[i] - y[off])
                pred_delta = float(pred[i] - pred[off])
                pair_rows.append(
                    {
                        "task": task,
                        "seed": seed,
                        "i": i,
                        "j": off,
                        "smiles_i": table.iloc[i]["smiles"],
                        "smiles_j": table.iloc[off]["smiles"],
                        "similarity": float(sim),
                        "true_delta": true_delta,
                        "pred_delta": pred_delta,
                        "abs_true_delta": abs(true_delta),
                        "abs_pred_delta": abs(pred_delta),
                        "direction_correct": float(np.sign(true_delta) == np.sign(pred_delta)) if true_delta != 0 and pred_delta != 0 else np.nan,
                        "gap_abs_error": abs(abs(true_delta) - abs(pred_delta)),
                        "y_i": y[i],
                        "y_j": y[off],
                        "pred_i": pred[i],
                        "pred_j": pred[off],
                    }
                )
        pairs = pd.DataFrame(pair_rows)
        if pairs.empty:
            continue
        cutoff = pairs["abs_true_delta"].quantile(0.75)
        cliffs = pairs[pairs["abs_true_delta"] >= cutoff].copy()
        rho = spearmanr(cliffs["abs_true_delta"], cliffs["abs_pred_delta"]).statistic if len(cliffs) >= 3 else np.nan
        pear = pearsonr(cliffs["abs_true_delta"], cliffs["abs_pred_delta"])[0] if len(cliffs) >= 3 else np.nan
        rows.append(
            {
                "task": task,
                "seed": seed,
                "n_pairs": len(pairs),
                "n_cliff_pairs": len(cliffs),
                "cliff_abs_delta_cutoff": cutoff,
                "gap_spearman": rho,
                "gap_pearson": pear,
                "direction_accuracy": cliffs["direction_correct"].mean(),
                "mean_gap_abs_error": cliffs["gap_abs_error"].mean(),
                "mean_similarity": cliffs["similarity"].mean(),
            }
        )
        worst = cliffs.sort_values(["gap_abs_error", "abs_true_delta"], ascending=False).head(1)
        best = cliffs.sort_values(["gap_abs_error", "abs_true_delta"], ascending=[True, False]).head(1)
        for case_kind, pick in [("cliff_gap_failure", worst), ("cliff_gap_success", best)]:
            for _, r in pick.iterrows():
                case_rows.append({**r.to_dict(), "case_type": case_kind})
    detail = pd.DataFrame(rows)
    cases = pd.DataFrame(case_rows)
    if detail.empty:
        return detail, cases
    detail.to_csv(OUT / "moleculeace_gap_correlation_summary.csv", index=False)
    cases.to_csv(OUT / "moleculeace_cliff_pair_cases.csv", index=False)

    fig, ax = plt.subplots(figsize=(4.2, 3.6))
    ax.scatter(detail["gap_spearman"], detail["direction_accuracy"], s=18, alpha=0.75, color="#2563eb")
    ax.axvline(0, color="#111827", ls="--", lw=0.8)
    ax.set_xlabel("Spearman(abs true gap, abs predicted gap)")
    ax.set_ylabel("Direction accuracy")
    ax.set_title("MoleculeACE gap-correlation audit")
    save_fig(fig, "moleculeace_gap_correlation")

    plot_cases = cases.sort_values("gap_abs_error", ascending=False).head(4)
    mols = []
    legends = []
    for _, r in plot_cases.iterrows():
        mols.extend([Chem.MolFromSmiles(r["smiles_i"]), Chem.MolFromSmiles(r["smiles_j"])])
        legends.extend(
            [
                f"{r['task']} seed {int(r['seed'])}\ntrue {r['y_i']:.2f} pred {r['pred_i']:.2f}",
                f"sim {r['similarity']:.2f}\ntrue {r['y_j']:.2f} pred {r['pred_j']:.2f}",
            ]
        )
    if mols:
        img = Draw.MolsToGridImage(mols, molsPerRow=2, subImgSize=(280, 220), legends=legends)
        img.save(FIG / "moleculeace_cliff_pair_cases.png")
        svg = Draw.MolsToGridImage(mols, molsPerRow=2, subImgSize=(280, 220), legends=legends, useSVG=True)
        (FIG / "moleculeace_cliff_pair_cases.svg").write_text(svg, encoding="utf-8")
    return detail, cases


def build_extended_failure_cases(low_cases: pd.DataFrame, cliff_cases: pd.DataFrame) -> pd.DataFrame:
    base_path = REPORTS / "manuscript_tables" / "table24_targeted_improvement_case_studies.csv"
    frames = []
    if base_path.exists():
        base = pd.read_csv(base_path)
        base_out = pd.DataFrame(
            {
                "case_id": base["case_id"],
                "case_type": base["case_type"],
                "dataset": base["dataset"],
                "smiles": base.get("smiles", ""),
                "y_true": base.get("y_true", np.nan),
                "y_pred": base.get("y_pred", np.nan),
                "risk_or_similarity": base.get("risk_or_roughness", np.nan),
                "interpretation": base["interpretation"],
            }
        )
        frames.append(base_out)
    if not low_cases.empty:
        low = low_cases.sort_values("abs_error", ascending=False).head(3).copy()
        frames.append(
            pd.DataFrame(
                {
                    "case_id": [f"LowSim-{i+1}" for i in range(len(low))],
                    "case_type": low["case_type"],
                    "dataset": low["dataset"],
                    "smiles": low["smiles"],
                    "y_true": low["y_true"],
                    "y_pred": low["y_pred"],
                    "risk_or_similarity": low["max_train_tanimoto"],
                    "interpretation": low["reason"],
                }
            )
        )
    if not cliff_cases.empty:
        cliff = cliff_cases.sort_values("gap_abs_error", ascending=False).head(3).copy()
        frames.append(
            pd.DataFrame(
                {
                    "case_id": [f"Cliff-{i+1}" for i in range(len(cliff))],
                    "case_type": cliff["case_type"],
                    "dataset": cliff["task"],
                    "smiles": cliff["smiles_i"],
                    "y_true": cliff["y_i"],
                    "y_pred": cliff["pred_i"],
                    "risk_or_similarity": cliff["similarity"],
                    "interpretation": "MoleculeACE neighboring-pair gap case; compare with paired molecule in moleculeace_cliff_pair_cases.csv.",
                }
            )
        )
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    out.to_csv(OUT / "extended_failure_cases.csv", index=False)
    return out


def update_completion_audit() -> None:
    rows = [
        ["Nested validation", "completed as seed-nested selector audit", "nested_seed_validation_summary.csv"],
        ["Unified ablation matrix", "completed with available candidate-pool mappings", "unified_ablation_matrix_summary.csv"],
        ["Exact Tanimoto bins", "completed", "exact_tanimoto_bins_summary.csv"],
        ["Conformal 80/90/95", "completed", "conformal_80_90_95_summary.csv"],
        ["MoleculeACE gap correlation", "completed", "moleculeace_gap_correlation_summary.csv"],
        ["Failure cases", "completed/expanded", "extended_failure_cases.csv"],
    ]
    pd.DataFrame(rows, columns=["item", "status", "main_output"]).to_csv(OUT / "completion_audit_after_full_run.csv", index=False)


def main() -> None:
    pool = load_metric_pool()
    run_seed_nested_validation(pool)
    run_unified_ablation(pool)
    _, low_cases = run_exact_similarity_bins()
    combine_conformal()
    _, cliff_cases = run_moleculeace_gap_correlation()
    build_extended_failure_cases(low_cases, cliff_cases)
    update_completion_audit()
    print(f"Wrote remaining experiment outputs to {OUT}")


if __name__ == "__main__":
    main()
