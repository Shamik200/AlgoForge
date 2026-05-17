"""Unit tests for the Breakout signal family."""

import numpy as np
import pytest
from datetime import datetime, timezone, timedelta, time

from algoforge.core.constants import Timeframe
from algoforge.core.models import OHLCV, OHLCVSeries
from algoforge.regime.models import RegimeProbabilities
from algoforge.signals.models import SignalDirection
from algoforge.signals.breakout.donchian import calc_donchian_channels, detect_failed_breakout
from algoforge.signals.breakout.signal_orb import ORBSignal
from algoforge.signals.breakout.signal_volatility import VolatilityBreakoutSignal
from algoforge.signals.breakout.volatility import calc_keltner_channels, detect_squeeze


def test_volatility_squeeze():
    """Test Keltner Channels and Squeeze detection."""
    # Create flat data
    highs = np.full(30, 105.0)
    lows = np.full(30, 95.0)
    closes = np.full(30, 100.0)
    
    # Keltner
    kc_u, kc_c, kc_l = calc_keltner_channels(highs, lows, closes, ema_period=20, atr_period=14)
    
    # ATR is 10. 1.5 * 10 = 15. Center is 100.
    assert np.isclose(kc_u[-1], 115.0)
    assert np.isclose(kc_l[-1], 85.0)
    
    # If BB is inside Keltner, it's a squeeze
    bb_u = np.full(30, 110.0)
    bb_l = np.full(30, 90.0)
    
    squeeze = detect_squeeze(bb_u, bb_l, kc_u, kc_l)
    assert squeeze[-1] == True
    
    # If BB expands outside Keltner, squeeze is over
    bb_u[-1] = 120.0
    bb_l[-1] = 80.0
    
    squeeze_off = detect_squeeze(bb_u, bb_l, kc_u, kc_l)
    assert squeeze_off[-1] == False


def test_failed_breakout_reversal():
    """Test stateless recognition of failed breakouts."""
    closes = np.full(25, 100.0)
    dh = np.full(25, 105.0)
    dl = np.full(25, 95.0)
    atr = 2.0
    
    # 1. Normal state
    f_bull, f_bear = detect_failed_breakout(closes, dh, dl, atr)
    assert f_bull == 0
    assert f_bear == 0
    
    # 2. Breakout occurred previously, now reversing
    # Previous close was above DH[prev]
    closes[-2] = 106.0 
    dh[-2] = 105.0
    
    # Current close is back inside
    # Current close < DH[curr] - 0.5 * ATR -> 105.0 - 1.0 = 104.0
    closes[-1] = 103.0
    dh[-1] = 105.0
    
    f_bull, f_bear = detect_failed_breakout(closes, dh, dl, atr)
    assert f_bull == 1
    assert f_bear == 0


def test_orb_signal_timeframes():
    """Test ORB isolation to intraday logic."""
    orb = ORBSignal(open_time=time(9, 30), duration_minutes=30)
    
    # Test rejection of daily data
    series_d1 = OHLCVSeries(symbol="AAPL", timeframe=Timeframe.D1)
    res = orb.evaluate(series_d1)
    assert res.is_valid is False
    assert res.metadata["filter_failed"] == "invalid_timeframe"
    
    # Test intraday M5 data setup
    series_m5 = OHLCVSeries(symbol="AAPL", timeframe=Timeframe.M5)
    base_time = datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc)
    
    for i in range(30):
        # Time steps of 5 minutes
        dt = base_time + timedelta(minutes=5*i)
        series_m5.append(OHLCV(
            symbol="AAPL", timeframe=Timeframe.M5, timestamp=dt,
            open=100.0, high=101.0, low=99.0, close=100.0, volume=1000.0
        ))
        
    res2 = orb.evaluate(series_m5)
    # The last bar in loop is 11:25. It's past the 10:00 end of ORB.
    # However, volume ratio might be 1.0 (flat volume).
    assert res2.is_valid is False
    assert res2.metadata["filter_failed"] == "insufficient_volume"


def test_volatility_breakout_guards():
    """Test Regime and Volume guards on standard breakout."""
    signal = VolatilityBreakoutSignal(period=20)
    
    series = OHLCVSeries(symbol="AAPL", timeframe=Timeframe.D1)
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    
    for i in range(25):
        series.append(OHLCV(
            symbol="AAPL", timeframe=Timeframe.D1, timestamp=base_time + timedelta(days=i),
            open=100.0, high=101.0, low=99.0, close=100.0, volume=10.0
        ))
        
    bb_u = np.full(25, 110.0)
    bb_l = np.full(25, 90.0)
    
    # 1. Regime Guard failure
    regime_chop = RegimeProbabilities(trend_up=0.2, trend_down=0.2, mean_revert=0.6, crisis=0.0)
    res = signal.evaluate(series, bb_u, bb_l, regime_probs=regime_chop)
    assert res.is_valid is False
    assert res.metadata["filter_failed"] == "regime_guard"
    
    # 2. Volume confirmation failure
    regime_trend = RegimeProbabilities(trend_up=0.8, trend_down=0.0, mean_revert=0.2, crisis=0.0)
    res_vol = signal.evaluate(series, bb_u, bb_l, regime_probs=regime_trend)
    assert res_vol.is_valid is False
    assert res_vol.metadata["filter_failed"] == "insufficient_volume"


