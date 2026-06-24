#!/usr/bin/env python3
"""Audit data-source health for an A-share watchpool run directory."""

from __future__ import annotations

import argparse
import csv
import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}


def count_csv(path: Path) -> int | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def status_rank(status: str) -> int:
    return {"ok": 0, "warning": 1, "failed": 2}.get(status, 1)


def audit(snapshot_dir: Path, risk_json: Path | None, execution_json: Path | None) -> dict[str, Any]:
    gate = read_json(snapshot_dir / "market_gate_snapshot.json") or {}
    trade_session = read_json(snapshot_dir / "trade_session.json") or gate.get("trade_session") or {}
    risk = read_json(risk_json) if risk_json else None
    execution = read_json(execution_json) if execution_json else None
    snapshot_rows = count_csv(snapshot_dir / "all_a_share_snapshot.csv")
    seed_rows = count_csv(snapshot_dir / "candidate_seed.csv")

    checks: list[dict[str, Any]] = []

    def add(name: str, status: str, detail: str) -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    if snapshot_rows is None:
        add("snapshot_file", "failed", "missing all_a_share_snapshot.csv")
    elif snapshot_rows >= 3000:
        add("snapshot_rows", "ok", f"{snapshot_rows} rows")
    else:
        add("snapshot_rows", "failed", f"only {snapshot_rows} rows")

    if seed_rows is None:
        add("candidate_seed", "warning", "missing candidate_seed.csv")
    elif seed_rows > 0:
        add("candidate_seed", "ok", f"{seed_rows} rows")
    else:
        add("candidate_seed", "warning", "empty candidate seed")

    data_quality = gate.get("data_quality")
    valid = gate.get("is_valid_for_trading_report")
    if data_quality == "complete" and valid:
        add("market_gate_quality", "ok", "complete and valid")
    else:
        add("market_gate_quality", "failed", f"data_quality={data_quality}, valid={valid}")

    fetch_status = gate.get("fetch_status")
    fetch_source = gate.get("fetch_source")
    if fetch_status == "complete":
        add("quote_source", "ok", f"{fetch_source} complete")
    else:
        add("quote_source", "warning", f"{fetch_source} status={fetch_status}")

    if trade_session:
        calendar_source = trade_session.get("calendar_source")
        if calendar_source == "weekday_fallback_not_holiday_adjusted":
            add("trade_calendar", "warning", "weekday fallback; holiday accuracy incomplete")
        elif trade_session.get("_read_error"):
            add("trade_calendar", "failed", str(trade_session.get("_read_error")))
        else:
            add("trade_calendar", "ok", f"session={trade_session.get('session')}")
    else:
        add("trade_calendar", "warning", "missing trade_session")

    if risk is not None:
        if risk.get("_read_error"):
            add("risk_source", "failed", str(risk.get("_read_error")))
        elif risk.get("risk_check_complete") and risk.get("promote_allowed_by_risk_check"):
            add("risk_source", "ok", "risk check complete; no block/incomplete")
        elif risk.get("incomplete_codes"):
            add("risk_source", "failed", f"incomplete_codes={risk.get('incomplete_codes')}")
        elif risk.get("block_codes"):
            add("risk_source", "failed", f"block_codes={risk.get('block_codes')}")
        else:
            add("risk_source", "warning", "risk warnings or partial result")
    else:
        add("risk_source", "warning", "risk json not supplied")

    if execution is not None:
        if execution.get("_read_error"):
            add("execution_source", "failed", str(execution.get("_read_error")))
        elif execution.get("promote_allowed_by_execution_check"):
            add("execution_source", "ok", "no execution block")
        else:
            add("execution_source", "failed", f"block_codes={execution.get('block_codes')}")
    else:
        add("execution_source", "warning", "execution json not supplied")

    worst = max(checks, key=lambda item: status_rank(item["status"]))["status"] if checks else "failed"
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "snapshot_dir": str(snapshot_dir),
        "health_status": worst,
        "can_rank_paper_watch": worst == "ok",
        "checks": checks,
        "gate_summary": {
            "data_quality": data_quality,
            "valid_quote_ratio": gate.get("valid_quote_ratio"),
            "raw_rows": gate.get("raw_rows"),
            "fetch_source": fetch_source,
            "fetch_status": fetch_status,
        },
    }


