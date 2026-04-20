---
gap_closure: false
---

# Plan 10-01: Risk Management Engine

## Objective
Implement the complete Risk Management system. This includes fractional Kelly position sizing powered by a rolling Trade Ledger, hard-veto limits based on an abstract Account State, Portfolio Concentration checks, and a cached Correlation Matrix.

## Tasks

- [ ] **1. Core Risk Data Models**
  - Create `src/algoforge/risk/models.py`.
  - Implement `AccountState` (equity, drawdowns, pnl, consecutive_losses).
  - Implement `TradeRecord` and `TradeLedger` to calculate Win Rate and Payoff Ratio.
  - Implement `ActivePosition` (symbol, sector, direction, size).
  - Implement `RiskEvaluation` (result model with size and boolean approval).

- [ ] **2. Position Sizing Engine**
  - Create `src/algoforge/risk/sizing.py`.
  - Implement `calculate_kelly_fraction` using `TradeLedger`.
  - Implement fallback `fixed_fractional` sizing.
  - Output exact capital allocation based on `AccountState.current_equity`.

- [ ] **3. Correlation Matrix Cache**
  - Create `src/algoforge/risk/correlation.py`.
  - Implement `CorrelationMatrix` class.
  - Needs `update(returns_df)` to compute matrix, and `get_correlation(sym_a, sym_b)` for O(1) lookups.

- [ ] **4. Hard Limits & Veto Rules**
  - Create `src/algoforge/risk/limits.py`.
  - Implement `check_account_limits` (Daily Loss, Drawdown, Consecutive Losses).
  - Implement `check_portfolio_limits` (Sector cap, Directional cap, Max Open, Correlation).
  - Implement `check_trade_limits` (Circuit breakers, Liquidity, Min R:R).

- [ ] **5. Risk Engine Orchestrator**
  - Create `src/algoforge/risk/engine.py`.
  - `RiskEngine` class tying sizing and limits together.
  - `evaluate_trade(trade_request, account_state, active_positions)` -> `RiskEvaluation`.

- [ ] **6. Testing & Verification**
  - Create `tests/unit/test_risk_engine.py`.
  - Test Kelly math and fallback logic.
  - Test account killswitches (drawdown vetoes).
  - Test portfolio concentration and correlation limiters.
