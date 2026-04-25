# Phase 15: Backtesting Engine - Research

## Context
The backtesting engine is the ultimate validation tool for the trading system. It must be highly accurate, replicating exactly what the Paper Trading Engine and OMS do, but running significantly faster to support Walk-Forward Optimization (WFO) and Monte Carlo simulations.

## Technical Findings

1. **Simulation Loop:**
   - A fast synchronous loop iterating over historical OHLCV data.
   - For each candle:
     1. Evaluate existing limit/market orders against the current candle's High/Low using `PaperTradingEngine.process_tick`.
     2. Run Signal generators.
     3. Run Risk Management.
     4. If a trade is approved, spawn Exits (Tranches) and submit to OMS.
   - Bypassing the Async Event Bus here is necessary for speed. The logic remains 100% identical.

2. **Metrics Engine (`metrics.py`):**
   - Must calculate:
     - **Sharpe Ratio:** `(Annualized Return - Risk Free Rate) / Annualized Volatility`. Must mandate a "haircut" (divide by 2) for realistic expectations.
     - **Sortino Ratio:** Same as Sharpe, but uses downside deviation.
     - **Max Drawdown:** Peak-to-trough drop in equity.
     - **Profit Factor:** Gross Profit / Gross Loss.
     - **Expectancy:** Average P&L per trade.
     - **Win Rate:** Winners / Total Trades.

3. **Walk-Forward Optimization (WFO):**
   - Data is split into expanding train/test folds.
   - Train Fold 1: Year 1. Test Fold 1: Year 2.
   - Train Fold 2: Years 1+2. Test Fold 2: Year 3.
   - Evaluates hyperparameters (e.g., `time_limit_candles`, `ATR multiplier`) across folds.

4. **Monte Carlo Simulation (`monte_carlo.py`):**
   - Takes a list of executed trade PnLs from a backtest run.
   - Shuffles the chronological order 10,000 times to create 10,000 synthetic equity curves.
   - Calculates the 5th, 50th, and 95th percentiles (P5/P50/P95) for Max Drawdown and Final Equity.

## Implementation Path
- Create `src/algoforge/backtest/models.py` (BacktestResult, MetricsResult).
- Create `src/algoforge/backtest/metrics.py` (Calculations and Sharpe haircut).
- Create `src/algoforge/backtest/monte_carlo.py` (Trade sequence shuffling).
- Create `src/algoforge/backtest/wfo.py` (Expanding window splitter).
- Create `src/algoforge/backtest/engine.py` (The fast-path loop).
- Tests.
