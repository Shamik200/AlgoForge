# Phase 9: Signal Family 4 — Structural Confluence - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-20
**Phase:** 09-structural-signal
**Areas discussed:** "Approaches" Proximity Threshold, Reversal Micro-Structure, Multi-Timeframe Integration

---

## "Approaches" Proximity Threshold

| Option | Description | Selected |
|--------|-------------|----------|
| ATR-Based | Level is tested if price enters `+/- 0.5 * ATR(14)` of the level | **YES** |
| Fixed Percentage | Rigid percentage band (e.g. 0.1%) | |

## Reversal Micro-Structure (Candlesticks)

| Option | Description | Selected |
|--------|-------------|----------|
| Strict Math | Wick > 50% of candle range AND Volume > 1.5x SMA | **YES** |
| Subjective | Loose pattern matching | |

## Multi-Timeframe Integration Mechanics

| Option | Description | Selected |
|--------|-------------|----------|
| HTF Snapshot Overlap | Pass HTF snapshots into `evaluate()`; multiply score by 1.5x if level aligns | **YES** |
| Implicit Weights | Only evaluate the highest timeframe possible and ignore LTF | |
