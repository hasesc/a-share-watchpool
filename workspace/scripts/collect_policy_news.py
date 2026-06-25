#!/usr/bin/env python3
"""Best-effort policy/news catalyst collector for the watchpool report."""

from __future__ import annotations

import argparse
import csv
import json
import threading
import queue
import socket
import urllib.request
import urllib.error
from datetime import datetime

# Set global timeout for socket operations
socket.setdefaulttimeout(15)
from pathlib import Path
from typing import Any


THEME_KEYWORDS = {
    "半导体": ["半导体", "芯片", "存储", "集成电路", "国产替代", "光刻", "先进封装", "美光", "英伟达", "台积电", "阿斯麦", "辉达", "美光科技", "英伟达财报", "nvda", "mu"],
    "光通信": ["光通信", "光模块", "算力", "数据中心", "CPO", "高速互联"],
    "新材料": ["新材料", "稀有金属", "钨", "稀土", "锂电", "材料"],
    "消费电子": ["消费电子", "面板", "OLED", "AI手机", "终端", "苹果", "apple", "华为", "huawei"],
    "黄金资源": ["黄金", "贵金属", "资源", "矿业"],
    "机器人": ["机器人", "人形机器人", "减速器", "传感器"],
    "AI": ["人工智能", "AI", "大模型", "算力", "服务器", "openai", "chatgpt", "sora", "claude"],
}

GLOBAL_GIANTS_MAP = {
    "美光": "半导体",
    "英伟达": "半导体",
    "台积电": "半导体",
    "阿斯麦": "半导体",
    "辉达": "半导体",
    "美光科技": "半导体",
    "nvda": "半导体",
    "mu": "半导体",
    "openai": "AI",
    "chatgpt": "AI",
    "sora": "AI",
    "claude": "AI",
    "特斯拉": "机器人",
    "tesla": "机器人",
    "苹果": "消费电子",
    "apple": "消费电子",
    "华为": "消费电子",
    "huawei": "消费电子"
}
CATALYST_ACTIONS = ["财报", "业绩", "季报", "营收", "超预期", "净利润", "大增", "发布会", "禁令", "制裁", "限制", "关税"]

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
    seen: set[str] = set()
    deduped: list[str] = []
    for text in texts:
        clean = " ".join(str(text).split())
        if not clean or clean in seen:
            continue
        seen.add(clean)
        deduped.append(clean)
    categories: dict[str, dict[str, Any]] = {}
    for category, keywords in NEWS_CATEGORY_KEYWORDS.items():
        matched_words: set[str] = set()
        matched_headlines: list[str] = []
        for text in deduped:
            hits = [word for word in keywords if word.lower() in text.lower()]
            if not hits:
                continue
            matched_words.update(hits)
            if len(matched_headlines) < 5:
                matched_headlines.append(text)
        categories[category] = {
            "count": len(matched_headlines),
            "matched_words": sorted(matched_words),
            "headlines": matched_headlines,
        }
    return {
        "source": "collector_rows_and_stock_headlines",
        "deduped_headline_count": len(deduped),
        "categories": categories,
        "scoring_policy": {
            "policy_level": "可有限加分",
            "industry_level": "可有限加分",
            "company_positive": "只在证据明确时小幅加分",
            "company_negative": "优先扣分或降级",
            "sentiment_level": "只小幅加分，不能作为核心理由",
        },
    }


def evidence_quality(status: str, sources: dict[str, Any], generated_at: str) -> dict[str, Any]:
    ok_sources = [name for name, item in sources.items() if item.get("ok")]
    failed_sources = [name for name, item in sources.items() if not item.get("ok")]
    score = 70
    if status == "ok":
        score += 10
    elif status == "partial":
        score -= 15
    elif status == "failed":
        score -= 35
    if not ok_sources:
        score -= 20
    if not generated_at:
        score -= 10
    return {
        "source_status": status,
        "ok_sources": ok_sources,
        "failed_sources": failed_sources,
        "generated_at": generated_at,
        "has_timestamp": bool(generated_at),
        "credibility_score": max(0, min(100, score)),
        "scoring_rule": "政策/行业有限加分；公司负面优先扣分；情绪级和 partial 源限制正向加分。",
    }


