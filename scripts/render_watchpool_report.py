#!/usr/bin/env python3
"""Render an A-share watchpool report as screenshot-ready HTML."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


DEFAULT_DISCLAIMER = (
    "以上内容仅用于个人学习研究与策略验证记录，不构成投资建议、买卖依据或收益承诺。"
    "市场有风险，交易需谨慎。"
)


def esc(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def score_class(score: Any) -> str:
    try:
        value = float(score)
    except (TypeError, ValueError):
        return "score-neutral"
    if value >= 85:
        return "score-strong"
    if value >= 75:
        return "score-good"
    if value >= 65:
        return "score-watch"
    return "score-risk"


def score_display_class(score: Any, score_display: str) -> str:
    if "%" in score_display:
        try:
            value = float(score)
        except (TypeError, ValueError):
            value = None
        if value is not None:
            if value > 0:
                return "score-up"
            if value < 0:
                return "score-down"
            return "score-flat"
    return score_class(score)


def evidence_class(label: str) -> str:
    return {
        "Strong": "ev-strong",
        "Medium": "ev-medium",
        "Weak": "ev-weak",
        "Unverified": "ev-unverified",
    }.get(label, "ev-unverified")


def group_label(value: Any) -> str:
    return {
        "tradable": "短线主榜",
        "premarket_inference": "中线趋势",
        "research": "中期线索",
        "post_close_review": "主榜复盘",
        "post_close_research_review": "中期跟踪",
        "weekly_latest_top": "周复盘主榜",
        "weekly_backup": "周复盘备选",
        "weekly_research": "周复盘研究",
    }.get(str(value or ""), str(value or "观察"))


def score_tone_class(score: Any, score_display: str) -> str:
    if "%" in score_display:
        try:
            value = float(score)
        except (TypeError, ValueError):
            value = 0.0
        if value > 0:
            return "tone-up"
        if value < 0:
            return "tone-down"
        return "tone-flat"
    try:
        value = float(score)
    except (TypeError, ValueError):
        return "tone-flat"
    if value >= 75:
        return "tone-up"
    if value >= 65:
        return "tone-watch"
    return "tone-down"


def render_cards(data: dict[str, Any]) -> str:
    cards = [
        ("◈", "今日评级", data.get("today_view", "未评级")),
        ("◇", "建议仓位", data.get("suggested_position", "待定")),
        ("◉", "环境分", data.get("environment_score", "NA")),
        ("★", "首选观察", data.get("preferred", "待定")),
    ]
    return "\n".join(
        f'<div class="metric"><div class="metric-icon">{icon}</div>'
        f'<div class="metric-label">{esc(label)}</div>'
        f'<div class="metric-value">{esc(value)}</div></div>'
        for icon, label, value in cards
    )


def render_directions(directions: list[dict[str, Any]]) -> str:
    if not directions:
        return '<div class="empty">暂无方向数据</div>'
    blocks = []
    for idx, item in enumerate(directions, 1):
        blocks.append(
            '<article class="direction">'
            f'<h3>{idx}. {esc(item.get("title", "未命名方向"))}</h3>'
            f'<p>{esc(item.get("summary", ""))}</p>'
            '</article>'
        )
    return "\n".join(blocks)


def render_scarce_layers(block: Any) -> str:
    if not isinstance(block, dict) or not block:
        return (
            '<div class="empty">暂无产业链卡点拆解。若报告是主题驱动，应补充系统变化、'
            '优先层级、市场可能没看清的地方和失败条件。</div>'
        )
    layers = block.get("priority_layers") or []
    if layers:
        layer_html = "\n".join(
            '<div class="layer">'
            f'<strong>{esc(item.get("name", "未命名层级"))}</strong>'
            f'<p>{esc(item.get("reason", ""))}</p>'
            '</div>'
            if isinstance(item, dict)
            else f'<div class="layer"><strong>{esc(item)}</strong></div>'
            for item in layers
        )
    else:
        layer_html = '<div class="layer"><strong>待补充</strong><p>暂无优先层级。</p></div>'
    return (
        '<div class="scarce-grid">'
        '<div class="scarce-main">'
        f'<p><b>系统变化</b>：{esc(block.get("system_change", "待补充"))}</p>'
        f'<p><b>市场可能没看清的地方</b>：{esc(block.get("market_miss", "待补充"))}</p>'
        '</div>'
        f'<div class="layers">{layer_html}</div>'
        '</div>'
    )


def render_downgrade_constraints(data: dict[str, Any]) -> str:
    gate = data.get("market_gate") if isinstance(data.get("market_gate"), dict) else {}
    filters = data.get("hard_filters") if isinstance(data.get("hard_filters"), dict) else {}
    execution = data.get("execution_quality") if isinstance(data.get("execution_quality"), dict) else {}
    scarce = data.get("scarce_layers") if isinstance(data.get("scarce_layers"), dict) else {}

    cards: list[tuple[str, str, str]] = []
    for item in gate.get("downgrades") or []:
        cards.append(("市场门槛", "constraint-warn", str(item)))
    for item in filters.get("warnings") or []:
        cards.append(("硬过滤", "constraint-warn", str(item)))
    warning_codes = execution.get("warning_codes") or []
    if warning_codes:
        cards.append(("执行降级", "constraint-watch", "warning 代码：" + "、".join(str(code) for code in warning_codes)))
    block_codes = execution.get("block_codes") or []
    if block_codes:
        cards.append(("执行阻断", "constraint-block", "block 代码：" + "、".join(str(code) for code in block_codes)))
    downgraded = scarce.get("downgraded")
    if downgraded:
        cards.append(("产业链约束", "constraint-info", str(downgraded)))
    if not cards:
        cards.append(("当前约束", "constraint-ok", "未触发强制降级；仍按纸面验证口径跟踪。"))

    return '<div class="constraint-grid">' + "".join(
        '<div class="constraint-card">'
        f'<span class="constraint-tag {esc(css)}">{esc(title)}</span>'
        f'<p>{esc(text)}</p>'
        '</div>'
        for title, css, text in cards
    ) + '</div>'


def render_market_gate(gate: Any) -> str:
    if not isinstance(gate, dict) or not gate:
        return '<div class="empty">暂无量化市场门槛诊断。真实报告应补充市场门槛分、数据质量和降级理由。</div>'
    diagnostics = gate.get("diagnostics") or []
    downgrades = gate.get("downgrades") or []
    diag_html = "".join(f"<li>{esc(item)}</li>" for item in diagnostics) or "<li>暂无诊断明细</li>"
    down_html = "".join(f"<li>{esc(item)}</li>" for item in downgrades) or "<li>无强制降级</li>"
    return (
        '<div class="gate-grid">'
        '<div class="gate-score">'
        f'<span>市场门槛分</span><strong>{esc(gate.get("score", "NA"))}</strong>'
        f'<em>{esc(gate.get("regime", "未评级"))} · {esc(gate.get("position", "待定"))}</em>'
        f'<small>数据质量：{esc(gate.get("data_quality", "未标注"))}</small>'
        '</div>'
        '<div class="box compact"><h3>诊断</h3><ul>'
        f'{diag_html}</ul></div>'
        '<div class="box compact"><h3>降级/约束</h3><ul>'
        f'{down_html}</ul></div>'
        '</div>'
    )


def fmt_html_pct(value: Any) -> str:
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return "NA"


def fmt_html_amount(value: Any) -> str:
    try:
        return f"{float(value) / 100000000:.2f}亿元"
    except (TypeError, ValueError):
        return "NA"


def render_market_microstructure(block: Any) -> str:
    if not isinstance(block, dict) or not block:
        return '<div class="empty">暂无板块强度、炸板率、公告和事件风险模块。</div>'
    sector = block.get("sector_strength") or {}
    limit_break = block.get("limit_break_rate") or {}
    event = block.get("event_risk") or {}

    sector_items = sector.get("items") or []
    sector_html = "".join(
        '<div class="sector-row">'
        f'<div><strong>{esc(item.get("name", "未命名方向"))}</strong>'
        f'<span>{esc("、".join(str(x) for x in (item.get("top_names") or [])))}</span></div>'
        f'<em>{fmt_html_pct(item.get("avg_pct"))}</em>'
        f'<small>{esc(item.get("up_count", 0))}/{esc(item.get("count", 0))} 上涨 · {fmt_html_amount(item.get("amount"))}</small>'
        '</div>'
        for item in sector_items[:4]
        if isinstance(item, dict)
    ) or '<div class="muted-line">暂无板块强度代理数据</div>'

    touched = limit_break.get("touched_limit_count", 0)
    sealed = limit_break.get("sealed_limit_count", 0)
    failed = limit_break.get("failed_limit_count", 0)
    failed_rate = limit_break.get("failed_limit_rate")

    risk_status = "通过" if event.get("promote_allowed") else "需复核"
    return (
        '<div class="micro-grid">'
        '<div class="micro-card sector-card">'
        '<div class="micro-head"><h3>板块强度</h3><span>候选池代理</span></div>'
        f'<p>{esc(sector.get("note", ""))}</p>'
        f'<div class="sector-list">{sector_html}</div>'
        '</div>'
        '<div class="micro-card">'
        '<div class="micro-head"><h3>炸板率</h3><span>快照估算</span></div>'
        '<div class="limit-stats">'
        f'<div><span>触板</span><strong>{esc(touched)}</strong></div>'
        f'<div><span>封住</span><strong>{esc(sealed)}</strong></div>'
        f'<div><span>炸板</span><strong>{esc(failed)}</strong></div>'
        f'<div><span>炸板率</span><strong>{fmt_html_pct(failed_rate)}</strong></div>'
        '</div>'
        f'<p>{esc(limit_break.get("note", ""))}</p>'
        '</div>'
        '<div class="micro-card">'
        f'<div class="micro-head"><h3>公告/事件风险</h3><span>{esc(risk_status)}</span></div>'
        '<div class="limit-stats risk-stats">'
        f'<div><span>核验</span><strong>{esc(event.get("codes_checked", 0))}</strong></div>'
        f'<div><span>Clear</span><strong>{esc(event.get("clear", 0))}</strong></div>'
        f'<div><span>Warning</span><strong>{esc(event.get("warning", 0))}</strong></div>'
        f'<div><span>Block</span><strong>{esc(event.get("block", 0))}</strong></div>'
        '</div>'
        f'<p>incomplete {esc(event.get("incomplete", 0))}；风险事件结果会影响候选升级与降级解释。</p>'
        '</div>'
        '</div>'
    )


def render_policy_news(block: Any) -> str:
    if not isinstance(block, dict) or not block:
        return '<div class="empty">暂无新闻/政策催化数据。源未接入时不应把题材当作已验证催化。</div>'
    themes = block.get("catalyst_themes") or []
    theme_html = "".join(
        '<div class="policy-theme">'
        f'<div><strong>{esc(item.get("theme", "未分类"))}</strong><span>命中 {esc(item.get("hit_count", 0))}</span></div>'
        '<ul>'
        + "".join(f'<li>{esc(title)}</li>' for title in (item.get("headlines") or [])[:3])
        + '</ul></div>'
        for item in themes[:4]
        if isinstance(item, dict)
    ) or '<div class="muted-line">暂无明确政策/新闻主题命中。</div>'
    notes = block.get("notes") or []
    note_html = "".join(f"<li>{esc(item)}</li>" for item in notes) or "<li>暂无备注</li>"
    return (
        '<div class="policy-grid">'
        '<div class="policy-score">'
        f'<span>催化分</span><strong>{esc(block.get("policy_news_score", "NA"))}</strong>'
        f'<em>{esc(block.get("source_status", "unknown"))}</em>'
        '</div>'
        '<div class="policy-list">'
        f'{theme_html}'
        '</div>'
        '<div class="policy-notes"><h3>使用约束</h3><ul>'
        f'{note_html}</ul></div>'
        '</div>'
    )


def render_hard_filters(filters: Any) -> str:
    if not isinstance(filters, dict) or not filters:
        return '<div class="empty">暂无硬过滤记录。真实报告应列出通过、警告和剔除原因。</div>'
    passed = "通过" if filters.get("passed") else "未完全通过"
    warnings = filters.get("warnings") or []
    rejected = filters.get("rejected") or []
    warn_html = "".join(f"<li>{esc(item)}</li>" for item in warnings) or "<li>无降级警告</li>"
    if rejected:
        rej_html = "".join(
            "<li>"
            f'{esc(item.get("code", ""))} {esc(item.get("name", ""))}：{esc(item.get("reason", ""))}'
            "</li>"
            if isinstance(item, dict)
            else f"<li>{esc(item)}</li>"
            for item in rejected
        )
    else:
        rej_html = "<li>无强制剔除</li>"
    return (
        '<div class="two-col">'
        f'<div class="box compact"><h3>硬过滤：{esc(passed)}</h3><ul>{warn_html}</ul></div>'
        f'<div class="box compact"><h3>剔除名单</h3><ul>{rej_html}</ul></div>'
        '</div>'
    )


def render_execution_quality(block: Any) -> str:
    if not isinstance(block, dict) or not block:
        return '<div class="empty">暂无可执行性检查。真实报告应补充一字板、缺报价、流动性、跳空、振幅和延展风险。</div>'
    block_codes = block.get("block_codes") or []
    warning_codes = block.get("warning_codes") or []
    counts = block.get("counts") or {}
    status = "允许升级" if block.get("promote_allowed_by_execution_check") else "不可升级"
    status_class = "exec-ok" if block.get("promote_allowed_by_execution_check") else "exec-stop"

    def pills(items: list[Any], css: str, empty_text: str) -> str:
        if not items:
            return f'<span class="code-pill muted">{esc(empty_text)}</span>'
        return "".join(f'<span class="code-pill {esc(css)}">{esc(item)}</span>' for item in items)

    return (
        '<div class="execution-panel">'
        '<div class="exec-summary">'
        f'<span class="exec-status {status_class}">{esc(status)}</span>'
        f'<strong>{esc(block.get("summary") or block.get("rule") or "暂无摘要")}</strong>'
        '</div>'
        '<div class="exec-grid">'
        f'<div class="exec-card"><span>Clear</span><strong>{esc(counts.get("clear", "NA"))}</strong></div>'
        f'<div class="exec-card"><span>Warning</span><strong>{esc(counts.get("warning", len(warning_codes)))}</strong></div>'
        f'<div class="exec-card"><span>Block</span><strong>{esc(counts.get("block", len(block_codes)))}</strong></div>'
        '</div>'
        '<div class="exec-code-row">'
        '<div><b>阻断代码</b><div class="pill-row">'
        f'{pills(block_codes, "block", "无")}</div></div>'
        '<div><b>警告代码</b><div class="pill-row">'
        f'{pills(warning_codes, "warn", "无")}</div></div>'
        '</div>'
        '</div>'
    )


def render_candidate(item: dict[str, Any], fallback_rank: int) -> str:
    rank = item.get("rank", fallback_rank)
    score = item.get("score", "NA")
    score_display = item.get("score_label", f"{esc(score)}分")
    score_css = score_display_class(score, str(score_display))
    tone_css = score_tone_class(score, str(score_display))
    evidence = item.get("evidence", "Unverified")
    driver = item.get("driver_score", "NA")
    penalty = item.get("risk_penalty", "NA")
    execution_score = item.get("execution_score", "NA")
    confidence = item.get("review_confidence", "NA")
    momentum_score = item.get("momentum_score", "NA")
    sector_score = item.get("sector_score", "NA")
    liquidity_score = item.get("liquidity_score", "NA")
    policy_score = item.get("policy_score", "NA")
    bucket = {
        "main_candidate": "驱动力达标 / 风险可控",
        "high_driver_high_risk": "强驱动 / 高风险推演",
        "weak_driver": "驱动力不足 / 观察",
    }.get(str(item.get("selection_bucket", "")), str(item.get("selection_bucket", "未分层") or "未分层"))
    risk_notes = item.get("risk_notes") or []
    risk_note_text = "、".join(str(x) for x in risk_notes[:4]) if risk_notes else "未触发主要风险扣分"
    mini = [
        ("观察", item.get("entry_plan")),
        ("支撑", item.get("support")),
        ("目标", item.get("target")),
        ("弹性", item.get("elasticity")),
    ]
    mini_html = "\n".join(
        f'<div class="mini"><span>{esc(label)}</span><strong>{esc(value or "待定")}</strong></div>'
        for label, value in mini
    )
    failure = item.get("failure", "")
    failure_label = item.get("failure_label", "失败")
    return (
        f'<article class="candidate {tone_css}">'
        '<div class="candidate-head">'
        '<div class="candidate-title-row">'
        f'<div class="rank-badge">{esc(rank)}</div>'
        '<div class="candidate-title">'
        f'<h3>{esc(item.get("name", "未命名"))}</h3>'
        '<div class="chip-row">'
        f'<span class="chip code">{esc(item.get("code", ""))}</span>'
        f'<span class="chip">{esc(item.get("sector", ""))}</span>'
        f'<span class="chip">{esc(group_label(item.get("group", "")))}</span>'
        f'<span class="evidence {evidence_class(str(evidence))}">{esc(evidence)}</span>'
        '</div>'
        '</div>'
        '</div>'
        f'<div class="score {score_css}">{esc(score_display)}</div>'
        '</div>'
        '<div class="score-strip">'
        f'<div><span>上涨驱动力</span><strong>{esc(driver)}</strong></div>'
        f'<div><span>风险扣分</span><strong>{esc(penalty)}</strong></div>'
        f'<div><span>可执行性</span><strong>{esc(execution_score)}</strong></div>'
        f'<div><span>复盘可信度</span><strong>{esc(confidence)}</strong></div>'
        f'<div><span>分层结论</span><strong>{esc(bucket)}</strong></div>'
        '</div>'
        '<div class="factor-strip">'
        f'<div><span>强度</span><strong>{esc(momentum_score)}</strong></div>'
        f'<div><span>板块</span><strong>{esc(sector_score)}</strong></div>'
        f'<div><span>资金</span><strong>{esc(liquidity_score)}</strong></div>'
        f'<div><span>政策/新闻</span><strong>{esc(policy_score)}</strong></div>'
        '</div>'
        '<div class="candidate-main">'
        '<div class="thesis">'
        '<span class="eyebrow">核心逻辑</span>'
        f'<p>{esc(item.get("core_logic", ""))}</p>'
        '<span class="eyebrow">催化/跟踪点</span>'
        f'<p>{esc(item.get("catalyst", ""))}</p>'
        '</div>'
        '<div class="metric-list">'
        f'<div class="kv"><span>卡点</span><strong>{esc(item.get("scarce_layer", "待定"))}</strong></div>'
        f'<div class="kv"><span>资金</span><strong>{esc(item.get("capital", "待定"))}</strong></div>'
        f'<div class="kv"><span>技术</span><strong>{esc(item.get("technical", "待定"))}</strong></div>'
        f'<div class="kv"><span>扣分原因</span><strong>{esc(risk_note_text)}</strong></div>'
        '</div>'
        '</div>'
        f'<div class="mini-grid">{mini_html}</div>'
        f'<p class="failure"><b>{esc(failure_label)}</b>：{esc(failure)}</p>'
        '</article>'
    )

def render_candidates(candidates: list[dict[str, Any]]) -> str:
    if not candidates:
        return '<div class="empty">暂无候选股。市场条件或证据质量不足时，应保持空仓观察。</div>'
    return "\n".join(render_candidate(item, idx) for idx, item in enumerate(candidates, 1))


def render_candidate_groups(data: dict[str, Any]) -> str:
    tradable = data.get("tradable_candidates")
    if tradable is None:
        tradable = data.get("candidates") or []
    inference = data.get("premarket_inference_candidates") or []
    research = data.get("research_leads") or []
    titles = data.get("candidate_group_titles") or {}
    tradable_title = titles.get("tradable", "短线波段候选 (1-10日)")
    inference_title = titles.get("premarket_inference", "中线趋势候选 (20-60日)")
    research_title = titles.get("research", "长线价值线索 (60-240日)")
    blocks = [
        '<section>',
        f'<h2>{esc(tradable_title)}</h2>',
        f'{render_candidates(tradable)}',
        '</section>',
    ]
    if inference:
        blocks.extend([
            '<section>',
            f'<h2>{esc(inference_title)}</h2>',
            f'{render_candidates(inference)}',
            '</section>',
        ])
    elif not titles:
        blocks.extend([
            '<section>',
            f'<h2>{esc(inference_title)}</h2>',
            '<div class="empty">暂无中线趋势候选 (20-60日)。历史数据只能生成观察名单，不能替代尾盘确认。</div>',
            '</section>',
        ])
    if research:
        blocks.extend([
            '<section>',
            f'<h2>{esc(research_title)}</h2>',
            f'{render_candidates(research)}',
            '</section>',
        ])
    elif not titles:
        blocks.extend([
            '<section>',
            f'<h2>{esc(research_title)}</h2>',
            '<div class="empty">暂无长线价值线索 (60-240日)。强产业链逻辑但短线确认不足的标的应放在这里。</div>',
            '</section>',
        ])
    return "".join(blocks)


def render_risks(risks: list[Any]) -> str:
    if not risks:
        return "<p>暂无额外风险条目；仍需关注指数回落、流动性收缩和高位股亏钱效应。</p>"
    return "<ul>" + "".join(f"<li>{esc(risk)}</li>" for risk in risks) + "</ul>"


def render_cross_check(block: Any) -> str:
    if not isinstance(block, dict) or not block:
        block = {
            "status": "not_run",
            "bull_case": "未进行多模型交叉验证",
            "bear_case": "未进行多模型交叉验证",
            "data_quality": "未标注",
            "disagreement": "未进行多模型交叉验证",
            "action": "needs_data",
        }
    reviewers = block.get("reviewers") or []
    reviewer_text = "、".join(str(item) for item in reviewers) if reviewers else "无"
    rows = [
        ("状态", block.get("status", "not_run")),
        ("实际审查者", reviewer_text),
        ("正方理由", block.get("bull_case", "")),
        ("反方理由", block.get("bear_case", "")),
        ("数据质量", block.get("data_quality", "")),
        ("分歧", block.get("disagreement", "")),
        ("动作", block.get("action", "")),
    ]
    return '<div class="box compact">' + "".join(
        f'<p><b>{esc(label)}</b>：{esc(value)}</p>' for label, value in rows
    ) + "</div>"


def render_selection_model(block: Any) -> str:
    if not isinstance(block, dict) or not block:
        return '<div class="empty">暂无筛选模型说明。</div>'
    rules = block.get("main_rules") or []
    buckets = block.get("buckets") or {}
    rules_html = "".join(f"<li>{esc(item)}</li>" for item in rules) or "<li>暂无主榜规则</li>"
    buckets_html = "".join(
        f'<div class="model-bucket"><span>{esc(key)}</span><strong>{esc(value)}</strong></div>'
        for key, value in buckets.items()
    ) or '<div class="model-bucket"><span>未定义</span><strong>暂无分层说明</strong></div>'
    
    feedback_html = ""
    rule_feedback = block.get("rule_feedback")
    if rule_feedback:
        feedback_rows = []
        for item in rule_feedback:
            loss_rate = item.get("loss_rate", 0.0)
            loss_rate_display = f"{loss_rate:.2f}%"
            action_class = "action-warn" if "建议" in str(item.get("action")) else "action-observe"
            feedback_rows.append(
                '<div class="feedback-row">'
                f'  <div class="feedback-title-cell"><strong>{esc(item.get("title"))}</strong><span class="small-tag">{esc(item.get("rule"))}</span></div>'
                f'  <div class="feedback-stat-cell">样本: <b>{item.get("sample_count")}</b> | 亏损: <b class="color-green">{item.get("loss_count")}</b> | 亏损率: <b class="color-green">{loss_rate_display}</b></div>'
                f'  <div class="feedback-action-cell {action_class}"><strong>{esc(item.get("action"))}</strong><small>{esc(item.get("note"))}</small></div>'
                '</div>'
            )
        feedback_html = (
            '<div class="feedback-section">'
            '  <h3>规则回测反馈与调参建议</h3>'
            + ("".join(feedback_rows) if feedback_rows else '<div class="muted-line">未触发异常的亏损率警示规则。</div>') +
            '</div>'
        )

    return (
        '<div class="model-grid">'
        f'<div class="box compact"><h3>模型版本</h3><p>{esc(block.get("version", "unknown"))}</p></div>'
        f'<div class="box compact"><h3>主榜门槛</h3><ul>{rules_html}</ul></div>'
        f'<div class="model-buckets">{buckets_html}</div>'
        '</div>'
        + feedback_html
    )

def render_review_tracking(block: Any) -> str:
    if not isinstance(block, dict) or not block:
        return '<div class="empty">暂无复盘字段。真实报告应记录 entry_reference、benchmark 和缺失字段。</div>'
    missing = block.get("fields_missing") or []
    missing_text = "、".join(str(item) for item in missing) if missing else "无"
    rows = [
        ("可复盘", "是" if block.get("log_ready") else "否"),
        ("入场参考", block.get("entry_reference", "待定")),
        ("基准", block.get("benchmark", "待定")),
        ("缺失字段", missing_text),
    ]
    return '<div class="box compact">' + "".join(
        f'<p><b>{esc(label)}</b>：{esc(value)}</p>' for label, value in rows
    ) + "</div>"


def render_failure_attribution(block: Any) -> str:
    if not isinstance(block, dict) or not block:
        return '<div class="empty">暂无失败归因数据</div>'
    tag_counts = block.get("tag_counts") or {}
    bucket_counts = block.get("bucket_counts") or {}
    high_risk = block.get("high_risk_examples") or []
    
    tag_html = "".join(
        f'<div class="attribution-tag-row"><span>{esc(tag)}</span><strong>{count} 次</strong></div>'
        for tag, count in tag_counts.items()
    ) or '<div class="muted-line">无失败归因标签数据</div>'
    
    bucket_html = "".join(
        f'<div class="attribution-bucket-row"><span>{esc(bucket)}</span><strong>{count} 只</strong></div>'
        for bucket, count in bucket_counts.items()
    ) or '<div class="muted-line">无分层统计数据</div>'
    
    risk_html = "".join(
        '<li>'
        f'<strong>{esc(item.get("name"))}</strong> ({esc(item.get("code"))}) - '
        f'风险扣分: {esc(item.get("risk_penalty"))}, 反证分: {esc(item.get("contradiction_score"))} '
        f'<span class="tags-row">' + " ".join(f'<span class="small-tag">{esc(t)}</span>' for t in item.get("reason_tags", [])) + '</span>'
        '</li>'
        for item in high_risk[:6]
    ) or '<li>无高风险/反证扣分候选股记录</li>'

    return f"""<div class="attribution-grid">
  <div class="box compact">
    <h3>失败标签统计</h3>
    <div class="attribution-list">{tag_html}</div>
  </div>
  <div class="box compact">
    <h3>分层个股统计</h3>
    <div class="attribution-list">{bucket_html}</div>
  </div>
  <div class="box compact">
    <h3>高风险/反证扣分实例</h3>
    <ul class="attribution-risk-list">{risk_html}</ul>
  </div>
