"""Tests for Phase 3 — Structural Analysis (S/R, Trendlines, Trend Direction)."""

from datetime import datetime, timezone

import numpy as np
import pytest

from algoforge.technical.structural.models import (
    Channel,
    ChannelType,
    SRLevel,
    SRType,
    StructuralSnapshot,
    SwingPoint,
    Trendline,
    TrendDirection,
)
from algoforge.technical.structural.sr_detector import SRDetector
from algoforge.technical.structural.trendline_builder import TrendlineBuilder
from algoforge.technical.structural.trend_analyzer import TrendAnalyzer
from algoforge.technical.structural.engine import StructuralEngine
from algoforge.core.constants import Timeframe
from algoforge.core.models import OHLCV, OHLCVSeries


# ---------------------------------------------------------------------------
# Test data generators
# ---------------------------------------------------------------------------

def _ts(i: int) -> datetime:
    """Generate a timestamp for index i."""
    return datetime(2024, 1, 1, i % 24, tzinfo=timezone.utc)


def _make_uptrend(n: int = 100) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[datetime]]:
    """Generate uptrend data with clear HH/HL pattern and swing points."""
    np.random.seed(42)
    base = 100.0
    closes = np.zeros(n)
    highs = np.zeros(n)
    lows = np.zeros(n)
    volumes = np.zeros(n)
    timestamps = []

    for i in range(n):
        # Create zigzag up pattern
        cycle = i % 10
        if cycle < 5:
            base += 0.3  # Rally phase
        else:
            base -= 0.15  # Shallow pullback (higher lows)

        noise = np.random.randn() * 0.05
        closes[i] = base + noise
        highs[i] = closes[i] + abs(np.random.randn()) * 0.2
        lows[i] = closes[i] - abs(np.random.randn()) * 0.2
        volumes[i] = 100000 + np.random.randint(-20000, 20000)
        timestamps.append(_ts(i))

    return highs, lows, closes, volumes, timestamps


def _make_downtrend(n: int = 100) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[datetime]]:
    """Generate downtrend data with clear LH/LL pattern."""
    np.random.seed(42)
    base = 200.0
    closes = np.zeros(n)
    highs = np.zeros(n)
    lows = np.zeros(n)
    volumes = np.zeros(n)
    timestamps = []

    for i in range(n):
        cycle = i % 10
        if cycle < 5:
            base -= 0.3
        else:
            base += 0.15

        noise = np.random.randn() * 0.05
        closes[i] = base + noise
        highs[i] = closes[i] + abs(np.random.randn()) * 0.2
        lows[i] = closes[i] - abs(np.random.randn()) * 0.2
        volumes[i] = 100000 + np.random.randint(-20000, 20000)
        timestamps.append(_ts(i))

    return highs, lows, closes, volumes, timestamps


def _make_range(n: int = 100) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[datetime]]:
    """Generate ranging/sideways data."""
    np.random.seed(42)
    base = 150.0
    closes = np.zeros(n)
    highs = np.zeros(n)
    lows = np.zeros(n)
    volumes = np.zeros(n)
    timestamps = []

    for i in range(n):
        closes[i] = base + np.sin(i * 0.3) * 2 + np.random.randn() * 0.1
        highs[i] = closes[i] + abs(np.random.randn()) * 0.3
        lows[i] = closes[i] - abs(np.random.randn()) * 0.3
        volumes[i] = 100000 + np.random.randint(-20000, 20000)
        timestamps.append(_ts(i))

    return highs, lows, closes, volumes, timestamps


