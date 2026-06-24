import json
from pathlib import Path


PAPER_SIM_FILES = [
    Path("workspace/paper-sim/scripts/paper_sim_portfolio.py"),
    Path("workspace/paper-sim/scripts/paper_sim_strategy_lab.py"),
    Path("workspace/paper-sim/config.json"),
]

FORBIDDEN_BROKER_TERMS = [
    "easytrader",
    "xtquant",
    "qmt",
    "broker_api",
    "submit_order",
    "place_order",
    "trade_password",
    "account_id",
    "account_number",
]


def test_paper_sim_config_is_explicitly_paper_only():
    config = json.loads(Path("workspace/paper-sim/config.json").read_text(encoding="utf-8"))

    assert config["paper_only"] is True
    notes = config["notes"].lower()
    assert "no broker connection" in notes
    assert "no real orders" in notes
    assert "no investment advice" in notes


def test_paper_simulator_contains_required_boundary_statement():
    source = Path("workspace/paper-sim/scripts/paper_sim_portfolio.py").read_text(encoding="utf-8")

    assert "never connects to a broker" in source
    assert "never places real orders" in source
    assert "不连接券商" in source
    assert "不构成投资建议" in source


def test_paper_sim_files_do_not_reference_broker_integrations():
    combined = "\n".join(path.read_text(encoding="utf-8").lower() for path in PAPER_SIM_FILES)

    for term in FORBIDDEN_BROKER_TERMS:
        assert term not in combined
