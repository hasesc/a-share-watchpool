#!/usr/bin/env python3
"""Best-effort public announcement risk scanner for A-share candidates."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests
import urllib3


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


ANN_URL = "https://np-anotice-stock.eastmoney.com/api/security/ann"
CNINFO_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://data.eastmoney.com/notices/",
}
CNINFO_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
    "Origin": "http://www.cninfo.com.cn",
}

BLOCK_RULES = [
    ("regulatory_investigation", ["立案", "调查", "行政处罚", "处罚决定", "纪律处分"]),
    ("delisting_or_st", ["退市风险警示", "其他风险警示", "终止上市", "暂停上市", "被实施ST", "被实施 ST"]),
    ("trading_halt", ["停牌", "无法按期披露"]),
    ("default_or_solvency", ["债务逾期", "债务违约", "破产", "重整", "清算"]),
    ("major_litigation", ["重大诉讼", "重大仲裁"]),
    ("governance_red_flag", ["资金占用", "违规担保", "会计差错更正", "内部控制否定"]),
]

WARN_RULES = [
    ("shareholder_reduction", ["减持", "被动减持", "大宗交易减持"]),
    ("unlock", ["限售股上市流通", "解除限售", "解禁"]),
    ("exchange_inquiry", ["监管函", "问询函", "关注函", "警示函"]),
    ("earnings_risk", ["业绩预告", "业绩快报", "亏损", "下修", "计提", "商誉减值"]),
    ("pledge_or_freeze", ["质押", "冻结", "司法冻结"]),
    ("litigation_or_guarantee", ["诉讼", "仲裁", "担保"]),
    ("major_transaction", ["重大资产重组", "发行股份购买资产", "控制权变更"]),
]

CSV_FIELDS = [
    "source",
    "code",
    "title",
    "notice_date",
    "risk_level",
    "risk_category",
    "keywords",
    "action",
    "art_code",
    "url",
]


def suffix_code(code: str) -> str:
    code = code.strip()
    if code.startswith(("6", "9")):
        return f"{code}.SH"
    if code.startswith(("8", "4")):
        return f"{code}.BJ"
    return f"{code}.SZ"


def fetch_announcements_eastmoney(code: str, page_size: int = 50) -> list[dict[str, Any]]:
    import time
    params = {
        "sr": "-1",
        "page_size": page_size,
        "page_index": 1,
        "ann_type": "A",
        "client_source": "web",
        "stock_list": suffix_code(code),
    }
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(ANN_URL, params=params, headers=HEADERS, timeout=15, verify=False)
            response.raise_for_status()
            payload = response.json()
            return (payload.get("data") or {}).get("list") or []
        except Exception as exc:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    return []


def fetch_announcements_cninfo(code: str, page_size: int = 30) -> list[dict[str, Any]]:
    import time
    today = datetime.now()
    begin = (today - timedelta(days=90)).strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")
    data = {
        "stock": code,
        "searchkey": "",
        "plate": "",
        "category": "",
        "trade": "",
        "column": "szse" if not code.startswith(("6", "9")) else "sse",
        "columnTitle": "历史公告查询",
        "pageNum": 1,
        "pageSize": page_size,
        "tabName": "fulltext",
        "sortName": "",
        "sortType": "",
        "limit": "",
        "seDate": f"{begin}~{end}",
    }
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(CNINFO_URL, data=data, headers=CNINFO_HEADERS, timeout=15)
            response.raise_for_status()
            payload = response.json()
            return payload.get("announcements") or []
        except Exception as exc:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    return []


def parse_date(value: str) -> datetime | None:
    if not value:
        return None
    text = value[:10]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None


def scan_title(title: str) -> tuple[str, str, list[str], str]:
    for category, keywords in BLOCK_RULES:
        hits = [kw for kw in keywords if kw in title]
        if hits:
            return "block", category, hits, "block_from_paper_watch"
    for category, keywords in WARN_RULES:
        hits = [kw for kw in keywords if kw in title]
        if hits:
            return "warning", category, hits, "manual_review_or_downgrade"
    return "clear", "", [], "none"


def normalize_notice(code: str, notice: dict[str, Any], source: str) -> dict[str, Any]:
    title = notice.get("title") or notice.get("notice_title") or notice.get("announcementTitle") or ""
    notice_date = notice.get("notice_date") or notice.get("display_time") or notice.get("announcementTime") or ""
    if isinstance(notice_date, int):
        notice_date = datetime.fromtimestamp(notice_date / 1000).strftime("%Y-%m-%d")
    level, category, keywords, action = scan_title(title)
    art_code = notice.get("art_code") or notice.get("notice_id") or ""
    if source == "eastmoney":
        url = f"https://data.eastmoney.com/notices/detail/{suffix_code(code)}/{art_code}.html" if art_code else ""
    else:
        adjunct = notice.get("adjunctUrl") or ""
        url = f"http://static.cninfo.com.cn/{adjunct}" if adjunct else ""
    return {
        "source": source,
        "code": code,
        "title": title,
        "notice_date": notice_date,
        "risk_level": level,
        "risk_category": category,
        "keywords": "、".join(keywords),
        "action": action,
        "art_code": art_code,
        "url": url,
    }


def source_failure_row(code: str, source: str, exc: Exception) -> dict[str, Any]:
    return {
        "source": source,
        "code": code,
        "title": f"公告抓取失败：{type(exc).__name__}: {exc}",
        "notice_date": "",
        "risk_level": "incomplete",
        "risk_category": "source_failed",
        "keywords": "source_failed",
        "action": "block_until_manual_check",
        "art_code": "",
        "url": "",
    }


def check_single_code(code: str, days: int, page_size: int, sources: list[str], cutoff: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    success_sources = []
    failed_sources = []
    source_notices = {}
    for source in sources:
        try:
            if source == "eastmoney":
                notices = fetch_announcements_eastmoney(code, page_size=page_size)
            elif source == "cninfo":
                notices = fetch_announcements_cninfo(code, page_size=page_size)
            else:
                continue
            source_notices[source] = notices
            success_sources.append(source)
        except Exception as exc:
            failed_sources.append((source, exc))
    
    # 决策逻辑
    if len(failed_sources) == len(sources):
        # 所有数据源都挂了，判定为 incomplete 级阻断
        for source, exc in failed_sources:
            rows.append(source_failure_row(code, source, exc))
    else:
        # 至少有一个成功。失败的数据源降级为 warning，不阻断 promotion
        for source, exc in failed_sources:
            row = source_failure_row(code, source, exc)
            row["risk_level"] = "warning"
            row["action"] = "manual_review_or_downgrade"
            rows.append(row)
        
        # 成功的数据源正常解析
        for source in success_sources:
            for notice in source_notices[source]:
                row = normalize_notice(code, notice, source)
                dt = parse_date(row["notice_date"])
                if dt is not None and dt < cutoff:
                    continue
                if row["risk_level"] != "clear":
                    rows.append(row)
    return rows


def check_codes(codes: list[str], days: int, page_size: int, sources: list[str]) -> list[dict[str, Any]]:
    cutoff = datetime.now() - timedelta(days=days)
    rows: list[dict[str, Any]] = []
    
    from concurrent.futures import ThreadPoolExecutor, as_completed
    max_workers = min(16, len(codes) or 1)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(check_single_code, code, days, page_size, sources, cutoff): code
            for code in codes
        }
        for future in as_completed(futures):
            try:
                res = future.result()
                rows.extend(res)
            except Exception as exc:
                code = futures[future]
                rows.append(source_failure_row(code, "thread_pool", exc))
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def summary(rows: list[dict[str, Any]], codes: list[str], days: int) -> dict[str, Any]:
    counts: dict[str, int] = {}
    categories: dict[str, int] = {}
    source_counts: dict[str, dict[str, int]] = {}
    by_code: dict[str, dict[str, Any]] = {}
    for row in rows:
        level = row["risk_level"]
        counts[level] = counts.get(level, 0) + 1
        source = row.get("source") or "unknown"
        source_counts.setdefault(source, {})
        source_counts[source][level] = source_counts[source].get(level, 0) + 1
        category = row.get("risk_category") or "(uncategorized)"
        categories[category] = categories.get(category, 0) + 1
        code = row["code"]
        item = by_code.setdefault(
            code,
            {"block": 0, "warning": 0, "incomplete": 0, "clear": 0, "action": "clear", "notices": []},
        )
        if level in item:
            item[level] += 1
        if level == "block":
            item["action"] = "block_from_paper_watch"
        elif level == "incomplete" and item["action"] != "block_from_paper_watch":
            item["action"] = "block_until_manual_check"
        elif level == "warning" and item["action"] == "clear":
            item["action"] = "manual_review_or_downgrade"
        item["notices"].append(row)
    for code in codes:
        by_code.setdefault(
            code,
            {"block": 0, "warning": 0, "incomplete": 0, "clear": 1, "action": "clear", "notices": []},
        )
    incomplete_codes = [code for code, item in by_code.items() if item.get("incomplete", 0) > 0]
    block_codes = [code for code, item in by_code.items() if item.get("block", 0) > 0]
    warning_codes = [code for code, item in by_code.items() if item.get("warning", 0) > 0]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "lookback_days": days,
        "codes_checked": codes,
        "counts": counts,
        "categories": categories,
        "source_counts": source_counts,
        "by_code": by_code,
        "risk_check_complete": not incomplete_codes,
        "block_codes": block_codes,
        "warning_codes": warning_codes,
        "incomplete_codes": incomplete_codes,
        "promote_allowed_by_risk_check": not block_codes and not incomplete_codes,
        "rule": "block means do not promote to paper watch; warning means manual review/downgrade; incomplete blocks promotion until manually checked.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check recent A-share announcement risk events.")
    parser.add_argument("--codes", required=True, help="Comma-separated stock codes.")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--sources", default="eastmoney,cninfo", help="Comma-separated: eastmoney,cninfo")
    parser.add_argument("--output", required=True, help="JSON output path.")
    parser.add_argument("--csv-output", help="Optional CSV output path.")
    args = parser.parse_args()

    codes = [item.strip() for item in args.codes.split(",") if item.strip()]
    sources = [item.strip() for item in args.sources.split(",") if item.strip()]
    rows = check_codes(codes, days=args.days, page_size=args.page_size, sources=sources)
    result = summary(rows, codes, args.days)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.csv_output:
        write_csv(Path(args.csv_output), rows)
    print(f"Wrote {out} with {len(rows)} risk rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
