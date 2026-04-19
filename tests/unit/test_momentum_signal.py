"""Unit tests for the Momentum signal family."""

import numpy as np
import pytest
from datetime import datetime, timezone, timedelta

from algoforge.core.constants import Timeframe
from algoforge.core.models import OHLCV, OHLCVSeries
from algoforge.regime.models import RegimeProbabilities, RegimeState
from algoforge.signals.models import SignalDirection, SignalResult
from algoforge.signals.momentum.evaluator import (
    check_atr_percentile,
    check_volume_confirmation,
    time_series_momentum,
)
from algoforge.signals.momentum.signal import MomentumSignal
from algoforge.signals.momentum.vwap import calculate_vwap, vwap_momentum_score


def test_vwap_calculation():
    """Test VWAP calculation with session reset."""
    series = OHLCVSeries(symbol="AAPL", timeframe=Timeframe.M1)
    
    # Day 1: 3 bars
    base_time = datetime(2024, 1, 1, 9, 30, tzinfo=timezone.utc)
    series.append(OHLCV(symbol="AAPL", timeframe=Timeframe.M1, timestamp=base_time, open=100.0, high=101.0, low=99.0, close=100.0, volume=100.0))
    series.append(OHLCV(symbol="AAPL", timeframe=Timeframe.M1, timestamp=base_time + timedelta(minutes=1), open=100.0, high=102.0, low=100.0, close=101.0, volume=200.0))
    series.append(OHLCV(symbol="AAPL", timeframe=Timeframe.M1, timestamp=base_time + timedelta(minutes=2), open=101.0, high=103.0, low=101.0, close=102.0, volume=300.0))
    
    # Day 2: 2 bars (should reset)
    base_time_2 = datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc)
    series.append(OHLCV(symbol="AAPL", timeframe=Timeframe.M1, timestamp=base_time_2, open=200.0, high=201.0, low=199.0, close=200.0, volume=100.0))
    series.append(OHLCV(symbol="AAPL", timeframe=Timeframe.M1, timestamp=base_time_2 + timedelta(minutes=1), open=200.0, high=202.0, low=200.0, close=201.0, volume=100.0))
    
    vwap = calculate_vwap(series)
    
    # Typical prices: Day 1 -> 100.0, 101.0, 102.0
    # VWAP 1: (100*100) / 100 = 100.0
    assert np.isclose(vwap[0], 100.0)
    
    # VWAP 2: (100*100 + 101*200) / 300 = 30200 / 300 = 100.666...
    assert np.isclose(vwap[1], 100.66666666666667)
    
    # VWAP 3: (30200 + 102*300) / 600 = 60800 / 600 = 101.333...
    assert np.isclose(vwap[2], 101.33333333333333)
    
    # Typical prices: Day 2 -> 200.0, 201.0
    # VWAP 4 (reset): (200*100) / 100 = 200.0
    assert np.isclose(vwap[3], 200.0)
    
    # VWAP 5: (200*100 + 201*100) / 200 = 40100 / 200 = 200.5
    assert np.isclose(vwap[4], 200.5)


def test_time_series_momentum():
    """Test time-series momentum with skip logic."""
    closes = np.linspace(100, 200, 300) # steady uptrend
    
    score = time_series_momentum(closes, lookback=252, skip_recent=21)
    assert score > 0.0 # Positive trend
    
    closes_down = np.linspace(200, 100, 300)
    score_down = time_series_momentum(closes_down, lookback=252, skip_recent=21)
    assert score_down < 0.0 # Negative trend


def test_check_atr_percentile():
    """Test ATR percentile filtering."""
    atr = np.linspace(1.0, 10.0, 200) # 1 to 10
    
    # Latest is 10.0 (100th percentile) -> should fail
    assert check_atr_percentile(atr, 20.0, 80.0) is False
    
    # Force latest to be median (5.5) -> should pass
    atr[-1] = 5.5
    assert check_atr_percentile(atr, 20.0, 80.0) is True


def test_momentum_signal_regime_boost():
    """Test MomentumSignal with and without regime boost."""
    signal = MomentumSignal(tsmom_lookback=10, tsmom_skip=2, regime_boost=1.3)
    
    series = OHLCVSeries(symbol="AAPL", timeframe=Timeframe.D1)
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    
    # Create a strong uptrend
    for i in range(20):
        series.append(OHLCV(
            symbol="AAPL", timeframe=Timeframe.D1, timestamp=base_time + timedelta(days=i),
            open=100.0+i, high=101.0+i, low=99.0+i, close=100.0+i, volume=1000.0 + (i * 10.0)
        ))
        
    atr_series = np.linspace(1.0, 2.0, 200)
    atr_series[-1] = 1.5 # Median ATR -> valid
    
    # 1. No regime -> base score
    res_no_regime = signal.evaluate(series, kama=90.0, atr_series=atr_series)
    assert res_no_regime.is_valid is True
    assert res_no_regime.direction == SignalDirection.LONG
    base_score = res_no_regime.score
    
    # 2. Trend Up regime -> boosted score
    regime = RegimeProbabilities(trend_up=0.8, trend_down=0.1, mean_revert=0.1, crisis=0.0)
    res_boosted = signal.evaluate(series, kama=90.0, atr_series=atr_series, regime_probs=regime)
    assert res_boosted.is_valid is True
    assert res_boosted.score > base_score
    assert np.isclose(res_boosted.score, min(base_score * 1.3, 1.0))
    assert res_boosted.metadata.get("regime_boost") is True
    
    # 3. KAMA conflict -> invalid
    # Price is ~119, KAMA is 150 -> price is below trend but we want to go LONG
    res_invalid = signal.evaluate(series, kama=150.0, atr_series=atr_series)
    assert res_invalid.is_valid is False
    assert res_invalid.metadata.get("filter_failed") == "kama_conflict_long"
