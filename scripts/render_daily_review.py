#!/usr/bin/env python3
"""Render a same-screen review of previous candidates and current candidates."""

from __future__ import annotations

import argparse
import csv
import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


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


def fmt_pct(value: float | None) -> str:
    return "NA" if value is None else f"{value * 100:.2f}%"


def fmt_pct_colored(value: float | None) -> str:
    if value is None:
        return "NA"
    pct_val = value * 100
    if pct_val > 0:
        return f'<span class="color-up">+{pct_val:.2f}%</span>'
    elif pct_val < 0:
        return f'<span class="color-down">{pct_val:.2f}%</span>'
    else:
        return f'<span class="color-flat">0.00%</span>'


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def current_candidates_from_report(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for key, label in [
        ("tradable_candidates", "paper_watch"),
        ("premarket_inference_candidates", "premarket_inference"),
        ("research_leads", "research"),
    ]:
        for item in data.get(key) or []:
            row = dict(item)
            row["group"] = row.get("group") or label
            rows.append(row)
    return rows


def previous_table(rows: list[dict[str, Any]]) -> str:
    body = []
    for row in rows:
        ret_t1 = pct(row.get("close_t1"), row.get("entry_price"))
        ret_t2 = pct(row.get("close_t2"), row.get("entry_price"))
        ret_t3 = pct(row.get("close_t3"), row.get("entry_price"))
        body.append(
            "<tr>"
            f"<td>{esc(row.get('report_date'))}</td>"
            f"<td>{esc(row.get('code'))}</td>"
            f"<td>{esc(row.get('name'))}</td>"
            f"<td>{esc(row.get('sector'))}</td>"
            f"<td>{esc(row.get('entry_price'))}</td>"
            f"<td>{fmt_pct_colored(ret_t1)}</td>"
            f"<td>{fmt_pct_colored(ret_t2)}</td>"
            f"<td>{fmt_pct_colored(ret_t3)}</td>"
            f"<td>{esc(row.get('failure_reason') or row.get('exit_reason'))}</td>"
            "</tr>"
        )
    return "".join(body) or '<tr><td colspan="9">暂无上一批候选复盘数据</td></tr>'


def current_table(rows: list[dict[str, Any]]) -> str:
    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{esc(row.get('rank'))}</td>"
            f"<td>{esc(row.get('code'))}</td>"
            f"<td>{esc(row.get('name'))}</td>"
            f"<td>{esc(row.get('sector'))}</td>"
            f"<td>{esc(row.get('group'))}</td>"
            f"<td>{esc(row.get('score'))}</td>"
            f"<td>{esc(row.get('failure'))}</td>"
            "</tr>"
        )
    return "".join(body) or '<tr><td colspan="7">暂无当前候选</td></tr>'


def render(previous_rows: list[dict[str, Any]], current_rows: list[dict[str, Any]]) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>A股观察池前后对比</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Noto+Sans+SC:wght@400;500;700;900&display=swap');

:root {{
  --bg-deep: #060A13;
  --bg-surface: rgba(13, 21, 38, 0.9);
  --bg-card: rgba(26, 38, 59, 0.55);
  --border: rgba(148, 163, 184, 0.1);
  --border-accent: rgba(6, 182, 212, 0.3);
  --accent: #06B6D4;
  --accent-light: #22D3EE;
  --accent-glow: rgba(6, 182, 212, 0.15);
  --red: #EF4444;
  --green: #10B981;
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
    radial-gradient(ellipse 80% 50% at 50% -8%, rgba(6, 182, 212, 0.08), transparent),
    radial-gradient(ellipse 60% 40% at 85% 108%, rgba(16, 185, 129, 0.03), transparent);
  color: var(--text);
  font-family: 'Inter', 'Noto Sans SC', sans-serif;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}}

main {{
  max-width: 1180px;
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

section {{
  margin: 20px 0;
  padding: 20px;
  background: var(--bg-surface);
  backdrop-filter: blur(18px);
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: var(--shadow);
  transition: border-color 0.3s, box-shadow 0.3s;
}}
section:hover {{
  border-color: var(--border-accent);
  box-shadow: 0 13px 30px var(--accent-glow);
}}
section h2 {{
  margin-bottom: 18px;
  font-size: 18px;
  font-weight: 800;
  color: var(--accent-light);
  display: flex;
  align-items: center;
  gap: 8px;
}}
section h2::before {{
  content: "";
  display: inline-block;
  width: 3px;
  height: 16px;
  background: var(--accent);
  border-radius: 2px;
}}

table {{
  width: 100%;
  border-collapse: collapse;
}}
th, td {{
  padding: 13px 14px;
  font-size: 15px;
  text-align: left;
  vertical-align: middle;
  border-bottom: 1px solid var(--border);
}}
th {{
  background: rgba(30, 41, 59, 0.45);
  color: var(--text-bright);
  font-weight: 700;
  border-radius: 4px;
}}
tr:hover td {{
  background: rgba(30, 41, 59, 0.2);
}}

/* A-Share Red/Green coloring */
.color-up {{ color: var(--red); font-weight: 700; }}
.color-down {{ color: var(--green); font-weight: 700; }}
.color-flat {{ color: var(--dim); }}

@media(max-width:720px) {{
  body {{ padding: 16px; }}
  main {{ overflow-x: auto; }}
  th, td {{ padding: 8px; font-size: 14px; }}
}}
</style>
</head>
<body>
<main>
  <h1>A股观察池前后对比</h1>
  <p class="note">生成时间：{esc(datetime.now().isoformat(timespec="seconds"))}。仅用于策略验证，不构成投资建议。</p>
  
  <section>
    <h2>上一批候选表现 <small>Previous candidates tracking</small></h2>
    <table>
      <thead>
        <tr>
          <th>报告日</th>
          <th>代码</th>
          <th>名称</th>
          <th>板块</th>
          <th>参考价</th>
          <th>T+1收益</th>
          <th>T+2收益</th>
          <th>T+3收益</th>
          <th>失败条件/退出原因</th>
        </tr>
      </thead>
      <tbody>{previous_table(previous_rows)}</tbody>
    </table>
  </section>
  
  <section>
    <h2>当前候选 <small>Current candidates</small></h2>
    <table>
      <thead>
        <tr>
          <th>排名</th>
          <th>代码</th>
          <th>名称</th>
          <th>板块</th>
          <th>观察分组</th>
          <th>量化分</th>
          <th>失败触发条件</th>
        </tr>
      </thead>
      <tbody>{current_table(current_rows)}</tbody>
    </table>
  </section>
</main>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Render previous-vs-current watchpool review HTML.")
    parser.add_argument("--previous-log", required=True, help="Filled validation CSV.")
    parser.add_argument("--current-report", help="Current report JSON.")
    parser.add_argument("--current-log", help="Optional current validation CSV instead of report JSON.")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    previous_rows = read_csv(Path(args.previous_log))
    if args.current_log:
        current_rows = read_csv(Path(args.current_log))
    elif args.current_report:
        current_rows = current_candidates_from_report(Path(args.current_report))
    else:
        current_rows = []
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(previous_rows, current_rows), encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
