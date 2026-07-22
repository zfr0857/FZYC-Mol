from __future__ import annotations

import argparse
import sys
from collections import OrderedDict
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import build_moleculenet_meta_pool_selector as meta_pool  # noqa: E402
import build_validation_selector as selector  # noqa: E402


OUT_DIR = ROOT / "reports" / "validation_selector_rescue_integration"
TABLE_DIR = ROOT / "reports" / "manuscript_tables"
TABLE19_PATH = TABLE_DIR / "table19_moleculenet_rescue_integrated_selector.csv"
TABLE17_PATH = TABLE_DIR / "table17_moleculenet_meta_pool_selector.csv"

DEFAULT_DATASETS = ["esol", "freesolv", "lipo", "bbbp", "bace", "clintox"]
DEFAULT_SEEDS = [13, 17, 23, 29, 31]

RESCUE_MEMBERS = [
    ("reports/pretrained_rescue_heads", "DeepChem_ChemBERTa-77M-MTR_emb_desc_extratrees_rescue"),
    ("reports/pretrained_rescue_heads", "DeepChem_ChemBERTa-77M-MTR_emb_desc_lgbm_rescue"),
    ("reports/pretrained_rescue_heads", "DeepChem_ChemBERTa-77M-MLM_emb_desc_extratrees_rescue"),
    ("reports/pretrained_rescue_heads", "DeepChem_ChemBERTa-77M-MLM_emb_desc_lgbm_rescue"),
    ("reports/pretrained_rescue_heads", "ibm_MoLFormer-XL-both-10pct_emb_desc_extratrees_rescue"),
    ("reports/pretrained_rescue_heads", "ibm_MoLFormer-XL-both-10pct_emb_desc_lgbm_rescue"),
]

RESCUE_MEMBER_SETS = OrderedDict(
    [
        ("pretrained_rescue_only", RESCUE_MEMBERS),
        ("q1_all_plus_rescue", selector.MEMBER_SETS["strict_core_q1_all"] + RESCUE_MEMBERS),
        ("q1_no_linear_pretrained_plus_rescue", selector.MEMBER_SETS["q1_no_pretrained"] + RESCUE_MEMBERS),
    ]
)

EXISTING_CANDIDATE_REPORTS = {
    "expanded_selector": ROOT / "reports" / "validation_selector_expanded" / "candidate_metrics_raw.csv",
    "ablation_pool": ROOT / "reports" / "validation_selector_ablation" / "candidate_metrics_raw.csv",
    "descriptor_motif_pool": ROOT
    / "reports"
    / "validation_selector_plus_descriptor_motif"
    / "candidate_metrics_raw.csv",
}


def build_rescue_candidate_metrics(
    datasets: list[str],
    seeds: list[int],
    families: list[str] | None,
    output_dir: Path,
) -> pd.DataFrame:
    selected_families = set(families) if families else None
    rows: list[dict[str, object]] = []

    for dataset in datasets:
        frame, spec = selector.load_dataset(dataset, data_dir=ROOT / "data")
        for seed in seeds:
            for family, members in RESCUE_MEMBER_SETS.items():
                if selected_families is not None and family not in selected_families:
                    continue
                candidates = selector.build_candidate_predictions(
                    dataset=dataset,
                    seed=seed,
                    family=family,
                    members=members,
                    task_type=spec.task_type,
                    frame=frame,
                )
                for item in candidates:
                    rows.append(
                        {
                            "dataset": dataset,
                            "model": item["candidate"],
                            "seed": seed,
                            "split": "scaffold",
                            "task_type": spec.task_type,
                            "selection_metric": item["selection_metric"],
                            "selection_direction": item["selection_direction"],
                            "selection_value": item["selection_value"],
                            "clip_lower": item["clip_lower"],
                            "clip_upper": item["clip_upper"],
                            "valid_member_clip_count": item["valid_member_clip_count"],
                            "test_member_clip_count": item["test_member_clip_count"],
                            **{f"valid_{k}": v for k, v in item["select_metrics"].items()},
                            **{f"test_{k}": v for k, v in item["test_metrics"].items()},
                        }
                    )
                print(f"[ok] {dataset} seed={seed} family={family} candidates={len(candidates)}")

    if not rows:
        raise RuntimeError("No rescue-integrated candidate rows were produced.")
    rescue = pd.DataFrame(rows)
    rescue.to_csv(output_dir / "rescue_candidate_metrics_raw.csv", index=False)
    return rescue


def add_table17_comparison(comparison: pd.DataFrame) -> pd.DataFrame:
    if not TABLE17_PATH.exists():
        comparison["delta_vs_table17_meta_pool"] = np.nan
        comparison["better_than_table17_meta_pool"] = False
        return comparison
    table17 = pd.read_csv(TABLE17_PATH)
    table17 = table17[["dataset", "meta_pool_primary_mean"]].rename(
        columns={"meta_pool_primary_mean": "table17_meta_pool_primary_mean"}
    )
    merged = comparison.merge(table17, on="dataset", how="left")
    direction = merged["primary_direction"].astype(str)
    merged["delta_vs_table17_meta_pool"] = np.where(
        direction.eq("lower"),
        merged["table17_meta_pool_primary_mean"] - merged["integrated_primary_mean"],
        merged["integrated_primary_mean"] - merged["table17_meta_pool_primary_mean"],
    )
    merged["better_than_table17_meta_pool"] = merged["delta_vs_table17_meta_pool"] > 1e-8
    return merged


