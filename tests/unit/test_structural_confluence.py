"""Tests for the Structural Confluence module."""

import numpy as np
import pytest
from datetime import datetime, timezone

from algoforge.core.constants import Timeframe
from algoforge.core.models import OHLCV, OHLCVSeries
from algoforge.structural.engine import StructuralConfluenceEngine
from algoforge.structural.models import ConfluenceZone, LevelType, PriceLevel
from algoforge.structural.swings import cluster_swings, detect_swings
from algoforge.technical.engine import IndicatorSnapshot
from algoforge.technical.indicator_base import IndicatorResult


def test_detect_swings() -> None:
    """Test swing high/low detection."""
    # Construct a simple peak and trough
    # Highs: 10, 11, 12, 11, 10 -> peak at index 2 (12)
    # Lows:  9,  8,  7,  8,  9 -> trough at index 2 (7)
    
    # We need left_bars + right_bars + 1 data points. Let's use 2 and 2 for a total of 5.
    highs = np.array([10.0, 11.0, 15.0, 11.0, 10.0])
    lows = np.array([9.0, 8.0, 5.0, 8.0, 9.0])
    
    swings = detect_swings(highs, lows, left_bars=2, right_bars=2)
    
    assert len(swings) == 2
    
    # Check types and values (sorted by price ascending)
    assert swings[0].level_type == LevelType.SWING_LOW
    assert swings[0].price == 5.0
    
    assert swings[1].level_type == LevelType.SWING_HIGH
    assert swings[1].price == 15.0


def test_detect_swings_insufficient_data() -> None:
    """Test detect_swings with too little data."""
    highs = np.array([10.0, 11.0])
    lows = np.array([9.0, 8.0])
    
    swings = detect_swings(highs, lows, left_bars=2, right_bars=2)
    assert len(swings) == 0


def test_cluster_swings() -> None:
    """Test clustering of nearby swing points."""
    swings = [
        PriceLevel(price=10.0, level_type=LevelType.SWING_HIGH, strength=1.0, age=5),
        PriceLevel(price=10.1, level_type=LevelType.SWING_HIGH, strength=1.0, age=10),
        PriceLevel(price=15.0, level_type=LevelType.SWING_HIGH, strength=1.0, age=2),
        PriceLevel(price=5.0, level_type=LevelType.SWING_LOW, strength=1.0, age=1),
        PriceLevel(price=4.9, level_type=LevelType.SWING_LOW, strength=1.0, age=20),
    ]
    
    # ATR = 1.0. Threshold is 0.5 * ATR = 0.5.
    # 10.0 and 10.1 should cluster.
    # 5.0 and 4.9 should cluster.
    # 15.0 stays alone.
    
    clustered = cluster_swings(swings, atr=1.0)
    
    assert len(clustered) == 3
    
    # Lows first because sorted by price
    assert clustered[0].level_type == LevelType.SWING_LOW
    assert np.isclose(clustered[0].price, 4.95)
    assert clustered[0].age == 1 # Minimum age of the group
    
    # Highs next
    assert clustered[1].level_type == LevelType.SWING_HIGH
    assert np.isclose(clustered[1].price, 10.05)
    assert clustered[1].age == 5
    
    assert clustered[2].level_type == LevelType.SWING_HIGH
    assert np.isclose(clustered[2].price, 15.0)


def test_engine_empty_series() -> None:
    """Test engine with an empty series."""
    engine = StructuralConfluenceEngine()
    series = OHLCVSeries(symbol="AAPL", timeframe=Timeframe.D1)
    snapshot = IndicatorSnapshot()
    
    zones = engine.compute(series, snapshot)
    assert zones == []


def test_engine_confluence() -> None:
    """Test engine confluence aggregation."""
    engine = StructuralConfluenceEngine(confluence_bandwidth_atr=0.5)
    
    # Mock a series
    series = OHLCVSeries(symbol="AAPL", timeframe=Timeframe.D1)
    base = 100.0
    for i in range(250):
        series.append(
            OHLCV(
                symbol="AAPL",
                timeframe=Timeframe.D1,
                timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
                open=base,
                high=base + 1,
                low=base - 1,
                close=base,
                volume=1000.0,
            )
        )
    
    # Mock an IndicatorSnapshot with converging elements around price 100.0
    snapshot = IndicatorSnapshot()
    
    # KAMA at 100.5
    snapshot.set("kama", IndicatorResult(
        name="kama",
        values={"kama": [100.5]},
        params={}
    ))
    
    # Volume Profile POC at 99.8, VAH at 105, VAL at 95
    snapshot.set("volume_profile", IndicatorResult(
        name="volume_profile",
        values={"poc": [99.8], "vah": [105.0], "val": [95.0]},
        params={}
    ))
    
    # ATR = 2.0. Threshold = 0.5 * 2.0 = 1.0.
    snapshot.set("atr", IndicatorResult(
        name="atr",
        values={"atr": [2.0]},
        params={}
    ))
    
    zones = engine.compute(series, snapshot)
    
    # Expect a high confluence zone around 100
    # Contributing elements:
    # 1. KAMA at 100.5
    # 2. POC at 99.8
    # 3. EMA 50/200 (since series is flat at 100, EMAs will be 100)
    # 4. Swings (flat series won't have many swings, but let's see)
    
    confluence_zones = [z for z in zones if z.is_high_confluence]
    
    assert len(confluence_zones) > 0
    main_zone = next(z for z in confluence_zones if abs(z.center_price - 100.0) < 2.0)
    
    assert main_zone.score >= 3.0
    
    # Check that the contributing levels include our mocks
    level_types = [l.level_type for l in main_zone.contributing_levels]
    assert LevelType.POC in level_types
    
    # Either dynamic support or resistance should be there from KAMA or EMA
    assert LevelType.DYNAMIC_RESISTANCE in level_types or LevelType.DYNAMIC_SUPPORT in level_types