</div>"""


def render_html(data: dict[str, Any]) -> str:
    title = data.get("title", "A股短线观察池日报")
    subtitle = data.get("subtitle", "个人学习研究与策略验证记录")
    strategy_version = data.get("strategy_version", "")
    date = data.get("date", "")
    cutoff = data.get("data_cutoff", "14:50-14:56")
    mode = data.get("mode", "intraday")
    disclaimer = data.get("disclaimer") or DEFAULT_DISCLAIMER
    one_pick = data.get("one_pick") or {}
    if isinstance(one_pick, str):
        one_pick = {"text": one_pick}

    # Determine body class and mode display based on mode & report_type
    body_class = "mode-premarket"
    mode_lower = str(mode).lower()
    report_type_lower = str(data.get("report_type", "")).lower()
    
    if "weekly" in mode_lower or "weekly" in report_type_lower:
        body_class = "mode-weekly"
        mode_display = "周度审计"
    elif "post_close" in mode_lower or "post-close" in mode_lower or report_type_lower == "review":
        body_class = "mode-postclose"
        mode_display = "盘后复盘"
    elif "status" in mode_lower or report_type_lower == "data_failure":
        body_class = "mode-status"
        mode_display = "数据故障"
    else:
        mode_display = "盘前前瞻"

    # Select dynamic layouts
    if body_class == "mode-status":
        content_html = f"""
  <div class="metrics">
    {render_cards(data)}
  </div>

  <section class="market">
    <h2>状态详情/阻断原因</h2>
    <div class="box"><p style="color: var(--red); font-weight: 800; font-size: 17px;">{esc(data.get("market_environment", "暂无故障详情。"))}</p></div>
  </section>

  <section>
    <h2>量化门槛与质量</h2>
    {render_market_gate(data.get("market_gate"))}
  </section>

  <section>
    <h2>执行性阻断/排除约束</h2>
    {render_downgrade_constraints(data)}
  </section>
