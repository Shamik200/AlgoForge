# Requirements: AlgoForge

**Defined:** 2026-04-18
**Core Value:** Risk management is supreme — no trade executes without passing every risk check.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Data Infrastructure

- [ ] **DATA-01**: System can ingest real-time OHLCV candle data from configurable market data sources (WebSocket + REST)
- [ ] **DATA-02**: System stores OHLCV data in TimescaleDB with hypertable compression for 1min through 1Year timeframes
- [ ] **DATA-03**: System resamples 1-min candles to 5min, 15min, 1H, 4H, 1D, 1W, 1M timeframes on-the-fly
- [ ] **DATA-04**: System normalizes data from different sources into standardized OHLCV format with volume
- [ ] **DATA-05**: System handles data feed disconnections with automatic reconnection and gap detection

### Configuration & Market Selection

- [ ] **CONF-01**: User can select market (Indian Stocks, US Stocks, Crypto, Forex) at runtime via YAML config — no code changes
- [ ] **CONF-02**: All strategy parameters are configurable via YAML files, not hardcoded
- [ ] **CONF-03**: Risk management limits are configurable via YAML with validation (reject invalid values at startup)
- [ ] **CONF-04**: System loads market-specific settings (trading hours, fees, instruments, currency) from market YAML configs
- [ ] **CONF-05**: User can select operational timeframe mode (Intraday Trading or Swing/Investment) per instrument

### Technical Indicators

- [ ] **INDI-01**: System computes EMA (5, 9, 21, 50, 100, 200) across all configured timeframes
- [ ] **INDI-02**: System computes RSI (14-period configurable) with overbought/oversold detection
- [ ] **INDI-03**: System computes ADX/DMI (14-period) for trend strength measurement
- [ ] **INDI-04**: System computes ATR (14-period) for volatility and SL/TP sizing
- [ ] **INDI-05**: System computes MACD (12, 26, 9) with signal line crossover detection
- [ ] **INDI-06**: System computes Bollinger Bands (20, 2σ) with squeeze detection
- [ ] **INDI-07**: System computes Keltner Channels (20, 1.5×ATR) for squeeze confirmation
- [ ] **INDI-08**: System computes VWAP (session-based) for institutional fair value
- [ ] **INDI-09**: System computes Supertrend (10, 3.0) for trend following signals
- [ ] **INDI-10**: System computes Stochastic Oscillator (14, 3, 3) for range trading
- [ ] **INDI-11**: System computes Donchian Channels (20-period) for breakout detection
- [ ] **INDI-12**: System computes Volume Profile with POC, VAH, VAL levels
- [ ] **INDI-13**: System computes OBV (cumulative) for volume-price divergence
- [ ] **INDI-14**: System computes Ichimoku Cloud (9, 26, 52) for multi-factor analysis

### Structural Analysis

- [ ] **STRU-01**: System detects support and resistance levels on higher timeframes (1D/1H for trading mode, 1M/1Y for investment mode)
- [ ] **STRU-02**: System scores each S/R level by strength (number of touches, recency, volume at level)
- [ ] **STRU-03**: System algorithmically constructs trendlines on mid timeframes (15min/5min for trading, 1W/1D for investment) using 2-3 touch points minimum
- [ ] **STRU-04**: System identifies ascending/descending channels from trendline pairs
- [ ] **STRU-05**: System determines bigger trend direction (higher highs + higher lows = UP, lower highs + lower lows = DOWN)
- [ ] **STRU-06**: System invalidates and removes broken trendlines in real-time

### Market Regime Detection

- [ ] **REGM-01**: System classifies market regime into 5 categories: Trending, Range/Sideways, Breakout, Reversal, Liquidity Trap
- [ ] **REGM-02**: System outputs regime probabilities (not just a single label) per instrument
- [ ] **REGM-03**: System uses ADX, Bollinger Band width, ATR expansion, volume, and divergence metrics for classification
- [ ] **REGM-04**: Regime classification runs BEFORE any strategy is activated (mandatory gate)

