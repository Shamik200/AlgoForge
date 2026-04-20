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
