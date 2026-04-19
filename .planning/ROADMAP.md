# Roadmap: AlgoForge v2

**Created:** 2026-04-19
**Milestone:** v2.0 — Institutional-Grade 5-Signal-Family Architecture
**Phases:** 22
**Granularity:** Fine
**Mode:** YOLO

> Architecture redesign based on refined_trading_system_prompt.md — transforms the system from 31 pattern-matching strategies into 5 decorrelated signal families with HMM regime detection, signal combination framework, and alpha decay monitoring.

## Phases

### Phase 1: Foundation & Data Infrastructure
**Goal:** Project scaffolding, async config system, Pydantic data models, market data feeds, TimescaleDB storage, data normalization, and multi-timeframe resampling.
**Depends on:** (none)
**UI hint:** no

**Success Criteria:**
1. System ingests live OHLCV candles from at least one data source and stores in TimescaleDB
2. Multi-timeframe resampling produces correct 1min/5min/15min/1H/4H/1D/1W/1M candles
3. YAML config loads market-specific settings (stocks_india, stocks_us, crypto, forex) without code changes
4. Data feed reconnects automatically after simulated disconnect
5. All data models validated by Pydantic schemas
6. Both intraday and swing timeframe configs load correctly from YAML

---

### Phase 2: Async Event Bus & Message Architecture
**Goal:** Build the asyncio event-driven backbone with Redis Streams pub/sub, correlation IDs, and async data pipeline. Foundation for real-time multi-instrument processing.
**Depends on:** Phase 1
**UI hint:** no

**Success Criteria:**
1. Event bus processes MarketDataEvent, SignalEvent, OrderEvent, FillEvent with pub/sub
2. All data pipeline operations (feed, resampler, indicators) run as async tasks
3. System handles 100+ instruments concurrently via asyncio
4. Correlation IDs trace events from data ingestion through to order execution
5. Redis Streams used for durable event persistence with consumer groups
6. Signal-to-order internal latency < 50ms (excluding network)

---

### Phase 3: Orthogonal Indicator Engine (7 Indicators)
**Goal:** Implement the 7 orthogonal indicators (zero redundancy) plus supporting tools. Each measures a unique dimension of market behavior.
**Depends on:** Phase 1
**UI hint:** no

**Success Criteria:**
1. KAMA (10, 2, 30) — adaptive trend direction (replaces multiple EMAs)
2. ADX/DMI (14) — trend strength measurement
3. ROC (14) — pure momentum (replaces RSI/Stochastic/MACD for signals)
4. ATR (14) + Bollinger %B (20, 2σ) — volatility state and extremes
5. OBV + VWAP — volume-price divergence, institutional fair value
6. RSI (14) — used ONLY for divergence detection, not overbought/oversold signals
7. Supporting tools: Donchian Channels (20), Keltner Channels (20, 1.5×ATR), Volume Profile
8. All indicators compute correctly against reference values
9. Cached computation avoids redundant recalculation
10. Indicator engine processes 100 instruments × 6 timeframes within 1 second

---

### Phase 4: Structural Confluence Detection
**Goal:** Build objective, data-driven S/R detection using volume profile, swing point clustering, and dynamic MAs. Replaces subjective trendline analysis with quantifiable confluence scoring.
**Depends on:** Phase 3
**UI hint:** no

**Success Criteria:**
1. Volume Profile computes POC, Value Area High/Low for each session and rolling periods
2. Swing point clustering identifies levels with strength = touches × recency weight
3. Dynamic S/R from KAMA and 50/200 EMA as objective support/resistance
4. Confluence score (0–5) counts converging structural elements at each price level
5. Multi-timeframe agreement boosts confluence weight
6. Entry trigger: price approaches high-confluence level (score ≥ 3) with reversal microstructure

---

### Phase 5: HMM Probabilistic Regime Detector
**Goal:** Build 4-state Hidden Markov Model for market regime classification. Outputs continuous probability vectors — not binary labels — for adaptive signal family weighting.
**Depends on:** Phase 3
**UI hint:** no

**Success Criteria:**
1. HMM with 4 states (Trending-Up, Trending-Down, Mean-Reverting, Crisis/Stress) trained via hmmlearn
2. Input features: returns, realized volatility, volume ratio, cross-asset correlations, ATR percentile
3. Output: probability vector [P(trend_up), P(trend_down), P(mean_revert), P(crisis)]
4. Cross-asset regime confirmation using VIX, bond yields, DXY, crude oil
5. Regime disagreement between HMM and cross-asset → uncertainty flag → position size reduction
6. Rolling 252-day retraining window, retrained weekly without data leakage
7. No rapid flip-flopping: regime transitions are smooth probability shifts

