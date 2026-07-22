from __future__ import annotations

import hashlib
import itertools
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from rdkit import Chem, DataStructs
from rdkit.Chem import AllChem
from rdkit.Chem.Scaffolds import MurckoScaffold
from scipy.stats import rankdata, spearmanr, t
from sklearn.base import clone
from sklearn.covariance import LedoitWolf
from sklearn.metrics import average_precision_score, mean_squared_error, roc_auc_score


ROOT = Path("D:/fzyc")
sys.path.insert(0, str(ROOT / "scripts"))
import run_shared_split_multiview_nested_20260624 as shared  # noqa: E402

MULTI = Path(os.environ.get("FZYC_MULTIVIEW_BASE", ROOT / "results" / "reviewer_core_20260624" / "multiview_nested"))
PREFIX_BASE = Path(os.environ.get("FZYC_PREFIX_BASE", ROOT / "results" / "nested_selection" / "repeated_nested"))
CORE20 = Path(os.environ.get("FZYC_CORE_OUT", ROOT / "output" / "paper20_candidate_pool_audit_20260712"))
HARD = ROOT / "output" / "sci1_hardening_20260707"
UQ = ROOT / "output" / "sci1_mechanism_uq_decision_20260707"
OUT = Path(os.environ.get("FZYC_ANALYSIS_OUT", ROOT / "output" / "paper21_final_reanalysis_20260713"))
SEEDS = [11, 23, 37, 53, 71]
RNG_SEED = 20260713


def sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_indices(values: np.ndarray | list[int]) -> str:
    return sha_text(",".join(map(str, np.asarray(values, dtype=int).tolist())))


def prediction_hash(values: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(values, dtype=np.float64).tobytes()).hexdigest()


def entropy_metrics(x: np.ndarray) -> dict[str, float]:
    x = np.asarray(x, dtype=float)
    keep = np.nanstd(x, axis=0) > 1e-12
    x = x[:, keep]
    if x.shape[1] <= 1:
        return {"lw_entropy_rank": 1.0, "participation_rank": 1.0, "median_correlation": 1.0}
    sd = x.std(axis=0, ddof=1)
    z = (x - x.mean(axis=0)) / np.where(sd > 1e-12, sd, 1.0)
    cov = LedoitWolf().fit(z).covariance_
    scale = np.sqrt(np.clip(np.diag(cov), 1e-15, None))
    corr = np.clip(cov / np.outer(scale, scale), -1, 1)
    np.fill_diagonal(corr, 1)
    eig = np.clip(np.linalg.eigvalsh(corr), 0, None)
    p = eig / eig.sum()
    p = p[p > 1e-15]
    off = corr[np.triu_indices_from(corr, 1)]
    return {
        "lw_entropy_rank": float(np.exp(-(p * np.log(p)).sum())),
        "participation_rank": float(eig.sum() ** 2 / np.square(eig).sum()),
        "median_correlation": float(np.median(off)),
    }


