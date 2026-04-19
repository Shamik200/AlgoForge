# Phase 7: Signal Family 2 — Mean Reversion - Context

**Gathered:** 2026-04-19
**Status:** Completed (Auto-selected recommended options)

<domain>
## Phase Boundary

Implement the Mean Reversion signal family. Generates a composite z-score using VWAP deviation (40%), Bollinger %B extreme with RSI divergence (30%), and a Pairs trading stub (30%). Integrates HMM activation guards and momentum anti-trend guards.
</domain>

<decisions>
## Implementation Decisions

### RSI Divergence Definition
- **D-01:** Strict pivot matching. Rather than a lazy proxy, we will leverage the swing point detection algorithms implemented in Phase 4. We will compare the last two recognized price swing lows against the last two RSI swing lows to rigorously identify bullish/bearish divergence.

### Pairs/Relative Value Architecture
- **D-02:** Placeholder stub. Full cointegration and spread trading require cross-asset state management. For this phase, the 30% pairs weight will be calculated via a stub function that defaults to 0. The true relative value architecture will be built in Phase 17, slotting perfectly into this stub.

### Anti-Trend Guard Coupling
- **D-03:** Explicit input dependency. The `MeanReversionSignal.evaluate()` function will accept an optional `momentum_score: float` argument. If provided and the score represents an extreme trend (top/bottom 20%), the mean reversion signal will immediately return `is_valid = False`, protecting capital from trend continuation steamrollers.
</decisions>

<canonical_refs>
## Canonical References
- `.planning/ROADMAP.md` — Phase 7 success criteria
</canonical_refs>
