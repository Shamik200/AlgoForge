# Phase 7: Signal Family 2 — Mean Reversion - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-19
**Phase:** 07-mean-reversion
**Areas discussed:** RSI Divergence Definition, Pairs/Relative Value Architecture, Anti-Trend Guard Coupling

---

## RSI Divergence Definition

| Option | Description | Selected |
|--------|-------------|----------|
| Strict Pivot Matching | Use Phase 4 swing detection to rigorously match price/RSI pivots | **YES** |
| Simplified Proxy | Just check if price is at N-period extreme while RSI is not | |

## Pairs/Relative Value Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Placeholder Stub | Create stub returning 0; implement full logic in Phase 17 | **YES** |
| Full Cointegration | Build cross-asset coordinator and cointegration math now | |

## Anti-Trend Guard Coupling

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit Input | Pass Momentum score into evaluate() to disable signal internally | **YES** |
| Orchestrator Suppression | Let strategy orchestrator override the signal externally | |
