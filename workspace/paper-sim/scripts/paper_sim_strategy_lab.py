#!/usr/bin/env python3
"""Shadow strategy lab for the A-share paper simulator.

This script is deliberately separate from paper_sim_portfolio.py. It reads the
same local watchpool data, but writes its own state under paper-sim/lab so the
locked one-month main experiment is not contaminated by rule iteration.
"""

from __future__ import annotations

import argparse
import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from paper_sim_portfolio import (
    DISCLAIMER,
    INITIAL_CASH,
    as_float,
    date_in_window,
    latest_run_dir,
    load_candidates,
    load_config,
    money,
    pct,
    portfolio_equity,
    position_value,
    read_json,
    read_jsonl,
    today_yyyymmdd,
    write_json,
)


PROJECT_ROOT_DEFAULT = Path(r"D:\CodexData\a-share-watchpool")
SIM_ROOT_DEFAULT = PROJECT_ROOT_DEFAULT / "paper-sim"
DEFAULT_STRATEGY = "lab_v1_quality_defensive"


def append_jsonl(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(data, ensure_ascii=False) + "\n")


def lab_root(sim_root: Path, strategy: str) -> Path:
    return sim_root / "lab" / strategy


def load_lab_state(root: Path) -> dict[str, Any]:
    path = root / "data" / "state.json"
    if path.exists():
        return read_json(path, {}) or {}
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "strategy": root.name,
        "initial_cash": INITIAL_CASH,
        "cash": INITIAL_CASH,
        "positions": {},
        "realized_pnl": 0.0,
        "last_decision_date": None,
    }


def save_lab_state(root: Path, state: dict[str, Any]) -> None:
    write_json(root / "data" / "state.json", state)


def lab_policy(gate_score: float, gate_regime: str | None, candidate_count: int) -> dict[str, Any]:
    regime = gate_regime or "未评级"
    if gate_score < 45:
        return {
            "target_exposure": 0.0,
            "target_positions": 0,
            "stop_loss_pct": -3.0,
            "take_profit_pct": 6.0,
            "max_hold_decisions": 1,
            "reason": f"lab_v1: 市场门槛 {gate_score:.1f} / {regime}，保持空仓。",
        }
    if gate_score < 60:
        return {
            "target_exposure": 0.30,
            "target_positions": min(2, candidate_count),
            "stop_loss_pct": -3.5,
            "take_profit_pct": 7.0,
            "max_hold_decisions": 2,
            "reason": f"lab_v1: 市场门槛 {gate_score:.1f} / {regime}，低仓位验证。",
        }
    if gate_score < 75:
        return {
            "target_exposure": 0.50,
            "target_positions": min(3, candidate_count),
            "stop_loss_pct": -4.5,
            "take_profit_pct": 8.0,
            "max_hold_decisions": 3,
            "reason": f"lab_v1: 市场门槛 {gate_score:.1f} / {regime}，质量优先中等仓位。",
        }
    return {
        "target_exposure": 0.75,
        "target_positions": min(4, candidate_count),
        "stop_loss_pct": -5.0,
        "take_profit_pct": 10.0,
        "max_hold_decisions": 4,
        "reason": f"lab_v1: 市场门槛 {gate_score:.1f} / {regime}，提高仓位但控制持仓数。",
    }


def lab_buy_score(candidate: Any) -> float:
    score = candidate.seed_score
    if candidate.execution_action != "clear":
        score -= 20
    if candidate.amount >= 1_000_000_000:
        score += 4
    elif candidate.amount >= 500_000_000:
        score += 2
    else:
        score -= 6
    if candidate.pct_chg >= 8:
        score -= 8
    elif candidate.pct_chg >= 6:
        score -= 4
    elif candidate.pct_chg < 0:
        score -= 3
    if "near_or_at_limit_up" in candidate.execution_flags:
        score -= 15
    if "large_open_gap" in candidate.execution_flags:
        score -= 6
    return score


