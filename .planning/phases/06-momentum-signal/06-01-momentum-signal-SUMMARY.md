# Plan 06-01: Momentum Signal Family

## Outcome
Implemented the first core signal family: Momentum. The module outputs a normalized `[-1.0, 1.0]` composite score combining time-series momentum (ROC) and intraday VWAP deviation. Confirmation filters (ATR percentiles, Volume ROC, and KAMA trend agreement) correctly block low-quality signals. Integrated the regime probabilities to apply a 1.3x boost when the HMM detects a favorable trend.

## Self-Check: PASSED
- [x] All tasks executed
- [x] Each task committed individually
- [x] SUMMARY.md created in plan directory
- [x] STATE.md and ROADMAP.md updated

## Artifacts

### `key-files.created`
- src/algoforge/signals/models.py
- src/algoforge/signals/momentum/vwap.py
- src/algoforge/signals/momentum/evaluator.py
- src/algoforge/signals/momentum/signal.py
- src/algoforge/signals/momentum/__init__.py
- tests/unit/test_momentum_signal.py

### `key-files.modified`
- src/algoforge/technical/indicator_base.py (Added `roc_calc`)
- src/algoforge/core/models.py (Discovered attributes for OHLCVSeries)

## Technical Notes
- `OHLCVSeries` operates on `series.candles` rather than `bars` or pure iteration.
- Handled numpy boolean return types in Python strict `assert` statements by casting `p_low <= atr <= p_high` back to a `bool()` inside the ATR filter.
- VWAP logic properly resets when the day index `tm_yday` shifts, preventing memory leakage across intraday trading sessions.
