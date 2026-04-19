---
gap_closure: false
---

# Plan 08-01: Breakout & Volatility Signal Family

## Objective
Implement the Breakout signal family, capturing volatility expansion via TTM Squeeze mechanics, volume-confirmed Donchian breakouts, intraday ORB, and stateless failure reversal patterns.

## Tasks

- [ ] **1. Implement Volatility Squeeze Engine**
  - Create `src/algoforge/signals/breakout/volatility.py`.
  - Implement Keltner Channels: EMA(20) and 1.5x ATR(14) bands.
  - Implement Squeeze detection: Bollinger Bands strictly inside Keltner Channels.
  - Track consecutive Squeeze duration.

- [ ] **2. Implement Breakout Detectors**
  - Create `src/algoforge/signals/breakout/donchian.py`.
  - Implement N-period Donchian Channels.
  - Detect standard breakouts (Close > Donchian High / Close < Donchian Low).
  - Implement Stateless Failure Recognition (Prev Close > High AND Current Close < High - 0.5*ATR).

- [ ] **3. Build the Volatility Breakout Signal Class**
  - Create `src/algoforge/signals/breakout/signal_volatility.py`.
  - `VolatilityBreakoutSignal`: Combines Squeeze status, Donchian Breakout, and Volume Expansion (>2x SMA).
  - Implement Regime Guard: Active only if `RegimeProbabilities.trend_up` or `trend_down` > 50%.
  - Emit failure reversal scores (e.g., -1.0 on failed bull breakout).

- [ ] **4. Build the Opening Range Breakout (ORB) Signal Class**
  - Create `src/algoforge/signals/breakout/signal_orb.py`.
  - `ORBSignal`: Intraday specifically. Tracks high/low of first N minutes of the session based on `timestamp`.
  - Emits breakout scores upon violating the opening range with volume.

- [ ] **5. Testing & Verification**
  - Create `tests/unit/test_breakout_signal.py`.
  - Test Keltner Channel and Squeeze overlap logic.
  - Test the stateless failed breakout pattern recognition.
  - Test the ORB time-boundary isolation.
