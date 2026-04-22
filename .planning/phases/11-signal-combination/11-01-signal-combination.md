---
gap_closure: false
---

# Plan 11-01: Signal Combination Engine

## Objective
Implement the Signal Combination & Conviction Framework to normalize, decorrelate, and adaptively weight multiple signal families into a single master conviction score bounded by `[-1.0, 1.0]`.

## Tasks

- [ ] **1. Rolling Normalizer**
  - Create `src/algoforge/combination/normalization.py`.
  - Implement `RollingNormalizer` class with a 100-period deque for each family.
  - Implement `z_score` calculation and clipping to `[-1.0, 1.0]`.

- [ ] **2. Adaptive Softmax Weighter**
  - Create `src/algoforge/combination/weighting.py`.
  - Implement `calculate_softmax_weights(sharpe_ratios: dict[str, float]) -> dict[str, float]`.
  - Ensure weights sum to 1.0 and gracefully handle negative/zero Sharpe ratios.

- [ ] **3. Decorrelation Matrix & Routing**
  - Create `src/algoforge/combination/correlation.py`.
  - Implement `SignalCorrelationMatrix` to track historical signals.
  - Implement `cull_redundant_signals` which drops families if pairwise correlation > 0.7 (keeping the one with the higher Sharpe).

- [ ] **4. Combination Engine Orchestrator**
  - Create `src/algoforge/combination/engine.py`.
  - Implement `CombinationEngine.combine(...)`.
  - Flow: Normalization -> Correlation Cull -> Softmax Weighting -> Composite Score.
  - Output standard `SignalResult` with `family_name="composite"`.

- [ ] **5. Integration & API**
  - Create `src/algoforge/combination/__init__.py`.
  - Export public classes and functions.

- [ ] **6. Testing & Verification**
  - Create `tests/unit/test_combination_engine.py`.
  - Test z-score math over a series of inputs.
  - Test softmax weights math (e.g. `[1.0, -1.0, 0.0]`).
  - Test tie-breaker dropping logic and weight recalculation.
