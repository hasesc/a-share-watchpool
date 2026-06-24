#!/usr/bin/env python3
"""Collect public A-share data for watchpool validation.

This script uses best-effort public endpoints. Interfaces can change, so reports
must label data quality and keep raw snapshots for audit.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from datetime import date, datetime, time as dtime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests


EASTMONEY_CLIST = "https://push2.eastmoney.com/api/qt/clist/get"
EASTMONEY_KLINE = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
CN_TZ = ZoneInfo("Asia/Shanghai")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://quote.eastmoney.com/",
}

CLIST_FIELDS = [
    "f12",
    "f14",
    "f2",
    "f3",
    "f4",
    "f5",
    "f6",
    "f7",
    "f8",
    "f10",
    "f15",
    "f16",
    "f17",
    "f18",
    "f20",
    "f21",
    "f62",
    "f184",
]

FIELD_MAP = {
    "f12": "code",
    "f14": "name",
    "f2": "latest",
    "f3": "pct_chg",
    "f4": "chg",
    "f5": "volume",
    "f6": "amount",
    "f7": "amplitude",
    "f8": "turnover",
    "f10": "volume_ratio",
    "f15": "high",
    "f16": "low",
    "f17": "open",
    "f18": "prev_close",
    "f20": "total_mv",
    "f21": "float_mv",
    "f62": "main_net",
    "f184": "main_net_pct",
}

AKSHARE_SPOT_COLUMNS = {
    "代码": "source_symbol",
    "名称": "name",
    "最新价": "latest",
    "涨跌额": "chg",
    "涨跌幅": "pct_chg",
    "昨收": "prev_close",
    "今开": "open",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "amount",
    "时间戳": "source_time",
}

EASTMONEY_INDEX_MARKETS = {
    "000300": 1,
    "000905": 1,
    "000852": 1,
    "399006": 0,
}


def request_json(
    url: str,
    params: dict[str, Any],
    *,
    retries: int = 3,
    retry_sleep: float = 0.8,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, params=params, headers=HEADERS, timeout=15, verify=False)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(retry_sleep * attempt)
    assert last_error is not None
    raise last_error


def parse_yyyymmdd(value: Any) -> date | None:
    if value in (None, ""):
        return None
    text = str(value).strip()[:10]
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def fallback_weekday_trade_dates(center: date) -> list[date]:
    start = date(center.year - 1, 1, 1)
    end = date(center.year + 1, 12, 31)
    days: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current = date.fromordinal(current.toordinal() + 1)
    return days


def load_trade_dates(center: date | None = None) -> tuple[list[date], str, list[str]]:
    center = center or datetime.now(CN_TZ).date()
    errors: list[str] = []
    try:
        import akshare as ak  # type: ignore[import-not-found]

        frame = ak.tool_trade_date_hist_sina()
        raw_dates = []
        for item in frame.to_dict(orient="records"):
            raw = item.get("trade_date") or item.get("日期") or next(iter(item.values()), None)
            parsed = parse_yyyymmdd(raw)
            if parsed is not None:
                raw_dates.append(parsed)
        trade_dates = sorted(set(raw_dates))
        if trade_dates:
            return trade_dates, "akshare.tool_trade_date_hist_sina", errors
        errors.append("akshare trade calendar returned no dates")
    except Exception as exc:
        errors.append(f"akshare trade calendar failed: {exc!r}")
    return fallback_weekday_trade_dates(center), "weekday_fallback_not_holiday_adjusted", errors


def nearest_trade_dates(trade_dates: list[date], target: date) -> tuple[date | None, date | None]:
    previous = None
    next_day = None
    for item in trade_dates:
        if item < target:
            previous = item
        elif item > target and next_day is None:
            next_day = item
            break
    return previous, next_day


def classify_a_share_session(now: datetime | None = None) -> dict[str, Any]:
    now = now.astimezone(CN_TZ) if now else datetime.now(CN_TZ)
    today = now.date()
    trade_dates, calendar_source, calendar_errors = load_trade_dates(today)
    trade_set = set(trade_dates)
    previous_trade_day, next_trade_day = nearest_trade_dates(trade_dates, today)
    is_trade_day = today in trade_set
    current_time = now.time()

    if not is_trade_day:
        session = "non_trading_day"
        mode = "no_live_report"
        allow_intraday_sample = False
        allow_post_close_review = False
        message = "今日不是交易日；只能做历史复盘、盘前准备或数据维护。"
    elif current_time < dtime(9, 15):
        session = "pre_market"
        mode = "premarket_preparation"
        allow_intraday_sample = False
        allow_post_close_review = False
        message = "盘前阶段，只能生成中线趋势候选 (20-60日)。"
    elif current_time < dtime(9, 25):
        session = "opening_call_auction"
        mode = "observe_only"
        allow_intraday_sample = False
        allow_post_close_review = False
        message = "开盘集合竞价阶段，不生成尾盘样本。"
    elif current_time < dtime(9, 30):
        session = "pre_open_pause"
        mode = "observe_only"
        allow_intraday_sample = False
        allow_post_close_review = False
        message = "开盘前静默阶段，不生成尾盘样本。"
    elif current_time < dtime(11, 30):
        session = "morning_continuous"
        mode = "intraday_observe_only"
        allow_intraday_sample = False
        allow_post_close_review = False
        message = "上午连续竞价阶段，只观察不生成尾盘确认样本。"
    elif current_time < dtime(13, 0):
        session = "lunch_break"
        mode = "observe_only"
        allow_intraday_sample = False
        allow_post_close_review = False
        message = "午间休市阶段，只做观察和预筛。"
    elif current_time < dtime(14, 30):
        session = "afternoon_continuous"
        mode = "intraday_observe_only"
        allow_intraday_sample = False
        allow_post_close_review = False
        message = "下午连续竞价早段，只观察不生成尾盘确认样本。"
    elif current_time < dtime(14, 50):
        session = "intraday_pre_screen"
        mode = "pre_screen_only"
        allow_intraday_sample = False
        allow_post_close_review = False
        message = "14:30 预筛窗口，只用于缩小候选池。"
    elif current_time < dtime(14, 57):
        session = "late_session_confirmation"
        mode = "late_session_paper_sample"
        allow_intraday_sample = True
        allow_post_close_review = False
        message = "尾盘确认窗口，可生成短线波段样本。"
    elif current_time < dtime(15, 0):
        session = "closing_call_auction"
        mode = "close_formation_observe"
        allow_intraday_sample = False
        allow_post_close_review = False
        message = "收盘集合竞价阶段，只观察收盘价形成。"
    else:
        session = "post_close"
        mode = "post_close_review"
        allow_intraday_sample = False
        allow_post_close_review = True
        message = "收盘后只能生成盘后复盘或次日准备报告。"

    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "timezone": "Asia/Shanghai",
        "date": today.isoformat(),
        "time": current_time.strftime("%H:%M:%S"),
        "is_trade_day": is_trade_day,
        "session": session,
        "recommended_mode": mode,
        "allow_intraday_paper_sample": allow_intraday_sample,
        "allow_post_close_review": allow_post_close_review,
        "previous_trade_day": previous_trade_day.isoformat() if previous_trade_day else None,
        "next_trade_day": next_trade_day.isoformat() if next_trade_day else None,
        "calendar_source": calendar_source,
        "calendar_errors": calendar_errors,
        "message": message,
    }


def eastmoney_market_for_code(code: str) -> int:
    if code in EASTMONEY_INDEX_MARKETS:
        return EASTMONEY_INDEX_MARKETS[code]
    return 1 if code.startswith(("6", "9")) else 0


def secid(code: str) -> str:
    return f"{eastmoney_market_for_code(code)}.{code}"


def sina_symbol(code: str) -> str:
    code = code.strip()
    if code in ("000300", "000905", "000852"):
        return f"sh{code}"
    if code == "399006":
        return f"sz{code}"
    if code.startswith(("6", "9")):
        return f"sh{code}"
    if code.startswith(("8", "4")):
        return f"bj{code}"
    return f"sz{code}"


def to_number(value: Any) -> float | None:
    if value in (None, "-", ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number


def page_size_fallbacks(page_size: int) -> list[int]:
    candidates = [page_size, 5000, 1000, 500, 200, 100, 50, 20, 10, 5]
    out = []
    for size in candidates:
        if size <= page_size and size not in out:
            out.append(max(1, size))
    return out


def normalize_akshare_spot_frame(frame: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in frame.to_dict(orient="records"):
        symbol = str(item.get("代码", "")).strip()
        code = symbol[-6:] if len(symbol) >= 6 else symbol
        row: dict[str, Any] = {target: item.get(source) for source, target in AKSHARE_SPOT_COLUMNS.items()}
        row.update(
            {
                "code": code,
                "source": "akshare_sina_spot",
                "amplitude": None,
                "turnover": None,
                "volume_ratio": None,
                "total_mv": None,
                "float_mv": None,
                "main_net": None,
                "main_net_pct": None,
            }
        )
        rows.append(row)
    return rows


def fetch_market_snapshot_akshare(retries: int = 3) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started = time.time()
    try:
        import akshare as ak  # type: ignore[import-not-found]
    except Exception as exc:
        return [], {
            "fetch_source": "akshare_sina_spot",
            "fetch_status": "failed",
            "source_total_rows": None,
            "source_coverage_ratio": None,
            "elapsed_seconds": round(time.time() - started, 2),
            "fetch_errors": [{"error": f"akshare import failed: {exc!r}"}],
        }
    errors: list[dict[str, Any]] = []
    best_rows: list[dict[str, Any]] = []
    for attempt in range(1, retries + 1):
        attempt_started = time.time()
        try:
            frame = ak.stock_zh_a_spot()
            rows = normalize_akshare_spot_frame(frame)
        except Exception as exc:
            errors.append(
                {
                    "attempt": attempt,
                    "elapsed_seconds": round(time.time() - attempt_started, 2),
                    "error": repr(exc),
                }
            )
            if attempt < retries:
                time.sleep(1.5 * attempt)
            continue
        if len(rows) > len(best_rows):
            best_rows = rows
        if len(rows) >= 3000:
            return rows, {
                "fetch_source": "akshare_sina_spot",
                "fetch_status": "complete",
                "source_total_rows": len(rows),
                "source_coverage_ratio": 1.0,
                "elapsed_seconds": round(time.time() - started, 2),
                "fetch_errors": errors,
                "akshare_attempts": attempt,
            }
        errors.append(
            {
                "attempt": attempt,
                "elapsed_seconds": round(time.time() - attempt_started, 2),
                "error": f"akshare returned only {len(rows)} rows",
            }
        )
        if attempt < retries:
            time.sleep(1.5 * attempt)
    rows = best_rows
    return rows, {
        "fetch_source": "akshare_sina_spot",
        "fetch_status": "partial" if rows else "failed",
        "source_total_rows": len(rows) if rows else None,
        "source_coverage_ratio": 1.0 if len(rows) >= 3000 else None,
        "elapsed_seconds": round(time.time() - started, 2),
        "fetch_errors": errors,
        "akshare_attempts": retries,
    }


def fetch_eastmoney_snapshot_once(page_size: int = 5000, max_pages: int = 3) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    fields = ",".join(CLIST_FIELDS)
    total_rows: int | None = None
    errors: list[dict[str, Any]] = []
    page = 1
    hard_page_limit = max(max_pages, 1)
    while page <= hard_page_limit:
        params = {
            "pn": page,
            "pz": page_size,
            "po": 1,
            "np": 1,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": 2,
            "invt": 2,
            # Sort by code for unbiased full-universe pagination. Sorting by
            # pct_chg can make some public endpoints fail on later pages and
            # overrepresent limit-up names when a partial response is used.
            "fid": "f12",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
            "fields": fields,
        }
        try:
            payload = request_json(EASTMONEY_CLIST, params)
        except Exception as exc:
            errors.append({"page": page, "page_size": page_size, "error": repr(exc)})
            break
        diff = (payload.get("data") or {}).get("diff") or []
        if not diff:
            break
        for item in diff:
            row = {FIELD_MAP[key]: item.get(key) for key in CLIST_FIELDS}
            rows.append(row)
        total_rows = int((payload.get("data") or {}).get("total") or len(rows))
        if total_rows and page == 1:
            expected_pages = math.ceil(total_rows / page_size)
            hard_page_limit = min(max(hard_page_limit, expected_pages), 2000)
        if total_rows and len(rows) >= total_rows:
            break
        page += 1
        time.sleep(0.2)
    if not rows:
        status = "failed"
    elif errors or (total_rows and len(rows) < total_rows):
        status = "partial"
    else:
        status = "complete"
    return rows, {
        "fetch_source": "eastmoney_clist",
        "fetch_status": status,
        "page_size": page_size,
        "source_total_rows": total_rows,
        "source_coverage_ratio": (len(rows) / total_rows) if total_rows else None,
        "pages_requested": page,
        "fetch_errors": errors,
    }


def fetch_eastmoney_snapshot(page_size: int = 5000, max_pages: int = 3) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    attempts = []
    best_rows: list[dict[str, Any]] = []
    best_meta: dict[str, Any] | None = None
    for current_page_size in page_size_fallbacks(page_size):
        rows, meta = fetch_eastmoney_snapshot_once(page_size=current_page_size, max_pages=max_pages)
        attempts.append(dict(meta))
        if best_meta is None or len(rows) > len(best_rows):
            best_rows = rows
            best_meta = meta
        if meta["fetch_status"] == "complete":
            meta["fetch_attempts"] = list(attempts)
            return rows, meta
    if best_meta is not None:
        best_meta["fetch_attempts"] = list(attempts)
        return best_rows, best_meta
    return [], {
        "fetch_status": "failed",
        "page_size": page_size,
        "source_total_rows": None,
        "source_coverage_ratio": None,
        "pages_requested": 0,
        "fetch_errors": [],
        "fetch_attempts": attempts,
    }


def fetch_market_snapshot(
    page_size: int = 5000,
    max_pages: int = 3,
    source: str = "auto",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    best_rows: list[dict[str, Any]] = []
    best_meta: dict[str, Any] | None = None

    if source in ("auto", "akshare"):
        rows, meta = fetch_market_snapshot_akshare()
        attempts.append(dict(meta))
        best_rows, best_meta = rows, meta
        if meta.get("fetch_status") == "complete" and len(rows) >= 3000:
            meta["fetch_attempts"] = list(attempts)
            return rows, meta
        if source == "akshare":
            meta["fetch_attempts"] = list(attempts)
            return rows, meta

    if source in ("auto", "eastmoney"):
        rows, meta = fetch_eastmoney_snapshot(page_size=page_size, max_pages=max_pages)
        attempts.extend(meta.get("fetch_attempts") or [dict(meta)])
        if best_meta is None or len(rows) > len(best_rows):
            best_rows, best_meta = rows, meta
        if meta.get("fetch_status") == "complete":
            meta["fetch_attempts"] = list(attempts)
            return rows, meta

    if best_meta is not None:
        best_meta["fetch_attempts"] = list(attempts)
        return best_rows, best_meta
    return [], {
        "fetch_source": source,
        "fetch_status": "failed",
        "source_total_rows": None,
        "source_coverage_ratio": None,
        "fetch_errors": [{"error": "no source attempted"}],
        "fetch_attempts": attempts,
    }


def market_gate_stats(rows: list[dict[str, Any]], fetch_meta: dict[str, Any] | None = None) -> dict[str, Any]:
    fetch_meta = fetch_meta or {}
    valid_quote_rows = [
        row
        for row in rows
        if to_number(row.get("pct_chg")) is not None
        and to_number(row.get("amount")) is not None
        and to_number(row.get("latest")) is not None
        and to_number(row.get("prev_close")) is not None
    ]
    valid_ratio = len(valid_quote_rows) / len(rows) if rows else 0
    coverage_ratio = fetch_meta.get("source_coverage_ratio")
    coverage_ok = coverage_ratio is not None and coverage_ratio >= 0.95
    fetch_complete = fetch_meta.get("fetch_status") == "complete"
    if len(rows) >= 3000 and valid_ratio >= 0.8 and coverage_ok and fetch_complete:
        data_quality = "complete"
        is_valid = True
    elif len(rows) < 500 or valid_ratio < 0.2:
        data_quality = "failed"
        is_valid = False
    else:
        data_quality = "partial"
        is_valid = False

    tradable = valid_quote_rows
    total = len(tradable)
    up = sum(1 for row in tradable if (to_number(row.get("pct_chg")) or 0) > 0)
    down = sum(1 for row in tradable if (to_number(row.get("pct_chg")) or 0) < 0)
    limit_up = sum(1 for row in tradable if (to_number(row.get("pct_chg")) or 0) >= 9.8)
    limit_down = sum(1 for row in tradable if (to_number(row.get("pct_chg")) or 0) <= -9.8)
    total_amount = sum(to_number(row.get("amount")) or 0 for row in tradable)
    adv_ratio = up / total if total else None
    score = 50
    if adv_ratio is not None:
        score += (adv_ratio - 0.5) * 60
    if limit_up > limit_down * 2:
        score += 8
    if limit_down > limit_up:
        score -= 10
    if total_amount >= 1_000_000_000_000:
        score += 8
    elif total_amount < 700_000_000_000:
        score -= 6
    score = max(0, min(100, round(score, 1)))
    if score >= 80:
        regime, position = "进攻日", "50-70%"
    elif score >= 60:
        regime, position = "试探日", "20-40%"
    elif score >= 40:
        regime, position = "防守日", "0-20%"
    else:
        regime, position = "空仓观察日", "0%"
    downgrades = ["未接入板块强度、炸板率、公告和事件风险，门槛分仅作基础输入。"]
    if not is_valid:
        downgrades.insert(
            0,
            "数据完整性未通过：不得生成短线波段候选 (1-10日)，该日不计入有效验证样本。",
        )
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "score": score,
        "regime": regime,
        "position": position if is_valid else "0%",
        "data_quality": data_quality,
        "is_valid_for_trading_report": is_valid,
        "raw_rows": len(rows),
        "valid_quote_rows": len(valid_quote_rows),
        "valid_quote_ratio": valid_ratio,
        "fetch_status": fetch_meta.get("fetch_status", "unknown"),
        "fetch_source": fetch_meta.get("fetch_source", "unknown"),
        "source_total_rows": fetch_meta.get("source_total_rows"),
        "source_coverage_ratio": coverage_ratio,
        "fetch_page_size": fetch_meta.get("page_size"),
        "fetch_errors": fetch_meta.get("fetch_errors", []),
        "fetch_attempts": fetch_meta.get("fetch_attempts", []),
        "minimum_required_rows": 3000,
        "minimum_valid_quote_ratio": 0.8,
        "minimum_source_coverage_ratio": 0.95,
        "total": total,
        "advancing": up,
        "declining": down,
        "advancing_ratio": adv_ratio,
        "limit_up_count": limit_up,
        "limit_down_count": limit_down,
        "total_amount": total_amount,
        "diagnostics": [
            f"上涨家数 {up}/{total}",
            f"下跌家数 {down}/{total}",
            f"涨停约 {limit_up}，跌停约 {limit_down}",
            f"全市场成交额约 {total_amount / 100000000:.0f} 亿元",
        ],
        "downgrades": downgrades,
    }


def candidate_seed(rows: list[dict[str, Any]], limit: int = 80) -> list[dict[str, Any]]:
    candidates = []
    for row in rows:
        pct = to_number(row.get("pct_chg"))
        amount = to_number(row.get("amount"))
        turnover = to_number(row.get("turnover"))
        latest = to_number(row.get("latest"))
        volume_ratio = to_number(row.get("volume_ratio"))
        if pct is None or amount is None or latest is None:
            continue
        if amount < 200_000_000:
            continue
        if pct < 1.0 or pct >= 9.8:
            continue
        if turnover is not None and turnover < 1.0:
            continue
        import math
        amount_in_million = amount / 1_000_000.0
        base_amount_score = 10.0 + math.log(amount_in_million / 20.0 + 1.0, 1.3)
        vr = volume_ratio if volume_ratio is not None else 1.0
        vr_factor = min(1.5, max(0.5, vr))
        amount_score = min(30.0, base_amount_score * vr_factor)
        pct_score = min(40, pct * 4)
        turnover_score = min(20, (turnover or 0) * 2)
        main_score = max(-10, min(10, (to_number(row.get("main_net_pct")) or 0)))
        seed_score = round(amount_score + pct_score + turnover_score + main_score, 2)
        out = dict(row)
        out["seed_score"] = seed_score
        out["seed_reason"] = "量比、涨幅、换手和资金字段的机械初筛；需再做产业链/公告/风险验证。"
        candidates.append(out)
    candidates.sort(key=lambda item: item["seed_score"], reverse=True)
    return candidates[:limit]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def snapshot(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    trade_session = classify_a_share_session()
    rows, fetch_meta = fetch_market_snapshot(
        page_size=args.page_size,
        max_pages=args.max_pages,
        source=args.source,
    )
    seeds = candidate_seed(rows, limit=args.seed_limit)
    gate = market_gate_stats(rows, fetch_meta=fetch_meta)
    gate["trade_session"] = trade_session
    gate["data_cutoff"] = trade_session["generated_at"]
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "all_a_share_snapshot.csv", rows)
    write_csv(output_dir / "candidate_seed.csv", seeds)
    (output_dir / "trade_session.json").write_text(
        json.dumps(trade_session, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "market_gate_snapshot.json").write_text(
        json.dumps(gate, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(rows)} snapshot rows and {len(seeds)} seed candidates to {output_dir}")
    return 0


def fetch_history_eastmoney(code: str, begin: str, end: str, fqt: int = 1) -> list[dict[str, Any]]:
    params = {
        "secid": secid(code),
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": 101,
        "fqt": fqt,
        "beg": begin,
        "end": end,
    }
    payload = request_json(EASTMONEY_KLINE, params)
    data = payload.get("data") or {}
    name = data.get("name", "")
    klines = data.get("klines") or []
    rows = []
    for line in klines:
        parts = line.split(",")
        if len(parts) < 11:
            continue
        rows.append(
            {
                "code": code,
                "name": name,
                "date": parts[0],
                "open": parts[1],
                "close": parts[2],
                "high": parts[3],
                "low": parts[4],
                "volume": parts[5],
                "amount": parts[6],
                "amplitude": parts[7],
                "pct_chg": parts[8],
                "chg": parts[9],
                "turnover": parts[10],
            }
        )
    return rows


def fetch_history_sina_akshare(code: str, begin: str, end: str, fqt: int = 1) -> list[dict[str, Any]]:
    try:
        import akshare as ak  # type: ignore[import-not-found]
    except Exception:
        return []
    adjust = {0: "", 1: "qfq", 2: "hfq"}.get(fqt, "qfq")
    frame = ak.stock_zh_a_daily(
        symbol=sina_symbol(code),
        start_date=begin,
        end_date=end,
        adjust=adjust,
    )
    rows = []
    for item in frame.to_dict(orient="records"):
        parsed_date = parse_yyyymmdd(item.get("date"))
        rows.append(
            {
                "code": code,
                "name": "",
                "date": parsed_date.isoformat() if parsed_date else str(item.get("date", "")),
                "open": item.get("open"),
                "close": item.get("close"),
                "high": item.get("high"),
                "low": item.get("low"),
                "volume": item.get("volume"),
                "amount": item.get("amount"),
                "amplitude": "",
                "pct_chg": "",
                "chg": "",
                "turnover": item.get("turnover"),
                "source": "akshare_sina_daily",
            }
        )
    return rows


def fetch_history(code: str, begin: str, end: str, fqt: int = 1) -> list[dict[str, Any]]:
    errors: list[str] = []
    for fetcher in (fetch_history_sina_akshare, fetch_history_eastmoney):
        try:
            rows = fetcher(code, begin, end, fqt=fqt)
        except Exception as exc:
            errors.append(f"{fetcher.__name__}: {type(exc).__name__}: {exc}")
            continue
        if rows:
            return rows
    return []


def history(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, Any]] = []
    for code in [item.strip() for item in args.codes.split(",") if item.strip()]:
        rows = fetch_history(code, args.begin, args.end, fqt=args.fqt)
        all_rows.extend(rows)
        if args.per_code:
            write_csv(output_dir / f"{code}_daily_kline.csv", rows)
        time.sleep(0.2)
    write_csv(output_dir / "daily_kline.csv", all_rows)
    print(f"Wrote {len(all_rows)} daily kline rows to {output_dir}")
    return 0


def calendar(args: argparse.Namespace) -> int:
    if args.datetime:
        now = datetime.fromisoformat(args.datetime)
        if now.tzinfo is None:
            now = now.replace(tzinfo=CN_TZ)
    elif args.date:
        time_text = args.time or "12:00:00"
        now = datetime.fromisoformat(f"{args.date}T{time_text}")
        now = now.replace(tzinfo=CN_TZ)
    else:
        now = datetime.now(CN_TZ)
    result = classify_a_share_session(now)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect public A-share data for watchpool validation.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_snapshot = sub.add_parser("snapshot", help="Collect full-market snapshot and seed candidates.")
    p_snapshot.add_argument("--output-dir", required=True)
    p_snapshot.add_argument("--page-size", type=int, default=5000)
    p_snapshot.add_argument("--max-pages", type=int, default=3)
    p_snapshot.add_argument("--seed-limit", type=int, default=80)
    p_snapshot.add_argument("--source", choices=["auto", "akshare", "eastmoney"], default="auto")
    p_snapshot.set_defaults(func=snapshot)

    p_history = sub.add_parser("history", help="Collect daily K-line history for comma-separated codes.")
    p_history.add_argument("--codes", required=True)
    p_history.add_argument("--begin", required=True, help="YYYYMMDD")
    p_history.add_argument("--end", required=True, help="YYYYMMDD")
    p_history.add_argument("--output-dir", required=True)
    p_history.add_argument("--fqt", type=int, default=1, help="Eastmoney adjustment flag, default 1.")
    p_history.add_argument("--per-code", action="store_true")
    p_history.set_defaults(func=history)

    p_calendar = sub.add_parser("calendar", help="Classify A-share trading day and current session.")
    p_calendar.add_argument("--date", help="YYYY-MM-DD, defaults to today.")
    p_calendar.add_argument("--time", help="HH:MM:SS, used with --date.")
    p_calendar.add_argument("--datetime", help="ISO datetime, optionally with timezone.")
    p_calendar.add_argument("--output", help="Optional JSON output path.")
    p_calendar.set_defaults(func=calendar)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
