# Roadmap: AlgoForge

**Created:** 2026-04-18
**Milestone:** v1.0 — Complete Trading System
**Phases:** 15
**Granularity:** Fine
**Mode:** YOLO

## Phases

### Phase 1: Foundation & Data Infrastructure
**Goal:** Establish project scaffolding, configuration system, data pipeline, and database — the foundation everything else depends on.
**Requirements:** DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, CONF-01, CONF-02, CONF-03, CONF-04, CONF-05
**Depends on:** (none)
**UI hint:** no

**Success Criteria:**
1. System ingests live OHLCV candles from at least one data source and stores in TimescaleDB
2. Multi-timeframe resampling produces correct 5min/15min/1H/1D candles from 1-min data
3. YAML config loads market-specific settings without code changes
4. Data feed reconnects automatically after simulated disconnect
5. All data models validated by Pydantic schemas

---

### Phase 2: Technical Indicator Engine
**Goal:** Implement all 14 technical indicators with configurable parameters, computed efficiently across multiple timeframes.
**Requirements:** INDI-01, INDI-02, INDI-03, INDI-04, INDI-05, INDI-06, INDI-07, INDI-08, INDI-09, INDI-10, INDI-11, INDI-12, INDI-13, INDI-14
**Depends on:** Phase 1
**UI hint:** no

**Success Criteria:**
1. All 14 indicators compute correctly against reference values (TA-Lib verification)
2. Indicator values update in real-time as new candles arrive
3. Cached computation avoids redundant recalculation
4. Indicator engine processes 100 instruments × 6 timeframes within 1 second

---

### Phase 3: Structural Analysis (S/R + Trendlines)
**Goal:** Build algorithmic detection of support/resistance levels and trendline construction — the foundation of the primary strategy.
**Requirements:** STRU-01, STRU-02, STRU-03, STRU-04, STRU-05, STRU-06
**Depends on:** Phase 2
**UI hint:** no

**Success Criteria:**
1. S/R levels detected on 1D/1H timeframes with strength scoring match manual analysis on 5 test instruments
2. Trendlines connect 2-3+ swing points and correctly identify ascending/descending channels
3. Bigger trend direction (UP/DOWN/UNCLEAR) correctly classified on test data
4. Broken trendlines are invalidated and removed within 1 candle of the break

---

### Phase 4: Market Regime Detection
**Goal:** Classify each instrument's current market condition into one of 5 regimes, gating strategy activation.
**Requirements:** REGM-01, REGM-02, REGM-03, REGM-04
**Depends on:** Phase 2, Phase 3
**UI hint:** no

**Success Criteria:**
1. Regime classification outputs probabilities for all 5 regimes (not just a label)
2. Classification runs automatically before any strategy logic (mandatory gate verified)
3. ADX > 25 correctly triggers Trending regime; ADX < 20 correctly triggers Range
4. Regime changes are logged with timestamps for analysis

---

### Phase 5: Primary Strategy & Candlestick Patterns
**Goal:** Implement the user's trendline-pullback strategy (the dominant signal source) plus candlestick pattern recognition used for entry confirmation.
**Requirements:** PRIM-01, PRIM-02, PRIM-03, PRIM-04, PRIM-05, PRIM-06, PRIM-07, PRIM-08, PRIM-09, PRIM-10, PRIM-11, PRIM-12, CNDL-01, CNDL-02, CNDL-03
**Depends on:** Phase 3, Phase 4
**UI hint:** no

**Success Criteria:**
1. Strategy generates buy signals at lower trendline in uptrend with full 4-step confirmation
2. Strategy generates sell signals at upper trendline in downtrend with full 4-step confirmation
3. Strategy skips instruments when trend direction is unclear
4. All 12 candlestick patterns correctly detected against reference examples
5. Signals include SL/TP at trendline-S/R intersections with ATR buffer
6. Strategy rejects entries below 1:2 risk-reward ratio

---

### Phase 6: Risk Management Engine
**Goal:** Build the complete risk management system — per-trade controls, portfolio controls, position sizing, dynamic adjustment, and circuit breaker.
**Requirements:** RISK-01 to RISK-20, SIZE-01 to SIZE-04
**Depends on:** Phase 1, Phase 2
**UI hint:** no

**Success Criteria:**
1. System rejects any signal without a stop loss (verified by test)
2. No single trade risks more than 2% of capital
3. Portfolio-level checks prevent exceeding sector limits, daily loss limits, and drawdown kill switch
4. Position sizer calculates correct lot size from Kelly Criterion / risk-parity
5. Signal with no SL/TP is rejected before reaching execution
6. Circuit breaker halts all trading when market drops > 5% from open

