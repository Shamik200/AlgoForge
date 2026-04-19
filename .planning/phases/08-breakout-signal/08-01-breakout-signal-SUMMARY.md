# Plan 08-01: Breakout & Volatility Signal Family

## Outcome
Implemented the Breakout and Volatility Expansion signal family. We successfully decoupled the timeframe-agnostic Volatility Breakout from the intraday-specific Opening Range Breakout (ORB). The system effectively calculates TTM-style squeezes by tracking Bollinger Band compressions inside Keltner Channels. Most importantly, it supports a fully stateless recognition of "failed breakouts" (reversals) ensuring our signal models remain pure functions without tracking state arrays.

## Self-Check: PASSED
- [x] All tasks executed
- [x] Each task committed individually
- [x] SUMMARY.md created in plan directory
- [x] STATE.md and ROADMAP.md updated

## Artifacts

### `key-files.created`
- src/algoforge/signals/breakout/volatility.py
- src/algoforge/signals/breakout/donchian.py
- src/algoforge/signals/breakout/signal_volatility.py
- src/algoforge/signals/breakout/signal_orb.py
- src/algoforge/signals/breakout/__init__.py
- tests/unit/test_breakout_signal.py

### `key-files.modified`
- src/algoforge/technical/indicator_base.py (Added `sma_calc` and `atr_calc` helpers).

## Technical Notes
- Discovered that `sma_calc` and `atr_calc` were missing from our foundational `indicator_base.py` module during testing. Added these core mathematical building blocks to avoid repeating standard SMA/ATR loops inside the signal logic.
- ORB handles session times correctly using datetime `time` checks against the standard 30-minute session opening block.
- Volatility squeezes perfectly scale their output conviction `(0.5 + 0.5 * duration)` ensuring massive expansions post-squeeze are weighted heavier than standard breakout chops.
