# Phase 20: ML Pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.

**Date:** 2026-04-26
**Phase:** 20-ml-pipeline
**Areas discussed:** Feature Engineering, Model Selection, Ensemble, Validation, Interface

---

## Feature Engineering Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Multi-Source Feature Builder | 50+ features from signals, regime, microstructure, cross-asset, time | **YES** |
| Minimal Feature Set | Just signal scores as features | |

## Model Selection

| Option | Description | Selected |
|--------|-------------|----------|
| LightGBM (Primary) | Faster than XGBoost, native categoricals, better regularization | **YES** |
| XGBoost | Classic gradient boosting, slightly slower | |
| LSTM/Transformer | Deep learning on sequences | Deferred |
| PPO/SAC RL | Reinforcement learning for sizing | Deferred |

## Validation Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Purged Walk-Forward | Train → Purge Gap → Test, prevents label leakage | **YES** |
| Standard k-Fold | Illegal for time series, leaks future | |
| Expanding Window Only | Valid but doesn't purge | |

## Ensemble Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Two-Layer Stacking | L1: LightGBM clf + reg, L2: LogReg meta-model | **YES** |
| Simple Average | Average base model predictions | |
| Voting | Majority vote classification | |

## Feature Importance

| Option | Description | Selected |
|--------|-------------|----------|
| LightGBM Gain Importance | Fast, built-in, sufficient for feature selection | **YES** |
| SHAP Analysis | Slower but more interpretable | Deferred |
