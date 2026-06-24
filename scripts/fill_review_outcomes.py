#!/usr/bin/env python3
"""Fill T+1/T+2/T+3 outcomes in a watchpool validation CSV."""

from __future__ import annotations

import argparse
import csv
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

from benchmark_utils import DEFAULT_STRATEGY_VERSION, benchmark_map_for_report
from collect_public_data import fetch_history


OUTCOME_COLUMNS = [
    "strategy_version",
    "benchmark_code",
    "benchmark_name",
    "benchmark_match_note",
    "entry_price",
    "close_t1",
    "close_t2",
    "close_t3",
    "low_t1",
    "low_t2",
    "low_t3",
    "benchmark_entry",
    "benchmark_t1",
    "benchmark_t2",
    "benchmark_t3",
    "failure_reason",
    "failure_tags",
    "exit_reason",
    "notes",
]


def parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    text = str(value).strip()[:10]
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def yyyymmdd(value: date) -> str:
    return value.strftime("%Y%m%d")


def is_blank(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def normalize_number(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        return f"{float(value):.4f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(value)


def number(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def append_note(row: dict[str, Any], note: str) -> None:
    existing = str(row.get("notes") or "").strip()
    if note in existing:
        return
    row["notes"] = f"{existing}; {note}" if existing else note


def pct(close_value: Any, entry_value: Any) -> float | None:
    close = number(close_value)
    entry = number(entry_value)
    if close is None or entry in (None, 0):
        return None
    return close / entry - 1.0


def set_strategy_version(row: dict[str, Any], version: str) -> None:
    if is_blank(row.get("strategy_version")):
        row["strategy_version"] = version


def set_benchmark(row: dict[str, Any], explicit_code: str | None, auto: bool) -> tuple[str | None, str | None]:
    if explicit_code:
        if is_blank(row.get("benchmark_code")):
            row["benchmark_code"] = explicit_code
        if is_blank(row.get("benchmark_name")):
            row["benchmark_name"] = f"benchmark_{explicit_code}"
        return explicit_code, row.get("benchmark_name")
    if not auto and not row.get("benchmark_code"):
        return None, None
    if is_blank(row.get("benchmark_code")):
        profile = benchmark_map_for_report(row.get("sector"), row.get("name"))
        row.update(profile)
    return str(row.get("benchmark_code") or "").strip() or None, row.get("benchmark_name")


def attribute_failure(row: dict[str, Any]) -> None:
    tags: list[str] = []
    if is_blank(row.get("entry_price")):
        tags.append("missing_entry")
    if any(is_blank(row.get(f"close_t{idx}")) for idx in range(1, 4)):
        tags.append("pending_or_missing_forward_data")
    ret_t3 = pct(row.get("close_t3"), row.get("entry_price"))
    low_returns = [pct(row.get(f"low_t{idx}"), row.get("entry_price")) for idx in range(1, 4)]
    low_returns = [value for value in low_returns if value is not None]
    bench_t3 = pct(row.get("benchmark_t3"), row.get("benchmark_entry"))
    alpha_t3 = ret_t3 - bench_t3 if ret_t3 is not None and bench_t3 is not None else None
    notes = str(row.get("notes") or "")
    exit_reason = str(row.get("exit_reason") or "").strip().lower()

    if "no_entry" in exit_reason:
        tags.append("no_entry")
    if "auto_fill_no_history_rows" in notes or "auto_fill_failed" in notes:
        tags.append("data_missing")
    if "risk" in notes or "公告" in notes:
        tags.append("event_risk")
    if ret_t3 is not None:
        if ret_t3 <= -0.04:
            tags.append("price_failed")
        elif ret_t3 > 0:
            tags.append("positive_close")
    if low_returns and min(low_returns) <= -0.05:
        tags.append("drawdown_exceeded")
    if alpha_t3 is not None and alpha_t3 <= -0.02:
        tags.append("underperformed_benchmark")
    if not tags:
        tags.append("pending_review")

    priority = [
        ("no_entry", "no_entry"),
        ("data_missing", "data_missing"),
        ("missing_entry", "missing_entry"),
        ("pending_or_missing_forward_data", "pending"),
        ("event_risk", "event_risk"),
        ("drawdown_exceeded", "drawdown_failed"),
        ("underperformed_benchmark", "underperformed_benchmark"),
        ("price_failed", "price_failed"),
        ("positive_close", "completed_positive"),
    ]
    reason = "pending_review"
    for tag, label in priority:
        if tag in tags:
            reason = label
            break
    row["failure_tags"] = "、".join(dict.fromkeys(tags))
    row["failure_reason"] = reason


def load_csv(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    for column in OUTCOME_COLUMNS:
        if column not in fieldnames:
            fieldnames.append(column)
    return rows, fieldnames


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def fetch_history_cached(
    cache: dict[str, list[dict[str, Any]]],
    code: str,
    begin: date,
    end: date,
    fqt: int,
) -> list[dict[str, Any]]:
    if code not in cache:
        cache[code] = fetch_history(code, yyyymmdd(begin), yyyymmdd(end), fqt=fqt)
        time.sleep(0.2)
    return cache[code]


def rows_by_date(history_rows: list[dict[str, Any]]) -> dict[date, dict[str, Any]]:
    out: dict[date, dict[str, Any]] = {}
    for row in history_rows:
        parsed = parse_date(row.get("date"))
        if parsed is not None:
            out[parsed] = row
    return out


def next_trade_rows(history_rows: list[dict[str, Any]], report_day: date) -> list[dict[str, Any]]:
    dated = []
    for row in history_rows:
        parsed = parse_date(row.get("date"))
        if parsed is not None and parsed > report_day:
            dated.append((parsed, row))
    dated.sort(key=lambda item: item[0])
    return [row for _, row in dated[:3]]


def fill_row_outcomes(
    row: dict[str, Any],
    history_rows: list[dict[str, Any]],
    report_day: date,
    *,
    fill_entry_from_report_close: bool,
) -> int:
    changed = 0
    by_date = rows_by_date(history_rows)
    report_kline = by_date.get(report_day)
    if fill_entry_from_report_close and report_kline and is_blank(row.get("entry_price")):
        row["entry_price"] = normalize_number(report_kline.get("close"))
        changed += 1
    targets = next_trade_rows(history_rows, report_day)
    missing = []
    for idx, target in enumerate(targets, 1):
        close_col = f"close_t{idx}"
        low_col = f"low_t{idx}"
        if is_blank(row.get(close_col)):
            row[close_col] = normalize_number(target.get("close"))
            changed += 1
        if is_blank(row.get(low_col)):
            row[low_col] = normalize_number(target.get("low"))
            changed += 1
    for idx in range(1, 4):
        if is_blank(row.get(f"close_t{idx}")) or is_blank(row.get(f"low_t{idx}")):
            missing.append(f"t{idx}")
    if missing:
        append_note(row, f"auto_fill_missing={','.join(missing)}")
    elif str(row.get("exit_reason") or "").strip().lower() in ("", "pending"):
        row["exit_reason"] = "completed"
        changed += 1
    return changed


def fill_benchmark(
    row: dict[str, Any],
    benchmark_rows: list[dict[str, Any]],
    report_day: date,
) -> int:
    changed = 0
    by_date = rows_by_date(benchmark_rows)
    report_kline = by_date.get(report_day)
    if report_kline and is_blank(row.get("benchmark_entry")):
        row["benchmark_entry"] = normalize_number(report_kline.get("close"))
        changed += 1
    targets = next_trade_rows(benchmark_rows, report_day)
    for idx, target in enumerate(targets, 1):
        col = f"benchmark_t{idx}"
        if is_blank(row.get(col)):
            row[col] = normalize_number(target.get("close"))
            changed += 1
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Fill watchpool CSV outcomes from public daily K-line data.")
    parser.add_argument("--input", required=True, help="Input validation CSV.")
    parser.add_argument("--output", required=True, help="Output CSV. Use a new file; do not overwrite raw logs.")
    parser.add_argument("--as-of", default=datetime.now().strftime("%Y-%m-%d"), help="Last date to fetch, YYYY-MM-DD.")
    parser.add_argument("--benchmark-code", help="Optional benchmark code, for example 399006.")
    parser.add_argument("--auto-benchmark", action="store_true", help="Infer benchmark_code from sector/name when missing.")
    parser.add_argument("--strategy-version", default=DEFAULT_STRATEGY_VERSION)
    parser.add_argument("--fqt", type=int, default=1, help="Eastmoney adjustment flag, default 1.")
    parser.add_argument(
        "--fill-entry-from-report-close",
        action="store_true",
        help="Fill missing entry_price with report-day close. Use only for post-close paper samples.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    rows, fieldnames = load_csv(input_path)
    as_of = parse_date(args.as_of)
    if as_of is None:
        raise SystemExit(f"Invalid --as-of date: {args.as_of}")

    candidate_cache: dict[str, list[dict[str, Any]]] = {}
    benchmark_cache: dict[str, list[dict[str, Any]]] = {}
    total_changed = 0
    for row in rows:
        code = str(row.get("code") or "").strip()
        report_day = parse_date(row.get("report_date"))
        set_strategy_version(row, args.strategy_version)
        if not code or report_day is None:
            append_note(row, "auto_fill_skipped_missing_code_or_report_date")
            attribute_failure(row)
            continue
        begin = report_day
        try:
            history_rows = fetch_history_cached(candidate_cache, code, begin, as_of, args.fqt)
        except Exception as exc:
            append_note(row, f"auto_fill_failed_{type(exc).__name__}")
            continue
        if not history_rows:
            append_note(row, "auto_fill_no_history_rows")
        total_changed += fill_row_outcomes(
            row,
            history_rows,
            report_day,
            fill_entry_from_report_close=args.fill_entry_from_report_close,
        )
        benchmark_code, _benchmark_name = set_benchmark(row, args.benchmark_code, args.auto_benchmark)
        if benchmark_code:
            try:
                benchmark_rows = fetch_history_cached(benchmark_cache, benchmark_code, begin, as_of, args.fqt)
                total_changed += fill_benchmark(row, benchmark_rows, report_day)
                if not benchmark_rows:
                    append_note(row, f"benchmark_no_history_rows_{benchmark_code}")
            except Exception as exc:
                append_note(row, f"benchmark_fill_failed_{type(exc).__name__}")
        append_note(row, f"auto_filled_as_of={as_of.isoformat()}")
        attribute_failure(row)

    output_path = Path(args.output)
    write_csv(output_path, rows, fieldnames)
    print(f"Wrote {output_path} with {len(rows)} rows; changed {total_changed} fields")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
