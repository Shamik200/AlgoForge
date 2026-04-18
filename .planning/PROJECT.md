# AlgoForge — Institutional-Grade Algorithmic Trading System

## What This Is

An institutional-grade, HFT-level algorithmic trading system that combines fundamental analysis (AI-powered agentic workflows), multi-timeframe technical analysis (31 strategies across 5 market regimes), and ML/DL/RL models — all gated by a risk management engine with absolute veto power. The system is market-agnostic (stocks, crypto, forex selected at runtime), supports two operational modes (intraday trading and swing/investment), and executes through a high-fidelity paper trading engine before any live capital is deployed.

## Core Value

**Risk management is supreme.** No trade executes without passing every risk check. A strategy is only as good as its risk management — this system protects capital first, grows it second.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Three-module sequential pipeline: Fundamental → Technical → Execution
- [ ] Market-agnostic architecture: stocks (Indian/US), crypto, forex — config-driven, no code changes
- [ ] Fundamental Analysis Module with 4 LangChain/LangGraph agents (news/sentiment, financial screener, sector/macro, stock selector)
- [ ] Real-time news ingestion and NLP sentiment analysis (FinBERT or LLM-based)
- [ ] Financial statement screening with exhaustive metrics (valuation, profitability, growth, leverage, efficiency, cash flow, quality, ownership)
- [ ] Confidence scoring (0–100) and position allocation weights per instrument
- [ ] Technical Analysis Module with market regime detection (trending, range, breakout, reversal, liquidity trap)
- [ ] Primary Strategy: User's Trendline-Pullback Strategy generating >50% of all trades
- [ ] Multi-timeframe S/R detection (1D/1H for trading, 1M/1Y for investment)
- [ ] Algorithmic trendline construction (15min/5min for trading, 1W/1D for investment)
- [ ] EMA (5, 9, 21), RSI, ADX, ATR indicator suite on execution timeframe
- [ ] Candlestick pattern recognition at trendline touches with momentum confirmation
- [ ] SL/TP at trendline-S/R intersections with ATR buffer, minimum 1:2 R:R
- [ ] 30 secondary strategies across 5 market regime categories
- [ ] Two operational timeframe modes: Intraday Trading (1min execution, 15min–1h hold) and Swing/Investment (1H/4H execution, 1week–1month hold)
- [ ] Risk management engine with per-trade controls (1–2% max risk, mandatory SL, 1:2 min R:R)
- [ ] Portfolio-level risk controls (sector limits, directional limits, VaR, correlation, drawdown kill switch)
- [ ] Dynamic risk adjustment based on VIX, ATR, drawdown state, confidence scores
- [ ] ML/DL/RL model integration (XGBoost, LSTM/Transformer, PPO/SAC RL, ensemble stacking)
- [ ] Walk-forward training pipeline with no lookahead bias
- [ ] Paper trading engine with slippage, commission, latency simulation on any market
- [ ] Event-driven backtesting engine with Monte Carlo simulation
- [ ] Live trading bridge with modular broker adapter pattern (Zerodha, Alpaca, Binance, IBKR)
- [ ] Next.js monitoring dashboard with real-time performance analytics
- [ ] Kelly Criterion / risk-parity position sizing with sector concentration limits

### Out of Scope

- Broker API integration (deferred — adapter interfaces only, implementations later)
- Options/futures/derivatives trading — equities, crypto spot, and forex spot only for v1
- Social/copy trading features
- Mobile application — web dashboard only

## Context

**Origin**: The user is an active intraday trader with a specific personal trading methodology: draw S/R on higher timeframes (1D/1H), construct trendlines on mid timeframes (15min/5min), execute on 1min chart with EMA/RSI/ADX/ATR confirmation + candlestick pattern validation at trendline touches, trade only with the bigger trend direction (buy at lower trendline in uptrend, sell at upper trendline in downtrend), and wait for momentum confirmation before entry. This personal strategy must be the dominant signal source (>50% of trades).

**Trading Philosophy**: The user emphasizes that advanced strategies only matter when rare market conditions occur — the focus is on basic, high-frequency strategies that play out repeatedly. The system should be biased toward the user's trendline-pullback approach for most trades, with other strategies filling in for range, breakout, reversal, and trap market conditions.

**Architecture**: The system uses an agentic AI workflow (LangChain + LangGraph) for fundamental analysis with 4 specialized agents, a rule-based + ML-enhanced technical analysis engine, and a paper/live execution layer. All three modules run sequentially — no trades without fundamental screening first.

**Market Support**: System must support Indian Stocks (NSE/BSE), US Stocks, Crypto, and Forex through configuration. User selects market at runtime. No hardcoded market assumptions.

**Paper Trading Capital**: ₹1,00,00,000 (1 Crore INR) or $100,000 USD depending on selected market.

**Dashboard**: Next.js for fastest, best-looking production UI with real-time WebSocket updates.

**Prior Work**: A comprehensive master prompt document exists at the project root capturing all 31 strategies, indicator parameters, risk rules, ML model architectures, tech stack choices, and project structure in full detail.

## Constraints

- **Tech Stack**: Python 3.11+ (backend), Next.js/TypeScript (dashboard), LangChain/LangGraph (agents)
- **Performance**: Signal-to-order latency < 50ms within application; handle 1000+ instruments concurrently
- **Data**: Must use TA-Lib/pandas-ta for indicators; TimescaleDB/InfluxDB for time-series storage
- **Risk**: Every trade must have mandatory stop loss — non-negotiable; max 1–2% risk per trade
- **Architecture**: Event-driven with async/await; YAML-driven configuration; Pydantic data models
- **Quality**: Type hints everywhere, pytest + hypothesis testing, structured JSON logging (structlog)
- **Deployment**: Docker + Docker Compose
- **No Lookahead Bias**: Event-driven backtesting only, no vectorized backtesting

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Market-agnostic from day 1 | User trades multiple markets; avoid rebuilding architecture per market | — Pending |
| Next.js over Streamlit for dashboard | User wants fastest + best-looking UI; Next.js is production-grade with real-time WebSocket support | — Pending |
| Trendline-Pullback as >50% dominant strategy | Mirrors user's actual trading methodology; proven personal edge | — Pending |
| Fundamental analysis gates technical analysis | Ensures trades only on fundamentally sound instruments; prevents trading garbage | — Pending |
| Paper trading before live trading | Risk mitigation — validate system before deploying real capital | — Pending |
| Event-driven backtesting (not vectorized) | Prevents lookahead bias; realistic simulation of live conditions | — Pending |
| Broker API deferred to adapter interfaces | Avoid coupling to specific broker; user will provide API details later | — Pending |
| RL for position sizing (not just rules) | Institutional-grade adaptive sizing; PPO/SAC can learn optimal allocation | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-18 after initialization*
