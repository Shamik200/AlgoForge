---
gap_closure: false
---

# Plan 18-01: Pairs & Cointegration Trading

## Objective
Implement Engle-Granger cointegration testing, spread z-score signal generation, and rolling re-validation for statistical arbitrage.

## Tasks

- [x] **1. Cointegration Testing**
  - Create `src/algoforge/signals/pairs/cointegration.py`.
  - Implement `engle_granger_test(prices_a, prices_b)`.
  - OLS hedge ratio + simplified ADF on residuals.

- [x] **2. Pairs Trading Family**
  - Create `src/algoforge/signals/pairs/family.py`.
  - Implement `PairsTradingFamily.calibrate()` and `.generate()`.
  - Rolling z-score with ±2σ entry and 0σ exit.
  - Periodic re-validation every 252 bars.

- [x] **3. Integration & Testing**
  - Create `src/algoforge/signals/pairs/__init__.py`.
  - Create `tests/unit/test_pairs.py`.
  - Test cointegration detection, signal generation, and invalidation.
