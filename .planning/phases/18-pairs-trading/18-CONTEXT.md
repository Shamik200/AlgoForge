# Phase 18: Pairs & Cointegration Trading - Context

**Gathered:** 2026-04-25
**Status:** Completed (Auto-selected recommended options)

<domain>
## Phase Boundary

Expand the signal universe with a pairs/relative value trading signal family. Uses Engle-Granger cointegration testing to identify valid pairs, trades the spread z-score for mean-reversion, and maintains market-neutral position sizing.
</domain>

<decisions>
## Implementation Decisions

### Cointegration Testing Method
- **D-01:** Engle-Granger Two-Step. Run OLS regression of Asset A on Asset B to get the hedge ratio. Then run an Augmented Dickey-Fuller (ADF) test on the residuals. If p-value < 0.05, the pair is cointegrated.

### Spread Signal Logic
- **D-02:** Z-Score Entry/Exit. Calculate the spread = Asset_A - (hedge_ratio × Asset_B). Normalize via rolling z-score. Entry at ±2σ (long spread when z < -2, short spread when z > +2). Exit when z-score returns to 0 (mean).

### Rolling Validation
- **D-03:** Periodic Re-Test. Every N bars (e.g., 252 bars for daily = 1 year), re-run the Engle-Granger test. If the pair is no longer cointegrated, the system automatically invalidates it and closes any open positions.
</decisions>

<canonical_refs>
## Canonical References
- `.planning/ROADMAP.md` — Phase 18 success criteria
</canonical_refs>