def seed_split_audit() -> tuple[pd.DataFrame, pd.DataFrame]:
    registry = json.loads((ROOT / "data" / "dataset_registry.json").read_text(encoding="utf-8"))
    policy = pd.read_csv(MULTI / "policy_detail.csv")
    rows = []
    for task in shared.TASKS:
        frame, task_type = shared.load_task(task, registry)
        representations, groups, keep = shared.featurize(frame["smiles"])
        frame = frame.loc[keep].reset_index(drop=True)
        y = frame["y"].to_numpy()
        for seed in SEEDS:
            outer_splits, outer_type = shared.make_splits(y, groups, task_type, 3, seed)
            specs = {spec["candidate"]: spec for spec in shared.candidate_specs(task_type, seed)}
            for outer_fold, (outer_train, outer_test) in enumerate(outer_splits, start=1):
                inner_splits, inner_type = shared.make_splits(y[outer_train], groups[outer_train], task_type, 3, seed + outer_fold)
                inner_assignment = []
                for inner_fold, (_, valid_local) in enumerate(inner_splits, start=1):
                    inner_assignment.extend((int(outer_train[i]), inner_fold) for i in valid_local)
                scaffold_assignment = [
                    (int(i), str(groups[i]), "test" if i in set(outer_test) else "train") for i in range(len(y))
                ]
                selected_row = policy.loc[
                    policy["task"].eq(task) & policy["seed"].eq(seed) & policy["outer_fold"].eq(outer_fold)
                    & policy["policy"].eq("validation_best") & policy["variant"].eq("full_multiview")
                ].iloc[0]
                morgan_row = policy.loc[
                    policy["task"].eq(task) & policy["seed"].eq(seed) & policy["outer_fold"].eq(outer_fold)
                    & policy["policy"].eq("validation_best") & policy["variant"].eq("morgan_only")
                ].iloc[0]
                rerun = {}
                for label, candidate in [("selected", selected_row["selected_candidate"]), ("morgan", morgan_row["selected_candidate"])]:
                    spec = specs[str(candidate)]
                    x = representations[str(spec["representation"])]
                    model = clone(spec["model"])
                    model.fit(x[outer_train], y[outer_train])
                    pred = shared.predict(model, x[outer_test], task_type)
                    rerun[label] = {
                        "candidate": candidate,
                        "prediction_hash": prediction_hash(pred),
                        "utility": shared.utility(y[outer_test], pred, task_type),
                        "random_state": model.steps[-1][1].get_params(deep=False).get("random_state"),
                    }
                rows.append({
                    "endpoint": task, "task_type": task_type, "seed": seed, "outer_fold": outer_fold,
                    "outer_split_type": outer_type, "inner_split_type": inner_type,
                    "train_indices_hash": hash_indices(outer_train),
                    "validation_indices_hash": sha_text(json.dumps(sorted(inner_assignment))),
                    "test_indices_hash": hash_indices(outer_test),
                    "scaffold_assignment_hash": sha_text(json.dumps(scaffold_assignment, separators=(",", ":"))),
                    "selected_candidate": rerun["selected"]["candidate"],
                    "candidate_random_state": rerun["selected"]["random_state"],
                    "prediction_hash": rerun["selected"]["prediction_hash"],
                    "morgan_prediction_hash": rerun["morgan"]["prediction_hash"],
                    "outer_performance": rerun["selected"]["utility"],
                    "stored_outer_performance": float(selected_row["outer_utility"]),
                    "rerun_minus_stored": rerun["selected"]["utility"] - float(selected_row["outer_utility"]),
                    "paired_gain": rerun["selected"]["utility"] - rerun["morgan"]["utility"],
                })
    detail = pd.DataFrame(rows)
    summary_rows = []
    for (task, task_type), group in detail.groupby(["endpoint", "task_type"]):
        summary_rows.append({
            "endpoint": task, "task_type": task_type,
            "unique_outer_split_assignments": group.groupby("seed")["scaffold_assignment_hash"].first().nunique(),
            "unique_test_hashes_across_seed_fold": group["test_indices_hash"].nunique(),
            "all_fold_test_hashes_identical_by_seed": group.groupby("outer_fold")["test_indices_hash"].nunique().max() == 1,
            "unique_selected_candidates": group["selected_candidate"].nunique(),
            "unique_prediction_hashes": group["prediction_hash"].nunique(),
            "max_abs_rerun_minus_stored": group["rerun_minus_stored"].abs().max(),
            "valid_split_replication_count": group.groupby("seed")["scaffold_assignment_hash"].first().nunique(),
            "inference_status": "five distinct scaffold partitions" if group.groupby("seed")["scaffold_assignment_hash"].first().nunique() == 5 else "one unique scaffold partition; model-seed repetitions only",
        })
    return detail, pd.DataFrame(summary_rows)