def integrate_candidate_pools(rescue: pd.DataFrame, min_seeds: int, output_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    existing = meta_pool.load_candidates(EXISTING_CANDIDATE_REPORTS)
    rescue = rescue.copy()
    rescue["candidate_pool"] = "rescue_integration_pool"
    combined = pd.concat([existing, rescue], ignore_index=True, sort=False)
    combined = combined.drop_duplicates(["dataset", "seed", "candidate_pool", "model"], keep="last")
    clean = meta_pool.valid_candidate_rows(combined)
    audit, selected = meta_pool.choose_dataset_level_candidates(clean, min_seeds=min_seeds)
    summary = meta_pool.summarize_selected(selected)
    comparison = meta_pool.compare_to_current(summary)

    summary = summary.rename(
        columns={
            "meta_pool_primary_mean": "integrated_primary_mean",
            "meta_pool_primary_std": "integrated_primary_std",
        }
    )
    comparison = comparison.rename(
        columns={
            "meta_pool_primary_mean": "integrated_primary_mean",
            "meta_pool_primary_std": "integrated_primary_std",
            "meta_delta_vs_current": "integration_delta_vs_current",
            "meta_better_than_current": "integration_better_than_current",
        }
    )
    comparison["selected_uses_rescue_pool"] = comparison["selected_pool_counts"].astype(str).str.contains(
        "rescue_integration_pool", regex=False
    )
    comparison["selected_uses_rescue_model"] = comparison["selected_model_counts"].astype(str).str.contains(
        "rescue", regex=False
    )
    comparison = add_table17_comparison(comparison)

    combined.to_csv(output_dir / "all_candidate_metrics_raw.csv", index=False)
    clean.to_csv(output_dir / "all_candidate_metrics_clean.csv", index=False)
    audit.to_csv(output_dir / "candidate_audit.csv", index=False)
    selected.to_csv(output_dir / "selected_seed_metrics.csv", index=False)
    summary.to_csv(output_dir / "selected_summary.csv", index=False)
    comparison.to_csv(output_dir / "comparison_to_current.csv", index=False)
    comparison.to_csv(TABLE19_PATH, index=False)
    return summary, comparison


def write_report(output_dir: Path, rescue: pd.DataFrame, comparison: pd.DataFrame) -> None:
    improved = comparison[comparison["integration_better_than_current"].fillna(False)]
    rescue_selected = comparison[comparison["selected_uses_rescue_pool"].fillna(False)]
    lines = [
        "# Rescue-Integrated Validation Selector",
        "",
        "Date: 2026-05-31",
        "",
        "This run adds the frozen-pretrained rescue heads into the MoleculeNet validation-only selector pool.",
        "It builds three new rescue-aware candidate families:",
        "",
    ]
    for family in RESCUE_MEMBER_SETS:
        lines.append(f"- `{family}`")
    lines.extend(
        [
            "",
            f"New rescue-aware candidate rows: {len(rescue)}.",
            f"Datasets selecting a rescue-aware candidate: {len(rescue_selected)}/{len(comparison)}.",
            f"Datasets improved over current Table 2 selector: {len(improved)}/{len(comparison)}.",
            "",
            "## Endpoint Decisions",
            "",
        ]
    )
    for _, row in comparison.iterrows():
        verdict = "improved" if bool(row["integration_better_than_current"]) else "not improved"
        rescue_tag = "rescue-selected" if bool(row["selected_uses_rescue_pool"]) else "existing-pool"
        lines.append(
            f"- `{row['dataset']}`: {verdict}, {rescue_tag}; current {row['current_primary_mean']:.4g}, "
            f"integrated {row['integrated_primary_mean']:.4g}, delta {row['integration_delta_vs_current']:.4g}; "
            f"selected {row['selected_model_counts']}."
        )
    lines.extend(
        [
            "",
            "## Manuscript Use",
            "",
            "Use this as the decisive validation-only integration check for Table 18. If rescue-aware candidates",
            "are not selected, keep rescue heads as a module-level appendix rather than changing the main Table 2 selector.",
            "",
            "## Outputs",
            "",
            "- `reports/validation_selector_rescue_integration/rescue_candidate_metrics_raw.csv`",
            "- `reports/validation_selector_rescue_integration/all_candidate_metrics_clean.csv`",
            "- `reports/validation_selector_rescue_integration/candidate_audit.csv`",
            "- `reports/validation_selector_rescue_integration/selected_summary.csv`",
            "- `reports/validation_selector_rescue_integration/comparison_to_current.csv`",
            "- `reports/manuscript_tables/table19_moleculenet_rescue_integrated_selector.csv`",
            "",
        ]
    )
    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Integrate pretrained rescue heads into the validation selector pool.")
    parser.add_argument("--datasets", nargs="*", default=DEFAULT_DATASETS)
    parser.add_argument("--seeds", nargs="*", type=int, default=DEFAULT_SEEDS)
    parser.add_argument("--families", nargs="*", default=None)
    parser.add_argument("--min-seeds", type=int, default=5)
    parser.add_argument("--output-dir", default=str(OUT_DIR))
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    rescue = build_rescue_candidate_metrics(
        datasets=args.datasets,
        seeds=args.seeds,
        families=args.families,
        output_dir=output_dir,
    )
    _, comparison = integrate_candidate_pools(rescue, min_seeds=args.min_seeds, output_dir=output_dir)
    write_report(output_dir, rescue, comparison)

    print(f"Wrote {TABLE19_PATH}")
    print(
        comparison[
            [
                "dataset",
                "current_primary_mean",
                "integrated_primary_mean",
                "integration_delta_vs_current",
                "selected_uses_rescue_pool",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
