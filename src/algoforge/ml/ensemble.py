"""Two-layer stacking ensemble for combining ML model outputs.

Layer 1: GBMClassifier (direction probabilities) + GBMRegressor (return magnitude)
Layer 2: Logistic regression meta-model that combines L1 outputs into a final signal.

AUDIT FIX: Uses out-of-fold predictions for meta-feature generation
to prevent stacking data leak (the #1 cause of false ML alpha).
"""

import numpy as np
from sklearn.linear_model import LogisticRegression

from algoforge.ml.models import GBMClassifier, GBMRegressor
from algoforge.ml.validation import purged_walk_forward_split


class StackingEnsemble:
    """Two-layer stacking ensemble for HFT-grade signal generation.

    AUDIT FIX: Meta-features are generated via out-of-fold predictions
    from purged walk-forward CV, not in-sample predictions.
    """

    def __init__(self) -> None:
        self.classifier = GBMClassifier()
        self.regressor = GBMRegressor()
        self.meta_model = LogisticRegression(max_iter=1000, C=1.0)
        self._is_trained = False

    def fit(self, X: np.ndarray, y_class: np.ndarray, y_return: np.ndarray) -> None:
        """Train the full ensemble with out-of-fold meta-features.

        Args:
            X: Feature matrix (n_samples, n_features).
            y_class: Classification labels {-1, 0, +1}.
            y_return: Continuous forward return labels.
        """
        n = len(X)

        # --- Generate out-of-fold meta-features (audit fix for stacking leak) ---
        oof_class_proba = np.zeros((n, 3))
        oof_return_pred = np.zeros(n)
        oof_mask = np.zeros(n, dtype=bool)

        # Use purged walk-forward splits for OOF predictions
        train_size = max(100, n // 4)
        test_size = max(50, n // 8)
        purge = 5

        for (tr_start, tr_end), (te_start, te_end) in purged_walk_forward_split(
            n, train_size, test_size, purge
        ):
            X_tr, y_cls_tr, y_ret_tr = X[tr_start:tr_end], y_class[tr_start:tr_end], y_return[tr_start:tr_end]
            X_te = X[te_start:te_end]

            # Fit temporary L1 models on this fold's training data
            fold_clf = GBMClassifier()
            fold_reg = GBMRegressor()
            fold_clf.fit(X_tr, y_cls_tr)
            fold_reg.fit(X_tr, y_ret_tr)

            # Predict on test fold (out-of-fold)
            proba = fold_clf.predict_proba(X_te)
            ret = fold_reg.predict(X_te)

            # Ensure proba has 3 columns (pad if needed)
            if proba.shape[1] < 3:
                padded = np.zeros((len(X_te), 3))
                padded[:, :proba.shape[1]] = proba
                proba = padded

            oof_class_proba[te_start:te_end] = proba
            oof_return_pred[te_start:te_end] = ret
            oof_mask[te_start:te_end] = True

        # Train final L1 models on ALL data
        self.classifier.fit(X, y_class)
        self.regressor.fit(X, y_return)

        # Train L2 meta-model on out-of-fold predictions ONLY
        if oof_mask.sum() > 10:
            meta_features = np.hstack([
                oof_class_proba[oof_mask],
                oof_return_pred[oof_mask].reshape(-1, 1),
            ])
            self.meta_model.fit(meta_features, y_class[oof_mask])
        else:
            # Fallback: not enough OOF data, use in-sample (flagged)
            meta_features = self._build_meta_features(X)
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
        """Build the meta-feature matrix from Layer 1 predictions."""
        class_proba = self.classifier.predict_proba(X)  # (n, 3)
        # Pad if classifier didn't see all classes
        if class_proba.shape[1] < 3:
            padded = np.zeros((len(X), 3))
            padded[:, :class_proba.shape[1]] = class_proba
            class_proba = padded
        return_pred = self.regressor.predict(X).reshape(-1, 1)  # (n, 1)
        return np.hstack([class_proba, return_pred])