def cross_fitted_intervals() -> tuple[pd.DataFrame, pd.DataFrame]:
    units = pd.read_csv(CORE20 / "cross_fitted_reference_units.csv")
    rows, fold_rows = [], []
    rng = np.random.default_rng(RNG_SEED)
    for (task, task_type), group in units.groupby(["task", "task_type"]):
        wide = group.pivot_table(index=["seed", "outer_fold"], columns="candidate_count", values=["same_unit_gap", "cross_fitted_gap"])
        same = wide["same_unit_gap"][32] - wide["same_unit_gap"][4]
        cross = wide["cross_fitted_gap"][32] - wide["cross_fitted_gap"][4]
        diff = same - cross
        for (seed, fold), value in same.items():
            fold_rows.append({"task": task, "task_type": task_type, "seed": seed, "outer_fold": fold, "same_unit_effect": value, "cross_fitted_effect": cross.loc[(seed, fold)], "same_minus_cross": diff.loc[(seed, fold)]})
        row = {"task": task, "task_type": task_type, "same_unit_effect": same.mean(), "cross_fitted_effect": cross.mean(), "same_minus_cross": diff.mean()}
        for name, values in [("same_unit", same), ("cross_fitted", cross), ("difference", diff)]:
            seed_means = values.groupby("seed").mean().reindex(SEEDS)
            fold_means = values.groupby("outer_fold").mean().reindex([1, 2, 3])
            row[f"positive_seed_means_{name}"] = int((seed_means > 0).sum())
            row[f"leave_one_seed_min_{name}"] = min(seed_means.drop(index=s).mean() for s in SEEDS)
            row[f"leave_one_seed_max_{name}"] = max(seed_means.drop(index=s).mean() for s in SEEDS)
            sem = seed_means.std(ddof=1) / math.sqrt(5)
            row[f"model_seed_t95_low_{name}"] = seed_means.mean() - t.ppf(0.975, 4) * sem
            row[f"model_seed_t95_high_{name}"] = seed_means.mean() + t.ppf(0.975, 4) * sem
            row[f"outer_fold_descriptive_min_{name}"] = fold_means.min()
            row[f"outer_fold_descriptive_max_{name}"] = fold_means.max()
            draws = rng.choice(seed_means.to_numpy(), size=(10000, 5), replace=True).mean(axis=1)
            row[f"split_seed_bootstrap95_low_{name}"] = np.quantile(draws, 0.025)
            row[f"split_seed_bootstrap95_high_{name}"] = np.quantile(draws, 0.975)
            row[f"primary_interval_type_{name}"] = "split-seed clustered bootstrap over five distinct scaffold partitions"
        rows.append(row)
    return pd.DataFrame(rows), pd.DataFrame(fold_rows)


