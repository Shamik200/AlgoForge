# Plan 12-01: Multi-Target Exits

## Outcome
Implemented a robust dynamic exit framework. Single trades are now cleanly split into three independent `ActivePosition` tranches (50/30/20). The engine supports ATR-anchored initial stops tied to the HMM regime, time-based breakeven tightening based on elapsed candles, and a closed-candle trailing stop ratchet for the runner tranche.

## Self-Check: PASSED
- [x] All tasks executed
- [x] Each task committed individually
- [x] SUMMARY.md created in plan directory
- [x] STATE.md and ROADMAP.md updated

## Artifacts

### `key-files.created`
- src/algoforge/exits/stops.py
- src/algoforge/exits/tranches.py
- src/algoforge/exits/manager.py
- src/algoforge/exits/__init__.py
- tests/unit/test_exits.py

### `key-files.modified`
- src/algoforge/risk/models.py

## Technical Notes
- `ActivePosition` was enhanced to support `parent_trade_id` and `tranche_id`. This effectively maps our internal risk models directly to how external brokers handle partial closing (as independent child orders).
- The `ExitManager` specifically groups active positions by `parent_trade_id` when evaluating candle closes. This allows it to check if `tranche_id=1` is still alive; if it isn't, we know TP1 was hit, and the breakeven tightening rule is correctly bypassed for the remaining tranches.
- The trailing stop (`trailing_step`) enforces a strict forward-only ratchet that only evaluates on the candle close, successfully preventing intraday wicks from causing premature stop-outs.