def source_quality_summary(status: str, sources: dict[str, Any], stock_news: dict[str, Any]) -> dict[str, Any]:
    source_total = len(sources)
    source_ok = sum(1 for item in sources.values() if item.get("ok"))
    stock_total = len(stock_news)
    stock_ok = sum(1 for item in stock_news.values() if item.get("ok"))
    failed = [name for name, item in sources.items() if not item.get("ok")]
    failed += [f"stock_news:{code}" for code, item in stock_news.items() if not item.get("ok")]
    ok_rate = (source_ok + stock_ok) / max(1, source_total + stock_total)
    cap = 1.0
    if status == "partial":
        cap = 0.55
    elif status in ("missing", "failed"):
        cap = 0.25
    return {
        "status": status,
        "source_ok": source_ok,
        "source_total": source_total,
        "stock_news_ok": stock_ok,
        "stock_news_total": stock_total,
        "ok_rate": round(ok_rate, 4),
        "failed_sources": failed,
        "positive_score_cap_multiplier": cap,
        "source_weights": {
            "official_policy_or_cctv": 1.0,
            "credible_financial_wire": 0.75,
            "stock_news": 0.6,
            "sentiment_only": 0.25,
        },
        "rule": "partial/failed 源降低正向新闻加分上限；公司负面不受 cap 保护，仍优先扣分。",
    }


def read_codes(candidate_path: Path, limit: int) -> list[str]:
    if not candidate_path.exists():
        return []
    codes: list[str] = []
    with candidate_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            code = str(row.get("code") or row.get("source_symbol") or "").strip()[-6:]
            if code:
                codes.append(code)
            if len(codes) >= limit:
                break
    return codes


