"""ML Pipeline orchestrator."""

import logging
import joblib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from algoforge.ml.ensemble import StackingEnsemble
from algoforge.ml.features import FeatureBuilder
from algoforge.ml.labels import generate_labels
from algoforge.ml.validation import purged_walk_forward_split

logger = logging.getLogger(__name__)


@dataclass
class MLPipelineResult:
    """Result of ML pipeline training and evaluation."""
    avg_accuracy: float
    fold_accuracies: list[float]
    feature_importance: dict[str, float]
    n_folds: int


class MLPipeline:
    """Orchestrates the full ML enhancement pipeline.

    Handles: feature building → label generation → purged CV → ensemble training.
    """

    def __init__(
        self,
        forward_bars: int = 5,
        atr_threshold_mult: float = 0.5,
        train_size: int = 500,
        test_size: int = 100,
    ) -> None:
        """Initialize the ML pipeline.

        Args:
            forward_bars: Number of bars forward for label generation.
            atr_threshold_mult: ATR multiplier for label thresholds.
            train_size: Initial training set size for walk-forward.
            test_size: Test set size for each fold.
        """
        self.forward_bars = forward_bars
        self.atr_threshold_mult = atr_threshold_mult
        self.train_size = train_size
        self.test_size = test_size
        self.ensemble = StackingEnsemble()

    def save(self, file_path: str | Path) -> None:
        """Save the trained ensemble to disk."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.ensemble, path)
        logger.info(f"ML Pipeline model saved to {path}")

    def load(self, file_path: str | Path) -> bool:
        """Load a trained ensemble from disk."""
        path = Path(file_path)
        if path.exists():
            try:
                self.ensemble = joblib.load(path)
                logger.info(f"ML Pipeline model loaded from {path}")
                return True
            except Exception as e:
                logger.error(f"Failed to load ML model from {path}: {e}")
        return False

    def train(
        self,
        features: np.ndarray,
        closes: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
    ) -> MLPipelineResult:
        """Train the ML ensemble with purged walk-forward cross-validation.

        Args:
            features: Feature matrix (n_samples, n_features).
            closes: Close price array.
            highs: High price array.
            lows: Low price array.

        Returns:
            MLPipelineResult with cross-validated performance metrics.
        """
        # Generate labels
        class_labels = generate_labels(
            closes, highs, lows,
            forward_bars=self.forward_bars,
            atr_threshold_mult=self.atr_threshold_mult,
        )

        # Forward returns for regressor
        forward_returns = np.zeros_like(closes)
        for i in range(len(closes) - self.forward_bars):
            forward_returns[i] = (closes[i + self.forward_bars] - closes[i]) / closes[i]

        # Filter out NaN labels
        valid_mask = ~np.isnan(class_labels)
        X_valid = features[valid_mask]
        y_class = class_labels[valid_mask]
        y_return = forward_returns[valid_mask]

        if len(X_valid) < self.train_size + self.test_size + self.forward_bars:
            logger.warning("Insufficient data for ML training. Need %d, have %d",
                           self.train_size + self.test_size + self.forward_bars, len(X_valid))
            return MLPipelineResult(0.0, [], {}, 0)

        # Purged Walk-Forward Cross-Validation
        fold_accuracies = []
        folds = list(purged_walk_forward_split(
            len(X_valid), self.train_size, self.test_size, purge_gap=self.forward_bars
        ))

        for fold_idx, (train_bounds, test_bounds) in enumerate(folds):
            train_start, train_end = train_bounds
            test_start, test_end = test_bounds

            X_train = X_valid[train_start:train_end]
            y_train_cls = y_class[train_start:train_end]
            y_train_ret = y_return[train_start:train_end]

            X_test = X_valid[test_start:test_end]
            y_test_cls = y_class[test_start:test_end]

            # Ensure we have all 3 classes in training data
            unique_classes = np.unique(y_train_cls)
            if len(unique_classes) < 2:
                logger.warning("Fold %d skipped: only %d classes in training data",
                               fold_idx, len(unique_classes))
                continue

            # Train ensemble on this fold
            self.ensemble.fit(X_train, y_train_cls, y_train_ret)

            # Evaluate
            predictions = self.ensemble.predict(X_test)
            pred_classes = np.sign(predictions)  # Convert to {-1, 0, +1}
            # Treat near-zero predictions as FLAT
            pred_classes[np.abs(predictions) < 0.3] = 0

            accuracy = np.mean(pred_classes == y_test_cls)
            fold_accuracies.append(float(accuracy))

            logger.info("Fold %d: accuracy=%.3f (train=%d, test=%d)",
                        fold_idx, accuracy, len(X_train), len(X_test))

        # Final training on ALL valid data for production model
        self.ensemble.fit(X_valid, y_class, y_return)

        # Feature importance
        importance = self.ensemble.classifier.feature_importance
        feature_imp = {}
        if importance is not None and len(FeatureBuilder.FEATURE_NAMES) == len(importance):
            for name, imp in zip(FeatureBuilder.FEATURE_NAMES, importance):
                feature_imp[name] = float(imp)

        avg_acc = float(np.mean(fold_accuracies)) if fold_accuracies else 0.0

        return MLPipelineResult(
            avg_accuracy=avg_acc,
            fold_accuracies=fold_accuracies,
            feature_importance=feature_imp,
            n_folds=len(fold_accuracies),
        )

    def predict(self, features: np.ndarray) -> float:
        """Generate a prediction from the trained ensemble.

        Args:
            features: A single feature vector or batch.

        Returns:
            Signal score in [-1.0, +1.0].
        """
        if features.ndim == 1:
            features = features.reshape(1, -1)

        signals = self.ensemble.predict(features)
        return float(signals[0])
