#!/usr/bin/env python3
"""Check theme/sector concentration for a watchpool candidate list."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


THEME_RULES = [
    ("硬科技电子链", ("AI", "算力", "服务器", "PCB", "封装", "半导体", "芯片", "消费电子", "光学", "电子", "通信", "光模块")),
    ("机器人高端制造", ("机器人", "工业母机", "自动化", "高端制造", "机床")),
    ("新能源链", ("新能源", "锂电", "储能", "光伏", "风电", "电池")),
    ("医药医疗", ("医药", "医疗", "创新药", "CXO", "器械")),
    ("金融地产", ("银行", "保险", "证券", "地产")),
    ("消费", ("白酒", "食品", "家电", "消费", "旅游", "零售")),
    ("周期资源", ("有色", "煤炭", "钢铁", "化工", "资源", "油气")),
]


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_report(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for key in ("tradable_candidates", "premarket_inference_candidates", "research_leads", "candidates"):
        for item in data.get(key) or []:
            if isinstance(item, dict):
                rows.append(item)
    return rows


def family_for(row: dict[str, Any]) -> str:
    text = " ".join(str(row.get(key) or "") for key in ("sector", "scarce_layer", "core_logic", "name"))
    for family, keywords in THEME_RULES:
        if any(keyword in text for keyword in keywords):
            return family
    sector = str(row.get("sector") or "").strip()
    if sector:
        return sector.replace(" / ", "/").split("/")[0].split("、")[0].split(",")[0]
    return "未分类"


def load_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if args.report:
        rows.extend(read_report(Path(args.report)))
    if args.candidates:
        rows.extend(read_csv(Path(args.candidates)))
    if args.codes:
        rows.extend({"code": code.strip()} for code in args.codes.split(",") if code.strip())
    return rows


def evaluate(rows: list[dict[str, Any]], top_n: int, max_same_family: int) -> dict[str, Any]:
    selected = rows[:top_n]
    families = [family_for(row) for row in selected]
    counts = Counter(families)
    max_family, max_count = counts.most_common(1)[0] if counts else ("", 0)
    warning = max_count > max_same_family
    block = len(selected) >= 3 and max_count == len(selected)
    if block:
        action = "block_or_reduce_top_list"
    elif warning:
        action = "manual_review_or_reduce"
    else:
        action = "clear"
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "top_n": top_n,
        "max_same_family": max_same_family,
        "counts": dict(counts),
        "max_family": max_family,
        "max_count": max_count,
        "concentration_action": action,
        "block_concentration": block,
        "warning_concentration": warning,
        "by_code": [
            {
                "rank": idx + 1,
                "code": row.get("code"),
                "name": row.get("name"),
                "sector": row.get("sector"),
                "theme_family": family_for(row),
            }
            for idx, row in enumerate(selected)
        ],
        "rule": "If all top candidates share one theme family, reduce the list or move some names to research leads.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check candidate theme/sector concentration.")
    parser.add_argument("--report", help="Report JSON path.")
    parser.add_argument("--candidates", help="Candidate CSV/log path.")
    parser.add_argument("--codes", help="Fallback comma-separated codes.")
    parser.add_argument("--top-n", type=int, default=3)
    parser.add_argument("--max-same-family", type=int, default=2)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    rows = load_rows(args)
    if not rows:
        raise SystemExit("provide --report, --candidates, or --codes")
    result = evaluate(rows, args.top_n, args.max_same_family)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out} concentration_action={result['concentration_action']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
