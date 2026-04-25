# Plan 15-01: Backtesting Engine

## Outcome
Implemented a robust, event-driven backtesting engine that integrates seamlessly with the OMS and Paper Trading components. It executes a fast-path simulation loop over historical OHLCV data, runs Walk-Forward Optimization (WFO) using expanding windows, and accurately calculates metrics including the mandated Sharpe ratio haircut. Finally, it uses Monte Carlo sequence shuffling to surface worst-case P95 drawdowns.

## Self-Check: PASSED
- [x] All tasks executed
- [x] Each task committed individually
- [x] SUMMARY.md created in plan directory
- [x] STATE.md and ROADMAP.md updated

## Artifacts

### `key-files.created`
- src/algoforge/backtest/models.py
- src/algoforge/backtest/metrics.py
- src/algoforge/backtest/monte_carlo.py
- src/algoforge/backtest/wfo.py
- src/algoforge/backtest/engine.py
- src/algoforge/backtest/__init__.py
- tests/unit/test_backtest.py

### `key-files.modified`
- (none)

## Technical Notes
- The fast-path loop in `engine.py` correctly avoids the async event bus overhead while still instantiating the real `PaperTradingEngine` and `OrderManager`, guaranteeing that slippage, latency, and commissions match live trading perfectly.
- The WFO implementation supports dynamic train/test boundaries for regime testing.
- The Sharpe ratio explicitly divides by 2 in the metrics engine, acting as a built-in reality check against overfitting.
