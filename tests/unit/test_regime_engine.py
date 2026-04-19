"""Tests for the HMM Regime Detector."""

import numpy as np
import pytest
from datetime import datetime, timezone

from algoforge.core.constants import Timeframe
from algoforge.core.models import OHLCV, OHLCVSeries
from algoforge.regime.engine import RegimeEngine
from algoforge.regime.features import build_features, forward_fill_cross_asset, smooth_features
from algoforge.regime.models import RegimeProbabilities, RegimeState
from algoforge.regime.trainer import HMMTrainer


def test_forward_fill_cross_asset():
    """Test alignment of asynchronous cross-asset data."""
    # Target times: 10:00, 10:05, 10:10, 10:15, 10:20
    target_times = [1000, 1005, 1010, 1015, 1020]
    
    # Cross asset times: 09:50, 10:07, 10:18
    # Values: 1.0, 2.0, 3.0
    ca_times = [950, 1007, 1018]
    ca_values = np.array([1.0, 2.0, 3.0])
    
    aligned = forward_fill_cross_asset(target_times, ca_times, ca_values)
    
    assert aligned.shape == (5, 1)
    
    # 10:00 -> uses 9:50 value (1.0)
    assert aligned[0][0] == 1.0
    # 10:05 -> uses 9:50 value (1.0)
    assert aligned[1][0] == 1.0
    # 10:10 -> uses 10:07 value (2.0)
    assert aligned[2][0] == 2.0
    # 10:15 -> uses 10:07 value (2.0)
    assert aligned[3][0] == 2.0
    # 10:20 -> uses 10:18 value (3.0)
    assert aligned[4][0] == 3.0


def test_build_features():
    """Test feature construction logic."""
    series = OHLCVSeries(symbol="AAPL", timeframe=Timeframe.D1)
    
    # Create 30 days of data
    for i in range(30):
        close_val = 100.0 * (1.01 ** i)
        series.append(
            OHLCV(
                symbol="AAPL",
                timeframe=Timeframe.D1,
                timestamp=datetime(2024, 1, i + 1, tzinfo=timezone.utc) if i < 30 else datetime(2024, 2, 1, tzinfo=timezone.utc),
                open=100.0,
                high=max(105.0, close_val * 1.02),
                low=95.0,
                close=close_val,
                volume=1000.0,
            )
        )
        
    features = build_features(series)
    
    assert features.shape == (30, 3)
    
    # Returns should be approx log(1.01) ~ 0.00995
    assert np.isclose(features[1, 0], np.log(1.01))
    
    # Volatility should be close to 0 since returns are constant
    assert features[-1, 1] < 0.0001
    
    # Vol ratio should be 1.0 since volume is constant
    assert np.isclose(features[-1, 2], 1.0)


def test_smooth_features():
    """Test EMA smoothing of features."""
    features = np.ones((10, 2))
    features[5:, 0] = 2.0
    
    smoothed = smooth_features(features, period=3)
    
    assert smoothed.shape == (10, 2)
    # First few should be 1.0
    assert smoothed[0, 0] == 1.0
    # After step change, should smooth towards 2.0
    assert 1.0 < smoothed[6, 0] < 2.0
    assert smoothed[-1, 0] > smoothed[6, 0]


class MockHMMModel:
    """Mock hmmlearn model for testing."""
    def __init__(self):
        self.means_ = np.array([
            [0.01, 0.05, 1.0],  # State 0: High return, low vol (Trend Up)
            [-0.01, 0.05, 1.0], # State 1: Low return, low vol (Trend Down)
            [0.0, 0.02, 0.8],   # State 2: Zero return, very low vol (Mean Revert)
            [-0.05, 0.20, 2.0], # State 3: Very low return, high vol (Crisis)
        ])
        
    def predict_proba(self, X):
        # Return a deterministic probability vector for testing
        probs = np.zeros((X.shape[0], 4))
        probs[:, 0] = 0.7  # 70% Trend Up
        probs[:, 1] = 0.1
        probs[:, 2] = 0.1
        probs[:, 3] = 0.1
        return probs

class MockScaler:
    """Mock standard scaler."""
    def transform(self, X):
        return X

def test_regime_engine(tmp_path):
    """Test the full regime inference engine."""
    
    # We need to mock the HMMTrainer.load to avoid needing hmmlearn installed 
    # or having to actually train a model for the test
    import algoforge.regime.engine
    
    class MockTrainer:
        @classmethod
        def load(cls, *args, **kwargs):
            instance = cls()
            instance.model = MockHMMModel()
            instance.scaler = MockScaler()
            return instance
            
    # Patch the trainer class inside the engine module
    original_trainer = algoforge.regime.engine.HMMTrainer
    algoforge.regime.engine.HMMTrainer = MockTrainer
    
    try:
        engine = RegimeEngine(model_dir=tmp_path, smoothing_period=2)
        
        # Verify the state mapping logic
        # State 0 has highest return -> trend_up
        # State 3 has highest vol -> crisis
        # State 1 has lowest return -> trend_down
        # State 2 is mean_revert
        assert engine._state_mapping[0] == "trend_up"
        assert engine._state_mapping[3] == "crisis"
        assert engine._state_mapping[1] == "trend_down"
        assert engine._state_mapping[2] == "mean_revert"
        
        series = OHLCVSeries(symbol="AAPL", timeframe=Timeframe.D1)
        for i in range(25):
            series.append(
                OHLCV(
                    symbol="AAPL",
                    timeframe=Timeframe.D1,
                    timestamp=datetime(2024, 1, i + 1, tzinfo=timezone.utc) if i < 30 else datetime(2024, 2, 1, tzinfo=timezone.utc),
                    open=100.0, high=105.0, low=95.0, close=100.0, volume=1000.0,
                )
            )
            
        probs = engine.compute(series)
        
        assert isinstance(probs, RegimeProbabilities)
        assert probs.trend_up == 0.7
        assert probs.dominant_regime == RegimeState.TREND_UP
        assert probs.is_trending is True
        
        # Test uncertainty flag via VIX conflict
        # Engine says trend_up=0.7. If VIX is 35 (extreme fear), should flag uncertainty.
        probs_with_vix = engine.compute(series, current_vix=35.0)
        assert probs_with_vix.uncertainty_flag is True
        
    finally:
        # Restore the original trainer
        algoforge.regime.engine.HMMTrainer = original_trainer