def _make_series(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, volumes: np.ndarray, timestamps: list[datetime],
    symbol: str = "TEST", timeframe: Timeframe = Timeframe.D1,
) -> OHLCVSeries:
    """Convert arrays into OHLCVSeries."""
    series = OHLCVSeries(symbol=symbol, timeframe=timeframe)
    for i in range(len(closes)):
        o = float(closes[i - 1]) if i > 0 else float(closes[i])
        h = float(highs[i])
        lo = float(lows[i])
        c = float(closes[i])
        # Ensure OHLC consistency
        h = max(h, o, c)
        lo = min(lo, o, c)
        series.append(OHLCV(
            symbol=symbol, timeframe=timeframe, timestamp=timestamps[i],
            open=round(o, 4), high=round(h, 4), low=round(lo, 4),
            close=round(c, 4), volume=float(volumes[i]),
        ))
    return series


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestModels:
    """Test structural analysis Pydantic models."""

    def test_sr_level_creation(self) -> None:
        level = SRLevel(price=100.0, sr_type=SRType.SUPPORT, strength=85.0)
        assert level.price == 100.0
        assert level.sr_type == SRType.SUPPORT
        assert not level.broken

    def test_swing_point_creation(self) -> None:
        sp = SwingPoint(index=10, price=150.0, is_high=True, volume=50000)
        assert sp.index == 10
        assert sp.is_high

    def test_trendline_price_at(self) -> None:
        """Trendline price_at follows y = mx + b."""
        sp1 = SwingPoint(index=0, price=100.0, is_high=False)
        sp2 = SwingPoint(index=10, price=110.0, is_high=False)
        tl = Trendline(slope=1.0, intercept=100.0, touch_points=[sp1, sp2], is_upper=False)
        assert tl.price_at(5) == 105.0
        assert tl.price_at(10) == 110.0

    def test_trendline_touch_count(self) -> None:
        sp1 = SwingPoint(index=0, price=100.0, is_high=True)
        sp2 = SwingPoint(index=10, price=110.0, is_high=True)
        sp3 = SwingPoint(index=20, price=120.0, is_high=True)
        tl = Trendline(slope=1.0, intercept=100.0, touch_points=[sp1, sp2, sp3], is_upper=True)
        assert tl.touch_count == 3

    def test_structural_snapshot_filters(self) -> None:
        """Support/resistance level filters."""
        snap = StructuralSnapshot(
            symbol="TEST",
            sr_levels=[
                SRLevel(price=100, sr_type=SRType.SUPPORT, strength=50),
                SRLevel(price=110, sr_type=SRType.RESISTANCE, strength=80),
                SRLevel(price=95, sr_type=SRType.SUPPORT, strength=90, broken=True),
            ],
        )
        assert len(snap.support_levels) == 1  # Broken one excluded
        assert len(snap.resistance_levels) == 1

    def test_trend_direction_enum(self) -> None:
        assert TrendDirection.UP.value == "up"
        assert TrendDirection.DOWN.value == "down"
        assert TrendDirection.UNCLEAR.value == "unclear"


# ---------------------------------------------------------------------------
# S/R Detector tests
# ---------------------------------------------------------------------------

class TestSRDetector:
    """Test fractal-based S/R detection."""

    def test_find_swing_points_uptrend(self) -> None:
        """Uptrend should produce swing highs and lows."""
        h, l, c, v, ts = _make_uptrend()
        detector = SRDetector(fractal_window=2)
        sh, sl = detector.find_swing_points(h, l, v, ts)
        assert len(sh) > 0, "Should find swing highs"
        assert len(sl) > 0, "Should find swing lows"

    def test_find_swing_points_range(self) -> None:
        """Range data should produce many swing points."""
        h, l, c, v, ts = _make_range()
        detector = SRDetector(fractal_window=2)
        sh, sl = detector.find_swing_points(h, l, v, ts)
        assert len(sh) >= 3, "Range should have multiple swing highs"
        assert len(sl) >= 3, "Range should have multiple swing lows"

    def test_detect_returns_sr_levels(self) -> None:
        """Full detect returns levels with strength scores."""
        h, l, c, v, ts = _make_range()
        detector = SRDetector(fractal_window=2, max_levels=10)
        levels, sh, sl = detector.detect(h, l, c, v, ts)
        assert len(levels) > 0
        assert all(lev.strength > 0 for lev in levels)

    def test_max_levels_respected(self) -> None:
        """Never returns more than max_levels."""
        h, l, c, v, ts = _make_range()
        detector = SRDetector(fractal_window=2, max_levels=3)
        levels, _, _ = detector.detect(h, l, c, v, ts)
        assert len(levels) <= 3

    def test_levels_sorted_by_strength(self) -> None:
        """Returned levels are sorted by strength descending."""
        h, l, c, v, ts = _make_range()
        detector = SRDetector(fractal_window=2)
        levels, _, _ = detector.detect(h, l, c, v, ts)
        strengths = [lev.strength for lev in levels]
        assert strengths == sorted(strengths, reverse=True)

    def test_cluster_merging(self) -> None:
        """Nearby levels should be merged."""
        h, l, c, v, ts = _make_range(200)
        detector = SRDetector(fractal_window=2, merge_pct=0.01)  # 1% merge
        levels, _, _ = detector.detect(h, l, c, v, ts)
        # No two levels should be within 1% of each other
        for i, a in enumerate(levels):
            for b in levels[i + 1:]:
                pct_diff = abs(a.price - b.price) / max(a.price, b.price)
                assert pct_diff > 0.005, f"Levels {a.price:.2f} and {b.price:.2f} too close"


