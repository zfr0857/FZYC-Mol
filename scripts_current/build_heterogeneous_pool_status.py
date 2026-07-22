from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]


def build_status_rows(*, available_artifacts: set[str], root: Path = ROOT) -> list[dict[str, object]]:
    config = yaml.safe_load((root / "configs" / "heterogeneous_pool.yaml").read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    for candidate in config["required_candidates"]:
        candidate_id = candidate["candidate_id"]
        artifact_available = candidate_id in available_artifacts
        rows.append(
            {
                **candidate,
                "artifact_available": artifact_available,
                "outer_split_compatible": False,
                "status": "not_completed",
                "reason": (
                    "historical_predictions_exist_but_not_for_the_frozen_11_23_37_53_71_outer_splits"
                    if artifact_available
                    else "no_complete_prediction_artifact_for_all_nine_endpoints_and_frozen_outer_splits"
                ),
                "validation_utility": None,
                "test_utility": None,
                "claim_action": config["claim_if_incomplete"],
            }
        )
    return rows


def discover_available_artifacts(root: Path = ROOT) -> set[str]:
    available = {"morgan_rf", "rdkit_catboost", "xgboost_morgan"}
    if any((root / "reports" / "pretrained_rescue_heads").glob("*ChemBERTa*predictions.csv")):
        available.add("chemberta_frozen_head")
    if any((root / "reports" / "pretrained_rescue_heads").glob("*MoLFormer*predictions.csv")):
        available.add("molformer_frozen_head")
    if any((root / "reports").rglob("*chemprop*predictions.csv")):
        available.add("chemprop")
    if any((root / "reports").rglob("*gnn*predictions.csv")):
        available.add("graph_neural_network")
    if any((root / "reports").rglob("*fusion*predictions.csv")):
        available.add("topk_fusion")
    return available


def main() -> None:
    output = ROOT / "results" / "nested_selection" / "heterogeneous_pool_results.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(build_status_rows(available_artifacts=discover_available_artifacts())).to_csv(output, index=False)
    print(output)


if __name__ == "__main__":
    main()
