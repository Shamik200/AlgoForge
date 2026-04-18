# Project Research Summary

**Project:** AlgoForge — Institutional-Grade Algorithmic Trading System
**Domain:** Algorithmic Trading (HFT-level, multi-market, multi-strategy)
**Researched:** 2026-04-18
**Confidence:** HIGH

## Executive Summary

AlgoForge is an institutional-grade algorithmic trading system that operates as a three-module sequential pipeline: Fundamental Analysis (AI-powered stock selection) → Technical Analysis (31 strategies across 5 market regimes) → Execution (paper/live trading). The system is market-agnostic, supporting Indian stocks, US stocks, crypto, and forex through configuration-driven adapters.

The recommended approach is a Python-first event-driven architecture with async/await for concurrent I/O, Polars for high-performance data processing, and a Next.js dashboard for real-time monitoring. The system prioritizes the user's personal trendline-pullback strategy (>50% of all trades) while supporting 30 secondary strategies activated based on detected market regime. Risk management sits on the critical path with absolute veto power over every trade.

Key risks include lookahead bias in backtesting (mitigated by event-driven architecture), overfitting of strategy parameters (mitigated by walk-forward validation), and ML model overconfidence on non-stationary financial data (mitigated by treating ML as confirmation layer, not primary signal). The phased build order prioritizes the data pipeline and risk engine before any strategy implementation.

## Key Findings

### Recommended Stack

Python 3.11+ for all backend logic (strategy, ML, data pipeline) with Next.js + TypeScript for the monitoring dashboard. The system avoids the common trap of trying to achieve microsecond latency — retail API-based trading has inherent 50-200ms latency, so signal quality matters more than speed.

**Core technologies:**
- Python 3.11+ (asyncio): Core engine — strategy logic, ML training, data processing
- Polars 1.x: High-performance DataFrames for backtesting (10-50x faster than pandas for large datasets)
- TA-Lib + pandas-ta: Comprehensive indicator library (14 indicators, C-based for speed)
- LangChain + LangGraph: AI agent orchestration for fundamental analysis
- XGBoost + PyTorch + Stable-Baselines3: ML/DL/RL model stack
- TimescaleDB: Time-series storage for OHLCV data (hypertable compression)
- Redis: Real-time caching and event pub/sub
- Next.js 14+: Production-grade dashboard with WebSocket real-time updates

### Expected Features

**Must have (table stakes):**
- Multi-timeframe OHLCV data pipeline with real-time feeds
- 14 technical indicators (EMA, RSI, ADX, ATR, MACD, Bollinger, etc.)
- Algorithmic S/R detection and trendline construction
- Market regime detection (5 regimes)
- 31 trading strategies with regime-based activation
- Complete risk management engine with kill switch
- Event-driven backtesting engine
- Paper trading with slippage/commission simulation
- Two timeframe modes (intraday + swing/investment)

**Should have (competitive):**
- AI-powered fundamental analysis with 4 agents
- ML/DL/RL model integration for signal enhancement
- Next.js real-time monitoring dashboard
- Dynamic risk adjustment (VIX, drawdown, confidence-based)

**Defer (v2+):**
- Live trading bridge (after paper trading validates profitability)
- Options/derivatives support
- Multi-broker simultaneous execution

### Architecture Approach

Event-driven architecture where all components communicate via an internal event bus (MarketData → Signal → Order → Fill events). This design enables identical code paths for backtesting and live trading — the only difference is the event source (historical replay vs. live WebSocket). All 31 strategies inherit from a base Strategy class and declare which market regimes activate them. The risk manager sits as a mandatory checkpoint between signal generation and order execution.

**Major components:**
1. **Orchestration Engine** — Coordinates Module 1→2→3 sequential pipeline
2. **Data Feed Manager** — Connects to market data sources, normalizes to standardized OHLCV
3. **Technical Analysis Pipeline** — Indicators → Structure → Regime → Strategy → Signal
4. **Risk Management Engine** — Per-trade + portfolio-level validation with veto power
5. **Execution Engine** — Paper trading simulator + broker adapter pattern for live
6. **Fundamental Analysis Pipeline** — 4 LangGraph agents for stock selection
7. **ML Pipeline** — Feature engineering, model training, real-time inference

### Critical Pitfalls

1. **Lookahead bias** — Event-driven backtesting only; execute on next bar, never current; strict temporal ordering
2. **Overfitting** — Walk-forward validation mandatory; max 3-5 parameters per strategy; in-sample vs out-of-sample gap < 0.5 Sharpe
3. **Risk as afterthought** — Build risk engine BEFORE strategies; mandatory SL; veto power
4. **Ignoring transaction costs** — Model slippage + fees in paper trading; test at 2x slippage for robustness
5. **Wrong regime strategy application** — Mandatory regime detection before strategy activation; skip trades when regime is unclear

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Foundation & Data Infrastructure
**Rationale:** Everything depends on clean, multi-timeframe market data
**Delivers:** Project scaffolding, config system, data pipeline, database setup
**Addresses:** Data pipeline, OHLCV storage, normalization
**Avoids:** Data quality pitfall; survivorship bias

### Phase 2: Indicator Engine & Structural Analysis
**Rationale:** Indicators and S/R/trendlines are prerequisites for ALL strategies
**Delivers:** 14 technical indicators, S/R detection, trendline construction
**Addresses:** Core indicator needs; user's strategy foundations
**Avoids:** Indicator multicollinearity by design

