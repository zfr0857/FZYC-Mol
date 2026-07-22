from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TABLE_DIR = ROOT / "reports" / "manuscript_tables"
DOCS = ROOT / "docs"
PILOT_DIR = ROOT / "reports" / "strong_tabpfn_moleculenet_pilot_20260603"
TDC_SMOKE_DIR = ROOT / "reports" / "tdc_tabpfn_guard_smoke_20260603"

TABLE47 = TABLE_DIR / "table47_strong_baseline_model_coverage.csv"
TABLE48 = TABLE_DIR / "table48_low_performance_targeted_actions.csv"
TABLE49 = TABLE_DIR / "table49_same_split_model_comparison_registry.csv"
DOC_MD = DOCS / "strong_baseline_model_improvement_update_20260603.md"


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def fmt(value: object, digits: int = 4) -> str:
    try:
        value = float(value)
    except Exception:
        return "NA"
    if not np.isfinite(value):
        return "NA"
    return f"{value:.{digits}f}"


def dependency_status() -> dict[str, object]:
    path = PILOT_DIR / "dependency_status.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def selected_line() -> str:
    selected = read_csv(PILOT_DIR / "selected_metrics_raw.csv")
    if selected.empty:
        return "pilot run has not produced selected metrics yet."
    parts = []
    for row in selected.itertuples(index=False):
        parts.append(
            f"{row.dataset}: {row.model}, valid={fmt(row.validation_primary)}, test={fmt(row.primary_value)}"
        )
    return "; ".join(parts)


def tdc_smoke_line() -> str:
    selected = read_csv(TDC_SMOKE_DIR / "selected_metrics_raw.csv")
    if selected.empty:
        return "TDC guard smoke has not produced selected metrics yet."
    parts = []
    for row in selected.itertuples(index=False):
        parts.append(
            f"{row.dataset}: {row.model}, valid={fmt(row.validation_primary)}, test={fmt(row.primary_value)}"
        )
    return "; ".join(parts)


