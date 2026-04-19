# Phase 1: Foundation & Data Infrastructure - Context

**Gathered:** 2026-04-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the foundational data infrastructure: async config system, Pydantic data models, multi-source market data feeds (YFinance + Binance + Alpha Vantage), TimescaleDB persistent storage with Redis caching, data normalization, and multi-timeframe resampling (1min through 1M). Upgrade existing v1 modules incrementally — no clean slate.

</domain>

<decisions>
## Implementation Decisions

### Data Storage (D-01)
- **D-01:** Use **Redis + TimescaleDB** dual storage — Redis as real-time cache (current bars, latest prices, session state), TimescaleDB (PostgreSQL extension) as persistent historical store. Hot/cold separation. TimescaleDB gives SQL-based analytics, continuous aggregates for resampling, and data retention policies.

### Data Feed Adapters (D-02, D-03)
- **D-02:** Wire up **3 data feeds** for full asset class coverage using free APIs:
  - **YFinance** (already built) — US Stocks, Indian Stocks (NSE/BSE), basic crypto & forex fallback
  - **Binance API** — Crypto real-time WebSocket, no API key required for market data
  - **Alpha Vantage** — Forex pairs (free tier: 25 req/min with free API key)
- **D-03:** Use **modular adapter pattern** — each feed implements a common interface so adding future feeds (Polygon.io, Zerodha Kite, IBKR) is just a new adapter class with no core changes.

### Market-Specific Configuration (D-04, D-05)
- **D-04:** Create **full per-market YAML configs** — separate files for `stocks_india.yaml`, `stocks_us.yaml`, `crypto.yaml`, `forex.yaml`. Each defines: trading hours, fee structure (commission model, STT/GST for India, maker/taker for crypto), lot sizes, tick sizes, symbol format/prefix, available timeframes, and default instrument universe.
- **D-05:** Create **per-timeframe-mode configs** — `intraday.yaml` and `swing.yaml` defining which timeframes map to structure/trend/execution layers as specified in the refined prompt §2.1.

### Existing Code Treatment (D-06)
- **D-06:** **Incremental upgrade** — keep v1 code as the working base. Refactor module by module as each phase touches it. Phase 1 specifically upgrades `data/`, `core/config.py`, `core/models.py`, and adds TimescaleDB storage. The rest stays untouched until its phase arrives. 378 existing tests must keep passing throughout.

### Agent's Discretion
- Choice of TimescaleDB client library (psycopg2 vs asyncpg — prefer asyncpg for async compatibility)
- Binance and Alpha Vantage adapter implementation details (WebSocket vs REST polling)
- Redis cache TTL and eviction strategy
- Data normalization pipeline internals (cleaning, NaN handling, timezone standardization)
- TimescaleDB table schema design (hypertables, chunk intervals, compression policies)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & Design
- `refined_trading_system_prompt.md` — Master system design document; §2.1 for timeframe modes, Tech Infrastructure section for data pipeline architecture and technology stack
- `.planning/PROJECT.md` — Project constraints (Python 3.11+, async/await, Pydantic, YAML configs, structlog)
- `.planning/ROADMAP.md` — Phase 1 success criteria (6 items)

### Existing Code (incremental upgrade base)
- `src/algoforge/core/config.py` — Current YAML config system (RedisConfig, DataFeedConfig, Settings)
- `src/algoforge/core/models.py` — Current Pydantic data models (OHLCV, Signal) with Redis key generation
- `src/algoforge/core/constants.py` — Market, Timeframe, Direction, MarketRegime enums
- `src/algoforge/data/feeds/` — YFinance adapter (working, keep and extend)
- `src/algoforge/data/pipeline.py` — Data pipeline with resampling logic
- `src/algoforge/data/storage/redis_store.py` — Redis sorted set storage (keep as cache layer)
- `config/settings.yaml` — Current base config (extend, don't replace)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/config.py`: Pydantic-based YAML config loader — extend with new market/timeframe models
- `core/models.py`: OHLCV model with Redis serialization — add TimescaleDB serialization
- `core/constants.py`: Market/Timeframe/Direction enums — add missing timeframes (4H, 1W, 1M)
- `data/feeds/yfinance_feed.py`: Working YFinance adapter — use as template for Binance/AlphaVantage adapters
- `data/pipeline.py`: Resampling logic (up to 1D) — extend with 1W, 1M aggregation
- `data/storage/redis_store.py`: Redis adapter — keep as cache layer, add TimescaleDB adapter alongside

### Established Patterns
- Pydantic BaseModel for all config and data types
- structlog for structured JSON logging
- pytest for testing with unit test fixtures
- Enum-based constants for type safety (Market, Timeframe, Direction)

### Integration Points
- `core/config.py` Settings class needs new fields for TimescaleDB, Binance, Alpha Vantage
- `data/storage/` needs new `timescale_store.py` alongside existing `redis_store.py`
- `data/feeds/` needs new `binance_feed.py` and `alphavantage_feed.py`
- `config/` needs new market YAML files and timeframe mode YAML files

</code_context>

<specifics>
## Specific Ideas

- User wants **all possible stocks, forex, and crypto** coverage — not just a subset. The 3-feed combo (YFinance + Binance + Alpha Vantage) covers this with free APIs.
- Timeframe modes directly from refined prompt §2.1: Intraday (1D/1H structure → 15min/5min trend → 1min execution) and Swing (1M/1Y structure → 1W/1D trend → 1H/4H execution).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation-data*
*Context gathered: 2026-04-19*