def matched_k3_all_subsets() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    inner = pd.read_csv(MULTI / "inner_scores.csv")
    outer = pd.read_csv(MULTI / "outer_candidate_scores.csv")
    registry = inner[["candidate_order", "candidate", "representation", "family"]].drop_duplicates().sort_values("candidate_order")
    inner_means = inner.groupby(["task", "task_type", "seed", "outer_fold", "candidate_order"], as_index=False)["inner_utility"].mean()
    out = outer[["task", "task_type", "seed", "outer_fold", "candidate_order", "outer_utility"]]
    morgan_orders = [1, 2, 3]
    baseline_units = []
    for key, group in inner_means.loc[inner_means.candidate_order.isin(morgan_orders)].groupby(["task", "task_type", "seed", "outer_fold"]):
        chosen = group.sort_values(["inner_utility", "candidate_order"], ascending=[False, True]).iloc[0]
        utility = out.loc[(out.task == key[0]) & (out.seed == key[2]) & (out.outer_fold == key[3]) & (out.candidate_order == chosen.candidate_order), "outer_utility"].iloc[0]
        baseline_units.append((*key, utility))
    baseline = pd.DataFrame(baseline_units, columns=["task", "task_type", "seed", "outer_fold", "morgan_k3_utility"])
    unit_rows, summary_rows, selection_rows = [], [], []
    harmonic3 = 1 + 1 / 2 + 1 / 3
    mrr_random = harmonic3 / 3
    combinations = list(itertools.combinations(registry.candidate_order.astype(int), 3))
    for subset_id, combo in enumerate(combinations, start=1):
        meta = registry.loc[registry.candidate_order.isin(combo)]
        reps = sorted(meta.representation.unique())
        fams = sorted(meta.family.unique())
        categories = {
            "single_representation": len(reps) == 1,
            "single_learner": len(fams) == 1,
            "representation_balanced": len(reps) == 3,
            "learner_balanced": len(fams) == 3,
            "includes_concatenation": "multiview" in reps,
            "excludes_concatenation": "multiview" not in reps,
            "morgan_containing": "morgan512" in reps,
            "morgan_excluding": "morgan512" not in reps,
        }
        if set(combo) == {1, 2, 3}:
            composition_class = "Morgan-only reference"
        elif len(reps) == 1:
            composition_class = "single-representation only"
        elif len(fams) == 1:
            composition_class = "single-learner only"
        elif len(reps) == 3 and "multiview" in reps:
            composition_class = "representation-balanced with concatenation"
        elif len(reps) == 3:
            composition_class = "representation-balanced without concatenation"
        else:
            composition_class = "mixed unbalanced"
        subset_inner = inner_means.loc[inner_means.candidate_order.isin(combo)]
        subset_outer = out.loc[out.candidate_order.isin(combo)]
        selected = subset_inner.sort_values(["task", "seed", "outer_fold", "inner_utility", "candidate_order"], ascending=[True, True, True, False, True]).groupby(["task", "task_type", "seed", "outer_fold"], as_index=False).first()
        selected = selected.merge(subset_outer, on=["task", "task_type", "seed", "outer_fold", "candidate_order"])
        selected = selected.merge(baseline, on=["task", "task_type", "seed", "outer_fold"])
        selected["selected_model_gain_vs_morgan_k3"] = selected.outer_utility - selected.morgan_k3_utility
        audit_best = subset_outer.groupby(["task", "task_type", "seed", "outer_fold"], as_index=False).outer_utility.max().rename(columns={"outer_utility": "audit_best_utility"})
        selected = selected.merge(audit_best, on=["task", "task_type", "seed", "outer_fold"])
        rank_rows = []
        for key, group in subset_inner.groupby(["task", "task_type", "seed", "outer_fold"]):
            audit = subset_outer.loc[(subset_outer.task == key[0]) & (subset_outer.seed == key[2]) & (subset_outer.outer_fold == key[3])].sort_values(["outer_utility", "candidate_order"], ascending=[False, True]).iloc[0]
            ordered = group.sort_values(["inner_utility", "candidate_order"], ascending=[False, True]).reset_index(drop=True)
            rank = int(np.flatnonzero(ordered.candidate_order.to_numpy() == int(audit.candidate_order))[0] + 1)
            mrr = 1 / rank
            rank_rows.append((*key, rank, mrr, (mrr - mrr_random) / (1 - mrr_random)))
        ranks = pd.DataFrame(rank_rows, columns=["task", "task_type", "seed", "outer_fold", "audit_best_inner_rank", "mrr", "normalized_mrr_gain"])
        selected = selected.merge(ranks, on=["task", "task_type", "seed", "outer_fold"])
        # Hit@3 is identically one for K=3; chance adjustment has zero denominator.
        selected["hit_at_3"] = 1
        selected["chance_adjusted_hit_at_3"] = np.nan
        cross_rows = []
        for task in selected.task.unique():
            for held_seed in SEEDS:
                training = subset_outer.loc[(subset_outer.task == task) & (subset_outer.seed != held_seed)]
                ref_order = int(training.groupby("candidate_order").outer_utility.mean().sort_values(ascending=False).index[0])
                held_ref = subset_outer.loc[(subset_outer.task == task) & (subset_outer.seed == held_seed) & (subset_outer.candidate_order == ref_order), ["outer_fold", "outer_utility"]]
                for _, rr in held_ref.iterrows(): cross_rows.append((task, held_seed, int(rr.outer_fold), ref_order, float(rr.outer_utility)))
        cross = pd.DataFrame(cross_rows, columns=["task", "seed", "outer_fold", "cross_reference_order", "cross_reference_utility"])
        selected = selected.merge(cross, on=["task", "seed", "outer_fold"])
        selected["cross_fitted_gap"] = selected.cross_reference_utility - selected.outer_utility
        selected["subset_id"] = subset_id
        selected["candidate_orders"] = "|".join(map(str, combo))
        for name, value in categories.items(): selected[name] = value
        selected["composition_class"] = composition_class
        unit_rows.append(selected)
        for task, group in selected.groupby("task"):
            matrix = subset_outer.loc[subset_outer.task.eq(task)].pivot_table(index=["seed", "outer_fold"], columns="candidate_order", values="outer_utility").to_numpy(float)
            diversity = entropy_metrics(matrix)
            gains = group.selected_model_gain_vs_morgan_k3.to_numpy(float)
            summary_rows.append({
                "subset_id": subset_id, "candidate_orders": "|".join(map(str, combo)), "task": task,
                "task_type": group.task_type.iloc[0], "representations": "|".join(reps), "learners": "|".join(fams),
                **categories, "composition_class": composition_class,
                "selected_model_gain_mean": gains.mean(), "selected_model_gain_median": np.median(gains),
                "selected_model_gain_q25": np.quantile(gains, .25), "selected_model_gain_q75": np.quantile(gains, .75),
                "selected_model_gain_p2_5": np.quantile(gains, .025), "selected_model_gain_p97_5": np.quantile(gains, .975),
                "cross_fitted_gap_mean": group.cross_fitted_gap.mean(), **diversity,
                "hit_at_3": 1.0, "chance_adjusted_hit_at_3": np.nan,
                "chance_adjusted_hit_at_3_status": "not estimable for K=3 because random Hit@3 expectation equals 1",
                "normalized_mrr_gain_mean": group.normalized_mrr_gain.mean(),
                "outperforming_morgan_only_proportion": float((gains > 0).mean()),
            })
        chosen = selected.merge(registry, on="candidate_order")
        freq = chosen.groupby(["task", "representation", "family"], as_index=False).size()
        freq["subset_id"] = subset_id
        selection_rows.append(freq)
    return pd.concat(unit_rows, ignore_index=True), pd.DataFrame(summary_rows), pd.concat(selection_rows, ignore_index=True)