---

### Phase 7: Paper Trading Engine
**Goal:** Build high-fidelity paper trading simulator with realistic slippage, commission, and latency modeling for any market.
**Requirements:** PAPR-01, PAPR-02, PAPR-03, PAPR-04, PAPR-05, PAPR-06
**Depends on:** Phase 5, Phase 6
**UI hint:** no

**Success Criteria:**
1. Paper trading executes signals with configurable slippage (0.05-0.1%)
2. Commission modeling matches real brokerage fees for at least 2 markets
3. Latency simulation adds 50-200ms delays between signal and fill
4. Paper trading runs on live market data with ₹1Cr / $100K capital
5. P&L calculation accounts for all fees, slippage, and taxes

---

### Phase 8: Backtesting Engine
**Goal:** Build event-driven backtester with walk-forward validation, Monte Carlo simulation, and comprehensive performance metrics.
**Requirements:** BACK-01, BACK-02, BACK-03, BACK-04, BACK-05, BACK-06, BACK-07
**Depends on:** Phase 7
**UI hint:** no

**Success Criteria:**
1. Backtester processes historical data one candle at a time (event-driven, verified no lookahead)
2. Walk-forward optimization splits data correctly into train/validate windows
3. Monte Carlo simulation with shuffled trades produces confidence intervals
4. All performance metrics computed: Sharpe, Sortino, Calmar, max drawdown, win rate, profit factor, expectancy
5. Primary strategy backtest produces >50% of trade signals
6. Transaction costs match paper trading engine

---

### Phase 9: Secondary Strategies — Trending & Range
**Goal:** Implement 15 secondary strategies for trending and range/sideways market regimes.
**Requirements:** TRND-01 to TRND-08, RANG-01 to RANG-07
**Depends on:** Phase 5, Phase 6
**UI hint:** no

**Success Criteria:**
1. All 8 trending strategies generate signals only when regime = Trending
2. All 7 range strategies generate signals only when regime = Range/Sideways
3. Each strategy inherits from base Strategy class with standardized interface
4. Strategy-specific parameters loaded from strategies.yaml config
5. All strategies backtested with positive expectancy in their target regime

---

### Phase 10: Secondary Strategies — Breakout, Reversal, Liquidity
**Goal:** Implement remaining 16 secondary strategies for breakout, reversal, and liquidity trap regimes.
**Requirements:** BRKT-01 to BRKT-07, REVS-01 to REVS-05, LIQD-01 to LIQD-04
**Depends on:** Phase 9
**UI hint:** no

**Success Criteria:**
1. All 7 breakout strategies activate on Breakout regime with volume/ATR confirmation
2. All 5 reversal strategies activate on Reversal/Transition regime
3. All 4 liquidity strategies detect false breakout / stop hunt patterns
4. Strategy orchestrator selects correct strategies based on detected regime
5. Full backtest with all 31 strategies shows primary strategy still >50% of trades

---

### Phase 11: Dual Timeframe Mode Integration
**Goal:** Ensure both Intraday Trading and Swing/Investment timeframe modes are fully functional with correct timeframe configurations.
**Requirements:** TIME-01, TIME-02, TIME-03, TIME-04
**Depends on:** Phase 10
**UI hint:** no

**Success Criteria:**
1. Intraday mode uses 1D/1H for S/R, 15min/5min for trendlines, 1min for execution
2. Swing mode uses 1M/1Y for S/R, 1W/1D for trendlines, 1H/4H for execution
3. Same strategy engine runs both modes with only timeframe config changed
4. User can run different instruments in different modes simultaneously

---

### Phase 12: Fundamental Analysis Module
**Goal:** Build AI-powered fundamental analysis pipeline with 4 LangGraph agents for stock selection, screening, and confidence scoring.
**Requirements:** FUND-01, FUND-02, FUND-03, FUND-04, FUND-05, FUND-06, FUND-07, FUND-08
**Depends on:** Phase 1
**UI hint:** no

**Success Criteria:**
1. News agent ingests and scores sentiment from at least 3 sources
2. Financial screener analyzes 30+ fundamental metrics per instrument
3. Sector/macro agent tracks at least 5 macro indicators
4. Stock selector produces ranked watchlist with confidence scores (0-100) and allocation weights
5. LangGraph workflow orchestrates all 4 agents with error recovery
6. Fundamental output gates technical analysis (sequential pipeline verified)

