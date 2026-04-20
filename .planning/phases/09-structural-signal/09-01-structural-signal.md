---
gap_closure: false
---

# Plan 09-01: Structural Confluence Signal Family

## Objective
Implement the Structural Confluence signal family, generating signals when price tests heavy confluence zones with micro-structure candlestick rejections, enhanced by Multi-Timeframe (MTF) alignment and HMM regime awareness.

## Tasks

- [ ] **1. Implement Microstructure Detectors**
  - Create `src/algoforge/signals/structural/microstructure.py`.
  - Implement Wick calculations (Lower Wick for Support, Upper Wick for Resistance).
  - Implement `detect_rejection` requiring Wick Ratio > 0.5 AND Volume > 1.5 * SMA(20).

- [ ] **2. Implement Proximity & MTF Aligners**
  - Create `src/algoforge/signals/structural/proximity.py`.
  - Implement `find_tested_levels` which checks if `High` or `Low` is within `0.5 * ATR(14)` of any Phase 4 `StructuralSnapshot` level.
  - Implement `check_htf_overlap` which returns a 1.5x multiplier if an HTF snapshot level exists near the tested LTF level.

- [ ] **3. Build the Structural Signal Class**
  - Create `src/algoforge/signals/structural/signal.py`.
  - Combine tested levels + microstructure rejection.
  - Direction determined by Support (Long) vs Resistance (Short).
  - Apply Regime Multipliers: `0.3x` if strong trend, `1.3x` if mean-reverting.
  - Output standardized `SignalResult` `[-1.0, 1.0]`.

- [ ] **4. Integration & API**
  - Create `src/algoforge/signals/structural/__init__.py`.
  - Export public classes and functions.

- [ ] **5. Testing & Verification**
  - Create `tests/unit/test_structural_signal.py`.
  - Test candlestick wick math and volume climax.
  - Test proximity detection using mocked `StructuralSnapshot` objects.
  - Test Multi-Timeframe multiplier and Regime multipliers.
