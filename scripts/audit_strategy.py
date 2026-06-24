#!/usr/bin/env python3
"""Audit whether the watchpool strategy has enough evidence to keep using."""

from __future__ import annotations

import argparse
import csv
import html
import json
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any


def to_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def pct(close_value: Any, entry_value: Any) -> float | None:
    close = to_float(close_value)
    entry = to_float(entry_value)
    if close is None or entry in (None, 0):
        return None
    return close / entry - 1.0


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_db_rows(path: Path) -> list[dict[str, Any]]:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in conn.execute("SELECT * FROM watchpool_log")]
    finally:
        conn.close()


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    returns = [pct(row.get("close_t3"), row.get("entry_price")) for row in rows]
    returns = [value for value in returns if value is not None]
    alphas = []
    drawdowns = []
    for row in rows:
        ret = pct(row.get("close_t3"), row.get("entry_price"))
        bench = pct(row.get("benchmark_t3"), row.get("benchmark_entry"))
        low_values = [pct(row.get(f"low_t{idx}"), row.get("entry_price")) for idx in range(1, 4)]
        low_values = [value for value in low_values if value is not None]
        if ret is not None and bench is not None:
            alphas.append(ret - bench)
        if low_values:
            drawdowns.append(min(low_values))
    wins = [value for value in returns if value > 0]
    return {
        "rows": len(rows),
        "effective_t3_samples": len(returns),
        "avg_t3_return": mean(returns) if returns else None,
        "t3_hit_rate": len(wins) / len(returns) if returns else None,
        "avg_t3_alpha": mean(alphas) if alphas else None,
        "avg_max_drawdown": mean(drawdowns) if drawdowns else None,
    }


def grouped(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(key) or "(blank)")].append(row)
    return {name: summarize(items) for name, items in sorted(buckets.items())}


def audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    overall = summarize(rows)
    n = overall["effective_t3_samples"]
    pause_flags: list[str] = []
    if n >= 10:
        last = rows[-10:]
        last_summary = summarize(last)
        if (last_summary["avg_t3_return"] or 0) < 0:
            pause_flags.append("last_10_avg_t3_negative")
    if n >= 20 and (overall["t3_hit_rate"] or 0) < 0.45:
        pause_flags.append("hit_rate_below_45pct")
    if n >= 20 and overall["avg_max_drawdown"] is not None and overall["avg_max_drawdown"] < -0.04:
        pause_flags.append("avg_drawdown_worse_than_4pct")
    if n < 20:
        verdict = "collect_more_samples"
    elif pause_flags:
        verdict = "pause_and_review"
    elif n < 60:
        verdict = "continue_validation_no_reweight"
    else:
        verdict = "enough_samples_for_weight_review"
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": verdict,
        "pause_flags": pause_flags,
        "overall": overall,
        "by_strategy_version": grouped(rows, "strategy_version"),
        "by_gate_regime": grouped(rows, "gate_regime"),
        "by_failure_reason": grouped(rows, "failure_reason"),
        "rule": "Do not recalibrate weights before 20 effective T+3 samples; prefer 60 samples for stable conclusions.",
    }


def fmt_pct(value: float | None) -> str:
    return "NA" if value is None else f"{value * 100:.2f}%"


def render_html(result: dict[str, Any]) -> str:
    overall = result["overall"]
    
    def fmt_pct_colored(val):
        if val is None:
            return "NA"
        pct_val = val * 100
        if pct_val > 0:
            return f'<span class="color-up">+{pct_val:.2f}%</span>'
        elif pct_val < 0:
            return f'<span class="color-down">{pct_val:.2f}%</span>'
        else:
            return f'<span class="color-flat">0.00%</span>'

    verdict_display = {
        "collect_more_samples": "样本收集阶段 (少于 20 样本)",
        "pause_and_review": "触发风控暂停 (请检查规则/参数)",
        "continue_validation_no_reweight": "样本持续验证阶段",
        "enough_samples_for_weight_review": "样本充足 (可调整策略权重)",
    }.get(str(result.get("verdict")), str(result.get("verdict")))

    verdict_class = {
        "collect_more_samples": "verdict-warn",
        "pause_and_review": "verdict-block",
        "continue_validation_no_reweight": "verdict-info",
        "enough_samples_for_weight_review": "verdict-ok",
    }.get(str(result.get("verdict")), "verdict-info")

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>策略审计周报</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Noto+Sans+SC:wght@400;500;700;900&display=swap');

:root {{
  --bg-deep: #080710;
  --bg-surface: rgba(13, 11, 24, 0.9);
  --bg-card: rgba(29, 22, 48, 0.55);
  --border: rgba(148, 163, 184, 0.1);
  --border-accent: rgba(139, 92, 246, 0.3);
  --accent: #8B5CF6;
  --accent-light: #A78BFA;
  --accent-glow: rgba(139, 92, 246, 0.15);
  --red: #EF4444;
  --red-bg: rgba(239, 68, 68, 0.1);
  --green: #10B981;
  --green-bg: rgba(16, 185, 129, 0.1);
  --amber: #F59E0B;
  --amber-bg: rgba(245, 158, 11, 0.1);
  --text: #CBD5E1;
  --text-bright: #F8FAFC;
  --muted: #94A3B8;
  --dim: #64748B;
  --shadow: 0 13px 40px rgba(0, 0, 0, 0.4);
}}

@keyframes fadeInUp {{
  from {{ opacity: 0; transform: translateY(18px); }}
  to   {{ opacity: 1; transform: translateY(0); }}
}}

