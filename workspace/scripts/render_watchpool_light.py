#!/usr/bin/env python3
"""Deterministic light report builder for the A-share watchpool workflow.

This script owns the daily JSON construction, HTML rendering, and output
validation so Codex automations do not need to hand-compose reports.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_DEFAULT = Path(r"D:\CodexData\a-share-watchpool")
RENDERER = Path(
    r"C:\Users\Administrator\.codex\skills\a-share-watchpool-report\scripts\render_watchpool_report.py"
)
DISCLAIMER = (
    "以上内容仅用于个人学习研究与策略验证记录，不构成投资建议、买卖依据或收益承诺，"
    "不提供真实买卖指令。市场有风险，交易需谨慎。"
)
STRATEGY_VERSION = "a-share-watchpool-v0.9.0"
MAIN_GATE_MIN_SCORE = 50.0
MAIN_RISK_MAX = 8
MAIN_DRIVER_MIN = 72
MAIN_EXECUTION_MIN = 70
HIGH_LIMIT_BREAK_RATE = 35.0
MIN_SUPPLEMENTAL_AMOUNT = 3_000_000_000
LOW_POSITION_MIN_PCT = 2.5
LOW_POSITION_MAX_PCT = 6.5
TOP_DIRECTION_LIMIT = 4
LOCAL_INDUSTRY_MAP = ROOT_DEFAULT / "config" / "industry_theme_map.json"


THEME_HINTS = {
    "000725": ("显示面板 / 消费电子", "大市值显示面板方向锚点", "显示面板与消费电子"),
    "300285": ("电子材料 / 陶瓷材料", "高端电子材料", "电子材料与半导体光电"),
    "600703": ("化合物半导体 / LED", "化合物半导体与光电器件", "电子材料与半导体光电"),
    "300548": ("光通信 / 高速光模块", "光通信高弹性硬件", "光通信与高景气硬件"),
    "603663": ("新材料 / 锆系材料", "高弹性新材料", "新材料与资源品"),
    "600487": ("光通信 / 电力线缆", "光通信与能源互联硬件", "光通信与高景气硬件"),
    "601869": ("光纤光缆 / 光通信", "光通信基础材料与链路", "光通信与高景气硬件"),
    "000657": ("硬质合金 / 稀有金属", "高端钨材料", "新材料与资源品"),
    "600549": ("稀有金属 / 新材料", "钨钼稀有金属与材料供给", "新材料与资源品"),
    "603986": ("存储芯片 / 半导体设计", "存储与MCU国产替代", "半导体设计与存储"),
    "600584": ("半导体封测", "先进封装与封测产能", "半导体封测"),
    "600498": ("光通信 / 通信设备", "光通信与网络设备", "光通信与高景气硬件"),
    "002636": ("覆铜板 / 电子材料", "PCB上游电子材料", "电子材料与半导体光电"),
    "002155": ("黄金 / 有色资源", "贵金属资源供给", "黄金资源与有色金属"),
    "002378": ("钨 / 小金属", "钨资源与硬质合金材料", "新材料与资源品"),
    "600176": ("玻璃纤维 / 新材料", "玻纤材料供给", "新材料与资源品"),
    "600392": ("稀土 / 有色资源", "稀土资源与分离冶炼", "新材料与资源品"),
    "601688": ("证券 / 非银金融", "券商风险偏好弹性", "非银金融与券商"),
    "300769": ("锂电材料 / 正极材料", "磷酸铁锂正极材料", "锂电材料"),
    "000426": ("有色金属 / 银锡资源", "银锡矿产资源", "黄金资源与有色金属"),
    "002245": ("锂电 / LED芯片", "锂电与LED芯片弹性", "锂电材料"),
    "688200": ("半导体设备 / 测试设备", "半导体测试设备", "半导体设备"),
    "600226": ("资源品 / 化工材料", "资源品与化工材料", "新材料与资源品"),
    "002709": ("锂电材料 / 电解液", "电解液材料供给", "锂电材料"),
    "300903": ("PCB / 电子制造", "PCB制造与电子链条", "PCB与电子制造"),
    "300209": ("商业航天 / 数据服务", "航天数据与行业应用", "商业航天与数字服务"),
    "601628": ("保险 / 非银金融", "保险风险偏好弹性", "非银金融与保险"),
    "300037": ("锂电材料 / 电解液添加剂", "锂电化学品供给", "锂电材料"),
    "603993": ("钼钴 / 有色资源", "钼钴资源供给", "黄金资源与有色金属"),
    "600459": ("贵金属 / 铂族金属", "铂族金属材料", "黄金资源与有色金属"),
    "600667": ("半导体 / 电子制造", "半导体配套与电子制造", "电子与半导体"),
    "600030": ("证券 / 非银金融", "券商风险偏好弹性", "非银金融与券商"),
    "002056": ("磁材 / 光伏锂电", "磁性材料与新能源材料", "新材料与资源品"),
    "600378": ("化工新材料", "高端化工材料", "新材料与资源品"),
    "002491": ("通信线缆 / 网络设备", "通信线缆与网络设备", "光通信与高景气硬件"),
    "600641": ("半导体 / 电子硬件", "电子硬件链条", "电子与半导体"),
    "600309": ("化工 / 聚氨酯材料", "化工材料龙头", "化工新材料"),
    "600089": ("电力设备 / 硅料变压器", "电力设备与能源材料", "电力设备与新能源"),
    "000807": ("铝 / 有色资源", "电解铝资源供给", "黄金资源与有色金属"),
    "688729": ("半导体设备 / 刻蚀沉积", "半导体设备链条", "半导体设备"),
    "600410": ("IT服务 / 算力应用", "信息化与算力应用", "AI与数字服务"),
    "688146": ("电子特气 / 半导体材料", "半导体电子特气", "电子材料与半导体光电"),
}



DEFAULT_INDUSTRY_THEME_RULES = [
    {"keywords": ["证券", "多元金融"], "sector": "证券 / 非银金融", "scarce_layer": "券商风险偏好弹性", "direction": "非银金融与券商"},
    {"keywords": ["保险"], "sector": "保险 / 非银金融", "scarce_layer": "保险风险偏好弹性", "direction": "非银金融与保险"},
    {"keywords": ["通信设备", "光模块", "光通信", "光纤", "光缆", "CPO", "高速互联"], "sector": "光通信 / 通信设备", "scarce_layer": "通信链路硬件", "direction": "光通信与高景气硬件"},
    {"keywords": ["半导体设备", "半导体材料", "电子化学品", "电子特气", "光刻", "刻蚀", "沉积"], "sector": "半导体设备 / 材料", "scarce_layer": "半导体设备材料链条", "direction": "电子材料与半导体光电"},
    {"keywords": ["半导体", "芯片", "集成电路", "电子元件", "存储", "MCU"], "sector": "半导体 / 电子", "scarce_layer": "电子硬件链条", "direction": "电子与半导体"},
    {"keywords": ["PCB", "印制电路", "覆铜板"], "sector": "PCB / 电子制造", "scarce_layer": "PCB制造与电子链条", "direction": "PCB与电子制造"},
    {"keywords": ["锂电", "电池", "电解液", "正极", "负极"], "sector": "锂电 / 新能源材料", "scarce_layer": "锂电材料供给", "direction": "锂电材料"},
    {"keywords": ["稀土", "小金属", "工业金属", "贵金属", "铝", "钼", "钨", "黄金", "有色"], "sector": "有色资源", "scarce_layer": "有色金属资源供给", "direction": "黄金资源与有色金属"},
    {"keywords": ["电力设备", "光伏", "风电", "变压器", "硅料", "储能"], "sector": "电力设备 / 新能源", "scarce_layer": "电力设备与能源材料", "direction": "电力设备与新能源"},
    {"keywords": ["化学制品", "化工", "聚氨酯", "新材料"], "sector": "化工新材料", "scarce_layer": "化工材料供给", "direction": "化工新材料"},
]

_INDUSTRY_THEME_RULES: list[dict[str, Any]] | None = None

@dataclass
class Candidate:
    code: str
    name: str
    latest: float | None
    pct_chg: float | None
    prev_close: float | None
    open_price: float | None
    high: float | None
    low: float | None
    amount: float | None
    seed_score: float
    seed_rank: int
    industry_l1: str
    industry_l2: str
    industry_l3: str
    concepts: str
    candidate_source: str
    execution_action: str
    execution_score: float | None
    execution_flags: str
    risk_action: str


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt_pct(value: float | None) -> str:
    return "NA" if value is None else f"{value:.2f}%"


def fmt_amount(value: float | None) -> str:
    if value is None:
        return "NA"
    return f"{value / 100000000:.2f}亿元"


def yyyymmdd_today() -> str:
    return datetime.now().strftime("%Y%m%d")


def load_renderer():
    if not RENDERER.exists():
        raise FileNotFoundError(f"renderer not found: {RENDERER}")
    spec = importlib.util.spec_from_file_location("render_watchpool_report", RENDERER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load renderer: {RENDERER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render_html(report: dict[str, Any], output: Path) -> None:
    renderer = load_renderer()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(renderer.render_html(report), encoding="utf-8")


def daily_report_dir(root: Path, date: str) -> Path:
    return root / "reports" / "daily" / date


def dashboard_report_dir(root: Path) -> Path:
    return root / "reports" / "dashboard"


def latest_report_dir(root: Path) -> Path:
    return root / "reports" / "latest"


def report_path(root: Path, date: str, name: str) -> Path:
    return daily_report_dir(root, date) / name


def publish_latest(root: Path, paths: list[Path], date: str, kind: str) -> None:
    out_dir = latest_report_dir(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    links: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        target = out_dir / path.name
        shutil.copy2(path, target)
        links.append(f'<li><a href="{path.name}">{path.name}</a></li>')
    index = (
        "<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>A股观察池最新报告</title>"
        "<style>:root{--bg:#070b12;--panel:#101827;--panel2:#0d1422;--line:#243247;--text:#eef3ff;--muted:#93a4bc;--gold:#f5c15d}"
        "*{box-sizing:border-box}body{font-family:Microsoft YaHei,Arial,sans-serif;margin:0;padding:28px;color:var(--text);"
        "background:radial-gradient(circle at 20% 0%,#17233a 0,#070b12 34%,#05070d 100%)}main{max-width:860px;margin:auto;"
        "background:linear-gradient(180deg,rgba(16,24,39,.98),rgba(8,13,23,.98));border:1px solid var(--line);padding:26px;box-shadow:0 24px 80px rgba(0,0,0,.38)}"
        "h1{margin:0 0 10px;font-size:30px}p{color:var(--muted)}ul{background:var(--panel2);border:1px solid var(--line);padding:16px 16px 16px 34px}"
        "a{color:var(--gold);text-decoration:none;font-weight:800}li{margin:10px 0}</style></head><body><main>"
        f"<h1>A股观察池最新报告</h1><p>日期：{date}；类型：{kind}</p><ul>"
        + "".join(links)
        + "</ul></main></body></html>"
    )
    (out_dir / "index.html").write_text(index, encoding="utf-8")


def find_report(root: Path, date: str, legacy_name: str, new_name: str | None = None) -> Path:
    new_path = report_path(root, date, new_name or legacy_name)
    if new_path.exists():
        return new_path
    return root / "reports" / legacy_name


def read_audit(root: Path) -> dict[str, Any]:
    new_path = dashboard_report_dir(root) / "strategy_audit.json"
    if new_path.exists():
        return read_json(new_path, {}) or {}
    return read_json(root / "reports" / "strategy_audit.json", {}) or {}


def status_report(title: str, date: str, reason: str, mode: str = "status") -> dict[str, Any]:
    return {
        "title": title,
        "subtitle": "自动化状态页",
        "strategy_version": STRATEGY_VERSION,
        "date": f"{date[:4]}-{date[4:6]}-{date[6:]}",
        "data_cutoff": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,
        "report_type": "data_failure",
        "today_view": "不生成候选",
        "suggested_position": "0%",
        "environment_score": "NA",
        "preferred": "无",
        "market_environment": reason,
        "market_gate": {
            "score": "NA",
            "regime": "数据无效",
            "position": "0%",
            "data_quality": "invalid",
            "diagnostics": [reason],
            "downgrades": ["未通过报告生成前置条件。"],
        },
        "hard_filters": {"passed": False, "warnings": [reason], "rejected": []},
        "execution_quality": {
            "promote_allowed_by_execution_check": False,
            "block_codes": [],
            "warning_codes": [],
            "summary": reason,
        },
        "directions": [],
        "tradable_candidates": [],
        "premarket_inference_candidates": [],
        "research_leads": [],
        "cross_check": {"status": "not_run", "data_quality": "invalid", "action": "blocked"},
        "review_tracking": {"log_ready": False, "fields_missing": ["valid_daily_data"]},
        "one_pick": {"code": "无", "text": "前置条件不满足，不强行生成候选。"},
        "risks": [reason],
        "disclaimer": DISCLAIMER,
    }



def load_industry_theme_rules(root: Path | None = None) -> list[dict[str, Any]]:
    global _INDUSTRY_THEME_RULES
    if _INDUSTRY_THEME_RULES is not None:
        return _INDUSTRY_THEME_RULES
    rules = list(DEFAULT_INDUSTRY_THEME_RULES)
    config_path = (root or ROOT_DEFAULT) / "config" / "industry_theme_map.json"
    if config_path.exists():
        payload = read_json(config_path, {}) or {}
        for item in payload.get("rules", []):
            if not isinstance(item, dict):
                continue
            if not item.get("keywords") or not item.get("sector") or not item.get("direction"):
                continue
            rules.append(item)
    _INDUSTRY_THEME_RULES = rules
    return rules


def industry_mapping_diagnostics(candidates: list[Candidate]) -> dict[str, Any]:
    unknown = []
    by_direction: dict[str, int] = {}
    for candidate in candidates:
        sector, _, direction = theme_for(candidate)
        by_direction[direction] = by_direction.get(direction, 0) + 1
        if direction == "待识别方向" or sector == "未细分强势种子":
            unknown.append({"code": candidate.code, "name": candidate.name})
    total = len(candidates)
    return {
        "total_candidates": total,
        "unknown_count": len(unknown),
        "unknown_ratio": round(len(unknown) / total, 4) if total else 0,
        "unknown_examples": unknown[:12],
        "direction_count": by_direction,
        "local_map_path": str(LOCAL_INDUSTRY_MAP),
        "rule": "unknown_ratio 高时应补 structured industry/concept 或 config/industry_theme_map.json。",
    }

def load_candidates(run_dir: Path) -> list[Candidate]:
    seed_path = run_dir / "candidate_seed.csv"
    execution = read_json(run_dir / "execution_quality.json", {}) or {}
    risk = read_json(run_dir / "risk_events.json", {}) or {}
    exec_by_code = execution.get("by_code") or {}
    risk_by_code = risk.get("by_code") or {}

    candidates: list[Candidate] = []
    with seed_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for idx, row in enumerate(csv.DictReader(handle), 1):
            code = (row.get("code") or row.get("source_symbol") or "").strip()
            code = code[-6:] if len(code) >= 6 else code
            if not code:
                continue
            exe = exec_by_code.get(code, {})
            risk_row = risk_by_code.get(code, {})
            candidates.append(
                Candidate(
                    code=code,
                    name=(row.get("name") or code).strip(),
                    latest=as_float(row.get("latest")),
                    pct_chg=as_float(row.get("pct_chg")),
                    prev_close=as_float(row.get("prev_close")),
                    open_price=as_float(row.get("open")),
                    high=as_float(row.get("high")),
                    low=as_float(row.get("low")),
                    amount=as_float(row.get("amount")),
                    seed_score=as_float(row.get("seed_score")) or 0.0,
                    seed_rank=idx,
                    industry_l1=str(row.get("sw_l1") or row.get("industry_l1") or row.get("申万一级") or ""),
                    industry_l2=str(row.get("sw_l2") or row.get("industry_l2") or row.get("申万二级") or ""),
                    industry_l3=str(row.get("sw_l3") or row.get("industry_l3") or row.get("申万三级") or ""),
                    concepts=str(row.get("concepts") or row.get("概念") or row.get("hot_concepts") or ""),
                    candidate_source=str(row.get("candidate_source") or "momentum_seed"),
                    execution_action=str(exe.get("execution_action") or "unknown"),
                    execution_score=as_float(exe.get("execution_score")),
                    execution_flags=str(exe.get("risk_flags") or ""),
                    risk_action=str(risk_row.get("action") or "unknown"),
                )
            )
    candidates.sort(key=lambda item: item.seed_score, reverse=True)
    return candidates


def supplemental_candidates_from_snapshot(
    run_dir: Path,
    existing_codes: set[str],
    start_rank: int,
    limit: int = 40,
) -> list[Candidate]:
    rows = load_csv_rows(run_dir / "all_a_share_snapshot.csv")
    candidates: list[Candidate] = []
    for row in rows:
        code = (row.get("code") or row.get("source_symbol") or "").strip()
        code = code[-6:] if len(code) >= 6 else code
        if not code or code in existing_codes:
            continue
        name = (row.get("name") or code).strip()
        pct = as_float(row.get("pct_chg"))
        amount = as_float(row.get("amount")) or 0.0
        if pct is None or pct < LOW_POSITION_MIN_PCT or pct > LOW_POSITION_MAX_PCT:
            continue
        if amount < MIN_SUPPLEMENTAL_AMOUNT:
            continue
        candidate = Candidate(
            code=code,
            name=name,
            latest=as_float(row.get("latest")),
            pct_chg=pct,
            prev_close=as_float(row.get("prev_close")),
            open_price=as_float(row.get("open")),
            high=as_float(row.get("high")),
            low=as_float(row.get("low")),
            amount=amount,
            seed_score=52.0 + min(12.0, pct * 1.6) + min(8.0, amount / 10_000_000_000),
            seed_rank=start_rank + len(candidates),
            industry_l1=str(row.get("sw_l1") or row.get("industry_l1") or row.get("申万一级") or ""),
            industry_l2=str(row.get("sw_l2") or row.get("industry_l2") or row.get("申万二级") or ""),
            industry_l3=str(row.get("sw_l3") or row.get("industry_l3") or row.get("申万三级") or ""),
            concepts=str(row.get("concepts") or row.get("概念") or row.get("hot_concepts") or ""),
            candidate_source="low_position_support",
            execution_action="unknown",
            execution_score=None,
            execution_flags="",
            risk_action="unknown",
        )
        sector, _, direction = theme_for(candidate)
        if direction == "待识别方向" or sector == "未细分强势种子":
            continue
        candidates.append(candidate)
    candidates.sort(
        key=lambda item: (
            item.amount or 0.0,
            -(item.pct_chg or 0.0),
            item.seed_score,
        ),
        reverse=True,
    )
    return candidates[:limit]


def load_csv_rows(csv_path: Path) -> list[dict[str, Any]]:
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def is_blocked(candidate: Candidate, execution: dict[str, Any], risk: dict[str, Any]) -> bool:
    return candidate.code in set(execution.get("block_codes") or []) or candidate.code in set(
        risk.get("block_codes") or []
    ) or candidate.code in set(risk.get("incomplete_codes") or [])


POLICY_THEME_ALIASES = {
    "半导体": ["半导体", "芯片", "存储", "封测", "电子", "MCU", "集成电路"],
    "光通信": ["光通信", "光模块", "光电", "光纤", "光缆", "CPO", "高速互联", "算力"],
    "新材料": ["新材料", "材料", "稀有金属", "钨", "稀土", "锂电", "锆"],
    "黄金资源": ["黄金", "资源", "矿业", "贵金属", "小金属", "有色"],
    "消费电子": ["消费电子", "显示", "面板", "终端"],
    "机器人": ["机器人", "减速器", "伺服", "自动化"],
    "AI": ["AI", "人工智能", "算力", "服务器", "数据中心"],
}

NEGATIVE_NEWS_WORDS = [
    "解禁",
    "减持",
    "辞职",
    "停产",
    "问询",
    "监管",
    "处罚",
    "亏损",
    "下修",
    "质押",
    "诉讼",
    "立案",
    "调查",
    "退市",
    "ST",
]

POSITIVE_NEWS_WORDS = [
    "涨停",
    "净流入",
    "加仓",
    "突破",
    "恢复生产",
    "政策",
    "订单",
    "中标",
    "算力",
    "芯片",
    "光通信",
    "稀土",
    "黄金",
    "主力资金",
]


NEWS_CATEGORY_KEYWORDS = {
    "policy_level": [
        "国务院",
        "发改委",
        "工信部",
        "财政部",
        "国家政策",
        "产业政策",
        "产业规划",
        "监管口径",
        "行动方案",
        "实施方案",
    ],
    "industry_level": [
        "涨价",
        "供需",
        "订单周期",
        "出口限制",
        "海外映射",
        "景气",
        "库存",
        "产能周期",
        "招标",
        "需求增长",
    ],
    "company_positive": [
        "订单",
        "中标",
        "合同",
        "业绩预增",
        "利润增长",
        "产能",
        "投产",
        "客户认证",
        "回购",
        "恢复生产",
    ],
    "company_negative": [
        "解禁",
        "减持",
        "辞职",
        "离职",
        "停产",
        "问询",
        "监管",
        "处罚",
        "亏损",
        "下修",
        "质押",
        "冻结",
        "诉讼",
        "立案",
        "调查",
        "退市",
        "ST",
    ],
    "sentiment_level": [
        "龙虎榜",
        "涨停",
        "连板",
        "主力资金",
        "净流入",
        "加仓",
        "概念爆发",
        "题材爆发",
        "人气",
        "杠杆资金",
    ],
}


def classify_news_texts(texts: list[str]) -> dict[str, Any]:
    categories: dict[str, dict[str, Any]] = {}
    for category, keywords in NEWS_CATEGORY_KEYWORDS.items():
        matched_words: set[str] = set()
        matched_headlines: list[str] = []
        for text in texts:
            hit_words = [word for word in keywords if word.lower() in text.lower()]
            if not hit_words:
                continue
            matched_words.update(hit_words)
            if len(matched_headlines) < 4:
                matched_headlines.append(text)
        categories[category] = {
            "count": len(matched_headlines),
            "matched_words": sorted(matched_words),
            "headlines": matched_headlines,
        }
    return categories


def flatten_policy_headlines(policy_news: dict[str, Any] | None) -> list[str]:
    policy_news = policy_news or {}
    texts: list[str] = []
    for item in policy_news.get("catalyst_themes") or []:
        texts.extend(str(text) for text in (item.get("headlines") or []) if text)
    for item in (policy_news.get("stock_news") or {}).values():
        texts.extend(str(text) for text in (item.get("headlines") or []) if text)
    return texts


def policy_news_classification(policy_news: dict[str, Any] | None) -> dict[str, Any]:
    policy_news = policy_news or {}
    existing = policy_news.get("classification_summary")
    if isinstance(existing, dict) and existing:
        return existing
    texts = flatten_policy_headlines(policy_news)
    categories = classify_news_texts(texts)
    return {
        "source": "derived_from_policy_news_headlines",
        "categories": categories,
        "notes": [
            "政策/行业级可有限加分，公司级负面优先扣分，情绪级只能小幅加分。",
        ],
    }


def policy_source_status(policy_news: dict[str, Any] | None) -> str:
    return str((policy_news or {}).get("source_status") or "missing")


def news_evidence_quality(policy_news: dict[str, Any] | None) -> dict[str, Any]:
    policy_news = policy_news or {}
    sources = policy_news.get("sources") or {}
    ok_sources = [name for name, item in sources.items() if isinstance(item, dict) and item.get("ok")]
    failed_sources = [name for name, item in sources.items() if isinstance(item, dict) and not item.get("ok")]
    generated_at = str(policy_news.get("generated_at") or "")
    status = policy_source_status(policy_news)
    score = 70
    if status == "ok":
        score += 10
    elif status == "partial":
        score -= 15
    elif status in ("missing", "failed"):
        score -= 35
    if not generated_at:
        score -= 10
    if not ok_sources:
        score -= 20
    return {
        "source_status": status,
        "ok_sources": ok_sources,
        "failed_sources": failed_sources,
        "generated_at": generated_at,
        "has_timestamp": bool(generated_at),
        "has_company_announcement_source": bool((policy_news.get("company_announcements") or [])),
        "credibility_score": max(0, min(100, score)),
        "scoring_rule": "政策/行业有限加分；公司公告优先；新闻源 partial、无时间戳或重复转载时限制加分。",
    }


def policy_theme_match(sector: str, direction: str, policy_news: dict[str, Any] | None) -> dict[str, Any]:
    policy_news = policy_news or {}
    haystack = f"{sector} {direction}".lower()
    best: dict[str, Any] | None = None
    for item in policy_news.get("catalyst_themes") or []:
        theme = str(item.get("theme") or "")
        keywords = list(item.get("keywords") or [])
        aliases = POLICY_THEME_ALIASES.get(theme, [])
        words = [theme, *keywords, *aliases]
        matched = any(str(word).lower() in haystack for word in words if word)
        if not matched:
            continue
        if best is None or int(item.get("hit_count") or 0) > int(best.get("hit_count") or 0):
            best = item
    if not best:
        return {"matched": False, "bonus": 0, "summary": "未命中明确新闻/政策主题。"}
    hit_count = int(best.get("hit_count") or 0)
    bonus = 4 if hit_count >= 5 else 2 if hit_count >= 2 else 1
    if policy_source_status(policy_news) != "ok":
        bonus = min(bonus, 3)
    return {
        "matched": True,
        "theme": best.get("theme"),
        "hit_count": hit_count,
        "bonus": bonus,
        "summary": f"{best.get('theme')}主题新闻命中 {hit_count} 条。",
    }


def candidate_news_signal(candidate: Candidate, policy_news: dict[str, Any] | None) -> dict[str, Any]:
    policy_news = policy_news or {}
    stock_news = (policy_news.get("stock_news") or {}).get(candidate.code) or {}
    headlines = [str(text) for text in (stock_news.get("headlines") or []) if text]
    classified = classify_news_texts(headlines)
    negative_hits = sorted(
        set(classified["company_negative"]["matched_words"])
        | {word for word in NEGATIVE_NEWS_WORDS if any(word in headline for headline in headlines)}
    )
    substance_hits = sorted(
        set(classified["policy_level"]["matched_words"])
        | set(classified["industry_level"]["matched_words"])
        | set(classified["company_positive"]["matched_words"])
    )
    sentiment_hits = sorted(set(classified["sentiment_level"]["matched_words"]))
    positive_hits = sorted(
        set(substance_hits)
        | set(sentiment_hits)
        | {word for word in POSITIVE_NEWS_WORDS if any(word in headline for headline in headlines)}
    )
    sentiment_only = bool(sentiment_hits) and not substance_hits and not negative_hits
    penalty = min(14, 6 + 2 * (len(negative_hits) - 1)) if negative_hits else 0
    bonus = min(4, len(substance_hits) + (1 if sentiment_hits else 0))
    if sentiment_only:
        bonus = min(bonus, 1)
    if policy_source_status(policy_news) != "ok":
        bonus = min(bonus, 2)
    parts: list[str] = []
    if substance_hits:
        parts.append("实质词：" + "、".join(substance_hits[:4]))
    if sentiment_hits:
        parts.append("情绪词：" + "、".join(sentiment_hits[:4]))
    if negative_hits:
        parts.append("风险词：" + "、".join(negative_hits[:4]))
    if not parts:
        parts.append("个股新闻未见明确正负面信号。")
    return {
        "headlines": headlines[:3],
        "positive_hits": positive_hits,
        "substance_hits": substance_hits,
        "sentiment_hits": sentiment_hits,
        "negative_hits": negative_hits,
        "sentiment_only": sentiment_only,
        "classified": classified,
        "bonus": bonus,
        "penalty": penalty,
        "summary": "；".join(parts),
    }


def policy_news_adjustment(
    candidate: Candidate,
    sector: str,
    direction: str,
    policy_news: dict[str, Any] | None,
) -> dict[str, Any]:
    theme = policy_theme_match(sector, direction, policy_news)
    stock = candidate_news_signal(candidate, policy_news)
    classification = policy_news_classification(policy_news)
    evidence_quality = news_evidence_quality(policy_news)
    categories = classification.get("categories") or {}
    policy_hits = int((categories.get("policy_level") or {}).get("count") or 0)
    industry_hits = int((categories.get("industry_level") or {}).get("count") or 0)
    sentiment_hits = int((categories.get("sentiment_level") or {}).get("count") or 0)
    classification_bonus = min(5, policy_hits * 2 + industry_hits)
    sentiment_bonus = min(1, sentiment_hits)
    net = (
        int(theme.get("bonus") or 0)
        + int(stock.get("bonus") or 0)
        + classification_bonus
        + sentiment_bonus
        - int(stock.get("penalty") or 0)
    )
    if policy_source_status(policy_news) == "missing":
        note = "新闻/政策数据缺失，不做加分。"
        net = min(net, 0)
    elif policy_source_status(policy_news) != "ok":
        note = "新闻源为 partial，正向只做有限加分，负面事件照常降级。"
        net = min(net, 4)
    else:
        note = "新闻/政策源可用。"
    if int(evidence_quality.get("credibility_score") or 0) < 60:
        net = min(net, 2)
        note += " 新闻可信度不足，进一步压低正向加分。"
    return {
        "net": net,
        "theme": theme,
        "stock": stock,
        "classification": classification,
        "evidence_quality": evidence_quality,
        "classification_bonus": classification_bonus,
        "sentiment_bonus": sentiment_bonus,
        "note": note,
    }


def pct_from_prices(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return (numerator / denominator - 1.0) * 100.0


def is_chasing_candidate(candidate: Candidate) -> bool:
    flags = candidate.execution_flags or ""
    return (
        "near_or_at_limit_up" in flags
        or "large_open_gap" in flags
        or "extended_from_intraday_low" in flags
        or (candidate.pct_chg or 0.0) >= 8.8
    )


def contradiction_review(
    candidate: Candidate,
    stock_news: dict[str, Any],
    sector_profile: dict[str, Any],
) -> dict[str, Any]:
    penalty = 0
    notes: list[str] = []
    flags = candidate.execution_flags or ""
    high_pct = pct_from_prices(candidate.high, candidate.prev_close)
    open_gap = pct_from_prices(candidate.open_price, candidate.prev_close)
    pct = candidate.pct_chg or 0.0
    core_score = float(sector_profile.get("core_score") or 50.0)
    amount_share = float(sector_profile.get("amount_share") or 0.0)
    amount_rank = int(sector_profile.get("amount_rank") or 99)

    if high_pct is not None and high_pct >= 9.8 and pct < 9.5:
        penalty += 8
        notes.append("触及涨停附近但未封住")
    if "near_or_at_limit_up" in flags and candidate.execution_action != "clear":
        penalty += 5
        notes.append("接近涨停但承接无法由执行质量验证")
    if open_gap is not None and open_gap >= 4.0:
        penalty += 5
        notes.append("高开过多")
    if "large_open_gap" in flags:
        penalty += 5
        notes.append("执行标记为大幅高开")
    if "extended_from_intraday_low" in flags:
        penalty += 5
        notes.append("盘中拉离低点过远")
    if "large_intraday_amplitude" in flags:
        penalty += 5
        notes.append("盘中振幅过大")
    if core_score < 55:
        penalty += 7
        notes.append("板块强但个股核心性不足")
    if amount_rank > 2 and amount_share < 0.16:
        penalty += 5
        notes.append("同题材资金更集中在龙头")
    if stock_news.get("sentiment_only"):
        penalty += 6
        notes.append("个股新闻只有情绪词，缺少订单/政策/产业实质")
    if stock_news.get("negative_hits"):
        penalty += 4
        notes.append("公司级负面新闻优先扣分")
    return {
        "score": max(0, min(35, penalty)),
        "notes": notes,
        "high_pct": high_pct,
        "open_gap_pct": open_gap,
    }


def reason_tags_from_notes(
    candidate: Candidate,
    risk_notes: list[str],
    contradictions: list[str],
    stock_news: dict[str, Any],
) -> list[str]:
    text = " ".join([candidate.execution_flags or "", *risk_notes, *contradictions])
    tags: set[str] = set()
    if "接近涨停" in text or "触及涨停" in text or "near_or_at_limit_up" in text:
        tags.add("near_or_at_limit_up")
    if "振幅过大" in text or "盘中拉" in text or "extended_from_intraday_low" in text or "large_intraday_amplitude" in text:
        tags.add("large_intraday_amplitude")
    if "高开" in text or "large_open_gap" in text:
        tags.add("large_open_gap")
    if "核心性不足" in text or "资金更集中" in text or "非核心" in text:
        tags.add("weak_sector_core")
    if stock_news.get("sentiment_only"):
        tags.add("sentiment_only_news")
    if candidate.execution_action == "unknown":
        tags.add("execution_unknown")
    elif candidate.execution_action != "clear":
        tags.add("execution_warning")
    if candidate.candidate_source == "low_position_support":
        tags.add("low_position_support")
    if stock_news.get("negative_hits"):
        tags.add("company_negative_news")
    return sorted(tags)



def candidate_score_breakdown(
    candidate: Candidate,
    group: str,
    policy_news: dict[str, Any] | None = None,
    sector_context: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    sector, _, direction = theme_for(candidate)
    news_adjust = policy_news_adjustment(candidate, sector, direction, policy_news)
    theme = news_adjust.get("theme") or {}
    stock = news_adjust.get("stock") or {}
    sector_row = (sector_context or {}).get(direction, {})
    sector_profile = (sector_row.get("by_code") or {}).get(candidate.code, {})
    classification = news_adjust.get("classification") or {}
    evidence_quality = news_adjust.get("evidence_quality") or {}
    categories = classification.get("categories") or {}

    pct = candidate.pct_chg or 0.0
    amount = candidate.amount or 0.0
    seed = candidate.seed_score or 0.0

    momentum_score = 28 + min(22, max(0, int((seed - 55) * 1.65)))
    if pct >= 9.0:
        momentum_score += 5
    elif pct >= 8.0:
        momentum_score += 3
    elif pct >= 6.5:
        momentum_score += 1
    momentum_score = max(20, min(55, momentum_score))

    liquidity_score = 6
    if amount >= 20_000_000_000:
        liquidity_score = 15
    elif amount >= 10_000_000_000:
        liquidity_score = 13
    elif amount >= 5_000_000_000:
        liquidity_score = 11
    elif amount >= 2_000_000_000:
        liquidity_score = 9

    sector_score = 8
    if sector_row:
        count = int(sector_row.get("count") or 0)
        avg_pct = float(sector_row.get("avg_pct") or 0.0)
        sector_amount = float(sector_row.get("amount") or 0.0)
        sector_score += min(5, count)
        if avg_pct >= 8.0:
            sector_score += 5
        elif avg_pct >= 6.5:
            sector_score += 3
        elif avg_pct >= 4.5:
            sector_score += 1
        if sector_amount >= 20_000_000_000:
            sector_score += 3
        elif sector_amount >= 8_000_000_000:
            sector_score += 2
        core_score = float(sector_profile.get("core_score") or 50.0)
        if core_score >= 78:
            sector_score += 4
        elif core_score >= 65:
            sector_score += 2
        elif core_score < 50:
            sector_score -= 4
    sector_score = max(6, min(20, sector_score))

    policy_count = int((categories.get("policy_level") or {}).get("count") or 0)
    industry_count = int((categories.get("industry_level") or {}).get("count") or 0)
    sentiment_count = int((categories.get("sentiment_level") or {}).get("count") or 0)
    policy_score = (
        4
        + max(0, int(theme.get("bonus") or 0))
        + max(0, int(stock.get("bonus") or 0))
        + min(4, policy_count * 2 + industry_count)
        + min(1, sentiment_count)
    )
    if (theme.get("matched") or False) and int(theme.get("hit_count") or 0) >= 5:
        policy_score += 3
    if stock.get("sentiment_only") and not theme.get("matched"):
        policy_score = min(policy_score, 7)
    if policy_source_status(policy_news) == "ok":
        policy_score += 2
    elif policy_source_status(policy_news) == "partial":
        policy_score = min(policy_score, 11)
    else:
        policy_score = min(policy_score, 6)
    if int(evidence_quality.get("credibility_score") or 0) < 60:
        policy_score = min(policy_score, 7)

    # Global giant catalyst direct maximum bonus
    catalyst_info = (policy_news or {}).get("global_macro_catalyst") or {}
    if catalyst_info.get("triggered") and catalyst_info.get("sector") == direction:
        policy_score = 20

    policy_score = max(0, min(20, policy_score))

    driver = momentum_score + liquidity_score + sector_score + policy_score
    driver = max(35, min(100, driver))

    execution_score = 100
    penalty = 0
    risk_notes: list[str] = []
    risk_tiers = {"block": [], "downgrade": [], "notice": []}
    if candidate.execution_action != "clear":
        execution_score -= 18
        penalty += 8
        risk_notes.append(f"执行质量 {candidate.execution_action}")
        risk_tiers["downgrade"].append(f"执行质量 {candidate.execution_action}")
    flags = candidate.execution_flags or ""
    if "near_or_at_limit_up" in flags:
        execution_score -= 14
        penalty += 5
        risk_notes.append("接近涨停/可执行性下降")
        risk_tiers["downgrade"].append("接近涨停")
    if "extended_from_intraday_low" in flags:
        execution_score -= 10
        penalty += 4
        risk_notes.append("盘中拉伸过大")
        risk_tiers["downgrade"].append("盘中拉伸过大")
    if "large_intraday_amplitude" in flags:
        execution_score -= 10
        penalty += 4
        risk_notes.append("振幅过大")
        risk_tiers["downgrade"].append("振幅过大")
    if "thin_liquidity" in flags:
        execution_score -= 25
        penalty += 8
        risk_notes.append("流动性不足")
        risk_tiers["block"].append("流动性不足")
    stock_penalty = int(stock.get("penalty") or 0)
    if stock_penalty:
        penalty += stock_penalty
        risk_notes.append("个股新闻/事件风险")
        risk_tiers["downgrade"].append("个股新闻/事件风险")
    contradiction = contradiction_review(candidate, stock, sector_profile)
    if contradiction["score"]:
        penalty += int(contradiction["score"])
        for note in contradiction["notes"]:
            risk_notes.append("反证：" + note)
            risk_tiers["downgrade"].append(note)
    if candidate.risk_action not in ("clear", "unknown", ""):
        execution_score -= 18
        penalty += 8
        risk_notes.append(f"公告风险 {candidate.risk_action}")
        risk_tiers["block"].append(f"公告风险 {candidate.risk_action}")
    if group == "research":
        penalty += 2
    execution_score = max(0, min(100, execution_score))
    penalty = max(0, min(45, penalty))
    reason_tags = reason_tags_from_notes(candidate, risk_notes, contradiction["notes"], stock)

    source_status = policy_source_status(policy_news)
    review_confidence = 82
    if source_status == "partial":
        review_confidence -= 10
    elif source_status in ("missing", "failed"):
        review_confidence -= 18
    if candidate.execution_action != "clear":
        review_confidence -= 8
    if risk_tiers["block"]:
        review_confidence -= 18
    elif risk_tiers["downgrade"]:
        review_confidence -= 8
    review_confidence = max(35, min(95, review_confidence))

    final = int(round(driver * 0.72 + execution_score * 0.18 + review_confidence * 0.10 - penalty))
    final = max(45, min(95, final))
    if risk_tiers["block"]:
        bucket = "blocked"
    elif (
        driver >= MAIN_DRIVER_MIN
        and penalty <= MAIN_RISK_MAX
        and execution_score >= MAIN_EXECUTION_MIN
        and candidate.execution_action == "clear"
    ):
        bucket = "main_candidate"
    elif driver >= MAIN_DRIVER_MIN:
        bucket = "high_driver_high_risk"
    elif execution_score >= 80 and driver < MAIN_DRIVER_MIN:
        bucket = "clean_but_weak"
    else:
        bucket = "weak_driver"
    return {
        "driver_score": driver,
        "momentum_score": momentum_score,
        "sector_score": sector_score,
        "liquidity_score": liquidity_score,
        "policy_score": policy_score,
        "execution_score": execution_score,
        "risk_penalty": penalty,
        "review_confidence": review_confidence,
        "score": final,
        "bucket": bucket,
        "risk_notes": risk_notes,
        "risk_tiers": risk_tiers,
        "news_adjustment": news_adjust,
        "contradiction_score": contradiction["score"],
        "contradictions": contradiction["notes"],
        "reason_tags": reason_tags,
        "sector_core_score": sector_profile.get("core_score", 50),
        "sector_core_profile": sector_profile,
    }

def candidate_score(
    candidate: Candidate,
    group: str,
    policy_news: dict[str, Any] | None = None,
    sector_context: dict[str, dict[str, Any]] | None = None,
) -> int:
    return int(candidate_score_breakdown(candidate, group, policy_news, sector_context)["score"])



def rank_candidates(
    candidates: list[Candidate],
    group: str,
    policy_news: dict[str, Any] | None = None,
    sector_context: dict[str, dict[str, Any]] | None = None,
) -> list[Candidate]:
    """Rank by the same final score shown in the report cards."""
    return sorted(
        candidates,
        key=lambda item: (
            candidate_score(item, group, policy_news, sector_context),
            item.seed_score,
            item.pct_chg if item.pct_chg is not None else -999.0,
            item.amount if item.amount is not None else 0.0,
        ),
        reverse=True,
    )

def theme_for(candidate: Candidate) -> tuple[str, str, str]:
    industry_text = " / ".join(
        text for text in [candidate.industry_l1, candidate.industry_l2, candidate.industry_l3] if text
    )
    concept_text = candidate.concepts or ""
    evidence_text = f"{industry_text} {concept_text} {candidate.name}"
    for rule in load_industry_theme_rules():
        keywords = [str(word) for word in (rule.get("keywords") or [])]
        if keywords and any(word and word in evidence_text for word in keywords):
            return (
                str(rule.get("sector") or "未细分强势种子"),
                str(rule.get("scarce_layer") or rule.get("sector") or "待识别产业链位置"),
                str(rule.get("direction") or "待识别方向"),
            )
    if candidate.code in THEME_HINTS:
        return THEME_HINTS[candidate.code]
    name = candidate.name
    if "证券" in name:
        return ("证券 / 非银金融", "券商风险偏好弹性", "非银金融与券商")
    if "保险" in name or "人寿" in name:
        return ("保险 / 非银金融", "保险风险偏好弹性", "非银金融与保险")
    if "锂" in name or "电池" in name:
        return ("锂电 / 新能源材料", "锂电材料供给", "锂电材料")
    if "铝" in name or "钼" in name or "锡" in name or "金" in name:
        return ("有色资源", "有色金属资源供给", "黄金资源与有色金属")
    if "化学" in name or "化工" in name:
        return ("化工新材料", "化工材料供给", "化工新材料")
    if "PCB" in name or "电路" in name:
        return ("PCB / 电子制造", "PCB制造与电子链条", "PCB与电子制造")
    if "光" in name:
        return ("光电 / 光通信", "光电硬件链条", "光电与通信硬件")
    if "钨" in name or "材" in name or "资源" in name:
        return ("新材料 / 资源品", "高端材料供给", "新材料与资源品")
    if "芯" in name or "电" in name:
        return ("半导体 / 电子", "电子硬件链条", "电子与半导体")
    return ("未细分强势种子", "待识别产业链位置", "待识别方向")

def candidate_card(candidate: Candidate, rank: int, group: str, policy_news: dict[str, Any] | None = None, sector_context: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    sector, scarce_layer, direction = theme_for(candidate)
    score_info = dict(candidate_score_breakdown(candidate, group, policy_news, sector_context))
    if group == "premarket_inference" and score_info.get("bucket") == "main_candidate":
        score_info["bucket"] = "backup_candidate"
    news_adjust = score_info["news_adjustment"]
    theme_news = news_adjust["theme"]
    stock_news = news_adjust["stock"]
    core_profile = score_info.get("sector_core_profile") or {}
    core_notes = core_profile.get("notes") or []
    core_line = (
        f"板块核心性 {score_info.get('sector_core_score', 'NA')} 分"
        + (f"（{'; '.join(str(note) for note in core_notes[:3])}）" if core_notes else "")
    )
    contradiction_line = (
        "反证：" + "、".join(str(note) for note in (score_info.get("contradictions") or [])[:4])
        if score_info.get("contradictions")
        else "反证：暂无硬反证。"
    )
    warning = candidate.execution_action != "clear"
    risk_text = (
        f"执行质量标记为 {candidate.execution_action}"
        + (f"，风险标记 {candidate.execution_flags}" if candidate.execution_flags else "")
        if warning
        else "执行质量 clear，公告/风险检查未见阻断。"
    )
    role = {
        "tradable": "短线纸面观察",
        "premarket_inference": "盘前/盘中推演",
        "research": "中期研究线索",
    }[group]
    if group == "research":
        core = (
            f"量价初筛排名第 {candidate.seed_rank}，涨幅 {fmt_pct(candidate.pct_chg)}，成交额约 {fmt_amount(candidate.amount)}；"
            f"来源 {candidate.candidate_source}；{core_line}；"
            "更适合做产业链方向跟踪，不放入短线主榜。"
        )
    elif group == "premarket_inference":
        core = (
            f"量价初筛排名第 {candidate.seed_rank}，未进入主榜前5但未被阻断；"
            f"涨幅 {fmt_pct(candidate.pct_chg)}，成交额约 {fmt_amount(candidate.amount)}；"
            f"来源 {candidate.candidate_source}；{core_line}，适合作为备选推演。"
        )
    else:
        core = (
            f"量价初筛排名第 {candidate.seed_rank}，涨幅 {fmt_pct(candidate.pct_chg)}，成交额约 {fmt_amount(candidate.amount)}；"
            f"来源 {candidate.candidate_source}；{core_line}；{risk_text}"
        )
    news_line = (
        f"新闻/政策：{theme_news.get('summary')} {stock_news.get('summary')} {news_adjust.get('note')}"
        if policy_news
        else "新闻/政策：未接入当日新闻数据。"
    )
    failure_extra = ""
    if stock_news.get("negative_hits"):
        failure_extra = " 个股新闻含" + "、".join(stock_news["negative_hits"][:4]) + "等风险词，需降级或退出纸面主榜。"
    return {
        "rank": rank,
        "name": candidate.name,
        "code": candidate.code,
        "sector": sector,
        "industry_l1": candidate.industry_l1,
        "industry_l2": candidate.industry_l2,
        "industry_l3": candidate.industry_l3,
        "concepts": candidate.concepts,
        "candidate_source": candidate.candidate_source,
        "group": group,
        "score": score_info["score"],
        "driver_score": score_info["driver_score"],
        "momentum_score": score_info["momentum_score"],
        "sector_score": score_info["sector_score"],
        "liquidity_score": score_info["liquidity_score"],
        "policy_score": score_info["policy_score"],
        "execution_score": score_info["execution_score"],
        "risk_penalty": score_info["risk_penalty"],
        "contradiction_score": score_info["contradiction_score"],
        "contradictions": score_info["contradictions"],
        "sector_core_score": score_info["sector_core_score"],
        "sector_core_profile": score_info["sector_core_profile"],
        "review_confidence": score_info["review_confidence"],
        "selection_bucket": score_info["bucket"],
        "risk_notes": score_info["risk_notes"],
        "risk_tiers": score_info["risk_tiers"],
        "reason_tags": score_info["reason_tags"],
        "evidence": "Medium" if candidate.execution_action == "clear" and not stock_news.get("negative_hits") else "Weak",
        "scarce_layer": scarce_layer,
        "core_logic": f"{core} {news_line}",
        "catalyst": f"{direction}早盘强度进入观察范围；{news_line}",
        "capital": f"成交额约 {fmt_amount(candidate.amount)}；{risk_text}",
        "technical": f"最新涨幅 {fmt_pct(candidate.pct_chg)}，观察是否强于所属方向且不出现放量冲高回落。{contradiction_line}",
        "entry_plan": f"{role}：只做纸面验证，不构成真实买卖指令。",
        "support": "早盘承接区 / 后续趋势平台",
        "target": "验证 1-3 日相对强弱" if group != "research" else "研究跟踪",
        "elasticity": "高" if (candidate.pct_chg or 0) >= 8 else "中等",
        "failure": "若板块退潮、个股放量回落、跌回早盘启动区，或后续出现公告/执行风险，则逻辑失效。" + failure_extra,
    }


def top_directions(items: list[Candidate]) -> list[dict[str, str]]:
    seen: dict[str, list[Candidate]] = {}
    for item in items:
        _, _, direction = theme_for(item)
        if direction == "待识别方向":
            continue
        seen.setdefault(direction, []).append(item)
    ordered = sorted(seen.items(), key=lambda kv: (len(kv[1]), max(i.seed_score for i in kv[1])), reverse=True)
    return [
        {
            "title": title,
            "summary": "、".join(i.name for i in group[:3]) + "进入候选池，后续重点看成交持续性和回落承接。",
        }
        for title, group in ordered[:3]
    ]



def load_historical_presence(root: Path, date: str, lookback: int = 5) -> dict[str, int]:
    daily_dir = root / "reports" / "daily"
    if not daily_dir.exists():
        return {}
    prior_files: list[Path] = []
    for path in sorted(daily_dir.glob("*/pre_market_top5.json")):
        day = path.parent.name
        if len(day) == 8 and day < date:
            prior_files.append(path)
    presence: dict[str, int] = {}
    for path in prior_files[-lookback:]:
        report = read_json(path, {}) or {}
        for section in ["tradable_candidates", "premarket_inference_candidates", "research_leads"]:
            for item in report.get(section) or []:
                code = str(item.get("code") or "")
                if code:
                    presence[code] = presence.get(code, 0) + 1
    return presence


def build_sector_context(
    candidates: list[Candidate],
    historical_presence: dict[str, int] | None = None,
) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[Candidate]] = {}
    historical_presence = historical_presence or {}
    for item in candidates:
        _, _, direction = theme_for(item)
        groups.setdefault(direction, []).append(item)
    context: dict[str, dict[str, Any]] = {}
    for direction, items in groups.items():
        pct_values = [item.pct_chg for item in items if item.pct_chg is not None]
        avg_pct = sum(pct_values) / len(pct_values) if pct_values else 0.0
        total_amount = sum(item.amount or 0.0 for item in items)
        by_amount = sorted(items, key=lambda item: item.amount or 0.0, reverse=True)
        by_pct = sorted(items, key=lambda item: item.pct_chg if item.pct_chg is not None else -999.0, reverse=True)
        by_seed = sorted(items, key=lambda item: item.seed_score, reverse=True)
        amount_rank = {item.code: rank for rank, item in enumerate(by_amount, 1)}
        pct_rank = {item.code: rank for rank, item in enumerate(by_pct, 1)}
        seed_rank = {item.code: rank for rank, item in enumerate(by_seed, 1)}
        by_code: dict[str, dict[str, Any]] = {}
        for item in items:
            share = ((item.amount or 0.0) / total_amount) if total_amount else 0.0
            pct_vs_avg = (item.pct_chg or 0.0) - avg_pct
            core_score = 45
            notes: list[str] = []
            if amount_rank[item.code] == 1:
                core_score += 18
                notes.append("同板块成交额第一")
            elif amount_rank[item.code] <= 3:
                core_score += 10
                notes.append("同板块成交额前三")
            elif len(items) >= 3:
                core_score -= 8
                notes.append("成交额不是板块前排")
            if pct_rank[item.code] == 1:
                core_score += 14
                notes.append("同板块涨幅第一")
            elif pct_rank[item.code] <= 3:
                core_score += 7
                notes.append("同板块涨幅前三")
            elif len(items) >= 3:
                core_score -= 6
                notes.append("涨幅落后于板块前排")
            if seed_rank[item.code] == 1:
                core_score += 12
                notes.append("初筛强度为板块首位")
            elif seed_rank[item.code] <= 3:
                core_score += 6
                notes.append("初筛强度为板块前三")
            if pct_vs_avg >= 1.0:
                core_score += 8
                notes.append("强于板块平均涨幅")
            elif pct_vs_avg < -0.8:
                core_score -= 8
                notes.append("弱于板块平均涨幅")
            if share >= 0.35:
                core_score += 10
                notes.append("资金集中度较高")
            elif len(items) >= 3 and share < 0.16 and amount_rank[item.code] > 2:
                core_score -= 10
                notes.append("同题材资金更集中在前排")
            if historical_presence.get(item.code, 0) >= 2:
                core_score += 8
                notes.append("近几日连续入池")
            by_code[item.code] = {
                "amount_rank": amount_rank[item.code],
                "pct_rank": pct_rank[item.code],
                "seed_rank": seed_rank[item.code],
                "pct_vs_avg": pct_vs_avg,
                "amount_share": share,
                "historical_presence": historical_presence.get(item.code, 0),
                "core_score": max(0, min(100, core_score)),
                "notes": notes,
            }
        context[direction] = {
            "count": len(items),
            "avg_pct": avg_pct,
            "amount": total_amount,
            "top_seed_score": max((item.seed_score for item in items), default=0.0),
            "by_code": by_code,
        }
    return context


def ranked_directions_from_context(context: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for direction, row in context.items():
        if direction == "待识别方向":
            continue
        count = int(row.get("count") or 0)
        avg_pct = float(row.get("avg_pct") or 0.0)
        amount = float(row.get("amount") or 0.0)
        top_seed = float(row.get("top_seed_score") or 0.0)
        strength = avg_pct * 5.0 + min(20.0, amount / 10_000_000_000) + min(12.0, count * 1.5) + max(0.0, top_seed - 55.0)
        rows.append(
            {
                "direction": direction,
                "count": count,
                "avg_pct": avg_pct,
                "amount": amount,
                "top_seed_score": top_seed,
                "sector_strength_score": round(strength, 2),
            }
        )
    rows.sort(
        key=lambda item: (
            item["sector_strength_score"],
            item["amount"],
            item["count"],
        ),
        reverse=True,
    )
    return rows


def priority_directions(context: dict[str, dict[str, Any]], limit: int = TOP_DIRECTION_LIMIT) -> set[str]:
    ranked = ranked_directions_from_context(context)
    return {str(item["direction"]) for item in ranked[:limit]}


def main_candidate_limit(gate: dict[str, Any], policy_news: dict[str, Any]) -> int:
    score = as_float(gate.get("score")) or 0.0
    regime = str(gate.get("regime") or "")
    if score < MAIN_GATE_MIN_SCORE or "空仓" in regime or "防守" in regime:
        return 0
    status = policy_source_status(policy_news)
    if status in ("partial", "failed", "missing"):
        return 1
    if "进攻" in regime or score >= 70:
        return 3
    if "试探" in regime or score >= 55:
        return 2
    return 1


def build_market_microstructure(
    snapshot_rows: list[dict[str, Any]],
    risk: dict[str, Any],
    candidates: list[Candidate],
) -> dict[str, Any]:
    groups: dict[str, list[Candidate]] = {}
    for item in candidates:
        _, _, direction = theme_for(item)
        groups.setdefault(direction, []).append(item)

    sector_rows: list[dict[str, Any]] = []
    for direction, items in groups.items():
        avg_pct_values = [item.pct_chg for item in items if item.pct_chg is not None]
        avg_pct = sum(avg_pct_values) / len(avg_pct_values) if avg_pct_values else None
        amount = sum(item.amount or 0.0 for item in items)
        up_count = sum(1 for item in items if (item.pct_chg or 0.0) > 0)
        sector_rows.append(
            {
                "name": direction,
                "count": len(items),
                "up_count": up_count,
                "avg_pct": avg_pct,
                "amount": amount,
                "top_names": [item.name for item in sorted(items, key=lambda row: row.seed_score, reverse=True)[:3]],
            }
        )
    sector_rows.sort(
        key=lambda row: (
            row["avg_pct"] if row["avg_pct"] is not None else -999.0,
            row["amount"],
            row["count"],
        ),
        reverse=True,
    )

    touched = 0
    sealed = 0
    failed = 0
    for row in snapshot_rows:
        prev_close = as_float(row.get("prev_close"))
        high = as_float(row.get("high"))
        pct = as_float(row.get("pct_chg"))
        if not prev_close or not high or pct is None:
            continue
        high_pct = (high / prev_close - 1.0) * 100.0
        if high_pct >= 9.8:
            touched += 1
            if pct >= 9.8:
                sealed += 1
            else:
                failed += 1
    failed_rate = (failed / touched * 100.0) if touched else None

    by_code = risk.get("by_code") or {}
    clear = warning = block = incomplete = 0
    for item in by_code.values():
        action = str(item.get("action") or "")
        if action == "clear":
            clear += 1
        elif action == "warning":
            warning += 1
        elif action == "block":
            block += 1
        elif action == "incomplete":
            incomplete += 1
    event_risk = {
        "codes_checked": len(risk.get("codes_checked") or by_code),
        "clear": clear,
        "warning": warning,
        "block": block,
        "incomplete": incomplete,
        "promote_allowed": bool(risk.get("promote_allowed_by_risk_check")),
        "source_counts": risk.get("source_counts") or {},
        "categories": risk.get("categories") or {},
    }
    return {
        "sector_strength": {
            "source": "candidate_seed_proxy",
            "note": "当前快照未提供全市场行业字段，先按候选池方向分组统计强度。",
            "items": sector_rows[:6],
        },
        "limit_break_rate": {
            "source": "snapshot_high_vs_close_estimate",
            "note": "用 high/prev_close 是否触及约 9.8% 与收盘涨幅是否仍接近涨停做近似估算。",
            "touched_limit_count": touched,
            "sealed_limit_count": sealed,
            "failed_limit_count": failed,
            "failed_limit_rate": failed_rate,
        },
        "event_risk": event_risk,
    }


def main_list_gate(
    gate: dict[str, Any],
    policy_news: dict[str, Any],
    risk: dict[str, Any],
    market_microstructure: dict[str, Any],
) -> dict[str, Any]:
    score = as_float(gate.get("score")) or 0.0
    regime = str(gate.get("regime") or "")
    source_status = policy_source_status(policy_news)
    event_risk = market_microstructure.get("event_risk") or {}
    limit_break = market_microstructure.get("limit_break_rate") or {}
    failed_rate = as_float(limit_break.get("failed_limit_rate"))
    reasons: list[str] = []
    allow_main = True
    chase_disabled = False

    if score < MAIN_GATE_MIN_SCORE or "空仓" in regime:
        allow_main = False
        reasons.append(f"市场门槛 {score:.1f}/{regime or '未评级'} 低于主榜阈值 {MAIN_GATE_MIN_SCORE:.0f}，主榜空仓观察。")
    if failed_rate is not None and failed_rate >= HIGH_LIMIT_BREAK_RATE:
        chase_disabled = True
        reasons.append(f"炸板率约 {failed_rate:.1f}% 偏高，追高/近涨停候选不得进入主榜。")
    incomplete_count = int(event_risk.get("incomplete") or 0)
    if source_status in ("failed", "missing") and incomplete_count:
        allow_main = False
        reasons.append("新闻源失败且风险事件检查存在 incomplete，只生成观察页，不升级主榜。")
    return {
        "allow_main": allow_main,
        "chase_disabled": chase_disabled,
        "reasons": reasons,
        "source_status": source_status,
        "failed_limit_rate": failed_rate,
        "minimum_gate_score": MAIN_GATE_MIN_SCORE,
        "main_risk_max": MAIN_RISK_MAX,
    }


def required_files(run_dir: Path) -> list[str]:
    return [
        name
        for name in [
            "candidate_seed.csv",
            "market_gate_snapshot.json",
            "trade_session.json",
            "data_health.json",
            "execution_quality.json",
            "risk_events.json",
        ]
        if not (run_dir / name).exists()
    ]



def why_not_main_candidate(
    candidate: Candidate,
    score_info: dict[str, Any],
    preferred_directions: set[str],
    main_gate: dict[str, Any],
) -> list[str]:
    reasons: list[str] = []
    direction = theme_for(candidate)[2]
    if not main_gate.get("allow_main"):
        reasons.extend(str(item) for item in (main_gate.get("reasons") or []))
    if direction not in preferred_directions:
        reasons.append("not_in_priority_direction")
    if candidate.execution_action != "clear":
        reasons.append(f"execution_{candidate.execution_action}")
    if score_info.get("driver_score", 0) < MAIN_DRIVER_MIN:
        reasons.append("driver_below_main_gate")
    if score_info.get("risk_penalty", 0) > MAIN_RISK_MAX:
        reasons.append("risk_penalty_above_main_gate")
    if score_info.get("execution_score", 0) < MAIN_EXECUTION_MIN:
        reasons.append("execution_score_below_main_gate")
    if score_info.get("contradiction_score", 0) > 0:
        reasons.append("contradiction_present")
    if candidate.candidate_source == "low_position_support":
        reasons.append("supplemental_pool_observation")
    return sorted(set(reasons))


def compact_candidate_record(
    candidate: Candidate,
    group: str,
    policy_news: dict[str, Any],
    sector_context: dict[str, dict[str, Any]],
    preferred_directions: set[str],
    main_gate: dict[str, Any],
) -> dict[str, Any]:
    score_info = candidate_score_breakdown(candidate, group, policy_news, sector_context)
    sector, scarce_layer, direction = theme_for(candidate)
    return {
        "code": candidate.code,
        "name": candidate.name,
        "sector": sector,
        "scarce_layer": scarce_layer,
        "direction": direction,
        "candidate_source": candidate.candidate_source,
        "seed_rank": candidate.seed_rank,
        "seed_score": round(candidate.seed_score, 2),
        "pct_chg": candidate.pct_chg,
        "amount": candidate.amount,
        "score": score_info["score"],
        "driver_score": score_info["driver_score"],
        "risk_penalty": score_info["risk_penalty"],
        "execution_score": score_info["execution_score"],
        "contradiction_score": score_info["contradiction_score"],
        "sector_core_score": score_info["sector_core_score"],
        "selection_bucket": score_info["bucket"],
        "reason_tags": score_info["reason_tags"],
        "why_not_main": why_not_main_candidate(candidate, score_info, preferred_directions, main_gate),
    }


def build_counterfactual_groups(
    all_candidates: list[Candidate],
    tradable: list[Candidate],
    inference: list[Candidate],
    research: list[Candidate],
    policy_news: dict[str, Any],
    sector_context: dict[str, dict[str, Any]],
    preferred_directions: set[str],
    main_gate: dict[str, Any],
) -> dict[str, Any]:
    selected_codes = {c.code for c in tradable} | {c.code for c in inference} | {c.code for c in research}
    momentum_top = sorted(
        [c for c in all_candidates if c.candidate_source == "momentum_seed"],
        key=lambda c: (c.seed_score, c.amount or 0.0),
        reverse=True,
    )[:5]
    sector_first_top = rank_candidates(
        [c for c in all_candidates if theme_for(c)[2] in preferred_directions],
        "tradable",
        policy_news,
        sector_context,
    )[:5]
    rejected_high_score = [
        c for c in rank_candidates(all_candidates, "tradable", policy_news, sector_context)
        if c.code not in selected_codes and why_not_main_candidate(
            c,
            candidate_score_breakdown(c, "tradable", policy_news, sector_context),
            preferred_directions,
            main_gate,
        )
    ][:8]
    supplemental_top = rank_candidates(
        [c for c in all_candidates if c.candidate_source == "low_position_support"],
        "premarket_inference",
        policy_news,
        sector_context,
    )[:5]
    return {
        "purpose": "记录未入选但可比较的反事实候选，后续统计过滤器是否过严或过松。",
        "momentum_seed_top5": [compact_candidate_record(c, "tradable", policy_news, sector_context, preferred_directions, main_gate) for c in momentum_top],
        "sector_first_top5": [compact_candidate_record(c, "tradable", policy_news, sector_context, preferred_directions, main_gate) for c in sector_first_top],
        "rejected_high_score": [compact_candidate_record(c, "tradable", policy_news, sector_context, preferred_directions, main_gate) for c in rejected_high_score],
        "low_position_support_top5": [compact_candidate_record(c, "premarket_inference", policy_news, sector_context, preferred_directions, main_gate) for c in supplemental_top],
    }


def build_failure_attribution_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    tag_counts: dict[str, int] = {}
    bucket_counts: dict[str, int] = {}
    high_risk_examples: list[dict[str, Any]] = []
    for item in items:
        bucket = str(item.get("selection_bucket") or "unknown")
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
        for tag in item.get("reason_tags") or []:
            tag_counts[str(tag)] = tag_counts.get(str(tag), 0) + 1
        if int(item.get("risk_penalty") or 0) > MAIN_RISK_MAX or int(item.get("contradiction_score") or 0) > 0:
            high_risk_examples.append({
                "code": item.get("code"),
                "name": item.get("name"),
                "risk_penalty": item.get("risk_penalty"),
                "contradiction_score": item.get("contradiction_score"),
                "reason_tags": item.get("reason_tags") or [],
            })
    return {
        "tag_counts": dict(sorted(tag_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "bucket_counts": dict(sorted(bucket_counts.items(), key=lambda kv: kv[0])),
        "high_risk_examples": high_risk_examples[:12],
        "rule": "T+1/T+2/T+3 回填后按 reason_tags 统计收益和回撤，样本不足 20 前只观察不调参。",
    }

def build_pre_market(root: Path, date: str, run_dir_override: Path | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    if run_dir_override:
        run_dir = run_dir_override
    else:
        run_dir = root / "data" / "watchpool" / f"{date}_pre_market"
    reports = root / "reports"
    if not run_dir.exists():
        reason = f"今日目录不存在：{run_dir}"
        return status_report("A股短线观察池日报", date, reason, "pre_market"), {"status": "blocked", "reason": reason}

    missing = required_files(run_dir)
    if missing:
        reason = "缺少必要文件：" + "、".join(missing)
        return status_report("A股短线观察池日报", date, reason, "pre_market"), {"status": "blocked", "reason": reason}

    health = read_json(run_dir / "data_health.json", {}) or {}
    gate = read_json(run_dir / "market_gate_snapshot.json", {}) or {}
    session = read_json(run_dir / "trade_session.json", {}) or gate.get("trade_session") or {}
    execution = read_json(run_dir / "execution_quality.json", {}) or {}
    risk = read_json(run_dir / "risk_events.json", {}) or {}
    policy_news = read_json(run_dir / "policy_news.json", {}) or {}
    if not policy_news:
        pre_market_news = root / "data" / "watchpool" / f"{date}_pre_market" / "policy_news.json"
        if pre_market_news.exists():
            policy_news = read_json(pre_market_news, {}) or {}

    # Global giant catalyst gate nudge
    catalyst_info = policy_news.get("global_macro_catalyst") or {}
    if catalyst_info.get("triggered"):
        original_score = float(gate.get("score") or 0.0)
        original_regime = gate.get("regime") or ""
        original_is_closed = (original_score < 50.0) or ("防守" in original_regime) or ("空仓" in original_regime)
        
        gate["score"] = min(100.0, original_score + 8.0)
        
        # If the gate is opened via the nudge, upgrade the regime to avoid the "防守" or "空仓" block
        if gate["score"] >= 50.0:
            gate["regime"] = "试探日(事件驱动)"
            gate["position"] = "20-40%"
            
        if original_is_closed and (gate["score"] >= 50.0):
            gate["gate_opened_by_catalyst"] = True
            gate["catalyst_sector"] = catalyst_info.get("sector")

    if not session.get("is_trade_day", True):
        reason = "今日非交易日，不生成候选。"
        return status_report("A股短线观察池日报", date, reason, "pre_market"), {"status": "blocked", "reason": reason}
    if health.get("health_status") != "ok" or not health.get("can_rank_paper_watch"):
        reason = "数据不合格，今日不生成未来三日看涨纸面候选。"
        return status_report("A股短线观察池日报", date, reason, "pre_market"), {"status": "blocked", "reason": reason}
    if not risk.get("promote_allowed_by_risk_check") or not execution.get("promote_allowed_by_execution_check"):
        reason = "风险事件或执行质量检查未通过，不生成候选。"
        return status_report("A股短线观察池日报", date, reason, "pre_market"), {"status": "blocked", "reason": reason}

    base_candidates = [c for c in load_candidates(run_dir) if not is_blocked(c, execution, risk)]
    supplemental = supplemental_candidates_from_snapshot(
        run_dir,
        {c.code for c in base_candidates},
        start_rank=len(base_candidates) + 1,
    )
    all_candidates = base_candidates + supplemental
    if len(all_candidates) < 5:
        reason = f"可用候选不足 5 只，仅 {len(all_candidates)} 只。"
        return status_report("A股短线观察池日报", date, reason, "pre_market"), {"status": "blocked", "reason": reason}
    historical_presence = load_historical_presence(root, date)
    sector_context = build_sector_context(all_candidates, historical_presence)
    ranked_sectors = ranked_directions_from_context(sector_context)
    preferred_directions = priority_directions(sector_context)
    market_microstructure = build_market_microstructure(
        load_csv_rows(run_dir / "all_a_share_snapshot.csv"),
        risk,
        all_candidates,
    )
    market_microstructure["sector_priority"] = {
        "method": "sector_first_then_stock",
        "top_directions": ranked_sectors[:TOP_DIRECTION_LIMIT],
        "allowed_main_directions": sorted(preferred_directions),
    }
    main_gate = main_list_gate(gate, policy_news, risk, market_microstructure)
    main_limit = main_candidate_limit(gate, policy_news)
    score_cache = {
        c.code: candidate_score_breakdown(c, "tradable", policy_news, sector_context)
        for c in all_candidates
    }

    main_pool = [
        c for c in all_candidates
        if main_gate["allow_main"]
        and main_limit > 0
        and theme_for(c)[2] in preferred_directions
        and c.execution_action == "clear"
        and score_cache[c.code]["driver_score"] >= MAIN_DRIVER_MIN
        and score_cache[c.code]["risk_penalty"] <= MAIN_RISK_MAX
        and score_cache[c.code]["execution_score"] >= MAIN_EXECUTION_MIN
        and not (
            main_gate["chase_disabled"] 
            and is_chasing_candidate(c)
            # 强核心龙头豁免机制：行业核心度 >= 80 且 驱动力得分 >= 75 的个股豁免追高剔除
            and not (score_cache[c.code]["sector_core_score"] >= 80 and score_cache[c.code]["driver_score"] >= 75)
        )
    ]
    tradable = rank_candidates(main_pool, "tradable", policy_news, sector_context)[:main_limit]
    tradable_codes = {c.code for c in tradable}
    empty_main_reasons = list(main_gate["reasons"])
    if main_gate["allow_main"] and not tradable:
        empty_main_reasons.append(f"无候选同时满足 driver>={MAIN_DRIVER_MIN}、risk_penalty<={MAIN_RISK_MAX}、execution>={MAIN_EXECUTION_MIN}，主榜空仓观察。")
    if main_limit == 0:
        empty_main_reasons.append("市场状态或新闻源约束使主榜上限为 0。")
    high_risk_pool = [
        c for c in all_candidates
        if c.code not in tradable_codes
        and (
            candidate_score_breakdown(c, "premarket_inference", policy_news, sector_context)["driver_score"] >= MAIN_DRIVER_MIN
            or not tradable
        )
    ]
    inference_pool = rank_candidates(high_risk_pool, "premarket_inference", policy_news, sector_context)
    if len(inference_pool) < 2:
        fallback_pool = [
            c for c in all_candidates
            if c.code not in tradable_codes and c.code not in {item.code for item in inference_pool}
        ]
        inference_pool.extend(rank_candidates(fallback_pool, "premarket_inference", policy_news, sector_context))
    inference = inference_pool[:3]
    excluded_codes = tradable_codes | {c.code for c in inference}
    research_pool = [c for c in all_candidates if c.code not in excluded_codes and c.execution_action == "clear"]
    research_pool = rank_candidates(research_pool, "research", policy_news, sector_context)
    if len(research_pool) < 2:
        research_codes = {c.code for c in research_pool}
        fallback_research = [
            c for c in all_candidates
            if c.code not in excluded_codes and c.code not in research_codes
        ]
        research_pool.extend(rank_candidates(fallback_research, "research", policy_news, sector_context))
    research = research_pool[:3]
    if tradable and (len(inference) < 2 or len(research) < 2):
        reason = (
            "候选池不足以填充短线、推演和中期研究三个板块："
            f"主榜 {len(tradable)}、推演 {len(inference)}、研究 {len(research)}。"
        )
        return status_report("A股短线观察池日报", date, reason, "pre_market"), {"status": "blocked", "reason": reason}
    if not tradable and not (inference or research):
        reason = "主榜为空且无可用推演/研究线索，今日只记录空仓。"
        return status_report("A股短线观察池日报", date, reason, "pre_market"), {"status": "observe_only", "reason": reason}

    report_date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    gate_downgrades = [
        item
        for item in (gate.get("downgrades") or [])
        if "未接入板块强度、炸板率、公告和事件风险" not in str(item)
    ] + empty_main_reasons
    policy_news_report = dict(policy_news)
    policy_news_report.setdefault("classification_summary", policy_news_classification(policy_news))
    policy_news_report.setdefault("evidence_quality", news_evidence_quality(policy_news))
    tradable_cards = [candidate_card(c, idx, "tradable", policy_news, sector_context) for idx, c in enumerate(tradable, 1)]
    inference_cards = [
        candidate_card(c, idx, "premarket_inference", policy_news, sector_context) for idx, c in enumerate(inference, 1)
    ]
    research_cards = [candidate_card(c, idx, "research", policy_news, sector_context) for idx, c in enumerate(research, 1)]
    counterfactual_groups = build_counterfactual_groups(
        all_candidates, tradable, inference, research, policy_news, sector_context, preferred_directions, main_gate
    )
    counterfactual_flat = []
    for group_items in counterfactual_groups.values():
        if isinstance(group_items, list):
            counterfactual_flat.extend(item for item in group_items if isinstance(item, dict))
    failure_attribution = build_failure_attribution_summary(
        tradable_cards + inference_cards + research_cards + counterfactual_flat
    )
    industry_diagnostics = industry_mapping_diagnostics(all_candidates)
    simulator_selection_pool = [
        {
            "code": item.get("code"),
            "name": item.get("name"),
            "group": "tradable_candidates",
            "score": item.get("score"),
            "driver_score": item.get("driver_score"),
            "risk_penalty": item.get("risk_penalty"),
            "execution_score": item.get("execution_score"),
            "contradiction_score": item.get("contradiction_score"),
            "sector_core_score": item.get("sector_core_score"),
            "candidate_source": item.get("candidate_source"),
            "selection_bucket": item.get("selection_bucket"),
            "reason_tags": item.get("reason_tags") or [],
        }
        for item in tradable_cards
    ]
    report_type = "premarket_inference" if tradable else "observe_only"
    suggested_position = gate.get("position", "0%") if tradable else "0%"
    preferred = tradable[0].code if tradable else "空仓观察"
    report = {
        "title": "A股短线观察池日报",
        "subtitle": "脚本生成 · 纸面观察排名卡片",
        "strategy_version": STRATEGY_VERSION,
        "date": report_date,
        "data_cutoff": gate.get("data_cutoff") or session.get("generated_at") or datetime.now().isoformat(timespec="seconds"),
        "mode": f"{session.get('session', 'pre_market')} / {session.get('recommended_mode', 'paper_validate_only')}",
        "report_type": report_type,
        "today_view": gate.get("regime", "未评级"),
        "suggested_position": suggested_position,
        "environment_score": round(float(gate.get("score") or 0), 1),
        "preferred": preferred,
        "market_gate": {
            "score": gate.get("score", "NA"),
            "regime": gate.get("regime", "未评级"),
            "position": gate.get("position", "0%"),
            "data_quality": gate.get("data_quality", "unknown"),
            "diagnostics": gate.get("diagnostics") or [],
            "downgrades": gate_downgrades,
        },
        "hard_filters": {
            "passed": True,
            "warnings": [
                "warning_codes 只做降级观察，不直接剔除；block/incomplete 已过滤。",
                "主榜必须通过反证分和风险扣分；空仓也是有效决策，不强行填满主榜。",
                "主榜先选板块方向，再在优先方向内选个股；低位承接池没有执行/风险 clear 时不得进主榜。",
                f"今日主榜数量上限：{main_limit}。",
                f"执行质量 warning：{', '.join(execution.get('warning_codes') or []) or '无'}",
            ],
            "rejected": [{"code": code, "name": "", "reason": "execution/risk block"} for code in (execution.get("block_codes") or [])],
        },
        "execution_quality": {
            "promote_allowed_by_execution_check": execution.get("promote_allowed_by_execution_check", False),
            "block_codes": execution.get("block_codes") or [],
            "warning_codes": execution.get("warning_codes") or [],
            "counts": execution.get("counts") or {},
            "summary": (
                f"clear {execution.get('counts', {}).get('clear', 0)}、"
                f"warning {execution.get('counts', {}).get('warning', 0)}、"
                f"block {execution.get('counts', {}).get('block', 0)}。"
            ),
        },
        "market_environment": (
            f"数据健康 {health.get('health_status')}，候选种子 {len(all_candidates)} 只可用；"
            f"其中量价强势池 {len(base_candidates)} 只、低位承接补充池 {len(supplemental)} 只；"
            f"市场门槛分 {gate.get('score', 'NA')}，状态 {gate.get('regime', '未评级')}。"
            + ("主榜已通过硬门槛生成；" if tradable else "主榜空仓观察，仅保留推演/研究线索；")
            + "本页为纸面观察和后续复盘输入，不构成真实交易建议。"
        ),
        "scarce_layers": {
            "system_change": "早盘强势种子集中在电子硬件、光通信、半导体和新材料链条。",
            "priority_layers": [
                {"name": item["title"], "reason": item["summary"]} for item in top_directions(all_candidates)
            ],
            "market_miss": "只看涨幅会忽略反证、板块核心性、执行质量和公告风险；非核心跟风票不得靠板块热度进入主榜。",
            "downgraded": "跳空过大、近涨停、炸板、低流动性、盘中延展过高或只有情绪新闻的候选只保留纸面观察。",
        },
        "directions": top_directions(all_candidates),
        "candidate_group_titles": {
            "tradable": "短线波段：驱动力达标且风险未超门槛 (1-10日)",
            "premarket_inference": "中线趋势：强驱动高风险 / 均线企稳承接 (20-60日)",
            "research": "长线价值：产业链卡点与基本面线索 (60-240日)",
        },
        "market_microstructure": market_microstructure,
        "policy_news_catalyst": policy_news_report,
        "industry_mapping_diagnostics": industry_diagnostics,
        "failure_attribution": failure_attribution,
        "counterfactual_groups": counterfactual_groups,
        "simulator_selection_policy": {
            "rule": "模拟盘开仓候选必须来自 skill 策略主榜 tradable_candidates；仓位、持有和退出由模拟盘自行决定。",
            "allowed_open_groups": ["tradable_candidates"],
            "selection_model_version": "sector-first-driver-risk-execution-v4",
        },
        "simulator_selection_pool": simulator_selection_pool,
        "selection_model": {
            "version": "sector-first-driver-risk-execution-v4",
            "main_rules": [
                f"先按板块强度选前 {TOP_DIRECTION_LIMIT} 个方向，再在方向内选股",
                f"今日主榜数量上限 {main_limit}：进攻日最多3、试探日最多2、partial新闻源最多1",
                f"市场门槛分 >= {MAIN_GATE_MIN_SCORE:.0f} 且非空仓观察日",
                f"上涨驱动力分 >= {MAIN_DRIVER_MIN}",
                f"风险扣分 <= {MAIN_RISK_MAX}",
                f"可执行性分 >= {MAIN_EXECUTION_MIN}",
                "执行质量必须为 clear，unknown/manual_review 不得进入主榜",
                "反证分纳入风险扣分：炸板、非核心、情绪-only、高开/冲高过远会降级",
                f"炸板率 >= {HIGH_LIMIT_BREAK_RATE:.0f}% 时，追高/近涨停候选不得进入主榜",
                "阻断风险不得进入主榜",
            ],
            "buckets": {
                "main_candidate": "驱动力达标且风险未超阈值",
                "high_driver_high_risk": "强驱动但风险偏高，只进入推演",
                "clean_but_weak": "可执行性较好但上涨驱动力不足",
                "blocked": "阻断风险或数据风险",
            },
            "empty_main_reasons": empty_main_reasons,
            "candidate_sources": {
                "momentum_seed": len(base_candidates),
                "low_position_support": len(supplemental),
            },
            "sector_priority": market_microstructure["sector_priority"],
        },
        "tradable_candidates": tradable_cards,
        "premarket_inference_candidates": inference_cards,
        "research_leads": research_cards,
        "cross_check": {
            "status": "not_run",
            "reviewers": [],
            "bull_case": "本报告只使用本地脚本生成数据，未进行多模型交叉验证。",
            "bear_case": "市场门槛弱或执行质量 warning 会降低纸面验证质量。",
            "data_quality": gate.get("data_quality", "unknown"),
            "disagreement": "未进行多模型交叉验证。",
            "action": "paper_validate_only" if tradable else "observe_only",
        },
        "review_tracking": {
            "log_ready": True,
            "entry_reference": f"{session.get('session', 'pre_market')} 快照，仅用于纸面 T+1/T+2/T+3 验证",
            "benchmark": "后续按行业/市场基准自动复盘",
            "strategy_version": STRATEGY_VERSION,
            "fields_missing": ["close_t1", "close_t2", "close_t3", "industry_benchmark_return"],
        },
        "one_pick": {
            "code": tradable[0].code if tradable else "空仓",
            "text": (
                f"如果只保留一个纸面观察锚点，{tradable[0].name} 排名最高；仍只做纸面验证。"
                if tradable
                else "今日主榜不满足硬门槛，记录为空仓观察，不强行选股。"
            ),
        },
        "risks": [
            "市场门槛偏弱时，强势种子可能只是一日脉冲。",
            "执行质量 warning、公告风险、跳空过大、反证分过高都会使候选降级。",
            "新闻源 partial 或只有情绪词时，不得把情绪当作核心推荐理由。",
            "低位承接池只作为观察补充；没有公告/执行 clear 前不进入主榜。",
            "本报告不提供真实买卖指令。",
        ],
        "disclaimer": DISCLAIMER,
    }
    summary = {
        "status": "ok" if tradable else "observe_only",
        "kind": "pre_market",
        "date": date,
        "run_dir": str(run_dir),
        "json": str(report_path(root, date, "pre_market_top5.json")),
        "html": str(report_path(root, date, "pre_market_light.html")),
        "sections": {
            "tradable_candidates": [c.code for c in tradable],
            "premarket_inference_candidates": [c.code for c in inference],
            "research_leads": [c.code for c in research],
        },
        "main_gate": main_gate,
        "main_candidate_limit": main_limit,
        "empty_main_reasons": empty_main_reasons,
        "failure_attribution": failure_attribution,
        "counterfactual_groups": {
            key: [item.get("code") for item in value] if isinstance(value, list) else value
            for key, value in counterfactual_groups.items()
        },
        "industry_mapping_diagnostics": industry_diagnostics,
        "simulator_selection_pool": [item.get("code") for item in simulator_selection_pool],
    }
    return report, summary



def load_quote_map(csv_path: Path) -> dict[str, dict[str, Any]]:
    if not csv_path.exists():
        return {}
    rows: dict[str, dict[str, Any]] = {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            code = (row.get("code") or row.get("source_symbol") or "").strip()
            code = code[-6:] if len(code) >= 6 else code
            if not code:
                continue
            rows[code] = row
    return rows


def review_card_from_pre_candidate(
    item: dict[str, Any],
    rank: int,
    pre_quote: dict[str, Any] | None,
    close_quote: dict[str, Any] | None,
    warning_codes: set[str],
    *,
    group: str = "post_close_review",
    layer_label: str = "盘前主榜候选",
    entry_plan: str = "盘后复盘：只评价今天盘前推荐的纸面结果，不新增买卖建议。",
    target: str = "继续跟踪 T+1/T+2/T+3 是否跑赢基准",
) -> tuple[dict[str, Any], dict[str, Any]]:
    code = str(item.get("code") or "")
    name = str(item.get("name") or code)
    entry_price = as_float((pre_quote or {}).get("latest"))
    close_price = as_float((close_quote or {}).get("latest"))
    day_return = ((close_price / entry_price - 1.0) * 100.0) if entry_price and close_price else None
    close_pct = (as_float((close_quote or {}).get("pct_chg")) or 0.0)
    amount = (as_float((close_quote or {}).get("amount")) or 0.0)
    pre_driver = as_float(item.get("driver_score"))
    pre_risk = as_float(item.get("risk_penalty"))
    pre_execution = as_float(item.get("execution_score"))
    bucket = str(item.get("selection_bucket") or "")
    risk_notes = item.get("risk_notes") or []
    outcome = "待核验"
    if day_return is not None:
        if day_return > 0:
            outcome = "当日浮盈"
        elif day_return < 0:
            outcome = "当日浮亏"
        else:
            outcome = "当日持平"
    if day_return is not None and day_return > 1:
        if pre_risk and pre_risk > 14:
            reason = "当日浮盈，但盘前风险扣分偏高，说明强驱动暂时压过风险；仍需看 T+1 是否回吐。"
        else:
            reason = "当日浮盈，盘前驱动力与收盘承接方向一致，继续验证 T+1/T+2/T+3。"
    elif day_return is not None and day_return < -1:
        if pre_risk and pre_risk > 14:
            reason = "当日浮亏，盘前高风险扣分得到验证，重点复盘高开兑现、事件风险或可执行性不足。"
        elif pre_driver and pre_driver >= 72:
            reason = "当日浮亏，说明高驱动力未兑现，重点复盘板块持续性、开盘承接和尾盘资金兑现。"
        else:
            reason = "当日浮亏，盘前驱动力本就不足，不应作为短线主榜样本强化。"
    elif code in warning_codes or bucket == "high_driver_high_risk":
        reason = "当日变化不大但盘前已有降级风险，继续观察是否 T+1 回吐或补涨，不新增买卖建议。"
    else:
        reason = "当日变化不大，暂时不能证明策略有效，继续看 T+1/T+2/T+3。"
    if risk_notes:
        reason += " 盘前扣分项：" + "、".join(str(x) for x in risk_notes[:4]) + "。"
    review = {
        "rank": rank,
        "name": name,
        "code": code,
        "sector": item.get("sector", "未分类"),
        "group": group,
        "score": round(day_return or 0.0, 2),
        "score_label": fmt_pct(day_return),
        "driver_score": item.get("driver_score", "NA"),
        "momentum_score": item.get("momentum_score", "NA"),
        "sector_score": item.get("sector_score", "NA"),
        "liquidity_score": item.get("liquidity_score", "NA"),
        "policy_score": item.get("policy_score", "NA"),
        "execution_score": item.get("execution_score", "NA"),
        "risk_penalty": item.get("risk_penalty", "NA"),
        "contradiction_score": item.get("contradiction_score", "NA"),
        "contradictions": item.get("contradictions", []),
        "sector_core_score": item.get("sector_core_score", "NA"),
        "review_confidence": item.get("review_confidence", "NA"),
        "selection_bucket": item.get("selection_bucket", "post_close_review"),
        "risk_notes": item.get("risk_notes", []),
        "risk_tiers": item.get("risk_tiers", {}),
        "evidence": "Medium" if day_return is not None else "Unverified",
        "scarce_layer": item.get("scarce_layer", layer_label),
        "core_logic": "",
        "catalyst": reason,
        "capital": f"收盘成交额约 {fmt_amount(amount)}；收盘日涨跌幅 {fmt_pct(close_pct)}。",
        "technical": (
            f"盘前到收盘表现：{fmt_pct(day_return)}。"
            f"{'高开/执行 warning 需要降级看待。' if code in warning_codes else '未见执行阻断。'}"
            f"反证分 {item.get('contradiction_score', 'NA')}，板块核心性 {item.get('sector_core_score', 'NA')}。"
        ),
        "entry_plan": entry_plan,
        "support": f"盘前价 {entry_price:.2f}" if entry_price else "盘前参考价缺失",
        "target": target,
        "elasticity": outcome,
        "failure_label": "归因",
        "failure": reason,
    }
    entry_text = "NA" if not entry_price else f"{entry_price:.2f}"
    close_text = "NA" if not close_price else f"{close_price:.2f}"
    review["core_logic"] = (
        f"盘前参考价 {entry_text}，收盘价 {close_text}，当日纸面收益 {fmt_pct(day_return)}，结果：{outcome}。"
        f"盘前驱动力 {item.get('driver_score', 'NA')}，风险扣分 {item.get('risk_penalty', 'NA')}，"
        f"可执行性 {item.get('execution_score', 'NA')}。"
    )
    detail = {
        "code": code,
        "name": name,
        "entry_price": entry_price,
        "close_price": close_price,
        "day_return_pct": day_return,
        "outcome": outcome,
        "reason": reason,
        "warning": code in warning_codes,
        "driver_score": item.get("driver_score"),
        "risk_penalty": item.get("risk_penalty"),
        "contradiction_score": item.get("contradiction_score"),
        "contradictions": item.get("contradictions", []),
        "sector_core_score": item.get("sector_core_score"),
        "risk_notes": item.get("risk_notes", []),
        "reason_tags": item.get("reason_tags", []),
        "execution_score": item.get("execution_score"),
        "selection_bucket": item.get("selection_bucket"),
    }
    return review, detail


def build_rule_feedback(
    details: list[dict[str, Any]],
    effective_samples: int,
    policy_news: dict[str, Any],
) -> list[dict[str, Any]]:
    rules = [
        ("near_or_at_limit_up", "近涨停/封板验证不足", ["接近涨停", "触及涨停附近但未封住"]),
        ("large_intraday_amplitude", "盘中振幅/拉伸过大", ["振幅过大", "盘中拉离低点过远", "盘中拉伸过大"]),
        ("large_open_gap", "大幅高开", ["高开"]),
        ("weak_sector_core", "板块强但个股非核心", ["核心性不足", "资金更集中在龙头", "非核心"]),
        ("sentiment_only_news", "只有情绪新闻缺少实质", ["只有情绪词", "情绪"]),
        ("execution_unknown", "执行质量 unknown", ["执行质量 unknown"]),
        ("low_position_support", "低位承接池", ["low_position_support"]),
    ]
    feedback: list[dict[str, Any]] = []
    for key, title, keywords in rules:
        matched = []
        for item in details:
            if key in set(item.get("reason_tags") or []):
                matched.append(item)
                continue
            text = " ".join(str(value) for value in (item.get("risk_notes") or []) + (item.get("contradictions") or []))
            if any(keyword in text for keyword in keywords):
                matched.append(item)
        if not matched:
            continue
        losses = [item for item in matched if (item.get("day_return_pct") or 0.0) < 0]
        action = "只观察，不调参" if effective_samples < 20 else "纳入下一版参数审查"
        if effective_samples >= 20 and losses and len(losses) / len(matched) >= 0.5:
            action = "建议提高扣分或缩短持有窗口"
        feedback.append(
            {
                "rule": key,
                "title": title,
                "sample_count": len(matched),
                "loss_count": len(losses),
                "loss_rate": round(len(losses) / len(matched) * 100.0, 2) if matched else 0.0,
                "action": action,
                "note": "有效样本少于 20 天时只记录观察，不大调参数。" if effective_samples < 20 else "样本达到审查门槛，可进入参数复核。",
            }
        )
    source_status = policy_source_status(policy_news)
    if source_status == "partial":
        feedback.append(
            {
                "rule": "partial_policy_source_cap",
                "title": "新闻源 partial 时限制政策加分",
                "sample_count": len(details),
                "loss_count": sum(1 for item in details if (item.get("day_return_pct") or 0.0) < 0),
                "loss_rate": 0.0,
                "action": "只观察，不调参" if effective_samples < 20 else "复核政策加分上限",
                "note": "当前已对 partial 源降低正向加分上限；样本未满 20 天前不继续大调。",
            }
        )
    return feedback
def build_post_close(root: Path, date: str) -> tuple[dict[str, Any], dict[str, Any]]:
    data_root = root / "data" / "watchpool"
    pre_json = find_report(root, date, f"{date}_pre_market_top5.json", "pre_market_top5.json")
    audit = read_audit(root)
    if not pre_json.exists():
        reason = f"未找到今日盘前候选 JSON：{pre_json}"
        return status_report("A股观察池盘后复盘", date, reason, "post_close_review"), {
            "status": "blocked",
            "reason": reason,
        }

    pre = read_json(pre_json, {}) or {}
    tradable = pre.get("tradable_candidates") or []
    research_items = pre.get("research_leads") or []
    pre_dir = data_root / f"{date}_pre_market"
    post_dir = data_root / f"{date}_post_close"
    pre_quotes = load_quote_map(pre_dir / "all_a_share_snapshot.csv") or load_quote_map(pre_dir / "candidate_seed.csv")
    close_quotes = load_quote_map(post_dir / "all_a_share_snapshot.csv") or load_quote_map(post_dir / "candidate_seed.csv")
    post_risk = read_json(post_dir / "risk_events.json", {}) or read_json(pre_dir / "risk_events.json", {}) or {}
    policy_news = read_json(post_dir / "policy_news.json", {}) or read_json(pre_dir / "policy_news.json", {}) or {}
    post_health = read_json(post_dir / "data_health.json", {}) or {}
    post_gate = read_json(post_dir / "market_gate_snapshot.json", {}) or {}
    post_session = read_json(post_dir / "trade_session.json", {}) or {}
    warning_codes = set((pre.get("execution_quality") or {}).get("warning_codes") or [])
    market_microstructure = build_market_microstructure(
        load_csv_rows(post_dir / "all_a_share_snapshot.csv") or load_csv_rows(pre_dir / "all_a_share_snapshot.csv"),
        post_risk,
        load_candidates(pre_dir) if pre_dir.exists() else [],
    )
    post_gate_downgrades = [
        item
        for item in (post_gate.get("downgrades") or [])
        if "未接入板块强度、炸板率、公告和事件风险" not in str(item)
    ]

    tracked: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    for rank, item in enumerate(tradable[:5], 1):
        card, detail = review_card_from_pre_candidate(
            item,
            rank,
            pre_quotes.get(str(item.get("code") or "")),
            close_quotes.get(str(item.get("code") or "")),
            warning_codes,
        )
        tracked.append(card)
        details.append(detail)

    research_tracked: list[dict[str, Any]] = []
    research_details: list[dict[str, Any]] = []
    for rank, item in enumerate(research_items[:5], 1):
        card, detail = review_card_from_pre_candidate(
            item,
            rank,
            pre_quotes.get(str(item.get("code") or "")),
            close_quotes.get(str(item.get("code") or "")),
            warning_codes,
            group="post_close_research_review",
            layer_label="中期研究线索",
            entry_plan="中期线索跟踪：只记录盘前列入研究池后的涨跌，不纳入短线主榜胜负。",
            target="继续观察产业链方向持续性和后续 T+1/T+2/T+3 相对强弱",
        )
        research_tracked.append(card)
        research_details.append(detail)

    returns = [item["day_return_pct"] for item in details if item.get("day_return_pct") is not None]
    research_returns = [
        item["day_return_pct"] for item in research_details if item.get("day_return_pct") is not None
    ]
    avg_return = sum(returns) / len(returns) if returns else 0.0
    avg_research_return = sum(research_returns) / len(research_returns) if research_returns else 0.0
    winners = [item for item in details if (item.get("day_return_pct") or 0.0) > 0]
    losers = [item for item in details if (item.get("day_return_pct") or 0.0) < 0]
    research_winners = [item for item in research_details if (item.get("day_return_pct") or 0.0) > 0]
    research_losers = [item for item in research_details if (item.get("day_return_pct") or 0.0) < 0]
    best = max(details, key=lambda item: item.get("day_return_pct") if item.get("day_return_pct") is not None else -999) if details else None
    worst = min(details, key=lambda item: item.get("day_return_pct") if item.get("day_return_pct") is not None else 999) if details else None
    effective = int(audit.get("effective_t3_samples") or audit.get("effective_samples") or 0)
    status = "样本不足" if effective < 20 else "继续纸面验证"
    policy_news_report = dict(policy_news)
    policy_news_report.setdefault("classification_summary", policy_news_classification(policy_news))
    rule_feedback = build_rule_feedback(details, effective, policy_news)
    feedback_text = (
        "；".join(f"{item['title']}：{item['action']}" for item in rule_feedback[:3])
        if rule_feedback
        else "今日未形成新的规则反馈观察。"
    )
    result_text = (
        f"今日盘前主榜 {len(tracked)} 只，收盘可计算 {len(returns)} 只；"
        f"平均当日纸面收益 {fmt_pct(avg_return)}，浮盈 {len(winners)} 只、浮亏 {len(losers)} 只。"
        "这只是当日复盘，最终仍看 T+1/T+2/T+3。"
    )
    directions = [
        {"title": "当日结果", "summary": result_text},
        {"title": "最好表现", "summary": f"{best['name']} {fmt_pct(best.get('day_return_pct'))}：{best.get('reason')}" if best else "暂无"},
        {"title": "最弱表现", "summary": f"{worst['name']} {fmt_pct(worst.get('day_return_pct'))}：{worst.get('reason')}" if worst else "暂无"},
        {
            "title": "中期线索",
            "summary": (
                f"跟踪 {len(research_tracked)} 只，平均当日涨跌 {fmt_pct(avg_research_return)}，"
                f"上涨 {len(research_winners)} 只、下跌 {len(research_losers)} 只。"
            ),
        },
        {
            "title": "规则反推",
            "summary": feedback_text + f" 当前有效 T+3 样本 {effective}，少于 20 时不大调参数。",
        },
    ]
    report = {
        "title": "A股观察池盘后复盘",
        "subtitle": "盘前推荐当日结果 · 盈亏与原因归因",
        "strategy_version": pre.get("strategy_version", STRATEGY_VERSION),
        "date": f"{date[:4]}-{date[4:6]}-{date[6:]}",
        "data_cutoff": post_session.get("generated_at") or datetime.now().isoformat(timespec="seconds"),
        "mode": "post_close_review",
        "report_type": "review",
        "today_view": f"均值 {fmt_pct(avg_return)}",
        "suggested_position": pre.get("suggested_position", "0%"),
        "environment_score": post_gate.get("score", pre.get("environment_score", "NA")),
        "preferred": pre.get("preferred", "无"),
        "market_environment": (
            f"盘后数据健康 {post_health.get('health_status', 'unknown')}。{result_text}"
            f" 中期研究线索 {len(research_tracked)} 只，平均当日涨跌 {fmt_pct(avg_research_return)}。"
            f" 当前有效 T+3 样本 {effective}，少于 20 时不调整策略权重。"
        ),
        "market_gate": {
            "score": post_gate.get("score", "NA"),
            "regime": post_gate.get("regime", "未评级"),
            "position": post_gate.get("position", "0%"),
            "data_quality": post_gate.get("data_quality", "unknown"),
            "diagnostics": post_gate.get("diagnostics") or [],
            "downgrades": post_gate_downgrades,
        },
        "hard_filters": {
            "passed": bool(tracked) and post_health.get("health_status") == "ok",
            "warnings": [
                "本页只复盘今天盘前主榜，不重新推荐股票。",
                "中期研究线索只做方向跟踪，不计入短线主榜胜负。",
                "盘前带 execution warning 的候选，收益也要降级解释。",
                "有效样本少于 20，不下最终策略结论。",
            ],
            "rejected": [],
        },
        "execution_quality": pre.get("execution_quality", {}),
        "scarce_layers": pre.get("scarce_layers", {}),
        "directions": directions,
        "market_microstructure": market_microstructure,
        "policy_news_catalyst": policy_news_report,
        "selection_model": {
            **(pre.get("selection_model") or {}),
            "version": (pre.get("selection_model") or {}).get("version", "sector-first-driver-risk-execution-v4"),
            "rule_feedback": rule_feedback,
            "review_note": "盘后只复盘盘前主榜；样本少于 20 天时，反馈只记录观察，不大调参数。",
        },
        "candidate_group_titles": {
            "tradable": "今日主榜复盘",
            "premarket_inference": "备选名单回看",
            "research": "研究线索回看",
        },
        "tradable_candidates": tracked,
        "premarket_inference_candidates": [],
        "research_leads": research_tracked,
        "cross_check": {
            "status": "not_run",
            "data_quality": post_health.get("health_status", "unknown"),
            "bull_case": f"浮盈数量 {len(winners)}，平均收益 {fmt_pct(avg_return)}。",
            "bear_case": f"浮亏数量 {len(losers)}；弱项主要来自市场门槛、早盘冲高回落或执行 warning。",
            "disagreement": "未进行多模型交叉验证。",
            "action": status,
        },
        "review_tracking": {
            "log_ready": bool(tracked),
            "entry_reference": "盘前快照 latest；收盘用 post_close snapshot latest。",
            "benchmark": "当日先看绝对收益，T+1/T+2/T+3 再比较行业/市场基准。",
            "strategy_version": pre.get("strategy_version", STRATEGY_VERSION),
            "fields_missing": ["close_t1", "close_t2", "close_t3", "benchmark_return"],
        },
        "one_pick": {
            "code": best.get("code") if best else pre.get("preferred", "无"),
            "text": f"今日表现最好的是 {best.get('name')}，当日纸面收益 {fmt_pct(best.get('day_return_pct'))}。" if best else "暂无可计算结果。",
        },
        "risks": [
            "当日盈利不等于 T+1/T+2/T+3 策略有效。",
            "盘前参考价来自当时快照，不代表真实成交价格。",
            "本报告仅作纸面复盘，不构成投资建议。",
        ],
        "disclaimer": DISCLAIMER,
    }
    summary = {
        "status": "ok",
        "kind": "post_close_review",
        "date": date,
        "json": str(report_path(root, date, "post_close_review_light.json")),
        "html": str(report_path(root, date, "post_close_review_light.html")),
        "strategy_status": status,
        "avg_day_return_pct": avg_return,
        "winner_count": len(winners),
        "loser_count": len(losers),
        "reviewed_candidates": details,
        "rule_feedback": rule_feedback,
        "research_tracked_candidates": research_details,
        "avg_research_day_return_pct": avg_research_return,
        "research_winner_count": len(research_winners),
        "research_loser_count": len(research_losers),
        "validation_errors": [],
    }
    return report, summary

def latest_report_json(reports: Path, suffix: str) -> Path | None:
    files = sorted((reports / "daily").glob(f"*/*{suffix}"))
    if not files and suffix.startswith("_"):
        files = sorted((reports / "daily").glob(f"*/{suffix[1:]}"))
    if not files:
        files = sorted(reports.glob(f"*{suffix}"))
    return files[-1] if files else None


def build_weekly(root: Path, date: str) -> tuple[dict[str, Any], dict[str, Any]]:
    reports = root / "reports"
    audit = read_audit(root)
    latest_pre = latest_report_json(reports, "_pre_market_top5.json")
    pre = read_json(latest_pre, {}) if latest_pre else {}
    tracked = []
    for item in (pre.get("tradable_candidates") or [])[:5]:
        copied = dict(item)
        copied["group"] = "weekly_latest_top"
        copied["core_logic"] = f"本周最近一次主榜样本：{item.get('core_logic', '')}"
        copied["entry_plan"] = "周复盘跟踪：只做阶段观察，等待样本数和 T+3 结果积累。"
        tracked.append(copied)
    inference = []
    for item in (pre.get("premarket_inference_candidates") or [])[:3]:
        copied = dict(item)
        copied["group"] = "weekly_backup"
        copied["entry_plan"] = "周复盘备选：只观察方向持续性。"
        inference.append(copied)
    research = []
    for item in (pre.get("research_leads") or [])[:3]:
        copied = dict(item)
        copied["group"] = "weekly_research"
        copied["entry_plan"] = "周复盘研究线索：不纳入短线最终结论。"
        research.append(copied)

    effective = int(audit.get("effective_t3_samples") or audit.get("effective_samples") or 0)
    verdict = audit.get("verdict") or ("样本不足" if effective < 20 else "继续纸面验证")
    report = {
        "title": "A股观察池周复盘",
        "subtitle": "脚本生成 · 阶段验证卡片",
        "strategy_version": pre.get("strategy_version", STRATEGY_VERSION),
        "date": f"{date[:4]}-{date[4:6]}-{date[6:]}",
        "data_cutoff": datetime.now().isoformat(timespec="seconds"),
        "mode": "weekly_review",
        "report_type": "review",
        "today_view": verdict,
        "suggested_position": "0%",
        "environment_score": "NA",
        "preferred": (tracked[0].get("code") if tracked else "无"),
        "market_environment": (
            f"当前有效 T+3 样本 {effective}。少于 20 个有效样本时，只输出阶段观察，"
            "不调整策略权重，不下最终结论。"
        ),
        "market_gate": {
            "score": "NA",
            "regime": verdict,
            "position": "0%",
            "data_quality": "review",
            "diagnostics": [
                f"有效 T+3 样本：{effective}",
                f"策略审计结论：{verdict}",
                f"最近盘前报告：{latest_pre.name if latest_pre else '无'}",
            ],
            "downgrades": ["样本不足 20 时，不允许修改规则或权重。"] if effective < 20 else [],
        },
        "hard_filters": {
            "passed": True,
            "warnings": ["周复盘只做策略验证，不产生新的买卖指令。"],
            "rejected": [],
        },
        "execution_quality": {
            "promote_allowed_by_execution_check": True,
            "block_codes": [],
            "warning_codes": [],
            "summary": "周复盘读取已有报告和审计结果，不重新扫描市场。",
        },
        "scarce_layers": pre.get("scarce_layers", {}),
        "directions": pre.get("directions", []),
        "tradable_candidates": tracked,
        "premarket_inference_candidates": inference,
        "research_leads": research,
        "cross_check": {
            "status": "not_run",
            "data_quality": "review",
            "bull_case": "继续积累纸面样本。",
            "bear_case": "样本不足时任何结论都不稳定。",
            "disagreement": "未进行多模型交叉验证。",
            "action": verdict,
        },
        "review_tracking": {
            "log_ready": True,
            "entry_reference": "watchpool.sqlite / strategy_audit.json",
            "benchmark": "dashboard / strategy_audit",
            "strategy_version": pre.get("strategy_version", STRATEGY_VERSION),
            "fields_missing": [] if effective >= 20 else ["more_valid_t3_samples"],
        },
        "one_pick": {
            "code": tracked[0].get("code") if tracked else "无",
            "text": "周复盘不新增唯一选择，只跟踪策略有效性。",
        },
        "risks": [
            "有效样本不足时不调整权重。",
            "阶段观察不能替代实盘验证。",
            "本报告不构成投资建议。",
        ],
        "disclaimer": DISCLAIMER,
    }
    summary = {
        "status": "ok",
        "kind": "weekly_review",
        "date": date,
        "json": str(report_path(root, date, "weekly_review_light.json")),
        "html": str(report_path(root, date, "weekly_review_light.html")),
        "strategy_status": verdict,
        "effective_t3_samples": effective,
        "latest_pre_market_json": str(latest_pre) if latest_pre else None,
        "tracked_candidates": [item.get("code") for item in tracked],
    }
    return report, summary


def validate_report(report: dict[str, Any], html_path: Path, require_all_sections: bool) -> list[str]:
    errors: list[str] = []
    html = html_path.read_text(encoding="utf-8") if html_path.exists() else ""
    for key in ["title", "date", "disclaimer"]:
        if not report.get(key):
            errors.append(f"missing report.{key}")
    if require_all_sections:
        for key in ["tradable_candidates", "premarket_inference_candidates", "research_leads"]:
            items = report.get(key) or []
            if not items:
                errors.append(f"empty {key}")
            for item in items:
                if item.get("name") and item["name"] not in html:
                    errors.append(f"candidate not found in html: {item['name']}")
    if "不构成投资建议" not in html:
        errors.append("missing disclaimer in html")
    # Strip list items and bullet points (which contain news headlines) to prevent false positives
    import re
    html_clean = re.sub(r'<li>.*?</li>', '', html, flags=re.DOTALL)
    html_clean = re.sub(r'<ul>.*?</ul>', '', html_clean, flags=re.DOTALL)
    if "买入" in html_clean or "卖出" in html_clean:
        errors.append("html contains direct trading wording")
    return errors


def command_pre_market(args: argparse.Namespace) -> int:
    root = Path(args.root)
    date = args.date or yyyymmdd_today()
    run_dir_override = Path(args.run_dir) if args.run_dir else None
    report, summary = build_pre_market(root, date, run_dir_override=run_dir_override)
    out_dir = daily_report_dir(root, date)
    if run_dir_override:
        parts = run_dir_override.name.split("_")
        suffix = "_".join(parts[1:]) if len(parts) > 1 else run_dir_override.name
        json_path = out_dir / f"{suffix}_top5.json"
        html_path = out_dir / f"{suffix}_light.html"
        summary_path = out_dir / f"{suffix}_run_summary.json"
    else:
        json_path = out_dir / "pre_market_top5.json"
        html_path = out_dir / "pre_market_light.html"
        summary_path = out_dir / "pre_market_run_summary.json"
    write_json(json_path, report)
    render_html(report, html_path)
    errors = validate_report(report, html_path, require_all_sections=summary.get("status") == "ok")
    summary.update({"validation_errors": errors, "generated_at": datetime.now().isoformat(timespec="seconds")})
    write_json(summary_path, summary)
    publish_latest(root, [html_path, json_path, summary_path], date, "pre_market")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if errors else 0


def command_post_close(args: argparse.Namespace) -> int:
    root = Path(args.root)
    date = args.date or yyyymmdd_today()
    report, summary = build_post_close(root, date)
    out_dir = daily_report_dir(root, date)
    json_path = out_dir / "post_close_review_light.json"
    html_path = out_dir / "post_close_review_light.html"
    write_json(json_path, report)
    render_html(report, html_path)
    errors = validate_report(report, html_path, require_all_sections=False)
    summary.update({"validation_errors": errors, "generated_at": datetime.now().isoformat(timespec="seconds")})
    summary_path = out_dir / "post_close_review_run_summary.json"
    write_json(summary_path, summary)
    publish_latest(root, [html_path, json_path, summary_path], date, "post_close_review")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if errors else 0


def command_weekly(args: argparse.Namespace) -> int:
    root = Path(args.root)
    date = args.date or yyyymmdd_today()
    report, summary = build_weekly(root, date)
    out_dir = daily_report_dir(root, date)
    json_path = out_dir / "weekly_review_light.json"
    html_path = out_dir / "weekly_review_light.html"
    write_json(json_path, report)
    render_html(report, html_path)
    errors = validate_report(report, html_path, require_all_sections=False)
    summary.update({"validation_errors": errors, "generated_at": datetime.now().isoformat(timespec="seconds")})
    summary_path = out_dir / "weekly_review_run_summary.json"
    write_json(summary_path, summary)
    publish_latest(root, [html_path, json_path, summary_path], date, "weekly_review")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Render deterministic light watchpool reports.")
    parser.add_argument("--root", default=str(ROOT_DEFAULT))
    parser.add_argument("--date", help="YYYYMMDD, default: today")
    parser.add_argument("--run-dir", help="Explicit path to watchpool run directory (bypasses default folder construction)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pre-market")
    sub.add_parser("post-close")
    sub.add_parser("weekly")
    args = parser.parse_args()
    if args.cmd == "pre-market":
        return command_pre_market(args)
    if args.cmd == "post-close":
        return command_post_close(args)
    if args.cmd == "weekly":
        return command_weekly(args)
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
















