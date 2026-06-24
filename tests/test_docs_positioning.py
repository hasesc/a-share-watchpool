from pathlib import Path


README = Path("README.md")
QUICK_START = Path("docs/quick-start.md")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_readme_uses_open_source_research_positioning():
    readme = read(README)

    assert "A股观察池 · A-Share Watchpool" in readme
    assert "基于公开行情数据的 A 股市场研究、纸面模拟与策略审计框架" in readme
    assert "[English]" in readme
    assert "public market data research, paper simulation, and strategy audit" in readme


def test_docs_use_canonical_clone_url():
    expected = "https://github.com/hasesc/a-share-watchpool.git"
    combined = read(README) + "\n" + read(QUICK_START)

    assert expected in combined
    assert "https://github.com/your-username/a-share-watchpool.git" not in combined


def test_readme_declares_core_compliance_boundaries():
    readme = read(README)

    required_phrases = [
        "仅使用公开行情和公开信息源",
        "不连接任何券商接口",
        "不产生真实买卖指令或自动下单动作",
        "不承诺收益，不提供荐股、跟单或投资建议",
        "学习、研究、数据管道实验、纸面模拟和策略审计",
    ]

    for phrase in required_phrases:
        assert phrase in readme


def test_quick_start_keeps_paper_simulation_boundary():
    quick_start = read(QUICK_START)

    assert "纸面模拟用于记录观察样本" in quick_start
    assert "不连接任何券商接口" in quick_start
    assert "不产生真实订单或真实买卖指令" in quick_start
