from __future__ import annotations

import csv
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "output" / "paper14_work"
REFS = WORK / "references_extracted.txt"
OUT = WORK / "reference_audit.csv"


def fetch_json(url: str) -> tuple[int, dict | None, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "paper14-reference-audit/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode("utf-8")), ""
    except Exception as e:
        return 0, None, str(e)


def clean_title(ref: str) -> str:
    no_num = re.sub(r"^\[\d+\]\s*", "", ref)
    parts = no_num.split(". ")
    if len(parts) >= 2:
        return parts[1].strip().rstrip(".")
    return no_num[:120]


def year_from_item(item: dict) -> str:
    for key in ("published-print", "published-online", "published", "issued"):
        parts = item.get(key, {}).get("date-parts", [])
        if parts and parts[0]:
            return str(parts[0][0])
    return ""


def pages_from_item(item: dict) -> str:
    return item.get("page", "") or item.get("article-number", "")


def main() -> None:
    rows = []
    for line in REFS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        pid, ref = line.split("\t", 1)
        doi_match = re.search(r"doi:([^\s.]+(?:\.[^\s.]+)*)", ref, flags=re.I)
        arxiv_match = re.search(r"arXiv:([0-9.]+)", ref, flags=re.I)
        url_match = re.search(r"https?://[^\s.]+(?:\.[^\s.]+)*", ref)
        title = clean_title(ref)
        row = {
            "paragraph_id": pid,
            "reference": ref,
            "declared_doi": doi_match.group(1).rstrip(".") if doi_match else "",
            "declared_arxiv": arxiv_match.group(1) if arxiv_match else "",
            "declared_url": url_match.group(0) if url_match else "",
            "queried": "",
            "status": "",
            "crossref_title": "",
            "crossref_year": "",
            "crossref_container": "",
            "crossref_volume": "",
            "crossref_page": "",
            "crossref_doi": "",
            "note": "",
        }
        if row["declared_doi"]:
            doi = urllib.parse.quote(row["declared_doi"])
            row["queried"] = f"https://api.crossref.org/works/{doi}"
            status, data, err = fetch_json(row["queried"])
            if status == 200 and data:
                item = data.get("message", {})
                row.update(
                    {
                        "status": "doi_found",
                        "crossref_title": (item.get("title") or [""])[0],
                        "crossref_year": year_from_item(item),
                        "crossref_container": (item.get("container-title") or [""])[0],
                        "crossref_volume": item.get("volume", ""),
                        "crossref_page": pages_from_item(item),
                        "crossref_doi": item.get("DOI", ""),
                    }
                )
            else:
                row["status"] = "doi_not_verified"
                row["note"] = err
            time.sleep(0.15)
        elif row["declared_arxiv"]:
            row["queried"] = f"https://arxiv.org/abs/{row['declared_arxiv']}"
            row["status"] = "arxiv_declared_not_crossref_checked"
        elif row["declared_url"]:
            row["queried"] = row["declared_url"]
            row["status"] = "url_declared_not_crossref_checked"
        else:
            query = urllib.parse.urlencode({"query.bibliographic": title, "rows": 1})
            row["queried"] = f"https://api.crossref.org/works?{query}"
            status, data, err = fetch_json(row["queried"])
            if status == 200 and data and data.get("message", {}).get("items"):
                item = data["message"]["items"][0]
                row.update(
                    {
                        "status": "title_query_top_hit",
                        "crossref_title": (item.get("title") or [""])[0],
                        "crossref_year": year_from_item(item),
                        "crossref_container": (item.get("container-title") or [""])[0],
                        "crossref_volume": item.get("volume", ""),
                        "crossref_page": pages_from_item(item),
                        "crossref_doi": item.get("DOI", ""),
                        "note": f"score={item.get('score', '')}",
                    }
                )
            else:
                row["status"] = "not_verified"
                row["note"] = err
            time.sleep(0.15)
        rows.append(row)

    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(json.dumps({"rows": len(rows), "output": str(OUT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
