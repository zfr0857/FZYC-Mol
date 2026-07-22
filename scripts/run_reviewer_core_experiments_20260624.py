from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "reviewer_core_20260624"
SEEDS = [11, 23, 37, 53, 71]
POOL_SIZES = [4, 8, 16, 32]
SIGNALS = [0.0, 0.10, 0.25, 0.50, 0.75, 1.0]
RNG_SEED = 20260624


def percentile_interval(values: np.ndarray) -> tuple[float, float]:
    return tuple(np.quantile(values, [0.025, 0.975]).astype(float))


def endpoint_bootstrap(
    frame: pd.DataFrame,
    value_col: str,
    reps: int = 10_000,
    seed: int = RNG_SEED,
) -> tuple[float, float]:
    endpoint_values = {
        endpoint: group[value_col].to_numpy(float)
        for endpoint, group in frame.groupby("endpoint", sort=True)
    }
    endpoints = list(endpoint_values)
    rng = np.random.default_rng(seed)
    draws = np.empty(reps, dtype=float)
    for i in range(reps):
        sampled = rng.choice(endpoints, size=len(endpoints), replace=True)
        draws[i] = np.mean(np.concatenate([endpoint_values[e] for e in sampled]))
    return percentile_interval(draws)


def exact_sign_flip_p(endpoint_effects: np.ndarray) -> float:
    effects = np.asarray(endpoint_effects, dtype=float)
    observed = abs(float(effects.mean()))
    null = []
    for signs in itertools.product([-1.0, 1.0], repeat=len(effects)):
        null.append(abs(float(np.mean(effects * np.asarray(signs)))))
    return float(np.mean(np.asarray(null) >= observed - 1e-15))


def holm_adjust(p_values: list[float]) -> list[float]:
    order = np.argsort(p_values)
    adjusted = np.empty(len(p_values), dtype=float)
    running = 0.0
    n = len(p_values)
    for rank, idx in enumerate(order):
        running = max(running, (n - rank) * p_values[idx])
        adjusted[idx] = min(1.0, running)
    return adjusted.tolist()


def paired_pool_effects() -> dict[str, object]:
    regret = pd.read_csv(ROOT / "results" / "nested_selection" / "repeated_regret_decomposition.csv")
    ranking = pd.read_csv(ROOT / "results" / "nested_selection" / "repeated_ranking_metrics_long.csv")
    keys = ["endpoint", "repeat", "outer_fold", "repeat_seed", "pool_size"]
    data = regret[keys + ["fixed_normalized_regret"]].merge(
        ranking[keys + ["chance_adjusted_hit", "mrr", "ndcg", "spearman"]],
        on=keys,
        validate="one_to_one",
    )
    unit_keys = ["endpoint", "repeat", "outer_fold", "repeat_seed"]
    rows: list[dict[str, object]] = []
    endpoint_rows: list[dict[str, object]] = []
    metrics = ["fixed_normalized_regret", "chance_adjusted_hit", "mrr"]
    for metric in metrics:
        wide = data.pivot(index=unit_keys, columns="pool_size", values=metric).reset_index()
        for pool_size in [8, 16, 32]:
            effect_name = f"{pool_size}_minus_4"
            wide[effect_name] = wide[pool_size] - wide[4]
            endpoint = wide.groupby("endpoint", as_index=False)[effect_name].mean()
            endpoint["metric"] = metric
            endpoint["comparison"] = f"K={pool_size} vs K=4"
            endpoint_rows.extend(endpoint.to_dict("records"))
            low, high = endpoint_bootstrap(wide, effect_name)
            endpoint_effects = endpoint[effect_name].to_numpy(float)
            expected = endpoint_effects > 0 if metric == "fixed_normalized_regret" else endpoint_effects < 0
            rows.append(
                {
                    "metric": metric,
                    "comparison": f"K={pool_size} vs K=4",
                    "paired_units": len(wide),
                    "endpoints": endpoint["endpoint"].nunique(),
                    "mean_paired_effect": float(wide[effect_name].mean()),
                    "endpoint_cluster_ci95_low": low,
                    "endpoint_cluster_ci95_high": high,
                    "endpoint_median_effect": float(np.median(endpoint_effects)),
                    "endpoints_in_expected_direction": int(expected.sum()),
                    "exact_sign_flip_p": exact_sign_flip_p(endpoint_effects),
                }
            )
    summary = pd.DataFrame(rows)
    summary["holm_p_across_9_tests"] = holm_adjust(summary["exact_sign_flip_p"].tolist())
    pd.DataFrame(endpoint_rows).to_csv(OUT / "paired_pool_endpoint_effects.csv", index=False)
    summary.to_csv(OUT / "paired_pool_effects.csv", index=False)
    return {
        "k32_vs_k4_fixed_regret": summary.query(
            "metric == 'fixed_normalized_regret' and comparison == 'K=32 vs K=4'"
        ).iloc[0].to_dict(),
        "k32_vs_k4_chance_hit": summary.query(
            "metric == 'chance_adjusted_hit' and comparison == 'K=32 vs K=4'"
        ).iloc[0].to_dict(),
    }


