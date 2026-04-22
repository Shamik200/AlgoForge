# Plan 11-01: Signal Combination Engine

## Outcome
Implemented the full Signal Combination & Conviction Framework. The engine accurately aggregates raw signal scores across multiple strategies, normalizes them via rolling z-scores, culls redundant strategies based on rolling Pearson correlation matrices, and adaptively weights the survivors via a Sharpe-ratio Softmax.

## Self-Check: PASSED
- [x] All tasks executed
- [x] Each task committed individually
- [x] SUMMARY.md created in plan directory
- [x] STATE.md and ROADMAP.md updated

## Artifacts

### `key-files.created`
- src/algoforge/combination/normalization.py
- src/algoforge/combination/weighting.py
- src/algoforge/combination/correlation.py
- src/algoforge/combination/engine.py
- src/algoforge/combination/__init__.py
- tests/unit/test_combination_engine.py

### `key-files.modified`
- (none)

## Technical Notes
- The `SignalResult` model enforces strict JSON serializable typing in its metadata. An integration test failed originally because `engine.py` was directly passing python dict objects rather than JSON strings for the internal weights and correlation culls. This was promptly fixed.
- Because `Softmax` forces all array entries to sum to exactly `1.0`, we divide the initial z-scores by `3.0` and clip them to `[-1.0, 1.0]`. When sum-producted against Softmax weights, this mathematically guarantees the final Master Conviction composite score will always be bounded between `[-1.0, 1.0]`. 
