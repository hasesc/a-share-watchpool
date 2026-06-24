"""Benchmark matching helpers for A-share watchpool review logs."""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_STRATEGY_VERSION = "a-share-watchpool-v0.9.0"


@dataclass(frozen=True)
class BenchmarkProfile:
    code: str
    name: str
    match_keywords: tuple[str, ...]
    note: str


BENCHMARK_PROFILES = [
    BenchmarkProfile(
        code="399006",
        name="半导体/电子成长基准（创业板指fallback）",
        match_keywords=("半导体", "芯片", "封装", "PCB", "存储", "功率器件", "消费电子", "光学", "电子"),
        note="细分电子指数或 ETF 行情不可用时，使用创业板指作为成长风格 fallback。",
    ),
    BenchmarkProfile(
        code="399006",
        name="AI算力/软件成长基准（创业板指fallback）",
        match_keywords=("AI", "算力", "服务器", "云", "软件", "信创", "数据中心", "光模块", "通信"),
        note="AI/算力链暂用创业板指作为成长风格 fallback。",
    ),
    BenchmarkProfile(
        code="000905",
        name="机器人/高端制造基准（中证500fallback）",
        match_keywords=("机器人", "机床", "工业母机", "自动化", "高端制造", "设备"),
        note="制造业中盘属性较强，使用中证500 fallback。",
    ),
    BenchmarkProfile(
        code="000905",
        name="新能源/周期制造基准（中证500fallback）",
        match_keywords=("新能源", "锂电", "储能", "光伏", "风电", "电池", "化工", "有色", "材料"),
        note="新能源和周期制造暂用中证500 fallback。",
    ),
    BenchmarkProfile(
        code="000300",
        name="金融消费蓝筹基准（沪深300fallback）",
        match_keywords=("银行", "保险", "证券", "白酒", "食品", "家电", "医药", "消费", "大盘", "蓝筹"),
        note="大盘蓝筹和稳定消费默认基准。",
    ),
    BenchmarkProfile(
        code="000852",
        name="小盘题材基准（中证1000fallback）",
        match_keywords=("小盘", "题材", "专精特新", "北交所"),
        note="小盘题材默认基准。",
    ),
    BenchmarkProfile(
        code="399006",
        name="创业板指",
        match_keywords=("成长",),
        note="成长风格默认基准；行业 ETF/指数不可用时优先使用。",
    ),
    BenchmarkProfile(
        code="000300",
        name="沪深300",
        match_keywords=("银行", "保险", "证券", "白酒", "消费", "家电", "医药", "大盘", "蓝筹"),
        note="大盘蓝筹和稳定消费默认基准。",
    ),
    BenchmarkProfile(
        code="000905",
        name="中证500",
        match_keywords=("周期", "化工", "机械", "材料", "有色", "军工", "新能源", "中盘"),
        note="中盘周期和制造默认基准。",
    ),
    BenchmarkProfile(
        code="000852",
        name="中证1000",
        match_keywords=("小盘", "题材", "专精特新", "北交所"),
        note="小盘题材默认基准。",
    ),
]


def infer_benchmark(sector: str | None, name: str | None = None) -> BenchmarkProfile:
    text = f"{sector or ''} {name or ''}".lower()
    for profile in BENCHMARK_PROFILES:
        for keyword in profile.match_keywords:
            if keyword.lower() in text:
                return profile
    return BENCHMARK_PROFILES[0]


def benchmark_map_for_report(sector: str | None, name: str | None = None) -> dict[str, str]:
    profile = infer_benchmark(sector, name=name)
    return {
        "benchmark_code": profile.code,
        "benchmark_name": profile.name,
        "benchmark_match_note": profile.note,
    }

