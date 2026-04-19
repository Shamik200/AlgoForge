# Phase 3: Orthogonal Indicator Engine (7 Indicators) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-19
**Phase:** 03-indicator-engine
**Areas discussed:** Engine Restructuring, KAMA Implementation, Caching Granularity

---

## Engine Restructuring

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed 7+3 | Hardcode exactly 7 orthogonal + 3 tools, remove rest | |
| Registry pattern | Config-driven indicator selection from registry | |
| Two-tier | Core 7 always computed, supporting tools optional | ✓ |

**User's choice:** Two-tier (core 7 fixed + optional supporting tools)
**Notes:** Old indicators (MACD, Stochastic, Supertrend, Ichimoku, EMA) stay in codebase but removed from default engine.

---

## KAMA/ROC Implementation

| Option | Description | Selected |
|--------|-------------|----------|
| Pure NumPy | Consistent with all v1 indicators, no new deps | ✓ |
| pandas-ta | Battle-tested library, adds ~20MB dependency | |
| ta-lib | C-based, 10× faster, painful Windows/CI install | |

**User's choice:** Pure NumPy
**Notes:** User considered ta-lib for speed but chose consistency. Performance target (100×6 in 1s) is easily met with NumPy. Can swap to ta-lib later behind Indicator ABC if needed.

---

## Caching Granularity

| Option | Description | Selected |
|--------|-------------|----------|
| Unlimited in-memory | Current v1 pattern, no eviction | ✓ |
| LRU cache | Bounded entries, evicts least-recently-used | |
| TTL-based | Time-limited entries | |

**User's choice:** Unlimited in-memory
**Notes:** 600 entries is trivial memory. Engine recomputes on every candle so cache is always fresh.

## Agent's Discretion

- KAMA/ROC implementation details and edge cases
- Bollinger %B output format
- Engine constructor API for tool selection
- Test reference values for validation
- Performance benchmark approach

## Deferred Ideas

None — discussion stayed within phase scope