### Primary Strategy — Trendline-Pullback

- [ ] **PRIM-01**: Primary strategy generates >50% of all trade signals across all instruments
- [ ] **PRIM-02**: In uptrend, system waits for price pullback to lower trendline before generating buy signal
- [ ] **PRIM-03**: In downtrend, system waits for price rally to upper trendline before generating sell signal
- [ ] **PRIM-04**: System checks EMA alignment (5, 9, 21) for bullish/bearish confirmation at trendline touch
- [ ] **PRIM-05**: System checks RSI turning from oversold/overbought zone at trendline touch
- [ ] **PRIM-06**: System checks ADX > 20 for trend strength confirmation
- [ ] **PRIM-07**: System checks for bullish/bearish candlestick patterns at trendline touch (12+ patterns)
- [ ] **PRIM-08**: System waits for momentum confirmation (1-3 candles showing trend resumption) BEFORE entry
- [ ] **PRIM-09**: System sets SL at trendline-S/R intersection with ATR buffer (1-1.5× ATR)
- [ ] **PRIM-10**: System sets TP at next S/R level or opposite trendline, with trailing stop option
- [ ] **PRIM-11**: System enforces minimum 1:2 risk-reward ratio (rejects trades below this)
- [ ] **PRIM-12**: If trend is unclear, system skips the instrument — no forced trades

### Secondary Strategies — Trending (8 strategies)

- [ ] **TRND-01**: EMA Pullback Strategy — enter on pullback to 9/21 EMA in strong trend (ADX > 25)
- [ ] **TRND-02**: Moving Average Crossover — 9/21 EMA crossover with volume confirmation
- [ ] **TRND-03**: Break & Retest — break key level, retest from other side, enter on confirmation
- [ ] **TRND-04**: Channel Trading — trade within ascending/descending channels
- [ ] **TRND-05**: Supertrend Strategy — ATR-based trend-following signals
- [ ] **TRND-06**: Donchian Channel Trend — enter on N-period high/low breakout
- [ ] **TRND-07**: Momentum Continuation — enter when RSI > 60 (up) or < 40 (down) with volume spike
- [ ] **TRND-08**: All trending strategies only activate when regime = Trending

### Secondary Strategies — Range/Sideways (7 strategies)

- [ ] **RANG-01**: RSI Mean Reversion — buy RSI < 30, sell RSI > 70 within range
- [ ] **RANG-02**: Support Resistance Bounce — enter at S/R with reversal candle confirmation
- [ ] **RANG-03**: Bollinger Bands Mean Reversion — enter at outer band, target middle
- [ ] **RANG-04**: VWAP Reversion — trade reversion to VWAP from extended deviations
- [ ] **RANG-05**: Stochastic Oscillator Range — buy K < 20 crossover, sell K > 80
- [ ] **RANG-06**: Range Scalping — rapid entries at range boundaries with tight SL
- [ ] **RANG-07**: Midline Reversion — trade pullbacks to 50% of range

### Secondary Strategies — Breakout/Volatility (7 strategies)

- [ ] **BRKT-01**: Range Breakout — enter on break with volume > 2× average
- [ ] **BRKT-02**: Consolidation Breakout — tight consolidation to explosive move
- [ ] **BRKT-03**: Volatility Breakout (ATR) — enter when price moves > 1.5× ATR from open
- [ ] **BRKT-04**: Opening Range Breakout (ORB) — first 15/30 min range breakout (intraday only)
- [ ] **BRKT-05**: Triangle Breakout — symmetrical/ascending/descending triangle break
- [ ] **BRKT-06**: Flag/Pennant Breakout — continuation pattern on strong trend
- [ ] **BRKT-07**: Squeeze Breakout (Bollinger + Keltner) — Bollinger inside Keltner, breakout direction

