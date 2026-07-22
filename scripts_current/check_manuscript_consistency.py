from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLE_DIR = ROOT / "reports" / "manuscript_tables"
PACKAGE = ROOT / "reports" / "submission_package"


CHECKS = [
    {
        "source": "table2_moleculenet_main_long.csv",
        "description": "ESOL selector RMSE",
        "filters": {"dataset": "esol", "category": "FZYC-Mol validation selector"},
        "column": "value",
        "expected": 0.5828733975659611,
        "tolerance": 1e-8,
    },
    {
        "source": "table2_moleculenet_main_long.csv",
        "description": "BACE selector ROC-AUC",
        "filters": {"dataset": "bace", "category": "FZYC-Mol validation selector"},
        "column": "value",
        "expected": 0.8752872411705226,
        "tolerance": 1e-8,
    },
    {
        "source": "table2_moleculenet_main_long.csv",
        "description": "ClinTox selector ROC-AUC",
        "filters": {"dataset": "clintox", "category": "FZYC-Mol validation selector"},
        "column": "value",
        "expected": 0.948912033322636,
        "tolerance": 1e-8,
    },
    {
        "source": "table3_tdc_official_admet.csv",
        "description": "TDC HIA selector ROC-AUC",
        "filters": {"dataset": "tdc_hia_hou"},
        "column": "selector_value",
        "expected": 0.9791872852399404,
        "tolerance": 1e-8,
    },
    {
        "source": "table3_tdc_official_admet.csv",
        "description": "TDC Caco2 selector RMSE",
        "filters": {"dataset": "tdc_caco2_wang"},
        "column": "selector_value",
        "expected": 0.4516883180979844,
        "tolerance": 1e-8,
    },
    {
        "source": "table4_split_realism.csv",
        "description": "ESOL structure-separated RMSE",
        "filters": {"dataset": "esol"},
        "column": "structure_value",
        "expected": 0.7559770853202021,
        "tolerance": 1e-8,
    },
    {
        "source": "table4_split_realism.csv",
        "description": "BACE structure-separated ROC-AUC",
        "filters": {"dataset": "bace"},
        "column": "structure_value",
        "expected": 0.785253816258536,
        "tolerance": 1e-8,
    },
    {
        "source": "table4_split_realism.csv",
        "description": "TDC HIA structure-separated ROC-AUC",
        "filters": {"dataset": "tdc_hia_hou"},
        "column": "structure_value",
        "expected": 0.8252941176470588,
        "tolerance": 1e-8,
    },
    {
        "source": "table6_reliability_ad.csv",
        "description": "Hybrid reconstruction AD Spearman",
        "filters": {"family": "reconstruction_unfamiliarity", "score": "hybrid_recon_ad"},
        "column": "mean_spearman_abs_error",
        "expected": 0.2225213565822892,
        "tolerance": 1e-8,
    },
]


def apply_filters(frame: pd.DataFrame, filters: dict[str, str]) -> pd.DataFrame:
    out = frame
    for column, value in filters.items():
        out = out[out[column].astype(str).eq(str(value))]
    return out


def main() -> None:
    PACKAGE.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for check in CHECKS:
        path = TABLE_DIR / str(check["source"])
        frame = pd.read_csv(path)
        subset = apply_filters(frame, check["filters"])
        if subset.empty:
            actual = None
            status = "missing_row"
            difference = None
        else:
            actual = float(subset.iloc[0][str(check["column"])])
            difference = abs(actual - float(check["expected"]))
            status = "pass" if difference <= float(check["tolerance"]) else "fail"
        rows.append(
            {
                "description": check["description"],
                "source": check["source"],
                "column": check["column"],
                "expected": check["expected"],
                "actual": actual,
                "abs_difference": difference,
                "tolerance": check["tolerance"],
                "status": status,
            }
        )
    audit = pd.DataFrame(rows)
    audit_path = PACKAGE / "number_audit.csv"
    audit.to_csv(audit_path, index=False)

    lines = ["# Number Consistency Audit", ""]
    for _, row in audit.iterrows():
        lines.append(
            f"- **{row['status']}** `{row['description']}`: expected {row['expected']}, actual {row['actual']}"
        )
    status = "PASS" if audit["status"].eq("pass").all() else "CHECK_FAILED"
    lines.extend(["", f"Overall status: **{status}**"])
    (PACKAGE / "number_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {audit_path}")
    print(status)


if __name__ == "__main__":
    main()
