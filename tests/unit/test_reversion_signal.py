"""Unit tests for the Mean Reversion signal family."""

import numpy as np
import pytest
from datetime import datetime, timezone, timedelta

from algoforge.core.constants import Timeframe
from algoforge.core.models import OHLCV, OHLCVSeries
from algoforge.regime.models import RegimeProbabilities, RegimeState
from algoforge.signals.models import SignalDirection
from algoforge.signals.reversion.divergence import (
    bollinger_percent_b,
    detect_rsi_divergence,
    evaluate_bollinger_divergence,
)
from algoforge.signals.reversion.signal import MeanReversionSignal
from algoforge.signals.reversion.vwap_zscore import calculate_rolling_vwap, vwap_zscore


def test_rolling_vwap():
    """Test rolling VWAP calculation and Z-Score."""
    series = OHLCVSeries(symbol="AAPL", timeframe=Timeframe.D1)
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    
    # Create 30 days of data
    for i in range(30):
        series.append(OHLCV(
            symbol="AAPL", timeframe=Timeframe.D1, timestamp=base_time + timedelta(days=i),
            open=100.0, high=101.0, low=99.0, close=100.0, volume=10.0
        ))
        
    vwaps = calculate_rolling_vwap(series, period=20)
    
    assert len(vwaps) == 30
    assert np.isnan(vwaps[18])
    assert not np.isnan(vwaps[19])
    
    # Since prices are constant, VWAP should be exactly the typical price (100.0)
    assert np.isclose(vwaps[25], 100.0)
    
    # Test Z-Score calculation
    closes = np.array(series.closes)
    
    # std_dev will be 0, so score should be 0.0
    score = vwap_zscore(closes, vwaps, period=20)
    assert score == 0.0
    
    # Let's spike the last close price significantly
    closes[-1] = 110.0
    # Recalculate manually to get some variance
    std_dev = np.std(closes[-20:])
    z = (closes[-1] - vwaps[-1]) / std_dev
    expected_score = np.tanh(-z / 2.0)
    
    calc_score = vwap_zscore(closes, vwaps, period=20)
    assert np.isclose(calc_score, expected_score)
    # Since price spiked UP, z-score is positive, so mean reversion score should be NEGATIVE (Short)
    assert calc_score < 0.0


def test_bollinger_percent_b():
    """Test %B calculation."""
    # At lower band -> 0.0
    assert bollinger_percent_b(100.0, 110.0, 100.0) == 0.0
    # At upper band -> 1.0
    assert bollinger_percent_b(110.0, 110.0, 100.0) == 1.0
    # Middle -> 0.5
    assert bollinger_percent_b(105.0, 110.0, 100.0) == 0.5
    # Oversold -> < 0.0
    assert bollinger_percent_b(95.0, 110.0, 100.0) < 0.0
    

def test_rsi_divergence():
    """Test RSI divergence logic with mocked swings."""
    # We will simulate a bullish divergence: 
    # Price makes a lower low, but RSI makes a higher low.
    
    closes = np.full(100, 100.0)
    rsi = np.full(100, 50.0)
    
    # First pivot (t=80)
    closes[79:82] = [100.0, 90.0, 100.0]  # Low at 90
    rsi[79:82] = [50.0, 30.0, 50.0]       # Low at 30
    
    # Second pivot (t=90)
    closes[89:92] = [100.0, 85.0, 100.0]  # Lower Low at 85
    rsi[89:92] = [50.0, 40.0, 50.0]       # Higher Low at 40
    
    # Need to make sure left/right bars condition holds for detect_swings (default 5 bars)
    # The gap between pivots is 10 bars, which is fine.
    
    div = detect_rsi_divergence(closes, rsi, lookback=30, swing_bars=2)
    assert div == 1.0  # Bullish divergence
    
    
def test_mean_reversion_signal_guards():
    """Test Regime and Anti-Trend Guards."""
    signal = MeanReversionSignal(vwap_period=20)
    
    series = OHLCVSeries(symbol="AAPL", timeframe=Timeframe.D1)
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for i in range(25):
        series.append(OHLCV(
            symbol="AAPL", timeframe=Timeframe.D1, timestamp=base_time + timedelta(days=i),
            open=100.0, high=101.0, low=99.0, close=100.0, volume=10.0
        ))
        
    rsi = np.full(25, 50.0)
    
    # 1. Anti-Trend Steamroller Guard
    res = signal.evaluate(series, rsi, 110.0, 90.0, momentum_score=0.90)
    assert res.is_valid is False
    assert res.metadata["filter_failed"] == "anti_trend_guard"
    
    # 2. Regime Guard (too low)
    regime_low = RegimeProbabilities(trend_up=0.8, trend_down=0.0, mean_revert=0.2, crisis=0.0)
    res = signal.evaluate(series, rsi, 110.0, 90.0, regime_probs=regime_low, momentum_score=0.0)
    assert res.is_valid is False
    assert res.metadata["filter_failed"] == "regime_guard_too_low"
    
    # 3. Valid Execution
    regime_valid = RegimeProbabilities(trend_up=0.0, trend_down=0.0, mean_revert=0.9, crisis=0.1)
    res = signal.evaluate(series, rsi, 110.0, 90.0, regime_probs=regime_valid, momentum_score=0.1)
    assert res.is_valid is True
    # Since prices are flat, VWAP Z is 0. No divergence, so BB div is 0. Pairs is 0.
    assert res.score == 0.0
    assert res.direction == SignalDirection.NEUTRAL
