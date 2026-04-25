# Plan 16-01: Alpha Decay Monitoring System

## Outcome
Implemented the Alpha Decay Monitor that evaluates live signal family performance against backtest baselines. The monitor generates dynamic `health_multiplier` values (0.0 to 1.0) that the Combination Engine applies after Softmax weighting and re-normalizes, ensuring capital is automatically redirected away from failing strategies.

## Self-Check: PASSED
- [x] All tasks executed
- [x] Each task committed individually
- [x] SUMMARY.md created in plan directory
- [x] STATE.md and ROADMAP.md updated

## Artifacts

### `key-files.created`
- src/algoforge/decay/models.py
- src/algoforge/decay/monitor.py
- src/algoforge/decay/__init__.py
- tests/unit/test_decay.py

### `key-files.modified`
- src/algoforge/combination/engine.py (Added health_multipliers parameter)

## Technical Notes
- The monitor evaluates three cascading rules in severity order: Hit Rate Z-score > 2σ (PAUSED), Average R < 50% baseline (PAUSED), 30-day Sharpe < 0 (DEGRADED). Most severe match wins.
- The Combination Engine re-normalizes weights after applying multipliers so surviving families absorb the freed capacity. If all families are paused, the engine returns an invalid composite signal, preventing any trades.