---

### Phase 6: Signal Family 1 — Momentum
**Goal:** Implement the Momentum signal family with 3 sub-signals exploiting behavioral underreaction and herding.
**Depends on:** Phase 5
**UI hint:** no

**Success Criteria:**
1. Cross-sectional momentum: rank instruments by 1M/3M/6M/12M returns, favor top-ranked
2. Time-series momentum: long if trailing 12M return positive (with 1M skip for reversal avoidance)
3. Dual momentum: only take positions ranking high on both cross-sectional AND time-series
4. Intraday adaptation: 1H/4H momentum, VWAP-relative momentum with increasing deviation
5. Confirmation: KAMA direction + ROC volume confirmation + ATR 20th–80th percentile filter
6. Output: composite z-score normalized to [-1, +1], with 1.3× regime alignment boost when trending
7. Documented economic rationale for why this edge persists

---

### Phase 7: Signal Family 2 — Mean Reversion
**Goal:** Implement the Mean Reversion signal family for range-bound markets with activation guards.
**Depends on:** Phase 5
**UI hint:** no

**Success Criteria:**
1. VWAP z-score (40% weight): z-score of price relative to rolling 20-period VWAP
2. Bollinger %B extreme (30%): enter when %B < 0.05 or > 0.95 with RSI divergence confirmation
3. Pairs/relative value (30%): basic cointegration detection and spread trading (expanded in Phase 17)
4. Activation guard: only active when P(Mean-Reverting) > 40% from HMM
5. Anti-trend guard: disabled when momentum score is in top/bottom 20%
6. Hard stop: exit if price moves another 1σ against; time stop if no reversion within N candles
7. Output: composite z-score normalized to [-1, +1], 1.3× boost when regime = Mean-Reverting

---

### Phase 8: Signal Family 3 — Breakout / Volatility Expansion
**Goal:** Implement the Breakout signal family exploiting low-volatility compression releases with built-in failure handling.
**Depends on:** Phase 5
**UI hint:** no

**Success Criteria:**
1. Volatility squeeze: Bollinger Bands inside Keltner Channels with squeeze duration tracking
2. Volume-confirmed breakout: price breaks N-period Donchian high/low with volume > 2× 20-period avg
3. Opening Range Breakout (intraday only): first 15/30 min range with volume confirmation
4. Built-in failure handling: if breakout fails (returns inside range within N candles), immediately reverse
5. Activation guard: require P(Trending) or P(Breakout) > 50% before activation
6. Output: conviction score = f(squeeze_duration, volume_ratio, ATR_expansion, regime_prob) → [-1, +1]

---

### Phase 9: Signal Family 4 — Structural Confluence
**Goal:** Convert structural confluence detection (Phase 4) into a scored signal family that integrates with the combination framework.
**Depends on:** Phase 4, Phase 5
**UI hint:** no

**Success Criteria:**
1. Confluence score at each price level from Phase 4 drives signal generation
2. Entry trigger: price approaches confluence ≥ 3 with reversal micro-structure (volume climax, wick)
3. Direction determined by dominant regime + momentum score (not subjective trendline direction)
4. Higher weight when multiple timeframes agree on the same level
5. Output: structural confluence score normalized to [-1, +1]
6. Regime-aware: boosted in mean-reverting/ranging regimes, dampened in strong trends

---

### Phase 10: Risk Management Engine
**Goal:** Build the complete risk management system — per-trade controls, portfolio controls, position sizing (Kelly Criterion), dynamic adjustment, circuit breaker, and absolute veto power.
**Depends on:** Phase 1
**UI hint:** no

**Success Criteria:**
1. Per-trade: max 1–2% risk, max 5–10% position, min 1:2 R:R, mandatory SL on every trade
2. Daily loss limit (3–5%), weekly loss limit (7–10%), drawdown kill switch (15–20%)
3. Max consecutive losses (5) with cooldown (1hr intraday / 1 day swing)
4. Portfolio: sector limit (25%), directional limit (60%), max correlation (0.7), max open positions (5–10)
5. Kelly Criterion (fractional Kelly) + risk-parity position sizing
6. Dynamic adjustment: reduce size during high VIX/drawdown/low confidence, increase cautiously in trends
7. Circuit breaker: halt all trading if any symbol drops > 5% from session open
8. Liquidity check: position < 1% of daily volume, min 3× volume coverage
9. VaR (95%) must not exceed 3% of portfolio daily