def test_trendline_break_bullish():
    """Test bullish trendline break detection with volume confirmation."""
    from algoforge.technical.structural.models import StructuralSnapshot, Trendline, SwingPoint
    
    signal = VolatilityBreakoutSignal(period=20)
    
    # Create series with price breaking above resistance trendline
    series = OHLCVSeries(symbol="AAPL", timeframe=Timeframe.D1)
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    
    # Build price data that approaches and breaks a resistance line at ~105
    for i in range(25):
        # Price gradually rises from 100 to 106
        price = 100.0 + (i * 0.25)
        volume = 10.0 if i < 24 else 50.0  # High volume on breakout bar
        
        series.append(OHLCV(
            symbol="AAPL", timeframe=Timeframe.D1, timestamp=base_time + timedelta(days=i),
            open=price, high=price + 1.0, low=price - 1.0, close=price, volume=volume
        ))
    
    # Create a resistance trendline at ~105
    swing_points = [
        SwingPoint(index=10, price=102.5, is_high=True, volume=10.0, timestamp=base_time + timedelta(days=10)),
        SwingPoint(index=20, price=105.0, is_high=True, volume=10.0, timestamp=base_time + timedelta(days=20)),
    ]
    
    trendline = Trendline(
        slope=0.25,  # Rising resistance
        intercept=100.0,
        touch_points=swing_points,
        touches=2,
        is_upper=True,
        direction="resistance",
        strength=3.0,
        broken=False,
        invalidated=False,
    )
    
    snapshot = StructuralSnapshot(
        symbol="AAPL",
        trendlines=[trendline],
    )
    
    bb_u = np.full(25, 110.0)
    bb_l = np.full(25, 90.0)
    
    # Evaluate with trendline
    result = signal.evaluate(series, bb_u, bb_l, structural_snapshot=snapshot)
    
    # Should detect bullish trendline break
    assert result.is_valid is True
    assert result.direction == SignalDirection.LONG
    assert result.score > 0.7  # High conviction
    assert result.metadata["pattern"] == "trendline_breakout_bullish"
    assert "trendline_id" in result.metadata


def test_trendline_break_bearish():
    """Test bearish trendline break detection with volume confirmation."""
    from algoforge.technical.structural.models import StructuralSnapshot, Trendline, SwingPoint
    
    signal = VolatilityBreakoutSignal(period=20)
    
    # Create series with price breaking below support trendline
    series = OHLCVSeries(symbol="AAPL", timeframe=Timeframe.D1)
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    
    # Build price data that approaches and breaks a support line at ~95
    for i in range(25):
        # Price gradually falls from 100 to 94
        price = 100.0 - (i * 0.25)
        volume = 10.0 if i < 24 else 50.0  # High volume on breakout bar
        
        series.append(OHLCV(
            symbol="AAPL", timeframe=Timeframe.D1, timestamp=base_time + timedelta(days=i),
            open=price, high=price + 1.0, low=price - 1.0, close=price, volume=volume
        ))
    
    # Create a support trendline at ~95
    swing_points = [
        SwingPoint(index=10, price=97.5, is_high=False, volume=10.0, timestamp=base_time + timedelta(days=10)),
        SwingPoint(index=20, price=95.0, is_high=False, volume=10.0, timestamp=base_time + timedelta(days=20)),
    ]
    
    trendline = Trendline(
        slope=-0.25,  # Falling support
        intercept=100.0,
        touch_points=swing_points,
        touches=2,
        is_upper=False,
        direction="support",
        strength=3.0,
        broken=False,
        invalidated=False,
    )
    
    snapshot = StructuralSnapshot(
        symbol="AAPL",
        trendlines=[trendline],
    )
    
    bb_u = np.full(25, 110.0)
    bb_l = np.full(25, 90.0)
    
    # Evaluate with trendline
    result = signal.evaluate(series, bb_u, bb_l, structural_snapshot=snapshot)
    
    # Should detect bearish trendline break
    assert result.is_valid is True
    assert result.direction == SignalDirection.SHORT
    assert result.score < -0.7  # High conviction (negative)
    assert result.metadata["pattern"] == "trendline_breakout_bearish"
    assert "trendline_id" in result.metadata


def test_trendline_break_no_volume():
    """Test that trendline breaks without volume confirmation are ignored."""
    from algoforge.technical.structural.models import StructuralSnapshot, Trendline, SwingPoint
    
    signal = VolatilityBreakoutSignal(period=20)
    
    # Create series with price breaking above resistance but LOW volume
    series = OHLCVSeries(symbol="AAPL", timeframe=Timeframe.D1)
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    
    for i in range(25):
        price = 100.0 + (i * 0.25)
        volume = 10.0  # Constant low volume (no spike)
        
        series.append(OHLCV(
            symbol="AAPL", timeframe=Timeframe.D1, timestamp=base_time + timedelta(days=i),
            open=price, high=price + 1.0, low=price - 1.0, close=price, volume=volume
        ))
    
    swing_points = [
        SwingPoint(index=10, price=102.5, is_high=True, volume=10.0, timestamp=base_time + timedelta(days=10)),
        SwingPoint(index=20, price=105.0, is_high=True, volume=10.0, timestamp=base_time + timedelta(days=20)),
    ]
    
    trendline = Trendline(
        slope=0.25,
        intercept=100.0,
        touch_points=swing_points,
        touches=2,
        is_upper=True,
        direction="resistance",
        strength=3.0,
        broken=False,
        invalidated=False,
    )
    
    snapshot = StructuralSnapshot(
        symbol="AAPL",
        trendlines=[trendline],
    )
    
    bb_u = np.full(25, 110.0)
    bb_l = np.full(25, 90.0)
    
    # Evaluate with trendline but no volume
    result = signal.evaluate(series, bb_u, bb_l, structural_snapshot=snapshot)
    
    # Should NOT detect trendline break due to lack of volume
    # Will fall through to standard breakout logic which also requires volume
    assert result.is_valid is False
    assert result.metadata.get("filter_failed") == "insufficient_volume"
