#!/usr/bin/env python3
"""SQLite review database and HTML dashboard for watchpool validation logs."""

from __future__ import annotations

import argparse
import csv
import html
import sqlite3
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any


LOG_COLUMNS = [
    "strategy_version",
    "report_date",
    "checkpoint",
    "group_name",
    "rank",
    "code",
    "name",
    "sector",
    "score",
    "gate_regime",
    "gate_score",
    "entry_price",
    "close_t1",
    "close_t2",
    "close_t3",
    "low_t1",
    "low_t2",
    "low_t3",
    "benchmark_code",
    "benchmark_name",
    "benchmark_entry",
    "benchmark_t1",
    "benchmark_t2",
    "benchmark_t3",
    "failure_reason",
    "failure_tags",
    "exit_reason",
    "notes",
    "source_file",
    "imported_at",
]

HORIZONS = ("t1", "t2", "t3")


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS watchpool_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_version TEXT,
            report_date TEXT,
            checkpoint TEXT,
            group_name TEXT,
            rank INTEGER,
            code TEXT,
            name TEXT,
            sector TEXT,
            score REAL,
            gate_regime TEXT,
            gate_score REAL,
            entry_price REAL,
            close_t1 REAL,
            close_t2 REAL,
            close_t3 REAL,
            low_t1 REAL,
            low_t2 REAL,
            low_t3 REAL,
            benchmark_code TEXT,
            benchmark_name TEXT,
            benchmark_entry REAL,
            benchmark_t1 REAL,
            benchmark_t2 REAL,
            benchmark_t3 REAL,
            failure_reason TEXT,
            failure_tags TEXT,
            exit_reason TEXT,
            notes TEXT,
            source_file TEXT,
            imported_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_watchpool_log_key
        ON watchpool_log(report_date, checkpoint, code, group_name)
        """
    )
    ensure_columns(conn)
    conn.commit()


def ensure_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(watchpool_log)")}
    wanted = {
        "strategy_version": "TEXT",
        "benchmark_code": "TEXT",
        "benchmark_name": "TEXT",
        "failure_reason": "TEXT",
        "failure_tags": "TEXT",
    }
    for column, column_type in wanted.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE watchpool_log ADD COLUMN {column} {column_type}")


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


def to_int(value: Any) -> int | None:
    number = to_float(value)
    return int(number) if number is not None else None


def import_log(conn: sqlite3.Connection, csv_path: Path) -> int:
    init_db(conn)
    imported_at = datetime.now().isoformat(timespec="seconds")
    count = 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            values = {
                "strategy_version": row.get("strategy_version"),
                "report_date": row.get("report_date"),
                "checkpoint": row.get("checkpoint"),
                "group_name": row.get("group") or row.get("group_name"),
                "rank": to_int(row.get("rank")),
                "code": row.get("code"),
                "name": row.get("name"),
                "sector": row.get("sector"),
                "score": to_float(row.get("score")),
                "gate_regime": row.get("gate_regime"),
                "gate_score": to_float(row.get("gate_score")),
                "entry_price": to_float(row.get("entry_price")),
                "close_t1": to_float(row.get("close_t1")),
                "close_t2": to_float(row.get("close_t2")),
                "close_t3": to_float(row.get("close_t3")),
                "low_t1": to_float(row.get("low_t1")),
                "low_t2": to_float(row.get("low_t2")),
                "low_t3": to_float(row.get("low_t3")),
                "benchmark_code": row.get("benchmark_code"),
                "benchmark_name": row.get("benchmark_name"),
                "benchmark_entry": to_float(row.get("benchmark_entry")),
                "benchmark_t1": to_float(row.get("benchmark_t1")),
                "benchmark_t2": to_float(row.get("benchmark_t2")),
                "benchmark_t3": to_float(row.get("benchmark_t3")),
                "failure_reason": row.get("failure_reason"),
                "failure_tags": row.get("failure_tags"),
                "exit_reason": row.get("exit_reason"),
                "notes": row.get("notes"),
                "source_file": str(csv_path),
                "imported_at": imported_at,
            }
            conn.execute(
                """
                DELETE FROM watchpool_log
                WHERE COALESCE(strategy_version, '') = COALESCE(?, '')
                  AND COALESCE(report_date, '') = COALESCE(?, '')
                  AND COALESCE(checkpoint, '') = COALESCE(?, '')
                  AND COALESCE(group_name, '') = COALESCE(?, '')
                  AND COALESCE(rank, -1) = COALESCE(?, -1)
                  AND COALESCE(code, '') = COALESCE(?, '')
                """,
                [
                    values["strategy_version"],
                    values["report_date"],
                    values["checkpoint"],
                    values["group_name"],
                    values["rank"],
                    values["code"],
                ],
            )
            placeholders = ",".join("?" for _ in LOG_COLUMNS)
            conn.execute(
                f"INSERT INTO watchpool_log ({','.join(LOG_COLUMNS)}) VALUES ({placeholders})",
                [values[column] for column in LOG_COLUMNS],
            )
            count += 1
    conn.commit()
    return count


def pct(close_value: float | None, entry_value: float | None) -> float | None:
    if close_value is None or entry_value in (None, 0):
        return None
    return close_value / entry_value - 1.0


def load_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    init_db(conn)
    rows = []
    for item in conn.execute("SELECT * FROM watchpool_log ORDER BY report_date, rank, code"):
        row = dict(item)
        for horizon in HORIZONS:
            row[f"return_{horizon}"] = pct(row.get(f"close_{horizon}"), row.get("entry_price"))
            row[f"drawdown_{horizon}"] = pct(row.get(f"low_{horizon}"), row.get("entry_price"))
            bench_ret = pct(row.get(f"benchmark_{horizon}"), row.get("benchmark_entry"))
            row[f"alpha_{horizon}"] = (
                row[f"return_{horizon}"] - bench_ret
                if row[f"return_{horizon}"] is not None and bench_ret is not None
                else None
            )
        rows.append(row)
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"count": len(rows), "horizons": {}}
    for horizon in HORIZONS:
        returns = [r[f"return_{horizon}"] for r in rows if r[f"return_{horizon}"] is not None]
        alphas = [r[f"alpha_{horizon}"] for r in rows if r[f"alpha_{horizon}"] is not None]
        drawdowns = [r[f"drawdown_{horizon}"] for r in rows if r[f"drawdown_{horizon}"] is not None]
        wins = [value for value in returns if value > 0]
        losses = [value for value in returns if value < 0]
        out["horizons"][horizon] = {
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
    return out


def group_by(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        value = str(row.get(key) or "(blank)")
        groups.setdefault(value, []).append(row)
    return {name: summarize(items) for name, items in sorted(groups.items())}


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


def summary_table(title: str, summary: dict[str, Any]) -> str:
    rows = []
    for horizon in HORIZONS:
        item = summary["horizons"][horizon]
        wlr = f"{item['win_loss_ratio']:.2f}" if item['win_loss_ratio'] is not None else "NA"
        rows.append(
            "<tr>"
            f"<td>{html.escape(horizon.upper())}</td>"
            f"<td>{item['n']}</td>"
            f"<td>{fmt_pct_colored(item['avg_return'])}</td>"
            f"<td>{fmt_pct(item['hit_rate'])}</td>"
            f"<td>{fmt_pct_colored(item['avg_alpha'])}</td>"
            f"<td>{fmt_pct_colored(item['avg_drawdown'])}</td>"
            f"<td>{wlr}</td>"
            "</tr>"
        )
    return (
        f"<section class=\"panel\"><h2>{html.escape(title)} <small>n={summary['count']}</small></h2>"
        "<table><thead><tr><th>周期</th><th>样本</th><th>平均收益</th><th>胜率</th>"
        "<th>平均超额</th><th>平均回撤</th><th>盈亏比</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></section>"
    )


def dashboard_html(rows: list[dict[str, Any]]) -> str:
    overall = summarize(rows)
    sections = [summary_table("总体", overall)]
    for field, label in [
        ("strategy_version", "按策略版本"),
        ("group_name", "按候选分组"),
        ("gate_regime", "按市场门槛"),
        ("sector", "按板块"),
        ("failure_reason", "按失败归因"),
    ]:
        sections.append(f"<section class=\"group-section\"><h2>{label}</h2></section>")
        for key, summary in group_by(rows, field).items():
            sections.append(summary_table(f"{label}: {key}", summary))
    latest_rows = rows[-20:]
    latest_html = "".join(
        "<tr>"
        f"<td>{html.escape(str(row.get('report_date') or ''))}</td>"
        f"<td>{html.escape(str(row.get('group_name') or ''))}</td>"
        f"<td>{html.escape(str(row.get('code') or ''))}</td>"
        f"<td>{html.escape(str(row.get('name') or ''))}</td>"
        f"<td>{html.escape(str(row.get('sector') or ''))}</td>"
        f"<td>{fmt_pct_colored(row.get('return_t3'))}</td>"
        f"<td>{html.escape(str(row.get('failure_reason') or row.get('exit_reason') or ''))}</td>"
        "</tr>"
        for row in latest_rows
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>A股观察池复盘仪表盘</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Noto+Sans+SC:wght@400;500;700;900&display=swap');

:root {{
  --bg-deep: #060913;
  --bg-surface: rgba(13, 20, 37, 0.9);
  --bg-card: rgba(26, 36, 58, 0.55);
  --bg-card-hover: rgba(36, 48, 77, 0.8);
  --border: rgba(148, 163, 184, 0.1);
  --border-accent: rgba(217, 119, 6, 0.3);
  --accent: #D97706;
  --accent-light: #FBBF24;
  --accent-glow: rgba(217, 119, 6, 0.15);
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
    radial-gradient(ellipse 80% 50% at 50% -8%, rgba(217, 119, 6, 0.08), transparent),
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
  font-weight: 500;
}}

.group-section {{
  margin-top: 32px;
  margin-bottom: 14px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 6px;
  animation: fadeInUp 0.4s ease-out both;
}}
.group-section h2 {{
  font-size: 18px;
  font-weight: 800;
  color: var(--accent-light);
  display: flex;
  align-items: center;
  gap: 8px;
}}
.group-section h2::before {{
  content: "";
  display: inline-block;
  width: 3px;
  height: 16px;
  background: var(--accent);
  border-radius: 2px;
}}

.panel {{
  margin: 18px 0;
  padding: 20px;
  background: var(--bg-surface);
  backdrop-filter: blur(18px);
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: var(--shadow);
  transition: border-color 0.3s, box-shadow 0.3s;
}}
.panel:hover {{
  border-color: var(--border-accent);
  box-shadow: 0 13px 30px var(--accent-glow);
}}
.panel h2 {{
  margin: 0 0 18px;
  font-size: 17px;
  font-weight: 800;
  color: var(--text-bright);
}}
.panel h2 small {{
  color: var(--dim);
  font-weight: 500;
  margin-left: 6px;
  font-size: 14px;
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
  <h1>A股观察池复盘仪表盘</h1>
  <p class="note">生成时间：{html.escape(datetime.now().isoformat(timespec="seconds"))}。仅用于策略验证，不构成投资建议。</p>
  
  {''.join(sections)}
  
  <section class="panel">
    <h2>最近20条记录 <small>Latest logs</small></h2>
    <table>
      <thead>
        <tr>
          <th>日期</th>
          <th>分组</th>
          <th>代码</th>
          <th>名称</th>
          <th>板块</th>
          <th>T+3收益</th>
          <th>失败归因/退出说明</th>
        </tr>
      </thead>
      <tbody>
        {latest_html}
      </tbody>
    </table>
  </section>
</main>
</body>
</html>"""


def cmd_init(args: argparse.Namespace) -> int:
    with connect(Path(args.db)) as conn:
        init_db(conn)
    print(f"Initialized {args.db}")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    with connect(Path(args.db)) as conn:
        count = import_log(conn, Path(args.csv))
    print(f"Imported {count} rows into {args.db}")
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    with connect(Path(args.db)) as conn:
        rows = load_rows(conn)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dashboard_html(rows), encoding="utf-8")
    print(f"Wrote {output}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage watchpool review SQLite database.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create database schema.")
    p_init.add_argument("--db", required=True)
    p_init.set_defaults(func=cmd_init)

    p_import = sub.add_parser("import-log", help="Import CSV validation log.")
    p_import.add_argument("--db", required=True)
    p_import.add_argument("--csv", required=True)
    p_import.set_defaults(func=cmd_import)

    p_dash = sub.add_parser("dashboard", help="Render HTML dashboard.")
    p_dash.add_argument("--db", required=True)
    p_dash.add_argument("--output", required=True)
    p_dash.set_defaults(func=cmd_dashboard)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
