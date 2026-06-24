import json
from pathlib import Path


FORBIDDEN_TRADE_FIELDS = {
    "buy_order",
    "sell_order",
    "broker_api",
    "account_id",
    "account_number",
    "client_id",
    "trade_password",
}


def load_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def iter_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from iter_keys(child)
    elif isinstance(value, list):
        for item in value:
            yield from iter_keys(item)


def test_sample_data_health_is_valid_json():
    data = load_json("examples/sample_data_health.json")

    assert data["health_status"] == "ok"
    assert data["can_rank_paper_watch"] is True


def test_sample_watchlist_is_valid_json_without_real_trade_fields():
    data = load_json("examples/sample_watchlist.json")

    assert isinstance(data["watchlist_entries"], list)
    assert data["data_policy"]["broker_connection"] is False
    assert data["data_policy"]["real_trade_instruction"] is False

    keys = set(iter_keys(data))
    assert keys.isdisjoint(FORBIDDEN_TRADE_FIELDS)


def test_sample_report_summary_is_valid_json_without_real_trade_fields():
    data = load_json("examples/sample_report_summary.json")

    assert data["data_policy"]["public_data_only"] is True
    assert data["data_policy"]["broker_connection"] is False
    assert data["data_policy"]["real_trade_instruction"] is False

    keys = set(iter_keys(data))
    assert keys.isdisjoint(FORBIDDEN_TRADE_FIELDS)
