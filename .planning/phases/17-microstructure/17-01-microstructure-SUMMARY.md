# Plan 17-01: Signal Family 5 — Microstructure / Order Flow

## Outcome
Implemented the Microstructure signal family with VWAP deviation trading, Chaikin-style volume imbalance, and OBV divergence detection. The family correctly self-disables on non-intraday timeframes and automatically selects L1 or L2 mode based on data availability.

## Self-Check: PASSED
- [x] All tasks executed
- [x] SUMMARY.md created in plan directory
- [x] STATE.md and ROADMAP.md updated

## Artifacts

### `key-files.created`
- src/algoforge/signals/microstructure/vwap.py
- src/algoforge/signals/microstructure/volume.py
- src/algoforge/signals/microstructure/family.py
- src/algoforge/signals/microstructure/__init__.py
- tests/unit/test_microstructure.py

## Technical Notes
- VWAP deviation score is inverted for mean-reversion: price extended above VWAP produces a negative (short) signal.
- The composite weighting is VWAP 50%, Volume Imbalance 30%, OBV Divergence 20%.
- OBV divergence uses a 5% tolerance band to avoid false positives from minor OBV fluctuations.
