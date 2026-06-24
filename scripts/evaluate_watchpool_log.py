#!/usr/bin/env python3
"""Evaluate 1/2/3-day outcomes for A-share watchpool CSV logs."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


HORIZONS = ("t1", "t2", "t3")


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def pct(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator - 1.0


def row_metrics(row: dict[str, str]) -> dict[str, Any]:
    entry = to_float(row.get("entry_price"))
    bench_entry = to_float(row.get("benchmark_entry"))
    out: dict[str, Any] = {"row": row}
    for horizon in HORIZONS:
        close_ret = pct(to_float(row.get(f"close_{horizon}")), entry)
        low_ret = pct(to_float(row.get(f"low_{horizon}")), entry)
        bench_ret = pct(to_float(row.get(f"benchmark_{horizon}")), bench_entry)
        out[f"return_{horizon}"] = close_ret
        out[f"drawdown_{horizon}"] = low_ret
        out[f"benchmark_{horizon}"] = bench_ret
        out[f"alpha_{horizon}"] = (
            close_ret - bench_ret
            if close_ret is not None and bench_ret is not None
            else None
        )
    return out


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {"count": len(rows), "horizons": {}}
    for horizon in HORIZONS:
        returns = [r[f"return_{horizon}"] for r in rows if r[f"return_{horizon}"] is not None]
        alphas = [r[f"alpha_{horizon}"] for r in rows if r[f"alpha_{horizon}"] is not None]
        drawdowns = [r[f"drawdown_{horizon}"] for r in rows if r[f"drawdown_{horizon}"] is not None]
        wins = [value for value in returns if value > 0]
        losses = [value for value in returns if value < 0]
        summary["horizons"][horizon] = {
            "n": len(returns),
            "avg_return": mean(returns) if returns else None,
            "hit_rate": len(wins) / len(returns) if returns else None,
            "avg_alpha": mean(alphas) if alphas else None,
            "avg_drawdown": mean(drawdowns) if drawdowns else None,
            "win_loss_ratio": (
                abs(mean(wins) / mean(losses))
                if wins and losses and mean(losses) != 0
                else None
            ),
        }
    return summary


def group_summaries(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = row["row"].get(field) or "(blank)"
        grouped[key].append(row)
    return {key: summarize(value) for key, value in sorted(grouped.items())}


def fmt_pct(value: float | None) -> str:
    if value is None:
        return "NA"
    return f"{value * 100:.2f}%"


def print_summary(title: str, summary: dict[str, Any]) -> None:
    print(f"\n{title} (n={summary['count']})")
    for horizon in HORIZONS:
        item = summary["horizons"][horizon]
        print(
            f"  {horizon.upper()}: n={item['n']} "
            f"avg={fmt_pct(item['avg_return'])} "
            f"hit={fmt_pct(item['hit_rate'])} "
            f"alpha={fmt_pct(item['avg_alpha'])} "
            f"dd={fmt_pct(item['avg_drawdown'])} "
            f"wl={item['win_loss_ratio'] if item['win_loss_ratio'] is not None else 'NA'}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate watchpool CSV forward returns.")
    parser.add_argument("--input", required=True, help="CSV log path.")
    parser.add_argument("--json-output", help="Optional JSON output path.")
    parser.add_argument(
        "--group-by",
        default="group,gate_regime,sector",
        help="Comma-separated row fields for grouped summaries.",
    )
    args = parser.parse_args()

    path = Path(args.input)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [row_metrics(row) for row in reader]

    result: dict[str, Any] = {"overall": summarize(rows), "groups": {}}
    for field in [item.strip() for item in args.group_by.split(",") if item.strip()]:
        result["groups"][field] = group_summaries(rows, field)

    print_summary("Overall", result["overall"])
    for field, grouped in result["groups"].items():
        print(f"\nBy {field}")
        for key, summary in grouped.items():
            print_summary(f"{field}={key}", summary)

    if args.json_output:
        output = Path(args.json_output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nWrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