"""
    elif body_class == "mode-weekly":
        content_html = f"""
  <div class="metrics">
    {render_cards(data)}
  </div>

  <section class="market">
    <h2>周审计简报</h2>
    <div class="box"><p>{esc(data.get("market_environment", "暂无周审计摘要。"))}</p></div>
  </section>

  <section>
    <h2>策略审计与结论</h2>
    {render_market_gate(data.get("market_gate"))}
  </section>

  {render_candidate_groups(data)}

  <section>
    <h2>规则反馈与模型说明</h2>
    {render_selection_model(data.get("selection_model"))}
  </section>

  <section class="two-col">
    <div>
      <h2>交叉验证</h2>
      {render_cross_check(data.get("cross_check"))}
    </div>
    <div>
      <h2>复盘明细</h2>
      {render_review_tracking(data.get("review_tracking"))}
    </div>
  </section>

  <section class="two-col">
    <div class="box">
      <h2>本期首选</h2>
      <p><b>{esc(one_pick.get("code", data.get("preferred", "待定")))}</b>：{esc(one_pick.get("text", "周复盘不做强行选择。"))}</p>
    </div>
    <div class="box risk">
      <h2>审计风险提示</h2>
      {render_risks(data.get("risks") or [])}
    </div>
  </section>
"""
    elif body_class == "mode-postclose":
        content_html = f"""
  <div class="metrics">
    {render_cards(data)}
  </div>

  <section class="market">
    <h2>主力复盘结果简报</h2>
    <div class="box"><p>{esc(data.get("market_environment", "暂无复盘摘要。"))}</p></div>
  </section>

  {render_candidate_groups(data)}

  <section>
    <h2>失败归因统计</h2>
    {render_failure_attribution(data.get("failure_attribution"))}
  </section>

  <section>
    <h2>规则参数与反馈</h2>
    {render_selection_model(data.get("selection_model"))}
  </section>

  <section>
    <h2>盘后市场门槛诊断</h2>
    {render_market_gate(data.get("market_gate"))}
  </section>

  <section>
    <h2>市场细节快照</h2>
    {render_market_microstructure(data.get("market_microstructure"))}
  </section>

  <section>
    <h2>催化跟踪与卡点</h2>
    <div class="two-col" style="border-top: 1px solid var(--border);">
      <div>
        <h2>新闻/政策催化</h2>
        {render_policy_news(data.get("policy_news_catalyst"))}
      </div>
      <div>
        <h2>产业链卡点</h2>
        {render_scarce_layers(data.get("scarce_layers"))}
      </div>
    </div>
  </section>

  <section class="two-col">
    <div>
      <h2>多模型交叉验证</h2>
      {render_cross_check(data.get("cross_check"))}
    </div>
    <div>
      <h2>可执行性核验记录</h2>
      {render_execution_quality(data.get("execution_quality"))}
    </div>
  </section>

  <section class="two-col">
    <div class="box">
      <h2>本期首选：{esc(one_pick.get("code", data.get("preferred", "待定")))}</h2>
      <p>{esc(one_pick.get("text", "未达最强证据，不强行开仓。"))}</p>
    </div>
    <div class="box risk">
      <h2>复盘风险提示</h2>
      {render_risks(data.get("risks") or [])}
    </div>
  </section>
