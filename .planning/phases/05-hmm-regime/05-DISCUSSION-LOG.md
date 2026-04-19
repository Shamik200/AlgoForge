# Phase 5: HMM Probabilistic Regime Detector - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-19
**Phase:** 05-hmm-regime
**Areas discussed:** Feature Preprocessing, Cross-Asset Data Alignment, Retraining Pipeline, Defining the Uncertainty Flag

---

## Feature Preprocessing

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-smoothed inputs | Apply fast EMA before feeding to HMM to ensure smooth transitions | **YES** |
| Raw inputs | Feed raw returns/volatility directly to HMM | |

## Cross-Asset Data Alignment

| Option | Description | Selected |
|--------|-------------|----------|
| Forward-fill | Carry forward last known value to prevent lookahead bias | **YES** |
| Interpolation | Linearly interpolate missing data | |

## Retraining Pipeline

| Option | Description | Selected |
|--------|-------------|----------|
| Offline scheduled job | Background weekly job drops new model file, preventing live latency | **YES** |
| Synchronous retraining | Engine pauses to retrain on first tick of the week | |

## Defining the Uncertainty Flag

| Option | Description | Selected |
|--------|-------------|----------|
| Probability entropy | Flag if probabilities are too evenly spread or contradict VIX directly | **YES** |
| Absolute distance | Flag based solely on numeric divergence | |
