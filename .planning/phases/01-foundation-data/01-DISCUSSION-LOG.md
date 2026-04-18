# Phase 1: Foundation & Data Infrastructure - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-18
**Phase:** 01-foundation-data
**Areas discussed:** Data source, Database & dev environment, Config structure, Historical data strategy

---

## Data Source for Development

| Option | Description | Selected |
|--------|-------------|----------|
| yfinance (free) | Free Yahoo Finance API, no API key, REST-based, good for development | ✓ |
| Paid API (Alpha Vantage, Polygon) | Higher quality, rate limits, requires API key | |
| WebSocket streaming (Binance) | Real-time, but crypto-only, requires account | |

**User's choice:** yfinance — free, no API key needed
**Notes:** User explicitly wants free API for development. Build adapter interface for future paid feeds.

---

## Database & Dev Environment

| Option | Description | Selected |
|--------|-------------|----------|
| Redis (in-memory) | Sub-millisecond reads, fastest option, local install | ✓ |
| TimescaleDB (persistent) | SQL-based time-series, better for large historical data | |
| Redis + TimescaleDB (hybrid) | Redis for real-time, TimescaleDB for historical | |

**User's choice:** Redis — "fastest database like redis, Local Dev Env"
**Notes:** User prioritizes speed. TimescaleDB deferred to later phases when large-scale persistence is needed. Local dev environment, no Docker Compose.

---

## Config File Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Single settings.yaml | Everything in one file, simple, easy to find | ✓ |
| Split files (settings + strategies + risk + markets) | More organized, harder to find things | |
| TOML instead of YAML | Python-native (pyproject.toml style), less common in trading | |

**User's choice:** Single settings.yaml
**Notes:** User wants simplicity — one file for everything.

---

## Historical Data Bootstrap

| Option | Description | Selected |
|--------|-------------|----------|
| Real-time focus, minimal historical | Collect only what's needed for current timeframe mode | ✓ |
| Full historical download (1+ year) | More data for backtesting from day 1 | |
| Incremental collection over time | Start thin, accumulate as system runs | |

**User's choice:** Agent's discretion — per timeframe mode (1Y/1M for investment, 1D/1H for trading)
**Notes:** User said "we only need real time data" — historical is secondary, collected as needed for configured timeframe mode. ML/backtesting data needs will be addressed in those phases.

---

## Agent's Discretion

- Redis data structure design
- Resampling implementation approach
- Test instrument selection
- Error handling patterns

## Deferred Ideas

- TimescaleDB for persistent storage (future phase)
- Docker Compose orchestration (Phase 15)
- WebSocket streaming feeds (when broker APIs provided)
