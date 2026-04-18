# Pitfalls Research

**Domain:** Algorithmic Trading System (HFT-level, multi-market)
**Researched:** 2026-04-18
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Lookahead Bias in Backtesting

**What goes wrong:**
Backtesting uses future data to make past decisions — signals are computed using information that wasn't available at the time. This produces unrealistically profitable results that collapse in live trading.

**Why it happens:**
- Using close price to execute at the same bar (you don't know the close until the bar is done)
- Computing indicators over the entire dataset before iterating (vectorized approach)
- Using adjusted prices for historical fills but unadjusted for live
- Data alignment errors when merging multi-timeframe data

**How to avoid:**
- Event-driven backtesting: process ONE candle at a time, never access future candles
- Execute signals on the NEXT bar's open, not current bar's close
- Strict temporal ordering: indicator[t] can only use data from [0..t-1]
- Code review specifically for temporal correctness

**Warning signs:**
- Backtest Sharpe ratio > 3.0 (suspiciously good)
- Perfectly smooth equity curve with no drawdowns
- 90%+ win rate (too good to be true)

**Phase to address:** Phase 1 (data pipeline) and Phase 3 (backtesting engine)

---

### Pitfall 2: Overfitting / Curve Fitting

**What goes wrong:**
Strategy parameters are over-optimized on historical data, memorizing noise rather than genuine patterns. Strategy shows spectacular backtests but fails immediately in live trading.

**Why it happens:**
- Tuning too many parameters (>5 free parameters per strategy)
- Testing hundreds of parameter combinations and picking the best
- Not using out-of-sample validation
- Adding special rules to handle specific historical events

**How to avoid:**
- Walk-forward optimization: train on rolling window, validate on next period
- Keep strategy logic simple: 3-5 core parameters per strategy
- Out-of-sample validation MANDATORY before deploying any strategy
- Monte Carlo simulation: shuffle trades, verify positive expectancy holds
- Track in-sample vs out-of-sample Sharpe ratio gap (should be < 0.5)

**Warning signs:**
- Strategy works perfectly on 2020-2023 data but not 2024+
- Backtest win rate dramatically different from paper trading win rate
- Strategy has 10+ tunable parameters

**Phase to address:** Phase 3 (backtesting) and Phase 8 (ML models)

---

### Pitfall 3: Survivorship Bias in Data

**What goes wrong:**
Using a dataset that only includes currently active stocks, ignoring those that went bankrupt, were delisted, or merged. This creates a "winners-only" dataset that inflates returns.

**Why it happens:**
- Using current S&P 500 constituents for historical tests
- Data providers only supplying currently listed instruments
- Not accounting for corporate actions (splits, dividends, mergers)

**How to avoid:**
- Use point-in-time data that includes delisted stocks
- Account for corporate actions (adjusted OHLCV data)
- For Indian markets: include suspended/delisted NSE stocks in historical universe
- Document data source and any known survivorship limitations

**Warning signs:**
- All backtested stocks had positive long-term trends (no failures)
- Backtest returns significantly higher than market index returns
- Universe of stocks suspiciously small for the testing period

**Phase to address:** Phase 1 (data pipeline — data quality validation)

---

### Pitfall 4: Ignoring Transaction Costs and Slippage

**What goes wrong:**
Backtesting assumes perfect execution at exact prices. In reality, brokerage fees, exchange fees, taxes (STT/GST in India), and slippage destroy profitability of high-frequency strategies.

**Why it happens:**
- Assumes market order fills at exact quoted price
- Ignores bid-ask spread (especially wide in low-liquidity instruments)
- Doesn't account for market impact of larger orders
- Ignores taxes that can be significant (e.g., STT is 0.025% on sell in India)

**How to avoid:**
- Model realistic slippage: 0.05-0.1% for liquid stocks, higher for illiquid
- Include ALL fees: brokerage, exchange fees, stamp duty, GST, STT (market-specific)
- Factor in bid-ask spread as minimum slippage floor
- Test profitability at 2x expected slippage to verify robustness

**Warning signs:**
- Strategy has high trade frequency but thin per-trade profit
- Average profit per trade < 0.2% (fees will eat it)
- Strategy only profitable in zero-fee backtests

**Phase to address:** Phase 3 (paper trading engine — commission/slippage modeling)

---

### Pitfall 5: Risk Management as Afterthought

**What goes wrong:**
Building strategies first, then "adding" risk management. By then, strategies are already designed around unlimited risk, and retrofitting proper risk controls breaks their logic.

**Why it happens:**
- Developers focus on entries (the exciting part) and neglect exits/sizing
- Risk management is "boring" compared to strategy development
- "We'll add proper risk management later" syndrome

**How to avoid:**
- Build risk management BEFORE any strategy
- Every signal MUST include stop_loss and take_profit before reaching execution
- Risk manager has absolute veto power — no bypassing
- Implement kill switch and circuit breaker from day 1

**Warning signs:**
- Any strategy that "sometimes" doesn't set a stop loss
- Position sizes not adjusted for volatility
- No portfolio-level risk checks (just per-trade)

**Phase to address:** Phase 2 (risk management engine — build before strategies)

---

### Pitfall 6: Indicator Multicollinearity

**What goes wrong:**
Using many correlated indicators that provide the same information, giving false confidence in signals. Multiple indicators confirming each other doesn't add value if they measure the same thing.

**Why it happens:**
- "More indicators = better" assumption
- Using RSI + Stochastic + CCI (all momentum oscillators — they're correlated)
- Not understanding what each indicator actually measures

**How to avoid:**
- Use indicators from DIFFERENT categories: trend (EMA) + momentum (RSI) + volatility (ATR) + volume (OBV)
- Limit to 4-6 indicators per strategy
- Check correlation between indicator signals before combining
- Each indicator in a strategy must measure a DIFFERENT market dimension

**Warning signs:**
- Strategy uses 3+ oscillators (RSI, Stochastic, CCI, MFI all together)
- Multiple trend indicators redundantly confirming the same thing
- Signal "confidence" artificially inflated by correlated indicators

**Phase to address:** Phase 2 (strategy design) and Phase 8 (ML feature engineering)

---

### Pitfall 7: Wrong Market Regime Strategy Application

**What goes wrong:**
Applying a trending strategy in a ranging market (or vice versa). This is the #1 reason good strategies lose money — they're applied in the wrong conditions.

**Why it happens:**
- No market regime detection
- "This strategy worked last week" bias
- Ignoring ADX/volatility readings
- Not checking if market conditions match strategy assumptions

**How to avoid:**
- Mandatory regime detection before any strategy activation
- Each strategy declares which regimes it's valid for
- Track regime classification accuracy over time
- When regime is unclear, reduce position size or skip

**Warning signs:**
- Strategy has alternating winning and losing streaks aligned with market regime changes
- Strategy works great for 2-3 months then stops working
- Trend strategy losing money during sideways markets

**Phase to address:** Phase 2 (regime detection — must be built before strategies)

---

### Pitfall 8: ML Model Overconfidence

**What goes wrong:**
ML model trained on historical data appears highly accurate but fails in production because financial data is non-stationary — the distribution shifts over time.

**Why it happens:**
- Training on entire dataset without temporal split
- Using accuracy as primary metric (misleading for imbalanced trade data)
- Not accounting for concept drift (market regimes change)
- Feature leakage from future data or related instruments

**How to avoid:**
- Walk-forward validation ONLY (no random train/test split)
- Use profit-based metrics (Sharpe, Calmar) not just accuracy
- Implement concept drift detection (monitor prediction confidence over time)
- Schedule regular retraining (weekly/monthly)
- ML models are CONFIRMATION layers, not primary signal sources

**Warning signs:**
- Model accuracy > 75% (likely too good — financial prediction is noisy)
- Performance degrades rapidly after deployment
- Model makes the same prediction for every input (mode collapse)

**Phase to address:** Phase 8 (ML pipeline — walk-forward mandatory)

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcoded strategy parameters | Fast prototyping | Can't tune, can't adapt to new markets | Never in production |
| Single-threaded processing | Simpler code | Can't handle 100+ instruments in real-time | Early development only; must migrate to async |
| No trade logging | Less code to write | Can't analyze performance or debug issues | Never |
| Skipping unit tests for strategies | Faster development | Bugs compound; strategies silently produce wrong signals | Never — strategies MUST be tested |
| Using pandas for everything | Familiar API | Performance bottleneck at scale (>500 instruments) | OK for <50 instruments; migrate to Polars for scale |
| Storing data in CSV files | Easy to start | Can't query efficiently; no concurrent access | Early prototyping only; migrate to TimescaleDB |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Zerodha Kite API | Not handling token refresh; tokens expire daily at 6 AM IST | Implement automatic daily re-login before market open |
| Binance WebSocket | Not handling connection drops; losing data during reconnect | Implement reconnect with gap detection; backfill missed candles from REST |
| Yahoo Finance | Rate limiting; getting blocked for excessive requests | Implement request throttling; use yfinance with session caching |
| LLM APIs | Not handling token limits; request timeouts | Implement chunking, retry with exponential backoff, fallback providers |
| TimescaleDB | Not using hypertables; treating as regular PostgreSQL | Create hypertables with proper time partitioning; enable compression for historical data |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Computing ALL indicators on every tick | CPU usage > 80% | Cache indicator values; only recompute when new candle closes | > 50 instruments at 1-min frequency |
| Storing every tick in database | Disk fills up; queries slow | Store 1-min OHLCV, not raw ticks; compress historical data | > 6 months of data for 100+ instruments |
| Running all 31 strategies on every instrument | Latency > 1 second | Only run strategies matching detected regime | > 100 instruments simultaneously |
| Synchronous broker API calls | Blocks entire pipeline | Use async API calls; never block event loop | Any real-time trading scenario |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| API keys in source code | Keys leaked via git; unauthorized trading | Environment variables or encrypted secrets manager; .env with .gitignore |
| No authentication on dashboard | Anyone on network can view positions/P&L | Add authentication layer; HTTPS; IP whitelist |
| Unencrypted database connections | Trade data intercepted | SSL/TLS for all database connections; encrypted at rest |
| No rate limiting on order submission | Accidental infinite order loop | Max orders per second/minute; circuit breaker on rapid submissions |

## UX Pitfalls (Dashboard)

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Delayed P&L display | User doesn't know current position status | WebSocket push updates; sub-second P&L refresh |
| No visual regime indicator | User doesn't know which strategies are active | Color-coded regime display per instrument |
| Overly complex charts | Information overload; can't find key data | Clean layout; key metrics prominent; detailed views on drill-down |
| No kill switch in UI | Can't stop trading quickly in emergency | Big red button, always visible, one-click flatten all |

## "Looks Done But Isn't" Checklist

- [ ] **Backtesting:** Often missing realistic slippage model — verify fills account for bid-ask spread
- [ ] **Risk Manager:** Often missing portfolio-level checks — verify sector, correlation, VaR limits work
- [ ] **Paper Trading:** Often missing latency simulation — verify simulated delays match real API latency
- [ ] **S/R Detection:** Often missing multi-timeframe — verify S/R levels cascade from 1D→1H→15min
- [ ] **Trendline Algorithm:** Often missing invalidation — verify trendlines are removed when broken
- [ ] **Strategy Engine:** Often missing regime check — verify strategies don't run in wrong regime
- [ ] **Order Manager:** Often missing partial fill handling — verify system handles partial fills correctly
- [ ] **Config Loading:** Often missing validation — verify invalid YAML values are caught at startup

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Lookahead bias discovered in backtest | HIGH | Re-audit entire backtesting engine; rebuild with event-driven approach; re-run all backtests |
| Overfitted strategy in production | MEDIUM | Halt strategy; retrain with walk-forward; deploy only after out-of-sample validation |
| Risk management bypass discovered | HIGH | Emergency halt all trading; audit all open positions; fix risk pipeline; comprehensive testing |
| Data quality issues | MEDIUM | Identify corrupted periods; re-download clean data; re-run affected backtests |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Lookahead bias | Phase 1 (data), Phase 3 (backtesting) | Run "future data access" detection test |
| Overfitting | Phase 3 (backtesting), Phase 8 (ML) | Compare in-sample vs out-of-sample Sharpe |
| Survivorship bias | Phase 1 (data pipeline) | Verify delisted stocks appear in historical data |
| Transaction costs | Phase 3 (paper trading) | Compare paper trading P&L with and without fees |
| Risk as afterthought | Phase 2 (risk engine) | Attempt to submit signal without SL — must fail |
| Multicollinearity | Phase 2 (indicators) | Correlation matrix of indicator signals |
| Wrong regime application | Phase 2 (regime detection) | Strategy activation logs match detected regime |
| ML overconfidence | Phase 8 (ML pipeline) | Walk-forward validation shows realistic metrics |

## Sources

- "Advances in Financial Machine Learning" — Marcos López de Prado
- QuantConnect community post-mortems on failed strategies
- r/algotrading common failure modes (2024-2025 threads)
- Institutional trading system failure case studies

---
*Pitfalls research for: Algorithmic Trading System*
*Researched: 2026-04-18*
