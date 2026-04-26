# Phase 18: Pairs & Cointegration Trading - Research

## Context
Statistical arbitrage between cointegrated instruments. Instead of predicting directional moves, we trade the mean-reverting spread between two correlated assets.

## Technical Findings

1. **Engle-Granger Two-Step:**
   - Step 1: OLS regression `A = β*B + α + ε` to get hedge ratio β.
   - Step 2: ADF test on residuals ε. If stationary (p < 0.05), the pair is cointegrated.
   - Critical values (n>100): 1% = -3.43, 5% = -2.86, 10% = -2.57.

2. **Spread Z-Score Trading:**
   - Spread = A - (β × B).
   - Rolling z-score = (spread - mean) / std over a configurable window (default 60 bars).
   - Entry at ±2σ: z < -2 → buy A sell B, z > +2 → sell A buy B.
   - Exit at z = 0 (mean reversion complete).

3. **Rolling Re-Validation:**
   - Every 252 bars (1 year for daily), re-run cointegration test.
   - If the pair is no longer cointegrated, auto-invalidate and stop trading.

## Implementation Path
- Create `src/algoforge/signals/pairs/cointegration.py` — Engle-Granger test.
- Create `src/algoforge/signals/pairs/family.py` — PairsTradingFamily.
- Create `tests/unit/test_pairs.py`.
