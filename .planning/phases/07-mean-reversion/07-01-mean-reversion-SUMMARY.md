# Plan 07-01: Mean Reversion Signal Family

## Outcome
Implemented the Mean Reversion signal family. It outputs a normalized `[-1.0, 1.0]` composite score combining rolling VWAP z-scores and Bollinger %B extremes. Critically, we implemented strict RSI divergence logic using the structural swings engine from Phase 4, successfully mapping price pivots to RSI pivots. The signal is strictly guarded: it disables itself if the HMM mean reversion probability is < 0.40, or if concurrent momentum is extreme.

## Self-Check: PASSED
- [x] All tasks executed
- [x] Each task committed individually
- [x] SUMMARY.md created in plan directory
- [x] STATE.md and ROADMAP.md updated

## Artifacts

### `key-files.created`
- src/algoforge/signals/reversion/vwap_zscore.py
- src/algoforge/signals/reversion/divergence.py
- src/algoforge/signals/reversion/pairs.py
- src/algoforge/signals/reversion/signal.py
- src/algoforge/signals/reversion/__init__.py
- tests/unit/test_reversion_signal.py

## Technical Notes
- Leveraged the `age` attribute of `PriceLevel` to accurately sort swing points temporally, allowing us to find the exact last two structural pivots for divergence logic.
- Implemented `rolling_vwap` using `numpy.convolve` for speed rather than a slow loop.
- Built a clean interface stub for `pairs.py` to be expanded when the cross-asset orchestrator arrives in Phase 17.