"""
    else:
        # default pre-market layout
        content_html = f"""
  <div class="metrics">
    {render_cards(data)}
  </div>

  <section class="market">
    <h2>今日策略观点简报</h2>
    <div class="box"><p>{esc(data.get("market_environment", "暂无市场观点。"))}</p></div>
  </section>

  <section>
    <h2>盘前新闻政策催化</h2>
    {render_policy_news(data.get("policy_news_catalyst"))}
  </section>

  <section>
    <h2>最强板块方向</h2>
    <div class="direction-grid">
      {render_directions(data.get("directions") or [])}
    </div>
  </section>

  <section>
    <h2>产业链卡点拆解</h2>
    {render_scarce_layers(data.get("scarce_layers"))}
  </section>

  {render_candidate_groups(data)}

  <section>
    <h2>量化市场门槛</h2>
    {render_market_gate(data.get("market_gate"))}
  </section>

  <section>
    <h2>市场细节快照</h2>
    {render_market_microstructure(data.get("market_microstructure"))}
  </section>

  <section>
    <h2>硬过滤排除</h2>
    {render_hard_filters(data.get("hard_filters"))}
  </section>

  <section>
    <h2>主榜筛选模型</h2>
    {render_selection_model(data.get("selection_model"))}
  </section>

  <section>
    <h2>降级约束明细</h2>
    {render_downgrade_constraints(data)}
  </section>

  <section>
    <h2>尾盘可执行性检查</h2>
    {render_execution_quality(data.get("execution_quality"))}
  </section>

  <section class="two-col">
    <div>
      <h2>多模型交叉验证</h2>
      {render_cross_check(data.get("cross_check"))}
    </div>
    <div>
      <h2>复盘跟踪锚定</h2>
      {render_review_tracking(data.get("review_tracking"))}
    </div>
  </section>

  <section class="two-col">
    <div class="box">
      <h2>今日首选候选：{esc(one_pick.get("code", data.get("preferred", "待定")))}</h2>
      <p>{esc(one_pick.get("text", "候选不满足条件时空仓。"))}</p>
    </div>
    <div class="box risk">
      <h2>盘前风险提示</h2>
      {render_risks(data.get("risks") or [])}
    </div>
  </section>
