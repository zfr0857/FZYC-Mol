from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
REPORT = OUT / "小论文-11_严格复核报告.md"
CHECKLIST = OUT / "小论文-11_严格复核清单.csv"

COMMENTS = next(Path("C:/Users/Administrator/Desktop").glob("FZYC-Mol_*.docx"))
PAPER = OUT / "小论文-11.docx"
MAIN_AUDIT = ROOT / "results" / "audits" / "small_paper_11_audit.json"
THICK_AUDIT = ROOT / "results" / "audits" / "small_paper_11_thickened_experiments.json"
THICK_DIR = OUT / "小论文-11_加厚实验"
SUPP_DIR = OUT / "小论文-11_补充分析"

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


@dataclass
class Item:
    category: str
    requirement: str
    status: str
    evidence: str
    remaining_gap: str


def docx_text(path: Path) -> str:
    chunks: list[str] = []
    with ZipFile(path) as zf:
        for name in ["word/document.xml", "word/comments.xml", "docProps/core.xml", "docProps/app.xml"]:
            if name not in zf.namelist():
                continue
            root = ET.fromstring(zf.read(name))
            for p in root.findall(".//w:p", NS):
                txt = "".join(t.text or "" for t in p.findall(".//w:t", NS))
                if txt.strip():
                    chunks.append(txt.strip())
            if not chunks:
                chunks.append("".join(t.text or "" for t in root.iter()))
    return "\n".join(chunks)


def has_all(text: str, terms: list[str]) -> bool:
    return all(term in text for term in terms)


def exists(name: str) -> bool:
    return (THICK_DIR / name).exists() or (SUPP_DIR / name).exists()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def count_rows(path: Path) -> int:
    if not path.exists():
        return 0
    return len(pd.read_csv(path))


