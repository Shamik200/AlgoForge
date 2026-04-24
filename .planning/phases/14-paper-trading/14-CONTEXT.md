# Phase 14: Paper Trading Engine - Context

**Gathered:** 2026-04-23
**Status:** Completed (Auto-selected recommended options)

<domain>
## Phase Boundary

Build a high-fidelity paper trading simulator that models real-world execution friction: slippage, commissions, latency jitter, and market impact. Must support multi-asset classes (stocks, crypto, forex) via configuration only.
</domain>

<decisions>
## Implementation Decisions

### Slippage Model
- **D-01:** Percentage-Based Slippage. Configurable slippage as a percentage of fill price (default 0.05–0.1%). Applied as adverse movement: LONG fills get slipped UP, SHORT fills get slipped DOWN. This is simpler and more realistic than tick-based slippage for the asset classes we support.

### Commission Model
- **D-02:** Asset-Class Config Map. Commissions are defined per-asset-class in a config dict. US stocks use per-share fees, Indian stocks use percentage-based brokerage + STT, crypto uses maker/taker percentage fees. The engine reads the asset class from the config and applies the correct model — zero code changes needed to switch markets.

### Latency Simulation
- **D-03:** Random Jitter with Adverse Drift. Simulate 50–200ms random latency. During the latency window, the price drifts adversely by a small random amount (modeling the reality that prices move against you while your order is in flight). This is applied before the slippage model.

### Market Impact
- **D-04:** Square-Root Impact Model. For larger orders, apply temporary market impact proportional to `sqrt(order_size / avg_daily_volume)`. This penalizes oversized orders in illiquid markets while being negligible for normal-sized trades.

### Capital & Multi-Asset
- **D-05:** Config-Driven Capital. Starting capital, asset class, and all friction parameters are set in a single `PaperTradingConfig` dataclass. No code changes needed to switch between ₹1Cr Indian stocks, $100K US stocks, or crypto.
</decisions>

<canonical_refs>
## Canonical References
- `.planning/ROADMAP.md` — Phase 14 success criteria
- `.planning/phases/12-multi-target-exits/12-CONTEXT.md` — Tranche architecture
- `.planning/phases/13-oms/13-CONTEXT.md` — OMS state machine
</canonical_refs>
