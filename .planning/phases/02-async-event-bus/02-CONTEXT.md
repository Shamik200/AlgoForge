# Phase 2: Async Event Bus & Message Architecture - Context

**Gathered:** 2026-04-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the asyncio event-driven backbone with hybrid event transport (asyncio.Queue for hot dispatch + Redis Streams for durable persistence), hierarchical correlation IDs for full event traceability, worker pool concurrency model for 100+ instruments, and Pydantic-based event schema. Upgrade the existing v1 EventBus to production-grade while maintaining backward compatibility with the existing pipeline integration.

</domain>

<decisions>
## Implementation Decisions

### Event Transport (D-01)
- **D-01:** Use **hybrid transport** — asyncio.Queue for real-time in-process dispatch (keeps <1ms latency) + Redis Streams for durable event log/replay/audit. Events are dispatched immediately via Queue, then written asynchronously to Redis Streams. Consumer groups enable future cross-process event consumption.

### Correlation ID Design (D-02)
- **D-02:** Use **hierarchical correlation IDs** — each event gets its own UUID (`event_id`) plus a `parent_id` field pointing to the event that caused it. A MarketDataEvent has no parent; a SignalEvent's parent_id = the MarketDataEvent that triggered it; an OrderEvent's parent_id = the SignalEvent. This creates a full DAG: one candle → multiple signals → multiple orders. All events also carry a `correlation_id` (the root event_id of the chain) for quick filtering of entire trade lifecycles.

### Concurrency Model (D-03)
- **D-03:** Use **worker pool** with configurable pool size (default 20 workers) pulling from a shared asyncio.Queue. Each worker processes one instrument at a time (fetch → normalize → store → publish). Queue depth serves as a natural backpressure signal and health metric. If queue grows past configurable threshold → emit alert event. Pool size configurable via `settings.yaml`.

### Event Schema (D-04)
- **D-04:** **Migrate all event types from dataclass to Pydantic BaseModel** — full consistency with the rest of the system (OHLCV, Signal, Config are all Pydantic). JSON serialization comes free via `.model_dump_json()` for Redis Streams. Existing 5 event types (Event, MarketDataEvent, SystemEvent, SignalEvent, OrderEvent, RiskEvent) get rewritten as Pydantic models. FillEvent added for order lifecycle completion.

### Agent's Discretion
- Redis Streams key naming convention and retention policy
- Worker pool shutdown/drain strategy
- Event priority levels (if any)
- Redis Streams consumer group naming
- Backpressure threshold defaults
- Event serialization format for Redis Streams (JSON vs msgpack — start with JSON, optimize later if needed)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & Design
- `refined_trading_system_prompt.md` — Master system design; Tech Infrastructure section for event-driven architecture requirements
- `.planning/PROJECT.md` — Constraints: async/await, <50ms signal-to-order latency, 1000+ instruments
- `.planning/ROADMAP.md` — Phase 2 success criteria (6 items)

### Existing Code (upgrade base)
- `src/algoforge/core/event_bus.py` — v1 EventBus with asyncio.Queue, 5 event types (dataclass), topic-based pub/sub, stats tracking. This is the file being upgraded.
- `src/algoforge/__main__.py` — Application entry point; wires EventBus + DataPipeline + Feed; already runs event bus + polling as concurrent tasks
- `src/algoforge/data/pipeline.py` — DataPipeline already publishes MarketDataEvent on new candles; uses `event_bus.publish()` API

### Prior Phase Context
- `.planning/phases/01-foundation-data/01-CONTEXT.md` — Phase 1 decisions (dual storage, feed adapters, config system)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `event_bus.py`: Working v1 bus with subscribe/publish/start/stop lifecycle — upgrade in place
- `event_bus.py`: 5 event types already defined (MarketData, System, Signal, Order, Risk) — migrate to Pydantic
- `__main__.py`: Concurrent task pattern (`asyncio.create_task` for bus + polling) — extend with worker pool
- `redis_store.py`: Redis connection management — reuse for Redis Streams connection

### Established Patterns
- asyncio for all I/O (feeds, storage, event dispatch)
- structlog for JSON logging with context binding
- Pydantic BaseModel for all data structures
- `get_settings()` singleton for configuration access

### Integration Points
- `pipeline.py` → `event_bus.publish(MarketDataEvent(...))` — must keep this API stable
- `__main__.py` → `EventBus()` construction, `event_bus.start()`, `event_bus.stop()` lifecycle
- `redis_store.py` → Redis connection can be shared for Streams (same Redis instance)
- Future phases (6-9, 10-13) will subscribe to SignalEvent, OrderEvent, RiskEvent

</code_context>

<specifics>
## Specific Ideas

- The <50ms latency target (PROJECT.md) is for signal-to-order internal latency excluding network — the hybrid transport (asyncio.Queue for hot path) ensures this since Queue dispatch is <1ms
- Redis Streams write happens asynchronously (fire-and-forget or buffered batch write) so it doesn't block the hot path
- Worker pool size of 20 is a starting default — can be tuned based on actual instrument count and system resources

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-async-event-bus*
*Context gathered: 2026-04-19*
