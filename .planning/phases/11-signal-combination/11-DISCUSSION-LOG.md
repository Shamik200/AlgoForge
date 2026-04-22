# Phase 11: Signal Combination Framework - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-22
**Phase:** 11-signal-combination
**Areas discussed:** Signal Z-Score Normalization Window, Adaptive Weighting Function, Decorrelation Tie-Breaker Routing

---

## Signal Z-Score Normalization Window

| Option | Description | Selected |
|--------|-------------|----------|
| Rolling 100-Period | Track history via a rolling 100-bar window | **YES** |
| Expanding Window | Track all history since system initialization | |

## Adaptive Weighting Function

| Option | Description | Selected |
|--------|-------------|----------|
| Softmax | Use softmax over Sharpe ratios to ensure sum=1.0 and penalize negative Sharpes | **YES** |
| Linear / Rank | Linearly scale weights or rank them 1-N | |

## Decorrelation Tie-Breaker Routing

| Option | Description | Selected |
|--------|-------------|----------|
| Softmax Recalculation | Set weaker signal to 0.0 and recalculate softmax over remaining | **YES** |
| Hard Distribution | Redistribute weight explicitly to other signals manually | |
