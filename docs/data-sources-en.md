# Data Sources Explanation

The System uses only publicly accessible market data and information interfaces. It does not rely on paid data services, does not connect to broker interfaces, and does not read real account credentials or personal trading data.

---

## Primary Data Sources

### AKShare (Preferred)

- **Purpose**: Market snapshots, K-line history, trading calendar.
- **Installation**: `pip install akshare`
- **Interfaces**:
  - `stock_zh_a_spot()`: Live spot snapshots for Shanghai, Shenzhen, and Beijing A-shares.
  - `stock_zh_a_daily()`: Daily historical prices for individual stocks.
  - `tool_trade_date_hist_sina()`: Trading calendar history.

### Eastmoney (Backup)

- **Purpose**: Backup source for market spot data; provides more complete fields for certain values (e.g. turnover rate, market capitalization).
- **Limitation**: Page flipping can be unstable in some network environments; used as a fallback only.

### Tencent Finance

- **Purpose**: Cross-validation of single ticker prices; used for data health checks.

---

## Data Quality Levels

| Level | Meaning | Impact on Primary Watchlist |
|-------|---------|-----------------------------|
| `complete` | Market snapshot, candidate features, and risk checks are all complete. | Normal watchlist generation. |
| `partial` | Spot data is available, but announcement/sector/execution quality is incomplete. | Watchlist capped at 1 entry, or none generated. |
| `stale` | Data is delayed or timestamps are ambiguous. | No primary watchlist is generated. |
| `failed` | Data sources are completely unavailable. | Outputs a data health failure report. |

---

## Data Integrity Gating

After each execution of `monitor_data_health.py`, a `data_health.json` file is generated:

```json
{
  "health_status": "ok",
  "can_rank_paper_watch": true,
  "snapshot_rows": 5527,
  "quote_source": "complete",
  "risk_check": "complete",
  "execution_check": "complete"
}
```

If `can_rank_paper_watch=false`, the System will not generate a primary watchlist. This is a built-in safety protection mechanism.

---

## Data Usage Rules

- Each pipeline execution saves raw spot data under `workspace/data/watchpool/<yyyymmdd>_<stage>/`.
- Record precise data timestamps to prevent mixing cross-day data.
- Do not use data without explicit timestamp verification.
- Watchlist seeds (`candidate_seed.csv`) are raw inputs and must not be treated as final watchlist entries.
- Do not upload real account details, real trading logs, API keys, cookies, tokens, or personal identity data.

---

## News Catalyst Data

`collect_policy_news.py` gathers news across the following dimensions:

| Category | Weight Limit | Description |
|----------|--------------|-------------|
| Policy Catalyst | Medium-High | National policy, central bank actions, etc. |
| Industry Catalyst | Medium | Industry prosperity, trending themes. |
| Corporate Positive | Low | Better-than-expected earnings, large orders. |
| Corporate Negative | Block | Direct demotion of watchlist candidates (overrides other weights). |
| Sentiments & Rumors | Extremely Low | Reference only, no scoring bonus. |

> If news data quality is marked as `partial` (e.g. some news feeds failed), the primary watchlist capacity is capped at 1 candidate.
