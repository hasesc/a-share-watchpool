# Watchlist Construction Model Explanation

Current Version: `a-share-watchpool-v0.9.0`  
Model ID: `sector-first-driver-risk-execution-v4`

---

## Model Design Principles

1. **Sector First**: Identify the main market sector themes first, then construct watchlist entries within those sectors.
2. **Data Gating**: If the public data is incomplete, the system will not generate a primary watchlist (better to have no data than wrong data).
3. **Risk First**: Corporate announcement risks (share reduction, share unlocking, regulatory actions) take priority over technical indicators.
4. **Three-Tier Time Horizons**: Short-term, medium-term, and long-term research samples are strictly separated and must not be mixed.
5. **Paper Simulation Priority**: All downstream actions are recorded as paper simulations and do not represent real trading commands.

---

## Overall Pipeline

```text
Market Emotion Gate (score >= 50)
       ↓
Sector Direction Identification (sector-first ranking)
       ↓
Watchlist Seed Generation (momentum seeds + low-position support backup pool)
       ↓
Execution Quality Checks (limit up status, turnover, volatility, chasing highs)
       ↓
Corporate Announcement Risk Filtering (share reductions, unlock pressure, regulatory warnings, lawsuits, ST/delisting)
       ↓
Comprehensive Scoring & Ranking (3D: driver, risk, execution)
       ↓
Watchlist Entry Gate (all hard constraints passed)
       ↓
Three-Tier Time Horizon Outputs
```

---

## Market Emotion Gate

| Emotion Score | Market Environment | Primary Watchlist Capacity Limit |
|---------------|--------------------|----------------------------------|
| >= 65 | Aggressive research mode | Max 3 watchlist entries |
| 50-64 | Exploratory research mode | Max 2 watchlist entries |
| < 50 | Defensive research mode | 0 short-term watchlist entries (only medium/long-term leads) |

Emotion score factors: limit-up stock counts, limit-down stock counts, rising/falling stock ratios, and volume changes.

---

## Sector First

1. Calculate daily performance of all market sectors (price increase, turnover, limit-up ratio).
2. Identify leading sector directions (Top themes).
3. Construct watchlist entries ONLY from these leading sectors; others are demoted to the general research pool.

---

## Three-Dimensional Scoring

### `driver_score` (0-100)

Reflects the comprehensive momentum and fundamental strength of the candidate:

| Sub-dimension | Description |
|---------------|-------------|
| Price & Volume Momentum | Relative price increase and turnover ranking in the market |
| Sector Centrality | Strength relative to peers in the same theme |
| News Catalysts | Policy-level or industry-level catalyst bonuses (bounded; overridden by company negative events) |
| Contradiction Penalties | `contradiction_score`: penalizes conflicting signals (e.g., high turnover but weak price gain, chasing extreme highs) |

**Primary Watchlist Entrance Threshold: >= 72**

### `risk_penalty` (0-100, lower is better)

| Risk Type | Penalty |
|-----------|---------|
| Share Reduction (Insider Selling) | High penalty |
| Share Unlocking Pressure | Medium penalty |
| Regulatory Warning / Punishment | High penalty |
| Lawsuits / Arbitration | Medium penalty |
| ST / Delisting Risk | Hard block |
| Recent Limit-up Failure (Zhaban) | Medium penalty |
| Overextended High Position | Medium penalty |

**Primary Watchlist Entrance Threshold: <= 8**

### `execution_score` (0-100)

| Check Item | Description |
|------------|-------------|
| Liquidity | Whether turnover rate and volume meet observability conditions |
| Chasing Risk | Whether the daily price increase exceeds preset research limits |
| Limit-up Strength | Consecutive limit-up durability vs. blowout risk |
| Volatility | High intraday volatility lowers observability score |

**Primary Watchlist Entrance Threshold: >= 70, and `execution_action` must be `clear`**

`execution_action` is a research tag and paper-simulation input only, not a buy, sell, or real trading order.

---

## Three-Tier Time Horizons

### Short-Term Watchlist Entries (1-10 trading days)

- Candidate must pass all hard entry conditions.
- Watchlist capacity is dynamically throttled by market emotion scores.
- When news sources are `partial`, the primary watchlist is capped at 1 entry.

### Medium-Term Trend Candidates (20-60 trading days)

- Candidates that fail some minor conditions (e.g. `risk_penalty` slightly over threshold) can be downgraded to this tier.
- No T+1/T+2/T+3 review scores are tracked; kept for observation logs only.
- Source: solid fundamental thesis but high short-term risk indicators.

### Long-Term Value Leads (60-240 trading days)

- Pure research leads, not participating in primary watchlist ranking.
- Source: low-position value stocks, institutional holdings, and other public data leads.
- Must not be mixed with short-term watchlist entries.

---

## Model Version Control Standards

- Before changing scoring weights, there must be >= 20 valid T+3 paper simulation entries.
- Every logic change must increment `STRATEGY_VERSION` in `render_watchpool_light.py`.
- Version format: `a-share-watchpool-vX.Y.Z`.
- Model changes must update the documentation, examples, and tests.

---

## Output Fields Explanation

Key JSON fields in `pre_market_top5.json`:

| Field | Type | Description |
|-------|------|-------------|
| `driver_score` | float | Momentum and fundamental strength score (0-100) |
| `risk_penalty` | float | Cumulative risk penalty (lower is better) |
| `execution_score` | float | Execution observability score (0-100) |
| `execution_action` | string | `clear` / `caution` / `block`, research tags only |
| `candidate_source` | string | `momentum_seed` / `low_position_support` |
| `reason_tags` | list | List of tags for adding/excluding candidate |
| `selection_bucket` | string | `short_term` / `medium_term` / `long_term` |
| `contradiction_score` | float | Conflicting signals penalty (lower is better) |