def scaffold_fp(scaffold: str):
    mol = Chem.MolFromSmiles(str(scaffold))
    return AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=512) if mol is not None else None


def add_scaffold_relatedness(metadata: pd.DataFrame) -> pd.DataFrame:
    registry = json.loads((ROOT / "data" / "dataset_registry.json").read_text(encoding="utf-8"))
    rows = []
    for task in sorted(metadata.task.unique()):
        frame, task_type = shared.load_task(task, registry)
        _, groups, keep = shared.featurize(frame.smiles)
        frame = frame.loc[keep].reset_index(drop=True)
        y = frame.y.to_numpy()
        for seed in SEEDS:
            splits, _ = shared.make_splits(y, groups, task_type, 3, seed)
            for fold, (train, test) in enumerate(splits, start=1):
                train_fps = [scaffold_fp(x) for x in sorted(set(groups[train]))]
                train_fps = [x for x in train_fps if x is not None]
                for idx in test:
                    fp = scaffold_fp(groups[idx])
                    similarity = max(DataStructs.BulkTanimotoSimilarity(fp, train_fps)) if fp is not None and train_fps else np.nan
                    rows.append({"task": task, "seed": seed, "outer_fold": fold, "sample_index": int(idx), "max_train_scaffold_tanimoto": similarity, "scaffold_relation": "seen_or_related_scaffold" if similarity >= .5 else "novel_scaffold"})
    return metadata.merge(pd.DataFrame(rows), on=["task", "seed", "outer_fold", "sample_index"], how="left")


def regression_support_metadata() -> pd.DataFrame:
    registry = json.loads((ROOT / "data" / "dataset_registry.json").read_text(encoding="utf-8"))
    rows = []
    for task in ["esol", "freesolv", "lipo", "tdc_caco2_wang"]:
        frame, task_type = shared.load_task(task, registry)
        parsed = [Chem.MolFromSmiles(s) for s in frame.smiles.astype(str)]
        keep = np.asarray([m is not None for m in parsed])
        frame = frame.loc[keep].reset_index(drop=True)
        molecules = [m for m in parsed if m is not None]
        groups = np.asarray(
            [MurckoScaffold.MurckoScaffoldSmiles(mol=m, includeChirality=False) or Chem.MolToSmiles(m, canonical=True) for m in molecules]
        )
        molecule_fps = [AllChem.GetMorganFingerprintAsBitVect(m, 2, nBits=512) for m in molecules]
        scaffold_fps = [scaffold_fp(s) for s in groups]
        y = frame.y.to_numpy()
        for seed in SEEDS:
            splits, _ = shared.make_splits(y, groups, task_type, 3, seed)
            for fold, (train, test) in enumerate(splits, start=1):
                train_molecule_fps = [molecule_fps[i] for i in train]
                train_scaffold_fps = [scaffold_fps[i] for i in train if scaffold_fps[i] is not None]
                for index in test:
                    similarity = max(DataStructs.BulkTanimotoSimilarity(molecule_fps[index], train_molecule_fps))
                    scaffold_similarity = (
                        max(DataStructs.BulkTanimotoSimilarity(scaffold_fps[index], train_scaffold_fps))
                        if scaffold_fps[index] is not None and train_scaffold_fps
                        else np.nan
                    )
                    rows.append(
                        {
                            "task": task,
                            "task_type": task_type,
                            "seed": seed,
                            "outer_fold": fold,
                            "sample_index": int(index),
                            "smiles": frame.smiles.iloc[index],
                            "y_true_from_registry": float(y[index]),
                            "max_train_tanimoto": similarity,
                            "tanimoto_bin": "<0.5" if similarity < .5 else "0.5-0.7" if similarity < .7 else ">0.7",
                            "scaffold": groups[index],
                            "scaffold_status": "seen_or_related_scaffold" if scaffold_similarity >= .5 else "novel_scaffold",
                            "max_train_scaffold_tanimoto": scaffold_similarity,
                            "scaffold_relation": "seen_or_related_scaffold" if scaffold_similarity >= .5 else "novel_scaffold",
                        }
                    )
    return pd.DataFrame(rows)