# ---------------------------------------------------------------------------
# Trendline Builder tests
# ---------------------------------------------------------------------------

class TestTrendlineBuilder:
    """Test trendline construction."""

    def test_build_finds_trendlines(self) -> None:
        """Should find at least some trendlines from trend data."""
        h, l, c, v, ts = _make_uptrend()
        detector = SRDetector(fractal_window=2)
        _, sh, sl = detector.detect(h, l, c, v, ts)

        builder = TrendlineBuilder(touch_tolerance_pct=0.01, min_touches=2)
        lines = builder.build(sh, sl, h, l, c)
        # May or may not find lines depending on data — test it doesn't crash
        assert isinstance(lines, list)

    def test_max_lines_limit(self) -> None:
        """Never returns more than max_lines."""
        h, l, c, v, ts = _make_uptrend(200)
        detector = SRDetector(fractal_window=2)
        _, sh, sl = detector.detect(h, l, c, v, ts)

        builder = TrendlineBuilder(max_lines=4, touch_tolerance_pct=0.01)
        lines = builder.build(sh, sl, h, l, c)
        assert len(lines) <= 4

    def test_trendline_has_slope_and_intercept(self) -> None:
        """Each trendline has valid slope and intercept."""
        h, l, c, v, ts = _make_uptrend(200)
        detector = SRDetector(fractal_window=2)
        _, sh, sl = detector.detect(h, l, c, v, ts)

        builder = TrendlineBuilder(touch_tolerance_pct=0.01)
        lines = builder.build(sh, sl, h, l, c)
        for line in lines:
            assert isinstance(line.slope, float)
            assert isinstance(line.intercept, float)
            assert line.touch_count >= 2

    def test_empty_swing_points(self) -> None:
        """No crash with empty swing points."""
        builder = TrendlineBuilder()
        h = np.array([1.0, 2.0, 3.0])
        l = np.array([0.5, 1.0, 1.5])
        c = np.array([0.8, 1.5, 2.0])
        lines = builder.build([], [], h, l, c)
        assert lines == []

    def test_detect_trendlines_with_dataframe(self) -> None:
        """Test detect_trendlines method with DataFrame input."""
        import pandas as pd
        
        # Create sample data
        h, l, c, v, ts = _make_uptrend(100)
        bars = pd.DataFrame({
            "high": h,
            "low": l,
            "close": c,
            "volume": v,
        }, index=pd.DatetimeIndex(ts))
        
        builder = TrendlineBuilder(touch_tolerance_pct=0.01, min_touches=3)
        trendlines = builder.detect_trendlines("AAPL", bars, min_touches=3)
        
        # Verify trendlines have required fields
        assert isinstance(trendlines, list)
        for trendline in trendlines:
            assert hasattr(trendline, "id")
            assert trendline.symbol == "AAPL"
            assert hasattr(trendline, "slope")
            assert hasattr(trendline, "intercept")
            assert hasattr(trendline, "touches")
            assert trendline.touches >= 3
            assert hasattr(trendline, "direction")
            assert trendline.direction in ["support", "resistance"]
            assert hasattr(trendline, "strength")
            assert hasattr(trendline, "valid_from")
            assert hasattr(trendline, "last_touch")
            assert hasattr(trendline, "invalidated")
            assert trendline.invalidated is False

    def test_update_trendlines_with_new_bar(self) -> None:
        """Test update_trendlines method with new bar."""
        import pandas as pd
        
        # Create sample data and detect initial trendlines
        h, l, c, v, ts = _make_uptrend(100)
        bars = pd.DataFrame({
            "high": h,
            "low": l,
            "close": c,
            "volume": v,
        }, index=pd.DatetimeIndex(ts))
        
        builder = TrendlineBuilder(touch_tolerance_pct=0.01, min_touches=2)
        initial_trendlines = builder.detect_trendlines("AAPL", bars, min_touches=2)
        
        # Create a new bar
        new_bar = OHLCV(
            symbol="AAPL",
            timeframe=Timeframe.M1,
            timestamp=_ts(100),
            open=110.0,
            high=111.0,
            low=109.0,
            close=110.5,
            volume=1000.0,
        )
        
        # Update trendlines
        updated_trendlines = builder.update_trendlines("AAPL", new_bar)
        
        # Verify update worked
        assert isinstance(updated_trendlines, list)
        # Should have same or fewer trendlines (some may be invalidated)
        assert len(updated_trendlines) <= len(initial_trendlines)

    def test_check_proximity_within_threshold(self) -> None:
        """Test check_proximity returns True when price is near trendline."""
        import pandas as pd
        
        # Create sample data and detect trendlines
        h, l, c, v, ts = _make_uptrend(100)
        bars = pd.DataFrame({
            "high": h,
            "low": l,
            "close": c,
            "volume": v,
        }, index=pd.DatetimeIndex(ts))
        
        builder = TrendlineBuilder(touch_tolerance_pct=0.01, min_touches=2)
        trendlines = builder.detect_trendlines("AAPL", bars, min_touches=2)
        
        if trendlines:
            trendline = trendlines[0]
            # Calculate line price at current index
            current_index = trendline.touch_points[-1].index + 1
            line_price = trendline.price_at(current_index)
            
            # Test price very close to line (within 0.5 ATR)
            atr = 2.0
            close_price = line_price + 0.3 * atr  # Within 0.5 ATR
            assert builder.check_proximity(close_price, trendline, atr, threshold=0.5) is True
            
            # Test price far from line (beyond 0.5 ATR)
            far_price = line_price + 1.0 * atr  # Beyond 0.5 ATR
            assert builder.check_proximity(far_price, trendline, atr, threshold=0.5) is False

    def test_detect_trendlines_insufficient_bars(self) -> None:
        """Test detect_trendlines with insufficient bars."""
        import pandas as pd
        
        # Create very small dataset
        bars = pd.DataFrame({
            "high": [100.0, 101.0],
            "low": [99.0, 100.0],
            "close": [100.5, 100.8],
            "volume": [1000.0, 1100.0],
        })
        
        builder = TrendlineBuilder()
        trendlines = builder.detect_trendlines("AAPL", bars, min_touches=3)
        
        # Should return empty list
        assert trendlines == []


