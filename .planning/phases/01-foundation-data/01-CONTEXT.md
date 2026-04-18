# Phase 1: Foundation & Data Infrastructure - Context

**Gathered:** 2026-04-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish project scaffolding (Python package, pyproject.toml, directory structure), configuration system (single YAML file with validation), data pipeline (ingest OHLCV from yfinance → normalize → resample to multiple timeframes → store), and database setup (Redis for fast in-memory storage). This phase produces the foundation ALL other phases depend on — no strategies, no indicators, no risk management.

</domain>

<decisions>
## Implementation Decisions

### Data Source
- **D-01:** Use yfinance (free, no API key required) as the primary data feed for development and testing
- **D-02:** REST-based polling for data ingestion — no WebSocket streaming needed in Phase 1
- **D-03:** Build the DataFeed abstract interface so future feeds (Binance WebSocket, Zerodha, CCXT) can be added via adapter pattern without changing downstream code
- **D-04:** yfinance adapter is the first concrete implementation; adapter interface supports both REST and WebSocket patterns for future feeds

### Database & Dev Environment
- **D-05:** Redis as the primary data store — chosen for speed (in-memory, sub-millisecond reads)
- **D-06:** Redis stores real-time OHLCV candle data, computed indicators (future phases), and signal state
- **D-07:** Local development environment — no Docker Compose for Phase 1; Redis installed locally or via Docker single container
- **D-08:** Data persistence via Redis RDB/AOF snapshots — acceptable for development; production persistence decisions deferred
- **D-09:** TimescaleDB deferred to later phase if large-scale historical data storage is needed (ML training, multi-year backtesting)

### Config Structure
- **D-10:** Single `config/settings.yaml` file for ALL configuration (market selection, data feeds, database, logging, risk parameters, strategy parameters)
- **D-11:** Pydantic Settings model validates YAML at startup — reject invalid values immediately with clear error messages
- **D-12:** Secrets (API keys, database passwords) via environment variables, referenced in YAML with `${ENV_VAR}` syntax or .env file
- **D-13:** Market-specific sections within settings.yaml (not separate files per market) — keeps everything in one place

### Historical Data Strategy
- **D-14:** Real-time data is the priority — system designed for live signal generation, not historical analysis
- **D-15:** Historical data collection follows timeframe mode: Intraday Trading mode collects 1D/1H candles for S/R, 15min/5min for trendlines, 1min for execution; Swing/Investment mode collects 1Y/1M for S/R, 1W/1D for trendlines, 1H/4H for execution
- **D-16:** yfinance provides up to ~2 years of 1-min data and unlimited daily data — sufficient for Phase 1 development
- **D-17:** Data seeding: on startup, backfill missing historical candles from yfinance based on configured instruments and timeframes

### Agent's Discretion
- Redis data structure design (sorted sets for candles, hashes for metadata, streams for events)
- Exact resampling implementation (pandas resample vs custom aggregation)
- Logging format details within structlog JSON framework
- Test instrument selection for development (pick representative stocks/crypto for validation)
- Error handling patterns for yfinance rate limits and network failures
- pyproject.toml dependency grouping and optional extras

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Architecture
- `.planning/PROJECT.md` — Project vision, constraints, key decisions, market-agnostic requirement
- `.planning/research/ARCHITECTURE.md` — System overview diagram, component responsibilities, project structure, data flow
- `.planning/research/STACK.md` — Technology choices, versions, installation commands, alternatives
- `GEMINI.md` — Architecture conventions, code style, design decisions

### Requirements
- `.planning/REQUIREMENTS.md` §DATA-01 to DATA-05 — Data pipeline requirements (ingest, store, resample, normalize, reconnect)
- `.planning/REQUIREMENTS.md` §CONF-01 to CONF-05 — Configuration requirements (market selection, YAML params, risk config, market-specific settings, timeframe mode)

### Pitfalls
- `.planning/research/PITFALLS.md` §Pitfall 3 — Survivorship bias in data (data quality validation)
- `.planning/research/PITFALLS.md` §Integration Gotchas — Yahoo Finance rate limiting, TimescaleDB hypertables

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project, no existing code

### Established Patterns
- None yet — this phase ESTABLISHES the patterns (event bus, config loading, data models, adapter pattern)

### Integration Points
- This phase creates the foundation that ALL subsequent phases build on
- Phase 2 (indicators) will consume OHLCV data from Redis via the data pipeline built here
- Phase 3-5 (structure, regime, strategy) will read indicators computed on data stored here
- Phase 6 (risk management) will read portfolio state from Redis

</code_context>

<specifics>
## Specific Ideas

- User wants the "fastest database" — speed is the priority for data access, Redis chosen specifically for sub-millisecond reads
- User wants simplicity — single settings.yaml, local dev environment, no complex orchestration in Phase 1
- System must ask which market to target at startup via config — no hardcoded market assumptions
- Real-time data focus — historical data is secondary, collected as needed for the configured timeframe mode

</specifics>

<deferred>
## Deferred Ideas

- TimescaleDB for persistent historical storage — evaluate when ML/backtesting phases need multi-year data
- Docker Compose multi-service orchestration — defer to production readiness (Phase 15)
- WebSocket streaming feeds (Binance, Zerodha) — build adapter interface now, implement concrete adapters when broker APIs are provided

</deferred>

---

*Phase: 01-foundation-data*
*Context gathered: 2026-04-18*
