"""Tests for multi-timeframe resampler."""

from datetime import datetime, timezone

import pytest

from algoforge.core.constants import Timeframe
from algoforge.core.models import OHLCV
from algoforge.data.processors.resampler import Resampler


def _make_1m_candles(count: int = 10, base_minute: int = 0) -> list[OHLCV]:
    """Create N one-minute candles starting at base_minute."""
    candles = []
    for i in range(count):
        candles.append(
            OHLCV(
                symbol="TEST",
                timeframe=Timeframe.M1,
                timestamp=datetime(
                    2024, 1, 15, 9, base_minute + i, tzinfo=timezone.utc
                ),
                open=100.0 + i,
                high=102.0 + i,
                low=99.0 + i,
                close=101.0 + i,
                volume=1000.0 * (i + 1),
            )
        )
    return candles


class TestResampler:
    """Test OHLCV resampling logic."""

    def test_resample_1m_to_5m(self) -> None:
        """5 one-minute candles become 1 five-minute candle."""
        resampler = Resampler()
        candles = _make_1m_candles(5)

        result = resampler.resample(candles, Timeframe.M5)

        assert len(result) >= 1
        # Check the first 5-min candle
        c = result[0]
        assert c.timeframe == Timeframe.M5
        assert c.symbol == "TEST"

    def test_resample_preserves_ohlcv_rules(self) -> None:
        """OHLCV aggregation: Open=first, High=max, Low=min, Close=last, Volume=sum."""
        resampler = Resampler()
        candles = _make_1m_candles(5)

        result = resampler.resample(candles, Timeframe.M5)
        assert len(result) >= 1

        c = result[0]
        # Open should be from the first candle
        assert c.open == candles[0].open
        # High should be the max of all highs
        assert c.high == max(cndl.high for cndl in candles[:5])
        # Low should be the min of all lows
        assert c.low == min(cndl.low for cndl in candles[:5])
        # Close should be from the last candle
        assert c.close == candles[4].close
        # Volume should be sum
        assert c.volume == sum(cndl.volume for cndl in candles[:5])

    def test_resample_lower_timeframe_raises(self) -> None:
        """Resampling to a lower timeframe raises ValueError."""
        resampler = Resampler()
        candles = _make_1m_candles(5)

        # Change candles to 5m timeframe
        for c in candles:
            c.timeframe = Timeframe.M5

        with pytest.raises(ValueError, match="target must be a higher timeframe"):
            resampler.resample(candles, Timeframe.M1)

    def test_resample_same_timeframe_raises(self) -> None:
        """Resampling to the same timeframe raises ValueError."""
        resampler = Resampler()
        candles = _make_1m_candles(5)

        with pytest.raises(ValueError, match="target must be a higher timeframe"):
            resampler.resample(candles, Timeframe.M1)

    def test_resample_empty_input(self) -> None:
        """Empty candle list returns empty list."""
        resampler = Resampler()
        result = resampler.resample([], Timeframe.M5)
        assert result == []

    def test_resample_to_all(self) -> None:
        """Resample to multiple target timeframes at once."""
        resampler = Resampler()
        candles = _make_1m_candles(30)

        targets = [Timeframe.M5, Timeframe.M15]
        results = resampler.resample_to_all(candles, targets)

        assert Timeframe.M5 in results
        assert Timeframe.M15 in results
        assert len(results[Timeframe.M5]) > 0
        assert len(results[Timeframe.M15]) > 0

    def test_resample_to_all_skips_invalid(self) -> None:
        """resample_to_all skips invalid timeframes without crashing."""
        resampler = Resampler()
        candles = _make_1m_candles(5)

        # M1 candles can resample to M5 but not back to M1
        results = resampler.resample_to_all(candles, [Timeframe.M5, Timeframe.M1])

        assert Timeframe.M5 in results
        assert Timeframe.M1 not in results  # Skipped — can't go lower

    def test_resample_symbol_preserved(self) -> None:
        """Resampled candles retain the original symbol."""
        resampler = Resampler()
        candles = _make_1m_candles(5)

        result = resampler.resample(candles, Timeframe.M5)
        for c in result:
            assert c.symbol == "TEST"
