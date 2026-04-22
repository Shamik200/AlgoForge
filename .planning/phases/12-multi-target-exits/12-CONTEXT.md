# Phase 12: Multi-Target SL/TP & Partial Exits - Context

**Gathered:** 2026-04-22
**Status:** Completed (Auto-selected recommended options)

<domain>
## Phase Boundary

Implement the dynamic exit framework, replacing rigid single-target exits. This phase introduces ATR-anchored initial stops, staggered take-profits (TP1 at 50%, TP2 at 30%, TP3 running 20%), and time-based breakeven tightening to improve risk-adjusted capital velocity.
</domain>

<decisions>
## Implementation Decisions

### Position Data Architecture
- **D-01:** Tranche Architecture. A single conceptual trade will be split into three independent `ActivePosition` objects (tranches), linked by a shared `parent_trade_id`. This allows each tranche to independently track its own distinct stop-loss, take-profit, and trailing logic, making integration with the upcoming Order Management System (Phase 13) much simpler as each tranche directly maps to a broker child order.

### Time-Based Tightening Mechanism
- **D-02:** Candle Period Tracking. The engine will enforce the breakeven rule (moving the stop-loss to entry price if TP1 isn't hit) by counting the number of elapsed candle periods since entry, rather than raw clock time. This seamlessly handles timeframes, weekend gaps, and market closes during backtesting.

### Trailing Stop Ratchet Logic (TP3)
- **D-03:** Closed-Candle Ratcheting. The 2x ATR trailing stop for the final 20% runner (TP3) will only evaluate and step forward upon the close of a candle. It will not dynamically trail intra-candle ticks, preventing wicks and temporary intraday noise from prematurely tightening the stop and causing a whip-out.
</decisions>

<canonical_refs>
## Canonical References
- `.planning/ROADMAP.md` — Phase 12 success criteria
- `.planning/phases/10-risk-management/10-CONTEXT.md` — Existing risk architecture
</canonical_refs>
