# Phase 2: Async Event Bus & Message Architecture - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-19
**Phase:** 02-async-event-bus
**Areas discussed:** Event Transport, Correlation ID Design, Concurrency Model, Event Schema

---

## Event Transport (Redis Streams vs asyncio.Queue)

| Option | Description | Selected |
|--------|-------------|----------|
| Hybrid | asyncio.Queue for hot dispatch + Redis Streams for durable log/replay | ✓ |
| Redis Streams only | All events flow through Redis — single source of truth | |
| asyncio.Queue only | Pure in-memory, simplest, no durability | |

**User's choice:** Hybrid (asyncio.Queue + Redis Streams)
**Notes:** Keeps <1ms dispatch latency for hot path while enabling crash recovery and audit via Redis Streams async write.

---

## Correlation ID Design

| Option | Description | Selected |
|--------|-------------|----------|
| Signal-chain ID | Single UUID per trade lifecycle | |
| Candle-origin ID | UUID inherited from data source through chain | |
| Hierarchical | Own UUID (`event_id`) + `parent_id` for DAG tracing | ✓ |

**User's choice:** Hierarchical (own ID + parent ID)
**Notes:** Enables one candle → multiple signals → multiple orders DAG tracing. Root `correlation_id` field for quick lifecycle filtering.

---

## Concurrency Model for 100+ Instruments

| Option | Description | Selected |
|--------|-------------|----------|
| Per-instrument task | Dedicated asyncio.Task per symbol | |
| Worker pool | Fixed N workers pulling from shared queue | ✓ |
| Semaphore-bounded fan-out | asyncio.gather() with Semaphore(N) | |

**User's choice:** Worker pool (fixed N workers, shared queue)
**Notes:** Default 20 workers, configurable via settings. Queue depth as health metric and backpressure signal.

---

## Event Schema Evolution

| Option | Description | Selected |
|--------|-------------|----------|
| Migrate to Pydantic | Full consistency with rest of system | ✓ |
| Keep dataclass + serialization | Add manual to_dict/from_dict methods | |
| Pydantic + msgpack | Binary serialization for speed | |

**User's choice:** Migrate to Pydantic
**Notes:** Full consistency with OHLCV, Signal, Config. JSON serialization free via model_dump_json(). msgpack deferred as optimization.

## Agent's Discretion

- Redis Streams key naming, retention policy, consumer group naming
- Worker pool shutdown/drain strategy
- Event priority and backpressure threshold defaults
- Serialization format details (start JSON, optimize later)

## Deferred Ideas

None — discussion stayed within phase scope
