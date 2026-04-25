# Phase 17: Signal Family 5 — Microstructure / Order Flow - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-25
**Phase:** 17-microstructure
**Areas discussed:** VWAP Calculation Architecture, Graceful Degradation Strategy, Intraday-Only Activation Guard

---

## VWAP Calculation Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| VWAPTracker Class | Dedicated class with session-reset, cumulative volume-weighted tracking, and σ-based deviation signals | **YES** |
| Rolling VWAP | Use a rolling N-bar window instead of full session accumulation | |

## Graceful Degradation Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Automatic Mode Selection | Check data availability at init; auto-select L2 mode or L1 fallback (OBV + Volume-at-Price) | **YES** |
| Hard Requirement | Refuse to run without L2 data; raise error if unavailable | |

## Intraday-Only Activation Guard

| Option | Description | Selected |
|--------|-------------|----------|
| Timeframe Self-Disabling | Check candle resolution; return is_valid=False on >= 1D timeframes | **YES** |
| External Config Flag | Require user to manually enable/disable in config files | |