"""

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Noto+Sans+SC:wght@400;500;700;900&display=swap');

:root {{
  --bg-deep: #080C14;
  --bg-surface: rgba(13, 20, 37, 0.9);
  --bg-card: rgba(26, 36, 58, 0.55);
  --bg-card-hover: rgba(36, 48, 77, 0.8);
  --border: rgba(148, 163, 184, 0.1);
  --border-accent: rgba(59, 130, 246, 0.3);
  --accent: #3B82F6;
  --accent-light: #60A5FA;
  --accent-glow: rgba(59, 130, 246, 0.15);
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
  --bg-gradient: radial-gradient(ellipse 80% 50% at 15% -8%, rgba(59, 130, 246, 0.08), transparent),
                 radial-gradient(ellipse 60% 40% at 85% 108%, rgba(16, 185, 129, 0.03), transparent);
  --shadow: 0 13px 40px rgba(0, 0, 0, 0.4);
}}

/* Mode Overrides */
body.mode-premarket {{
  --accent: #3B82F6;
  --accent-light: #60A5FA;
  --accent-glow: rgba(59, 130, 246, 0.2);
  --bg-gradient: radial-gradient(ellipse 80% 50% at 15% -8%, rgba(59, 130, 246, 0.08), transparent),
                 radial-gradient(ellipse 60% 40% at 85% 108%, rgba(16, 185, 129, 0.03), transparent);
}}

body.mode-postclose {{
  --accent: #78909C;
  --accent-light: #B0BEC5;
  --accent-glow: rgba(120, 144, 156, 0.2);
  --bg-gradient: radial-gradient(ellipse 80% 50% at 15% -8%, rgba(148, 163, 184, 0.08), transparent),
                 radial-gradient(ellipse 60% 40% at 85% 108%, rgba(148, 163, 184, 0.03), transparent);
}}

body.mode-weekly {{
  --accent: #8B5CF6;
  --accent-light: #C4B5FD;
  --accent-glow: rgba(139, 92, 246, 0.2);
  --bg-gradient: radial-gradient(ellipse 80% 50% at 15% -8%, rgba(139, 92, 246, 0.08), transparent),
                 radial-gradient(ellipse 60% 40% at 85% 108%, rgba(139, 92, 246, 0.03), transparent);
}}

body.mode-status {{
  --accent: #EF4444;
  --accent-light: #FCA5A5;
  --accent-glow: rgba(239, 68, 68, 0.2);
  --bg-gradient: radial-gradient(ellipse 80% 50% at 15% -8%, rgba(239, 68, 68, 0.08), transparent),
                 radial-gradient(ellipse 60% 40% at 85% 108%, rgba(239, 68, 68, 0.03), transparent);
}}

@keyframes fadeInUp {{
  from {{ opacity: 0; transform: translateY(18px); }}
  to   {{ opacity: 1; transform: translateY(0); }}
}}

* {{ box-sizing: border-box; margin: 0; padding: 0; }}

body {{
  background: var(--bg-deep);
  background-image: var(--bg-gradient);
  color: var(--text);
  font-size: 15px;
  font-family: 'Inter', 'Noto Sans SC', -apple-system, BlinkMacSystemFont, sans-serif;
  line-height: 1.6;
  font-feature-settings: 'tnum';
  -webkit-font-smoothing: antialiased;
  min-height: 100vh;
}}

/* ── Page Container ─────────────────────────────────────── */
.page {{
  width: min(980px, calc(100vw - 32px));
  margin: 32px auto;
  padding: 0;
  animation: fadeInUp 0.5s ease-out;
}}

/* ── Header ─────────────────────────────────────────────── */
.header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  padding: 24px 32px;
  background: linear-gradient(135deg, rgba(13, 20, 37, 0.95), rgba(26, 36, 58, 0.9));
  backdrop-filter: blur(20px);
  border: 1px solid var(--border);
  border-bottom: 3px solid var(--accent);
  border-radius: 18px 18px 0 0;
  color: #fff;
  box-shadow: var(--shadow);
}}
.header h1 {{
  margin: 0;
  font-size: 26px;
  font-weight: 900;
  letter-spacing: -0.02em;
  background: linear-gradient(135deg, #fff 40%, var(--accent-light));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}}
.header p {{
  margin: 4px 0 0;
  color: var(--muted);
  font-size: 15px;
  font-weight: 500;
}}
.stamp {{
  text-align: right;
  font-size: 14px;
  color: var(--dim);
  line-height: 1.8;
}}

/* ── Top Metric Cards ───────────────────────────────────── */
.metrics {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1px;
  background: var(--border);
  border: 1px solid var(--border);
  border-top: 0;
  box-shadow: var(--shadow);
}}
.metric {{
  padding: 18px 20px;
  background: var(--bg-surface);
  backdrop-filter: blur(14px);
  text-align: center;
  transition: background 0.25s;
}}
.metric:hover {{ background: var(--bg-card-hover); }}
.metric-icon {{ font-size: 20px; margin-bottom: 2px; line-height: 1; color: var(--accent-light); }}
.metric-label {{
  color: var(--dim);
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}}
.metric-value {{
  margin-top: 6px;
  font-size: 20px;
  font-weight: 800;
  color: var(--text-bright);
}}

/* ── Sections & Headings ────────────────────────────────── */
section {{
  margin-top: 0;
  animation: fadeInUp 0.4s ease-out both;
  box-shadow: var(--shadow);
}}

h2 {{
  display: flex;
  align-items: center;
  gap: 13px;
  margin: 0;
  padding: 16px 24px;
  background: rgba(13, 20, 37, 0.95);
  backdrop-filter: blur(8px);
  border: 1px solid var(--border);
  border-top: 0;
  color: var(--text-bright);
  font-size: 17px;
  font-weight: 800;
  letter-spacing: 0.01em;
}}
h2::before {{
  content: "";
  display: inline-block;
  width: 3px;
  height: 17px;
  border-radius: 2px;
  background: linear-gradient(180deg, var(--accent), var(--accent-light));
  flex-shrink: 0;
}}

/* ── Generic Box / Compact ──────────────────────────────── */
.box {{
  padding: 18px 24px;
  background: var(--bg-surface);
  backdrop-filter: blur(14px);
  border: 1px solid var(--border);
  border-top: 0;
}}
.market p, .candidate p, .direction p {{ margin: 0; font-size: 15px; color: var(--muted); line-height: 1.7; }}

.compact {{ padding: 18px 20px; background: var(--bg-surface); backdrop-filter: blur(14px); }}
.compact h3 {{ margin: 0 0 8px; font-size: 15px; font-weight: 700; color: var(--text-bright); border-bottom: 1px solid var(--border); padding-bottom: 4px; }}
.compact p  {{ margin: 4px 0; font-size: 15px; color: var(--muted); }}
.compact ul {{ margin: 0; padding-left: 18px; }}
.compact li {{ margin: 4px 0; font-size: 15px; color: var(--muted); }}

/* ── Market Gate ────────────────────────────────────────── */
.gate-grid {{
  display: grid;
  grid-template-columns: 200px 1fr 1fr;
  gap: 1px;
  background: var(--border);
  border: 1px solid var(--border);
  border-top: 0;
}}
.gate-score {{
  padding: 22px;
  background: linear-gradient(150deg, var(--accent-glow), var(--bg-surface));
  backdrop-filter: blur(14px);
  display: flex; flex-direction: column; justify-content: center; align-items: center;
  text-align: center;
}}
.gate-score span, .gate-score small {{ display: block; color: var(--muted); font-size: 13px; font-weight: 600; }}
.gate-score strong {{
  display: block; margin: 6px 0; font-size: 40px; font-weight: 900; line-height: 1;
  color: var(--accent-light);
  text-shadow: 0 0 20px var(--accent-glow);
}}
.gate-score em {{ display: block; font-style: normal; font-weight: 700; color: var(--text-bright); font-size: 15px; }}

/* ── Market Microstructure ──────────────────────────────── */
.micro-grid {{
  display: grid;
  grid-template-columns: 1.35fr 0.9fr 0.9fr;
  gap: 1px;
  background: var(--border);
  border: 1px solid var(--border);
  border-top: 0;
}}
.micro-card {{ padding: 18px 18px; background: var(--bg-surface); backdrop-filter: blur(14px); }}
.micro-head {{ display: flex; align-items: baseline; justify-content: space-between; gap: 8px; margin-bottom: 8px; }}
.micro-head h3 {{ margin: 0; font-size: 15px; font-weight: 700; color: var(--text-bright); }}
.micro-head span {{ color: var(--dim); font-size: 13px; }}
.micro-card p {{ margin: 5px 0 0; color: var(--muted); font-size: 14px; }}

.sector-list {{ display: grid; gap: 4px; }}
.sector-row {{
  display: grid; grid-template-columns: 1fr auto; gap: 6px;
  padding: 8px 13px; border-radius: 6px;
  background: var(--bg-card); border: 1px solid var(--border);
  transition: border-color 0.2s;
}}
.sector-row:hover {{ border-color: var(--border-accent); }}
.sector-row strong {{ display: block; font-size: 14px; color: var(--text-bright); }}
.sector-row span   {{ display: block; margin-top: 1px; color: var(--dim); font-size: 13px; }}
.sector-row em     {{ color: var(--red); font-style: normal; font-weight: 900; }}
.sector-row small  {{ grid-column: 1 / -1; color: var(--dim); font-size: 13px; }}

.limit-stats {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 4px; }}
.limit-stats div {{ padding: 8px; border-radius: 6px; background: var(--bg-card); border: 1px solid var(--border); }}
.limit-stats span   {{ display: block; color: var(--dim); font-size: 13px; font-weight: 600; }}
.limit-stats strong {{ display: block; margin-top: 2px; font-size: 18px; color: var(--text-bright); }}

.muted-line {{ color: var(--dim); font-size: 14px; }}

/* ── Policy / News ──────────────────────────────────────── */
.policy-grid {{
  display: grid; grid-template-columns: 180px 1fr 1fr;
  gap: 1px; background: var(--border); border: 1px solid var(--border); border-top: 0;
}}
.policy-score {{
  padding: 18px; text-align: center; display: flex; flex-direction: column; justify-content: center;
  background: linear-gradient(150deg, var(--accent-glow), var(--bg-surface));
  backdrop-filter: blur(14px);
}}
.policy-score span, .policy-score em {{ display: block; color: var(--dim); font-size: 13px; font-style: normal; font-weight: 600; }}
.policy-score strong {{ display: block; margin: 6px 0; font-size: 32px; font-weight: 900; line-height: 1; color: var(--accent-light); }}

.policy-list {{ padding: 16px 18px; background: var(--bg-surface); display: grid; gap: 6px; }}
.policy-theme {{
  padding: 13px 14px; border: 1px solid var(--border); border-radius: 6px;
  background: var(--bg-card); transition: border-color 0.2s;
}}
.policy-theme:hover {{ border-color: var(--border-accent); }}
.policy-theme div   {{ display: flex; justify-content: space-between; gap: 8px; }}
.policy-theme strong {{ font-size: 14px; color: var(--text-bright); }}
.policy-theme span   {{ color: var(--dim); font-size: 13px; }}
.policy-theme ul, .policy-notes ul {{ margin: 5px 0 0; padding-left: 18px; }}
.policy-theme li, .policy-notes li {{ margin: 2px 0; font-size: 13px; line-height: 1.5; color: var(--muted); }}

.policy-notes {{ padding: 16px 18px; background: var(--bg-surface); }}
.policy-notes h3 {{ margin: 0; font-size: 15px; font-weight: 700; color: var(--text-bright); }}

/* ── Selection Model ────────────────────────────────────── */
.model-grid {{
  display: grid; grid-template-columns: 200px 1fr 1fr;
  gap: 1px; background: var(--border); border: 1px solid var(--border); border-top: 0;
}}
.model-buckets {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 1px; background: var(--border); }}
.model-bucket  {{ padding: 14px 16px; background: var(--bg-surface); }}
.model-bucket span   {{ display: block; color: var(--dim); font-size: 13px; font-weight: 700; }}
.model-bucket strong {{ display: block; margin-top: 4px; font-size: 14px; line-height: 1.5; color: var(--text-bright); }}

/* ── Rule Feedback (Post close special) ─────────────────── */
.feedback-section {{
  margin-top: 0;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-top: 0;
  padding: 18px 20px;
}}
.feedback-section h3 {{
  font-size: 15px;
  font-weight: 800;
  margin-bottom: 14px;
  color: var(--accent-light);
}}
.feedback-list {{
  display: grid;
  gap: 8px;
}}
.feedback-row {{
  display: grid;
  grid-template-columns: 1fr 1.3fr 1.2fr;
  gap: 14px;
  align-items: center;
  padding: 8px 14px;
  background: rgba(30,41,59,0.35);
  border: 1px solid var(--border);
  border-radius: 6px;
}}
.feedback-title-cell strong {{
  display: block;
  font-size: 14px;
  color: var(--text-bright);
}}
.feedback-title-cell span.small-tag {{
  display: inline-block;
  font-size: 12px;
  background: rgba(30,41,59,0.6);
  border: 1px solid var(--border);
  padding: 1px 4px;
  border-radius: 4px;
  color: var(--dim);
  margin-top: 2px;
}}
.feedback-stat-cell {{
  font-size: 13px;
  color: var(--muted);
}}
.feedback-stat-cell b {{
  color: var(--text-bright);
}}
.feedback-action-cell {{
  font-size: 13px;
}}
.feedback-action-cell strong {{
  display: block;
  font-weight: 800;
}}
.feedback-action-cell small {{
  display: block;
  font-size: 12px;
  color: var(--dim);
}}
.action-warn strong {{ color: var(--amber); }}
.action-observe strong {{ color: var(--accent-light); }}
.color-green {{ color: var(--green) !important; }}
.color-down {{ color: var(--green) !important; }}

/* ── Failure Attribution (Post close special) ───────────── */
.attribution-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr 1.5fr;
  gap: 1px;
  background: var(--border);
  border: 1px solid var(--border);
  border-top: 0;
}}
.attribution-list {{
  display: grid;
  gap: 6px;
  margin-top: 8px;
}}
.attribution-tag-row, .attribution-bucket-row {{
  display: flex;
  justify-content: space-between;
  padding: 6px 13px;
  background: rgba(30, 41, 59, 0.35);
  border-radius: 4px;
  font-size: 14px;
}}
.attribution-tag-row span, .attribution-bucket-row span {{
  color: var(--muted);
}}
.attribution-tag-row strong, .attribution-bucket-row strong {{
  color: var(--accent-light);
}}
.attribution-risk-list {{
  margin: 8px 0 0;
  padding-left: 18px;
  font-size: 14px;
  color: var(--muted);
}}
.attribution-risk-list li {{
  margin: 6px 0;
}}
.tags-row {{
  display: inline-flex;
  gap: 4px;
  margin-left: 6px;
}}
.small-tag {{
  font-size: 12px;
  background: rgba(30, 41, 59, 0.7);
  padding: 1px 4px;
  border-radius: 3px;
  border: 1px solid var(--border);
  color: var(--dim);
}}

/* ── Constraint Grid ────────────────────────────────────── */
.constraint-grid {{
  display: grid; grid-template-columns: repeat(2, 1fr);
  gap: 1px; background: var(--border); border: 1px solid var(--border); border-top: 0;
}}
.constraint-card {{ padding: 18px 18px; background: var(--bg-surface); backdrop-filter: blur(14px); }}
.constraint-card p {{ margin: 8px 0 0; font-size: 15px; color: var(--muted); }}
.constraint-tag {{
  display: inline-flex; align-items: center; min-height: 24px; padding: 3px 13px;
  border-radius: 6px; font-size: 14px; font-weight: 800;
}}
.constraint-warn  {{ color: var(--amber); background: var(--amber-bg); }}
.constraint-watch {{ color: #F97316; background: rgba(249,115,22,0.12); }}
.constraint-block {{ color: var(--red); background: var(--red-bg); }}
.constraint-info  {{ color: var(--accent-light); background: var(--accent-glow); }}
.constraint-ok    {{ color: var(--green); background: var(--green-bg); }}

/* ── Execution Panel ────────────────────────────────────── */
.execution-panel {{
  padding: 0; overflow: hidden;
  background: var(--bg-surface); backdrop-filter: blur(14px);
  border: 1px solid var(--border); border-top: 0;
}}
.exec-summary {{
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  padding: 18px 20px; border-bottom: 1px solid var(--border);
}}
.exec-summary strong {{ font-size: 15px; color: var(--muted); text-align: right; }}
.exec-status {{
  display: inline-flex; align-items: center; min-height: 28px; padding: 4px 14px;
  border-radius: 6px; font-size: 15px; font-weight: 800;
}}
.exec-ok   {{ color: var(--green); background: var(--green-bg); }}
.exec-stop {{ color: var(--red); background: var(--red-bg); }}
.exec-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; background: var(--border); }}
.exec-card {{ padding: 16px 18px; background: var(--bg-surface); }}
.exec-card span   {{ display: block; color: var(--dim); font-size: 13px; font-weight: 700; }}
.exec-card strong {{ display: block; margin-top: 4px; font-size: 22px; color: var(--text-bright); }}
.exec-code-row {{
  display: grid; grid-template-columns: 1fr 1fr; gap: 1px;
  background: var(--border); border-top: 1px solid var(--border);
}}
.exec-code-row > div {{ padding: 16px 18px; background: var(--bg-surface); }}
.exec-code-row b {{ display: block; margin-bottom: 8px; font-size: 14px; color: var(--text-bright); }}
.pill-row {{ display: flex; flex-wrap: wrap; gap: 6px; }}
.code-pill {{
  display: inline-flex; align-items: center; min-height: 24px; padding: 3px 13px;
  border-radius: 6px; font-size: 14px; font-weight: 800;
  background: rgba(30,41,59,0.55); color: var(--text); border: 1px solid var(--border);
}}
.code-pill.warn  {{ color: var(--amber); background: var(--amber-bg); border-color: rgba(245,158,11,0.2); }}
.code-pill.block {{ color: var(--red); background: var(--red-bg); border-color: rgba(239,68,68,0.2); }}
.code-pill.muted {{ color: var(--dim); }}

/* ── Scarce Layers ──────────────────────────────────────── */
.scarce-grid {{
  display: grid; grid-template-columns: 1.2fr 1fr;
  gap: 1px; background: var(--border); border: 1px solid var(--border); border-top: 0;
}}
.scarce-main {{ padding: 18px 20px; background: var(--bg-surface); backdrop-filter: blur(14px); }}
.scarce-main p {{ margin: 0 0 13px; font-size: 15px; color: var(--muted); line-height: 1.7; }}
.scarce-main p:last-child {{ margin-bottom: 0; }}
.layers {{ display: grid; gap: 1px; background: var(--border); }}
.layer  {{ padding: 16px 18px; background: var(--bg-surface); backdrop-filter: blur(14px); }}
.layer strong {{ font-size: 16px; color: var(--accent-light); }}
.layer p      {{ margin: 4px 0 0; color: var(--muted); font-size: 15px; }}

/* ── Directions ─────────────────────────────────────────── */
.direction-grid {{
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 1px; background: var(--border); border: 1px solid var(--border); border-top: 0;
}}
.direction {{
  min-height: 96px; padding: 18px 20px;
  background: var(--bg-surface); backdrop-filter: blur(14px);
  transition: background 0.2s;
}}
.direction:hover {{ background: var(--bg-card-hover); }}
.direction h3 {{ margin: 0 0 6px; font-size: 16px; font-weight: 700; color: var(--accent-light); }}

/* ── Candidate Cards ────────────────────────────────────── */
.candidate {{
  position: relative; overflow: hidden;
  background: var(--bg-surface); backdrop-filter: blur(18px);
  border: 1px solid var(--border); border-top: 0;
  margin-bottom: 0;
  box-shadow: none;
  transition: border-color 0.3s, box-shadow 0.3s;
}}
.candidate:first-child {{ border-top: 1px solid var(--border); }}
.candidate:hover {{
  border-color: var(--border-accent);
  box-shadow: 0 0 20px var(--accent-glow);
}}
.candidate::before {{
  content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
}}
.candidate.tone-up::before    {{ background: linear-gradient(180deg, var(--red), rgba(239,68,68,0.25)); box-shadow: 0 0 13px rgba(239,68,68,0.25); }}
.candidate.tone-down::before  {{ background: linear-gradient(180deg, var(--green), rgba(16,185,129,0.25)); box-shadow: 0 0 13px rgba(16,185,129,0.25); }}
.candidate.tone-watch::before {{ background: linear-gradient(180deg, var(--amber), rgba(245,158,11,0.25)); box-shadow: 0 0 13px rgba(245,158,11,0.25); }}
.candidate.tone-flat::before  {{ background: linear-gradient(180deg, var(--dim), rgba(100,116,139,0.2)); }}

.candidate-head {{
  display: flex; justify-content: space-between; align-items: center; gap: 18px;
  padding: 18px 20px 14px;
}}
.candidate-title-row {{ display: flex; align-items: center; gap: 14px; min-width: 0; }}
.rank-badge {{
  width: 36px; height: 36px; flex: 0 0 36px;
  display: grid; place-items: center; border-radius: 8px;
  color: var(--accent-light); background: rgba(59,130,246,0.12);
  border: 1px solid rgba(59,130,246,0.25);
  font-size: 18px; font-weight: 900; line-height: 1;
}}
.candidate-title {{ min-width: 0; }}
.candidate h3 {{ margin: 0; font-size: 18px; font-weight: 800; line-height: 1.2; color: var(--text-bright); }}
.chip-row {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }}
.chip {{
  display: inline-flex; align-items: center; min-height: 22px; padding: 2px 8px;
  border: 1px solid var(--border); border-radius: 4px;
  color: var(--muted); background: rgba(30,41,59,0.4); font-size: 13px; font-weight: 600;
}}
.chip.code {{ color: var(--accent-light); background: rgba(59,130,246,0.1); border-color: rgba(59,130,246,0.2); }}

/* ── Scores ─────────────────────────────────────────────── */
.score {{
  min-width: 80px; padding: 6px 14px; text-align: center;
  font-size: 18px; font-weight: 900; border-radius: 8px;
}}
.score-strong  {{ color: #fff; background: linear-gradient(135deg, #3B82F6, #2563EB); box-shadow: 0 4px 16px rgba(59,130,246,0.35); }}
.score-good    {{ color: var(--accent-light); background: rgba(59,130,246,0.15); }}
.score-watch   {{ color: var(--amber); background: var(--amber-bg); }}
.score-risk    {{ color: var(--red); background: var(--red-bg); }}
.score-up      {{ color: var(--red); background: var(--red-bg); }}
.score-down    {{ color: var(--green); background: var(--green-bg); }}
.score-flat    {{ color: var(--dim); background: rgba(30,41,59,0.5); }}
.score-neutral {{ color: var(--dim); background: rgba(30,41,59,0.5); }}

/* ── Score & Factor Strips ──────────────────────────────── */
.score-strip {{
  display: grid; grid-template-columns: repeat(5, 1fr);
  gap: 1px; background: var(--border); border-top: 1px solid var(--border);
}}
.score-strip div {{ padding: 13px 16px; background: rgba(15,23,42,0.55); }}
.score-strip span   {{ display: block; color: var(--dim); font-size: 13px; font-weight: 700; text-transform: uppercase; }}
.score-strip strong {{ display: block; margin-top: 3px; color: var(--text-bright); font-size: 16px; }}

.factor-strip {{
  display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 1px; background: var(--border);
}}
.factor-strip div {{ padding: 13px 16px; background: rgba(15,23,42,0.40); }}
.factor-strip span   {{ display: block; color: var(--dim); font-size: 13px; font-weight: 700; }}
.factor-strip strong {{ display: block; margin-top: 3px; color: var(--text); font-size: 15px; }}

/* ── Candidate Body ─────────────────────────────────────── */
.candidate-main {{
  display: grid; grid-template-columns: 1.2fr 0.9fr;
  gap: 1px; background: var(--border);
  border-top: 1px solid var(--border);
}}
.thesis {{ padding: 16px 18px; background: var(--bg-surface); border: 0; border-radius: 0; }}
.eyebrow {{
  display: block; margin-bottom: 4px;
  color: var(--accent-light); font-size: 13px; font-weight: 800;
  text-transform: uppercase; letter-spacing: 0.05em;
}}
.thesis p {{ margin: 0 0 14px; font-size: 15px; color: var(--muted); line-height: 1.7; }}
.thesis p:last-child {{ margin-bottom: 0; }}

.metric-list {{ display: grid; gap: 1px; background: var(--border); }}
.kv {{ padding: 13px 16px; background: var(--bg-surface); border: 0; border-radius: 0; }}
.kv span   {{ display: block; color: var(--dim); font-size: 13px; font-weight: 700; }}
.kv strong {{ display: block; margin-top: 3px; font-size: 15px; line-height: 1.5; color: var(--text); }}

.mini-grid {{
  display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 1px; background: var(--border); border-top: 1px solid var(--border);
  margin-top: 0;
}}
.mini {{
  padding: 14px 16px; min-height: 52px;
  background: rgba(15,23,42,0.45); border: 0; border-radius: 0;
}}
.mini span   {{ display: block; color: var(--dim); font-size: 13px; }}
.mini strong {{ display: block; margin-top: 4px; font-size: 15px; color: var(--text); }}

.failure {{
  margin: 0 !important;
  padding: 13px 18px; border: 0; border-radius: 0;
  color: var(--amber); background: rgba(245,158,11,0.06);
  border-top: 1px solid rgba(245,158,11,0.12);
  font-size: 15px;
}}

/* ── Two Column Layout ──────────────────────────────────── */
.two-col {{
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 1px; background: var(--border);
  border: 1px solid var(--border); border-top: 0;
}}
.two-col > div {{ background: var(--bg-surface); }}
.two-col .box  {{ border: 0; }}
.risk ul {{ margin: 0; padding-left: 20px; }}
.risk li {{ margin: 4px 0; color: var(--muted); font-size: 15px; }}

/* ── Evidence Badges ────────────────────────────────────── */
.evidence {{
  display: inline-block; margin-left: 6px; padding: 2px 7px;
  border-radius: 4px; font-size: 13px; font-weight: 700;
}}
.ev-strong     {{ color: var(--green); background: var(--green-bg); }}
.ev-medium     {{ color: var(--accent-light); background: var(--accent-glow); }}
.ev-weak       {{ color: var(--amber); background: var(--amber-bg); }}
.ev-unverified {{ color: var(--red); background: var(--red-bg); }}

/* ── Empty State ────────────────────────────────────────── */
.empty {{
  padding: 20px 24px; color: var(--dim);
  border: 1px dashed rgba(148,163,184,0.18);
  background: rgba(15,23,42,0.35);
  border-radius: 0; font-size: 15px;
}}

/* ── Footer ─────────────────────────────────────────────── */
.footer {{
  margin-top: 0; padding: 18px 24px;
  color: var(--dim); font-size: 13px;
  background: var(--bg-surface); backdrop-filter: blur(14px);
  border: 1px solid var(--border); border-top: 0;
  border-radius: 0 0 18px 18px;
}}

/* ── Responsive ─────────────────────────────────────────── */
@media (max-width: 760px) {{
  .page {{ width: 100%; margin: 0; }}
  .header {{ display: block; border-radius: 0; padding: 18px; }}
  .stamp  {{ text-align: left; margin-top: 8px; }}
  .metrics, .direction-grid, .gate-grid, .micro-grid, .policy-grid,
  .model-grid, .constraint-grid, .exec-grid, .exec-code-row,
  .scarce-grid, .candidate-main, .mini-grid, .score-strip,
  .factor-strip, .two-col, .model-buckets, .attribution-grid, .feedback-row {{
    grid-template-columns: 1fr;
  }}
  .candidate-head {{ display: block; }}
  .score {{ display: inline-block; margin-top: 13px; }}
  .exec-summary {{ display: block; }}
  .exec-summary strong {{ display: block; margin-top: 8px; text-align: left; }}
  .footer, .header {{ border-radius: 0; }}
}}
</style>
</head>
<body class="{body_class}">
<main class="page">
  <header class="header">
    <div>
      <h1>{esc(title)}</h1>
      <p>{esc(subtitle)}</p>
      <p>{esc(strategy_version)}</p>
    </div>
    <div class="stamp">
      <div>{esc(date)}</div>
      <div>数据截止：{esc(cutoff)}</div>
      <div>{esc(mode_display)}</div>
    </div>
  </header>

  {content_html}

  <footer class="footer">{esc(disclaimer)}</footer>
</main>
</body>
</html>"""


