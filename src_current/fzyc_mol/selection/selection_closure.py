from __future__ import annotations

import json
import math
from collections.abc import Iterable

import numpy as np
import pandas as pd


UNIT_KEYS = ["endpoint", "repeat", "outer_fold", "repeat_seed", "split_id", "pool_size"]


def _diagnostic_value(payload: object, key: str) -> float:
    if payload is None or (isinstance(payload, float) and np.isnan(payload)):
        return float("nan")
    items = json.loads(str(payload))
    values = dict(items)
    value = values.get(key, float("nan"))
    return float(value) if value is not None else float("nan")


def _one_se_size(value: object) -> int:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return 0
    return len([item for item in str(value).split(";") if item.strip()])


def build_selection_risk_frame(nested: pd.DataFrame, regret: pd.DataFrame) -> pd.DataFrame:
    """Build a validation-side risk score and attach frozen outer regret for audit.

    The score itself uses only one-SE ambiguity, inner-fold selection frequency,
    and inner-fold variability. Outer regret is joined afterwards and is never an
    input to the score.
    """

    missing_nested = set(UNIT_KEYS + ["one_se_candidates", "selection_reason"]) - set(nested.columns)
    missing_regret = set(UNIT_KEYS + ["fixed_normalized_regret"]) - set(regret.columns)
    if missing_nested or missing_regret:
        raise ValueError(
            f"missing columns: nested={sorted(missing_nested)}, regret={sorted(missing_regret)}"
        )

    risk = nested[UNIT_KEYS + ["one_se_candidates", "selection_reason"]].copy()
    risk["one_se_size"] = risk["one_se_candidates"].map(_one_se_size)
    risk["selection_frequency"] = risk["selection_reason"].map(
        lambda value: _diagnostic_value(value, "selection_frequency")
    )
    risk["fold_variability"] = risk["selection_reason"].map(
        lambda value: _diagnostic_value(value, "fold_variability")
    )

    denominator = (risk["pool_size"].astype(float) - 1.0).clip(lower=1.0)
    risk["ambiguity_component"] = ((risk["one_se_size"] - 1).clip(lower=0) / denominator).clip(0, 1)
    risk["instability_component"] = (1.0 - risk["selection_frequency"].clip(0, 1)).fillna(1.0)
    group_cols = ["endpoint", "pool_size"]
    risk["variability_component"] = (
        risk.groupby(group_cols, dropna=False)["fold_variability"]
        .rank(method="average", pct=True, na_option="bottom")
        .fillna(1.0)
    )
    risk["selection_risk"] = risk[
        ["ambiguity_component", "instability_component", "variability_component"]
    ].mean(axis=1)

    audit = regret[UNIT_KEYS + ["fixed_normalized_regret"]].copy()
    return risk.merge(audit, on=UNIT_KEYS, how="inner", validate="one_to_one")


def selection_risk_curve(
    frame: pd.DataFrame, coverages: Iterable[float] | None = None
) -> pd.DataFrame:
    """Return mean outer regret after retaining the lowest validation-side risk."""

    if coverages is None:
        coverages = np.linspace(0.1, 1.0, 10)
    clean = frame.dropna(subset=["selection_risk", "fixed_normalized_regret"]).sort_values(
        "selection_risk", kind="mergesort"
    )
    if clean.empty:
        raise ValueError("no complete selection-risk rows")
    rows = []
    for coverage in coverages:
        coverage = float(coverage)
        if not 0 < coverage <= 1:
            raise ValueError("coverage must be in (0, 1]")
        keep = max(1, min(len(clean), math.ceil(coverage * len(clean))))
        selected = clean.iloc[:keep]
        rows.append(
            {
                "coverage": coverage,
                "n_retained": keep,
                "mean_regret": float(selected["fixed_normalized_regret"].mean()),
                "median_regret": float(selected["fixed_normalized_regret"].median()),
                "risk_threshold": float(selected["selection_risk"].max()),
            }
        )
    return pd.DataFrame(rows)


def permutation_null_for_unit(
    validation_utility: np.ndarray,
    outer_utility: np.ndarray,
    n_permutations: int = 1000,
    seed: int = 0,
) -> pd.DataFrame:
    """Destroy validation-to-outer alignment while preserving both marginals."""

    validation = np.asarray(validation_utility, dtype=float)
    outer = np.asarray(outer_utility, dtype=float)
    if validation.ndim != 1 or outer.ndim != 1 or len(validation) != len(outer):
        raise ValueError("validation_utility and outer_utility must be aligned one-dimensional arrays")
    if len(validation) < 2 or n_permutations < 1:
        raise ValueError("at least two candidates and one permutation are required")
    if not (np.isfinite(validation).all() and np.isfinite(outer).all()):
        raise ValueError("utilities must be finite")

    rng = np.random.default_rng(seed)
    oracle = int(np.argmax(outer))
    k_top = min(3, len(validation))
    chance = k_top / len(validation)
    full_range = float(np.max(outer) - np.min(outer))
    rows = []
    for permutation in range(n_permutations):
        permuted = rng.permutation(validation)
        selected = int(np.argmax(permuted))
        top = np.argpartition(permuted, -k_top)[-k_top:]
        hit = float(oracle in top)
        chance_adjusted = 1.0 if chance == 1.0 else (hit - chance) / (1.0 - chance)
        regret = float(np.max(outer) - outer[selected])
        normalized = 0.0 if full_range <= 0 else regret / full_range
        rows.append(
            {
                "permutation": permutation,
                "selected_index": selected,
                "top3_hit": hit,
                "chance_adjusted_top3_hit": chance_adjusted,
                "fixed_normalized_regret": normalized,
            }
        )
    return pd.DataFrame(rows)


def leave_one_endpoint_out_policy(governance: pd.DataFrame) -> pd.DataFrame:
    """Select a governance rule on all other endpoints and audit the held endpoint."""

    required = {"endpoint", "variant", "full32_fixed_normalized_regret"}
    missing = required - set(governance.columns)
    if missing:
        raise ValueError(f"missing columns: {sorted(missing)}")
    endpoint_rule = (
        governance.groupby(["endpoint", "variant"], as_index=False)[
            "full32_fixed_normalized_regret"
        ].mean()
    )
    endpoints = sorted(endpoint_rule["endpoint"].unique())
    rows = []
    for held in endpoints:
        train = endpoint_rule.loc[endpoint_rule["endpoint"] != held]
        train_mean = (
            train.groupby("variant")["full32_fixed_normalized_regret"].mean().sort_values(kind="mergesort")
        )
        selected = str(train_mean.index[0])
        held_frame = endpoint_rule.loc[endpoint_rule["endpoint"] == held].set_index("variant")
        oracle_variant = str(held_frame["full32_fixed_normalized_regret"].idxmin())
        rows.append(
            {
                "held_endpoint": held,
                "selected_variant": selected,
                "training_mean_regret": float(train_mean.iloc[0]),
                "heldout_regret": float(
                    held_frame.loc[selected, "full32_fixed_normalized_regret"]
                ),
                "heldout_oracle_variant": oracle_variant,
                "heldout_oracle_regret": float(
                    held_frame.loc[oracle_variant, "full32_fixed_normalized_regret"]
                ),
            }
        )
    return pd.DataFrame(rows)
