# Phase 7: Signal Family 2 — Mean Reversion - Research

## Context
Building the Mean Reversion Signal Family which seeks to exploit temporary overextensions in range-bound or reverting markets. The signal outputs a normalized `[-1.0, 1.0]` composite score.

## Technical Findings

1. **VWAP Z-Score (40% weight):**
   - We need a rolling N-period (e.g. 20) VWAP, not just the session VWAP from Phase 6.
   - Formula: $\text{Rolling VWAP} = \frac{\sum_{i=0}^{N} (P_i \times V_i)}{\sum_{i=0}^{N} V_i}$
   - Z-Score: $(P - \text{Rolling VWAP}) / \text{StdDev(Price)}$.
   - Signal: Inverse to the Z-score. If price is 2 standard deviations above VWAP, the signal is strongly negative (short), expecting a reversion to the mean.

2. **Bollinger %B & RSI Divergence (30% weight):**
   - %B quantifies where price is relative to the Bollinger Bands: $\%B = (\text{Price} - \text{Lower Band}) / (\text{Upper Band} - \text{Lower Band})$.
   - Extremes are defined as `%B < 0.05` (oversold, look for longs) or `%B > 0.95` (overbought, look for shorts).
   - **RSI Divergence:** We must use Phase 4 structural swings. 
     - *Bullish Divergence:* Price makes a lower low, but RSI makes a higher low.
     - *Bearish Divergence:* Price makes a higher high, but RSI makes a lower high.
   - This sub-signal only activates when *both* the %B extreme and the divergence condition are met concurrently.

3. **Pairs/Relative Value Stub (30% weight):**
   - Since cross-asset architecture doesn't exist yet, we will provide a stub function `evaluate_pairs()` that currently returns `0.0`.

4. **Guards & Circuit Breakers:**
   - **Regime Guard:** The signal is completely deactivated (`is_valid = False`) if the HMM regime probability for `mean_revert` is less than `0.40`.
   - **Anti-Trend Guard:** The signal disables itself if the concurrent `MomentumSignalResult.score` is `> 0.80` (strong uptrend, don't short) or `< -0.80` (strong downtrend, don't buy).

5. **Regime Alignment (Composite Z-Score):**
   - Base Score = (VWAP Score * 0.40) + (Bollinger Score * 0.30) + (Pairs Score * 0.30)
   - Multiply by 1.3x if `RegimeState == MEAN_REVERT`.
   - Hard clip to `[-1.0, 1.0]`.

## Implementation Path
- Create `src/algoforge/signals/reversion/`
- Implement `RollingVWAP` calculator
- Implement `DivergenceDetector` using the `detect_swings` function from Phase 4
- Create `MeanReversionSignal` class inheriting from `SignalProvider` interface
- Unit tests focusing on the divergence matching and the circuit breaker logic
