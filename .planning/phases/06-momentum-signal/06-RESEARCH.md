# Phase 6: Signal Family 1 — Momentum - Research

## Context
Building the Momentum Signal Family (Sub-signals: Time-series, Intraday VWAP) which outputs a composite z-score normalized to `[-1, 1]`.

## Technical Findings

1. **Time-Series Momentum:**
   - Calculation: `sign(Trailing 12M Return)`. To avoid short-term mean reversion (the 1-month reversal effect), literature suggests skipping the most recent month. i.e., Momentum = Return from `t-12m` to `t-1m`.
   - On lower timeframes (e.g., 1H/4H), time-series momentum can be adapted to compare current price vs the N-period trailing moving average, or simply the N-period Rate of Change (ROC).

2. **Intraday VWAP Momentum:**
   - VWAP (Volume-Weighted Average Price) is calculated intra-day and resets at the market open.
   - Formula: $\text{VWAP} = \frac{\sum (\text{Typical Price} \times \text{Volume})}{\sum \text{Volume}}$, where $\text{Typical Price} = (H+L+C)/3$.
   - Signal generation: Distance from VWAP. When price is > VWAP, it signifies intraday bullish momentum. The deviation (z-score of distance) can be used as the momentum strength.

3. **Confirmation Filters:**
   - **KAMA (Kaufman's Adaptive Moving Average):** Confirms trend direction. Signal is valid if `price > KAMA` (long) or `price < KAMA` (short).
   - **ROC Volume Confirmation:** Ensures momentum is backed by volume. `ROC(Volume) > 0`.
   - **ATR Percentile:** Filters out "choppy" low-volatility environments and "exhausted" extreme-volatility environments. Signal is valid if current ATR is between the 20th and 80th percentile of its historical distribution.

4. **Regime Alignment (Composite Z-Score):**
   - The final score is equal-weighted across the sub-signals.
   - We receive the `RegimeProbabilities` from Phase 5.
   - If `Regime.dominant_regime` is `TREND_UP` (for longs) or `TREND_DOWN` (for shorts), the final composite score receives a 1.3x multiplier.
   - The result is hard-clipped: `np.clip(score, -1.0, 1.0)`.

## Implementation Path
- Create `src/algoforge/signals/momentum/`.
- Implement `VWAPCalculator` for resetting intraday logic.
- Implement `TimeSeriesMomentum` evaluator.
- Create `MomentumSignal` class that inherits from a base `SignalProvider` interface.
- Output a structured `SignalResult` containing the score and the boolean confirmation flags.
