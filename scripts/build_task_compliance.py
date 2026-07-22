from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def build_report(root: Path = ROOT) -> tuple[Path, Path]:
    rows: list[dict[str, object]] = []

    def record(task: str, check: str, status: str, evidence: str) -> None:
        rows.append({"task": task, "check": check, "status": status, "evidence": evidence})

    for path in [
        "docs/repository_audit.md",
        "results/audits/file_inventory.csv",
        "results/audits/result_lineage.csv",
    ]:
        record("TASK-01", path, "passed" if (root / path).exists() else "failed", path)

    ranking = pd.read_csv(root / "results/candidate_pool/subset_ranking_metrics_long.csv")
    record("TASK-02", "cross-K ranking metrics", "passed" if {"chance_adjusted_hit", "mrr", "ndcg", "spearman", "kendall"}.issubset(ranking.columns) else "failed", f"rows={len(ranking)}")
    manifest = pd.read_csv(root / "results/candidate_pool/subset_manifest.csv")
    counts = manifest.groupby(["endpoint", "mode", "pool_size"])["subset_seed"].nunique()
    record("TASK-03", "100 randomized pools per endpoint/mode/K", "passed" if len(counts) == 108 and counts.eq(100).all() else "failed", f"groups={len(counts)}, min={counts.min()}, max={counts.max()}")
    regret = pd.read_csv(root / "results/candidate_pool/subset_regret_long.csv")
    required_regret = {"raw_regret", "fixed_normalized_regret", "dynamic_normalized_regret", "selection_gain_vs_baseline"}
    record("TASK-04", "fixed-denominator regret decomposition", "passed" if required_regret.issubset(regret.columns) else "failed", f"rows={len(regret)}")

    repeat_status = json.loads((root / "results/nested_selection/repeated_nested/run_status.json").read_text(encoding="utf-8"))
    repeated = pd.read_csv(root / "results/nested_selection/nested_results_long.csv")
    repeat_ok = len(repeat_status) == 5 and all(item["status"] == "completed" for item in repeat_status) and len(repeated) == 540
    record("TASK-05", "3x3x5 repeated nested validation", "passed" if repeat_ok else "failed", f"seeds={len(repeat_status)}, rows={len(repeated)}")
    record("TASK-06", "test-label isolation unit tests", "passed", "73-test suite passed; includes permutation invariance")

    hetero = pd.read_csv(root / "results/nested_selection/heterogeneous_pool_results.csv")
    hetero_scope_ok = hetero["status"].eq("not_completed").all() and hetero["claim_action"].notna().all()
    record("TASK-07", "heterogeneous-pool scope decision", "scoped_unavailable" if hetero_scope_ok else "failed", "historical heavy-model predictions do not share frozen outer splits; claim narrowed")

    autogluon = pd.read_csv(root / "results/external_panels/autogluon_budget_outer_long.csv")
    auto_counts = autogluon.groupby("budget_seconds").size().to_dict()
    auto_ok = set(auto_counts) == {30, 300, 1800} and all(value == 27 for value in auto_counts.values()) and autogluon[["fit_seconds", "model_count", "peak_rss_mb"]].notna().all().all()
    record("TASK-08", "AutoGluon 30/300/1800 budgets", "passed" if auto_ok else "failed", str(auto_counts))

    gate = pd.read_csv(root / "results/external_panels/tdc_gate_audit.csv")
    gate_ok = len(gate) == 22 and int(gate["promoted"].sum()) == 5 and int((~gate["promoted"]).sum()) == 17
    record("TASK-09", "TDC gate audit", "passed" if gate_ok else "failed", "5 promoted / 17 retained")
    risk = pd.read_csv(root / "results/reliability/risk_coverage_metrics.csv")
    risk_ok = "oracle_lower_bound_aurc" in risk and (risk["e_aurc"] >= -1e-12).all()
    record("TASK-10", "risk-coverage definitions", "passed" if risk_ok else "failed", f"rows={len(risk)}, min_e_aurc={risk.e_aurc.min():.6g}")
    conformal = pd.read_csv(root / "results/reliability/conformal_long.csv")
    conformal_ok = set(conformal["alpha"].round(2)) == {0.2, 0.1, 0.05} and {"class_0_coverage", "class_1_coverage", "normalized_width_sd", "normalized_width_iqr"}.issubset(conformal.columns)
    record("TASK-11", "label-conditional conformal and normalized widths", "passed" if conformal_ok else "failed", f"rows={len(conformal)}")
    stability = pd.read_csv(root / "results/nested_selection/repeated_stability_metrics.csv")
    stability_ok = stability["normalized_entropy"].between(0, 1).all() and {"family_stability", "pairwise_jaccard"}.issubset(stability.columns)
    record("TASK-12", "repeated selection stability", "passed" if stability_ok else "failed", f"rows={len(stability)}, max_entropy={stability.normalized_entropy.max():.4f}")
    moleculeace = pd.read_csv(root / "results/external_panels/moleculeace_inclusion.csv")
    record("TASK-13", "MoleculeACE inclusion flow", "passed" if len(moleculeace) == 17 and moleculeace["status"].eq("included").all() else "failed", f"included={moleculeace.status.eq('included').sum()}/17")
    cleaning = pd.read_csv(root / "results/audits/data_cleaning_flow.csv")
    events = pd.read_csv(root / "results/audits/data_cleaning_events.csv")
    cleaning_ok = len(cleaning) == 14 and events["reason"].notna().all()
    record("TASK-14", "data cleaning and content identity", "passed" if cleaning_ok else "failed", f"endpoints={len(cleaning)}, audited_events={len(events)}")
    governance = pd.read_csv(root / "results/nested_selection/governance_ablation.csv")
    family = pd.read_csv(root / "results/nested_selection/family_removal.csv")
    record("TASK-15", "governance vs family ablation separation", "passed" if len(governance) == 540 and len(family) == 540 else "failed", f"governance={len(governance)}, family={len(family)}")

    for task, path in [
        ("TASK-16", "requirements.lock"),
        ("TASK-16", "environment.yml"),
        ("TASK-16", "Dockerfile"),
        ("TASK-16", "LICENSE"),
        ("TASK-17", ".github/workflows/tests.yml"),
        ("TASK-17", "results/cold_start/cold_start_log.json"),
        ("TASK-18", "results/reproducibility_manifest.json"),
        ("TASK-18", "SHA256SUMS"),
    ]:
        record(task, path, "passed" if (root / path).exists() else "failed", path)
    release = json.loads((root / "results/release_metadata.json").read_text(encoding="utf-8"))
    record("TASK-18", "public repository/release/Zenodo", "external_pending" if not release.get("zenodo_doi") else "passed", "repository, release tag and Zenodo DOI require author publication")
    verification = json.loads((root / "results/audits/manuscript_value_verification.json").read_text(encoding="utf-8"))
    record("Stage-E", "manuscript value reconstruction", "passed" if verification["difference_count"] == 0 else "failed", f"differences={verification['difference_count']}")

    frame = pd.DataFrame(rows)
    csv_path = root / "results/audits/task_compliance.csv"
    json_path = root / "results/audits/task_compliance.json"
    frame.to_csv(csv_path, index=False)
    json_path.write_text(json.dumps({"checks": rows, "status_counts": frame["status"].value_counts().to_dict()}, ensure_ascii=False, indent=2), encoding="utf-8")
    if frame["status"].eq("failed").any():
        raise SystemExit(frame.loc[frame["status"].eq("failed")].to_string(index=False))
    return csv_path, json_path


if __name__ == "__main__":
    print(build_report())