* {{ box-sizing: border-box; margin: 0; padding: 0; }}

body {{
  margin: 0;
  padding: 28px;
  background: var(--bg-deep);
  background-image:
    radial-gradient(ellipse 80% 50% at 50% -8%, rgba(139, 92, 246, 0.08), transparent),
    radial-gradient(ellipse 60% 40% at 85% 108%, rgba(16, 185, 129, 0.03), transparent);
  color: var(--text);
  font-family: 'Inter', 'Noto Sans SC', sans-serif;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}}

main {{
  max-width: 1080px;
  margin: 0 auto;
  animation: fadeInUp 0.5s ease-out;
}}

h1 {{
  margin: 0 0 4px;
  font-size: 28px;
  font-weight: 900;
  letter-spacing: -0.02em;
  background: linear-gradient(135deg, #fff 40%, var(--accent-light));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}}
.note {{
  color: var(--muted);
  font-size: 15px;
  margin-bottom: 24px;
}}

.verdict-panel {{
  margin-top: 18px;
  margin-bottom: 18px;
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 17px;
}}
.verdict {{
  display: inline-flex; align-items: center; min-height: 32px; padding: 4px 16px;
  border-radius: 6px; font-weight: 800; font-size: 15px; border: 1px solid var(--border);
}}
.verdict-warn {{ color: var(--amber); background: var(--amber-bg); border-color: rgba(245,158,11,0.25); }}
.verdict-block {{ color: var(--red); background: var(--red-bg); border-color: rgba(239,68,68,0.25); }}
.verdict-info {{ color: var(--accent-light); background: var(--accent-glow); border-color: var(--border-accent); }}
.verdict-ok {{ color: var(--green); background: var(--green-bg); border-color: rgba(16,185,129,0.25); }}

.metrics {{
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 14px;
  margin: 20px 0;
}}
.metric {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  padding: 18px;
  border-radius: 8px;
  transition: border-color 0.25s, box-shadow 0.25s;
}}
.metric:hover {{
  border-color: var(--border-accent);
  box-shadow: 0 4px 20px var(--accent-glow);
}}
.label {{
  color: var(--muted);
  font-size: 14px;
  font-weight: 700;
}}
.value {{
  font-size: 20px;
  font-weight: 900;
  margin-top: 6px;
  color: var(--text-bright);
}}

.panel {{
  margin: 18px 0;
  padding: 20px;
  background: var(--bg-surface);
  backdrop-filter: blur(18px);
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: var(--shadow);
}}
.panel h2 {{
  margin-bottom: 14px;
  font-size: 17px;
  font-weight: 800;
  color: var(--accent-light);
}}
ul {{
  padding-left: 20px;
}}
li {{
  margin: 8px 0;
  font-size: 15px;
  color: var(--text);
}}

/* A-Share Red/Green coloring */
.color-up {{ color: var(--red); font-weight: 700; }}
.color-down {{ color: var(--green); font-weight: 700; }}
.color-flat {{ color: var(--dim); }}

@media(max-width:900px) {{
  .metrics {{ grid-template-columns: repeat(2, 1fr); }}
}}
@media(max-width:600px) {{
  body {{ padding: 16px; }}
  .metrics {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>
<main>
  <h1>观察池策略审计</h1>
  <p class="note">生成时间：{html.escape(str(result.get('generated_at', '')))}。样本不足 20 前只记录观察，不做权重重校准。</p>
  
  <div class="verdict-panel">
    <span>审计结论：</span>
    <span class="verdict {verdict_class}">{html.escape(verdict_display)}</span>
  </div>

  <section class="metrics">
    <div class="metric"><div class="label">有效 T+3 样本</div><div class="value">{overall['effective_t3_samples']}</div></div>
    <div class="metric"><div class="label">T+3 平均收益</div><div class="value">{fmt_pct_colored(overall['avg_t3_return'])}</div></div>
    <div class="metric"><div class="label">T+3 胜率</div><div class="value">{fmt_pct(overall['t3_hit_rate'])}</div></div>
    <div class="metric"><div class="label">T+3 平均超额</div><div class="value">{fmt_pct_colored(overall['avg_t3_alpha'])}</div></div>
    <div class="metric"><div class="label">平均最大回撤</div><div class="value">{fmt_pct_colored(overall['avg_max_drawdown'])}</div></div>
  </section>

  <section class="panel">
    <h2>风控触发标记</h2>
    <ul>
      <li>暂停标记列表：{html.escape('、'.join(result['pause_flags']) if result['pause_flags'] else '无')}</li>
      <li>审计基准提示：如果有效样本数超过 20 个，胜率低于 45% 或最大回撤差于 4.0%，会触发暂停标记警示。</li>
    </ul>
  </section>
</main>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit watchpool strategy evidence quality.")
    parser.add_argument("--csv")
    parser.add_argument("--db")
    parser.add_argument("--output", required=True)
    parser.add_argument("--html-output")
    args = parser.parse_args()

    if args.csv:
        rows = read_csv_rows(Path(args.csv))
    elif args.db:
        rows = read_db_rows(Path(args.db))
    else:
        raise SystemExit("provide --csv or --db")
    result = audit(rows)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.html_output:
        html_out = Path(args.html_output)
        html_out.parent.mkdir(parents=True, exist_ok=True)
        html_out.write_text(render_html(result), encoding="utf-8")
    print(f"Wrote {out} verdict={result['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
