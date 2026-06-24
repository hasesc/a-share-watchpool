# Example Schema Notes

This document describes the offline example files under `examples/`. The examples are fictional or anonymized and exist only to document data shape, testing expectations, and compliance boundaries.

## Shared Policy Fields

Example files should make their data policy explicit when practical:

| Field | Type | Meaning |
|------|------|---------|
| `public_data_only` | boolean | The example represents public-data research only. |
| `fictional_or_anonymized` | boolean | The file does not contain real personal, account, or trading data. |
| `broker_connection` | boolean | Must be `false`; examples must not imply broker connectivity. |
| `real_trade_instruction` | boolean | Must be `false`; examples must not contain real orders. |
| `investment_advice` | boolean | Must be `false`; examples must not provide investment advice. |

## `sample_data_health.json`

Purpose: show the minimum shape of a data health result.

Expected fields:

| Field | Type | Notes |
|------|------|-------|
| `generated_at` | string | ISO-like timestamp for the sample. |
| `stage` | string | Pipeline stage, such as `pre_market`. |
| `health_status` | string | Example value: `ok`. |
| `can_rank_paper_watch` | boolean | Whether watchlist construction can proceed in paper mode. |
| `snapshot_rows` | number | Fictional row count. |
| `quote_source` | string | Fictional or public source label. |
| `risk_check` | string | Data availability status. |
| `execution_check` | string | Data availability status. |
| `notes` | array | Boundary notes for readers and tests. |

## `sample_watchlist.json`

Purpose: show a small watchlist payload for public-data research and paper simulation records.

Expected fields:

| Field | Type | Notes |
|------|------|-------|
| `generated_at` | string | ISO-like timestamp for the sample. |
| `stage` | string | Pipeline stage. |
| `strategy_version` | string | Research strategy version label. |
| `data_policy` | object | Must state no broker connection or real trade instruction. |
| `watchlist_entries` | array | Fictional watchlist entries. |

Each `watchlist_entries` item may include:

| Field | Type | Notes |
|------|------|-------|
| `symbol` | string | Fictional code such as `SAMPLE001`. |
| `name` | string | Fictional display name. |
| `sector` | string | Fictional sector label. |
| `selection_bucket` | string | Research bucket such as `short_term` or `medium_term`. |
| `driver_score` | number | Research score only. |
| `risk_penalty` | number | Research score only. |
| `execution_score` | number | Research score only. |
| `execution_action` | string | Research label, not a trading command. |
| `reason_tags` | array | Explanation tags. |
| `paper_simulation_action` | string | Record-only paper simulation action. |
| `notes` | string | Human-readable boundary note. |

## `sample_report_summary.json`

Purpose: show an offline report summary that can be validated without live market data.

Expected fields:

| Field | Type | Notes |
|------|------|-------|
| `report_type` | string | Example value: `offline_sample`. |
| `generated_at` | string | ISO-like timestamp for the sample. |
| `title` | string | Report title. |
| `summary` | string | Short fictional summary. |
| `data_policy` | object | Must state public-only, fictional/anonymized, no broker, no real trade instruction. |
| `data_health` | object | Embedded data health summary. |
| `watchlist_overview` | object | Aggregate counts only. |
| `paper_simulation` | object | Record-only paper simulation section. |
| `audit_notes` | array | Compliance and data boundary notes. |

## Forbidden Fields

Example files must not include fields that imply real trading, broker connectivity, or account identity, including:

- `buy_order`
- `sell_order`
- `broker_api`
- `account_id`
- `account_number`
- `client_id`
- `trade_password`

The pytest suite checks these fields for the current example fixtures.
