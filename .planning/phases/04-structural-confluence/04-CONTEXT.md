# Phase 4: Structural Confluence Detection - Context

**Gathered:** 2026-04-19
**Status:** Executed (Fast-tracked)

<domain>
## Phase Boundary

Build objective, data-driven Support/Resistance (S/R) detection using volume profile, swing point clustering, and dynamic MAs. This replaces subjective trendline analysis with quantifiable confluence scoring.

</domain>

<decisions>
## Implementation Decisions

### Core Data Models
- **D-01:** Implement `PriceLevel` and `ConfluenceZone` as Pydantic models. `ConfluenceZone` aggregates multiple `PriceLevel`s and calculates an objective `score` between 0 and 5.

### Swing Point Clustering
- **D-02:** Use an ATR-based 1D greedy clustering algorithm to merge proximate swing points. Swings within `0.5 * ATR` are grouped into a single zone to reduce noise.

### Engine Architecture
- **D-03:** `StructuralConfluenceEngine` consumes the `IndicatorSnapshot` from Phase 3. It extracts Volume Profile (POC, VAH, VAL) and KAMA directly from the cache, preventing redundant calculations.

</decisions>

<canonical_refs>
## Canonical References
- `.planning/ROADMAP.md` — Phase 4 success criteria
- `src/algoforge/structural/engine.py` — The core engine implementation
</canonical_refs>
