# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
from pathlib import Path

from lxml import etree, html


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "reports" / "draft10_literature_review_20260621" / "sources"
OUT = ROOT / "reports" / "draft10_literature_review_20260621"


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def section_bucket(title: str) -> str:
    low = title.lower()
    if "abstract" in low:
        return "abstract"
    if any(x in low for x in ["method", "material", "experimental", "implementation"]):
        return "methods"
    if any(x in low for x in ["result", "evaluation", "benchmark", "performance"]):
        return "results"
    if "discussion" in low:
        return "discussion"
    if any(x in low for x in ["conclusion", "summary"]):
        return "conclusion"
    if any(x in low for x in ["introduction", "background"]):
        return "introduction"
    return "other"


def parse_html(path: Path) -> dict[str, object]:
    tree = html.fromstring(path.read_bytes())
    title = clean(" ".join(tree.xpath('//meta[@name="citation_title"]/@content'))) or clean(" ".join(tree.xpath("//h1//text()")))
    abstract_nodes = tree.xpath('//div[contains(@class,"c-article-section__content")][preceding-sibling::*[1][self::h2[contains(translate(.,"ABSTRACT","abstract"),"abstract")]]]//p')
    if not abstract_nodes:
        abstract_nodes = tree.xpath('//section[contains(@data-title,"Abstract")]//p | //div[contains(@id,"Abs")]//p')
    abstract = clean(" ".join(" ".join(x.itertext()) for x in abstract_nodes))
    sections: dict[str, list[str]] = {k: [] for k in ["introduction", "methods", "results", "discussion", "conclusion", "other"]}
    for sec in tree.xpath("//section"):
        heading = clean(" ".join(sec.xpath("./h2//text() | ./h3//text() | ./header//h2//text() | ./header//h3//text()")))
        if not heading:
            continue
        text = clean(" ".join(" ".join(p.itertext()) for p in sec.xpath(".//p")))
        if text:
            sections[section_bucket(heading)].append(f"[{heading}] {text}")
    return {"title": title, "abstract": abstract, "sections": {k: clean(" ".join(v)) for k, v in sections.items()}}


def parse_jats(path: Path) -> dict[str, object]:
    tree = etree.parse(str(path))
    title = clean(" ".join(tree.xpath("//article-title//text()")))
    abstract = clean(" ".join(tree.xpath("//abstract//text()")))
    sections: dict[str, list[str]] = {k: [] for k in ["introduction", "methods", "results", "discussion", "conclusion", "other"]}
    for sec in tree.xpath("//body//sec"):
        heading = clean(" ".join(sec.xpath("./title//text()")))
        if not heading:
            continue
        paragraphs = sec.xpath("./p | ./sec/p")
        text = clean(" ".join(" ".join(p.itertext()) for p in paragraphs))
        if text:
            sections[section_bucket(heading)].append(f"[{heading}] {text}")
    return {"title": title, "abstract": abstract, "sections": {k: clean(" ".join(v)) for k, v in sections.items()}}


def keyword_audit(text: str) -> dict[str, int]:
    groups = {
        "model_selection": ["model selection", "candidate selection", "validation selection"],
        "candidate_pool_scale": ["candidate pool", "pool size", "number of candidates", "search space"],
        "nested_validation": ["nested cross-validation", "nested validation", "outer fold", "inner fold"],
        "pre_registration": ["pre-register", "preregister", "registered candidate", "frozen candidate"],
        "negative_results": ["negative result", "failed candidate", "rejected candidate"],
        "applicability_domain": ["applicability domain", "out-of-distribution", "ood"],
        "uncertainty": ["uncertainty", "calibration", "conformal"],
        "activity_cliff": ["activity cliff"],
        "automl": ["automl", "autogluon"],
    }
    low = text.lower()
    return {key: sum(low.count(term) for term in terms) for key, terms in groups.items()}


def main() -> None:
    records: list[dict[str, object]] = []
    for path in sorted(SRC.glob("*.html")):
        record = parse_html(path)
        record["source_file"] = path.name
        records.append(record)
    for path in sorted(SRC.glob("*.xml")):
        record = parse_jats(path)
        record["source_file"] = path.name
        records.append(record)
    for record in records:
        combined = " ".join([record["abstract"], *record["sections"].values()])
        record["keyword_audit"] = keyword_audit(combined)
        record["character_count"] = len(combined)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "extracted_recent_literature.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Recent literature extraction", ""]
    for record in records:
        lines += [
            f"## {record['title']}",
            f"- Source: `{record['source_file']}`",
            f"- Extracted characters: {record['character_count']}",
            f"- Keyword audit: {record['keyword_audit']}",
            "",
            "### Abstract",
            record["abstract"],
            "",
        ]
        for name in ["methods", "results", "discussion", "conclusion"]:
            text = record["sections"].get(name, "")
            if text:
                lines += [f"### {name.title()}", text, ""]
    (OUT / "extracted_recent_literature.md").write_text("\n".join(lines), encoding="utf-8")
    for record in records:
        print(record["source_file"], record["title"], record["character_count"], record["keyword_audit"])


if __name__ == "__main__":
    main()
