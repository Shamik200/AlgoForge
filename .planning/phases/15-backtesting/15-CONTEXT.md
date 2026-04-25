# Phase 15: Backtesting Engine - Context

**Gathered:** 2026-04-25
**Status:** Completed (Auto-selected recommended options)

<domain>
## Phase Boundary

Build a robust, event-driven backtesting engine to validate the end-to-end trading system. The backtester must utilize the exact OMS and Paper Trading components built in earlier phases to guarantee transaction costs, latency, and slippage match production perfectly. It introduces Walk-Forward Optimization, Monte Carlo simulation, and comprehensive performance metrics (with the mandated Sharpe haircut).
</domain>

<decisions>
## Implementation Decisions

### Simulation Loop Architecture
- **D-01:** Fast-Path Event Loop. While the live system uses an asynchronous event bus (Phase 2), the backtester will bypass this and use a tight synchronous `for candle in dataset:` loop. It will instantiate and directly call the internal methods of `PaperTradingEngine` and `OrderManager`. This guarantees identical logic but allows years of backtesting to complete in seconds, which is a hard requirement for the WFO logic.

### Walk-Forward Optimization (WFO) Strategy
- **D-02:** Expanding Window. Hyperparameter optimization will utilize an expanding window approach (Train Y1 → Test Y2, Train Y1+Y2 → Test Y3). This prevents curve-fitting to specific market regimes and tests how well the system adapts to new, unseen data.

### Monte Carlo Mechanism
- **D-03:** Trade Sequence Shuffling. To generate the P5/P50/P95 confidence intervals, the engine will take the exact list of executed trades from the backtest and randomly shuffle their chronological sequence thousands of times. This breaks serial correlation and reveals the "true" max drawdown if the worst losses randomly clustered together.
</decisions>

<canonical_refs>
## Canonical References
- `.planning/ROADMAP.md` — Phase 15 success criteria
- `.planning/phases/14-paper-trading/14-CONTEXT.md` — Paper engine dependency
</canonical_refs>
