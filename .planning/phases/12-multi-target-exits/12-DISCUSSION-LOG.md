# Phase 12: Multi-Target Exits - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-22
**Phase:** 12-multi-target-exits
**Areas discussed:** Position Data Architecture, Time-Based Tightening Mechanism, Trailing Stop Ratchet Logic

---

## Position Data Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Tranche Architecture | Split one trade into 3 independent ActivePosition objects linked by parent_id | **YES** |
| Array Architecture | Keep 1 ActivePosition object with lists for active targets/sizes | |

## Time-Based Tightening Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Candle Periods | Count elapsed candle bars to trigger tightening (breakeven) | **YES** |
| Clock Time | Count absolute seconds/minutes elapsed | |

## Trailing Stop Ratchet Logic (TP3)

| Option | Description | Selected |
|--------|-------------|----------|
| Closed-Candle | Ratchet trailing stop only upon candle close | **YES** |
| Tick-Level | Ratchet trailing stop dynamically on every intra-candle high/low | |
