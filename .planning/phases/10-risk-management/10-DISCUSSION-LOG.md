# Phase 10: Risk Management Engine - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-20
**Phase:** 10-risk-management
**Areas discussed:** Kelly Criterion Data Source, Global Account Limits & State, Correlation Limit Implementation

---

## Kelly Criterion Data Source

| Option | Description | Selected |
|--------|-------------|----------|
| Rolling Ledger | Calculate live Kelly stats from a `TradeLedger`, fallback to fixed if `< 30` trades | **YES** |
| Hardcoded Stats | Feed the engine hypothetical expected values from backtests | |

## Global Account Limits & State

| Option | Description | Selected |
|--------|-------------|----------|
| Abstract `AccountState` | Pass an injected state object into the risk evaluations | **YES** |
| Engine-Managed State | Risk Engine maintains its own shadow accounting ledger | |

## Correlation Limit Implementation

| Option | Description | Selected |
|--------|-------------|----------|
| Cached Matrix | `CorrelationMatrix` updated daily for O(1) lookups | **YES** |
| On-the-fly | Recalculate historical correlation matrices upon every new trade generation | |