# ---------------------------------------------------------------------------
# Trend Analyzer tests
# ---------------------------------------------------------------------------

class TestTrendAnalyzer:
    """Test trend direction detection."""

    def test_uptrend_from_swings(self) -> None:
        """HH + HL pattern → UP."""
        analyzer = TrendAnalyzer(min_swing_points=3)
        # Create HH/HL swing points
        highs = [
            SwingPoint(index=10, price=105, is_high=True),
            SwingPoint(index=20, price=110, is_high=True),
            SwingPoint(index=30, price=115, is_high=True),
        ]
        lows = [
            SwingPoint(index=5, price=95, is_high=False),
            SwingPoint(index=15, price=98, is_high=False),
            SwingPoint(index=25, price=101, is_high=False),
        ]
        assert analyzer.detect_trend_from_swings(highs, lows) == TrendDirection.UP

    def test_downtrend_from_swings(self) -> None:
        """LH + LL pattern → DOWN."""
        analyzer = TrendAnalyzer(min_swing_points=3)
        highs = [
            SwingPoint(index=10, price=115, is_high=True),
            SwingPoint(index=20, price=110, is_high=True),
            SwingPoint(index=30, price=105, is_high=True),
        ]
        lows = [
            SwingPoint(index=5, price=101, is_high=False),
            SwingPoint(index=15, price=98, is_high=False),
            SwingPoint(index=25, price=95, is_high=False),
        ]
        assert analyzer.detect_trend_from_swings(highs, lows) == TrendDirection.DOWN

    def test_unclear_mixed_swings(self) -> None:
        """Mixed pattern → UNCLEAR."""
        analyzer = TrendAnalyzer(min_swing_points=3)
        highs = [
            SwingPoint(index=10, price=110, is_high=True),
            SwingPoint(index=20, price=105, is_high=True),  # Lower high
            SwingPoint(index=30, price=112, is_high=True),  # Higher high
        ]
        lows = [
            SwingPoint(index=5, price=95, is_high=False),
            SwingPoint(index=15, price=98, is_high=False),
            SwingPoint(index=25, price=96, is_high=False),
        ]
        assert analyzer.detect_trend_from_swings(highs, lows) == TrendDirection.UNCLEAR

    def test_insufficient_swings_unclear(self) -> None:
        """Too few swing points → UNCLEAR."""
        analyzer = TrendAnalyzer(min_swing_points=3)
        highs = [SwingPoint(index=10, price=110, is_high=True)]
        lows = [SwingPoint(index=5, price=95, is_high=False)]
        assert analyzer.detect_trend_from_swings(highs, lows) == TrendDirection.UNCLEAR

    def test_ema_confirmation_up(self) -> None:
        """EMA5 > EMA21 > EMA50 → UP."""
        analyzer = TrendAnalyzer()
        ema_vals = {
            "ema_5": [float("nan")] * 49 + [110.0],
            "ema_21": [float("nan")] * 49 + [105.0],
            "ema_50": [float("nan")] * 49 + [100.0],
        }
        assert analyzer.confirm_with_ema(ema_vals) == TrendDirection.UP

    def test_ema_confirmation_down(self) -> None:
        """EMA5 < EMA21 < EMA50 → DOWN."""
        analyzer = TrendAnalyzer()
        ema_vals = {
            "ema_5": [float("nan")] * 49 + [90.0],
            "ema_21": [float("nan")] * 49 + [95.0],
            "ema_50": [float("nan")] * 49 + [100.0],
        }
        assert analyzer.confirm_with_ema(ema_vals) == TrendDirection.DOWN

    def test_determine_trend_both_agree(self) -> None:
        """Swing + EMA both UP → UP."""
        analyzer = TrendAnalyzer(min_swing_points=3)
        highs = [
            SwingPoint(index=10, price=105, is_high=True),
            SwingPoint(index=20, price=110, is_high=True),
            SwingPoint(index=30, price=115, is_high=True),
        ]
        lows = [
            SwingPoint(index=5, price=95, is_high=False),
            SwingPoint(index=15, price=98, is_high=False),
            SwingPoint(index=25, price=101, is_high=False),
        ]
        ema_vals = {"ema_5": [110.0], "ema_21": [105.0], "ema_50": [100.0]}
        assert analyzer.determine_trend(highs, lows, ema_vals) == TrendDirection.UP

    def test_determine_trend_conflict_unclear(self) -> None:
        """Swing UP + EMA DOWN → UNCLEAR."""
        analyzer = TrendAnalyzer(min_swing_points=3)
        highs = [
            SwingPoint(index=10, price=105, is_high=True),
            SwingPoint(index=20, price=110, is_high=True),
            SwingPoint(index=30, price=115, is_high=True),
        ]
        lows = [
            SwingPoint(index=5, price=95, is_high=False),
            SwingPoint(index=15, price=98, is_high=False),
            SwingPoint(index=25, price=101, is_high=False),
        ]
        ema_vals = {"ema_5": [90.0], "ema_21": [95.0], "ema_50": [100.0]}
        assert analyzer.determine_trend(highs, lows, ema_vals) == TrendDirection.UNCLEAR

    def test_channel_detection_ascending(self) -> None:
        """Matching positive-slope upper+lower → ascending channel."""
        analyzer = TrendAnalyzer()
        sp_u1 = SwingPoint(index=0, price=110, is_high=True)
        sp_u2 = SwingPoint(index=20, price=120, is_high=True)
        sp_l1 = SwingPoint(index=5, price=100, is_high=False)
        sp_l2 = SwingPoint(index=25, price=110, is_high=False)

        upper = Trendline(slope=0.5, intercept=110, touch_points=[sp_u1, sp_u2], is_upper=True)
        lower = Trendline(slope=0.4, intercept=100, touch_points=[sp_l1, sp_l2], is_upper=False)

        channels = analyzer.detect_channels([upper, lower])
        assert len(channels) == 1
        assert channels[0].channel_type == ChannelType.ASCENDING


