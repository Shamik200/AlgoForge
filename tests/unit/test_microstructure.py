"""Unit tests for the Microstructure / Order Flow signal family."""

import pytest

from algoforge.signals.microstructure.vwap import VWAPTracker
from algoforge.signals.microstructure.volume import calculate_volume_imbalance, detect_obv_divergence
from algoforge.signals.microstructure.family import MicrostructureFamily
from algoforge.signals.models import SignalDirection


def test_vwap_tracker_basic():
    """Test VWAP accumulation and deviation score."""
    tracker = VWAPTracker(deviation_threshold=1.5)

    # Feed 5 candles with increasing prices and constant volume
    candles = [
        (100, 98, 99, 1000),   # TP = 99
        (101, 99, 100, 1000),  # TP = 100
        (102, 100, 101, 1000), # TP = 101
        (103, 101, 102, 1000), # TP = 102
        (104, 102, 103, 1000), # TP = 103
    ]
    for h, l, c, v in candles:
        tracker.update(h, l, c, v)

    # VWAP should be average of typical prices: (99+100+101+102+103)/5 = 101
    assert pytest.approx(tracker.current_vwap, 0.01) == 101.0

    # Price at 103 is above VWAP (101). Deviation is positive.
    # For mean reversion, score should be NEGATIVE (sell signal).
    score = tracker.deviation_score(103.0)
    assert score < 0  # Extended above VWAP → short signal


def test_vwap_session_reset():
    """Test that session reset clears all accumulators."""
    tracker = VWAPTracker()
    tracker.update(100, 98, 99, 1000)
    assert tracker.current_vwap > 0

    tracker.reset_session()
    assert tracker.current_vwap == 0.0


def test_volume_imbalance():
    """Test buying pressure calculation."""
    # Close at high → max buying pressure
    assert calculate_volume_imbalance(110, 100, 110) == 1.0

    # Close at low → max selling pressure
    assert calculate_volume_imbalance(110, 100, 100) == 0.0

    # Close at midpoint → neutral
    assert calculate_volume_imbalance(110, 100, 105) == 0.5

    # Doji (high == low) → neutral
    assert calculate_volume_imbalance(100, 100, 100) == 0.5


def test_obv_divergence_bearish():
    """Test bearish divergence detection (price high, OBV not)."""
    # Create a scenario: price trends up but volume dries up
    prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109,
              110, 111, 112, 113, 114, 115]
    # Volume decreasing on up moves
    volumes = [1000, 900, 800, 700, 600, 500, 400, 300, 200, 100,
               90, 80, 70, 60, 50, 40]

    score = detect_obv_divergence(prices, volumes, window=14)
    # Price is at a high but OBV should show divergence
    # Score should be negative (bearish)
    assert score <= 0.0


def test_obv_divergence_insufficient_data():
    """Test OBV returns 0 with insufficient data."""
    assert detect_obv_divergence([100, 101], [1000, 1000], window=14) == 0.0


def test_microstructure_family_intraday():
    """Test the full family generates valid signals on intraday data."""
    family = MicrostructureFamily(timeframe="5m")

    # Feed enough candles to build up VWAP and OBV history
    for i in range(20):
        price = 100 + i * 0.5
        result = family.generate(
            high=price + 1, low=price - 1, close=price, volume=1000
        )
    
    assert result.is_valid is True
    assert result.family_name == "microstructure"
    assert -1.0 <= result.score <= 1.0


def test_microstructure_family_daily_disabled():
    """Test the family self-disables on daily timeframe."""
    family = MicrostructureFamily(timeframe="1d")

    result = family.generate(high=105, low=95, close=100, volume=1000)

    assert result.is_valid is False
    assert result.score == 0.0
    assert "disabled" in result.metadata.get("reason", "")


def test_microstructure_family_weekly_disabled():
    """Test the family self-disables on weekly timeframe."""
    family = MicrostructureFamily(timeframe="1W")

    result = family.generate(high=105, low=95, close=100, volume=1000)
    assert result.is_valid is False