---

### Phase 11: Signal Combination & Conviction Framework
**Goal:** Build the signal combination engine — THE core edge. Decorrelation matrix, adaptive Sharpe-based weighting, composite scoring with conviction-based position sizing.
**Depends on:** Phase 6, Phase 7, Phase 8, Phase 9
**UI hint:** no

**Success Criteria:**
1. All signal family outputs normalized to z-scores within their own history → common [-1, +1] scale
2. Rolling pairwise correlation between families; if correlation > 0.7, keep only higher-Sharpe family
3. Family weights adaptive based on rolling Sharpe ratio (not static)
4. Composite signal = Σ(signal_i × weight_i × regime_alignment_i)
5. Conviction thresholds: |composite| < 0.3 = skip, 0.3–0.6 = half position, ≥ 0.6 = full position
6. Pairwise signal family correlations < 0.3 in backtesting
7. No single signal family contributes > 40% of total P&L

---

### Phase 12: Multi-Target SL/TP & Partial Exits
**Goal:** Replace single SL/TP with ATR-anchored multi-target exits — TP1/TP2/TP3 scaling, trailing stops, time-based exit tightening.
**Depends on:** Phase 10, Phase 11
**UI hint:** no

**Success Criteria:**
1. ATR-anchored initial SL: 1.5×ATR in trending regime, 1.0×ATR in ranging
2. TP1 exits 50% of position at 1.5× risk distance
3. TP2 exits 30% of position at 2.5× risk distance
4. TP3 trails remaining 20% with 2×ATR trailing stop (let winners run)
5. Time-based tightening: breakeven stop after 45min (intraday) / 5 days (swing) if TP1 not hit
6. All partial exits correctly update position size, P&L tracking, and risk calculations

---

### Phase 13: Order Management System (OMS)
**Goal:** Build proper order lifecycle management with limit orders default, market orders only for SL exits, and full audit trail.
**Depends on:** Phase 2, Phase 10
**UI hint:** no

**Success Criteria:**
1. OMS tracks order states: New → Submitted → PartialFill → Filled → Cancelled → Rejected
2. Limit orders used by default; market orders only for stop-loss exits
3. Each order carries a correlation ID linking it to originating signal and event bus
4. Order history persisted for audit trail
5. OMS emits events on state transitions via event bus
6. Idempotent handlers: duplicate events don't create duplicate orders

---

### Phase 14: Paper Trading Engine
**Goal:** Build high-fidelity paper trading simulator with realistic slippage, commission, latency, and market impact modeling for any market (stocks, crypto, forex).
**Depends on:** Phase 12, Phase 13
**UI hint:** no

**Success Criteria:**
1. Slippage modeling: configurable 0.05–0.1% per fill
2. Commission modeling matches real brokerage fees for US stocks, Indian stocks, and crypto
3. Latency simulation: 50–200ms random jitter with adverse price drift
4. Market impact modeling for larger orders
5. Multi-asset support: switch between crypto, stocks, forex via config — no code changes
6. Paper trading runs on live market data with ₹1Cr / $100K capital
7. P&L accounts for all fees, slippage, taxes, and partial fills from TP1/TP2/TP3

---

### Phase 15: Backtesting Engine
**Goal:** Event-driven backtester with walk-forward optimization, Monte Carlo simulation, and comprehensive performance metrics.
**Depends on:** Phase 14
**UI hint:** no

**Success Criteria:**
1. Event-driven: processes historical data one candle at a time (verified no lookahead bias)
2. Walk-forward optimization with rolling/expanding train-test windows
3. Monte Carlo simulation with shuffled trades produces confidence intervals (P5/P50/P95)
4. Full metrics: Sharpe, Sortino, Calmar, max drawdown, win rate, profit factor, expectancy
5. Transaction costs match paper trading engine exactly
6. Sharpe haircut: divide backtest Sharpe by 2 for realistic expectations
7. Trade distribution analysis by hour/day/strategy/signal family

---

### Phase 16: Alpha Decay Monitoring System
**Goal:** Build per-signal-family health monitoring with automatic alerts and weight adjustment. No strategy runs without health tracking — built from day one.
**Depends on:** Phase 11, Phase 15
**UI hint:** no

