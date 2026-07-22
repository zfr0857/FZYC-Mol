from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from scipy.stats import kendalltau, spearmanr


ROOT = Path("D:/fzyc")
BASE = ROOT / "results" / "nested_selection" / "repeated_nested"
HARD = ROOT / "output" / "sci1_hardening_20260707"
OUT = ROOT / "output" / "paper19_rejection_driven_experiments_20260712"
SEEDS = [11, 23, 37, 53, 71]
POOL_SIZES = [4, 8, 16, 32]
POLICIES = ["fixed_single", "validation_best", "one_se_stable", "risk_adjusted"]
N_BOOT = 10000
RNG_SEED = 20260712


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_seed_csv(name: str) -> pd.DataFrame:
    frames = []
    for seed in SEEDS:
        path = BASE / f"seed_{seed}" / name
        frame = pd.read_csv(path)
        frame.insert(0, "seed", seed)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def bootstrap_mean_ci(values: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        return math.nan, math.nan
    indices = rng.integers(0, len(values), size=(N_BOOT, len(values)))
    means = values[indices].mean(axis=1)
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def spectral_metrics(matrix: pd.DataFrame) -> dict[str, float]:
    if matrix.shape[1] == 1:
        return {
            "median_pairwise_correlation": 1.0,
            "entropy_effective_rank": 1.0,
            "participation_effective_rank": 1.0,
        }
    corr = matrix.corr().fillna(0.0).to_numpy(dtype=float)
    np.fill_diagonal(corr, 1.0)
    off = corr[np.triu_indices_from(corr, k=1)]
    eig = np.clip(np.linalg.eigvalsh(corr), 0.0, None)
    total = float(eig.sum())
    p = eig / total if total > 0 else np.ones_like(eig) / len(eig)
    nz = p[p > 0]
    entropy_rank = float(np.exp(-(nz * np.log(nz)).sum()))
    participation = float(total**2 / np.square(eig).sum()) if np.square(eig).sum() > 0 else 1.0
    return {
        "median_pairwise_correlation": float(np.nanmedian(off)),
        "entropy_effective_rank": entropy_rank,
        "participation_effective_rank": participation,
    }


def prepare_units() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    inner = load_seed_csv("inner_scores.csv").rename(columns={"dataset": "task"})
    outer = load_seed_csv("outer_candidate_scores.csv").rename(columns={"dataset": "task"})
    policy = load_seed_csv("policy_detail.csv").rename(columns={"dataset": "task"})
    registry = load_seed_csv("candidate_registry.csv").rename(columns={"dataset": "task"})

    policy = policy[policy["policy"].isin(POLICIES)].copy()
    inner_mean = (
        inner.groupby(["task", "task_type", "seed", "outer_fold", "candidate_order"], as_index=False)
        ["inner_utility"]
        .mean()
    )
    joined = inner_mean.merge(
        outer[["task", "task_type", "seed", "outer_fold", "candidate_order", "outer_utility"]],
        on=["task", "task_type", "seed", "outer_fold", "candidate_order"],
        how="inner",
    )
    random_rows = []
    for (task, task_type, seed, fold), unit in joined.groupby(
        ["task", "task_type", "seed", "outer_fold"]
    ):
        for k in POOL_SIZES:
            g = unit[unit["candidate_order"].le(k)]
            oracle = g.sort_values(["outer_utility", "candidate_order"], ascending=[False, True]).iloc[0]
            outer_range = max(float(g["outer_utility"].max() - g["outer_utility"].min()), 1e-12)
            expected_outer = float(g["outer_utility"].mean())
            random_rows.append(
                {
                    "task": task,
                    "task_type": task_type,
                    "seed": int(seed),
                    "outer_fold": int(fold),
                    "outer_split_type": "same_as_registered_unit",
                    "pool_size": k,
                    "policy": "uniform_random_expected",
                    "selected_candidate": "uniform expectation over registered prefix",
                    "selected_family": "mixed",
                    "inner_mean": float(g["inner_utility"].mean()),
                    "inner_sd": float(g["inner_utility"].std(ddof=1)),
                    "outer_utility": expected_outer,
                    "test_oracle_candidate": f"candidate_order_{int(oracle['candidate_order'])}",
                    "test_oracle_utility": float(oracle["outer_utility"]),
                    "test_regret": float(oracle["outer_utility"] - expected_outer),
                    "normalized_test_regret": float((oracle["outer_utility"] - expected_outer) / outer_range),
                    "top3_hit": min(3.0 / k, 1.0),
                }
            )
    policy = pd.concat([policy, pd.DataFrame(random_rows)], ignore_index=True, sort=False)
    policy["metric"] = np.where(policy["task_type"].eq("classification"), "ROC-AUC", "RMSE")
    policy["selected_raw_metric"] = np.where(
        policy["task_type"].eq("classification"), policy["outer_utility"], -policy["outer_utility"]
    )
    policy["observed_audit_oracle_raw_metric"] = np.where(
        policy["task_type"].eq("classification"),
        policy["test_oracle_utility"],
        -policy["test_oracle_utility"],
    )
    policy["raw_selection_loss"] = policy["test_oracle_utility"] - policy["outer_utility"]
    policy["validation_optimism_gap_utility"] = policy["inner_mean"] - policy["outer_utility"]
    policy = policy.rename(
        columns={
            "test_oracle_candidate": "observed_audit_oracle_candidate",
            "test_oracle_utility": "observed_audit_oracle_utility",
            "test_regret": "audit_selection_loss",
            "normalized_test_regret": "range_normalized_audit_selection_loss",
        }
    )
    return inner, outer, policy, registry


def selection_summaries(policy: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(RNG_SEED)
    rows = []
    for keys, g in policy.groupby(["task", "task_type", "metric", "pool_size", "policy"], sort=True):
        lo, hi = bootstrap_mean_ci(g["raw_selection_loss"].to_numpy(float), rng)
        olo, ohi = bootstrap_mean_ci(g["validation_optimism_gap_utility"].to_numpy(float), rng)
        rows.append(
            {
                "task": keys[0],
                "task_type": keys[1],
                "metric": keys[2],
                "candidate_count": int(keys[3]),
                "policy": keys[4],
                "n_outer_units": int(len(g)),
                "mean_raw_selection_loss": float(g["raw_selection_loss"].mean()),
                "median_raw_selection_loss": float(g["raw_selection_loss"].median()),
                "raw_selection_loss_ci95_low": lo,
                "raw_selection_loss_ci95_high": hi,
                "mean_validation_optimism_gap_utility": float(g["validation_optimism_gap_utility"].mean()),
                "validation_optimism_ci95_low": olo,
                "validation_optimism_ci95_high": ohi,
                "mean_range_normalized_loss": float(g["range_normalized_audit_selection_loss"].mean()),
                "top3_hit_rate": float(g["top3_hit"].mean()),
            }
        )
    summary = pd.DataFrame(rows)

    unit_keys = ["task", "task_type", "seed", "outer_fold", "policy"]
    k4 = policy[policy["pool_size"].eq(4)].set_index(unit_keys)
    k32 = policy[policy["pool_size"].eq(32)].set_index(unit_keys)
    paired = k32[["raw_selection_loss", "range_normalized_audit_selection_loss", "validation_optimism_gap_utility"]].join(
        k4[["raw_selection_loss", "range_normalized_audit_selection_loss", "validation_optimism_gap_utility"]],
        lsuffix="_k32",
        rsuffix="_k4",
        how="inner",
    ).reset_index()
    for col in ["raw_selection_loss", "range_normalized_audit_selection_loss", "validation_optimism_gap_utility"]:
        paired[f"delta_{col}_k32_minus_k4"] = paired[f"{col}_k32"] - paired[f"{col}_k4"]

    endpoint_rows = []
    for keys, g in paired.groupby(["task", "task_type", "policy"], sort=True):
        vals = g["delta_raw_selection_loss_k32_minus_k4"].to_numpy(float)
        lo, hi = bootstrap_mean_ci(vals, rng)
        endpoint_rows.append(
            {
                "task": keys[0],
                "task_type": keys[1],
                "metric": "ROC-AUC" if keys[1] == "classification" else "RMSE",
                "policy": keys[2],
                "n_paired_outer_units": int(len(g)),
                "mean_delta_raw_loss_k32_minus_k4": float(vals.mean()),
                "median_delta_raw_loss_k32_minus_k4": float(np.median(vals)),
                "ci95_low": lo,
                "ci95_high": hi,
                "direction_increase_fraction": float((vals > 0).mean()),
                "mean_delta_normalized_loss": float(g["delta_range_normalized_audit_selection_loss_k32_minus_k4"].mean()),
                "mean_delta_optimism_gap": float(g["delta_validation_optimism_gap_utility_k32_minus_k4"].mean()),
            }
        )
    endpoint = pd.DataFrame(endpoint_rows)

    loeo_rows = []
    ep = endpoint[endpoint["policy"].eq("validation_best")].copy()
    for omitted in ["__none__", *sorted(ep["task"].unique())]:
        kept = ep if omitted == "__none__" else ep[~ep["task"].eq(omitted)]
        for task_type, g in kept.groupby("task_type"):
            loeo_rows.append(
                {
                    "omitted_endpoint": omitted,
                    "task_type": task_type,
                    "n_endpoints": int(len(g)),
                    "mean_endpoint_delta_raw_loss": float(g["mean_delta_raw_loss_k32_minus_k4"].mean()),
                    "median_endpoint_delta_raw_loss": float(g["mean_delta_raw_loss_k32_minus_k4"].median()),
                    "endpoints_with_increased_loss": int((g["mean_delta_raw_loss_k32_minus_k4"] > 0).sum()),
                }
            )
    loeo = pd.DataFrame(loeo_rows)
    return summary, paired, endpoint, loeo


def ranking_fidelity(inner: pd.DataFrame, outer: pd.DataFrame) -> pd.DataFrame:
    inner_mean = (
        inner.groupby(["task", "task_type", "seed", "outer_fold", "candidate_order", "candidate"], as_index=False)
        ["inner_utility"]
        .mean()
    )
    outer_keep = outer[
        ["task", "task_type", "seed", "outer_fold", "candidate_order", "candidate", "outer_utility"]
    ]
    joined = inner_mean.merge(
        outer_keep,
        on=["task", "task_type", "seed", "outer_fold", "candidate_order", "candidate"],
        how="inner",
    )
    rows = []
    for (task, task_type, seed, fold), unit in joined.groupby(["task", "task_type", "seed", "outer_fold"]):
        for k in POOL_SIZES:
            g = unit[unit["candidate_order"].le(k)].copy()
            rho = spearmanr(g["inner_utility"], g["outer_utility"]).statistic
            tau = kendalltau(g["inner_utility"], g["outer_utility"]).statistic
            inner_rank = g.sort_values(["inner_utility", "candidate_order"], ascending=[False, True]).reset_index(drop=True)
            oracle = g.sort_values(["outer_utility", "candidate_order"], ascending=[False, True]).iloc[0]
            rank = int(inner_rank.index[inner_rank["candidate_order"].eq(oracle["candidate_order"])][0]) + 1
            rows.append(
                {
                    "task": task,
                    "task_type": task_type,
                    "seed": int(seed),
                    "outer_fold": int(fold),
                    "candidate_count": k,
                    "spearman_validation_vs_audit": float(rho),
                    "kendall_validation_vs_audit": float(tau),
                    "oracle_inner_rank": rank,
                    "top1_hit": int(rank == 1),
                    "top3_hit": int(rank <= 3),
                    "mrr": 1.0 / rank,
                }
            )
    return pd.DataFrame(rows)


def effective_diversity(inner: pd.DataFrame, outer: pd.DataFrame, ranking: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for task in sorted(outer["task"].unique()):
        o_task = outer[outer["task"].eq(task)]
        i_task = inner[inner["task"].eq(task)]
        task_type = str(o_task["task_type"].iloc[0])
        for k in POOL_SIZES:
            o = o_task[o_task["candidate_order"].le(k)].pivot_table(
                index=["seed", "outer_fold"], columns="candidate_order", values="outer_utility"
            )
            i = i_task[i_task["candidate_order"].le(k)].pivot_table(
                index=["seed", "outer_fold", "inner_fold"], columns="candidate_order", values="inner_utility"
            )
            om = spectral_metrics(o)
            im = spectral_metrics(i)
            rank_g = ranking[ranking["task"].eq(task) & ranking["candidate_count"].eq(k)]
            rows.append(
                {
                    "task": task,
                    "task_type": task_type,
                    "candidate_count": k,
                    "outer_units": int(o.shape[0]),
                    "inner_units": int(i.shape[0]),
                    "outer_median_pairwise_correlation": om["median_pairwise_correlation"],
                    "outer_entropy_effective_rank": om["entropy_effective_rank"],
                    "outer_participation_effective_rank": om["participation_effective_rank"],
                    "inner_median_pairwise_correlation": im["median_pairwise_correlation"],
                    "inner_entropy_effective_rank": im["entropy_effective_rank"],
                    "inner_participation_effective_rank": im["participation_effective_rank"],
                    "mean_validation_audit_spearman": float(rank_g["spearman_validation_vs_audit"].mean()),
                    "top1_hit_rate": float(rank_g["top1_hit"].mean()),
                    "mrr": float(rank_g["mrr"].mean()),
                }
            )
    return pd.DataFrame(rows)


def strong_baseline_diversity() -> pd.DataFrame:
    path = HARD / "six_task_strong_baseline_outer_scores.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    rows = []
    overlap_path = HARD / "six_task_error_overlap_pairwise_summary.csv"
    overlap = pd.read_csv(overlap_path) if overlap_path.exists() else pd.DataFrame()
    for task, g in df.groupby("task"):
        pivot = g.pivot_table(index=["seed", "outer_fold"], columns="candidate", values="outer_utility")
        metrics = spectral_metrics(pivot)
        rows.append(
            {
                "task": task,
                "task_type": str(g["task_type"].iloc[0]),
                "candidate_count": int(pivot.shape[1]),
                **metrics,
                "mean_error_jaccard_all_pairs": float(overlap["mean_jaccard_error_overlap"].mean())
                if not overlap.empty
                else math.nan,
                "error_jaccard_min": float(overlap["mean_jaccard_error_overlap"].min())
                if not overlap.empty
                else math.nan,
                "error_jaccard_max": float(overlap["mean_jaccard_error_overlap"].max())
                if not overlap.empty
                else math.nan,
            }
        )
    return pd.DataFrame(rows)


def oracle_bias_simulation() -> pd.DataFrame:
    rng = np.random.default_rng(RNG_SEED)
    rows = []
    n_rep = 30000
    for scenario in ["equal_truth", "weak_gradient"]:
        for n_eff in [25, 50, 100, 200]:
            sigma = 1.0 / math.sqrt(n_eff)
            for rho in [0.0, 0.5, 0.9, 0.99]:
                for k in POOL_SIZES:
                    truth = np.zeros(k) if scenario == "equal_truth" else np.linspace(0.0, 0.15, k)
                    common_a = rng.normal(size=(n_rep, 1))
                    idio_a = rng.normal(size=(n_rep, k))
                    noise_a = sigma * (math.sqrt(rho) * common_a + math.sqrt(1.0 - rho) * idio_a)
                    audit = truth[None, :] + noise_a
                    winners = np.argmax(audit, axis=1)
                    observed = audit[np.arange(n_rep), winners]
                    true_winner = truth[winners]
                    common_i = rng.normal(size=(n_rep, 1))
                    idio_i = rng.normal(size=(n_rep, k))
                    independent = truth[None, :] + sigma * (
                        math.sqrt(rho) * common_i + math.sqrt(1.0 - rho) * idio_i
                    )
                    independent_winner_score = independent[np.arange(n_rep), winners]
                    optimism = observed - true_winner
                    attenuation = observed - independent_winner_score
                    observed_gain = observed - audit[:, 0]
                    true_gain = true_winner - truth[0]
                    rows.append(
                        {
                            "truth_scenario": scenario,
                            "effective_audit_sample_size": n_eff,
                            "pairwise_candidate_correlation": rho,
                            "candidate_count": k,
                            "n_replicates": n_rep,
                            "noise_sd": sigma,
                            "mean_observed_oracle_optimism": float(optimism.mean()),
                            "optimism_ci95_low": float(np.quantile(optimism, 0.025)),
                            "optimism_ci95_high": float(np.quantile(optimism, 0.975)),
                            "mean_audit_to_independent_attenuation": float(attenuation.mean()),
                            "mean_observed_gain_vs_first": float(observed_gain.mean()),
                            "mean_true_realized_gain_vs_first": float(true_gain.mean()),
                            "true_best_selection_rate": float((winners == int(np.argmax(truth))).mean()),
                        }
                    )
    return pd.DataFrame(rows)


def budget_and_registry(inner: pd.DataFrame, outer: pd.DataFrame, registry: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    inner_budget = inner.groupby(["task", "candidate_order", "candidate", "family"], as_index=False).agg(
        inner_fits=("fit_seconds", "size"), inner_fit_seconds=("fit_seconds", "sum")
    )
    outer_budget = outer.groupby(["task", "candidate_order", "candidate", "family"], as_index=False).agg(
        outer_fits=("fit_seconds", "size"), outer_fit_seconds=("fit_seconds", "sum")
    )
    budget = inner_budget.merge(
        outer_budget, on=["task", "candidate_order", "candidate", "family"], how="outer"
    ).fillna(0)
    budget["total_fits"] = budget["inner_fits"] + budget["outer_fits"]
    budget["total_fit_seconds"] = budget["inner_fit_seconds"] + budget["outer_fit_seconds"]
    budget["budget_interpretation"] = "fixed fit-count protocol; wall time reported, not equalized"

    reg = registry[registry["seed"].eq(SEEDS[0])].copy()
    reg = reg.merge(
        budget[["task", "candidate_order", "candidate", "total_fits", "total_fit_seconds"]],
        on=["task", "candidate_order", "candidate"],
        how="left",
    )
    reg["eligibility"] = "retrospective registered candidate"
    reg["status"] = "completed"
    reg["replacement_after_failure"] = False
    reg["evidence_role"] = "near-duplicate/conventional-model candidate-pool stress"
    return budget, reg


def timeline() -> pd.DataFrame:
    rows = []
    for seed in SEEDS:
        for name in ["candidate_registry.csv", "inner_scores.csv", "outer_candidate_scores.csv", "policy_detail.csv"]:
            p = BASE / f"seed_{seed}" / name
            rows.append(
                {
                    "event": name.replace(".csv", ""),
                    "seed": seed,
                    "timestamp_utc_from_file_mtime": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(),
                    "path": str(p.relative_to(ROOT)),
                    "sha256": sha256(p),
                    "confirmatory_status": "historical output; timestamp does not prove preregistration",
                }
            )
    rows.append(
        {
            "event": "paper19_analysis_lock",
            "seed": "",
            "timestamp_utc_from_file_mtime": datetime.now(timezone.utc).isoformat(),
            "path": "output/paper19_rejection_driven_experiments_20260712/paper19_analysis_lock.json",
            "sha256": "written after script definition",
            "confirmatory_status": "analysis plan reconstructed before paper19 summaries; outer outcomes already existed",
        }
    )
    rows.append(
        {
            "event": "independent_confirmation",
            "seed": "",
            "timestamp_utc_from_file_mtime": "not_available",
            "path": "",
            "sha256": "",
            "confirmatory_status": "not completed; no claim of independent confirmation",
        }
    )
    return pd.DataFrame(rows)


def make_figure(diversity: pd.DataFrame, summary: pd.DataFrame, endpoint: pd.DataFrame, sim: pd.DataFrame) -> None:
    plt.rcParams.update(
        {
            "font.family": "Arial",
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 11,
            "xtick.labelsize": 9,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "svg.fonttype": "none",
        }
    )
    colors = {4: "#6E7A86", 8: "#3A6EA5", 16: "#4C9A74", 32: "#B86B5E"}
    fig, axes = plt.subplots(2, 2, figsize=(12.2, 8.5))
    ax1, ax2, ax3, ax4 = axes.ravel()

    for task, g in diversity.groupby("task"):
        ax1.plot(g["candidate_count"], g["outer_entropy_effective_rank"], color="#B7BEC7", lw=1, alpha=0.7)
    mean_div = diversity.groupby("candidate_count", as_index=False)["outer_entropy_effective_rank"].mean()
    ax1.plot(
        mean_div["candidate_count"],
        mean_div["outer_entropy_effective_rank"],
        color="#1F2937",
        marker="o",
        lw=2.3,
        label="Endpoint mean",
    )
    ax1.plot(POOL_SIZES, POOL_SIZES, color="#D1D5DB", ls="--", lw=1, label="Nominal K")
    ax1.set_xscale("log", base=2)
    ax1.set_xticks(POOL_SIZES, POOL_SIZES)
    ax1.set_xlabel("Nominal candidate count")
    ax1.set_ylabel("Spectral effective rank")
    ax1.set_title("Nominal K versus effective diversity")
    ax1.legend(frameon=False)

    vb = summary[summary["policy"].eq("validation_best")]
    for task, g in vb.groupby("task"):
        ax2.plot(g["candidate_count"], g["mean_range_normalized_loss"], color="#B7BEC7", lw=1, alpha=0.75)
    vb_mean = vb.groupby("candidate_count", as_index=False)["mean_range_normalized_loss"].mean()
    ax2.plot(
        vb_mean["candidate_count"],
        vb_mean["mean_range_normalized_loss"],
        color="#1F2937",
        marker="o",
        lw=2.3,
        label="Endpoint mean",
    )
    ax2.set_xscale("log", base=2)
    ax2.set_xticks(POOL_SIZES, POOL_SIZES)
    ax2.set_xlabel("Candidate count")
    ax2.set_ylabel("Range-normalized audit loss")
    ax2.set_title("Selection loss across endpoints")
    ax2.legend(frameon=False)

    forest = endpoint[endpoint["policy"].eq("validation_best")].sort_values("mean_delta_raw_loss_k32_minus_k4")
    y = np.arange(len(forest))
    err = np.vstack(
        [
            forest["mean_delta_raw_loss_k32_minus_k4"] - forest["ci95_low"],
            forest["ci95_high"] - forest["mean_delta_raw_loss_k32_minus_k4"],
        ]
    )
    point_colors = ["#3A6EA5" if t == "classification" else "#4C9A74" for t in forest["task_type"]]
    ax3.errorbar(
        forest["mean_delta_raw_loss_k32_minus_k4"],
        y,
        xerr=err,
        fmt="none",
        ecolor="#C8D0DA",
        capsize=2,
        lw=1.3,
    )
    ax3.scatter(forest["mean_delta_raw_loss_k32_minus_k4"], y, c=point_colors, s=38, edgecolor="#1F2937", lw=0.35)
    ax3.axvline(0, color="#1F2937", lw=1)
    ax3.set_yticks(y, forest["task"])
    ax3.set_xlabel("K=32 minus K=4 raw selection loss")
    ax3.set_title("Endpoint-level raw-unit effects")
    ax3.legend(
        handles=[
            Line2D([0], [0], marker="o", color="none", markerfacecolor="#3A6EA5", markeredgecolor="#1F2937", label="Classification"),
            Line2D([0], [0], marker="o", color="none", markerfacecolor="#4C9A74", markeredgecolor="#1F2937", label="Regression"),
        ],
        frameon=False,
        loc="lower right",
    )

    s = sim[
        sim["truth_scenario"].eq("equal_truth")
        & sim["effective_audit_sample_size"].eq(50)
    ]
    for rho, g in s.groupby("pairwise_candidate_correlation"):
        ax4.plot(
            g["candidate_count"],
            g["mean_observed_oracle_optimism"],
            marker="o",
            lw=2,
            label=f"rho={rho:g}",
        )
    ax4.set_xscale("log", base=2)
    ax4.set_xticks(POOL_SIZES, POOL_SIZES)
    ax4.set_xlabel("Candidate count")
    ax4.set_ylabel("Observed-oracle optimism (SD units)")
    ax4.set_title("Finite-audit winner optimism")
    ax4.legend(frameon=False)

    for ax in axes.ravel():
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", color="#E7EBF0", lw=0.8)
        ax.set_axisbelow(True)
    fig.tight_layout(w_pad=2.0, h_pad=2.0)
    fig.savefig(OUT / "fig_paper19_candidate_diversity_selection_loss.png", dpi=600, bbox_inches="tight")
    fig.savefig(OUT / "fig_paper19_candidate_diversity_selection_loss.svg", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    lock = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "analysis plan reconstructed before paper19 summaries; original outer outcomes already existed",
        "primary_analysis": "endpoint-specific raw audit-set selection loss for K=32 versus K=4",
        "secondary_analysis": [
            "range-normalized audit loss",
            "validation-audit ranking fidelity",
            "spectral effective rank",
            "synthetic known-truth observed-oracle optimism calibration",
        ],
        "pool_sizes": POOL_SIZES,
        "policies": POLICIES,
        "seeds": SEEDS,
        "bootstrap_replicates": N_BOOT,
        "third_party_reproduction": "deferred by user; not claimed",
        "independent_confirmation": "not available; not claimed",
    }
    (OUT / "paper19_analysis_lock.json").write_text(json.dumps(lock, ensure_ascii=False, indent=2), encoding="utf-8")

    inner, outer, policy, registry = prepare_units()
    summary, paired, endpoint, loeo = selection_summaries(policy)
    ranking = ranking_fidelity(inner, outer)
    diversity = effective_diversity(inner, outer, ranking)
    strong = strong_baseline_diversity()
    sim = oracle_bias_simulation()
    budget, reg = budget_and_registry(inner, outer, registry)
    time = timeline()

    outputs = {
        "paper19_policy_units.csv": policy,
        "paper19_raw_selection_loss_summary.csv": summary,
        "paper19_k32_vs_k4_paired_units.csv": paired,
        "paper19_k32_vs_k4_endpoint_effects.csv": endpoint,
        "paper19_leave_one_endpoint_out.csv": loeo,
        "paper19_ranking_fidelity_units.csv": ranking,
        "paper19_effective_diversity.csv": diversity,
        "paper19_strong_baseline_effective_diversity.csv": strong,
        "paper19_oracle_extreme_value_simulation.csv": sim,
        "paper19_compute_budget.csv": budget,
        "paper19_candidate_registry.csv": reg,
        "paper19_selection_timeline.csv": time,
    }
    for name, frame in outputs.items():
        frame.to_csv(OUT / name, index=False)

    make_figure(diversity, summary, endpoint, sim)

    ep_vb = endpoint[endpoint["policy"].eq("validation_best")]
    sim_key = sim[
        sim["truth_scenario"].eq("equal_truth")
        & sim["effective_audit_sample_size"].eq(50)
        & sim["pairwise_candidate_correlation"].eq(0.9)
    ].set_index("candidate_count")
    div_mean = diversity.groupby("candidate_count")["outer_entropy_effective_rank"].mean()
    summary_json = {
        "input_outer_rows": int(len(outer)),
        "input_inner_rows": int(len(inner)),
        "policy_rows": int(len(policy)),
        "tasks": sorted(outer["task"].unique().tolist()),
        "seeds": SEEDS,
        "outer_folds": sorted(outer["outer_fold"].unique().tolist()),
        "candidate_counts": POOL_SIZES,
        "validation_best_endpoints_with_increased_raw_loss": int(
            (ep_vb["mean_delta_raw_loss_k32_minus_k4"] > 0).sum()
        ),
        "validation_best_endpoints_total": int(len(ep_vb)),
        "classification_mean_raw_delta": float(
            ep_vb.loc[ep_vb["task_type"].eq("classification"), "mean_delta_raw_loss_k32_minus_k4"].mean()
        ),
        "regression_mean_raw_delta": float(
            ep_vb.loc[ep_vb["task_type"].eq("regression"), "mean_delta_raw_loss_k32_minus_k4"].mean()
        ),
        "mean_entropy_effective_rank_k4": float(div_mean.loc[4]),
        "mean_entropy_effective_rank_k32": float(div_mean.loc[32]),
        "equal_truth_oracle_optimism_rho09_n50_k4": float(sim_key.loc[4, "mean_observed_oracle_optimism"]),
        "equal_truth_oracle_optimism_rho09_n50_k32": float(sim_key.loc[32, "mean_observed_oracle_optimism"]),
        "independent_confirmation_completed": False,
        "third_party_reproduction_completed": False,
    }
    checks = {
        "all_expected_outputs_exist": all((OUT / name).exists() for name in outputs),
        "nine_tasks": len(summary_json["tasks"]) == 9,
        "five_seeds": len(SEEDS) == 5,
        "three_outer_folds": len(summary_json["outer_folds"]) == 3,
        "four_pool_sizes": len(POOL_SIZES) == 4,
        "figure_png": (OUT / "fig_paper19_candidate_diversity_selection_loss.png").exists(),
        "figure_svg": (OUT / "fig_paper19_candidate_diversity_selection_loss.svg").exists(),
    }
    audit = {"summary": summary_json, "checks": checks, "passed": all(checks.values())}
    (OUT / "paper19_experiment_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
