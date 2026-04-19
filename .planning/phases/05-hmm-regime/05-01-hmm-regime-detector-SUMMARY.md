# Plan 05-01: HMM Probabilistic Regime Detector

## Outcome
Implemented a 4-state HMM using `hmmlearn` to continuously classify market regimes into probability vectors rather than binary labels. Built the offline trainer, feature preprocessor, and the runtime inference engine.

## Self-Check: PASSED
- [x] All tasks executed
- [x] Each task committed individually
- [x] SUMMARY.md created in plan directory
- [x] STATE.md and ROADMAP.md updated

## Artifacts

### `key-files.created`
- src/algoforge/regime/models.py
- src/algoforge/regime/features.py
- src/algoforge/regime/trainer.py
- src/algoforge/regime/engine.py
- src/algoforge/regime/__init__.py
- tests/unit/test_regime_engine.py

## Technical Notes
- `GaussianHMM` with diagonal covariance captures the regime states well across non-stationary features when standard-scaled.
- Handled cross-asset alignment correctly using a fast forward-fill to avoid lookahead bias.
- VIX heuristics explicitly override the HMM probabilities if they disagree via the `uncertainty_flag`.
