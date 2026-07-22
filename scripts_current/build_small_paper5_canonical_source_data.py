import os
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = Path(os.environ.get("FZYC_SOURCE_PACKAGE", str(ROOT / "output" / "小论文-5_图表包"))) / "source_data"


GROUPS = {
    1: [],
    2: ["fig03_candidate_pool_summary.csv", "fig03_null_calibration_summary.csv"],
    3: ["fig04_repeated_nested_bootstrap.csv", "fig04_selection_risk_units.csv", "fig04_selection_risk_curve.csv"],
    4: ["fig04_paired_pool_endpoint_effects.csv", "fig04_signal_recovery_summary.csv", "fig04_risk_quartiles.csv", "fig04_cross_endpoint_meta_risk_endpoint_summary.csv"],
    5: ["fig05_policy_summary.csv", "fig05_paired_multiview_effects.csv", "fig05_endpoint_representation_counts.csv", "fig05_validation_best_representation_counts.csv"],
    6: ["fig05_moleculenet_source.csv", "fig05_clintox_recall.csv", "fig05_rank_audit.csv"],
    7: ["fig06_tdc_gate_audit.csv", "fig06_gate_counts.csv"],
    8: ["fig08_prediction_risk_curves.csv", "fig08_conformal_summary.csv"],
    9: ["fig09_moleculeace_task_summary.csv", "fig09_bro5_cycpept_pampa_compact_summary.csv", "fig09_linpept_parsed.csv", "fig09_maintext_table_failure_cases_compact.csv"],
    10: ["fig10_ablation_summary.csv", "fig10_autogluon_budget.csv", "fig10_leave_one_endpoint_out_policy.csv", "fig10_autogluon_budget_summary.csv"],
    11: ["fig11_failure_cases.csv", "fig11_strategies.csv", "fig11_case_signals.csv", "fig11_fragment_support.csv", "fig11_evidence_inventory.csv"],
}


def main() -> None:
    concept = pd.DataFrame([
        {"panel":"workflow","entity":"task protocol","relationship":"feeds","target":"candidate registry"},
        {"panel":"workflow","entity":"candidate registry","relationship":"feeds","target":"inner validation"},
        {"panel":"workflow","entity":"inner validation","relationship":"freezes","target":"outer audit"},
        {"panel":"workflow","entity":"outer audit","relationship":"emits","target":"endpoint decision card"},
        {"panel":"workflow","entity":"sample reliability","relationship":"emits","target":"sample decision card"},
    ])
    concept.to_csv(SRC / "fig01_source_data.csv", index=False, encoding="utf-8-sig")
    for number, names in GROUPS.items():
        if number == 1: continue
        frames = []
        for name in names:
            path = SRC / name
            if not path.exists():
                continue
            frame = pd.read_csv(path)
            frame.insert(0, "source_table", name)
            frames.append(frame)
        if not frames:
            raise FileNotFoundError(f"no inputs for figure {number}: {names}")
        pd.concat(frames, ignore_index=True, sort=False).to_csv(SRC / f"fig{number:02d}_source_data.csv", index=False, encoding="utf-8-sig")
    print("canonical source data built for figures 1-11")


if __name__ == "__main__": main()
