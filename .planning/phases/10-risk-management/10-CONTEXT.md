# Phase 10: Risk Management Engine - Context

**Gathered:** 2026-04-20
**Status:** Completed (Auto-selected recommended options)

<domain>
## Phase Boundary

Implement the complete Risk Management Engine. This engine is responsible for enforcing strict per-trade limits (risk %, position size, R:R), global account constraints (daily/weekly loss limits, drawdowns), portfolio concentration limits (sector, direction, correlation), and calculating optimal position sizing using a fractional Kelly approach.
</domain>

<decisions>
## Implementation Decisions

### Kelly Criterion Data Source
- **D-01:** Rolling `TradeLedger`. To calculate dynamic Kelly position sizes, we will build a `TradeLedger` component that tracks historical performance. The Risk Engine will use this ledger to derive live win rates and payoff ratios. If the ledger has fewer than 30 trades of history, the engine will safely fallback to a conservative fixed-fractional risk sizing model (e.g., 1.0% risk per trade).

### Global Account Limits & State
- **D-02:** Abstract `AccountState` Model. Since there is no live broker connection at this layer, the Risk Engine will remain functionally pure by accepting an abstract `AccountState` data class (containing current equity, daily PnL, consecutive losses, etc.) upon evaluation. Maintaining and passing this state will be the responsibility of the downstream Portfolio Manager (Phase 13).

### Correlation Limit Implementation
- **D-03:** Daily `CorrelationMatrix` Cache. To enforce the 0.7 max correlation limit without tanking system performance via on-the-fly matrix math, we will implement a dedicated `CorrelationMatrix` cache. This matrix will be updated daily (e.g. end-of-day processing) allowing the Risk Engine to perform instantaneous O(1) lookups during intraday trade evaluations.
</decisions>

<canonical_refs>
## Canonical References
- `.planning/ROADMAP.md` — Phase 10 success criteria
</canonical_refs>