def build_model_coverage() -> pd.DataFrame:
    deps = dependency_status()
    tabpfn_state = "package installed; runtime not ready" if deps.get("tabpfn") and not deps.get("tabpfn_ready") else "ready"
    rows = [
        {
            "priority": 1,
            "model_or_direction": "TabPFNv2 + RDKit descriptors/Morgan/embedding",
            "current_status": tabpfn_state,
            "evidence_file": "scripts/run_nature_multimethod_fusion_appendix.py; scripts/run_tdc_performance_mode_appendix.py",
            "result_or_decision": "Candidate path added with PCA, train-size guard, and non-interactive readiness check; skipped until TABPFN_TOKEN/model cache is available.",
            "paper_location": "main text or strong appendix after authorization",
            "next_action": "Accept TabPFN license or set TABPFN_TOKEN, then rerun full validation-only integration.",
        },
        {
            "priority": 1,
            "model_or_direction": "CatBoost / XGBoost / LightGBM / ExtraTrees / RF",
            "current_status": "implemented and runnable",
            "evidence_file": "reports/strong_tabpfn_moleculenet_pilot_20260603; reports/tdc_performance_mode_appendix",
            "result_or_decision": "Strong tree baselines are already in the selector pool; pilot did not beat retained-best on FreeSolv/Lipo/ClinTox, so no main-table overwrite.",
            "paper_location": "main comparison table and appendix",
            "next_action": "Keep as mandatory same-split head-to-head baselines; run full formal integration only when changing selector policy.",
        },
        {
            "priority": 2,
            "model_or_direction": "Chemprop / D-MPNN",
            "current_status": "existing baseline outputs found",
            "evidence_file": "reports/chemprop_baseline/metrics_summary.csv",
            "result_or_decision": "Use as same-split deep learning baseline rather than literature-only comparison.",
            "paper_location": "model comparison appendix",
            "next_action": "Add compact row in comparison table; do not restart full deep training unless a missing endpoint is critical.",
        },
        {
            "priority": 2,
            "model_or_direction": "ChemBERTa / MoLFormer frozen embedding + tree/MLP/stacking",
            "current_status": "implemented through frozen embedding heads",
            "evidence_file": "data/processed/pretrained_embeddings; reports/nature_multimethod_fusion_appendix",
            "result_or_decision": "Frozen embedding heads are useful complementary views; validation-only fusion decides whether they are retained.",
            "paper_location": "model structure supplement and appendix",
            "next_action": "Keep frozen-encoder setting; avoid large fine-tuning restart unless targeted endpoint evidence is strong.",
        },
        {
            "priority": 2,
            "model_or_direction": "Top-K mean / validation stacking / uncertainty-aware fusion",
            "current_status": "implemented",
            "evidence_file": "reports/nature_multimethod_fusion_appendix; reports/tdc_performance_mode_appendix",
            "result_or_decision": "Most useful as selector improvement rather than model-count expansion; pilot selected stack/rank fusion for all three tested endpoints.",
            "paper_location": "selector and ablation subsection",
            "next_action": "If formally optimizing main results, pre-fix risk_adjusted_lambda_0.5 or stability tie-breaker and rerun once.",
        },
        {
            "priority": 2,
            "model_or_direction": "Target transform selector for regression",
            "current_status": "implemented for TDC; available in MoleculeNet fusion script",
            "evidence_file": "reports/tdc_performance_mode_appendix/candidate_metrics_raw.csv",
            "result_or_decision": "Best suited to long-tail ADME regression endpoints such as clearance, half-life, PPBR, VDss, and Caco2.",
            "paper_location": "low-performance regression subsection",
            "next_action": "Report transform as endpoint-wise validation-only candidate, not as universal replacement.",
        },
        {
            "priority": 2,
            "model_or_direction": "Balanced undersampling ensemble for imbalanced classification",
            "current_status": "implemented",
            "evidence_file": "reports/tdc_performance_mode_appendix; reports/manuscript_tables/table22_imbalanced_classification_metrics.csv",
            "result_or_decision": "Adds PR-AUC, Brier, ECE, MCC, and balanced accuracy evidence so ROC-AUC is not the only signal.",
            "paper_location": "reliability and imbalance appendix",
            "next_action": "Use for ClinTox, DILI, hERG, and CYP substrate tasks.",
        },
        {
            "priority": 3,
            "model_or_direction": "KPGT / GROVER / Graphormer-lite / Uni-Mol / 3D encoder",
            "current_status": "not recommended as full-panel rerun",
            "evidence_file": "reports/manuscript_tables/table35_3d_roughness_regression_retained_best.csv",
            "result_or_decision": "3D-lite/roughness pilot did not pass validation gate; keep 3D/graph transformer as targeted appendix only.",
            "paper_location": "limitations and targeted appendix",
            "next_action": "Consider only for FreeSolv/ESOL/Lipo targeted case study if time allows.",
        },
    ]
    return pd.DataFrame(rows)


