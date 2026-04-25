---
gap_closure: false
---

# Plan 15-01: Backtesting Engine

## Objective
Build a fast, event-driven backtesting engine with a comprehensive metrics suite, Monte Carlo trade shuffling, and expanding-window Walk-Forward Optimization (WFO).

## Tasks

- [ ] **1. Backtest Models**
  - Create `src/algoforge/backtest/models.py`.
  - Define `TradePnL` dataclass for tracking realized returns.
  - Define `MetricsResult` and `BacktestResult`.

- [ ] **2. Metrics Engine**
  - Create `src/algoforge/backtest/metrics.py`.
  - Implement `calculate_metrics(pnl_series, initial_capital)`.
  - Include Sharpe (with /2 haircut), Sortino, Calmar, Max Drawdown, Win Rate, Profit Factor, Expectancy.

- [ ] **3. Monte Carlo Simulator**
  - Create `src/algoforge/backtest/monte_carlo.py`.
  - Implement `run_monte_carlo_drawdown(trades, num_simulations=1000)`.
  - Shuffle chronological sequence and return P5, P50, P95 metrics.

- [ ] **4. Walk-Forward Optimization (WFO)**
  - Create `src/algoforge/backtest/wfo.py`.
  - Implement `generate_expanding_windows(dataframe, train_size_bars, test_size_bars)`.

- [ ] **5. Fast-Path Backtest Loop**
  - Create `src/algoforge/backtest/engine.py`.
  - Implement `BacktestEngine.run(dataframe, strategy)`.
  - Setup loop over dataframe rows: update PaperTradingEngine -> update Strategy -> record PnL.

- [ ] **6. Integration & Testing**
  - Create `src/algoforge/backtest/__init__.py`.
  - Create `tests/unit/test_backtest.py`.
  - Test metrics calculations (especially drawdown and Sharpe haircut).
  - Test Monte Carlo shuffling logic.
  - Test WFO window boundaries.