def risk_validation() -> dict[str, object]:
    data = pd.read_csv(ROOT / "results" / "selection_closure" / "selection_risk_units.csv")
    components = [
        "ambiguity_component",
        "instability_component",
        "variability_component",
        "selection_risk",
    ]
    rng = np.random.default_rng(RNG_SEED)
    endpoints = sorted(data["endpoint"].unique())
    endpoint_indices = [np.flatnonzero(data["endpoint"].to_numpy() == endpoint) for endpoint in endpoints]
    permutation_indices = [
        group.index.to_numpy()
        for _, group in data.groupby(["endpoint", "pool_size"], sort=True)
    ]
    regret = data["fixed_normalized_regret"].to_numpy(float)
    component_rows: list[dict[str, object]] = []
    for component in components:
        score = data[component].to_numpy(float)
        observed = float(spearmanr(score, regret).statistic)
        boots = []
        for _ in range(5000):
            sampled = rng.integers(0, len(endpoint_indices), size=len(endpoint_indices))
            indices = np.concatenate([endpoint_indices[i] for i in sampled])
            boots.append(float(spearmanr(score[indices], regret[indices]).statistic))
        null = []
        for _ in range(5000):
            shuffled = regret.copy()
            for indices in permutation_indices:
                shuffled[indices] = rng.permutation(regret[indices])
            null.append(float(spearmanr(score, shuffled).statistic))
        low, high = percentile_interval(np.asarray(boots))
        p_perm = (1 + int(np.sum(np.asarray(null) >= observed))) / (len(null) + 1)
        component_rows.append(
            {
                "component": component,
                "spearman": observed,
                "endpoint_bootstrap_ci95_low": low,
                "endpoint_bootstrap_ci95_high": high,
                "within_endpoint_pool_permutation_p_one_sided": p_perm,
            }
        )
    pd.DataFrame(component_rows).to_csv(OUT / "risk_component_summary.csv", index=False)

    quartiles = data.copy()
    quartiles["risk_quartile"] = pd.qcut(
        quartiles["selection_risk"], 4, labels=["Q1 low", "Q2", "Q3", "Q4 high"]
    )
    quartile_summary = quartiles.groupby("risk_quartile", observed=True, as_index=False).agg(
        n=("fixed_normalized_regret", "size"),
        mean_risk=("selection_risk", "mean"),
        mean_regret=("fixed_normalized_regret", "mean"),
        median_regret=("fixed_normalized_regret", "median"),
    )
    quartile_summary.to_csv(OUT / "risk_quartiles.csv", index=False)

    loeo_rows: list[dict[str, object]] = []
    endpoint_rows: list[dict[str, object]] = []
    for held in endpoints:
        train = data[~data["endpoint"].eq(held)]
        test = data[data["endpoint"].eq(held)].copy()
        calibrator = IsotonicRegression(out_of_bounds="clip", increasing=True)
        calibrator.fit(train["selection_risk"], train["fixed_normalized_regret"])
        test["predicted_regret"] = calibrator.predict(test["selection_risk"])
        test["baseline_predicted_regret"] = float(train["fixed_normalized_regret"].mean())
        test["held_endpoint"] = held
        loeo_rows.extend(test.to_dict("records"))
        threshold = float(train["selection_risk"].median())
        retained = test[test["selection_risk"] <= threshold]
        q75 = float(train["fixed_normalized_regret"].quantile(0.75))
        high = (test["fixed_normalized_regret"] >= q75).astype(int)
        auc = float(roc_auc_score(high, test["predicted_regret"])) if high.nunique() == 2 else np.nan
        endpoint_rows.append(
            {
                "endpoint": held,
                "n": len(test),
                "loeo_mae": float(mean_absolute_error(test["fixed_normalized_regret"], test["predicted_regret"])),
                "constant_baseline_mae": float(mean_absolute_error(test["fixed_normalized_regret"], test["baseline_predicted_regret"])),
                "high_regret_auc": auc,
                "risk_gate_threshold_from_other_endpoints": threshold,
                "risk_gate_coverage": len(retained) / len(test),
                "all_mean_regret": float(test["fixed_normalized_regret"].mean()),
                "retained_mean_regret": float(retained["fixed_normalized_regret"].mean()),
                "risk_gate_delta": float(retained["fixed_normalized_regret"].mean() - test["fixed_normalized_regret"].mean()),
            }
        )
    loeo = pd.DataFrame(loeo_rows)
    endpoint_summary = pd.DataFrame(endpoint_rows)
    loeo.to_csv(OUT / "risk_loeo_predictions.csv", index=False)
    endpoint_summary.to_csv(OUT / "risk_loeo_endpoint_summary.csv", index=False)
    delta_low, delta_high = endpoint_bootstrap(
        endpoint_summary.rename(columns={"endpoint": "endpoint"}), "risk_gate_delta", reps=10_000
    )
    overall = {
        "n_predictions": len(loeo),
        "loeo_mae": float(mean_absolute_error(loeo["fixed_normalized_regret"], loeo["predicted_regret"])),
        "constant_baseline_mae": float(
            mean_absolute_error(loeo["fixed_normalized_regret"], loeo["baseline_predicted_regret"])
        ),
        "loeo_spearman": float(spearmanr(loeo["predicted_regret"], loeo["fixed_normalized_regret"]).statistic),
        "mean_high_regret_auc": float(endpoint_summary["high_regret_auc"].mean()),
        "risk_gate_mean_delta": float(endpoint_summary["risk_gate_delta"].mean()),
        "risk_gate_endpoint_bootstrap_ci95_low": delta_low,
        "risk_gate_endpoint_bootstrap_ci95_high": delta_high,
        "endpoints_with_lower_retained_regret": int((endpoint_summary["risk_gate_delta"] < 0).sum()),
    }
    (OUT / "risk_loeo_summary.json").write_text(json.dumps(overall, indent=2), encoding="utf-8")
    return {
        "components": component_rows,
        "quartiles": quartile_summary.to_dict("records"),
        "loeo": overall,
    }


