#!/usr/bin/env python3
"""Check whether A-share watchpool candidates are practically observable."""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any


CSV_FIELDS = [
    "code",
    "name",
    "execution_action",
    "execution_score",
    "risk_flags",
    "latest",
    "pct_chg",
    "open_gap_pct",
    "amount_yuan",
    "amplitude_pct",
    "intraday_extension_pct",
    "near_limit_threshold",
]


def to_float(value: Any) -> float | None:
    if value in (None, "", "-"):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number


def limit_threshold(code: str) -> float:
    code = code.strip()
    if code.startswith(("8", "4")):
        return 29.0
    if code.startswith(("300", "301", "688")):
        return 19.5
    return 9.5


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def row_key(row: dict[str, Any]) -> str:
    return str(row.get("code") or row.get("代码") or row.get("证券代码") or "").strip()[-6:]


def index_snapshot(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row_key(row): row for row in rows if row_key(row)}


def select_codes(args: argparse.Namespace) -> list[str]:
    codes: list[str] = []
    if args.codes:
        codes.extend(item.strip()[-6:] for item in args.codes.split(",") if item.strip())
    if args.candidates:
        for row in read_csv(Path(args.candidates)):
            code = row_key(row)
            if code:
                codes.append(code)
    out: list[str] = []
    for code in codes:
        if code not in out:
            out.append(code)
    return out


def evaluate(code: str, row: dict[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {
            "code": code,
            "name": "",
            "execution_action": "block_from_paper_watch",
            "execution_score": 0,
            "risk_flags": "missing_snapshot_row",
            "latest": "",
            "pct_chg": "",
            "open_gap_pct": "",
            "amount_yuan": "",
            "amplitude_pct": "",
            "intraday_extension_pct": "",
            "near_limit_threshold": limit_threshold(code),
        }
    name = str(row.get("name") or row.get("名称") or "")
    latest = to_float(row.get("latest"))
    pct_chg = to_float(row.get("pct_chg"))
    amount = to_float(row.get("amount"))
    high = to_float(row.get("high"))
    low = to_float(row.get("low"))
    open_price = to_float(row.get("open"))
    prev_close = to_float(row.get("prev_close"))
    amplitude_field = to_float(row.get("amplitude"))
    limit = limit_threshold(code)
    flags: list[str] = []
    score = 100

    if latest is None or pct_chg is None or amount is None or prev_close in (None, 0):
        flags.append("missing_core_quote_fields")
        score -= 50
    open_gap = ((open_price / prev_close - 1.0) * 100.0) if open_price is not None and prev_close else None
    amplitude = amplitude_field
    if amplitude is None and high is not None and low is not None and prev_close:
        amplitude = (high - low) / prev_close * 100.0
    extension = ((latest - low) / prev_close * 100.0) if latest is not None and low is not None and prev_close else None

    if pct_chg is not None and pct_chg >= limit:
        flags.append("near_or_at_limit_up")
        score -= 45
    if all(value is not None for value in (open_price, high, low, latest)) and pct_chg is not None:
        if abs(open_price - high) < 1e-6 and abs(high - low) < 1e-6 and abs(low - latest) < 1e-6 and pct_chg >= limit:
            flags.append("one_word_limit_up")
            score = 0
    if open_gap is not None:
        if open_gap >= 8:
            flags.append("excessive_open_gap")
            score -= 25
        elif open_gap >= 5:
            flags.append("large_open_gap")
            score -= 12
    if amount is not None:
        if amount < 100_000_000:
            flags.append("insufficient_liquidity")
            score -= 35
        elif amount < 300_000_000:
            flags.append("thin_liquidity")
            score -= 15
    if amplitude is not None:
        if amplitude >= 16:
            flags.append("excessive_intraday_amplitude")
            score -= 25
        elif amplitude >= 10:
            flags.append("large_intraday_amplitude")
            score -= 10
    if extension is not None and pct_chg is not None:
        if extension >= 8 and pct_chg >= 5:
            flags.append("extended_from_intraday_low")
            score -= 15

    score = max(0, min(100, round(score, 1)))
    if "one_word_limit_up" in flags or "missing_core_quote_fields" in flags or "insufficient_liquidity" in flags:
        action = "block_from_paper_watch"
    elif score < 70 or flags:
        action = "manual_review_or_downgrade"
    else:
        action = "clear"
    return {
        "code": code,
        "name": name,
        "execution_action": action,
        "execution_score": score,
        "risk_flags": "、".join(flags),
        "latest": latest if latest is not None else "",
        "pct_chg": pct_chg if pct_chg is not None else "",
        "open_gap_pct": round(open_gap, 3) if open_gap is not None else "",
        "amount_yuan": amount if amount is not None else "",
        "amplitude_pct": round(amplitude, 3) if amplitude is not None else "",
        "intraday_extension_pct": round(extension, 3) if extension is not None else "",
        "near_limit_threshold": limit,
    }


def summarize(rows: list[dict[str, Any]], snapshot_path: str) -> dict[str, Any]:
    block_codes = [row["code"] for row in rows if row["execution_action"] == "block_from_paper_watch"]
    warning_codes = [row["code"] for row in rows if row["execution_action"] == "manual_review_or_downgrade"]
    clear_codes = [row["code"] for row in rows if row["execution_action"] == "clear"]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "snapshot": snapshot_path,
        "counts": {
            "clear": len(clear_codes),
            "warning": len(warning_codes),
            "block": len(block_codes),
        },
        "clear_codes": clear_codes,
        "warning_codes": warning_codes,
        "block_codes": block_codes,
        "promote_allowed_by_execution_check": not block_codes,
        "by_code": {row["code"]: row for row in rows},
        "rule": "block means do not promote to paper watch; warning means manual review/downgrade.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check candidate execution quality against a quote snapshot.")
    parser.add_argument("--snapshot", required=True, help="all_a_share_snapshot.csv path.")
    parser.add_argument("--codes", help="Comma-separated codes.")
    parser.add_argument("--candidates", help="Optional candidate CSV/log containing code column.")
    parser.add_argument("--output", required=True, help="JSON output path.")
    parser.add_argument("--csv-output", help="Optional CSV output.")
    args = parser.parse_args()

    snapshot_rows = read_csv(Path(args.snapshot))
    snapshot = index_snapshot(snapshot_rows)
    codes = select_codes(args)
    if not codes:
        raise SystemExit("provide --codes or --candidates")
    rows = [evaluate(code, snapshot.get(code)) for code in codes]
    result = summarize(rows, args.snapshot)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.csv_output:
        write_csv(Path(args.csv_output), rows)
    print(f"Wrote {out} with {len(rows)} execution rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
