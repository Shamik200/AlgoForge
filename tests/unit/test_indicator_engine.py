"""Tests for IndicatorEngine orchestrator + integration tests."""

import time
from datetime import datetime, timezone

import numpy as np
import pytest

from algoforge.core.constants import Timeframe
from algoforge.core.models import OHLCV, OHLCVSeries
from algoforge.technical.engine import IndicatorEngine, IndicatorSnapshot


def _make_series(symbol: str, timeframe: Timeframe, num_candles: int = 200) -> OHLCVSeries:
    """Generate a realistic OHLCV series for testing."""
    np.random.seed(42)
    base = 100.0
    series = OHLCVSeries(symbol=symbol, timeframe=timeframe)

    for i in range(num_candles):
        change = np.random.randn() * 0.5
        close = base + change
        high = max(base, close) + abs(np.random.randn()) * 0.3
        low = min(base, close) - abs(np.random.randn()) * 0.3
        volume = float(np.random.randint(50000, 200000))

        candle = OHLCV(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            open=round(base, 4),
            high=round(high, 4),
            low=round(low, 4),
            close=round(close, 4),
            volume=volume,
        )
        series.append(candle)
        base = close

    return series


class TestIndicatorSnapshot:
    """Test IndicatorSnapshot container."""

    def test_empty_snapshot(self) -> None:
        snap = IndicatorSnapshot()
        assert snap.indicator_names == []
        assert snap.latest_values() == {}

    def test_set_and_get(self) -> None:
        from algoforge.technical.indicator_base import IndicatorResult

        snap = IndicatorSnapshot()
        result = IndicatorResult(name="test", values={"v": [1.0, 2.0]})
        snap.set("test", result)
        assert snap.get("test") is result
        assert "test" in snap.indicator_names


class TestIndicatorEngine:
    """Test IndicatorEngine orchestrator."""

    def test_engine_has_14_indicators(self) -> None:
        """Engine registers all 14 indicators."""
        engine = IndicatorEngine()
        assert engine.indicator_count == 14

    def test_engine_computes_all_indicators(self) -> None:
        """All 14 indicators produce results from sufficient data."""
        engine = IndicatorEngine()
        series = _make_series("AAPL", Timeframe.D1, 200)
        snapshot = engine.compute(series)

        # All 14 should succeed with 200 candles
        assert len(snapshot.indicator_names) == 14

    def test_engine_caching(self) -> None:
        """Results are cached by symbol/timeframe."""
        engine = IndicatorEngine()
        series = _make_series("AAPL", Timeframe.D1, 200)
        engine.compute(series)

        cached = engine.get_cached("AAPL", Timeframe.D1)
        assert cached is not None
        assert len(cached.indicator_names) == 14

    def test_engine_cache_miss(self) -> None:
        """Cache miss returns None."""
        engine = IndicatorEngine()
        assert engine.get_cached("MISSING", Timeframe.D1) is None

    def test_engine_clear_cache(self) -> None:
        """Clear cache removes all entries."""
        engine = IndicatorEngine()
        series = _make_series("AAPL", Timeframe.D1, 200)
        engine.compute(series)
        assert engine.cache_size == 1

        engine.clear_cache()
        assert engine.cache_size == 0

    def test_engine_clear_cache_by_symbol(self) -> None:
        """Clear cache for specific symbol."""
        engine = IndicatorEngine()
        engine.compute(_make_series("AAPL", Timeframe.D1, 200))
        engine.compute(_make_series("GOOG", Timeframe.D1, 200))
        assert engine.cache_size == 2

        engine.clear_cache("AAPL")
        assert engine.cache_size == 1
        assert engine.get_cached("AAPL", Timeframe.D1) is None
        assert engine.get_cached("GOOG", Timeframe.D1) is not None

    def test_engine_handles_insufficient_data(self) -> None:
        """Indicators needing more data are silently skipped."""
        engine = IndicatorEngine()
        series = _make_series("AAPL", Timeframe.D1, 10)  # Only 10 candles
        snapshot = engine.compute(series)

        # Some indicators (EMA-200, Ichimoku-52, etc.) need more data
        assert len(snapshot.indicator_names) < 14
        # But short-period ones should still compute
        assert len(snapshot.indicator_names) > 0

    def test_engine_empty_series(self) -> None:
        """Empty series produces empty snapshot."""
        engine = IndicatorEngine()
        series = OHLCVSeries(symbol="AAPL", timeframe=Timeframe.D1)
        snapshot = engine.compute(series)
        assert len(snapshot.indicator_names) == 0

    def test_engine_stats(self) -> None:
        """Stats track computations."""
        engine = IndicatorEngine()
        engine.compute(_make_series("AAPL", Timeframe.D1, 200))
        stats = engine.stats
        assert stats["total_computations"] == 1
        assert stats["total_time_ms"] > 0

    def test_engine_custom_params(self) -> None:
        """Custom indicator parameters are respected."""
        engine = IndicatorEngine(
            ema_periods=[10, 20],
            rsi_period=7,
            atr_period=10,
        )
        series = _make_series("AAPL", Timeframe.D1, 200)
        snapshot = engine.compute(series)

        ema_result = snapshot.get("ema")
        assert ema_result is not None
        assert "ema_10" in ema_result.values
        assert "ema_20" in ema_result.values

    def test_engine_compute_batch(self) -> None:
        """Batch compute processes multiple series."""
        engine = IndicatorEngine(ema_periods=[5, 9])
        series_list = [
            _make_series("AAPL", Timeframe.D1, 200),
            _make_series("GOOG", Timeframe.H1, 200),
        ]
        snapshots = engine.compute_batch(series_list)
        assert len(snapshots) == 2
        assert all(len(s.indicator_names) > 0 for s in snapshots)

    def test_engine_latest_values(self) -> None:
        """Snapshot provides latest values from all indicators."""
        engine = IndicatorEngine()
        series = _make_series("AAPL", Timeframe.D1, 200)
        snapshot = engine.compute(series)
        latest = snapshot.latest_values()

        assert "ema" in latest
        assert "rsi" in latest
        assert "macd" in latest
        assert isinstance(latest["rsi"]["rsi"], float)


class TestIndicatorPerformance:
    """Performance tests — ensure engine meets the 1-second target."""

    def test_single_instrument_speed(self) -> None:
        """Single 200-candle computation under 100ms."""
        engine = IndicatorEngine()
        series = _make_series("AAPL", Timeframe.D1, 200)

        start = time.perf_counter()
        engine.compute(series)
        elapsed = (time.perf_counter() - start) * 1000

        assert elapsed < 100, f"Single compute took {elapsed:.1f}ms, expected < 100ms"

    def test_batch_6_timeframes_speed(self) -> None:
        """6 timeframes for 1 instrument under 500ms."""
        engine = IndicatorEngine()
        timeframes = [
            Timeframe.M1, Timeframe.M5, Timeframe.M15,
            Timeframe.H1, Timeframe.H4, Timeframe.D1,
        ]
        series_list = [_make_series("AAPL", tf, 200) for tf in timeframes]

        start = time.perf_counter()
        engine.compute_batch(series_list)
        elapsed = (time.perf_counter() - start) * 1000

        assert elapsed < 500, f"6-timeframe batch took {elapsed:.1f}ms, expected < 500ms"
