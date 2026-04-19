---
gap_closure: false
---

# Phase 4: Structural Confluence Detection - Execution Plan

## Goal
Implement the Structural Confluence engine to objectively measure S/R.

## Steps

1. **Create Data Models**
   - Create `src/algoforge/structural/models.py` with `PriceLevel` and `ConfluenceZone`.
2. **Implement Swing Clustering**
   - Create `src/algoforge/structural/swings.py` with `detect_swings` and `cluster_swings`.
3. **Build Confluence Engine**
   - Create `src/algoforge/structural/engine.py` with `StructuralConfluenceEngine`.
4. **Testing**
   - Write unit and integration tests in `tests/unit/test_structural_confluence.py`.