def build_targeted_actions() -> pd.DataFrame:
    retained = read_csv(TABLE_DIR / "table44_strong_tabpfn_moleculenet_retained_best.csv")
    lookup = {str(row.dataset): row for row in retained.itertuples(index=False)} if not retained.empty else {}
    rows = []
    for dataset, issue, action in [
        ("freesolv", "remaining low-regression module", "Do not promote pilot result; keep targeted_rebuild retained-best and discuss as remaining limitation."),
        ("lipo", "rescue-sensitive endpoint", "Keep current retained-best; use pilot to show that stacking is considered but not accepted when validation/test retained gate is worse."),
        ("clintox", "imbalanced high-risk classification", "Prioritize PR-AUC/Brier/ECE/uncertainty case study over ROC-AUC chasing."),
    ]:
        row = lookup.get(dataset)
        rows.append(
            {
                "endpoint_group": dataset,
                "issue": issue,
                "current_retained_or_reference": fmt(getattr(row, "previous_retained_primary_mean", np.nan)) if row is not None else "NA",
                "pilot_strong_baseline": fmt(getattr(row, "fusion_primary_mean", np.nan)) if row is not None else "NA",
                "delta_vs_retained": fmt(getattr(row, "delta_vs_previous_retained", np.nan)) if row is not None else "NA",
                "decision": "retain previous best",
                "recommended_text": action,
            }
        )
    rows.extend(
        [
            {
                "endpoint_group": "ADME regression",
                "issue": "long-tail target and local roughness",
                "current_retained_or_reference": "see table15/table32",
                "pilot_strong_baseline": "target-transform candidates available",
                "delta_vs_retained": "endpoint-specific",
                "decision": "appendix-level targeted improvement",
                "recommended_text": "Emphasize target transform, roughness diagnosis, and validation-only retained-best gate.",
            },
            {
                "endpoint_group": "CYP substrate / DILI / hERG",
                "issue": "class imbalance and calibration risk",
                "current_retained_or_reference": "see table22",
                "pilot_strong_baseline": "underbagging implemented",
                "delta_vs_retained": "endpoint-specific",
                "decision": "add reliability metrics",
                "recommended_text": "Report PR-AUC, Brier, ECE, MCC, balanced accuracy, and calibration curves.",
            },
            {
                "endpoint_group": "TabPFNv2",
                "issue": "strong baseline pending authorization",
                "current_retained_or_reference": "not yet runnable",
                "pilot_strong_baseline": "skipped",
                "delta_vs_retained": "NA",
                "decision": "code-ready but not result-ready",
                "recommended_text": "Do not cite numeric TabPFN performance until license/token/cache is ready and full validation-only run finishes.",
            },
        ]
    )
    return pd.DataFrame(rows)


def build_comparison_registry() -> pd.DataFrame:
    rows = []
    sources = [
        ("MoleculeNet Nature fusion", ROOT / "reports" / "nature_multimethod_fusion_appendix" / "candidate_metrics_raw.csv"),
        ("MoleculeNet strong pilot", PILOT_DIR / "candidate_metrics_raw.csv"),
        ("TDC performance mode", ROOT / "reports" / "tdc_performance_mode_appendix" / "candidate_metrics_raw.csv"),
        ("TDC TabPFN guard smoke", TDC_SMOKE_DIR / "candidate_metrics_raw.csv"),
        ("Chemprop D-MPNN", ROOT / "reports" / "chemprop_baseline" / "metrics_raw.csv"),
    ]
    for source, path in sources:
        frame = read_csv(path)
        if frame.empty:
            rows.append(
                {
                    "source": source,
                    "file": str(path.relative_to(ROOT)),
                    "n_rows": 0,
                    "model_families": "missing",
                    "same_split_use": "not available",
                }
            )
            continue
        model_col = "model" if "model" in frame.columns else "model_name" if "model_name" in frame.columns else None
        families = "unknown" if model_col is None else "; ".join(sorted(set(frame[model_col].astype(str)))[:24])
        rows.append(
            {
                "source": source,
                "file": str(path.relative_to(ROOT)),
                "n_rows": int(len(frame)),
                "model_families": families,
                "same_split_use": "head-to-head candidate pool" if source != "Chemprop D-MPNN" else "deep baseline comparison",
            }
        )
    rows.append(
        {
            "source": "TabPFNv2",
            "file": "scripts/run_nature_multimethod_fusion_appendix.py; scripts/run_tdc_performance_mode_appendix.py",
            "n_rows": 0,
            "model_families": "tabpfn_hier_motif/morgan/embedding heads after authorization",
            "same_split_use": "pending license/token/cache",
        }
    )
    return pd.DataFrame(rows)