def demo_data() -> dict[str, Any]:
    return {
        "title": "A股短线观察池日报",
        "subtitle": "个人学习研究与策略验证记录",
        "strategy_version": "a-share-watchpool-v0.9.0",
        "date": "2026-06-17",
        "data_cutoff": "14:50-14:56",
        "mode": "intraday",
        "today_view": "试探日",
        "suggested_position": "30%",
        "environment_score": 76,
        "preferred": "示例001",
        "market_gate": {
            "score": 76,
            "regime": "试探日",
            "position": "30%",
            "data_quality": "partial",
            "diagnostics": [
                "指数结构中性偏强，未接入实时行情。",
                "板块轮动较快，需要降低追高权重。",
                "成交和涨停生态为演示字段，真实报告必须替换。",
            ],
            "downgrades": ["实时数据缺失，仓位按试探日处理。"],
        },
        "hard_filters": {
            "passed": True,
            "warnings": ["示例报告未核验流动性和公告。"],
            "rejected": [
                {"code": "示例999", "name": "示例剔除", "reason": "无实际尾盘确认入口。"}
            ],
        },
        "execution_quality": {
            "promote_allowed_by_execution_check": False,
            "block_codes": [],
            "warning_codes": ["示例001"],
            "summary": "演示报告未核验真实尾盘可执行性。",
        },
        "market_environment": "指数环境中性偏强，题材轮动较快。报告仅演示版式，未接入实时行情。",
        "scarce_layers": {
            "system_change": "AI终端和服务器升级带来带宽、功耗、散热和验证周期压力。",
            "priority_layers": [
                {"name": "光学材料与模组", "reason": "靠近显示和感知升级中的材料约束。"},
                {"name": "半导体设备与测试", "reason": "扩产和良率改善需要设备验证。"},
            ],
            "market_miss": "市场容易只看整机和热门概念，忽略上游验证周期和供给弹性。",
            "downgraded": "缺少公告、订单和成交确认的纯概念股先降级。",
        },
        "directions": [
            {"title": "AI硬件", "summary": "板块强度较高，但需确认成交量和龙头持续性。"},
            {"title": "半导体设备", "summary": "政策与国产替代逻辑仍在，观察资金是否继续回流。"},
            {"title": "消费电子", "summary": "适合关注低位补涨和公告催化，避免追高。"},
        ],
        "tradable_candidates": [
            {
                "rank": 1,
                "name": "示例股份",
                "code": "示例001",
                "sector": "AI硬件",
                "group": "tradable",
                "score": 82,
                "evidence": "Unverified",
                "scarce_layer": "示例：光学材料与模组",
                "core_logic": "演示候选。真实报告需要补充实时行情、公告和资金数据。",
                "catalyst": "待核验。",
                "capital": "待核验。",
                "technical": "待核验。",
                "entry_plan": "14:30预筛，14:50-14:56尾盘确认；不构成买入指令。",
                "support": "待定",
                "target": "待定",
                "elasticity": "待定",
                "failure": "实时数据无法验证或板块强度回落。",
            }
        ],
        "research_leads": [
            {
                "rank": 1,
                "name": "示例价值线索",
                "code": "示例002",
                "sector": "半导体设备",
                "group": "research",
                "score": 78,
                "evidence": "Unverified",
                "scarce_layer": "示例：设备验证",
                "core_logic": "产业链位置可能较好，但当前缺少短线成交确认。",
                "catalyst": "待核验。",
                "capital": "无短线确认。",
                "technical": "待核验。",
                "entry_plan": "不进入短线候选，先作为中期线索跟踪。",
                "support": "待定",
                "target": "待定",
                "elasticity": "待定",
                "failure": "客户认证和订单证据不足。",
            }
        ],
        "cross_check": {
            "status": "not_run",
            "reviewers": [],
            "bull_case": "未进行多模型交叉验证。",
            "bear_case": "未进行多模型交叉验证。",
            "data_quality": "partial",
            "disagreement": "未进行多模型交叉验证。",
            "action": "needs_data",
        },
        "review_tracking": {
            "log_ready": False,
            "entry_reference": "14:50-14:56 quote or 15:00 close",
            "benchmark": "创业板指",
            "fields_missing": ["entry_price", "close_t1", "close_t2", "close_t3"],
        },
        "one_pick": {"code": "示例001", "text": "仅作版式演示；真实使用时必须先完成证据核验。"},
        "risks": ["演示数据不代表真实行情。", "短线波动大，策略需要严格复盘。"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render A-share watchpool HTML report.")
    parser.add_argument("--input", help="Input JSON file. Omit with --demo.")
    parser.add_argument("--output", required=True, help="Output HTML path.")
    parser.add_argument("--demo", action="store_true", help="Render built-in demo data.")
    args = parser.parse_args()

    if args.demo:
        data = demo_data()
    elif args.input:
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    else:
        parser.error("provide --input data.json or --demo")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_html(data), encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())







