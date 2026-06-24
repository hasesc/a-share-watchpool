from pathlib import Path


def test_disclaimer_contains_required_safety_statements():
    disclaimer = Path("DISCLAIMER.md").read_text(encoding="utf-8")

    required_phrases = [
        "非投资建议",
        "不连接任何券商接口",
        "不产生真实买卖指令",
    ]

    for phrase in required_phrases:
        assert phrase in disclaimer