def write_markdown(model_coverage: pd.DataFrame, targeted: pd.DataFrame, registry: pd.DataFrame) -> None:
    deps = dependency_status()
    lines = [
        "# 强模型对照与性能补强更新（2026-06-03）",
        "",
        "本轮按两个方向推进：第一，补齐强模型对照，特别是 TabPFNv2、CatBoost/XGBoost/LightGBM/ExtraTrees/RF、Chemprop/D-MPNN、冻结 ChemBERTa/MoLFormer 表征；第二，补强真正可能提升性能的实验方向，包括 target transform、balanced undersampling、Top-K/stacking 和 selector tie-breaker。",
        "",
        "## 已完成的代码和实验",
        "",
        "- `run_nature_multimethod_fusion_appendix.py` 已新增 TabPFN descriptor/Morgan/embedding heads，并接入 Top-K、stacking、uncertainty-weighted fusion 与 AD-gating。",
        "- `run_tdc_performance_mode_appendix.py` 已加入 TabPFN runtime-ready guard，避免未授权时触发交互登录导致实验中断。",
        f"- 当前依赖状态：xgboost={deps.get('xgboost')}, catboost={deps.get('catboost')}, tabpfn={deps.get('tabpfn')}, tabpfn_ready={deps.get('tabpfn_ready')}.",
        f"- MoleculeNet pilot 结果：{selected_line()}。",
        f"- TDC guard smoke 结果：{tdc_smoke_line()}。",
        "",
        "## 关键判断",
        "",
        "本轮 pilot 不建议覆盖主结果。FreeSolv、Lipo 和 ClinTox 的强候选在单 seed pilot 中均未超过已有 retained-best，因此应作为 appendix/pilot 证据保留，而不是强行写成主结果提升。这个处理更符合 validation-only 原则，也能避免审稿人质疑 cherry-picking。",
        "",
        "TabPFNv2 目前属于“代码已接入、结果未就绪”。包已安装，但本机尚未完成 PriorLabs/TabPFN license/token/cache 准备，因此自动实验会跳过它。授权后可以直接复用同一脚本重跑正式 integration。",
        "",
        "## 建议写入论文的实验叙述",
        "",
        "在模型对照部分，应把树模型全套、Chemprop/D-MPNN、冻结分子语言模型表征和 TabPFN 放在同一张模型覆盖表中。TabPFN 只报告实现状态和待授权重跑，不报告数值。对于低分模块，正文重点写 Lipo rescue 已有 retained-best、FreeSolv 仍是 remaining limitation、ADME regression 受长尾 target 和 roughness 影响、ClinTox/CYP substrate 需要 PR-AUC/Brier/ECE 等可靠性指标。",
        "",
        "## 下一轮正式冲分命令",
        "",
        "授权 TabPFN 后，可运行：",
        "",
        "```powershell",
        "py scripts\\run_nature_multimethod_fusion_appendix.py --datasets esol freesolv lipo bbbp bace clintox --seeds 13 17 23 29 31 --no-resume --n-estimators 160 --embedding-pca 96 --undersampling-bags 7 --include-xgb --include-catboost --include-tabpfn --tabpfn-estimators 4 --tabpfn-max-train 2048 --tabpfn-pca 96",
        "py scripts\\run_tdc_performance_mode_appendix.py --seeds 13 17 23 --no-resume --n-estimators 180 --undersampling-bags 5 --include-catboost --include-tabpfn --tabpfn-estimators 4 --tabpfn-max-train 2048",
        "```",
        "",
        "若不授权 TabPFN，则下一步更值得做 selector 改进：固定 `risk_adjusted_lambda_0.5` 或 `stability_tie_breaker` 其中一个策略，再跑一次 formal integration，而不是继续堆候选模型。",
        "",
        "## 输出文件",
        "",
        f"- 模型覆盖表：`{TABLE47.relative_to(ROOT)}`",
        f"- 低分模块补强表：`{TABLE48.relative_to(ROOT)}`",
        f"- same-split 对照注册表：`{TABLE49.relative_to(ROOT)}`",
    ]
    DOCS.mkdir(parents=True, exist_ok=True)
    DOC_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    model_coverage = build_model_coverage()
    targeted = build_targeted_actions()
    registry = build_comparison_registry()
    model_coverage.to_csv(TABLE47, index=False)
    targeted.to_csv(TABLE48, index=False)
    registry.to_csv(TABLE49, index=False)
    write_markdown(model_coverage, targeted, registry)
    print(f"wrote {TABLE47.relative_to(ROOT)}")
    print(f"wrote {TABLE48.relative_to(ROOT)}")
    print(f"wrote {TABLE49.relative_to(ROOT)}")
    print(f"wrote {DOC_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