def run_shadow(project_root: Path, sim_root: Path, strategy: str, date: str, stage: str | None) -> dict[str, Any]:
    config = load_config(sim_root)
    root = lab_root(sim_root, strategy)
    data_dir = root / "data"
    reports_dir = root / "reports"
    state = load_lab_state(root)
    state.setdefault("positions", {})
    state.setdefault("cash", INITIAL_CASH)
    state.setdefault("realized_pnl", 0.0)

    if not date_in_window(date, config):
        summary = {"status": "blocked", "reason": "date outside experiment window", "date": date}
        write_json(data_dir / f"{date}_run_summary.json", summary)
        return summary
    if state.get("last_decision_date") == date:
        return {"status": "skipped", "reason": "today already decided", "date": date, "strategy": strategy}

    run_dir = latest_run_dir(project_root, date, stage)
    if run_dir is None:
        summary = {"status": "blocked", "reason": "no candidate run dir", "date": date, "strategy": strategy}
        write_json(data_dir / f"{date}_run_summary.json", summary)
        return summary

    health = read_json(run_dir / "data_health.json", {}) or {}
    gate = read_json(run_dir / "market_gate_snapshot.json", {}) or {}
    session = read_json(run_dir / "trade_session.json", {}) or gate.get("trade_session") or {}
    execution = read_json(run_dir / "execution_quality.json", {}) or {}
    risk = read_json(run_dir / "risk_events.json", {}) or {}
    candidates = load_candidates(run_dir)
    price_by_code = {item.code: item.price for item in candidates}
    gate_score = as_float(gate.get("score"))
    policy = lab_policy(gate_score, gate.get("regime"), len(candidates))

    warnings: list[str] = []
    if not session.get("is_trade_day", True):
        warnings.append("非交易日，不做模拟交易。")
    if health.get("health_status") != "ok":
        warnings.append(f"data_health={health.get('health_status')}，不新开仓。")
    if not risk.get("promote_allowed_by_risk_check", False):
        warnings.append("risk_events 未允许升级，不新开仓。")
    if not execution.get("promote_allowed_by_execution_check", False):
        warnings.append("execution_quality 未允许升级，不新开仓。")
    if policy["target_exposure"] <= 0:
        warnings.append(policy["reason"])

    orders: list[dict[str, Any]] = []
    positions = state["positions"]
    allow_buy = not warnings and policy["target_exposure"] > 0 and bool(candidates)

    top_codes = {item.code for item in sorted(candidates, key=lab_buy_score, reverse=True)[:8]}
    for code in list(positions.keys()):
        pos = positions[code]
        mark = price_by_code.get(code, as_float(pos.get("last_price")))
        entry = as_float(pos.get("avg_price"))
        ret_pct = (mark / entry - 1.0) * 100.0 if entry else 0.0
        pos["last_price"] = mark
        pos["last_mark_date"] = date
        pos["hold_decisions"] = int(pos.get("hold_decisions") or 0) + 1
        exit_reason = None
        if ret_pct <= policy["stop_loss_pct"]:
            exit_reason = f"lab_stop_loss {pct(ret_pct)}"
        elif ret_pct >= policy["take_profit_pct"]:
            exit_reason = f"lab_take_profit {pct(ret_pct)}"
        elif int(pos.get("hold_decisions") or 0) >= policy["max_hold_decisions"]:
            exit_reason = f"lab_max_hold_decisions {policy['max_hold_decisions']}"
        elif allow_buy and code not in top_codes:
            exit_reason = "lab_dropped_out_of_top8"
        if exit_reason:
            shares = int(pos.get("shares") or 0)
            proceeds = shares * mark
            pnl = proceeds - shares * entry
            state["cash"] = as_float(state.get("cash")) + proceeds
            state["realized_pnl"] = as_float(state.get("realized_pnl")) + pnl
            orders.append({
                "date": date,
                "time": datetime.now().isoformat(timespec="seconds"),
                "action": "SELL",
                "code": code,
                "name": pos.get("name"),
                "price": mark,
                "shares": shares,
                "amount": proceeds,
                "reason": exit_reason,
                "paper_only": True,
                "shadow_only": True,
            })
            del positions[code]

    if allow_buy:
        equity = portfolio_equity(state, price_by_code)
        current_value = sum(
            position_value(pos, price_by_code.get(code, as_float(pos.get("last_price"))))
            for code, pos in positions.items()
        )
        target_value = equity * policy["target_exposure"]
        slots = max(0, int(policy["target_positions"]) - len(positions))
        per_position = min((max(0.0, target_value - current_value) / slots) if slots else 0.0, as_float(state.get("cash")))
        for candidate in sorted(candidates, key=lab_buy_score, reverse=True):
            if len(positions) >= int(policy["target_positions"]):
                break
            if candidate.code in positions or candidate.execution_action != "clear":
                continue
            cash = as_float(state.get("cash"))
            amount = min(per_position, cash)
            shares = int(amount // candidate.price // 100) * 100
            if shares <= 0:
                continue
            cost = shares * candidate.price
            state["cash"] = cash - cost
            positions[candidate.code] = {
                "code": candidate.code,
                "name": candidate.name,
                "shares": shares,
                "avg_price": candidate.price,
                "last_price": candidate.price,
                "entry_date": date,
                "last_mark_date": date,
                "hold_decisions": 0,
                "source_run_dir": str(run_dir),
                "seed_rank": candidate.seed_rank,
                "seed_score": candidate.seed_score,
                "lab_buy_score": lab_buy_score(candidate),
            }
            orders.append({
                "date": date,
                "time": datetime.now().isoformat(timespec="seconds"),
                "action": "BUY",
                "code": candidate.code,
                "name": candidate.name,
                "price": candidate.price,
                "shares": shares,
                "amount": cost,
                "reason": f"lab_v1 gate {gate_score:.1f}, score {lab_buy_score(candidate):.2f}",
                "policy": policy,
                "paper_only": True,
                "shadow_only": True,
            })

    equity = portfolio_equity(state, price_by_code)
    previous_curve = read_jsonl(data_dir / "equity_curve.jsonl")
    previous_equity = as_float(previous_curve[-1].get("equity"), INITIAL_CASH) if previous_curve else INITIAL_CASH
    daily_pnl = equity - previous_equity
    daily_return_pct = (daily_pnl / previous_equity * 100.0) if previous_equity else 0.0
    state["last_decision_date"] = date
    state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    state["last_run_dir"] = str(run_dir)
    state["last_equity"] = equity

    snapshot = {
        "status": "ok",
        "strategy": strategy,
        "date": date,
        "generated_at": state["updated_at"],
        "run_dir": str(run_dir),
        "gate_score": gate_score,
        "gate_regime": gate.get("regime"),
        "cash": as_float(state.get("cash")),
        "equity": equity,
        "realized_pnl": as_float(state.get("realized_pnl")),
        "previous_equity": previous_equity,
        "daily_pnl": daily_pnl,
        "daily_return_pct": daily_return_pct,
        "positions": list(positions.values()),
        "orders": orders,
        "warnings": warnings,
        "policy": policy,
        "paper_only": True,
        "shadow_only": True,
        "experiment": config,
        "disclaimer": DISCLAIMER,
    }
    save_lab_state(root, state)
    write_json(data_dir / f"{date}_decision.json", snapshot)
    write_json(data_dir / f"{date}_run_summary.json", {
        "status": "ok",
        "strategy": strategy,
        "date": date,
        "decision": str(data_dir / f"{date}_decision.json"),
        "html": str(reports_dir / f"{date}_paper_portfolio.html"),
        "cash": snapshot["cash"],
        "equity": snapshot["equity"],
        "daily_pnl": daily_pnl,
        "daily_return_pct": daily_return_pct,
        "orders": orders,
        "warnings": warnings,
        "positions": [p["code"] for p in snapshot["positions"]],
        "policy": policy,
        "paper_only": True,
        "shadow_only": True,
    })
    for order in orders:
        append_jsonl(data_dir / "orders.jsonl", order)
    append_jsonl(data_dir / "equity_curve.jsonl", snapshot)
    render_html(snapshot, reports_dir / f"{date}_paper_portfolio.html")
    return snapshot


def render_html(snapshot: dict[str, Any], output: Path) -> None:
    positions = snapshot.get("positions") or []
    orders = snapshot.get("orders") or []
    warnings = snapshot.get("warnings") or []
    pos_rows = "\n".join(
        f"<tr><td>{html.escape(p.get('code',''))}</td><td>{html.escape(p.get('name',''))}</td>"
        f"<td>{int(p.get('shares') or 0)}</td><td>{money(as_float(p.get('avg_price')))}</td>"
        f"<td>{money(as_float(p.get('last_price')))}</td><td>{money(as_float(p.get('lab_buy_score')))}</td></tr>"
        for p in positions
    ) or '<tr><td colspan="6">暂无持仓</td></tr>'
    order_rows = "\n".join(
        f"<tr><td>{html.escape(o.get('action',''))}</td><td>{html.escape(o.get('code',''))}</td>"
        f"<td>{html.escape(o.get('name',''))}</td><td>{int(o.get('shares') or 0)}</td>"
        f"<td>{money(as_float(o.get('price')))}</td><td>{html.escape(o.get('reason',''))}</td></tr>"
        for o in orders
    ) or '<tr><td colspan="6">今日无 shadow 交易</td></tr>'
    warning_html = "".join(f"<li>{html.escape(item)}</li>" for item in warnings) or "<li>无</li>"
    content = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>模拟盘 Shadow 策略</title>
<style>
:root {{ --bg:#070b12; --panel:#101827; --panel2:#0d1422; --line:#243247; --text:#eef3ff; --muted:#93a4bc; --gold:#f5c15d; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:radial-gradient(circle at 20% 0%,#17233a 0,#070b12 34%,#05070d 100%); color:var(--text); font-family:"Microsoft YaHei",Arial,sans-serif; }}
.page {{ width:min(1080px,calc(100vw - 32px)); margin:24px auto; padding:26px; background:linear-gradient(180deg,rgba(16,24,39,.98),rgba(8,13,23,.98)); border:1px solid var(--line); box-shadow:0 24px 80px rgba(0,0,0,.38); }}
.header {{ background:#0b1321; color:var(--text); padding:18px 22px; border:1px solid var(--line); display:flex; justify-content:space-between; gap:20px; }}
.metrics {{ display:grid; grid-template-columns:repeat(5,1fr); gap:10px; margin:14px 0; }}
.metric {{ background:var(--panel2); border:1px solid var(--line); padding:12px; }}
.label {{ color:var(--muted); font-size:12px; }} .value {{ font-size:22px; font-weight:900; color:var(--gold); }}
.box {{ border:1px solid var(--line); background:var(--panel2); padding:14px; margin:14px 0; }}
table {{ width:100%; border-collapse:collapse; }} th,td {{ border-bottom:1px solid var(--line); padding:9px; text-align:left; font-size:14px; }} th {{ background:#162238; color:#c9d7ee; }}
.footer {{ color:var(--muted); font-size:12px; margin-top:18px; }}
@media (max-width:860px) {{ .metrics {{ grid-template-columns:1fr; }} .header {{ display:block; }} .page {{ overflow-x:auto; }} }}
</style>
</head>
<body><main class="page">
<header class="header"><div><h1>模拟盘 Shadow 策略</h1><div>{html.escape(snapshot.get('strategy',''))}</div></div><div>{html.escape(snapshot.get('date',''))}<br>{html.escape(snapshot.get('generated_at',''))}</div></header>
<section class="metrics">
<div class="metric"><div class="label">现金</div><div class="value">{money(as_float(snapshot.get('cash')))}</div></div>
<div class="metric"><div class="label">总权益</div><div class="value">{money(as_float(snapshot.get('equity')))}</div></div>
<div class="metric"><div class="label">今日收益</div><div class="value">{money(as_float(snapshot.get('daily_pnl')))}</div></div>
<div class="metric"><div class="label">收益率</div><div class="value">{pct(as_float(snapshot.get('daily_return_pct')))}</div></div>
<div class="metric"><div class="label">市场门槛</div><div class="value">{snapshot.get('gate_score')}</div></div>
</section>
<section class="box"><h2>策略约束</h2><ul>{warning_html}</ul><p>{html.escape((snapshot.get('policy') or {}).get('reason',''))}</p></section>
<section class="box"><h2>Shadow 持仓</h2><table><thead><tr><th>代码</th><th>名称</th><th>股数</th><th>成本</th><th>现价</th><th>Lab评分</th></tr></thead><tbody>{pos_rows}</tbody></table></section>
<section class="box"><h2>Shadow 交易</h2><table><thead><tr><th>动作</th><th>代码</th><th>名称</th><th>股数</th><th>价格</th><th>原因</th></tr></thead><tbody>{order_rows}</tbody></table></section>
<footer class="footer">Shadow-only，不修改正式模拟盘。{html.escape(DISCLAIMER)}</footer>
</main></body></html>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")


def command_summary(args: argparse.Namespace) -> int:
    root = lab_root(Path(args.sim_root), args.strategy)
    config = load_config(Path(args.sim_root))
    curves = read_jsonl(root / "data" / "equity_curve.jsonl")
    orders = read_jsonl(root / "data" / "orders.jsonl")
    start = str(config.get("start_date", "")).replace("-", "")
    end = str(config.get("end_date", "")).replace("-", "")
    curves = [row for row in curves if (not start or row.get("date", "") >= start) and (not end or row.get("date", "") <= end)]
    orders = [row for row in orders if (not start or row.get("date", "") >= start) and (not end or row.get("date", "") <= end)]
    initial = as_float(config.get("initial_cash"), INITIAL_CASH)
    ending = as_float(curves[-1].get("equity"), initial) if curves else initial
    peak = initial
    max_dd = 0.0
    for row in curves:
        equity = as_float(row.get("equity"), initial)
        peak = max(peak, equity)
        if peak > 0:
            max_dd = min(max_dd, (equity / peak - 1.0) * 100.0)
    summary = {
        "status": "ok",
        "strategy": args.strategy,
        "period": f"{config.get('start_date')} 至 {config.get('end_date')}",
        "decision_days": len(curves),
        "order_count": len(orders),
        "buy_count": sum(1 for row in orders if row.get("action") == "BUY"),
        "sell_count": sum(1 for row in orders if row.get("action") == "SELL"),
        "initial_cash": initial,
        "ending_equity": ending,
        "return_pct": (ending / initial - 1.0) * 100.0 if initial else 0.0,
        "max_drawdown_pct": max_dd,
        "paper_only": True,
        "shadow_only": True,
    }
    write_json(root / "data" / "period_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Shadow strategy lab for the A-share paper simulator.")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT_DEFAULT))
    parser.add_argument("--sim-root", default=str(SIM_ROOT_DEFAULT))
    parser.add_argument("--strategy", default=DEFAULT_STRATEGY)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("--date")
    p_run.add_argument("--stage", default="late_confirm")
    sub.add_parser("summary")
    args = parser.parse_args()
    if args.cmd == "run":
        date = args.date or today_yyyymmdd()
        result = run_shadow(Path(args.project_root), Path(args.sim_root), args.strategy, date, args.stage)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("status") in {"ok", "skipped"} else 1
    if args.cmd == "summary":
        return command_summary(args)
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