def build_validation_feature_table() -> pd.DataFrame:
    risk = pd.read_csv(ROOT / "results" / "selection_closure" / "selection_risk_units.csv")
    rows: list[dict[str, object]] = []
    for repeat, seed in enumerate(SEEDS, start=1):
        task_root = ROOT / "results" / "nested_selection" / "repeated_nested" / f"seed_{seed}" / "tasks"
        for task_dir in sorted(p for p in task_root.iterdir() if p.is_dir()):
            inner_path = task_dir / "inner_scores.csv"
            if not inner_path.exists():
                continue
            inner = pd.read_csv(inner_path)
            endpoint = task_dir.name
            for outer_fold, outer_group in inner.groupby("outer_fold", sort=True):
                for pool_size in POOL_SIZES:
                    pool = outer_group[outer_group["candidate_order"] <= pool_size].copy()
                    means = pool.groupby("candidate", sort=False)["inner_utility"].mean().sort_values(ascending=False)
                    sds = pool.groupby("candidate", sort=False)["inner_utility"].std(ddof=1).reindex(means.index)
                    top_gap = float(means.iloc[0] - means.iloc[1]) if len(means) > 1 else 0.0
                    score_sd = max(float(means.std(ddof=0)), 1e-12)
                    pivot = pool.pivot(index="candidate", columns="inner_fold", values="inner_utility")
                    rank_corr = pivot.corr(method="spearman").to_numpy(float)
                    off_diagonal = rank_corr[np.triu_indices_from(rank_corr, k=1)]
                    winners = []
                    winner_families = []
                    for _, fold in pool.groupby("inner_fold", sort=True):
                        winner = fold.sort_values(["inner_utility", "candidate_order"], ascending=[False, True]).iloc[0]
                        winners.append(str(winner["candidate"]))
                        winner_families.append(str(winner["family"]))
                    winner_frequency = max(pd.Series(winners).value_counts(normalize=True))
                    rows.append(
                        {
                            "endpoint": endpoint,
                            "repeat": repeat,
                            "repeat_seed": seed,
                            "outer_fold": int(outer_fold),
                            "pool_size": pool_size,
                            "is_classification": int(str(pool["task_type"].iloc[0]) == "classification"),
                            "log2_pool_size": float(np.log2(pool_size)),
                            "candidate_score_sd": float(means.std(ddof=0)),
                            "normalized_top_gap": top_gap / score_sd,
                            "top_candidate_sd": float(sds.iloc[0]),
                            "mean_candidate_sd": float(sds.mean()),
                            "sd_to_dispersion": float(sds.mean()) / score_sd,
                            "inner_rank_agreement": float(np.nanmean(off_diagonal)),
                            "fold_winner_frequency": float(winner_frequency),
                            "fold_winner_family_count": len(set(winner_families)),
                        }
                    )
    features = pd.DataFrame(rows)
    merge_keys = ["endpoint", "repeat", "repeat_seed", "outer_fold", "pool_size"]
    table = features.merge(risk, on=merge_keys, validate="one_to_one")
    table.to_csv(OUT / "cross_endpoint_risk_features.csv", index=False)
    return table


