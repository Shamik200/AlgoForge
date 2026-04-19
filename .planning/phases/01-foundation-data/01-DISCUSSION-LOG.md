# Phase 1: Foundation & Data Infrastructure - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-19
**Phase:** 01-foundation-data
**Areas discussed:** Data Storage Strategy, Data Feed Adapters, Market-Specific Config Structure, Existing Code Treatment

---

## Data Storage Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Redis + TimescaleDB | Redis as real-time cache, TimescaleDB as persistent historical store. Institutional standard hot/cold separation. | ✓ |
| Redis + Parquet Files | Redis as cache, Parquet files on disk for historical data. Simpler but no real-time queries. | |
| Redis Only | Keep current approach. Simple but limited for multi-year backtesting. | |

**User's choice:** Redis + TimescaleDB
**Notes:** User selected the recommended institutional-standard approach without hesitation.

---

## Data Feed Adapters

| Option | Description | Selected |
|--------|-------------|----------|
| YFinance only | Keep what works, add others later. | |
| YFinance + one real-time | Add Polygon.io or Binance alongside YFinance. | |
| Full multi-source | YFinance + Polygon.io + CoinGecko + Alpha Vantage. | |

**User's choice:** Custom — "I want it to include all the possible stocks, forex and crypto so you can consider one or more free API source as per that"
**Notes:** User wants maximum asset class coverage with free APIs. Resolved to: YFinance (stocks US/India) + Binance (crypto real-time WebSocket) + Alpha Vantage (forex). All free, modular adapter pattern for future expansion.

---

## Market-Specific Config Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Full market configs | Separate YAML per market with trading hours, fees, lot sizes, symbol format, universe. Plus timeframe mode configs. | ✓ |
| Lightweight configs | Just timeframe mappings and symbol prefixes per market. | |
| Single unified config | One settings.yaml with nested market sections. | |

**User's choice:** Full market configs
**Notes:** Selected the most detailed option — each market gets its own comprehensive YAML.

---

## Existing Code Treatment

| Option | Description | Selected |
|--------|-------------|----------|
| Incremental upgrade | Keep v1 code, refactor module by module as each phase touches it. 378 tests keep passing. | ✓ |
| Clean slate | Delete src/algoforge/, rebuild from scratch. Lose all working code. | |
| Parallel build | New src/algoforge_v2/ alongside existing. Zero risk but confusion potential. | |

**User's choice:** Incremental upgrade
**Notes:** Lower risk approach — upgrade what's touched, keep everything else working.

## Agent's Discretion

- TimescaleDB client library choice (asyncpg preferred)
- Binance/Alpha Vantage adapter implementation details
- Redis cache TTL and eviction strategy
- Data normalization pipeline internals
- TimescaleDB schema design

## Deferred Ideas

None — discussion stayed within phase scope.
