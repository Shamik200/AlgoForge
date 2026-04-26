"""LightGBM model wrappers with HFT-optimized hyperparameters.

LightGBM is the workhorse of modern quantitative finance.
These wrappers use conservative hyperparameters designed to prevent overfitting
on noisy financial data.
"""

import numpy as np


# HFT-optimized hyperparameters (conservative to prevent overfitting)
DEFAULT_GBM_PARAMS = {
    "n_estimators": 500,
    "num_leaves": 31,
    "min_child_samples": 100,    # Require statistical significance
    "feature_fraction": 0.7,     # Random feature selection per tree
    "bagging_fraction": 0.7,     # Random sample selection per tree
    "bagging_freq": 1,
    "lambda_l1": 0.1,            # L1 regularization
    "lambda_l2": 0.1,            # L2 regularization
    "learning_rate": 0.05,
    "verbose": -1,
}


class GBMClassifier:
    """LightGBM-based 3-class classifier for trade direction.

    Predicts P(LONG), P(FLAT), P(SHORT) and converts to a signal score.
    Falls back to sklearn's GradientBoostingClassifier if lightgbm isn't available.
    """

    def __init__(self, params: dict | None = None) -> None:
        self.params = {**DEFAULT_GBM_PARAMS, **(params or {})}
        self._model = None
        self._use_lightgbm = False

        try:
            import lightgbm as lgb
            self._lgb = lgb
            self._use_lightgbm = True
        except ImportError:
            from sklearn.ensemble import GradientBoostingClassifier
            self._sklearn_cls = GradientBoostingClassifier
            self._use_lightgbm = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """Train the classifier.

        Args:
            X: Feature matrix (n_samples, n_features).
            y: Labels array {-1, 0, +1}.
        """
        if self._use_lightgbm:
            self._model = self._lgb.LGBMClassifier(**self.params)
            self._model.fit(X, y)
        else:
            self._model = self._sklearn_cls(
                n_estimators=min(self.params["n_estimators"], 200),
                max_depth=5,
                learning_rate=self.params["learning_rate"],
                min_samples_leaf=self.params["min_child_samples"],
            )
            self._model.fit(X, y)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict class probabilities.

        Args:
            X: Feature matrix.

        Returns:
            Array of shape (n_samples, n_classes) with probabilities.
        """
        if self._model is None:
            raise RuntimeError("Model not trained. Call fit() first.")
        return self._model.predict_proba(X)

    def predict_signal(self, X: np.ndarray) -> np.ndarray:
        """Convert probabilities to a signal score in [-1.0, +1.0].

        Signal = P(LONG) - P(SHORT). P(FLAT) acts as a dampener.

        Args:
            X: Feature matrix.

        Returns:
            Array of signal scores.
        """
        proba = self.predict_proba(X)
        classes = list(self._model.classes_)

        long_idx = classes.index(1) if 1 in classes else None
        short_idx = classes.index(-1) if -1 in classes else None

        p_long = proba[:, long_idx] if long_idx is not None else np.zeros(len(X))
        p_short = proba[:, short_idx] if short_idx is not None else np.zeros(len(X))

        return p_long - p_short

    @property
    def feature_importance(self) -> np.ndarray | None:
        """Get feature importance (gain-based)."""
        if self._model is None:
            return None
        if self._use_lightgbm:
            return self._model.feature_importances_
        return self._model.feature_importances_


class GBMRegressor:
    """LightGBM-based regressor for return magnitude prediction."""

    def __init__(self, params: dict | None = None) -> None:
        self.params = {**DEFAULT_GBM_PARAMS, **(params or {})}
        self._model = None
        self._use_lightgbm = False

        try:
            import lightgbm as lgb
            self._lgb = lgb
            self._use_lightgbm = True
        except ImportError:
            from sklearn.ensemble import GradientBoostingRegressor
            self._sklearn_reg = GradientBoostingRegressor
            self._use_lightgbm = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """Train the regressor.

        Args:
            X: Feature matrix.
            y: Continuous target (forward returns).
        """
        if self._use_lightgbm:
            self._model = self._lgb.LGBMRegressor(**self.params)
            self._model.fit(X, y)
        else:
            self._model = self._sklearn_reg(
                n_estimators=min(self.params["n_estimators"], 200),
                max_depth=5,
                learning_rate=self.params["learning_rate"],
                min_samples_leaf=self.params["min_child_samples"],
            )
            self._model.fit(X, y)

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict return magnitudes.

        Args:
            X: Feature matrix.

        Returns:
            Array of predicted returns.
        """
        if self._model is None:
            raise RuntimeError("Model not trained. Call fit() first.")
        return self._model.predict(X)


# ---------------------------------------------------------------------------
# Legacy ML classes (used by the existing orchestrator pipeline)
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MLPrediction:
    """Prediction output from a single ML model."""
    model_name: str = ""
    confidence_adjustment: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class DummyTrendModel:
    """A simple heuristic model that adjusts confidence based on ADX/RSI."""

    name: str = "dummy_trend"

    def predict(self, features: dict[str, float]) -> MLPrediction:
        """Predict confidence adjustment from indicator features.

        Args:
            features: Dict of indicator values (e.g., adx, rsi).

        Returns:
            MLPrediction with confidence adjustment in [-0.3, 0.3].
        """
        adx = features.get("adx", 25)
        rsi = features.get("rsi", 50)

        # Strong trend (high ADX) → boost confidence
        adj = 0.0
        if adx > 30:
            adj += (adx - 30) / 100  # +0.01 per ADX point above 30
        elif adx < 20:
            adj -= (20 - adx) / 100

        # Extreme RSI → reduce confidence (reversal risk)
        if rsi > 70 or rsi < 30:
            adj -= 0.05

        adj = max(-0.3, min(0.3, adj))
        return MLPrediction(model_name=self.name, confidence_adjustment=adj)


class EnsembleML:
    """Ensemble of ML models for signal enhancement.

    Combines predictions from multiple models using weighted averaging,
    then applies the aggregate adjustment to signal confidence scores.
    """

    def __init__(self, max_adjustment: float = 0.15) -> None:
        self.max_adjustment = max_adjustment
        self._models: list[tuple[Any, float]] = []  # (model, weight)

    @property
    def model_count(self) -> int:
        return len(self._models)

    def add_model(self, model: Any, weight: float = 1.0) -> None:
        """Add a model to the ensemble."""
        self._models.append((model, weight))

    def enhance_signals(self, signals: list, features: dict) -> list:
        """Apply ML enhancement to a list of signals.

        Args:
            signals: List of Signal objects.
            features: Dict of indicator features for ML models.

        Returns:
            List of signals with adjusted confidence scores.
        """
        if not self._models:
            return signals

        # Get weighted average adjustment
        total_weight = sum(w for _, w in self._models)
        if total_weight == 0:
            return signals

        weighted_adj = 0.0
        for model, weight in self._models:
            pred = model.predict(features)
            weighted_adj += pred.confidence_adjustment * weight
        weighted_adj /= total_weight

        # Cap adjustment
        weighted_adj = max(-self.max_adjustment, min(self.max_adjustment, weighted_adj))

        # Apply to all signals
        enhanced = []
        for sig in signals:
            new_conf = max(0.0, min(1.0, sig.confidence + weighted_adj))
            # Create a copy with updated confidence
            from copy import copy
            new_sig = copy(sig)
            new_sig.confidence = new_conf
            enhanced.append(new_sig)

        return enhanced
