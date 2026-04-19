# Phase 6: Signal Family 1 — Momentum - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-19
**Phase:** 06-momentum-signal
**Areas discussed:** Cross-Sectional Architecture, Intraday Adaptation Logic, Composite Z-Score Normalization

---

## Cross-Sectional Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Central Coordinator | Signal emits raw scores; central `SignalCombiner` handles cross-asset ranking | **YES** |
| Local State | Signal maintains global universe state and ranks itself | |

## Intraday Adaptation Logic

| Option | Description | Selected |
|--------|-------------|----------|
| Snapshot Dependency | Rely on `IndicatorEngine` for 1H/4H snapshots; compute VWAP dynamically | **YES** |
| Local Calculation | Calculate all higher timeframe data locally inside the signal | |

## Composite Z-Score Normalization

| Option | Description | Selected |
|--------|-------------|----------|
| Equal-Weighting | Equal weight the sub-signals, apply 1.3x regime boost, clip to [-1, 1] | **YES** |
| Volatility Weighting | Inverse-volatility weight the sub-signals | |