---

### Phase 13: ML/DL/RL Model Integration
**Goal:** Build, train, and deploy ML models as enhancement layers for trade direction prediction, price forecasting, and position sizing.
**Requirements:** MLAI-01 to MLAI-09
**Depends on:** Phase 8
**UI hint:** no

**Success Criteria:**
1. XGBoost/LightGBM classifier trained with walk-forward validation (no random split)
2. LSTM/Transformer produces price forecasts within reasonable error bands
3. PPO/SAC RL agent learns position sizing that improves risk-adjusted returns
4. Ensemble stacking combines model outputs coherently
5. ML-enhanced system improves Sharpe ratio by ≥ 0.3 vs rule-based only
6. SHAP analysis identifies top-10 features driving predictions
7. Models serve as confirmation layer (not replacing rule-based strategies)

---

### Phase 14: Dashboard & Monitoring
**Goal:** Build production-grade Next.js monitoring dashboard with real-time WebSocket updates, performance analytics, and kill switch.
**Requirements:** DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, DASH-06
**Depends on:** Phase 7
**UI hint:** yes

**Success Criteria:**
1. Dashboard displays live P&L and positions with sub-second WebSocket updates
2. Market regime shown per instrument with color-coded visualization
3. Per-strategy performance breakdown with win rate and P&L
4. Kill switch button flattens all positions and halts trading within 2 seconds
5. Backtesting results visualized with equity curve and drawdown chart
6. Dashboard is responsive and works on desktop browsers

---

### Phase 15: Live Trading Bridge & Production
**Goal:** Build broker adapter interfaces, gradual deployment pipeline, and production Docker deployment.
**Requirements:** LIVE-01, LIVE-02, LIVE-03, LIVE-04
**Depends on:** Phase 7, Phase 14
**UI hint:** no

**Success Criteria:**
1. Broker adapter interface defined with at least one placeholder implementation
2. Gradual deployment starts at 10% capital with scaling plan
3. Paper and live can run simultaneously for comparison (parallel running)
4. Kill switch works in both paper and live modes
5. Docker Compose spins up complete system (database, Redis, engine, dashboard)
6. Comprehensive test suite passes: unit, integration, and backtest validation

---

## Phase Dependency Graph

```
Phase 1 (Foundation)
  ├── Phase 2 (Indicators)
  │     ├── Phase 3 (S/R + Trendlines)
  │     │     ├── Phase 4 (Regime Detection)
  │     │     │     └── Phase 5 (Primary Strategy)
  │     │     │           ├── Phase 7 (Paper Trading) ──→ Phase 8 (Backtesting)
  │     │     │           │                                  └── Phase 13 (ML/DL/RL)
  │     │     │           └── Phase 9 (Trending+Range) ──→ Phase 10 (Breakout+Reversal+Liquidity)
  │     │     │                                                └── Phase 11 (Dual Timeframe)
  │     │     └── Phase 4
  │     └── Phase 6 (Risk Management)
  └── Phase 12 (Fundamental Analysis)

Phase 7 ──→ Phase 14 (Dashboard)
Phase 7 + Phase 14 ──→ Phase 15 (Live Trading + Production)
```

## Summary

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|-------------|-----------------|
| 1 | Foundation & Data | Data pipeline, config, database | 10 | 5 |
| 2 | Indicator Engine | 14 technical indicators | 14 | 4 |
| 3 | Structural Analysis | S/R detection + trendlines | 6 | 4 |
| 4 | Regime Detection | 5-class market regime classifier | 4 | 4 |
| 5 | Primary Strategy | Trendline-pullback + candlestick patterns | 15 | 6 |
| 6 | Risk Management | Per-trade + portfolio risk engine | 24 | 6 |
| 7 | Paper Trading | Realistic execution simulator | 6 | 5 |
| 8 | Backtesting | Event-driven historical validation | 7 | 6 |
| 9 | Trending & Range | 15 secondary strategies | 15 | 5 |
| 10 | Breakout/Reversal/Trap | 16 secondary strategies | 16 | 5 |
| 11 | Dual Timeframe | Intraday + Swing modes | 4 | 4 |
| 12 | Fundamental Analysis | 4 AI agents, LangGraph | 8 | 6 |
| 13 | ML/DL/RL | Model integration pipeline | 9 | 7 |
| 14 | Dashboard | Next.js monitoring UI | 6 | 6 |
| 15 | Live Trading | Broker bridge + production | 4 | 6 |
| **Total** | | | **118** | **77** |
