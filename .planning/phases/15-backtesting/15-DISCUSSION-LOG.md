# Phase 15: Backtesting Engine - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-25
**Phase:** 15-backtesting
**Areas discussed:** Simulation Loop Architecture, Walk-Forward Optimization Strategy, Monte Carlo Mechanism

---

## Simulation Loop Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Fast-Path Event Loop | Bypasses async event bus, directly calls simulator methods in tight loop | **YES** |
| Async Event Bus (Full) | Routes all data through Phase 2 event bus exactly like production | |

## Walk-Forward Optimization (WFO) Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Expanding Window | Train window grows (Y1, Y1+Y2) while test window stays fixed | **YES** |
| Rolling Window | Train window size stays fixed (Y1, then Y2, then Y3) sliding forward | |

## Monte Carlo Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Sequence Shuffling | Shuffle chronological order of executed trades to test drawdowns | **YES** |
| Trade Dropping | Randomly remove X% of winning trades to test robustness | |