def worker(kind: str, arg: str | None, q: queue.Queue) -> None:
    try:
        import akshare as ak

        if kind == "cctv":
            df = ak.news_cctv(date=arg or datetime.now().strftime("%Y%m%d"))
        elif kind == "sina":
            df = ak.stock_info_global_sina()
        elif kind == "em":
            df = ak.stock_info_global_em()
        elif kind == "stock_news":
            df = ak.stock_news_em(symbol=arg or "")
        else:
            raise ValueError(kind)
        
        if df is None or df.empty:
            q.put({"ok": True, "rows": [], "columns": []})
        else:
            rows = df.head(80).to_dict(orient="records")
            q.put({"ok": True, "rows": rows, "columns": list(df.columns)})
    except Exception as exc:  # noqa: BLE001 - preserve source failure in output
        q.put({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def run_with_timeout(kind: str, arg: str | None = None, timeout: int = 15) -> dict[str, Any]:
    q = queue.Queue()
    t = threading.Thread(target=worker, args=(kind, arg, q))
    t.daemon = True
    t.start()
    t.join(timeout)
    if t.is_alive():
        return {"ok": False, "error": f"{kind} timeout after {timeout}s"}
    if q.empty():
        return {"ok": False, "error": f"{kind} returned no payload"}
    return q.get()


def row_text(row: dict[str, Any]) -> str:
    return " ".join(str(value) for value in row.values() if value not in (None, ""))


def row_title(row: dict[str, Any]) -> str:
    for key in ["标题", "title", "新闻标题", "内容", "summary"]:
        value = row.get(key)
        if value:
            return str(value)
    text = row_text(row)
    return text[:80]


def classify_news(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {name: [] for name in THEME_KEYWORDS}
    for row in rows:
        text = row_text(row)
        for theme, keywords in THEME_KEYWORDS.items():
            if any(keyword.lower() in text.lower() for keyword in keywords):
                buckets[theme].append(row)
                break
    output = []
    for theme, items in buckets.items():
        if not items:
            continue
        output.append(
            {
                "theme": theme,
                "hit_count": len(items),
                "headlines": [row_title(item) for item in items[:4]],
                "keywords": THEME_KEYWORDS[theme],
            }
        )
    output.sort(key=lambda item: item["hit_count"], reverse=True)
    return output[:6]

def analyze_catalysts_via_llm(headlines: list[str]) -> dict[str, Any] | None:
    import os
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
        
    api_base = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    
    # Select a subset of headlines to avoid blowing context window
    selected_headlines = headlines[:60]
    
    prompt = (
        "You are an expert quantitative researcher. Analyze the following financial headlines for any major global catalyst "
        "caused by an industry giant (e.g. Nvidia, Micron, TSMC, OpenAI, Tesla, Apple, Huawei) releasing earnings, "
        "guidance, or making product breakthroughs that would heavily influence A-share sectors like Semiconductors, AI, "
        "Robotics, or Consumer Electronics.\n\n"
        "Headlines:\n" + "\n".join(f"- {h}" for h in selected_headlines) + "\n\n"
        "Respond ONLY with a JSON object of the following format (no markdown, no other text):\n"
        "{\n"
        "  \"triggered\": true,\n"
        "  \"giant\": \"Micron\",\n"
        "  \"sector\": \"半导体\",\n"
        "  \"action\": \"earnings\",\n"
        "  \"headline\": \"the matched headline\"\n"
        "}\n"
        "If no major global catalyst is found, respond with {\"triggered\": false}."
    )
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    data = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"}
    }
    
    try:
        req = urllib.request.Request(
            f"{api_base}/chat/completions",
            data=json.dumps(data).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            content = res_data["choices"][0]["message"]["content"].strip()
            result = json.loads(content)
            if result.get("triggered"):
                return {
                    "triggered": True,
                    "giant": str(result.get("giant") or ""),
                    "sector": str(result.get("sector") or ""),
                    "action": str(result.get("action") or ""),
                    "headline": str(result.get("headline") or "")
                }
    except Exception as e:
        print(f"LLM API analysis failed or timed out: {e}. Falling back to regex.")
        
    return None


def detect_global_catalyst(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    # 1. Try LLM first if API key is present
    headlines = [row_title(row) for row in rows if row_title(row)]
    llm_result = analyze_catalysts_via_llm(headlines)
    if llm_result:
        print(f"LLM detected catalyst: {llm_result}")
        return llm_result
        
    # 2. Fallback to local regex-based matcher
    for row in rows:
        text = row_text(row)
        text_lower = text.lower()
        for giant, sector in GLOBAL_GIANTS_MAP.items():
            if giant in text_lower:
                for action in CATALYST_ACTIONS:
                    if action in text_lower:
                        return {
                            "triggered": True,
                            "giant": giant,
                            "sector": sector,
                            "action": action,
                            "headline": row_title(row)
                        }
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect policy/news catalyst evidence.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"))
    parser.add_argument("--code-limit", type=int, default=8)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    codes = read_codes(run_dir / "candidate_seed.csv", args.code_limit)
    sources: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []

    for kind, arg in [("cctv", args.date), ("sina", None), ("em", None)]:
        payload = run_with_timeout(kind, arg, timeout=15)
        sources[kind] = {"ok": payload.get("ok"), "error": payload.get("error"), "rows": len(payload.get("rows") or [])}
        rows.extend(payload.get("rows") or [])

    stock_news: dict[str, Any] = {}
    for code in codes[:5]:
        payload = run_with_timeout("stock_news", code, timeout=12)
        stock_news[code] = {
            "ok": payload.get("ok"),
            "error": payload.get("error"),
            "headlines": [row_title(row) for row in (payload.get("rows") or [])[:5]],
        }
        rows.extend(payload.get("rows") or [])

    catalyst = classify_news(rows)
    core_ok = bool(sources.get("sina", {}).get("ok") and sources.get("em", {}).get("ok"))
    if core_ok:
        status = "ok"
    else:
        ok_sources = sum(1 for item in sources.values() if item.get("ok"))
        if ok_sources >= 1:
            status = "partial"
        else:
            status = "failed"
    classification_texts = [row_title(row) for row in rows]
    for item in stock_news.values():
        classification_texts.extend(str(text) for text in (item.get("headlines") or []) if text)

    generated_at = datetime.now().isoformat(timespec="seconds")
    output = {
        "generated_at": generated_at,
        "date": args.date,
        "source_status": status,
        "sources": sources,
        "stock_news": stock_news,
        "catalyst_themes": catalyst,
        "global_macro_catalyst": detect_global_catalyst(rows),
        "classification_summary": classify_news_texts(classification_texts),
        "evidence_quality": evidence_quality(status, sources, generated_at),
        "source_quality": source_quality_summary(status, sources, stock_news),
        "policy_news_score": min(100, 45 + sum(item["hit_count"] for item in catalyst[:3]) * 5) if catalyst else 35,
        "notes": [
            "新闻/政策模块为公共源 best-effort 采集，源失败不阻断行情筛选。",
            "政策级和行业级可有限加分，公司级负面优先扣分，情绪级只能小幅加分。",
            "主题命中只用于纸面研究权重，不构成投资建议。",
        ],
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if status != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
