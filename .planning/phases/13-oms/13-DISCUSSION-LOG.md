# Phase 13: Order Management System (OMS) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-22
**Phase:** 13-oms
**Areas discussed:** Idempotency & Concurrency Strategy, Limit Order Time-In-Force, State Machine Persistence

---

## Idempotency & Concurrency Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Correlation ID Lock | Use unique constraint on correlation_id + symbol to drop duplicates | **YES** |
| Queue Debouncing | Add a time delay and debounce incoming signals before processing | |

## Limit Order Time-In-Force (TIF)

| Option | Description | Selected |
|--------|-------------|----------|
| Candle Expiry | Cancel unfilled limit orders after N candles | **YES** |
| Wait Indefinitely | Leave limit orders GTC (Good 'Til Cancelled) forever | |

## State Machine Persistence

| Option | Description | Selected |
|--------|-------------|----------|
| SQLite Audit Trail | Store order states in ACID-compliant SQLite db | **YES** |
| In-Memory Dict | Store order states purely in RAM (lost on crash) | |
