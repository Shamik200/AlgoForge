"""Two-layer stacking ensemble for combining ML model outputs.

Layer 1: GBMClassifier (direction probabilities) + GBMRegressor (return magnitude)
Layer 2: Logistic regression meta-model that combines L1 outputs into a final signal.

This is the standard stacking approach used by Kaggle grandmasters and quant firms.
"""

import numpy as np
from sklearn.linear_model import LogisticRegression

from algoforge.ml.models import GBMClassifier, GBMRegressor


class StackingEnsemble:
    """Two-layer stacking ensemble for HFT-grade signal generation."""

    def __init__(self) -> None:
        self.classifier = GBMClassifier()
        self.regressor = GBMRegressor()
        self.meta_model = LogisticRegression(max_iter=1000, C=1.0)
        self._is_trained = False

    def fit(self, X: np.ndarray, y_class: np.ndarray, y_return: np.ndarray) -> None:
        """Train the full ensemble.

        Args:
            X: Feature matrix (n_samples, n_features).
            y_class: Classification labels {-1, 0, +1}.
            y_return: Continuous forward return labels.
        """
        # Train Layer 1 models
        self.classifier.fit(X, y_class)
        self.regressor.fit(X, y_return)

        # Generate Layer 1 predictions for meta-model training
        meta_features = self._build_meta_features(X)

        # Train Layer 2 meta-model
        self.meta_model.fit(meta_features, y_class)
        self._is_trained = True

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Generate final signal scores.

        Args:
            X: Feature matrix.

        Returns:
            Array of signal scores in [-1.0, +1.0].
        """
        if not self._is_trained:
            raise RuntimeError("Ensemble not trained. Call fit() first.")

        meta_features = self._build_meta_features(X)

        # Meta-model predicts class probabilities
        meta_proba = self.meta_model.predict_proba(meta_features)
        classes = list(self.meta_model.classes_)

        long_idx = classes.index(1) if 1 in classes else None
        short_idx = classes.index(-1) if -1 in classes else None

        p_long = meta_proba[:, long_idx] if long_idx is not None else np.zeros(len(X))
        p_short = meta_proba[:, short_idx] if short_idx is not None else np.zeros(len(X))

        # Final signal: P(LONG) - P(SHORT), bounded to [-1, 1]
        signals = p_long - p_short
        return np.clip(signals, -1.0, 1.0)

    def _build_meta_features(self, X: np.ndarray) -> np.ndarray:
        """Build the meta-feature matrix from Layer 1 predictions.

        Combines:
        - Class probabilities from the classifier (3 features)
        - Predicted return magnitude from the regressor (1 feature)

        Args:
            X: Original feature matrix.

        Returns:
            Meta-feature matrix (n_samples, 4).
        """
        class_proba = self.classifier.predict_proba(X)  # (n, 3)
        return_pred = self.regressor.predict(X).reshape(-1, 1)  # (n, 1)
        return np.hstack([class_proba, return_pred])
