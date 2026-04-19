# Phase 8: Signal Family 3 — Breakout / Volatility Expansion - Research

## Context
Building the Breakout Signal Family which seeks to exploit volatility expansion and momentum ignition. The signal targets low-volatility compressions (squeezes) and opening ranges, outputting a normalized `[-1.0, 1.0]` composite score.

## Technical Findings

1. **Volatility Squeeze (TTM Squeeze Variant):**
   - **Keltner Channel Math:** Centerline is EMA(20). Bands are Centerline +/- (1.5 * ATR(14)).
   - **Bollinger Band Math:** SMA(20) +/- (2.0 * StdDev(20)).
   - **Squeeze Condition:** Bollinger Upper Band < Keltner Upper Band AND Bollinger Lower Band > Keltner Lower Band.
   - **Duration:** Track consecutive bars where the squeeze condition is true. Longer squeezes yield higher conviction upon breakout.

2. **Donchian Breakout & Volume Confirmation:**
   - **Donchian Channels:** rolling N-period High and N-period Low (usually N=20).
   - **Breakout Condition:** Current close > Donchian High (Long) or Current close < Donchian Low (Short).
   - **Volume Confirmation:** Current volume > 2 * SMA_Volume(20).

3. **Opening Range Breakout (ORB):**
   - **Time logic:** Capture the High and Low of the first 30 minutes of the trading session (e.g. 09:30 - 10:00 EST).
   - **Breakout:** Price closes above Opening Range High or below Opening Range Low.
   - **Volume:** Also requires volume expansion.
   - *Note:* This will be isolated into a specific `ORBSignal` class.

4. **Breakout Failure Reversal:**
   - **Stateless Detection:** 
     - *Failed Bull Breakout:* Previous Close > Donchian High(20) AND Current Close < Donchian High(20) - 0.5 * ATR.
     - *Failed Bear Breakout:* Previous Close < Donchian Low(20) AND Current Close > Donchian Low(20) + 0.5 * ATR.
   - Reverses the signal (e.g., if bull breakout fails, generate a Short signal `[-0.5, -1.0]`).

5. **Guards & Circuit Breakers:**
   - **Regime Guard:** Signal active only if HMM `trend_up` or `trend_down` > 50%.
   - **Output Scaling:** Base score scales with Squeeze Duration (up to max multiplier) and Volume Ratio.

## Implementation Path
- Create `src/algoforge/signals/breakout/`
- Implement `volatility.py` for Keltner Channels and Squeeze detection.
- Implement `donchian.py` for standard breakout channels.
- Create `VolatilityBreakoutSignal` class for squeeze + donchian logic.
- Create `ORBSignal` class for intraday opening range logic.
- Unit tests focusing on detecting squeezes and failed breakout patterns.