### Secondary Strategies — Reversal (5 strategies)

- [ ] **REVS-01**: Double Top/Bottom — classic reversal with neckline break
- [ ] **REVS-02**: Head & Shoulders — H&S/Inverse with volume profile
- [ ] **REVS-03**: Divergence (RSI/MACD) — bullish/bearish divergence at key levels
- [ ] **REVS-04**: Trend Reversal Break — break of trendline + S/R flip
- [ ] **REVS-05**: Exhaustion Move — parabolic move with declining volume → reversal

### Secondary Strategies — Liquidity/Trap (4 strategies)

- [ ] **LIQD-01**: Fake Breakout — enter opposite direction after false breakout beyond S/R
- [ ] **LIQD-02**: Liquidity Grab — detect stop hunts at obvious levels, enter on reversal
- [ ] **LIQD-03**: Stop Hunt — identify stop clusters, trade reversal after sweep
- [ ] **LIQD-04**: Breakout Failure — failed breakout → re-entry into range with momentum

### Candlestick Pattern Recognition

- [ ] **CNDL-01**: System detects bullish patterns: Hammer, Bullish Engulfing, Morning Star, Piercing Line, Dragonfly Doji, Three White Soldiers
- [ ] **CNDL-02**: System detects bearish patterns: Shooting Star, Bearish Engulfing, Evening Star, Dark Cloud Cover, Gravestone Doji, Three Black Crows
- [ ] **CNDL-03**: Pattern detection integrates with strategy signal generation as confirmation layer

### Risk Management — Per-Trade

- [ ] **RISK-01**: Maximum risk per trade limited to 1-2% of total capital (configurable)
- [ ] **RISK-02**: Maximum position size limited to 5-10% of total capital (configurable)
- [ ] **RISK-03**: Minimum risk-reward ratio of 1:2 enforced on every trade
- [ ] **RISK-04**: Every trade MUST have a stop loss — system rejects signals without SL
- [ ] **RISK-05**: Maximum 5 consecutive losses triggers cooldown (1 hour trading / 1 day investment)
- [ ] **RISK-06**: Maximum open positions limited to 5-10 (configurable)
- [ ] **RISK-07**: Maximum correlation between positions limited to 0.7 coefficient

### Risk Management — Portfolio Level

- [ ] **RISK-08**: Maximum daily loss limited to 3-5% of total capital (halt trading for day)
- [ ] **RISK-09**: Maximum weekly loss limited to 7-10% of total capital
- [ ] **RISK-10**: Maximum drawdown kill switch at 15-20% of peak equity (halt ALL trading)
- [ ] **RISK-11**: Sector exposure limited to 25% of capital per sector
- [ ] **RISK-12**: Net directional exposure capped at 60% of capital
- [ ] **RISK-13**: 95% VaR must not exceed 3% of portfolio daily
- [ ] **RISK-14**: Risk manager has absolute veto power over any signal from any strategy

### Risk Management — Dynamic & Execution

- [ ] **RISK-15**: Position sizes reduce during high VIX / elevated ATR environments
- [ ] **RISK-16**: Position sizes reduce proportionally during drawdown periods
- [ ] **RISK-17**: Slippage buffers included in all SL/TP calculations
- [ ] **RISK-18**: Liquidity check: reject trades if volume < 3× position size in daily volume
- [ ] **RISK-19**: Circuit breaker: halt trading if market drops > 5% from open
- [ ] **RISK-20**: Use limit orders by default; market orders only for stop-loss exits

### Position Sizing

- [ ] **SIZE-01**: Position sizing uses Kelly Criterion (fractional Kelly for safety) or risk-parity weighting
- [ ] **SIZE-02**: Maximum single-position limit: 5-10% of total capital
- [ ] **SIZE-03**: Sector concentration limit: 25% of total capital per sector
- [ ] **SIZE-04**: Confidence scores from fundamental analysis determine allocation weights

