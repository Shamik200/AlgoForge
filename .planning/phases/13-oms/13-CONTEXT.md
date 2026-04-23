# Phase 13: Order Management System (OMS) - Context

**Gathered:** 2026-04-22
**Status:** Completed (Auto-selected recommended options)

<domain>
## Phase Boundary

Implement the Order Management System (OMS) to handle the lifecycle of execution. This sits between the internal system logic (Signals, Risk, Exits) and the actual exchange/broker API. It ensures orders are tracked flawlessly, limits slippage, handles partial fills, and never executes the same signal twice.
</domain>

<decisions>
## Implementation Decisions

### Idempotency & Concurrency Strategy
- **D-01:** Correlation ID Lock. To prevent double-spending or duplicate orders when the async event bus fires rapidly, the OMS will use a strict lock (or unique constraint) keyed by `correlation_id` + `symbol` + `order_type`. Any incoming order request matching an existing active key will be silently discarded as a duplicate.

### Limit Order Time-In-Force (TIF)
- **D-02:** Candle Expiry Limits. The system mandates limit orders for entry to prevent slippage. If the market runs away and the order sits unfilled on the book, the OMS will automatically cancel it after `N` elapsed candles (e.g., 3 candles). This prevents stale limit orders from being filled during completely different market conditions hours later.

### State Machine Persistence
- **D-03:** SQLite Audit Trail. The OMS state machine (`New → Submitted → PartialFill → Filled → Cancelled → Rejected`) will be persisted in a lightweight SQLite database. This ensures ACID compliance, solves concurrency race conditions, guarantees recovery if the python process crashes mid-trade, and provides a queryable audit trail for Phase 15 backtesting and live accounting.
</decisions>

<canonical_refs>
## Canonical References
- `.planning/ROADMAP.md` — Phase 13 success criteria
- `.planning/phases/02-async-event-bus/02-CONTEXT.md` — Event bus architecture
</canonical_refs>
