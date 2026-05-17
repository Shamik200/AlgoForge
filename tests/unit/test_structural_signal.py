"""Unit tests for the Structural Confluence signal family."""

import pytest
from datetime import datetime, timezone, timedelta

from algoforge.core.constants import Timeframe
from algoforge.core.models import OHLCV, OHLCVSeries
from algoforge.regime.models import RegimeProbabilities
from algoforge.signals.models import SignalDirection
from algoforge.signals.structural.microstructure import detect_rejection
from algoforge.signals.structural.proximity import check_htf_overlap, find_tested_levels
from algoforge.signals.structural.signal import StructuralConfluenceSignal
from algoforge.technical.structural.engine import StructuralSnapshot
from algoforge.technical.structural.models import SRLevel, SRType


def test_detect_rejection():
    """Test candlestick wick and volume climax logic."""
    # Bullish Pin Bar
    # High: 105, Low: 95, Open: 104, Close: 104.5
    # Total range: 10. Lower wick: min(104, 104.5) - 95 = 9. Wick ratio: 9/10 = 0.9.
    assert detect_rejection(
        open_p=104.0, high_p=105.0, low_p=95.0, close_p=104.5,
        volume=2000.0, vol_sma=1000.0, is_support=True
    ) is True
    
    # Bearish Pin Bar (Failed support test because we need upper wick for resistance)
    assert detect_rejection(
        open_p=96.0, high_p=105.0, low_p=95.0, close_p=95.5,
        volume=2000.0, vol_sma=1000.0, is_support=True
    ) is False
    
    # Volume too low
    assert detect_rejection(
        open_p=104.0, high_p=105.0, low_p=95.0, close_p=104.5,
        volume=1000.0, vol_sma=1000.0, is_support=True
    ) is False


def test_proximity_levels():
    """Test finding levels within ATR bands."""
    snapshot = StructuralSnapshot(
        symbol="AAPL",
        timeframe=Timeframe.H1,
        timestamp=datetime.now(timezone.utc),
        sr_levels=[
            SRLevel(price=100.0, sr_type=SRType.SUPPORT, strength=4.5),
            SRLevel(price=90.0, sr_type=SRType.SUPPORT, strength=2.0),
            SRLevel(price=110.0, sr_type=SRType.RESISTANCE, strength=5.0)
        ]
    )
    
    # High 101, Low 99, ATR = 2. Band is +/- 1.0.
    # Level 100 is within [98, 102].
    support, resistance = find_tested_levels(101.0, 99.0, 2.0, snapshot)
    
    assert support is not None
    assert support.price == 100.0
    assert resistance is None
    
    # Test HTF overlap
    htf_snap = StructuralSnapshot(
        symbol="AAPL", timeframe=Timeframe.D1, timestamp=datetime.now(timezone.utc),
        sr_levels=[SRLevel(price=99.5, sr_type=SRType.SUPPORT, strength=3.0)]
    )
    
    overlap = check_htf_overlap(support, 2.0, [htf_snap])
    assert overlap is True  # 99.5 is within 100 +/- 1.0


