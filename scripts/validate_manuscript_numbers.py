from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "paper31_expanded_intervention" / "experiment_exports"


def fail(message: str) -> None:
    raise AssertionError(message)


def main() -> None:
    summary = pd.read_csv(EXPORTS / "Paper31_endpoint_pool_K_summary.csv")
    primary = summary.loc[
        summary.design.eq("equal_K") & summary.anchor_scheme.eq("shared_morgan_linear")
    ]
    expected_pools = {"Homogeneous Morgan", "Classical multiview", "Modern-augmented"}
    if set(primary.pool) != expected_pools:
        fail("Candidate-pool registry mismatch")
    if set(primary.candidate_count.astype(int)) != {4, 8, 16, 32}:
        fail("Candidate-count ladder mismatch")
    if primary.task.nunique() != 6:
        fail("Expanded intervention must contain six endpoints")

    paired = pd.read_csv(EXPORTS / "Paper31_paired_pool_effects.csv")
    modern = paired.loc[
        paired.candidate_count.eq(32)
        & paired.comparison.eq("Modern-augmented - Homogeneous Morgan")
        & paired.metric.eq("selected_model_gain")
    ]
    if len(modern) != 6 or int(modern.mean_paired_difference.gt(0).sum()) != 6:
        fail("Modern K=32 direction count does not match 6/6")

    cross_fitted = pd.read_csv(ROOT / "source_data" / "primary_cross_fitted_effects.csv")
    signs = cross_fitted["cross_fitted_effect"].dropna()
    if int(signs.gt(0).sum()) != 6 or int(signs.lt(0).sum()) != 3:
        fail("Cross-fitted endpoint direction count does not match six positive and three negative")

    selection_units = pd.read_csv(EXPORTS / "Paper31_selection_units.csv")
    locked_units = selection_units.loc[
        selection_units.design.eq("equal_K")
        & selection_units.anchor_scheme.eq("shared_morgan_linear")
    ]
    if len(locked_units) != 1080:
        fail("Expanded primary outer-unit count does not match 1,080")

    config = __import__("yaml").safe_load((ROOT / "configs" / "paper.yaml").read_text(encoding="utf-8"))
    if config["locked_claims"]["matched_subsets"] != 220:
        fail("Registered matched-subset count does not match 220")

    report = {
        "status": "PASS",
        "checked": {
            "composition_endpoints": 6,
            "candidate_pool_sizes": [4, 8, 16, 32],
            "cross_fitted_directions": {"positive": 6, "negative": 3},
            "modern_K32_positive": 6,
            "primary_outer_units": 1080,
            "matched_subsets": 220,
        },
    }
    output = ROOT / "reproduced_outputs" / "manuscript_number_validation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("PASS:")
    print("All manuscript values match machine-readable source tables.")


if __name__ == "__main__":
    main()