### Paper Trading Engine

- [ ] **PAPR-01**: Paper trading engine simulates realistic execution with configurable slippage (0.05-0.1%)
- [ ] **PAPR-02**: Commission modeling includes brokerage fees, exchange fees, and taxes (market-specific)
- [ ] **PAPR-03**: Latency simulation adds realistic delays (50-200ms)
- [ ] **PAPR-04**: System supports paper trading on any market (stocks, crypto, forex) without code changes
- [ ] **PAPR-05**: Paper trading uses live market data feeds for real-time simulation
- [ ] **PAPR-06**: Paper trading capital: ₹1,00,00,000 (INR) or $100,000 (USD) based on market

### Backtesting Engine

- [ ] **BACK-01**: Event-driven backtesting (not vectorized) — processes one candle at a time
- [ ] **BACK-02**: Walk-forward optimization with rolling/expanding windows
- [ ] **BACK-03**: Monte Carlo simulation for strategy robustness testing
- [ ] **BACK-04**: Transaction cost modeling matching paper trading engine
- [ ] **BACK-05**: Performance metrics: Sharpe, Sortino, Calmar, max drawdown, win rate, profit factor, expectancy
- [ ] **BACK-06**: Trade distribution analysis by hour, day, strategy
- [ ] **BACK-07**: No lookahead bias — execute signals on NEXT bar's open, never current bar

### Timeframe Modes

- [ ] **TIME-01**: Intraday Trading mode: S/R on 1D/1H, trendlines on 15min/5min, execute on 1min, hold 15min-1h
- [ ] **TIME-02**: Swing/Investment mode: S/R on 1M/1Y, trendlines on 1W/1D, execute on 1H/4H, hold 1week-1month
- [ ] **TIME-03**: Both modes use the same strategy engine with different timeframe configurations
- [ ] **TIME-04**: User can select mode per instrument independently

### Fundamental Analysis — Agentic AI

- [ ] **FUND-01**: Agent 1 (News/Sentiment) ingests real-time news from multiple sources with NLP sentiment scoring (-1 to +1)
- [ ] **FUND-02**: Agent 2 (Financial Screener) analyzes balance sheet, P&L, cash flow with 30+ fundamental metrics
- [ ] **FUND-03**: Agent 3 (Sector/Macro) tracks sector rotation, macro indicators (GDP, CPI, interest rates, VIX, DXY)
- [ ] **FUND-04**: Agent 4 (Stock Selector) combines scores from Agents 1-3 into ranked watchlist with confidence values (0-100)
- [ ] **FUND-05**: LangGraph DAG orchestrates all 4 agents in workflow with error handling
- [ ] **FUND-06**: Fundamental analysis MUST complete before technical analysis generates signals (sequential gate)
- [ ] **FUND-07**: Each instrument gets directional bias (Bullish/Bearish/Neutral) from fundamentals
- [ ] **FUND-08**: Suggested allocation weight (%) computed per instrument based on conviction and diversification

### ML/DL/RL Models

- [ ] **MLAI-01**: XGBoost/LightGBM classifier predicts trade direction (long/short/skip) from features
- [ ] **MLAI-02**: LSTM/Transformer model predicts price movement magnitude
- [ ] **MLAI-03**: PPO/SAC RL agent optimizes position sizing and execution timing
- [ ] **MLAI-04**: Ensemble meta-model (stacking) combines all model outputs
- [ ] **MLAI-05**: Walk-forward training pipeline with out-of-sample validation — no lookahead bias
- [ ] **MLAI-06**: Feature engineering from all indicators, patterns, regime probabilities, fundamental scores
- [ ] **MLAI-07**: SHAP-based feature importance analysis
- [ ] **MLAI-08**: Automatic retraining on schedule (weekly/monthly)
- [ ] **MLAI-09**: ML models serve as confirmation layer for rule-based signals, not replacements

### Dashboard & Monitoring