def test_structural_signal_evaluate():
    """Test full structural signal evaluation including regime modifiers."""
    signal = StructuralConfluenceSignal(atr_period=14, vol_sma_period=20)
    
    series = OHLCVSeries(symbol="AAPL", timeframe=Timeframe.H1)
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    
    # Build 25 bars. Last bar will be a strong bullish rejection off 100.0.
    for i in range(24):
        series.append(OHLCV(
            symbol="AAPL", timeframe=Timeframe.H1, timestamp=base_time + timedelta(hours=i),
            open=102.0, high=103.0, low=101.0, close=102.5, volume=100.0
        ))
        
    # Bar 25: The rejection
    series.append(OHLCV(
        symbol="AAPL", timeframe=Timeframe.H1, timestamp=base_time + timedelta(hours=24),
        open=104.0, high=105.0, low=99.5, close=104.5, volume=1000.0  # Massive volume
    ))
    
    # Snapshot with a heavy support level at 100.0
    snapshot = StructuralSnapshot(
        symbol="AAPL", timeframe=Timeframe.H1, timestamp=datetime.now(timezone.utc),
        sr_levels=[SRLevel(price=100.0, sr_type=SRType.SUPPORT, strength=4.0)]
    )
    
    # Base Evaluation
    res1 = signal.evaluate(series, snapshot)
    assert res1.is_valid is True
    assert res1.direction == SignalDirection.LONG
    assert res1.score == 4.0 / 5.0  # 0.8
    
    # With HTF Overlap
    htf_snap = StructuralSnapshot(
        symbol="AAPL", timeframe=Timeframe.D1, timestamp=datetime.now(timezone.utc),
        sr_levels=[SRLevel(price=100.2, sr_type=SRType.SUPPORT, strength=3.0)]
    )
    res2 = signal.evaluate(series, snapshot, htf_snapshots=[htf_snap])
    assert res2.is_valid is True
    # Should cap at 1.0
    assert res2.score == 1.0
    
    # With Strong Counter-Trend Regime Dampening
    regime_trend_down = RegimeProbabilities(trend_up=0.0, trend_down=0.9, mean_revert=0.1, crisis=0.0)
    res3 = signal.evaluate(series, snapshot, regime_probs=regime_trend_down)
    assert res3.is_valid is True
    assert res3.score == (4.0 / 5.0) * 0.3  # 0.24
    assert res3.metadata["regime_mod"] == "trend_down_dampen"
    
    # With Mean-Revert Regime Boost
    regime_range = RegimeProbabilities(trend_up=0.0, trend_down=0.0, mean_revert=0.8, crisis=0.0)
    res4 = signal.evaluate(series, snapshot, regime_probs=regime_range)
    assert res4.is_valid is True
    # 0.8 * 1.3 = 1.04, clipped to 1.0
    assert res4.score == 1.0
    assert res4.metadata["regime_mod"] == "mean_revert_boost"