def cross_endpoint_meta_risk() -> dict[str, object]:
    data = build_validation_feature_table()
    feature_cols = [
        "is_classification",
        "log2_pool_size",
        "candidate_score_sd",
        "normalized_top_gap",
        "top_candidate_sd",
        "mean_candidate_sd",
        "sd_to_dispersion",
        "inner_rank_agreement",
        "fold_winner_frequency",
        "fold_winner_family_count",
        "one_se_size",
        "selection_frequency",
        "fold_variability",
        "ambiguity_component",
        "instability_component",
        "variability_component",
    ]
    models = {
        "ridge": make_pipeline(StandardScaler(), Ridge(alpha=10.0)),
        "random_forest": RandomForestRegressor(
            n_estimators=500,
            max_depth=4,
            min_samples_leaf=15,
            max_features=0.7,
            random_state=RNG_SEED,
            n_jobs=-1,
        ),
        "hist_gradient_boosting": HistGradientBoostingRegressor(
            max_iter=150,
            learning_rate=0.04,
            max_depth=3,
            min_samples_leaf=20,
            l2_regularization=10.0,
            random_state=RNG_SEED,
        ),
    }
    endpoints = sorted(data["endpoint"].unique())
    prediction_rows: list[dict[str, object]] = []
    selection_rows: list[dict[str, object]] = []
    for held in endpoints:
        train = data[~data["endpoint"].eq(held)].copy()
        test = data[data["endpoint"].eq(held)].copy()
        cv_mae: dict[str, float] = {}
        for name, model in models.items():
            fold_mae = []
            for validation_endpoint in sorted(train["endpoint"].unique()):
                fit = train[~train["endpoint"].eq(validation_endpoint)]
                valid = train[train["endpoint"].eq(validation_endpoint)]
                fitted = clone(model).fit(fit[feature_cols], fit["fixed_normalized_regret"])
                pred = np.clip(fitted.predict(valid[feature_cols]), 0.0, 1.0)
                fold_mae.append(mean_absolute_error(valid["fixed_normalized_regret"], pred))
            cv_mae[name] = float(np.mean(fold_mae))
        selected_name = min(cv_mae, key=cv_mae.get)
        selected_model = clone(models[selected_name]).fit(train[feature_cols], train["fixed_normalized_regret"])
        test["predicted_regret"] = np.clip(selected_model.predict(test[feature_cols]), 0.0, 1.0)
        test["baseline_predicted_regret"] = float(train["fixed_normalized_regret"].mean())
        test["selected_model"] = selected_name
        test["held_endpoint"] = held
        prediction_rows.extend(test.to_dict("records"))
        selection_rows.append(
            {
                "held_endpoint": held,
                "selected_model": selected_name,
                **{f"inner_loeo_mae_{name}": value for name, value in cv_mae.items()},
            }
        )
    predictions = pd.DataFrame(prediction_rows)
    model_selection = pd.DataFrame(selection_rows)
    predictions.to_csv(OUT / "cross_endpoint_meta_risk_predictions.csv", index=False)
    model_selection.to_csv(OUT / "cross_endpoint_meta_risk_model_selection.csv", index=False)
    endpoint_rows = []
    for held, test in predictions.groupby("held_endpoint", sort=True):
        retained = test.nsmallest(max(1, len(test) // 2), "predicted_regret")
        train = data[~data["endpoint"].eq(held)]
        q75 = float(train["fixed_normalized_regret"].quantile(0.75))
        high = (test["fixed_normalized_regret"] >= q75).astype(int)
        endpoint_rows.append(
            {
                "endpoint": held,
                "selected_model": test["selected_model"].iloc[0],
                "mae": float(mean_absolute_error(test["fixed_normalized_regret"], test["predicted_regret"])),
                "baseline_mae": float(mean_absolute_error(test["fixed_normalized_regret"], test["baseline_predicted_regret"])),
                "high_regret_auc": float(roc_auc_score(high, test["predicted_regret"])) if high.nunique() == 2 else np.nan,
                "retained_coverage": len(retained) / len(test),
                "all_mean_regret": float(test["fixed_normalized_regret"].mean()),
                "retained_mean_regret": float(retained["fixed_normalized_regret"].mean()),
                "risk_gate_delta": float(retained["fixed_normalized_regret"].mean() - test["fixed_normalized_regret"].mean()),
            }
        )
    endpoint_summary = pd.DataFrame(endpoint_rows)
    endpoint_summary.to_csv(OUT / "cross_endpoint_meta_risk_endpoint_summary.csv", index=False)
    low, high = endpoint_bootstrap(endpoint_summary, "risk_gate_delta", reps=10_000)
    result = {
        "n_predictions": len(predictions),
        "loeo_mae": float(mean_absolute_error(predictions["fixed_normalized_regret"], predictions["predicted_regret"])),
        "constant_baseline_mae": float(mean_absolute_error(predictions["fixed_normalized_regret"], predictions["baseline_predicted_regret"])),
        "loeo_spearman": float(spearmanr(predictions["predicted_regret"], predictions["fixed_normalized_regret"]).statistic),
        "mean_high_regret_auc": float(endpoint_summary["high_regret_auc"].mean()),
        "risk_gate_mean_delta": float(endpoint_summary["risk_gate_delta"].mean()),
        "risk_gate_endpoint_bootstrap_ci95_low": low,
        "risk_gate_endpoint_bootstrap_ci95_high": high,
        "endpoints_with_lower_retained_regret": int((endpoint_summary["risk_gate_delta"] < 0).sum()),
        "selected_model_counts": model_selection["selected_model"].value_counts().to_dict(),
    }
    (OUT / "cross_endpoint_meta_risk_summary.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def load_outer_utilities() -> pd.DataFrame:
    rows = []
    for repeat, seed in enumerate(SEEDS, start=1):
        task_root = ROOT / "results" / "nested_selection" / "repeated_nested" / f"seed_{seed}" / "tasks"
        for task_dir in sorted(p for p in task_root.iterdir() if p.is_dir()):
            path = task_dir / "outer_candidate_scores.csv"
            if not path.exists():
                continue
            frame = pd.read_csv(path)
            frame["endpoint"] = frame["dataset"]
            frame["repeat"] = repeat
            frame["repeat_seed"] = seed
            rows.append(frame)
    data = pd.concat(rows, ignore_index=True)
    expected = 9 * 5 * 3 * 32
    if len(data) != expected:
        raise RuntimeError(f"Expected {expected} outer candidate rows, found {len(data)}")
    return data


def signal_recovery() -> dict[str, object]:
    outer = load_outer_utilities()
    rng = np.random.default_rng(RNG_SEED)
    rows: list[dict[str, object]] = []
    unit_keys = ["endpoint", "repeat", "repeat_seed", "outer_fold"]
    for keys, unit in outer.groupby(unit_keys, sort=True):
        unit = unit.sort_values("candidate_order")
        full = unit["outer_utility"].to_numpy(float)
        full_range = max(float(full.max() - full.min()), 1e-12)
        endpoint, repeat, seed, outer_fold = keys
        for pool_size in POOL_SIZES:
            utility = full[:pool_size]
            oracle = int(np.argmax(utility))
            z = (utility - utility.mean()) / max(float(utility.std(ddof=0)), 1e-12)
            chance = min(3, pool_size) / pool_size
            for signal in SIGNALS:
                reps = 1 if signal == 1.0 else 500
                noise = rng.normal(size=(reps, pool_size))
                scores = signal * z[None, :] + np.sqrt(max(0.0, 1.0 - signal**2)) * noise
                order = np.argsort(-scores, axis=1)
                ranks = np.argmax(order == oracle, axis=1) + 1
                selected = order[:, 0]
                top3_values = (ranks <= min(3, pool_size)).astype(float)
                adjusted_values = (top3_values - chance) / max(1.0 - chance, 1e-12)
                mrr_values = 1.0 / ranks
                regret_values = (utility[oracle] - utility[selected]) / full_range
                rows.append(
                    {
                        "endpoint": endpoint,
                        "repeat": repeat,
                        "repeat_seed": seed,
                        "outer_fold": outer_fold,
                        "pool_size": pool_size,
                        "signal_correlation": signal,
                        "simulation_replicates": reps,
                        "top3_hit": float(np.mean(top3_values)),
                        "chance_adjusted_hit": float(np.mean(adjusted_values)),
                        "mrr": float(np.mean(mrr_values)),
                        "fixed_normalized_regret": float(np.mean(regret_values)),
                    }
                )
    unit_summary = pd.DataFrame(rows)
    unit_summary.to_csv(OUT / "signal_recovery_units.csv", index=False)
    summary_rows: list[dict[str, object]] = []
    for (pool_size, signal), group in unit_summary.groupby(["pool_size", "signal_correlation"], sort=True):
        row: dict[str, object] = {"pool_size": pool_size, "signal_correlation": signal, "n_outer_units": len(group)}
        for metric in ["chance_adjusted_hit", "mrr", "fixed_normalized_regret"]:
            low, high = endpoint_bootstrap(group, metric, reps=5000, seed=RNG_SEED + int(pool_size * 100 + signal * 100))
            row[f"{metric}_mean"] = float(group[metric].mean())
            row[f"{metric}_ci95_low"] = low
            row[f"{metric}_ci95_high"] = high
        summary_rows.append(row)
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(OUT / "signal_recovery_summary.csv", index=False)
    monotonic = {}
    for pool_size, group in summary.groupby("pool_size"):
        ordered = group.sort_values("signal_correlation")
        monotonic[str(pool_size)] = {
            "chance_adjusted_hit_non_decreasing": bool(np.all(np.diff(ordered["chance_adjusted_hit_mean"]) >= -1e-12)),
            "mrr_non_decreasing": bool(np.all(np.diff(ordered["mrr_mean"]) >= -1e-12)),
            "regret_non_increasing": bool(np.all(np.diff(ordered["fixed_normalized_regret_mean"]) <= 1e-12)),
        }
    null = summary[summary["signal_correlation"].eq(0.0)]
    full = summary[summary["signal_correlation"].eq(1.0)]
    return {
        "monotonicity": monotonic,
        "null_max_abs_chance_adjusted_hit": float(null["chance_adjusted_hit_mean"].abs().max()),
        "full_signal_max_regret": float(full["fixed_normalized_regret_mean"].max()),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    values = {
        "paired_pool_effects": paired_pool_effects(),
        "risk_validation": risk_validation(),
        "cross_endpoint_meta_risk": cross_endpoint_meta_risk(),
        "signal_recovery": signal_recovery(),
    }
    (OUT / "reviewer_core_values.json").write_text(
        json.dumps(values, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(values, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
