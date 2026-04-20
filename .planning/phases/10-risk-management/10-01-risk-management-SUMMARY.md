# Plan 10-01: Risk Management Engine

## Outcome
Implemented the complete Risk Management Engine. The engine combines an adaptive Kelly fractional sizing calculator with a brutal gauntlet of hard-veto killswitches to ensure absolute capital preservation.

## Self-Check: PASSED
- [x] All tasks executed
- [x] Each task committed individually
- [x] SUMMARY.md created in plan directory
- [x] STATE.md and ROADMAP.md updated

## Artifacts

### `key-files.created`
- src/algoforge/risk/models.py
- src/algoforge/risk/sizing.py
- src/algoforge/risk/correlation.py
- src/algoforge/risk/limits.py
- src/algoforge/risk/engine.py
- src/algoforge/risk/__init__.py
- tests/unit/test_risk_engine.py

### `key-files.modified`
- (none)

## Technical Notes
- Implemented a `TradeLedger` data model. If history has < 30 trades, we safely fallback to a standard fixed-fractional sizing model (1% risk). Otherwise, we use fractional Kelly scaled by the Win Rate and Payoff Ratio.
- A critical catch was found during integration testing: While Kelly might suggest a 20,000 position size on a 100,000 account, our Portfolio Rules enforce a hard limit of `max_position_pct = 0.10` (10% of equity). The test properly caught the cap executing and allocating exactly 10,000 capital instead.
- The `CorrelationMatrix` cache proved vital. Instead of doing expensive `.corr()` dataframe operations on every intraday tick to verify portfolio concentration, the engine performs O(1) dictionary lookups against a matrix computed out-of-band.
