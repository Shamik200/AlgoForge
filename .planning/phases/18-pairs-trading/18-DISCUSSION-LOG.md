# Phase 18: Pairs & Cointegration Trading - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-25
**Phase:** 18-pairs-trading
**Areas discussed:** Cointegration Testing, Spread Signal Logic, Rolling Validation

---

## Cointegration Testing Method

| Option | Description | Selected |
|--------|-------------|----------|
| Engle-Granger Two-Step | OLS regression + ADF test on residuals | **YES** |
| Johansen Test | Multivariate cointegration (supports >2 series) | |

## Spread Signal Logic

| Option | Description | Selected |
|--------|-------------|----------|
| Z-Score Entry/Exit | Entry at ±2σ, exit at 0σ (mean) | **YES** |
| Bollinger Band on Spread | Use Bollinger Bands instead of raw z-score | |

## Rolling Validation

| Option | Description | Selected |
|--------|-------------|----------|
| Periodic Re-Test (252 bars) | Re-run Engle-Granger every N bars, auto-invalidate | **YES** |
| Continuous ADF Monitoring | Run ADF on every bar (expensive) | |
