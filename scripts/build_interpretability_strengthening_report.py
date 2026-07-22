from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "reports" / "interpretability_strengthening"


def short_feature_name(feature: str) -> str:
    for prefix in ["FG::", "BRICS::", "Murcko::"]:
        if feature.startswith(prefix):
            return feature[len(prefix) :]
    return feature


def motif_direction_note(direction: float, task_type: str = "classification") -> str:
    if not np.isfinite(direction) or abs(direction) < 1e-12:
        return "neutral or unstable association"
    if task_type == "classification":
        return "enriched in positive class" if direction > 0 else "enriched in negative class"
    return "positively associated with property" if direction > 0 else "negatively associated with property"


def build_top_motif_table() -> pd.DataFrame:
    path = ROOT / "reports" / "motif_attribution" / "motif_feature_importance.csv"
    motif = pd.read_csv(path)
    grouped = (
        motif.groupby(["dataset", "feature", "feature_family"], as_index=False)
        .agg(
            mean_importance=("importance", "mean"),
            std_importance=("importance", "std"),
            mean_direction=("direction", "mean"),
            n_seeds=("seed", "nunique"),
            best_rank=("rank", "min"),
        )
        .sort_values(["dataset", "mean_importance"], ascending=[True, False])
    )
    rows: list[pd.DataFrame] = []
    for dataset, sub in grouped.groupby("dataset"):
        top = sub.head(20).copy()
        top.insert(1, "motif_rank", np.arange(1, len(top) + 1))
        top["short_feature"] = top["feature"].map(short_feature_name)
        top["direction_note"] = top["mean_direction"].map(motif_direction_note)
        rows.append(top)
    out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    out.to_csv(OUT_DIR / "top_motif_importance_summary.csv", index=False)
    return out


def build_fragment_enrichment_table() -> pd.DataFrame:
    path = ROOT / "reports" / "scaffold_fragment_cases" / "scaffold_fragment_label_enrichment.csv"
    enrich = pd.read_csv(path)
    rows = []
    for dataset, sub in enrich.groupby("dataset"):
        positive = sub.sort_values(["delta_mean_y", "n"], ascending=[False, False]).head(12).copy()
        positive["association_direction"] = "positive-label enriched"
        negative = sub.sort_values(["delta_mean_y", "n"], ascending=[True, False]).head(12).copy()
        negative["association_direction"] = "negative-label enriched"
        rows.extend([positive, negative])
    out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    if not out.empty:
        out["short_feature"] = out["feature"].astype(str).str.slice(0, 120)
    out.to_csv(OUT_DIR / "fragment_scaffold_label_enrichment_top.csv", index=False)
    return out


def load_risk_predictions() -> pd.DataFrame:
    path = ROOT / "reports" / "risk_calibrated_selector" / "compound_risk_predictions.csv"
    if not path.exists():
        return pd.DataFrame()
    risk = pd.read_csv(path)
    keep = [
        "source",
        "dataset",
        "seed",
        "smiles",
        "risk_score",
        "error_model_score",
        "risk_percentile",
        "calibrator",
    ]
    keep = [column for column in keep if column in risk.columns]
    return risk[keep].drop_duplicates(["source", "dataset", "seed", "smiles"])


def build_high_error_case_table(top_motifs: pd.DataFrame) -> pd.DataFrame:
    path = ROOT / "reports" / "scaffold_fragment_cases" / "selector_high_error_cases.csv"
    cases = pd.read_csv(path)
    risk = load_risk_predictions()
    if not risk.empty:
        risk = risk[risk["source"].isin(["moleculenet", "structure", "tdc_admet"])]
        risk = risk.sort_values(["source"]).drop_duplicates(["dataset", "seed", "smiles"], keep="first")
        cases = cases.merge(risk, on=["dataset", "seed", "smiles"], how="left")

    motif_lookup = {
        dataset: set(sub["short_feature"].astype(str).head(30))
        for dataset, sub in top_motifs.groupby("dataset")
    }

    def matching_motifs(row: pd.Series) -> str:
        fragments = str(row.get("brics_fragments", "")).split("|")
        top = motif_lookup.get(row["dataset"], set())
        matches = [frag for frag in fragments if frag in top]
        return "|".join(matches[:8])

    cases["matched_top_brics_motifs"] = cases.apply(matching_motifs, axis=1)
    cases["brics_fragment_count"] = cases["brics_fragments"].fillna("").map(lambda x: 0 if x == "" else len(str(x).split("|")))
    columns = [
        "dataset",
        "seed",
        "smiles",
        "y_true",
        "y_pred",
        "abs_error",
        "risk_percentile",
        "risk_score",
        "error_model_score",
        "calibrator",
        "scaffold",
        "brics_fragment_count",
        "matched_top_brics_motifs",
        "brics_fragments",
    ]
    columns = [column for column in columns if column in cases.columns]
    cases = cases[columns].sort_values(["dataset", "abs_error"], ascending=[True, False])
    cases.to_csv(OUT_DIR / "high_error_interpretability_cases.csv", index=False)
    return cases


def build_family_summary(top_motifs: pd.DataFrame) -> pd.DataFrame:
    if top_motifs.empty:
        return pd.DataFrame()
    summary = (
        top_motifs.groupby(["dataset", "feature_family"], as_index=False)
        .agg(
            n_top_features=("feature", "count"),
            mean_importance=("mean_importance", "mean"),
            max_importance=("mean_importance", "max"),
            mean_abs_direction=("mean_direction", lambda x: float(np.mean(np.abs(x)))),
        )
        .sort_values(["dataset", "mean_importance"], ascending=[True, False])
    )
    summary.to_csv(OUT_DIR / "motif_family_contribution_summary.csv", index=False)
    return summary


def write_readme(
    top_motifs: pd.DataFrame,
    enrichment: pd.DataFrame,
    cases: pd.DataFrame,
    family: pd.DataFrame,
) -> None:
    lines = [
        "# Interpretability strengthening report",
        "",
        "This report consolidates motif/functional-group importance, scaffold/fragment label enrichment, and high-error case studies.",
        "",
        "## Outputs",
        "",
        "- `top_motif_importance_summary.csv`: top motif, BRICS, Murcko, and functional-group features by endpoint.",
        "- `motif_family_contribution_summary.csv`: feature-family level contribution summary.",
        "- `fragment_scaffold_label_enrichment_top.csv`: label-enriched BRICS fragments and Murcko scaffolds.",
        "- `high_error_interpretability_cases.csv`: high-error compounds with scaffold, fragments, and risk-calibrated scores when available.",
        "",
        "## Manuscript use",
        "",
        "- Use `top_motif_importance_summary.csv` for the strengthened motif attribution table.",
        "- Use `high_error_interpretability_cases.csv` for 5-10 reviewer-facing chemical case studies.",
        "- Link this section to recent functional-group representation and hierarchical atom-motif-molecule literature.",
        "",
        "## Counts",
        "",
        f"- Top motif rows: {len(top_motifs)}",
        f"- Enrichment rows: {len(enrichment)}",
        f"- High-error case rows: {len(cases)}",
        f"- Family summary rows: {len(family)}",
        "",
    ]
    (OUT_DIR / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    top_motifs = build_top_motif_table()
    enrichment = build_fragment_enrichment_table()
    cases = build_high_error_case_table(top_motifs)
    family = build_family_summary(top_motifs)
    write_readme(top_motifs, enrichment, cases, family)
    print(f"Wrote interpretability strengthening report to {OUT_DIR}")


if __name__ == "__main__":
    main()