- [ ] **DASH-01**: Next.js real-time dashboard with WebSocket updates
- [ ] **DASH-02**: Dashboard displays real-time P&L, open positions, and order status
- [ ] **DASH-03**: Dashboard shows market regime classification per instrument (color-coded)
- [ ] **DASH-04**: Dashboard shows strategy performance breakdown (win rate, P&L per strategy)
- [ ] **DASH-05**: One-click kill switch to flatten all positions and halt trading
- [ ] **DASH-06**: Backtesting results visualization (equity curve, drawdown, trade distribution)

### Live Trading Bridge

- [ ] **LIVE-01**: Modular broker adapter pattern supporting Zerodha, Alpaca, Binance, IBKR
- [ ] **LIVE-02**: Gradual deployment starting at 10% of intended capital
- [ ] **LIVE-03**: Parallel running: paper and live simultaneously for comparison
- [ ] **LIVE-04**: Kill switch: one-click flatten all positions and halt

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Advanced Execution

- **ADVX-01**: Options/futures/derivatives trading support
- **ADVX-02**: Multi-broker simultaneous execution for arbitrage
- **ADVX-03**: Smart order routing across multiple exchanges

### Advanced Analytics

- **ADVA-01**: Portfolio stress testing under historical crash scenarios (2008, 2020, 2022)
- **ADVA-02**: Beta-adjusted exposure monitoring
- **ADVA-03**: Detailed compliance and audit trail

### Mobile & Social

- **MOBI-01**: Mobile companion app for monitoring
- **SOCL-01**: Copy trading / signal sharing
- **SOCL-02**: Social trading leaderboard

## Out of Scope

| Feature | Reason |
|---------|--------|
| Sub-microsecond latency (FPGA/co-location) | Impossible via retail APIs; requires institutional infrastructure |
| Options/derivatives in v1 | High complexity; spot trading must be profitable first |
| Mobile application | Web dashboard sufficient; mobile adds development burden |
| Crypto DeFi integration | On-chain trading adds massive complexity; CEX APIs only |
| Social/copy trading | Not core to personal trading system; distraction from alpha |
| Custom exchange connectivity (FIX protocol) | Retail APIs are sufficient; FIX is institutional overhead |
| Backtesting GUI builder | Code-based strategies are more flexible; GUI adds complexity |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 to DATA-05 | Phase 1 | Pending |
| CONF-01 to CONF-05 | Phase 1 | Pending |
| INDI-01 to INDI-14 | Phase 2 | Pending |
| STRU-01 to STRU-06 | Phase 3 | Pending |
| REGM-01 to REGM-04 | Phase 4 | Pending |
| PRIM-01 to PRIM-12 | Phase 5 | Pending |
| CNDL-01 to CNDL-03 | Phase 5 | Pending |
| RISK-01 to RISK-20 | Phase 6 | Pending |
| SIZE-01 to SIZE-04 | Phase 6 | Pending |
| PAPR-01 to PAPR-06 | Phase 7 | Pending |
| BACK-01 to BACK-07 | Phase 8 | Pending |
| TRND-01 to TRND-08 | Phase 9 | Pending |
| RANG-01 to RANG-07 | Phase 9 | Pending |
| BRKT-01 to BRKT-07 | Phase 10 | Pending |
| REVS-01 to REVS-05 | Phase 10 | Pending |
| LIQD-01 to LIQD-04 | Phase 10 | Pending |
| TIME-01 to TIME-04 | Phase 11 | Pending |
| FUND-01 to FUND-08 | Phase 12 | Pending |
| MLAI-01 to MLAI-09 | Phase 13 | Pending |
| DASH-01 to DASH-06 | Phase 14 | Pending |
| LIVE-01 to LIVE-04 | Phase 15 | Pending |

**Coverage:**
- v1 requirements: 118 total
- Mapped to phases: 118
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-18*
*Last updated: 2026-04-18 after initial definition*
