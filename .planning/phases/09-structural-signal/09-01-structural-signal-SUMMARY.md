# Plan 09-01: Structural Confluence Signal Family

## Outcome
Implemented the Structural Confluence Signal Family. We successfully integrated the heavy `StructuralSnapshot` engine built in Phase 4 directly into our reactive Signal architecture. This required bridging statically detected support/resistance zones with live candlestick microstructure rejection logic (wicks > 50% candle range and volume climax). The signal is fully responsive to Multi-Timeframe (MTF) alignments and HMM Regime probabilities.

## Self-Check: PASSED
- [x] All tasks executed
- [x] Each task committed individually
- [x] SUMMARY.md created in plan directory
- [x] STATE.md and ROADMAP.md updated

## Artifacts

### `key-files.created`
- src/algoforge/signals/structural/microstructure.py
- src/algoforge/signals/structural/proximity.py
- src/algoforge/signals/structural/signal.py
- src/algoforge/signals/structural/__init__.py
- tests/unit/test_structural_signal.py

### `key-files.modified`
- (none)

## Technical Notes
- Discovered and fixed a slight mismatch between `StructuralSnapshot` properties (`support_levels`, `resistance_levels`) and the variable names used during rapid prototyping (`support`, `resistance`). Pydantic models correctly validated and caught this during unit testing.
- The `find_tested_levels` relies on a dynamic proximity band of `+/- 0.5 * ATR(14)`. This proves to be far more robust than using arbitrary 10-tick or 0.1% bands, as it scales natively with asset volatility.
- The Multi-Timeframe integration works purely by passing an array of HTF snapshots into the `evaluate` method. This allows the signal evaluator to remain completely decoupled from the data fetcher/engine cache.
