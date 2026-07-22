from __future__ import annotations

import math
from collections.abc import Mapping


def _finite_mapping(values: Mapping[str, float], name: str) -> dict[str, float]:
    clean = {str(key): float(value) for key, value in values.items()}
    if not clean:
        raise ValueError(f"{name} must not be empty")
    if not all(math.isfinite(value) for value in clean.values()):
        raise ValueError(f"{name} must contain only finite utilities")
    return clean


def regret_decomposition(
    pool_test_utility: Mapping[str, float],
    full_test_utility: Mapping[str, float],
    selected_id: str,
    baseline_id: str,
) -> dict[str, float | str]:
    """Compute outer-test regret using a denominator fixed by the full pool."""

    pool = _finite_mapping(pool_test_utility, "pool_test_utility")
    full = _finite_mapping(full_test_utility, "full_test_utility")
    if selected_id not in pool:
        raise KeyError(selected_id)
    if baseline_id not in full:
        raise KeyError(baseline_id)
    if not set(pool).issubset(full):
        raise ValueError("pool candidates must be present in full_test_utility")

    selected = pool[selected_id]
    oracle_id = max(pool, key=pool.get)
    oracle = pool[oracle_id]
    baseline = full[baseline_id]
    raw = oracle - selected
    full_range = max(full.values()) - min(full.values())
    dynamic_range = max(pool.values()) - min(pool.values())
    fixed = raw / full_range if full_range > 0 else math.nan
    dynamic = raw / dynamic_range if dynamic_range > 0 else math.nan
    status = "ok" if full_range > 0 else "zero_full_range"

    return {
        "selected_id": selected_id,
        "oracle_id": oracle_id,
        "baseline_id": baseline_id,
        "selected_test_utility": selected,
        "oracle_test_utility": oracle,
        "baseline_test_utility": baseline,
        "raw_regret": raw,
        "full_range": full_range,
        "dynamic_range": dynamic_range,
        "fixed_normalized_regret": fixed,
        "dynamic_normalized_regret": dynamic,
        "selection_gain_vs_baseline": selected - baseline,
        "normalization_status": status,
    }
