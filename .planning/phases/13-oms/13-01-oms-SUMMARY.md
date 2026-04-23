# Plan 13-01: Order Management System (OMS)

## Outcome
Implemented the full OMS with deterministic state machine, SQLite persistence, idempotent submission, and candle-based limit order expiry. The system correctly enforces limit-order-first execution with market orders reserved exclusively for stop-loss exits.

## Self-Check: PASSED
- [x] All tasks executed
- [x] Each task committed individually
- [x] SUMMARY.md created in plan directory
- [x] STATE.md and ROADMAP.md updated

## Artifacts

### `key-files.created`
- src/algoforge/oms/models.py
- src/algoforge/oms/state_machine.py
- src/algoforge/oms/store.py
- src/algoforge/oms/manager.py
- src/algoforge/oms/__init__.py
- tests/unit/test_oms.py

### `key-files.modified`
- (none)

## Technical Notes
- The state machine uses a strict allowlist of valid transitions. Terminal states (FILLED, CANCELLED, REJECTED) have zero outgoing edges, making it impossible to accidentally resurrect a closed order.
- The SQLite store uses `:memory:` mode in tests for speed and isolation. In production, it writes to `oms_orders.db` for crash recovery.
- Market orders are explicitly exempt from the candle expiry logic, since SL exits must execute immediately regardless of time.
- The `OrderManager` maintains an in-memory `_active_ids` set for O(1) idempotency checks, backed by the SQLite store for durability across restarts.
