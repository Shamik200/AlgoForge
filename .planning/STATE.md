# State: AlgoForge v2

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-18)

**Core value:** Risk management is supreme — no trade executes without passing every risk check.
**Current focus:** Phase 2 — Async Event Bus & Message Architecture

## Current Phase

**Phase:** 1 → ✅ COMPLETE
**Status:** Executed — all 4 plans across 3 waves
**Goal:** Project scaffolding, async config, data pipeline, TimescaleDB, multi-timeframe resampling
**Context:** Full roadmap rewrite — 22 phases aligned with refined trading system prompt (5 signal families, HMM regime, signal combination)
**Plans:** 4/4 complete | **Tests:** 427/427 passing

## Progress

| Phase | Name | Status | Plans |
|-------|------|--------|-------|
| 1 | Foundation & Data Infrastructure | ✅ Complete (2026-04-19) | 4/4 |
| 2 | Async Event Bus & Message Architecture | ⬜ Not started | 0 |
| 3 | Orthogonal Indicator Engine (7 Indicators) | ⬜ Not started | 0 |
| 4 | Structural Confluence Detection | ⬜ Not started | 0 |
| 5 | HMM Probabilistic Regime Detector | ⬜ Not started | 0 |
| 6 | Signal Family: Momentum | ⬜ Not started | 0 |
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

---
*Last updated: 2026-04-19 — Phase 1 complete — 427 tests — advancing to Phase 2*
