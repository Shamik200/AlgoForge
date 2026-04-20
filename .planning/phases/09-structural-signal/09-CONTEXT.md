# Phase 9: Signal Family 4 — Structural Confluence - Context

**Gathered:** 2026-04-20
**Status:** Completed (Auto-selected recommended options)

<domain>
## Phase Boundary

Implement the Structural Confluence signal family. This module generates signals when price interacts with high-conviction structural zones (discovered in Phase 4) and displays candlestick/volume micro-structure rejections. It applies Multi-Timeframe (MTF) analysis to boost conviction when levels align.
</domain>

<decisions>
## Implementation Decisions

### "Approaches" Proximity Threshold
- **D-01:** ATR-Based Proximity. A structural level is considered "tested" if the price enters within a band of `+/- 0.5 * ATR(14)` around the exact confluence price level. This allows the system to adapt to current market volatility rather than using a rigid, breakable percentage band.

### Reversal Micro-Structure (Candlesticks)
- **D-02:** Wick and Volume Definitions. 
  - A valid rejection requires the wick testing the level to be at least 50% of the entire candle's range `(High - Low)`. For a bullish rejection at support, the lower wick must be large. For a bearish rejection at resistance, the upper wick must be large.
  - A "volume climax" confirmation requires the volume on the rejection bar to be `> 1.5 * SMA(Volume, 20)`.

### Multi-Timeframe Integration Mechanics
- **D-03:** HTF Snapshot Overlap. The `StructuralSignal.evaluate()` method will accept an optional list of `StructuralSnapshot` objects representing higher timeframes (e.g., passing D1 snapshots into an H1 evaluation). If the HTF snapshot contains a level within `0.5 * ATR(14)` of the tested LTF level, the base conviction score receives a 1.5x multiplier.
</decisions>

<canonical_refs>
## Canonical References
- `.planning/ROADMAP.md` — Phase 9 success criteria
</canonical_refs>