**Success Criteria:**
1. Rolling 30-day Sharpe computed daily per signal family; < 0 for 30 days → reduce weight 50%
2. Rolling 90-day Sharpe computed weekly; < 0.3 → flag for review
3. Hit rate vs backtest baseline tracked; deviation > 2σ → alert
4. Average R per trade tracked; < 0.5R → pause signal family
5. Inter-family correlation monitored monthly; increase > 0.5 → investigate overlap
6. Yellow alert: automatically reduce weight by 50%, continue monitoring
7. Red alert: pause family, run diagnostic (regime shift? edge arbitraged?)
8. Retirement: archive family after 6+ months underperformance with no recovery

---

### Phase 17: Signal Family 5 — Microstructure / Order Flow
**Goal:** Implement VWAP deviation trading, volume imbalance, and VPIN trade flow toxicity. Graceful degradation when L2 data unavailable.
**Depends on:** Phase 11
**UI hint:** no

**Success Criteria:**
1. VWAP deviation trading: detect extended deviations, trade reversion to VWAP
2. Volume imbalance: buy/sell volume ratio at key levels signals directional pressure
3. VPIN (Volume-Synchronized Probability of Informed Trading) computed when tick data available
4. Graceful degradation: uses OBV divergence and volume-at-price as proxies when L2 unavailable
5. Signals only active in intraday mode (insufficient granularity for swing)
6. Output normalized to [-1, +1] matching other signal families

---

### Phase 18: Pairs & Cointegration Trading
**Goal:** Expand Mean Reversion signal family with full pairs/relative value trading — cointegration detection, spread trading, market-neutral sizing.
**Depends on:** Phase 7, Phase 15
**UI hint:** no

**Success Criteria:**
1. Engle-Granger cointegration test identifies valid pairs from instrument universe
2. Spread z-score triggers entry at ±2σ from mean
3. Market-neutral position sizing (dollar-neutral long/short)
4. Rolling cointegration validation with automatic pair invalidation when cointegration breaks
5. Pair selection from correlation screening of universe
6. Backtest shows market-neutral returns with low beta to benchmark

---

### Phase 19: Fundamental Analysis Module (LangGraph)
**Goal:** Build AI-powered fundamental analysis pipeline with 4 LangGraph agents — news sentiment, financial screener, sector/macro analyst, stock selector/confidence scorer.
**Depends on:** Phase 1
**UI hint:** no

**Success Criteria:**
1. News agent ingests and scores sentiment from at least 3 sources (FinBERT/LLM-based)
2. Financial screener analyzes 30+ fundamental metrics (valuation, profitability, growth, leverage, quality)
3. Sector/macro agent tracks GDP, inflation, interest rates, bond yields, DXY, VIX
4. Stock selector produces ranked watchlist with confidence (0–100) and allocation weights
5. LangGraph workflow orchestrates all 4 agents with error recovery
6. Fundamental output gates technical analysis (sequential pipeline: Module 1 → Module 2 → Module 3)

---

### Phase 20: ML/DL/RL Pipeline
**Goal:** Build ML models as enhancement layers — XGBoost classifier, LSTM/Transformer forecaster, PPO/SAC RL position sizer, ensemble meta-model. With Optuna tuning and MLflow tracking.
**Depends on:** Phase 15
**UI hint:** no

**Success Criteria:**
1. Feature engineering: all signal scores, regime probs, order flow, time features, cross-asset correlations
2. XGBoost/LightGBM classifier for trade direction with walk-forward validation
3. TCN or Transformer for multi-step price forecasting
4. PPO/SAC RL agent for optimal position sizing and execution timing
5. Ensemble stacking combines model outputs coherently
6. Optuna hyperparameter tuning with walk-forward cross-validation
7. MLflow tracks experiments: parameters, metrics, model artifacts
8. SHAP analysis identifies top-10 features; Sharpe haircut (÷2) for realistic expectations
9. ML-enhanced system improves Sharpe ratio by ≥ 0.3 vs rule-based only
10. Automatic weekly retraining pipeline with out-of-sample validation

---

### Phase 21: Dashboard & Monitoring
**Goal:** Production-grade Next.js monitoring dashboard with real-time WebSocket updates, performance analytics, signal family health, and kill switch.
**Depends on:** Phase 14, Phase 16
**UI hint:** yes

**Success Criteria:**
1. Live P&L and positions with sub-second WebSocket updates
2. HMM regime probabilities shown per instrument with color-coded visualization
3. Per-signal-family performance breakdown: Sharpe, win rate, P&L contribution %
4. Alpha decay health dashboard with yellow/red alert indicators
5. Kill switch button flattens all positions and halts trading within 2 seconds
6. Backtesting results with equity curve, drawdown chart, Monte Carlo confidence bands
7. Signal combination visualization: composite score breakdown by family
8. Responsive design, works on desktop browsers

