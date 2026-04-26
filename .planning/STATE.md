# State: AlgoForge v2

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-18)

**Core value:** Risk management is supreme — no trade executes without passing every risk check.
**Current focus:** Phase 5 — HMM Probabilistic Regime Detector

## Current Phase

**Phase:** 19 → ✅ COMPLETE
**Status:** Executed — Fundamental Analysis Module
**Goal:** AI-powered fundamental pipeline with 4 agents: news sentiment, financial screener, macro analyst, stock selector.
**Context:** Sequential pipeline with gate_score gating. Modular agent classes with mock LLM calls for testability.
**Plans:** executed inline | **Tests:** 554/554 passing

## Progress

| Phase | Name | Status | Plans |
|-------|------|--------|-------|
| 1 | Foundation & Data Infrastructure | ✅ Complete (2026-04-19) | 4/4 |
| 2 | Async Event Bus & Message Architecture | ✅ Complete (2026-04-19) | inline |
| 3 | Orthogonal Indicator Engine (7 Indicators) | ✅ Complete (2026-04-19) | inline |
| 4 | Structural Confluence Detection | ✅ Complete (2026-04-19) | inline |
| 5 | HMM Probabilistic Regime Detector | ✅ Complete (2026-04-19) | inline |
| 6 | Signal Family: Momentum | ✅ Complete (2026-04-19) | inline |
| 7 | Signal Family: Mean Reversion | ✅ Complete (2026-04-19) | inline |
| 8 | Signal Family: Breakout / Volatility | ✅ Complete (2026-04-19) | inline |
| 9 | Signal Family: Structural Confluence | ✅ Complete (2026-04-20) | inline |
| 10 | Risk Management Engine | ✅ Complete (2026-04-20) | inline |
| 11 | Signal Combination & Conviction Framework | ✅ Complete (2026-04-22) | inline |
| 12 | Multi-Target SL/TP & Partial Exits | ✅ Complete (2026-04-22) | inline |
| 13 | Order Management System (OMS) | ✅ Complete (2026-04-23) | inline |
| 14 | Paper Trading Engine | ✅ Complete (2026-04-24) | inline |
| 15 | Backtesting Engine | ✅ Complete (2026-04-25) | inline |
| 16 | Alpha Decay Monitoring System | ✅ Complete (2026-04-25) | inline |
| 17 | Signal Family: Microstructure / Order Flow | ✅ Complete (2026-04-25) | inline |
| 18 | Pairs & Cointegration Trading | ✅ Complete (2026-04-25) | inline |
| 19 | Fundamental Analysis Module (LangGraph) | ✅ Complete (2026-04-26) | inline |
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
| 2026-04-19 | Strict structural RSI divergence matching using Phase 4 swing logic | 7 |
| 2026-04-19 | Mean Reversion HMM regime guard (>0.40 probability to activate) | 7 |
| 2026-04-19 | Anti-trend steamroller guard (disables if momentum > 0.80) | 7 |
| 2026-04-19 | Stateless Breakout Failure detection pattern (prev_close > high AND close < high) | 8 |
| 2026-04-19 | TTM Squeeze Volatility detection (Bollinger Bands inside Keltner Channels) | 8 |
| 2026-04-20 | Dynamic proximity bounds (+/- 0.5 ATR) for testing structural levels | 9 |
| 2026-04-20 | MTF structural overlap multipliers (1.5x) for signal conviction | 9 |
| 2026-04-20 | Fractional Kelly Position Sizing with fallback to Fixed Fractional | 10 |
| 2026-04-20 | O(1) Cached Correlation Matrix limit evaluation | 10 |
| 2026-04-22 | Rolling 100-period z-score normalization bounded to [-1.0, 1.0] | 11 |
| 2026-04-22 | Sharpe-ratio driven Softmax weighting and Tie-breaker Tie-breaker redundancy culling | 11 |
| 2026-04-22 | Tranche architecture (50/30/20) with staggered R-multiple exits | 12 |
| 2026-04-22 | Time-based breakeven and closed-candle trailing stops for runners | 12 |
| 2026-04-23 | Deterministic order state machine (NEW→SUBMITTED→FILLED/CANCELLED/REJECTED) | 13 |
| 2026-04-23 | SQLite-backed OMS with idempotent submission and candle-based limit expiry | 13 |
| 2026-04-24 | Multi-asset class friction modeling (commissions, STT, slippage, latency jitter) | 14 |
| 2026-04-24 | Square-root market impact modeling for oversized orders | 14 |
| 2026-04-25 | Fast-path backtest loop bridging real Paper Engine execution logic | 15 |
| 2026-04-25 | Expanding window WFO and Trade sequence Monte Carlo shuffling | 15 |
| 2026-04-25 | Alpha Decay Monitor with Z-score hit rate deviation and health multipliers | 16 |
| 2026-04-25 | Combination Engine updated: post-Softmax health throttling and re-normalization | 16 |
| 2026-04-25 | VWAP deviation tracker with session reset and σ-based mean-reversion signals | 17 |
| 2026-04-25 | Volume imbalance (Chaikin proxy) and OBV divergence for L1 fallback | 17 |
| 2026-04-25 | Engle-Granger cointegration test with simplified ADF for pairs detection | 18 |
| 2026-04-25 | Spread z-score trading at ±2σ with rolling re-validation | 18 |
| 2026-04-26 | 4-agent fundamental pipeline: news sentiment, screener, macro, selector | 19 |
| 2026-04-26 | Gate score mechanism blocking technically valid but fundamentally broken trades | 19 |

---
*Last updated: 2026-04-26 — Phase 19 complete — 554 tests — advancing to Phase 20*
