# State: AlgoForge v2

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-18)

**Core value:** Risk management is supreme — no trade executes without passing every risk check.
**Current focus:** Phase 5 — HMM Probabilistic Regime Detector

## Current Phase

**Phase:** 6 → ✅ COMPLETE
**Status:** Executed — Momentum Signal Family
**Goal:** Implement the Momentum signal family (time-series + VWAP deviation) with KAMA/ATR/Volume confirmations.
**Context:** Outputs standard `SignalResult` (z-score [-1, 1]). Integrates HMM regime multiplier (1.3x boost in trends).
**Plans:** executed inline | **Tests:** 482/482 passing

## Progress

| Phase | Name | Status | Plans |
|-------|------|--------|-------|
| 1 | Foundation & Data Infrastructure | ✅ Complete (2026-04-19) | 4/4 |
| 2 | Async Event Bus & Message Architecture | ✅ Complete (2026-04-19) | inline |
| 3 | Orthogonal Indicator Engine (7 Indicators) | ✅ Complete (2026-04-19) | inline |
| 4 | Structural Confluence Detection | ✅ Complete (2026-04-19) | inline |
| 5 | HMM Probabilistic Regime Detector | ✅ Complete (2026-04-19) | inline |
| 6 | Signal Family: Momentum | ✅ Complete (2026-04-19) | inline |
| 7 | Signal Family: Mean Reversion | ⬜ Not started | 0 |
| 8 | Signal Family: Breakout / Volatility | ⬜ Not started | 0 |
| 9 | Signal Family: Structural Confluence | ⬜ Not started | 0 |
| 10 | Risk Management Engine | ⬜ Not started | 0 |
| 11 | Signal Combination & Conviction Framework | ⬜ Not started | 0 |
| 12 | Multi-Target SL/TP & Partial Exits | ⬜ Not started | 0 |
| 13 | Order Management System (OMS) | ⬜ Not started | 0 |
| 14 | Paper Trading Engine | ⬜ Not started | 0 |
| 15 | Backtesting Engine | ⬜ Not started | 0 |
| 16 | Alpha Decay Monitoring System | ⬜ Not started | 0 |
| 17 | Signal Family: Microstructure / Order Flow | ⬜ Not started | 0 |
| 18 | Pairs & Cointegration Trading | ⬜ Not started | 0 |
| 19 | Fundamental Analysis Module (LangGraph) | ⬜ Not started | 0 |
| 20 | ML/DL/RL Pipeline | ⬜ Not started | 0 |
| 21 | Dashboard & Monitoring | ⬜ Not started | 0 |
| 22 | Live Trading Bridge & Production | ⬜ Not started | 0 |

## Decisions Log

| Date | Decision | Phase |
|------|----------|-------|
| 2026-04-19 | Full roadmap rewrite: 31-strategy → 5-signal-family architecture | All |
| 2026-04-19 | HMM (4-state) replaces ADX-threshold regime detection | 5 |
| 2026-04-19 | 7 orthogonal indicators (zero redundancy) replace 14 indicators | 3 |
| 2026-04-19 | KAMA replaces 6 static EMAs as primary trend indicator | 3 |
| 2026-04-19 | Signal combination framework with decorrelation is THE core edge | 11 |
| 2026-04-19 | Alpha decay monitoring from day one — no strategy runs unmonitored | 16 |
| 2026-04-19 | Async event bus (asyncio + Redis Streams) is the architectural backbone | 2 |
| 2026-04-19 | Multi-target SL/TP: TP1 (50% at 1.5R), TP2 (30% at 2.5R), TP3 (20% trailing) | 12 |
| 2026-04-19 | Market-agnostic from day 1 (stocks/crypto/forex via config) | 1 |
| 2026-04-19 | Risk management has absolute veto power over all signals | 10 |
| 2026-04-19 | Event-driven backtesting only (no vectorized — prevents lookahead bias) | 15 |
| 2026-04-19 | Paper trading before live trading (mandatory validation) | 14 |
| 2026-04-19 | Broker API deferred — adapter interfaces only for v2 | 22 |
| 2026-04-19 | TimescaleDB + Redis dual storage (hot/cold) | 1 |
| 2026-04-19 | YFinance (universal) + Binance (crypto) + AlphaVantage (forex) feed adapters | 1 |
| 2026-04-19 | BaseFeed ABC + FeedFactory for pluggable provider selection | 1 |
| 2026-04-19 | Per-market YAML configs (stocks_india, stocks_us, crypto, forex) | 1 |
| 2026-04-19 | Intraday/Swing timeframe mode configs | 1 |
| 2026-04-19 | Hybrid event transport: asyncio.Queue (hot) + Redis Streams (durable) | 2 |
| 2026-04-19 | Hierarchical correlation IDs: event_id + parent_id + correlation_id | 2 |
| 2026-04-19 | Worker pool (20 workers) for 100+ instrument concurrency | 2 |
| 2026-04-19 | Event types migrated from dataclass to Pydantic BaseModel | 2 |
| 2026-04-19 | FillEvent added for order lifecycle completion | 2 |

| 2026-04-19 | Two-tier engine: 8 core always computed + optional tools | 3 |
| 2026-04-19 | Pure NumPy KAMA and ROC indicator implementations | 3 |
| 2026-04-19 | Unlimited in-memory caching granularity maintained | 3 |

| 2026-04-19 | Structural models (PriceLevel, ConfluenceZone) | 4 |
| 2026-04-19 | Swing point detection and ATR-based clustering | 4 |
| 2026-04-19 | Structural Confluence Engine (aggregating MAs, POC, Swings) | 4 |

| 2026-04-19 | Pre-smoothed features for HMM to avoid regime flip-flopping | 5 |
| 2026-04-19 | Offline weekly scheduled retraining for HMM | 5 |
| 2026-04-19 | Probability entropy threshold used for Uncertainty Flag | 5 |
| 2026-04-19 | Intraday session resets for VWAP tracking | 6 |
| 2026-04-19 | Centralized SignalResult model enforcing standard [-1, 1] scores | 6 |

---
*Last updated: 2026-04-19 — Phase 6 complete — 482 tests — advancing to Phase 7*
