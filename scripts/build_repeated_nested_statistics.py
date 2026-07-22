from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fzyc_mol.statistics.hierarchical_bootstrap import hierarchical_bootstrap  # noqa: E402


def build_outputs(root: Path = ROOT, *, replicates: int = 5000) -> Path:
    nested = root / "results" / "nested_selection"
    regret = pd.read_csv(nested / "repeated_regret_decomposition.csv")
    ranking = pd.read_csv(nested / "repeated_ranking_metrics_long.csv")
    joined = regret.merge(
        ranking[
            [
                "split_id",
                "pool_size",
                "chance_adjusted_hit",
                "mrr",
                "rank_percentile",
                "top_fraction_hit",
                "spearman",
                "kendall",
            ]
        ],
        on=["split_id", "pool_size"],
        validate="one_to_one",
    )
    rows: list[dict[str, object]] = []
    metrics = (
        "fixed_normalized_regret",
        "raw_regret",
        "chance_adjusted_hit",
        "mrr",
        "rank_percentile",
        "top_fraction_hit",
        "spearman",
        "kendall",
    )
    for pool_size, group in joined.groupby("pool_size", sort=True):
        for index, metric in enumerate(metrics):
            result = hierarchical_bootstrap(
                group,
                endpoint_col="endpoint",
                unit_col="split_id",
                value_col=metric,
                replicates=replicates,
                seed=20260622 + int(pool_size) * 100 + index,
            )
            rows.append(
                {
                    "pool_size": int(pool_size),
                    "metric": metric,
                    "primary_cluster_unit": "endpoint",
                    "n_endpoints": result.n_endpoints,
                    "n_outer_units": int(group["split_id"].nunique()),
                    "mean": result.estimate,
                    "median_endpoint": result.median,
                    "endpoint_iqr": result.iqr,
                    "ci95_low": result.ci_low,
                    "ci95_high": result.ci_high,
                    "bootstrap_replicates": replicates,
                }
            )
    output = root / "results" / "statistics" / "repeated_nested_bootstrap.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output, index=False)
    return output


if __name__ == "__main__":
    print(build_outputs())
