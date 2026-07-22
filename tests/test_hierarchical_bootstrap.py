from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fzyc_mol.statistics.hierarchical_bootstrap import hierarchical_bootstrap


def test_bootstrap_uses_endpoint_as_primary_cluster() -> None:
    frame = pd.DataFrame(
        {
            "endpoint": ["a"] * 3 + ["b"] * 3,
            "unit": [1, 2, 3, 1, 2, 3],
            "value": [0.0, 0.0, 0.0, 10.0, 10.0, 10.0],
        }
    )

    result = hierarchical_bootstrap(frame, endpoint_col="endpoint", unit_col="unit", value_col="value", replicates=500, seed=7)

    assert result.estimate == pytest.approx(5.0)
    assert result.ci_low == pytest.approx(0.0)
    assert result.ci_high == pytest.approx(10.0)
    assert set(np.unique(result.distribution)).issubset({0.0, 5.0, 10.0})


def test_bootstrap_is_reproducible() -> None:
    frame = pd.DataFrame({"endpoint": ["a", "a", "b", "b"], "unit": [1, 2, 1, 2], "value": [1, 2, 3, 4]})
    first = hierarchical_bootstrap(frame, endpoint_col="endpoint", unit_col="unit", value_col="value", replicates=100, seed=11)
    second = hierarchical_bootstrap(frame, endpoint_col="endpoint", unit_col="unit", value_col="value", replicates=100, seed=11)

    assert np.array_equal(first.distribution, second.distribution)