def performance(y: np.ndarray, p: np.ndarray, task_type: str) -> float:
    if task_type == "classification":
        return roc_auc_score(y, p) if len(np.unique(y)) == 2 else np.nan
    return math.sqrt(mean_squared_error(y, p))


def chemical_support_and_scaffold() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    class_predictions = pd.read_csv(HARD / "six_task_strong_baseline_outer_predictions.csv")
    class_predictions = class_predictions.loc[class_predictions.task_type.eq("classification")]
    class_metadata = pd.read_csv(UQ / "sample_scaffold_similarity_metadata.csv")
    class_metadata = add_scaffold_relatedness(class_metadata.loc[class_metadata.task_type.eq("classification")])
    class_selection = pd.read_csv(HARD / "six_task_strong_selection_detail.csv")
    class_selection = class_selection.loc[class_selection.task_type.eq("classification")]
    class_scores = pd.read_csv(HARD / "six_task_strong_baseline_outer_scores.csv")
    class_scores = class_scores.loc[class_scores.task_type.eq("classification")]

    regression_predictions = pd.read_csv(PREFIX_BASE / "regression_outer_predictions_all_candidates.csv.gz").rename(columns={"dataset": "task"})
    regression_metadata = regression_support_metadata()
    regression_selection_frames = []
    regression_score_frames = []
    for seed in SEEDS:
        selection_seed = pd.read_csv(PREFIX_BASE / f"seed_{seed}" / "policy_detail.csv").rename(columns={"dataset": "task"})
        selection_seed.insert(0, "seed", seed)
        regression_selection_frames.append(
            selection_seed.loc[
                selection_seed.task_type.eq("regression")
                & selection_seed.policy.eq("validation_best")
                & selection_seed.pool_size.eq(32)
            ]
        )
        score_seed = pd.read_csv(PREFIX_BASE / f"seed_{seed}" / "outer_candidate_scores.csv").rename(columns={"dataset": "task"})
        score_seed.insert(0, "seed", seed)
        regression_score_frames.append(score_seed.loc[score_seed.task_type.eq("regression")])
    regression_selection = pd.concat(regression_selection_frames, ignore_index=True)
    regression_scores = pd.concat(regression_score_frames, ignore_index=True)

    predictions = pd.concat([class_predictions, regression_predictions], ignore_index=True, sort=False)
    metadata = pd.concat([class_metadata, regression_metadata], ignore_index=True, sort=False)
    selection = pd.concat([class_selection, regression_selection], ignore_index=True, sort=False)
    scores = pd.concat([class_scores, regression_scores], ignore_index=True, sort=False)
    keys = ["task", "task_type", "seed", "outer_fold"]
    selection = selection[keys + ["selected_candidate"]]
    cross_rows = []
    for task in scores.task.unique():
        for held_seed in SEEDS:
            ref = scores.loc[(scores.task == task) & (scores.seed != held_seed)].groupby("candidate").outer_utility.mean().sort_values(ascending=False).index[0]
            cross_rows.append({"task": task, "seed": held_seed, "cross_reference_candidate": ref})
    cross = pd.DataFrame(cross_rows)
    pred = predictions.merge(metadata, on=["task", "task_type", "seed", "outer_fold", "sample_index", "smiles"], how="left")
    pred = pred.merge(selection, on=keys).merge(cross, on=["task", "seed"])
    selected = pred.loc[pred.candidate.eq(pred.selected_candidate)].copy().rename(columns={"y_pred": "selected_prediction"})
    reference = pred.loc[pred.candidate.eq(pred.cross_reference_candidate), keys + ["sample_index", "y_pred"]].rename(columns={"y_pred": "cross_reference_prediction"})
    sample = selected.merge(reference, on=keys + ["sample_index"])
    all_wide = pred.pivot_table(index=keys + ["sample_index"], columns="candidate", values="y_pred").reset_index()
    candidate_cols = [c for c in all_wide.columns if c not in keys + ["sample_index"]]
    all_wide["ensemble_std"] = all_wide[candidate_cols].std(axis=1)
    sample = sample.merge(all_wide[keys + ["sample_index", "ensemble_std"]], on=keys + ["sample_index"])
    sample["selected_abs_error"] = (sample.y_true - sample.selected_prediction).abs()
    sample["reference_abs_error"] = (sample.y_true - sample.cross_reference_prediction).abs()

    # Candidate-specific high-error flags use the 75th percentile within each outer unit.
    pred["abs_error"] = (pred.y_true - pred.y_pred).abs()
    pred["high_error"] = pred.groupby(keys + ["candidate"])["abs_error"].transform(lambda x: x >= x.quantile(.75))
    support_rows, scaffold_rows = [], []
    for group_cols, target_rows in [(["tanimoto_bin"], support_rows), (["scaffold_relation"], scaffold_rows)]:
        for key, group in sample.groupby(keys + group_cols):
            task, task_type, seed, fold = key[:4]
            stratum = key[4]
            unit_pred = pred.loc[(pred.task == task) & (pred.seed == seed) & (pred.outer_fold == fold) & pred.sample_index.isin(group.sample_index)]
            overlaps, disagreements = [], []
            for a, b in itertools.combinations(sorted(unit_pred.candidate.unique()), 2):
                wa = unit_pred.loc[unit_pred.candidate.eq(a)].set_index("sample_index")
                wb = unit_pred.loc[unit_pred.candidate.eq(b)].set_index("sample_index")
                common = wa.index.intersection(wb.index)
                ea = wa.loc[common, "high_error"].to_numpy(bool); eb = wb.loc[common, "high_error"].to_numpy(bool)
                union = (ea | eb).sum(); overlaps.append((ea & eb).sum() / union if union else np.nan)
                if task_type == "classification": disagreements.append(((wa.loc[common, "y_pred"] >= .5) != (wb.loc[common, "y_pred"] >= .5)).mean())
                else:
                    denom = np.subtract(*np.percentile(group.y_true, [75, 25])) or 1.0
                    disagreements.append(np.mean(np.abs(wa.loc[common, "y_pred"] - wb.loc[common, "y_pred"])) / denom)
            selected_perf = performance(group.y_true.to_numpy(), group.selected_prediction.to_numpy(), task_type)
            ref_perf = performance(group.y_true.to_numpy(), group.cross_reference_prediction.to_numpy(), task_type)
            rho = spearmanr(group.ensemble_std, group.selected_abs_error, nan_policy="omit").statistic if len(group) >= 4 else np.nan
            full_unit = sample.loc[(sample.task == task) & (sample.seed == seed) & (sample.outer_fold == fold)]
            if task_type == "classification":
                fn = ((group.y_true == 1) & (group.selected_prediction < .5)).sum()
                positives = (group.y_true == 1).sum()
                fnr = fn / positives if positives else np.nan
                fn_all = ((full_unit.y_true == 1) & (full_unit.selected_prediction < .5)).sum()
                pos_all = (full_unit.y_true == 1).sum()
                overall_fnr = fn_all / pos_all if pos_all else np.nan
                fn_enrichment = fnr / overall_fnr if overall_fnr and np.isfinite(overall_fnr) else np.nan
            else:
                fnr = fn_enrichment = np.nan
            high_rate = unit_pred.groupby("candidate").high_error.mean().mean()
            full_pred = pred.loc[(pred.task == task) & (pred.seed == seed) & (pred.outer_fold == fold)]
            overall_high = full_pred.groupby("candidate").high_error.mean().mean()
            target_rows.append({
                "task": task, "task_type": task_type, "seed": seed, "outer_fold": fold,
                group_cols[0]: stratum, "n": len(group), "selected_performance": selected_perf,
                "cross_reference_performance": ref_perf,
                "selected_minus_reference": selected_perf - ref_perf,
                "mean_pairwise_high_error_jaccard": np.nanmean(overlaps),
                "mean_model_disagreement": np.nanmean(disagreements),
                "uncertainty_error_spearman": rho, "false_negative_rate": fnr,
                "false_negative_enrichment": fn_enrichment,
                "high_error_enrichment": high_rate / overall_high if overall_high else np.nan,
            })

    diversity_rows, matrices = [], []
    for (task, task_type, seed, fold), group in pred.groupby(keys):
        wide = group.pivot_table(index="sample_index", columns="candidate", values="y_pred")
        errors = group.assign(error=group.y_true - group.y_pred).pivot_table(index="sample_index", columns="candidate", values="error")
        pm = entropy_metrics(wide.to_numpy(float)); em = entropy_metrics(errors.to_numpy(float))
        utility_group = scores.loc[(scores.task == task) & (scores.seed == seed) & (scores.outer_fold == fold)].sort_values("candidate")
        utility_rank = rankdata(-utility_group.outer_utility.to_numpy(float))
        pred_variance_rank = rankdata(-wide.var(axis=0).sort_index().to_numpy(float))
        diversity_rows.append({"task": task, "task_type": task_type, "seed": seed, "outer_fold": fold, **{f"prediction_{k}": v for k, v in pm.items()}, **{f"error_{k}": v for k, v in em.items()}, "utility_vs_prediction_variance_rank_spearman": spearmanr(utility_rank, pred_variance_rank).statistic})
        corr = np.corrcoef(wide.to_numpy(float), rowvar=False)
        for i, a in enumerate(wide.columns):
            for j, b in enumerate(wide.columns): matrices.append({"task": task, "seed": seed, "outer_fold": fold, "candidate_a": a, "candidate_b": b, "prediction_correlation": corr[i, j]})
    return pd.DataFrame(support_rows), pd.DataFrame(scaffold_rows), pd.DataFrame(diversity_rows), pd.DataFrame(matrices)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    split_detail, split_summary = seed_split_audit()
    cross_summary, cross_folds = cross_fitted_intervals()
    subset_units, subset_summary, subset_selection = matched_k3_all_subsets()
    support, scaffold, pred_diversity, pred_corr = chemical_support_and_scaffold()
    outputs = {
        "seed_split_prediction_audit_detail.csv": split_detail,
        "seed_split_prediction_audit_summary.csv": split_summary,
        "cross_fitted_complete_intervals.csv": cross_summary,
        "cross_fitted_fold_effects.csv": cross_folds,
        "matched_k3_220_subset_units.csv": subset_units,
        "matched_k3_220_subset_summary.csv": subset_summary,
        "matched_k3_220_selection_frequency.csv": subset_selection,
        "chemical_support_selection_audit.csv": support,
        "scaffold_novelty_error_complementarity.csv": scaffold,
        "prediction_level_effective_diversity.csv": pred_diversity,
        "prediction_correlation_long.csv": pred_corr,
    }
    for name, frame in outputs.items(): frame.to_csv(OUT / name, index=False)
    audit = {
        "analysis_date": "2026-07-13", "fixed_seed": RNG_SEED,
        "matched_k3_subsets": math.comb(12, 3),
        "outputs": {name: {"rows": len(frame), "sha256": hashlib.sha256((OUT / name).read_bytes()).hexdigest()} for name, frame in outputs.items()},
        "limitations": [
            "Five seeded scaffold partitions are distinct for both classification and regression; outer folds remain paired partitions rather than independent biological experiments.",
            "CAHit@3 is not estimable for K=3 because both observed and random Hit@3 equal one.",
            "Scaffold relatedness uses maximum Morgan Tanimoto between held-out and training Murcko scaffolds with a predefined 0.5 threshold; exact scaffolds are held out.",
            "Prediction-level diversity in the main boundary panel remains limited to the four-model six-task panel; the new 32-candidate molecule-level exports are reported separately.",
        ],
    }
    (OUT / "p0_expanded_analysis_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(OUT), "rows": {k: len(v) for k, v in outputs.items()}}, indent=2))


if __name__ == "__main__":
    main()