---

### Phase 22: Live Trading Bridge & Production
**Goal:** Broker adapter interfaces, gradual deployment pipeline, Prometheus + Grafana observability, and production Docker deployment.
**Depends on:** Phase 14, Phase 21
**UI hint:** no

**Success Criteria:**
1. Broker adapter interface with at least one placeholder implementation (Alpaca/Zerodha/Binance)
2. Gradual deployment: start at 10% capital with scaling plan
3. Paper and live run simultaneously for comparison (parallel running)
4. Kill switch works in both paper and live modes
5. Prometheus metrics: signal_latency_ms, order_fill_latency_ms, event_queue_depth
6. Grafana dashboard templates for system health (CPU, memory, latency, uptime)
7. Alert rules: queue depth > threshold, latency > 200ms, memory > 80%
8. Docker Compose spins up complete system (TimescaleDB, Redis, engine, dashboard, Prometheus, Grafana)
9. Comprehensive test suite passes: unit, integration, and backtest validation

---

## Phase Dependency Graph

```
Phase 1 (Foundation)
  ├── Phase 2 (Event Bus)
  │     └── Phase 13 (OMS)
  ├── Phase 3 (Indicators)
  │     ├── Phase 4 (Structural Confluence)
  │     │     └── Phase 9 (Signal: Structural)
  │     └── Phase 5 (HMM Regime)
  │           ├── Phase 6 (Signal: Momentum)
  │           ├── Phase 7 (Signal: Mean Reversion)
  │           ├── Phase 8 (Signal: Breakout)
  │           └── Phase 9 (Signal: Structural)
  ├── Phase 10 (Risk Management)
  │     ├── Phase 12 (Multi-Target SL/TP)
  │     └── Phase 13 (OMS)
  └── Phase 19 (Fundamental Analysis)

Phase 6 + 7 + 8 + 9 → Phase 11 (Signal Combiner)
Phase 10 + 11 → Phase 12 (SL/TP) → Phase 14 (Paper Trading)
Phase 2 + 10 → Phase 13 (OMS) → Phase 14
Phase 14 → Phase 15 (Backtesting)
Phase 11 + 15 → Phase 16 (Alpha Decay)
Phase 11 → Phase 17 (Microstructure)
Phase 7 + 15 → Phase 18 (Pairs Trading)
Phase 15 → Phase 20 (ML Pipeline)
Phase 14 + 16 → Phase 21 (Dashboard)
Phase 14 + 21 → Phase 22 (Live Trading + Production)
```

## Summary

| # | Phase | Goal | Success Criteria |
|---|-------|------|-----------------|
| 1 | Foundation & Data | Data pipeline, config, TimescaleDB | 6 |
| 2 | Async Event Bus | asyncio + Redis Streams backbone | 6 |
| 3 | Indicator Engine | 7 orthogonal indicators + KAMA | 10 |
| 4 | Structural Confluence | Volume profile + swing clustering | 6 |
| 5 | HMM Regime | 4-state probabilistic regime detector | 7 |
| 6 | Signal: Momentum | Cross-sectional + time-series + dual | 7 |
| 7 | Signal: Mean Reversion | VWAP z-score + Bollinger + pairs | 7 |
| 8 | Signal: Breakout | Squeeze + volume-confirmed + ORB | 6 |
| 9 | Signal: Structural | Confluence-driven signals | 6 |
| 10 | Risk Management | Per-trade + portfolio + Kelly + circuit | 9 |
| 11 | Signal Combiner | Decorrelation + composite + conviction | 7 |
| 12 | Multi-Target SL/TP | TP1/TP2/TP3 + trailing + time stops | 6 |
| 13 | OMS | Order lifecycle + limit orders | 6 |
| 14 | Paper Trading | Realistic execution simulator | 7 |
| 15 | Backtesting | Walk-forward + Monte Carlo | 7 |
| 16 | Alpha Decay | Per-family health monitoring | 8 |
| 17 | Signal: Microstructure | VWAP deviation + VPIN + order flow | 6 |
| 18 | Pairs Trading | Cointegration + spread trading | 6 |
| 19 | Fundamental Analysis | 4 LangGraph agents | 6 |
| 20 | ML/DL/RL | Optuna + MLflow + ensemble | 10 |
| 21 | Dashboard | Next.js + signal health UI | 8 |
| 22 | Live Trading | Broker bridge + Prometheus + Docker | 9 |
| **Total** | **22 phases** | | **150 criteria** |
