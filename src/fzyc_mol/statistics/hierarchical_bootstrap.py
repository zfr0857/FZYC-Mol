from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class HierarchicalBootstrapResult:
    estimate: float
    median: float
    iqr: float
    ci_low: float
    ci_high: float
    distribution: np.ndarray
    n_endpoints: int


def hierarchical_bootstrap(
    frame: pd.DataFrame,
    *,
    endpoint_col: str,
    unit_col: str,
    value_col: str,
    replicates: int = 5000,
    seed: int = 20260622,
) -> HierarchicalBootstrapResult:
    """Resample endpoints first and outer units within sampled endpoints second."""

    required = {endpoint_col, unit_col, value_col}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"missing bootstrap columns: {sorted(missing)}")
    if replicates < 1:
        raise ValueError("replicates must be positive")
    collapsed = frame.groupby([endpoint_col, unit_col], as_index=False)[value_col].mean().dropna(subset=[value_col])
    endpoints = collapsed[endpoint_col].drop_duplicates().to_numpy()
    if len(endpoints) == 0:
        raise ValueError("no finite endpoint values")
    values = {
        endpoint: collapsed.loc[collapsed[endpoint_col].eq(endpoint), value_col].to_numpy(dtype=float)
        for endpoint in endpoints
    }
    endpoint_means = np.asarray([np.mean(values[endpoint]) for endpoint in endpoints], dtype=float)
    rng = np.random.default_rng(seed)
    distribution = np.empty(replicates, dtype=float)
    for index in range(replicates):
        sampled_endpoints = rng.choice(endpoints, size=len(endpoints), replace=True)
        sampled_means = []
        for endpoint in sampled_endpoints:
            units = values[endpoint]
            sampled_means.append(float(np.mean(rng.choice(units, size=len(units), replace=True))))
        distribution[index] = float(np.mean(sampled_means))
    q1, q3 = np.quantile(endpoint_means, [0.25, 0.75])
    return HierarchicalBootstrapResult(
        estimate=float(np.mean(endpoint_means)),
        median=float(np.median(endpoint_means)),
        iqr=float(q3 - q1),
        ci_low=float(np.quantile(distribution, 0.025)),
        ci_high=float(np.quantile(distribution, 0.975)),
        distribution=distribution,
        n_endpoints=len(endpoints),
    )