def render_html(result: dict[str, Any]) -> str:
    status_dict = {"ok": "正常", "warning": "警告", "failed": "阻断/故障"}
    can_gen_dict = {True: "是 (允许生成候选)", False: "否 (条件不足)"}
    
    health_display = status_dict.get(str(result.get("health_status")), str(result.get("health_status")))
    can_gen_display = can_gen_dict.get(result.get("can_rank_paper_watch"), str(result.get("can_rank_paper_watch")))
    
    health_class = f"status-{result.get('health_status')}"
    can_gen_class = "status-ok" if result.get("can_rank_paper_watch") else "status-failed"

    rows = "".join(
        "<tr>"
        f"<td><strong>{html.escape(str(item['name']))}</strong></td>"
        f"<td><span class=\"status status-{html.escape(str(item['status']))}\">{status_dict.get(str(item['status']), str(item['status']))}</span></td>"
        f"<td>{html.escape(str(item['detail']))}</td>"
        "</tr>"
        for item in result["checks"]
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>数据源健康审计</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Noto+Sans+SC:wght@400;500;700;900&display=swap');

:root {{
  --bg-deep: #05080c;
  --bg-surface: rgba(10, 18, 30, 0.9);
  --bg-card: rgba(22, 34, 51, 0.55);
  --border: rgba(148, 163, 184, 0.1);
  --border-accent: rgba(16, 185, 129, 0.3);
  --accent: #10B981;
  --accent-light: #34D399;
  --accent-glow: rgba(16, 185, 129, 0.15);
  --red: #EF4444;
  --green: #10B981;
  --amber: #F59E0B;
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
    radial-gradient(ellipse 80% 50% at 50% -8%, rgba(16, 185, 129, 0.08), transparent),
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

.metric {{
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 18px;
  margin: 20px 0;
}}
.metric div {{
  background: var(--bg-surface);
  border: 1px solid var(--border);
  padding: 18px;
  border-radius: 13px;
  box-shadow: var(--shadow);
  transition: border-color 0.25s, box-shadow 0.25s;
}}
.metric div:hover {{
  border-color: var(--border-accent);
  box-shadow: 0 4px 20px var(--accent-glow);
}}
.label {{
  color: var(--muted);
  font-size: 14px;
  font-weight: 700;
}}
.value {{
  font-size: 22px;
  font-weight: 900;
  margin-top: 6px;
  display: inline-block;
}}

table {{
  width: 100%;
  border-collapse: collapse;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: var(--shadow);
  overflow: hidden;
}}
th, td {{
  padding: 14px 16px;
  font-size: 15px;
  text-align: left;
  vertical-align: middle;
  border-bottom: 1px solid var(--border);
}}
th {{
  background: rgba(30, 41, 59, 0.45);
  color: var(--text-bright);
  font-weight: 700;
}}
tr:hover td {{
  background: rgba(30, 41, 59, 0.2);
}}

.status {{
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  border-radius: 6px;
  padding: 2px 13px;
  font-weight: 800;
  font-size: 14px;
  border: 1px solid var(--border);
}}
.status-ok {{
  background: rgba(16, 185, 129, 0.1);
  color: var(--green);
  border-color: rgba(16, 185, 129, 0.2);
}}
.status-warning {{
  background: rgba(245, 158, 11, 0.1);
  color: var(--amber);
  border-color: rgba(245, 158, 11, 0.2);
}}
.status-failed {{
  background: rgba(239, 68, 68, 0.1);
  color: var(--red);
  border-color: rgba(239, 68, 68, 0.2);
}}

@media(max-width:720px) {{
  body {{ padding: 16px; }}
  .metric {{ grid-template-columns: 1fr; }}
  th, td {{ padding: 13px; font-size: 14px; }}
}}
</style>
</head>
<body>
<main>
  <h1>数据源健康审计</h1>
  <p class="note">生成时间：{html.escape(str(result.get('generated_at', '')))}。仅用于策略验证，不构成投资建议。</p>
  
  <section class="metric">
    <div>
      <div class="label">健康状态</div>
      <div class="value"><span class="status {health_class}">{html.escape(health_display)}</span></div>
    </div>
    <div>
      <div class="label">可生成短线波段候选</div>
      <div class="value"><span class="status {can_gen_class}">{html.escape(can_gen_display)}</span></div>
    </div>
  </section>
  
  <table>
    <thead>
      <tr>
        <th>检查项</th>
        <th>状态</th>
        <th>说明</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</main>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit watchpool data-source health.")
    parser.add_argument("--snapshot-dir", required=True)
    parser.add_argument("--risk-json")
    parser.add_argument("--execution-json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--html-output")
    args = parser.parse_args()

    result = audit(
        Path(args.snapshot_dir),
        Path(args.risk_json) if args.risk_json else None,
        Path(args.execution_json) if args.execution_json else None,
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.html_output:
        html_out = Path(args.html_output)
        html_out.parent.mkdir(parents=True, exist_ok=True)
        html_out.write_text(render_html(result), encoding="utf-8")
    print(f"Wrote {out} health_status={result['health_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