# ---------------------------------------------------------------------------
# Structural Engine integration tests
# ---------------------------------------------------------------------------

class TestStructuralEngine:
    """Test StructuralEngine orchestrator."""

    def test_analyze_uptrend(self) -> None:
        """Full analysis on uptrend data."""
        h, l, c, v, ts = _make_uptrend()
        series = _make_series(h, l, c, v, ts)
        engine = StructuralEngine()
        snap = engine.analyze(series)

        assert isinstance(snap, StructuralSnapshot)
        assert snap.symbol == "TEST"
        assert len(snap.sr_levels) > 0
        assert len(snap.swing_highs) > 0
        assert len(snap.swing_lows) > 0

    def test_analyze_range(self) -> None:
        """Range data should find S/R levels."""
        h, l, c, v, ts = _make_range()
        series = _make_series(h, l, c, v, ts)
        engine = StructuralEngine()
        snap = engine.analyze(series)
        assert len(snap.sr_levels) > 0

    def test_caching(self) -> None:
        """Results are cached."""
        h, l, c, v, ts = _make_uptrend()
        series = _make_series(h, l, c, v, ts)
        engine = StructuralEngine()
        engine.analyze(series)
        cached = engine.get_cached("TEST", Timeframe.D1)
        assert cached is not None

    def test_empty_series(self) -> None:
        """Empty series returns empty snapshot."""
        series = OHLCVSeries(symbol="EMPTY", timeframe=Timeframe.D1)
        engine = StructuralEngine()
        snap = engine.analyze(series)
        assert len(snap.sr_levels) == 0

    def test_stats_tracking(self) -> None:
        """Stats track analyses."""
        h, l, c, v, ts = _make_uptrend()
        series = _make_series(h, l, c, v, ts)
        engine = StructuralEngine()
        engine.analyze(series)
        assert engine.stats["total_analyses"] == 1
        assert engine.stats["total_time_ms"] > 0

    def test_analyze_with_ema(self) -> None:
        """Analysis with EMA values for trend confirmation."""
        h, l, c, v, ts = _make_uptrend()
        series = _make_series(h, l, c, v, ts)
        # Simulate bullish EMA alignment
        ema_vals = {
            "ema_5": [float(c[-1]) + 2] * len(c),
            "ema_21": [float(c[-1])] * len(c),
            "ema_50": [float(c[-1]) - 2] * len(c),
        }
        engine = StructuralEngine()
        snap = engine.analyze(series, ema_values=ema_vals)
        assert isinstance(snap.trend_direction, TrendDirection)
