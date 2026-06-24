#!/usr/bin/env python3
"""Validate offline example fixtures.

This script intentionally uses only the Python standard library. It validates
fictional examples without touching live market data, broker systems, or local
runtime output.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = PROJECT_ROOT / "examples"

REQUIRED_EXAMPLES = [
    "sample_data_health.json",
    "sample_watchlist.json",
    "sample_report_summary.json",
]

FORBIDDEN_FIELDS = {
    "buy_order",
    "sell_order",
    "broker_api",
    "account_id",
    "account_number",
    "client_id",
    "trade_password",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_keys(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from iter_keys(child)
    elif isinstance(value, list):
        for item in value:
            yield from iter_keys(item)


def validate_data_policy(payload: dict[str, Any], path: Path) -> list[str]:
    errors: list[str] = []
    policy = payload.get("data_policy")
    if policy is None:
        return errors
    if not isinstance(policy, dict):
        return [f"{path.name}: data_policy must be an object"]

    expected_false = {
        "broker_connection": "must not imply broker connectivity",
        "real_trade_instruction": "must not imply real trading instructions",
        "investment_advice": "must not imply investment advice",
    }
    for key, message in expected_false.items():
        if policy.get(key) is not False:
            errors.append(f"{path.name}: data_policy.{key} must be false ({message})")

    if "public_data_only" in policy and policy.get("public_data_only") is not True:
        errors.append(f"{path.name}: data_policy.public_data_only must be true when present")
    if "fictional_or_anonymized" in policy and policy.get("fictional_or_anonymized") is not True:
        errors.append(f"{path.name}: data_policy.fictional_or_anonymized must be true when present")

    return errors


def validate_example(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        payload = load_json(path)
    except json.JSONDecodeError as exc:
        return [f"{path.name}: invalid JSON: {exc}"]

    keys = set(iter_keys(payload))
    forbidden = sorted(keys & FORBIDDEN_FIELDS)
    if forbidden:
        errors.append(f"{path.name}: forbidden fields present: {', '.join(forbidden)}")

    if isinstance(payload, dict):
        errors.extend(validate_data_policy(payload, path))
    else:
        errors.append(f"{path.name}: top-level JSON value must be an object")

    return errors


def validate_examples(examples_dir: Path = EXAMPLES_DIR) -> list[str]:
    errors: list[str] = []
    for filename in REQUIRED_EXAMPLES:
        path = examples_dir / filename
        if not path.exists():
            errors.append(f"{filename}: missing required example")
            continue
        errors.extend(validate_example(path))
    return errors


def main() -> int:
    errors = validate_examples()
    if errors:
        for error in errors:
            print(error)
        return 1
    print("examples validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