def test_trendline_pullback_confirmation():
    """Test trendline pullback detection with EMA/RSI/ADX confirmation (Requirement 2.5)."""
    from algoforge.technical.structural.models import Trendline, TrendDirection, SwingPoint
    from algoforge.technical.indicator_base import IndicatorResult
    
    signal = StructuralConfluenceSignal(atr_period=14, vol_sma_period=20)
    
    series = OHLCVSeries(symbol="AAPL", timeframe=Timeframe.H1)
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    
    # Build 25 bars with uptrend
    for i in range(25):
        series.append(OHLCV(
            symbol="AAPL", timeframe=Timeframe.H1, timestamp=base_time + timedelta(hours=i),
            open=100.0 + i * 0.5, high=101.0 + i * 0.5, low=99.0 + i * 0.5, 
            close=100.5 + i * 0.5, volume=100.0
        ))
    
    # Create swing points for trendline
    swing_points = [
        SwingPoint(index=0, price=99.0, is_high=False, timestamp=base_time),
        SwingPoint(index=10, price=104.0, is_high=False, timestamp=base_time + timedelta(hours=10)),
        SwingPoint(index=20, price=109.0, is_high=False, timestamp=base_time + timedelta(hours=20))
    ]
    
    # Create a support trendline
    trendline = Trendline(
        id="tl_1",
        symbol="AAPL",
        slope=0.5,
        intercept=99.0,
        touch_points=swing_points,
        touches=3,
        is_upper=False,  # Support line
        direction="support",
        strength=4.0,
        broken=False,
        invalidated=False
    )
    
    # Snapshot with trendline
    snapshot = StructuralSnapshot(
        symbol="AAPL", timeframe=Timeframe.H1, timestamp=datetime.now(timezone.utc),
        sr_levels=[],
        trendlines=[trendline],
        trend_direction=TrendDirection.UP
    )
    
    # Test 1: Without indicators (basic proximity signal)
    res1 = signal.evaluate(series, snapshot)
    assert res1.is_valid is True
    assert res1.direction == SignalDirection.LONG
    assert "trendline_proximity" in res1.metadata.get("signal_type", "")
    
    # Test 2: With indicators but confirmation fails (RSI out of range)
    indicators = {
        "ema": IndicatorResult(
            name="ema",
            values={
                "ema_5": [110.0] * 25,
                "ema_9": [109.0] * 25,
                "ema_21": [108.0] * 25
            }
        ),
        "rsi": IndicatorResult(
            name="rsi",
            values={"rsi": [70.0] * 25}  # Overbought - should fail
        ),
        "adx": IndicatorResult(
            name="adx",
            values={"adx": [30.0] * 25}
        )
    }
    
    res2 = signal.evaluate(series, snapshot, indicators=indicators)
    assert res2.is_valid is True
    assert res2.direction == SignalDirection.LONG
    # Score should be reduced due to failed confirmation
    assert res2.score < res1.score
    assert res2.metadata.get("confirmation_status") == "failed"
    assert res2.metadata.get("rsi_check") == "failed"
    
    # Test 3: With indicators and confirmation passes
    indicators_pass = {
        "ema": IndicatorResult(
            name="ema",
            values={
                "ema_5": [112.0] * 25,
                "ema_9": [111.0] * 25,
                "ema_21": [110.0] * 25
            }
        ),
        "rsi": IndicatorResult(
            name="rsi",
            values={"rsi": [50.0] * 25}  # In range 40-60
        ),
        "adx": IndicatorResult(
            name="adx",
            values={"adx": [30.0] * 25}  # > 25
        )
    }
    
    res3 = signal.evaluate(series, snapshot, indicators=indicators_pass)
    assert res3.is_valid is True
    assert res3.direction == SignalDirection.LONG
    # Score should be boosted due to passed confirmation
    assert res3.score > res1.score
    assert res3.metadata.get("confirmation_status") == "passed"
    assert res3.metadata.get("ema_check") == "passed"
    assert res3.metadata.get("rsi_check") == "passed"
    assert res3.metadata.get("adx_check") == "passed"
    assert "trendline_pullback" in res3.metadata.get("signal_type", "")
    
    # Test 4: Bearish setup with resistance trendline
    # Create a new series for bearish test with price near resistance
    series_bearish = OHLCVSeries(symbol="AAPL", timeframe=Timeframe.H1)
    
    # Build 25 bars with price near resistance trendline
    for i in range(25):
        # Price should be near the resistance line at 103 (115 - 0.5*24)
        series_bearish.append(OHLCV(
            symbol="AAPL", timeframe=Timeframe.H1, timestamp=base_time + timedelta(hours=i),
            open=102.0, high=103.5, low=101.5, 
            close=102.5, volume=100.0
        ))
    
    swing_points_resistance = [
        SwingPoint(index=0, price=115.0, is_high=True, timestamp=base_time),
        SwingPoint(index=10, price=110.0, is_high=True, timestamp=base_time + timedelta(hours=10)),
        SwingPoint(index=20, price=105.0, is_high=True, timestamp=base_time + timedelta(hours=20))
    ]
    
    trendline_resistance = Trendline(
        id="tl_2",
        symbol="AAPL",
        slope=-0.5,
        intercept=115.0,
        touch_points=swing_points_resistance,
        touches=3,
        is_upper=True,  # Resistance line
        direction="resistance",
        strength=4.0,
        broken=False,
        invalidated=False
    )
    
    snapshot_bearish = StructuralSnapshot(
        symbol="AAPL", timeframe=Timeframe.H1, timestamp=datetime.now(timezone.utc),
        sr_levels=[],
        trendlines=[trendline_resistance],
        trend_direction=TrendDirection.DOWN
    )
    
    indicators_bearish = {
        "ema": IndicatorResult(
            name="ema",
            values={
                "ema_5": [101.0] * 25,
                "ema_9": [102.0] * 25,
                "ema_21": [103.0] * 25  # Bearish alignment
            }
        ),
        "rsi": IndicatorResult(
            name="rsi",
            values={"rsi": [50.0] * 25}
        ),
        "adx": IndicatorResult(
            name="adx",
            values={"adx": [30.0] * 25}
        )
    }
    
    res4 = signal.evaluate(series_bearish, snapshot_bearish, indicators=indicators_bearish)
    assert res4.is_valid is True
    assert res4.direction == SignalDirection.SHORT
    assert res4.score < 0  # Negative for short
    assert res4.metadata.get("confirmation_status") == "passed"
    assert res4.metadata.get("ema_alignment") == "bearish"