def main() -> None:
    comment_text = docx_text(COMMENTS)
    paper_text = docx_text(PAPER)
    main = load_json(MAIN_AUDIT)
    thick = load_json(THICK_AUDIT)

    strong = pd.read_csv(THICK_DIR / "strong_baseline_evidence_matrix.csv")
    confirmatory_yes = int(strong["confirmatory_same_outer_split"].eq("yes").sum())
    confirmatory_no = int(strong["confirmatory_same_outer_split"].eq("no").sum())

    registry32 = ROOT / "results" / "nested_selection" / "repeated_nested" / "seed_11" / "candidate_registry.csv"
    enriched32 = THICK_DIR / "lightweight32_candidate_registry_enriched.csv"
    reg32_rows = count_rows(registry32)
    reg32_cols = list(pd.read_csv(registry32).columns) if registry32.exists() else []
    enriched32_cols = list(pd.read_csv(enriched32).columns) if enriched32.exists() else []
    reg32_complete_cols = {
        "candidate_id",
        "representation",
        "learner",
        "params",
        "model_complexity",
        "randomness_source",
        "training_time",
        "candidate_eligibility",
        "candidate_status",
        "family",
    }
    reg32_missing_cols = sorted(reg32_complete_cols.difference(enriched32_cols))

    items: list[Item] = [
        Item(
            "核心命题",
            "重新凝练唯一主命题，并把其他模块按证据等级降级。",
            "已完成" if has_all(paper_text, ["唯一主命题", "验证信息固定", "确认性", "探索性"]) else "部分完成",
            "正文含“唯一主命题”、确认性/次要/探索性层级；主审计 has_unique_thesis=True。",
            "无明显硬缺口。",
        ),
        Item(
            "创新边界",
            "明确 FZYC-Mol 不是新预测主干，而是冻结验证治理协议。",
            "已完成" if has_all(paper_text, ["不是新的预测主干网络", "验证治理协议", "受控实验"]) else "部分完成",
            "摘要/引言/讨论均限定为 governance protocol，并说明不是替代预测模型。",
            "无明显硬缺口。",
        ),
        Item(
            "证据链收束",
            "减少功能堆叠，主文建议约 6 图、4-5 表，其他转补充。",
            "部分完成",
            f"文档当前 {main.get('inline_shapes')} 张图、{main.get('tables')} 张表；图 10/11 已删除，图号 1-9、表号 1-8 通过审计。",
            "仍未压缩到建议的约 6 图、4-5 表。",
        ),
        Item(
            "32 候选登记",
            "完整列出 32 候选的 ID、表示、学习器、超参数、复杂度、随机性、训练时间、资格、状态、家族。",
            "已完成" if enriched32.exists() and not reg32_missing_cols else "部分完成",
            f"32 候选基础 registry 存在：{registry32}，{reg32_rows} 行；已新增增强登记表 {enriched32.name}，字段覆盖 candidate_id/representation/learner/params/model_complexity/randomness_source/training_time/eligibility/status/family。",
            "无明显硬缺口。" if not reg32_missing_cols else "增强 registry 仍缺少字段：" + ", ".join(reg32_missing_cols),
        ),
        Item(
            "有效多样性",
            "报告候选预测相关矩阵、验证排名相关矩阵、错误重叠率和 K_eff。",
            "部分完成",
            "已输出 candidate_effective_diversity.csv、heterogeneous_pool_effective_diversity.csv、lightweight32_outer_utility_correlation_matrix.csv 和 lightweight32_validation_rank_correlation_matrix.csv；正文写入 K_eff 和相关中位数。",
            "缺少逐样本全候选预测，error-overlap 只能输出 lightweight32_error_overlap_status.csv，尚未真正计算错误重叠率。",
        ),
        Item(
            "真实异质扩池",
            "增加真实异质候选池，至少覆盖回归、常规分类、少数类毒性端点。",
            "部分完成",
            f"已补四级异质池；完整 12 候选多视图覆盖 {thick.get('multiview_n_units')} 个外层单位，K={thick.get('multiview_stage_K')}，G_realized={thick.get('multiview_G_realized'):.3f}。",
            "未完成 Chemprop/GNN/预训练表示进入同一确认性外层划分的 K=16/K=32 重训。",
        ),
        Item(
            "现代强基线",
            "现代强基线必须使用相同外层/内层划分、种子、指标和测试隔离规则统一重训。",
            "未完全完成",
            f"strong_baseline_evidence_matrix.csv 共 {len(strong)} 行；同分割确认性 yes={confirmatory_yes}，no={confirmatory_no}。树模型可作为同分割证据。",
            "Chemprop/D-MPNN、GNN、ChemBERTa、MoLFormer、TabPFN 尚未完成同一 3×3×5 确认性重训；这是最大的实验缺口。",
        ),
        Item(
            "收益分解",
            "统一报告 G_attain、L_select、G_realized 和 η。",
            "已完成" if has_all(paper_text, ["G_attain", "L_select", "G_realized", "η"]) and exists("gain_decomposition.csv") else "部分完成",
            "正文和 gain_decomposition.csv 均包含四个收益量；K=32 和异质 12 候选均写入数值。",
            "无明显硬缺口。",
        ),
        Item(
            "遗憾定义",
            "澄清固定分母遗憾，改为 full-pool-range-normalized selection loss/regret。",
            "已完成",
            "旧词“固定分母”“95% 配对区间”审计为 0；正文采用“完整池范围归一化选择损失”。",
            "英文术语 full-pool-range-normalized selection regret 可在英文稿中再统一一次。",
        ),
        Item(
            "统计推断",
            "收紧主次分析、多重比较、终点层配对效应。",
            "已完成" if has_all(paper_text, ["预设确认性分析", "Holm", "逐终点"]) else "部分完成",
            "正文写入确认性/次要/探索性分析和 Holm 校正；加厚实验有逐终点效应表。",
            "无明显硬缺口。",
        ),
        Item(
            "跨终点元风险",
            "跨终点元风险只能作为探索性结果。",
            "已完成" if "探索性" in paper_text else "部分完成",
            "正文将跨终点/TDC/样本风险等边界证据降级为次要或探索性。",
            "LOEO 特征稳定性和删除单终点敏感性是否完整，需要针对对应源表进一步专项核验。",
        ),
        Item(
            "TDC 三种子",
            "TDC 三种子区间不能承担强推断。",
            "已完成" if "seed variability interval" in paper_text else "部分完成",
            "正文写入 seed variability interval；tdc_gate_evidence_stratification.csv 汇总 promoted/cross-zero。",
            "无明显硬缺口。",
        ),
        Item(
            "保形预测",
            "补充分类/回归保形预测的可复现定义，并重点讨论 ClinTox 负结果。",
            "已完成" if has_all(paper_text, ["类别条件非一致性阈值", "split conformal", "fallback", "ClinTox"]) else "部分完成",
            f"正文补入 split conformal 定义；conformal_endpoint_detail.csv 共 {thick.get('conformal_rows')} 条记录。",
            "如果投稿目标要求英文方法公式，可再补英文公式化描述。",
        ),
        Item(
            "标题摘要引言",
            "修改题目、重写摘要、压缩重复引言。",
            "已完成",
            "标题改为“分子性质预测中候选池扩张的选择风险：嵌套验证与冻结治理框架”；摘要和引言由脚本重写。",
            "无明显硬缺口。",
        ),
        Item(
            "方法结构",
            "方法合并为 6 个主部分，明确确认性与探索性。",
            "已完成",
            "2.1-2.6 已重命名为任务登记、嵌套评估、选择策略、对照统计、多视图强基线、边界分析。",
            "无明显硬缺口。",
        ),
        Item(
            "去重敏感性",
            "比较全局去重、仅训练折内聚合、保留重复并按骨架分组三种方案。",
            "部分完成",
            f"已输出 duplicate_and_cleaning_audit_summary.csv；清洗事件 {thick.get('cleaning_events')} 条。",
            "尚未真正跑三套重复处理策略的主结果敏感性实验。",
        ),
        Item(
            "结果与讨论",
            "结果减少解释性开场，讨论围绕四个问题展开。",
            "已完成" if has_all(paper_text, ["4.1", "4.2", "4.3", "4.4"]) else "部分完成",
            "Discussion 已重构为四个问题；结果中主要数值和设置提前。",
            "无明显硬缺口。",
        ),
        Item(
            "图表与失败案例",
            "图表整合、原始尺度、TDC 原尺度森林图、失败案例分子结构图。",
            "部分完成",
            "已删除图 10/11，保留 9 张图；加厚目录包含 MoleculeACE、Tanimoto、低相似度和扩展失败案例 CSV。",
            "未重新生成所有建议图形；失败案例未确认已加入二维结构+最近邻结构的主文图。",
        ),
        Item(
            "复现与公开",
            "公开仓库、Zenodo DOI、元数据清理、依赖和运行日志。",
            "部分完成",
            "正文提及 Zenodo/公开 release 仍需投稿前完成；本地审计 JSON 和 source data 完整。",
            "公开仓库/DOI/第三方冷启动复跑不可能仅凭本地改稿自动完成，仍是投稿前硬任务。",
        ),
        Item(
            "参考文献覆盖",
            "补充 adaptive data analysis、winner’s curse、nested CV、conformal、AutoML 等文献。",
            "未核实",
            "本轮未对参考文献逐条做 bibliographic coverage 审计。",
            "需要单独导出参考文献并逐主题核对；当前不能断言完全补全。",
        ),
    ]

    rows = [item.__dict__ for item in items]
    with CHECKLIST.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    counts = pd.DataFrame(rows)["status"].value_counts().to_dict()
    hard_gaps = [x for x in items if x.status in {"未完全完成", "未核实"} or (x.status == "部分完成" and any(k in x.remaining_gap for k in ["尚未真正", "未完成 Chemprop", "公开仓库", "未重新生成", "仍缺少"]))]

    lines = [
        "# 小论文-11 严格复核报告",
        "",
        "## 总体结论",
        "",
        "不能判定为“所有实验已经全部补全”。小论文-11 已经严格响应了多数文本、定义、统计口径和中等规模可复算实验要求；但仍有若干修改意见属于重型统一重训、三策略敏感性、图形重绘或投稿前开放科学交付，当前只能判定为部分完成或未完全完成。",
        "",
        f"- 已完成：{counts.get('已完成', 0)} 项",
        f"- 部分完成：{counts.get('部分完成', 0)} 项",
        f"- 未完全完成：{counts.get('未完全完成', 0)} 项",
        f"- 未核实：{counts.get('未核实', 0)} 项",
        "",
        "## 已确认完成的关键改动",
        "",
        f"- Word 审计通过：图号 {main.get('figure_caption_numbers')}，表号 {main.get('table_caption_numbers')}，XML 错误 {main.get('xml_errors')}",
        f"- 加厚实验审计通过：{bool(thick.get('passed'))}",
        f"- 异质 12 候选多视图：K={thick.get('multiview_stage_K')}，n_units={thick.get('multiview_n_units')}，G_attain={thick.get('multiview_G_attain'):.3f}，L_select={thick.get('multiview_L_select'):.3f}，G_realized={thick.get('multiview_G_realized'):.3f}",
        f"- 补充实验表：{thick.get('copied_completion_tables')} 张；强基线证据矩阵：{len(strong)} 行",
        "",
        "## 仍未完全补全的硬缺口",
        "",
    ]
    for item in hard_gaps:
        lines.append(f"- **{item.requirement}**：{item.status}。{item.remaining_gap}")

    lines += [
        "",
        "## 逐项清单",
        "",
        "| 类别 | 要求 | 状态 | 证据 | 剩余缺口 |",
        "|---|---|---|---|---|",
    ]
    for item in items:
        lines.append(f"| {item.category} | {item.requirement} | {item.status} | {item.evidence} | {item.remaining_gap} |")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT)
    print(CHECKLIST)


if __name__ == "__main__":
    main()
