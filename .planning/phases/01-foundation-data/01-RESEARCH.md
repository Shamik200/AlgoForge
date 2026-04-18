# Phase 1: Foundation & Data Infrastructure - Research

**Researched:** 2026-04-18
**Confidence:** HIGH

## Key Technical Findings

### 1. yfinance Data Feed

- yfinance is NOT natively async — wrap calls in `ThreadPoolExecutor` via `asyncio.run_in_executor()`
- Rate limiting: ~2000 requests/hour; use batch `yf.download()` for multiple symbols
- Data availability: up to ~2 years of 1-min data, unlimited daily/weekly/monthly
- Returns pandas DataFrames; convert to Pydantic models at ingestion boundary
- Corporate actions (splits, dividends) handled automatically in adjusted data
- Use `interval` parameter: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
- Use `period` parameter: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max

### 2. Redis Data Storage

- **Redis TimeSeries module**: Best for OHLCV; native time-series operations, downsampling, retention
- If RedisTimeSeries unavailable: use Sorted Sets (score = timestamp, member = JSON OHLCV)
- Key naming: `ohlcv:{symbol}:{timeframe}` (e.g., `ohlcv:AAPL:1m`)
- Use Redis Pipelining for batch writes (10x throughput improvement)
- AOF with `appendfsync everysec` for persistence (balance safety vs performance)
- `redis-py` 5.0+ supports async via `redis.asyncio` — use this for non-blocking ops

### 3. Configuration with Pydantic Settings

- Use `pydantic-settings` with `YamlConfigSettingsSource` — native YAML support
- Priority: env vars > .env file > YAML file > default values
- Nested models for structured config sections (database, data_feeds, risk, strategies)
- `SettingsConfigDict(extra="ignore")` to prevent crashes from unknown YAML keys
- `env_prefix` for namespaced env var overrides (e.g., `ALGOFORGE_REDIS_HOST`)
- Validate at startup — fail fast with clear error messages

### 4. Multi-Timeframe Resampling

- pandas `resample()` with `Grouper` for OHLCV aggregation rules:
  - Open = first, High = max, Low = min, Close = last, Volume = sum
- Resample from base timeframe (1-min) to higher timeframes on-the-fly
- Cache resampled data in Redis to avoid recomputation
- Key per timeframe: `ohlcv:{symbol}:{timeframe}` with TTL for short timeframes

### 5. Event Bus Pattern

- For Phase 1: simple `asyncio.Queue` based event bus (no external dependencies)
- Event types: MarketDataEvent, SystemEvent (startup, shutdown, error)
- Future phases will add: SignalEvent, OrderEvent, FillEvent
- Type-safe events using Pydantic models
- Pub/Sub pattern with topic-based routing

### 6. Project Structure

- `pyproject.toml` with `hatchling` or `setuptools` build backend
- `src/` layout (not flat) for proper import isolation
- Dependency groups: core, ml, dev, test
- Entry point via `__main__.py` for `python -m algoforge`

## Implementation Approach

1. **Wave 1**: Project scaffolding (pyproject.toml, directory structure, config system)
2. **Wave 2**: Core data models (Pydantic OHLCV, events, enums) + event bus
3. **Wave 3**: Redis integration + yfinance feed adapter + resampling
4. **Wave 4**: Integration test: end-to-end data flow from yfinance → Redis multitimeframe

## Validation Architecture

### Testable Behaviors
- Config loads and validates from YAML with correct defaults
- yfinance adapter returns normalized OHLCV data
- Redis stores and retrieves candle data correctly
- Resampler produces accurate multi-timeframe candles
- Event bus delivers events to subscribers
- Invalid config values are rejected at startup

### Validation Methods
- pytest with hypothesis for property-based testing of resampling logic
- Integration test with real yfinance data (small symbol list)
- Redis mock for unit tests, real Redis for integration tests

---
*Research for Phase 1: Foundation & Data Infrastructure*
*Researched: 2026-04-18*

## RESEARCH COMPLETE
