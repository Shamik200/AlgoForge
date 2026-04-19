# Phase 8: Signal Family 3 — Breakout / Volatility Expansion - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-19
**Phase:** 08-breakout-signal
**Areas discussed:** Breakout Failure Reversal, Keltner Channel Math, ORB Architecture

---

## Breakout Failure Reversal

| Option | Description | Selected |
|--------|-------------|----------|
| Stateless Pattern | `evaluate()` determines failures purely from recent historical bars | **YES** |
| State-bearing | The signal class remembers internal state across evaluations | |

## Keltner Channel Math

| Option | Description | Selected |
|--------|-------------|----------|
| EMA(20) / ATR(14) 1.5x | Standardized TTM squeeze math wrapping BB(20,2) | **YES** |
| SMA / High-Low | Traditional Keltner calculation | |

## Opening Range Breakout (ORB) Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Split Classes | Create `VolatilityBreakoutSignal` and `ORBSignal` separately | **YES** |
| Single Class | Combine all logic with runtime config checks for timeframe | |
