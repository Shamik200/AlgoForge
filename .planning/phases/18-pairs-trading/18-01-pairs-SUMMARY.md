# Plan 18-01: Pairs & Cointegration Trading

## Outcome
Implemented the Pairs Trading signal family with Engle-Granger cointegration testing, spread z-score trading, and rolling re-validation. The family correctly identifies cointegrated pairs, fires signals at ±2σ deviation, and auto-invalidates when cointegration breaks.

## Self-Check: PASSED
- [x] All tasks executed
- [x] SUMMARY.md created in plan directory
- [x] STATE.md and ROADMAP.md updated

## Artifacts

### `key-files.created`
- src/algoforge/signals/pairs/cointegration.py
- src/algoforge/signals/pairs/family.py
- src/algoforge/signals/pairs/__init__.py
- tests/unit/test_pairs.py

## Technical Notes
- The Engle-Granger test uses a simplified ADF with hardcoded critical values for speed. For production use with scipy available, this could be swapped for `statsmodels.tsa.stattools.adfuller`.
- The spread z-score is inverted for the signal: a high spread (A overpriced relative to B) produces a SHORT signal (sell A, buy B).
- Rolling re-validation every 252 bars prevents trading on stale cointegration relationships.
