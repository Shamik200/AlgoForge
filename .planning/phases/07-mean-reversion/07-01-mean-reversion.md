---
gap_closure: false
---

# Plan 07-01: Mean Reversion Signal Family

## Objective
Implement the Mean Reversion signal family, generating a `[-1.0, 1.0]` composite score using VWAP deviations, Bollinger %B extremes confirmed by RSI divergence, and guarded by regime probabilities and momentum exhaustion.

## Tasks

- [ ] **1. Implement Rolling VWAP Calculator**
  - Create `src/algoforge/signals/reversion/vwap_zscore.py`.
  - Implement a sliding window VWAP (N-period) and calculate the z-score of the current price relative to this VWAP.

- [ ] **2. Implement Divergence Detector**
  - Create `src/algoforge/signals/reversion/divergence.py`.
  - Integrate with `detect_swings` from Phase 4 (`algoforge.technical.structure`).
  - Calculate RSI (if not passed directly) and detect RSI swings.
  - Implement logic to compare Price Pivot Lows with RSI Pivot Lows (Bullish Divergence).
  - Implement logic to compare Price Pivot Highs with RSI Pivot Highs (Bearish Divergence).

- [ ] **3. Implement Pairs Trading Stub**
  - Create `src/algoforge/signals/reversion/pairs.py`.
  - Provide an interface returning 0.0 for the current iteration (to be expanded in Phase 17).

- [ ] **4. Build the Mean Reversion Signal Class**
  - Create `src/algoforge/signals/reversion/signal.py`.
  - Combine Sub-signals: Rolling VWAP z-score (40%), Bollinger %B extreme + Divergence (30%), Pairs (30%).
  - Implement **Regime Guard**: Disable signal if `RegimeProbabilities.mean_revert < 0.40`.
  - Implement **Anti-Trend Guard**: Disable signal if `MomentumSignalResult.score` is extreme (`> 0.80` or `< -0.80`).
  - Apply the 1.3x multiplier if `RegimeState == MEAN_REVERT`.
  - Hard-clip final output to `[-1.0, 1.0]`.

- [ ] **5. Testing & Verification**
  - Create `tests/unit/test_reversion_signal.py`.
  - Test rolling VWAP logic.
  - Test the divergence detection math against hardcoded swing scenarios.
  - Test the circuit breakers (Regime minimum probability and Anti-Trend Guard).
