"""Unit tests for the ML Pipeline."""

import numpy as np
import pytest

from algoforge.ml.features import FeatureBuilder
from algoforge.ml.labels import generate_labels, calculate_atr
from algoforge.ml.validation import purged_walk_forward_split
from algoforge.ml.models import GBMClassifier, GBMRegressor
from algoforge.ml.ensemble import StackingEnsemble
from algoforge.ml.pipeline import MLPipeline


def test_feature_builder_output_shape():
    """Test FeatureBuilder produces the correct number of features."""
    features = FeatureBuilder.build(
        signal_scores={"momentum": 0.5, "mean_reversion": -0.3},
        returns_1=0.01, returns_5=0.03,
        hour=14, day_of_week=3, month=9,
    )
    # Should produce exactly 60 features (44 + 16 Alpha158 features)
    assert features.shape == (60,)
    assert features.dtype == np.float64


def test_feature_builder_cyclical_time():
    """Test cyclical time encoding produces bounded values."""
    features = FeatureBuilder.build(
        signal_scores={},
        hour=0, day_of_week=0, month=1,
    )
    # All time features should be between -1 and 1
    time_features = features[-6:]
    assert all(-1.0 <= f <= 1.0 for f in time_features)


def test_label_generation():
    """Test label generation with forward returns."""
    np.random.seed(42)
    n = 100
    closes = np.cumsum(np.random.randn(n) * 0.5) + 100
    highs = closes + np.abs(np.random.randn(n)) * 0.5
    lows = closes - np.abs(np.random.randn(n)) * 0.5

    labels = generate_labels(closes, highs, lows, forward_bars=5, atr_threshold_mult=0.5)

    # Last 5 bars should be NaN (no forward return available)
    assert np.isnan(labels[-1])
    assert np.isnan(labels[-5])

    # Valid labels should be in {-1, 0, 1}
    valid = labels[~np.isnan(labels)]
    assert all(v in [-1.0, 0.0, 1.0] for v in valid)


def test_atr_calculation():
    """Test ATR calculation."""
    highs = np.array([10.0, 11.0, 12.0, 11.5, 13.0] * 5)
    lows = np.array([9.0, 9.5, 10.0, 9.0, 11.0] * 5)
    closes = np.array([9.5, 10.5, 11.0, 10.0, 12.0] * 5)

    atr = calculate_atr(highs, lows, closes, period=5)

    # First 4 should be NaN
    assert np.isnan(atr[0])
    assert np.isnan(atr[3])
    # From index 4 onward should have values
    assert not np.isnan(atr[4])
    assert atr[4] > 0


def test_purged_walk_forward():
    """Test purged walk-forward split boundaries."""
    folds = list(purged_walk_forward_split(
        n_samples=500, train_size=200, test_size=50, purge_gap=5
    ))

    assert len(folds) >= 3

    for (train_start, train_end), (test_start, test_end) in folds:
        # Train always starts at 0
        assert train_start == 0
        # Purge gap exists between train and test
        assert test_start - train_end >= 5
        # Test end > test start
        assert test_end > test_start


def test_purged_walk_forward_no_overlap():
    """Test that train and test sets never overlap."""
    folds = list(purged_walk_forward_split(
        n_samples=300, train_size=100, test_size=30, purge_gap=5
    ))

    for (train_start, train_end), (test_start, test_end) in folds:
        # No overlap between train and test
        assert test_start > train_end


def test_gbm_classifier():
    """Test GBM classifier fits and predicts."""
    np.random.seed(42)
    X = np.random.randn(300, 10)
    y = np.random.choice([-1, 0, 1], size=300)

    clf = GBMClassifier({"n_estimators": 50, "min_child_samples": 5})
    clf.fit(X, y)

    proba = clf.predict_proba(X[:5])
    assert proba.shape[1] == 3  # 3 classes

    signals = clf.predict_signal(X[:5])
    assert all(-1.0 <= s <= 1.0 for s in signals)

    imp = clf.feature_importance
    assert imp is not None
    assert len(imp) == 10


def test_gbm_regressor():
    """Test GBM regressor fits and predicts."""
    np.random.seed(42)
    X = np.random.randn(200, 10)
    y = np.random.randn(200) * 0.01

    reg = GBMRegressor({"n_estimators": 50, "min_child_samples": 5})
    reg.fit(X, y)

    preds = reg.predict(X[:5])
    assert len(preds) == 5


def test_stacking_ensemble():
    """Test full stacking ensemble end-to-end."""
    np.random.seed(42)
    X = np.random.randn(300, 10)
    y_class = np.random.choice([-1, 0, 1], size=300)
    y_return = np.random.randn(300) * 0.01

    ensemble = StackingEnsemble()
    ensemble.fit(X, y_class, y_return)

    signals = ensemble.predict(X[:5])
    assert len(signals) == 5
    assert all(-1.0 <= s <= 1.0 for s in signals)


def test_ml_pipeline_end_to_end():
    """Test the full ML pipeline with synthetic data."""
    np.random.seed(42)
    n = 800

    # Generate synthetic price data
    closes = np.cumsum(np.random.randn(n) * 0.5) + 100
    highs = closes + np.abs(np.random.randn(n)) * 0.5
    lows = closes - np.abs(np.random.randn(n)) * 0.5

    # Generate synthetic features
    features = np.random.randn(n, 60)

    pipeline = MLPipeline(
        forward_bars=5, atr_threshold_mult=0.5,
        train_size=300, test_size=50
    )
    result = pipeline.train(features, closes, highs, lows)

    assert result.n_folds >= 1
    assert 0.0 <= result.avg_accuracy <= 1.0

    # Test prediction
    single_pred = pipeline.predict(features[0])
    assert -1.0 <= single_pred <= 1.0

    # Test confidence-bearing prediction
    scored_pred = pipeline.predict_with_confidence(features[0])
    assert -1.0 <= scored_pred.ensemble_score <= 1.0
    assert 0.0 <= scored_pred.confidence <= 1.0
    assert scored_pred.direction in {"long", "short", "neutral"}