### Phase 3: Market Regime Detection
**Rationale:** Must classify market regime BEFORE activating any strategy
**Delivers:** 5-regime classifier (trending, range, breakout, reversal, trap)
**Avoids:** Wrong-regime strategy application pitfall

### Phase 4: Primary Strategy (Trendline-Pullback)
**Rationale:** User's dominant strategy (>50% of trades); validate core logic first
**Delivers:** Complete 4-step trendline-pullback strategy with candlestick confirmation
**Addresses:** User's specific trading methodology

### Phase 5: Risk Management Engine
**Rationale:** Must be complete before adding more strategies or execution
**Delivers:** Per-trade limits, portfolio controls, position sizer, circuit breaker
**Avoids:** Risk-as-afterthought pitfall

### Phase 6: Candlestick Patterns & Signal Aggregation
**Rationale:** Candlestick confirmation required by primary strategy; signal pipeline needed before execution
**Delivers:** Pattern recognition, signal ranking, deduplication

### Phase 7: Paper Trading Engine
**Rationale:** Need realistic execution simulation before backtesting makes sense
**Delivers:** Paper trading with slippage, commission, latency modeling
**Avoids:** Ignoring transaction costs pitfall

### Phase 8: Backtesting Engine
**Rationale:** Validate primary strategy before building 30 more strategies
**Delivers:** Event-driven backtester, walk-forward validation, Monte Carlo
**Avoids:** Lookahead bias and overfitting pitfalls

### Phase 9: Secondary Strategies — Trending
**Rationale:** Most common regime after user's primary approach
**Delivers:** 7 trending market strategies (EMA Pullback, MA Crossover, etc.)

### Phase 10: Secondary Strategies — Range & Breakout
**Rationale:** Second and third most common regimes
**Delivers:** 7 range strategies + 7 breakout strategies

### Phase 11: Secondary Strategies — Reversal & Liquidity
**Rationale:** Less frequent but important for completeness
**Delivers:** 5 reversal strategies + 4 liquidity/trap strategies

### Phase 12: Fundamental Analysis Module
**Rationale:** Complex AI module; build after technical module is validated
**Delivers:** 4 LangGraph agents, news sentiment, financial screening, stock selection
**Uses:** LangChain, LangGraph, FinBERT/LLM

### Phase 13: ML/DL/RL Model Integration
**Rationale:** Enhancement layer; needs baseline rule-based performance for comparison
**Delivers:** XGBoost classifier, LSTM/Transformer forecaster, RL position sizer, ensemble
**Avoids:** ML overconfidence pitfall

### Phase 14: Dashboard & Monitoring
**Rationale:** System should run headless first; dashboard is observation layer
**Delivers:** Next.js real-time monitoring dashboard
**Uses:** Next.js, TypeScript, WebSocket

### Phase 15: Live Trading Bridge & Production
**Rationale:** Only after paper trading validates profitability
**Delivers:** Broker adapters, Docker deployment, comprehensive testing
**Addresses:** Production readiness

### Phase Ordering Rationale

- Data → Indicators → Structure → Regime → Strategy: strict dependency chain (each requires the previous)
- Risk engine built BEFORE adding secondary strategies: prevents risk-as-afterthought
- Paper trading and backtesting before expanding strategy count: validate core before adding complexity
- Fundamental analysis after technical: sequential pipeline requires Module 1 but it's separate enough to build later
- ML/DL models last in technical: need baseline performance to compare against
- Dashboard near end: system must work headless first; dashboard is observation only

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2:** S/R detection and trendline algorithms — sparse open-source implementations; need custom algorithms
- **Phase 12:** LangGraph agent orchestration — rapidly evolving library; verify API compatibility
- **Phase 13:** RL for position sizing — limited proven implementations; may need extensive experimentation

Phases with standard patterns (skip research-phase):
- **Phase 1:** Data pipeline — well-established patterns with WebSocket + TimescaleDB
- **Phase 9-11:** Secondary strategies — well-documented indicator-based strategies
- **Phase 14:** Dashboard — standard Next.js + WebSocket architecture

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Well-established Python trading ecosystem; verified library versions |
| Features | HIGH | User's requirements are extremely detailed; clear feature list |
| Architecture | HIGH | Event-driven architecture is industry standard for trading systems |
| Pitfalls | HIGH | Well-documented failure modes in quantitative finance literature |

**Overall confidence:** HIGH

### Gaps to Address

- **Trendline algorithm specifics:** Few production-quality open-source implementations; will need to research algorithmic approaches (linear regression, Hough transform, swing point connection) during Phase 2 planning
- **RL for position sizing:** Limited proven implementations in retail trading; may need to experiment with reward function design
- **LangGraph agent coordination:** Library is evolving rapidly; API may change; pin versions carefully

## Sources

### Primary (HIGH confidence)
- Industry research on institutional trading architecture (2025)
- "Advances in Financial Machine Learning" — Marcos López de Prado
- QuantConnect Lean Engine (open-source backtesting reference)

### Secondary (MEDIUM confidence)
- r/algotrading community consensus on stack choices (2024-2025)
- LangChain/LangGraph official documentation (evolving rapidly)
- Stable-Baselines3 documentation for RL approaches

### Tertiary (LOW confidence)
- Specific RL reward functions for position sizing — needs experimentation
- LangGraph production reliability for multi-agent trading workflows — few production deployments documented

---
*Research completed: 2026-04-18*
*Ready for roadmap: yes*
