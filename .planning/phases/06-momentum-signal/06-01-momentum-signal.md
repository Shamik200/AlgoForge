---
gap_closure: false
---

# Plan 06-01: Momentum Signal Family

## Objective
Implement the Momentum signal family, generating a `[-1.0, 1.0]` composite score using time-series momentum, VWAP adaptation, and KAMA/ATR confirmation filters, with a regime-aware boost.

## Tasks

- [ ] **1. Define Signal Output Models**
  - Create `src/algoforge/signals/models.py`.
  - Define `SignalDirection` Enum (LONG, SHORT, NEUTRAL).
  - Define `SignalResult` Pydantic model (score, direction, sub_scores dict, is_valid boolean).

- [ ] **2. Implement VWAP Calculator**
  - Create `src/algoforge/signals/momentum/vwap.py`.
  - Implement dynamic, session-resetting VWAP calculation based on Tick or 1-minute OHLCV data.

- [ ] **3. Implement Momentum Evaluator**
  - Create `src/algoforge/signals/momentum/evaluator.py`.
  - Implement time-series momentum (ROC).
  - Implement confirmation logic (KAMA trend agreement, Volume ROC > 0).
  - Implement ATR 20th-80th percentile filter check.

- [ ] **4. Build the Momentum Signal Class**
  - Create `src/algoforge/signals/momentum/signal.py`.
  - Combine VWAP deviation and time-series momentum into an equal-weighted composite score.
  - Apply the 1.3x multiplier if the `RegimeProbabilities` indicates a strong trend in the direction of the signal.
  - Hard-clip the final output to `[-1.0, 1.0]`.

- [ ] **5. Testing & Verification**
  - Create `tests/unit/test_momentum_signal.py`.
  - Test VWAP session reset logic.
  - Test the regime boost logic and bounds clipping.
  - Test confirmation filters (ATR percentile exclusion and KAMA agreement).
