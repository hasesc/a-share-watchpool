#!/usr/bin/env python3
"""Local paper-trading simulator for the A-share watchpool.

The simulator never connects to a broker and never places real orders. It keeps
cash, positions, orders, snapshots, and an HTML dashboard under the workspace.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT_DEFAULT = Path(r"D:\CodexData\a-share-watchpool")
SIM_ROOT_DEFAULT = PROJECT_ROOT_DEFAULT / "paper-sim"
INITIAL_CASH = 100000.0
MAX_PAPER_POSITION_CAP = 8
DISCLAIMER = "模拟盘仅作纸面验证和学习研究，不构成投资建议，不连接券商，不给真实买卖指令。"


@dataclass
class Candidate:
    code: str
    name: str
    price: float
    pct_chg: float
    amount: float
    seed_score: float
    seed_rank: int
    execution_action: str
    execution_flags: str
    risk_action: str
    strategy_score: float = 0.0
    driver_score: float = 0.0
    risk_penalty: float = 0.0
    execution_score: float = 0.0
    contradiction_score: float = 0.0
    sector_core_score: float = 0.0
    candidate_source: str = "strategy_report"
    selection_bucket: str = "main_candidate"
    reason_tags: list[str] | None = None
    source_report: str = ""
    holding_type: str = "short_term"
    sector: str = ""


def today_yyyymmdd() -> str:
    return datetime.now().strftime("%Y%m%d")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(data, ensure_ascii=False) + "\n")


def load_config(sim_root: Path) -> dict[str, Any]:
    config = read_json(sim_root / "config.json", {}) or {}
    return {
        "experiment_name": config.get("experiment_name", "a-share-paper-sim-month-001"),
        "start_date": config.get("start_date", "2026-06-22"),
        "end_date": config.get("end_date", "2026-07-22"),
        "initial_cash": as_float(config.get("initial_cash"), INITIAL_CASH),
        "decision_time": config.get("decision_time", "14:45"),
        "data_stage": config.get("data_stage", "late_confirm"),
        "paper_only": True,
        "rule_lock": config.get("rule_lock", "Rules locked for the experiment window unless explicitly reset."),
        "notes": config.get("notes", "One-month paper simulator."),
    }


def date_in_window(date: str, config: dict[str, Any]) -> bool:
    compact_start = str(config.get("start_date", "")).replace("-", "")
    compact_end = str(config.get("end_date", "")).replace("-", "")
    return (not compact_start or date >= compact_start) and (not compact_end or date <= compact_end)

def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def money(value: float) -> str:
    return f"{value:,.2f}"


def pct(value: float) -> str:
    return f"{value:.2f}%"


def latest_run_dir(root: Path, date: str, preferred_stage: str | None = None) -> Path | None:
    data_root = root / "data" / "watchpool"
    stages = [preferred_stage] if preferred_stage else []
    stages += ["late_confirm", "pre_screen", "pre_market", "post_close"]
    seen: set[str] = set()
    for stage in stages:
        if not stage or stage in seen:
            continue
        seen.add(stage)
        path = data_root / f"{date}_{stage}"
        if (path / "candidate_seed.csv").exists():
            return path
    candidates = sorted(data_root.glob(f"{date}_*"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in candidates:
        if (path / "candidate_seed.csv").exists():
            return path
    return None


def load_candidates(run_dir: Path) -> list[Candidate]:
    seed = run_dir / "candidate_seed.csv"
    execution = read_json(run_dir / "execution_quality.json", {}) or {}
    risk = read_json(run_dir / "risk_events.json", {}) or {}
    exec_by_code = execution.get("by_code") or {}
    risk_by_code = risk.get("by_code") or {}
    block = set(execution.get("block_codes") or []) | set(risk.get("block_codes") or []) | set(
        risk.get("incomplete_codes") or []
    )
    items: list[Candidate] = []
    with seed.open("r", encoding="utf-8-sig", newline="") as handle:
        for idx, row in enumerate(csv.DictReader(handle), 1):
            code = (row.get("code") or row.get("source_symbol") or "").strip()[-6:]
            if not code or code in block:
                continue
            price = as_float(row.get("latest"))
            if price <= 0:
                continue
            exe = exec_by_code.get(code, {})
            risk_row = risk_by_code.get(code, {})
            items.append(
                Candidate(
                    code=code,
                    name=(row.get("name") or code).strip(),
                    price=price,
                    pct_chg=as_float(row.get("pct_chg")),
                    amount=as_float(row.get("amount")),
                    seed_score=as_float(row.get("seed_score")),
                    seed_rank=idx,
                    execution_action=str(exe.get("execution_action") or "unknown"),
                    execution_flags=str(exe.get("risk_flags") or ""),
                    risk_action=str(risk_row.get("action") or "unknown"),
                )
            )
    items.sort(key=lambda item: item.seed_score, reverse=True)
    return items


def latest_strategy_report(root: Path, date: str) -> Path | None:
    path = root / "reports" / "daily" / date / "pre_market_top5.json"
    if path.exists():
        return path
    latest = root / "reports" / "latest" / "pre_market_top5.json"
    if latest.exists():
        payload = read_json(latest, {}) or {}
        if str(payload.get("date") or "").replace("-", "") == date:
            return latest
    return None


def load_quote_prices(run_dir: Path) -> dict[str, dict[str, Any]]:
    quote: dict[str, dict[str, Any]] = {}
    for filename in ["all_a_share_snapshot.csv", "candidate_seed.csv"]:
        path = run_dir / filename
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                code = (row.get("code") or row.get("source_symbol") or "").strip()[-6:]
                if code:
                    quote[code] = row
    return quote


def load_strategy_candidates(report_path: Path | None, run_dir: Path) -> tuple[list[Candidate], dict[str, Any], list[str]]:
    warnings: list[str] = []
    if report_path is None or not report_path.exists():
        return [], {}, ["missing strategy report; simulator will not open new positions"]
    report = read_json(report_path, {}) or {}
    quote = load_quote_prices(run_dir)
    
    execution = read_json(run_dir / "execution_quality.json", {}) or {}
    risk = read_json(run_dir / "risk_events.json", {}) or {}
    block = set(execution.get("block_codes") or []) | set(risk.get("block_codes") or []) | set(
        risk.get("incomplete_codes") or []
    )
    
    exec_by_code = execution.get("by_code") or {}
    risk_by_code = risk.get("by_code") or {}
    
    items: list[Candidate] = []
    groups_to_load = [
        ("tradable_candidates", "short_term", True),
        ("premarket_inference_candidates", "medium_term", False),
        ("research_leads", "long_term", False)
    ]

    seen_codes = set()
    
    for key, holding_type, strict in groups_to_load:
        row_list = report.get(key) or []
        for idx, row in enumerate(row_list, 1):
            if not isinstance(row, dict):
                continue
            code = str(row.get("code") or "").strip()[-6:]
            if not code or code in block or code in seen_codes:
                continue
            q = quote.get(code, {})
            price = as_float(q.get("latest") or row.get("entry_price") or row.get("price"))
            if price <= 0:
                warnings.append(f"{code} missing live quote; skipped")
                continue
            risk_penalty = as_float(row.get("risk_penalty"))
            execution_score = as_float(row.get("execution_score"))
            bucket = str(row.get("selection_bucket") or "main_candidate")
            tags = [str(tag) for tag in (row.get("reason_tags") or [])]
            if strict:
                if bucket != "main_candidate":
                    warnings.append(f"{code} bucket={bucket}; skipped")
                    continue
                if risk_penalty > 8 or execution_score < 70:
                    warnings.append(f"{code} failed strategy risk/execution gate; skipped")
                    continue
            
            # Fetch actual execution and risk details
            exe_info = exec_by_code.get(code, {})
            risk_info = risk_by_code.get(code, {})
            exec_action = str(exe_info.get("execution_action") or "unknown")
            risk_action = str(risk_info.get("action") or "unknown")
            
            # Combine reason tags from pre-market with real-time risk flags
            exe_flags_list = []
            if tags:
                exe_flags_list.extend(tags)
            realtime_flags = str(exe_info.get("risk_flags") or "")
            if realtime_flags:
                for f in realtime_flags.split("、"):
                    for sub_f in f.split(","):
                        sub_f = sub_f.strip()
                        if sub_f and sub_f not in exe_flags_list:
                            exe_flags_list.append(sub_f)
            execution_flags = ",".join(exe_flags_list)
            
            sector = str(row.get("sector") or q.get("sector") or q.get("sw_l1") or "").strip()
            seen_codes.add(code)
            items.append(Candidate(
                code=code,
                name=str(row.get("name") or q.get("name") or code),
                price=price,
                pct_chg=as_float(q.get("pct_chg")),
                amount=as_float(q.get("amount")),
                seed_score=as_float(q.get("seed_score") or row.get("score")),
                seed_rank=idx,
                execution_action=exec_action,
                execution_flags=execution_flags,
                risk_action=risk_action,
                strategy_score=as_float(row.get("score")),
                driver_score=as_float(row.get("driver_score")),
                risk_penalty=risk_penalty,
                execution_score=execution_score,
                contradiction_score=as_float(row.get("contradiction_score")),
                sector_core_score=as_float(row.get("sector_core_score")),
                candidate_source=str(row.get("candidate_source") or key),
                selection_bucket=bucket,
                reason_tags=tags,
                source_report=str(report_path),
                holding_type=holding_type,
                sector=sector,
            ))
    items.sort(key=buy_score, reverse=True)
    return items, report, warnings



def load_state(sim_root: Path) -> dict[str, Any]:
    state_path = sim_root / "data" / "state.json"
    if state_path.exists():
        return read_json(state_path, {}) or {}
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "initial_cash": INITIAL_CASH,
        "cash": INITIAL_CASH,
        "positions": {},
        "realized_pnl": 0.0,
        "last_decision_date": None,
    }


def save_state(sim_root: Path, state: dict[str, Any]) -> None:
    write_json(sim_root / "data" / "state.json", state)


def position_value(position: dict[str, Any], price: float | None = None) -> float:
    mark = price if price is not None else as_float(position.get("last_price"))
    return int(position.get("shares") or 0) * mark


def portfolio_equity(state: dict[str, Any], price_by_code: dict[str, float]) -> float:
    total = as_float(state.get("cash"))
    for code, pos in (state.get("positions") or {}).items():
        total += position_value(pos, price_by_code.get(code, as_float(pos.get("last_price"))))
    return total


def buy_score(candidate: Candidate) -> float:
    score = candidate.seed_score
    score += min(8.0, candidate.driver_score / 20.0)
    score += min(5.0, candidate.sector_core_score / 25.0)
    score -= candidate.risk_penalty
    score -= candidate.contradiction_score
    if candidate.execution_action != "clear":
        score -= 20
    if "near_or_at_limit_up" in candidate.execution_flags:
        score -= 10
    if "large_open_gap" in candidate.execution_flags:
        score -= 6
    if candidate.amount < 300_000_000:
        score -= 5
    return score

def policy_from_market(gate_score: float, gate_regime: str | None, candidate_count: int) -> dict[str, Any]:
    regime = gate_regime or "未评级"
    if gate_score < 35:
        return {
            "target_exposure": 0.0,
            "target_positions": 0,
            "stop_loss_pct": -3.5,
            "take_profit_pct": 6.0,
            "max_hold_decisions": 1,
            "reason": f"市场门槛 {gate_score:.1f} / {regime}，纸面模拟选择空仓。"
        }
    if gate_score < 50:
        return {
            "target_exposure": 0.25,
            "target_positions": min(2, candidate_count),
            "stop_loss_pct": -4.0,
            "take_profit_pct": 8.0,
            "max_hold_decisions": 5,
            "reason": f"市场门槛 {gate_score:.1f} / {regime}，只做小仓位试探。"
        }
    if gate_score < 70:
        return {
            "target_exposure": 0.60,
            "target_positions": min(4, candidate_count),
            "stop_loss_pct": -5.0,
            "take_profit_pct": 10.0,
            "max_hold_decisions": 7,
            "reason": f"市场门槛 {gate_score:.1f} / {regime}，做均衡纸面组合。"
        }
    return {
        "target_exposure": 0.95,
        "target_positions": min(MAX_PAPER_POSITION_CAP, max(1, min(6, candidate_count))),
        "stop_loss_pct": -6.0,
        "take_profit_pct": 12.0,
        "max_hold_decisions": 10,
        "reason": f"市场门槛 {gate_score:.1f} / {regime}，允许高仓位纸面验证。"
    }


def decide(project_root: Path, sim_root: Path, date: str, stage: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
    run_dir = latest_run_dir(project_root, date, stage)
    portfolio_dir = sim_root / "data"
    reports = sim_root / "reports"
    state = load_state(sim_root)
    state.setdefault("positions", {})
    state.setdefault("cash", INITIAL_CASH)
    state.setdefault("realized_pnl", 0.0)
    config = load_config(sim_root)

    if not date_in_window(date, config):
        summary = {
            "status": "blocked",
            "reason": "date outside experiment window",
            "date": date,
            "experiment": config,
            "state": str(portfolio_dir / "state.json"),
        }
        write_json(portfolio_dir / f"{date}_run_summary.json", summary)
        return state, summary

    if state.get("last_decision_date") == date and state.get("last_decision_stage", "late_confirm") == (stage or "late_confirm"):
        summary = {
            "status": "skipped",
            "reason": f"today stage {stage} already decided",
            "date": date,
            "stage": stage,
            "state": str(portfolio_dir / "state.json"),
        }
        return state, summary

    if run_dir is None:
        summary = {"status": "blocked", "reason": "no candidate run dir", "date": date}
        return state, summary

    health = read_json(run_dir / "data_health.json", {}) or {}
    gate = read_json(run_dir / "market_gate_snapshot.json", {}) or {}
    session = read_json(run_dir / "trade_session.json", {}) or gate.get("trade_session") or {}
    execution = read_json(run_dir / "execution_quality.json", {}) or {}
    risk = read_json(run_dir / "risk_events.json", {}) or {}
    strategy_report_path = latest_strategy_report(project_root, date)
    candidates, strategy_report, strategy_warnings = load_strategy_candidates(strategy_report_path, run_dir)
    quote_rows = load_quote_prices(run_dir)
    price_by_code = {code: as_float(row.get("latest")) for code, row in quote_rows.items()}
    price_by_code.update({item.code: item.price for item in candidates})

    orders: list[dict[str, Any]] = []
    global_blocks: list[str] = []
    if not session.get("is_trade_day", True):
        global_blocks.append("非交易日，不做模拟交易。")
    if health.get("health_status") != "ok":
        global_blocks.append(f"data_health={health.get('health_status')}，不新开仓。")
    if not risk.get("promote_allowed_by_risk_check", False):
        global_blocks.append("risk_events 未允许升级，不新开仓。")
    if not execution.get("promote_allowed_by_execution_check", False):
        global_blocks.append("execution_quality 未允许升级，不新开仓。")
    
    gate_score = as_float(gate.get("score"))
    policy = policy_from_market(gate_score, gate.get("regime"), len(candidates))
    
    allow_buy = not global_blocks and policy["target_exposure"] > 0 and bool(candidates)
    
    warnings: list[str] = []
    warnings.extend(global_blocks)
    if policy["target_exposure"] <= 0:
        warnings.append(policy["reason"])
    warnings.extend(strategy_warnings)

    positions = state["positions"]
    
    is_morning = (stage == "morning_confirm")
    is_late = (stage == "late_confirm")
    run_sells = not is_morning
    run_buys = not is_late

    # Update marks and decide exits first.
    exited_codes = set()
    for code in list(positions.keys()):
        pos = positions[code]
        mark = price_by_code.get(code, as_float(pos.get("last_price")))
        entry = as_float(pos.get("avg_price"))
        ret_pct = (mark / entry - 1.0) * 100.0 if entry else 0.0
        pos["last_price"] = mark
        pos["last_mark_date"] = date

        if not run_sells:
            # Morning confirm stage: do not evaluate exits
            continue

        # T+1 rule check: cannot sell today if bought today
        if pos.get("entry_date") == date:
            continue

        pos["hold_decisions"] = int(pos.get("hold_decisions") or 0) + 1
        
        # Update trailing maximum return
        max_ret = max(as_float(pos.get("max_return_pct", 0.0)), ret_pct)
        pos["max_return_pct"] = max_ret

        # Update consecutive days out of short-term watchpool
        h_type = pos.get("holding_type", "short_term")
        if h_type == "short_term":
            in_pool = code in {c.code for c in candidates if c.holding_type == "short_term"}
            if in_pool:
                pos["out_of_pool_days"] = 0
            else:
                pos["out_of_pool_days"] = int(pos.get("out_of_pool_days") or 0) + 1

        if h_type == "long_term":
            stop_loss = -20.0
            take_profit = 65.0
            max_hold = 240
        elif h_type == "medium_term":
            stop_loss = -15.0
            take_profit = 35.0
            max_hold = 60
        else: # short_term
            stop_loss = policy["stop_loss_pct"]
            take_profit = policy["take_profit_pct"]
            max_hold = policy["max_hold_decisions"]
            
        exit_reason = None
        if ret_pct <= stop_loss:
            exit_reason = f"stop_loss {pct(ret_pct)}"
        elif ret_pct >= take_profit:
            exit_reason = f"take_profit {pct(ret_pct)}"
        elif int(pos.get("hold_decisions") or 0) >= max_hold:
            exit_reason = f"max_hold_decisions {max_hold}"
        elif h_type == "short_term":
            if max_ret >= 3.5 and ret_pct <= 0.5:
                exit_reason = f"breakeven_stop (max_ret={pct(max_ret)}, current={pct(ret_pct)})"
            elif int(pos.get("out_of_pool_days") or 0) >= 2:
                exit_reason = "dropped_out_of_short_term_pool_2d"
            
        if exit_reason:
            shares = int(pos.get("shares") or 0)
            proceeds = shares * mark
            pnl = proceeds - shares * entry
            state["cash"] = as_float(state.get("cash")) + proceeds
            state["realized_pnl"] = as_float(state.get("realized_pnl")) + pnl
            order = {
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
            }
            orders.append(order)
            del positions[code]
            exited_codes.add(code)

    # Then open new paper positions if the gate allows.
    if allow_buy and run_buys:
        equity = portfolio_equity(state, price_by_code)
        target_total_value = equity * policy["target_exposure"]
        current_value = sum(position_value(pos, price_by_code.get(code, as_float(pos.get("last_price")))) for code, pos in positions.items())
        remaining_target_value = max(0.0, target_total_value - current_value)
        slots = max(0, int(policy["target_positions"]) - len(positions))
        target_amount = min(
            remaining_target_value / slots if slots else 0.0,
            as_float(state.get("cash")),
        )
        
        # Calculate sector distribution for concentration checks
        sector_counts: dict[str, int] = {}
        sector_values: dict[str, float] = {}
        for p_code, p_pos in positions.items():
            p_sector = p_pos.get("sector") or "unknown"
            p_val = position_value(p_pos, price_by_code.get(p_code))
            sector_counts[p_sector] = sector_counts.get(p_sector, 0) + 1
            sector_values[p_sector] = sector_values.get(p_sector, 0.0) + p_val

        ranked = sorted(candidates, key=buy_score, reverse=True)
        for candidate in ranked:
            if len(positions) >= int(policy["target_positions"]):
                break
            if candidate.code in positions:
                continue
            if candidate.code in exited_codes:
                continue
            if candidate.execution_action != "clear":
                continue
            cash = as_float(state.get("cash"))
            amount = min(target_amount, cash)
            shares = int(amount // candidate.price // 100) * 100
            if shares <= 0:
                continue
            cost = shares * candidate.price
            
            # Sector Concentration Checks (max 3 positions or 40% equity)
            cand_sector = candidate.sector or "unknown"
            if sector_counts.get(cand_sector, 0) >= 3:
                warnings.append(f"{candidate.code} skipped: sector concentration limit (max 3 in {cand_sector})")
                continue
            if equity > 0 and (sector_values.get(cand_sector, 0.0) + cost) / equity > 0.40:
                warnings.append(f"{candidate.code} skipped: sector value limit (max 40% equity in {cand_sector})")
                continue

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
                "strategy_score": candidate.strategy_score,
                "driver_score": candidate.driver_score,
                "risk_penalty": candidate.risk_penalty,
                "execution_score": candidate.execution_score,
                "contradiction_score": candidate.contradiction_score,
                "sector_core_score": candidate.sector_core_score,
                "selection_bucket": candidate.selection_bucket,
                "reason_tags": candidate.reason_tags or [],
                "source_report": candidate.source_report,
                "holding_type": candidate.holding_type,
                "sector": cand_sector,
            }
            # Update sector statistics for subsequent items in the same loop
            sector_counts[cand_sector] = sector_counts.get(cand_sector, 0) + 1
            sector_values[cand_sector] = sector_values.get(cand_sector, 0.0) + cost
            orders.append(
                {
                    "date": date,
                    "time": datetime.now().isoformat(timespec="seconds"),
                    "action": "BUY",
                    "code": candidate.code,
                    "name": candidate.name,
                    "price": candidate.price,
                    "shares": shares,
                    "amount": cost,
                    "reason": f"skill_strategy_pool ({candidate.holding_type}), gate {gate_score:.1f}, score {buy_score(candidate):.2f}",
                    "strategy_candidate": {
                        "source_report": candidate.source_report,
                        "selection_bucket": candidate.selection_bucket,
                        "driver_score": candidate.driver_score,
                        "risk_penalty": candidate.risk_penalty,
                        "contradiction_score": candidate.contradiction_score,
                        "sector_core_score": candidate.sector_core_score,
                        "reason_tags": candidate.reason_tags or [],
                        "holding_type": candidate.holding_type,
                    },
                    "policy": policy,
                    "paper_only": True,
                }
            )


    equity = portfolio_equity(state, price_by_code)
    previous_curve = read_jsonl(portfolio_dir / "equity_curve.jsonl")
    previous_equity = as_float(previous_curve[-1].get("equity"), INITIAL_CASH) if previous_curve else INITIAL_CASH
    daily_pnl = equity - previous_equity
    daily_return_pct = (daily_pnl / previous_equity * 100.0) if previous_equity else 0.0
    state["last_decision_date"] = date
    state["last_decision_stage"] = stage or "late_confirm"
    state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    state["last_run_dir"] = str(run_dir)
    state["last_equity"] = equity

    for order in orders:
        append_jsonl(portfolio_dir / "orders.jsonl", order)
        
    all_orders_today = [o for o in read_jsonl(portfolio_dir / "orders.jsonl") if o.get("date") == date]

    snapshot = {
        "date": date,
        "generated_at": state["updated_at"],
        "run_dir": str(run_dir),
        "stage": stage or "late_confirm",
        "gate_score": gate_score,
        "gate_regime": gate.get("regime"),
        "cash": as_float(state.get("cash")),
        "equity": equity,
        "realized_pnl": as_float(state.get("realized_pnl")),
        "previous_equity": previous_equity,
        "daily_pnl": daily_pnl,
        "daily_return_pct": daily_return_pct,
        "positions": list(positions.values()),
        "orders": all_orders_today,
        "warnings": warnings,
        "policy": policy,
        "paper_only": True,
        "experiment": config,
        "strategy_alignment": {
            "rule": "open candidates come only from skill report tradable_candidates/simulator_selection_pool",
            "strategy_report": str(strategy_report_path) if strategy_report_path else None,
            "strategy_version": strategy_report.get("strategy_version") if isinstance(strategy_report, dict) else None,
            "selection_model": (strategy_report.get("selection_model") or {}).get("version") if isinstance(strategy_report, dict) else None,
            "candidate_codes": [item.code for item in candidates],
        },
        "disclaimer": DISCLAIMER,
    }
    save_state(sim_root, state)
    
    # Save the stage-specific decision json
    decision_filename = f"{date}_{stage}_decision.json" if stage else f"{date}_decision.json"
    write_json(portfolio_dir / decision_filename, snapshot)
    # Also save to default decision json to keep standard paths working
    write_json(portfolio_dir / f"{date}_decision.json", snapshot)
    
    if not is_morning:
        append_jsonl(portfolio_dir / "equity_curve.jsonl", snapshot)
        
    render_html(snapshot, reports / f"{date}_paper_portfolio.html")
    summary = {
        "status": "ok",
        "date": date,
        "html": str(reports / f"{date}_paper_portfolio.html"),
        "decision": str(portfolio_dir / decision_filename),
        "state": str(portfolio_dir / "state.json"),
        "orders": orders, # return current stage orders in summary
        "warnings": warnings,
        "cash": snapshot["cash"],
        "equity": snapshot["equity"],
        "previous_equity": previous_equity,
        "daily_pnl": daily_pnl,
        "daily_return_pct": daily_return_pct,
        "positions": [p["code"] for p in snapshot["positions"]],
        "policy": policy,
        "paper_only": True,
        "experiment": config,
        "strategy_alignment": snapshot.get("strategy_alignment"),
    }
    write_json(portfolio_dir / f"{date}_run_summary.json", summary)
    return state, summary


def render_html(snapshot: dict[str, Any], output: Path) -> None:
    stage_name = snapshot.get("stage") or "late_confirm"
    stage_display = "09:35 早盘确认" if stage_name == "morning_confirm" else "14:45 尾盘结算"
    positions = snapshot.get("positions") or []
    orders = snapshot.get("orders") or []
    warnings = snapshot.get("warnings") or []
    
    # Calculate position values and overall metrics
    total_positions_val = 0.0
    pos_rows_list = []
    
    # A-share color classes (Red is up/positive, Green is down/negative)
    for p in positions:
        shares = int(p.get('shares') or 0)
        avg_price = as_float(p.get('avg_price'))
        last_price = as_float(p.get('last_price'))
        cost_basis = shares * avg_price
        current_value = shares * last_price
        total_positions_val += current_value
        
        pnl = current_value - cost_basis
        pnl_pct = (last_price / avg_price - 1.0) * 100.0 if avg_price else 0.0
        
        if pnl > 0.01:
            pnl_class = "up-color"
            pnl_sign = "+"
        elif pnl < -0.01:
            pnl_class = "down-color"
            pnl_sign = ""
        else:
            pnl_class = "neutral-color"
            pnl_sign = ""
            
        h_type = p.get('holding_type', 'short_term')
        if h_type == 'short_term':
            h_type_display = '<span class="badge badge-short">短线</span>'
        elif h_type == 'medium_term':
            h_type_display = '<span class="badge badge-medium">中线</span>'
        elif h_type == 'long_term':
            h_type_display = '<span class="badge badge-long">长线</span>'
        else:
            h_type_display = f'<span class="badge">{h_type}</span>'
            
        sector_display = html.escape(p.get('sector') or '未定义')
        
        pos_rows_list.append(
            f"<tr>"
            f"<td><div class='code-cell'><span class='code-symbol'>{html.escape(p.get('code',''))}</span><span class='code-name'>{html.escape(p.get('name',''))}</span></div></td>"
            f"<td>{h_type_display}</td>"
            f"<td>{sector_display}</td>"
            f"<td>{shares}</td>"
            f"<td>{money(avg_price)}</td>"
            f"<td>{money(last_price)}</td>"
            f"<td>{money(current_value)}</td>"
            f"<td class='{pnl_class} font-semibold'>{pnl_sign}{money(pnl)} ({pnl_sign}{pnl_pct:.2f}%)</td>"
            f"<td><span class='badge badge-neutral'>{int(p.get('hold_decisions') or 0)}天</span></td>"
            f"</tr>"
        )
    
    pos_rows = "\n".join(pos_rows_list) or '<tr><td colspan="9" class="text-center py-8 text-muted">暂无持仓</td></tr>'
    
    order_rows_list = []
    for o in orders:
        action = o.get('action', '')
        action_class = "badge-buy" if action == "BUY" else "badge-sell"
        action_display = "买入" if action == "BUY" else "卖出"
        
        shares = int(o.get('shares') or 0)
        price = as_float(o.get('price'))
        amount = as_float(o.get('amount'))
        
        cand_info = o.get('strategy_candidate', {})
        h_type = cand_info.get('holding_type') or o.get('holding_type') or 'short_term'
        if h_type == 'short_term':
            h_type_display = '<span class="badge badge-short">短线</span>'
        elif h_type == 'medium_term':
            h_type_display = '<span class="badge badge-medium">中线</span>'
        elif h_type == 'long_term':
            h_type_display = '<span class="badge badge-long">长线</span>'
        else:
            h_type_display = f'<span class="badge">{h_type}</span>'
            
        order_rows_list.append(
            f"<tr>"
            f"<td><span class='badge {action_class}'>{action_display}</span></td>"
            f"<td><div class='code-cell'><span class='code-symbol'>{html.escape(o.get('code',''))}</span><span class='code-name'>{html.escape(o.get('name',''))}</span></div></td>"
            f"<td>{h_type_display}</td>"
            f"<td>{shares}</td>"
            f"<td>{money(price)}</td>"
            f"<td>{money(amount)}</td>"
            f"<td class='text-muted'>{html.escape(o.get('reason',''))}</td>"
            f"</tr>"
        )
    order_rows = "\n".join(order_rows_list) or '<tr><td colspan="7" class="text-center py-8 text-muted">今日无模拟交易</td></tr>'
    
    warning_html = "".join(f"<div class='alert-item'><span class='alert-icon'>⚠️</span><span class='alert-text'>{html.escape(item)}</span></div>" for item in warnings) or "<div class='text-muted text-sm'>无异常报警</div>"
    
    # Format today's change with A-share color
    daily_pnl = as_float(snapshot.get('daily_pnl'))
    daily_return_pct = as_float(snapshot.get('daily_return_pct'))
    if daily_pnl > 0.01:
        pnl_class = "up-color"
        pnl_sign = "+"
        pnl_badge_class = "badge-up"
    elif daily_pnl < -0.01:
        pnl_class = "down-color"
        pnl_sign = ""
        pnl_badge_class = "badge-down"
    else:
        pnl_class = "neutral-color"
        pnl_sign = ""
        pnl_badge_class = "badge-neutral"
        
    gate_score = snapshot.get('gate_score')
    gate_regime = html.escape(str(snapshot.get('gate_regime') or '未评级'))
    
    policy_info = snapshot.get('policy') or {}
    policy_exposure_pct = as_float(policy_info.get('target_exposure')) * 100
    policy_positions = int(policy_info.get('target_positions') or 0)
    policy_reason = html.escape(str(policy_info.get('reason') or '暂无决策约束'))
    
    content = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>A股智能模拟盘控制台</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Noto+Sans+SC:wght@300;400;500;700&display=swap" rel="stylesheet">
<style>
:root {{
    --bg-main: #0a0f1d;
    --bg-card: rgba(20, 28, 52, 0.6);
    --border-color: rgba(38, 52, 92, 0.4);
    --border-highlight: rgba(99, 102, 241, 0.3);
    
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    
    /* A-Share Convention: Red Up, Green Down */
    --color-up: #ef4444;       /* Crimson Red */
    --color-down: #10b981;     /* Mint Green */
    --color-neutral: #94a3b8;
    
    --color-short: #ec4899;     /* Pink */
    --color-medium: #3b82f6;    /* Blue */
    --color-long: #8b5cf6;      /* Purple */
    
    --font-sans: 'Outfit', 'Noto Sans SC', -apple-system, sans-serif;
}}

* {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}}

body {{
    background-color: var(--bg-main);
    background-image: 
        radial-gradient(circle at 10% 20%, rgba(59, 130, 246, 0.08) 0%, transparent 40%),
        radial-gradient(circle at 80% 80%, rgba(139, 92, 246, 0.08) 0%, transparent 40%);
    color: var(--text-primary);
    font-family: var(--font-sans);
    min-height: 100vh;
    padding: 24px;
    line-height: 1.5;
}}

.dashboard-container {{
    max-width: 1280px;
    margin: 0 auto;
}}

/* Header Styling */
.header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 24px;
    border-bottom: 1px solid var(--border-color);
    margin-bottom: 24px;
}}

.header-title h1 {{
    font-size: 28px;
    font-weight: 800;
    background: linear-gradient(135deg, #fff 0%, #a5b4fc 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.5px;
}}

.header-title .tagline {{
    font-size: 14px;
    color: var(--text-secondary);
    margin-top: 4px;
    display: flex;
    align-items: center;
    gap: 8px;
}}

.stage-pill {{
    background: rgba(99, 102, 241, 0.15);
    color: #a5b4fc;
    padding: 2px 10px;
    border-radius: 99px;
    border: 1px solid var(--border-highlight);
    font-size: 12px;
    font-weight: 600;
}}

.header-meta {{
    text-align: right;
    font-size: 13px;
    color: var(--text-secondary);
}}

.header-meta .date {{
    font-weight: 600;
    font-size: 15px;
    color: var(--text-primary);
}}

/* Key Metrics Cards */
.metrics-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
}}

.metric-card {{
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 16px;
    padding: 20px;
    backdrop-filter: blur(12px);
    transition: all 0.3s ease;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}}

.metric-card:hover {{
    border-color: var(--border-highlight);
    transform: translateY(-2px);
    box-shadow: 0 12px 20px rgba(0, 0, 0, 0.2);
}}

.metric-card .metric-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: var(--text-secondary);
    font-size: 13px;
    margin-bottom: 12px;
}}

.metric-card .metric-value {{
    font-size: 26px;
    font-weight: 800;
    color: #fff;
    font-variant-numeric: tabular-nums;
}}

.metric-card .metric-footer {{
    margin-top: 12px;
    font-size: 12px;
    display: flex;
    align-items: center;
    gap: 6px;
}}

/* Colors & Badges */
.up-color {{ color: var(--color-up) !important; }}
.down-color {{ color: var(--color-down) !important; }}
.neutral-color {{ color: var(--color-neutral) !important; }}
.font-semibold {{ font-weight: 600; }}

.badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
}}

.badge-up {{
    background: rgba(239, 68, 68, 0.15);
    color: var(--color-up);
    border: 1px solid rgba(239, 68, 68, 0.2);
}}

.badge-down {{
    background: rgba(16, 185, 129, 0.15);
    color: var(--color-down);
    border: 1px solid rgba(16, 185, 129, 0.2);
}}

.badge-neutral {{
    background: rgba(148, 163, 184, 0.1);
    color: var(--color-neutral);
    border: 1px solid rgba(148, 163, 184, 0.2);
}}

.badge-short {{
    background: rgba(236, 72, 153, 0.15);
    color: var(--color-short);
    border: 1px solid rgba(236, 72, 153, 0.2);
}}

.badge-medium {{
    background: rgba(59, 130, 246, 0.15);
    color: var(--color-medium);
    border: 1px solid rgba(59, 130, 246, 0.2);
}}

.badge-long {{
    background: rgba(139, 92, 246, 0.15);
    color: var(--color-long);
    border: 1px solid rgba(139, 92, 246, 0.2);
}}

.badge-buy {{
    background: rgba(239, 68, 68, 0.15);
    color: var(--color-up);
    border: 1px solid rgba(239, 68, 68, 0.25);
    padding: 3px 10px;
    border-radius: 6px;
}}

.badge-sell {{
    background: rgba(16, 185, 129, 0.15);
    color: var(--color-down);
    border: 1px solid rgba(16, 185, 129, 0.25);
    padding: 3px 10px;
    border-radius: 6px;
}}

/* Two Column Layout */
.layout-grid {{
    display: grid;
    grid-template-columns: 2.3fr 1fr;
    gap: 20px;
    align-items: start;
}}

@media (max-width: 1024px) {{
    .layout-grid {{
        grid-template-columns: 1fr;
    }}
}}

/* Section Panel Styling */
.section-panel {{
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 20px;
    padding: 24px;
    backdrop-filter: blur(12px);
    margin-bottom: 20px;
}}

.section-panel h2 {{
    font-size: 18px;
    font-weight: 700;
    margin-bottom: 18px;
    color: #fff;
    display: flex;
    align-items: center;
    gap: 8px;
    border-left: 4px solid #6366f1;
    padding-left: 10px;
}}

/* Tables */
.table-wrapper {{
    overflow-x: auto;
    width: 100%;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    text-align: left;
}}

th {{
    color: var(--text-secondary);
    font-weight: 600;
    font-size: 12px;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border-color);
    text-transform: uppercase;
    background: rgba(15, 23, 42, 0.4);
}}

td {{
    padding: 16px;
    border-bottom: 1px solid var(--border-color);
    font-size: 14px;
    vertical-align: middle;
}}

tr:hover td {{
    background: rgba(255, 255, 255, 0.02);
}}

/* Stock Name and Symbol Layout */
.code-cell {{
    display: flex;
    flex-direction: column;
    gap: 2px;
}}

.code-symbol {{
    font-family: monospace;
    font-weight: 600;
    color: var(--text-primary);
}}

.code-name {{
    font-size: 12px;
    color: var(--text-secondary);
}}

/* Side Panel Info */
.policy-card {{
    background: rgba(15, 23, 42, 0.5);
    border-radius: 12px;
    padding: 16px;
    border: 1px solid var(--border-color);
    margin-bottom: 16px;
}}

.policy-card-title {{
    font-size: 12px;
    color: var(--text-secondary);
    text-transform: uppercase;
    font-weight: 600;
    margin-bottom: 8px;
}}

.policy-card-value {{
    font-size: 14px;
    color: var(--text-primary);
}}

/* Alerts Section */
.alerts-list {{
    display: flex;
    flex-direction: column;
    gap: 10px;
}}

.alert-item {{
    background: rgba(245, 158, 11, 0.08);
    border: 1px solid rgba(245, 158, 11, 0.2);
    padding: 12px 16px;
    border-radius: 10px;
    display: flex;
    gap: 10px;
    align-items: flex-start;
}}

.alert-icon {{
    color: #f59e0b;
    font-size: 16px;
}}

.alert-text {{
    font-size: 13px;
    color: #fde68a;
}}

.footer-disclaimer {{
    text-align: center;
    color: var(--text-muted);
    font-size: 11px;
    margin-top: 40px;
    padding-top: 20px;
    border-top: 1px solid var(--border-color);
}}
</style>
</head>
<body>
<main class="dashboard-container">
    <header class="header">
        <div class="header-title">
            <h1>A股智能模拟交易控制台</h1>
            <div class="tagline">
                <span>量化交易纸面回测决策系统</span>
                <span class="stage-pill">{stage_display}</span>
            </div>
        </div>
        <div class="header-meta">
            <div class="date">{html.escape(snapshot.get('date',''))}</div>
            <div>数据生成时间: {html.escape(snapshot.get('generated_at',''))}</div>
        </div>
    </header>

    <!-- Metrics Hero -->
    <section class="metrics-grid">
        <div class="metric-card">
            <div class="metric-header">
                <span>总权益 (Equity)</span>
                <span class="badge {pnl_badge_class}">{pnl_sign}{pct(daily_return_pct)}</span>
            </div>
            <div class="metric-value">{money(as_float(snapshot.get('equity')))}</div>
            <div class="metric-footer text-muted">
                <span>今日变动:</span>
                <span class="{pnl_class} font-semibold">{pnl_sign}{money(daily_pnl)}</span>
            </div>
        </div>
        <div class="metric-card">
            <div class="metric-header">
                <span>现金账户 (Cash)</span>
                <span class="badge badge-neutral">可用资金</span>
            </div>
            <div class="metric-value">{money(as_float(snapshot.get('cash')))}</div>
            <div class="metric-footer text-secondary">
                <span>资金占比: {as_float(snapshot.get('cash')) / max(1.0, as_float(snapshot.get('equity'))) * 100:.1f}%</span>
            </div>
        </div>
        <div class="metric-card">
            <div class="metric-header">
                <span>持仓市值 (Positions Value)</span>
                <span class="badge badge-neutral">股票资产</span>
            </div>
            <div class="metric-value">{money(total_positions_val)}</div>
            <div class="metric-footer text-secondary">
                <span>股票占比: {total_positions_val / max(1.0, as_float(snapshot.get('equity'))) * 100:.1f}%</span>
            </div>
        </div>
        <div class="metric-card">
            <div class="metric-header">
                <span>市场环境门槛 (Market Gate)</span>
                <span class="badge badge-neutral">大盘风控</span>
            </div>
            <div class="metric-value" style="color: #a5b4fc;">{gate_score} <span style="font-size: 15px; font-weight: normal; color: var(--text-secondary);">/ 100</span></div>
            <div class="metric-footer text-secondary">
                <span>市场状态: <strong style="color: #fff;">{gate_regime}</strong></span>
            </div>
        </div>
    </section>

    <!-- Content Layout -->
    <div class="layout-grid">
        <!-- Main Column -->
        <div class="main-column">
            <!-- Positions Panel -->
            <section class="section-panel">
                <h2>📊 当前仓位明细</h2>
                <div class="table-wrapper">
                    <table>
                        <thead>
                            <tr>
                                <th>代码/名称</th>
                                <th>类型</th>
                                <th>所属行业</th>
                                <th>持股数</th>
                                <th>持仓均价</th>
                                <th>最新价格</th>
                                <th>持仓市值</th>
                                <th>持仓盈亏 (A股红涨绿跌)</th>
                                <th>持有决策日</th>
                            </tr>
                        </thead>
                        <tbody>
                            {pos_rows}
                        </tbody>
                    </table>
                </div>
            </section>

            <!-- Orders Panel -->
            <section class="section-panel">
                <h2>⚡ 今日决策执行</h2>
                <div class="table-wrapper">
                    <table>
                        <thead>
                            <tr>
                                <th>执行动作</th>
                                <th>代码/名称</th>
                                <th>类型</th>
                                <th>执行股数</th>
                                <th>执行价格</th>
                                <th>发生金额</th>
                                <th>执行原因/触发条件</th>
                            </tr>
                        </thead>
                        <tbody>
                            {order_rows}
                        </tbody>
                    </table>
                </div>
            </section>
        </div>

        <!-- Sidebar Column -->
        <div class="sidebar-column">
            <!-- Policy Cards -->
            <section class="section-panel">
                <h2>⚙️ 今日交易约束</h2>
                
                <div class="policy-card">
                    <div class="policy-card-title">拟定目标总仓位比例</div>
                    <div class="policy-card-value font-semibold" style="color: #a5b4fc; font-size: 18px;">
                        {policy_exposure_pct:.0f}% <span style="font-size: 13px; font-weight: normal; color: var(--text-secondary);">上限</span>
                    </div>
                </div>

                <div class="policy-card">
                    <div class="policy-card-title">最大允许持仓只数</div>
                    <div class="policy-card-value font-semibold" style="color: #a5b4fc; font-size: 18px;">
                        {policy_positions} <span style="font-size: 13px; font-weight: normal; color: var(--text-secondary);">只标的</span>
                    </div>
                </div>

                <div class="policy-card">
                    <div class="policy-card-title">大盘风控评语</div>
                    <div class="policy-card-value text-secondary text-sm">
                        {policy_reason}
                    </div>
                </div>
            </section>

            <!-- Warnings/Alerts Panel -->
            <section class="section-panel">
                <h2>⚠️ 异常与运行警报</h2>
                <div class="alerts-list">
                    {warning_html}
                </div>
            </section>
        </div>
    </div>

    <!-- Footer Disclaimer -->
    <footer class="footer-disclaimer">
        <p>{html.escape(DISCLAIMER)}</p>
    </footer>
</main>
</body>
</html>
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def render_period_summary(summary: dict[str, Any], output: Path) -> None:
    order_rows = "\n".join(
        f"<tr><td>{html.escape(str(o.get('date','')))}</td><td>{html.escape(str(o.get('action','')))}</td>"
        f"<td>{html.escape(str(o.get('code','')))}</td><td>{html.escape(str(o.get('name','')))}</td>"
        f"<td>{int(o.get('shares') or 0)}</td><td>{money(as_float(o.get('amount')))}</td></tr>"
        for o in summary.get("orders", [])[-30:]
    ) or '<tr><td colspan="6">暂无交易</td></tr>'
    content = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>模拟盘阶段汇总</title>
<style>
:root {{ --bg:#070b12; --panel:#101827; --panel2:#0d1422; --line:#243247; --text:#eef3ff; --muted:#93a4bc; --gold:#f5c15d; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:radial-gradient(circle at 20% 0%,#17233a 0,#070b12 34%,#05070d 100%); color:var(--text); font-family:"Microsoft YaHei",Arial,sans-serif; }}
.page {{ width:min(1080px,calc(100vw - 32px)); margin:24px auto; padding:26px; background:linear-gradient(180deg,rgba(16,24,39,.98),rgba(8,13,23,.98)); border:1px solid var(--line); box-shadow:0 24px 80px rgba(0,0,0,.38); }}
.header {{ background:#0b1321; color:var(--text); padding:18px 22px; border:1px solid var(--line); }}
.metrics {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin:14px 0; }}
.metric {{ background:var(--panel2); border:1px solid var(--line); padding:12px; }}
.label {{ color:var(--muted); font-size:12px; }} .value {{ font-size:22px; font-weight:900; color:var(--gold); }}
section {{ background:var(--panel2); border:1px solid var(--line); padding:14px; }}
table {{ width:100%; border-collapse:collapse; }} th,td {{ border-bottom:1px solid var(--line); padding:9px; text-align:left; font-size:14px; }} th {{ background:#162238; color:#c9d7ee; }}
.footer {{ color:var(--muted); font-size:12px; margin-top:18px; }}
@media(max-width:860px) {{ .metrics {{ grid-template-columns:1fr; }} .page {{ overflow-x:auto; }} }}
</style>
</head>
<body><main class="page">
<header class="header"><h1>模拟盘阶段汇总</h1><div>{html.escape(summary.get('period',''))}</div></header>
<section class="metrics">
<div class="metric"><div class="label">初始资金</div><div class="value">{money(as_float(summary.get('initial_cash')))}</div></div>
<div class="metric"><div class="label">期末权益</div><div class="value">{money(as_float(summary.get('ending_equity')))}</div></div>
<div class="metric"><div class="label">收益率</div><div class="value">{pct(as_float(summary.get('return_pct')))}</div></div>
<div class="metric"><div class="label">最大回撤</div><div class="value">{pct(as_float(summary.get('max_drawdown_pct')))}</div></div>
</section>
<section><h2>交易记录</h2><table><thead><tr><th>日期</th><th>动作</th><th>代码</th><th>名称</th><th>股数</th><th>金额</th></tr></thead><tbody>{order_rows}</tbody></table></section>
<footer class="footer">{html.escape(DISCLAIMER)}</footer>
</main></body></html>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")


def command_summary(args: argparse.Namespace) -> int:
    sim_root = Path(args.sim_root)
    config = load_config(sim_root)
    data_dir = sim_root / "data"
    reports = sim_root / "reports"
    curves = read_jsonl(data_dir / "equity_curve.jsonl")
    orders = read_jsonl(data_dir / "orders.jsonl")
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
        "experiment": config,
        "period": f"{config.get('start_date')} 至 {config.get('end_date')}",
        "decision_days": len(curves),
        "order_count": len(orders),
        "buy_count": sum(1 for row in orders if row.get("action") == "BUY"),
        "sell_count": sum(1 for row in orders if row.get("action") == "SELL"),
        "initial_cash": initial,
        "ending_equity": ending,
        "return_pct": (ending / initial - 1.0) * 100.0 if initial else 0.0,
        "max_drawdown_pct": max_dd,
        "orders": orders,
        "paper_only": True,
        "disclaimer": DISCLAIMER,
    }
    write_json(data_dir / "period_summary.json", summary)
    render_period_summary(summary, reports / "period_summary.html")
    print(json.dumps({k: v for k, v in summary.items() if k != "orders"}, ensure_ascii=False, indent=2))
    return 0


def command_init(args: argparse.Namespace) -> int:
    sim_root = Path(args.sim_root)
    state_path = sim_root / "data" / "state.json"
    if state_path.exists() and not args.force:
        print(json.dumps({"status": "exists", "state": str(state_path)}, ensure_ascii=False, indent=2))
        return 0
    state = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "initial_cash": INITIAL_CASH,
        "cash": INITIAL_CASH,
        "positions": {},
        "realized_pnl": 0.0,
        "last_decision_date": None,
    }
    save_state(sim_root, state)
    print(json.dumps({"status": "initialized", "state": str(state_path)}, ensure_ascii=False, indent=2))
    return 0


def command_decide(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root)
    sim_root = Path(args.sim_root)
    date = args.date or today_yyyymmdd()
    _, summary = decide(project_root, sim_root, date, args.stage)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary.get("status") in {"ok", "skipped"} else 1


def command_status(args: argparse.Namespace) -> int:
    sim_root = Path(args.sim_root)
    state = load_state(sim_root)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def command_render(args: argparse.Namespace) -> int:
    sim_root = Path(args.sim_root)
    date = args.date or today_yyyymmdd()
    decision_path = sim_root / "data" / f"{date}_decision.json"
    if not decision_path.exists():
        print(json.dumps({"status": "blocked", "reason": "missing decision", "decision": str(decision_path)}, ensure_ascii=False, indent=2))
        return 1
    snapshot = read_json(decision_path, {}) or {}
    output = sim_root / "reports" / f"{date}_paper_portfolio.html"
    render_html(snapshot, output)
    print(json.dumps({"status": "ok", "date": date, "html": str(output), "decision": str(decision_path)}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="A-share local paper portfolio simulator.")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT_DEFAULT))
    parser.add_argument("--sim-root", default=str(SIM_ROOT_DEFAULT))
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_init = sub.add_parser("init")
    p_init.add_argument("--force", action="store_true")
    p_decide = sub.add_parser("decide")
    p_decide.add_argument("--date")
    p_decide.add_argument("--stage", default="late_confirm")
    p_render = sub.add_parser("render")
    p_render.add_argument("--date")
    sub.add_parser("status")
    sub.add_parser("summary")
    args = parser.parse_args()
    if args.cmd == "init":
        return command_init(args)
    if args.cmd == "decide":
        return command_decide(args)
    if args.cmd == "status":
        return command_status(args)
    if args.cmd == "render":
        return command_render(args)
    if args.cmd == "summary":
        return command_summary(args)
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
