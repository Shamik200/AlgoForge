# Phase 13: Order Management System (OMS) - Research

## Context
The OMS sits between our internal system (Signals → Risk → Exits) and the external exchange. It ensures that every order is tracked through its full lifecycle, enforces limit-order-first execution to reduce slippage, prevents duplicate orders, and persists everything for crash recovery and audit.

## Technical Findings

1. **Order State Machine:**
   - States: `NEW → SUBMITTED → PARTIAL_FILL → FILLED → CANCELLED → REJECTED`
   - Transitions are deterministic. Once an order reaches `FILLED`, `CANCELLED`, or `REJECTED`, it is terminal.
   - Each transition emits an event on the async event bus (Phase 2) with the `correlation_id`.

2. **Order Types:**
   - **LIMIT:** Default for entries and take-profit exits. Avoids market slippage.
   - **MARKET:** Used exclusively for stop-loss exits. Speed of execution is more important than price when a stop is triggered.

3. **Correlation ID Tracking:**
   - Every order carries a `correlation_id` linking it back to the originating `SignalResult.family_name` and the event bus event that triggered it.
   - The OMS maintains a set of active `correlation_id` values. Any incoming request with a matching ID is dropped as idempotent.

4. **Candle Expiry for Limit Orders:**
   - When a LIMIT order is created, its `max_candles` field is set (default 3).
   - On each candle close tick, the OMS checks unfilled limit orders. If `elapsed_candles >= max_candles`, it transitions the order to `CANCELLED`.

5. **SQLite Persistence:**
   - A single `orders` table stores all order records.
   - Schema: `id, correlation_id, symbol, direction, order_type, price, quantity, status, created_at, updated_at`
   - On startup, the OMS loads all non-terminal orders from SQLite to rebuild in-memory state.

## Implementation Path
- Create `src/algoforge/oms/models.py` — Order data models and enums.
- Create `src/algoforge/oms/state_machine.py` — Deterministic state transition logic.
- Create `src/algoforge/oms/store.py` — SQLite persistence layer.
- Create `src/algoforge/oms/manager.py` — OMS Manager orchestrating submission, idempotency, and candle expiry.
- Create `src/algoforge/oms/__init__.py` — Public API exports.
- Create `tests/unit/test_oms.py` — Full test coverage.
