"""Tests for Binance feed adapter."""

from datetime import datetime, timezone

from algoforge.core.constants import Timeframe
from algoforge.data.feeds.binance_feed import BinanceFeed


class TestBinanceFeed:
    """Binance feed adapter tests — no live API calls."""

    def test_instantiation(self) -> None:
        feed = BinanceFeed()
        assert feed._session is None

    def test_timeframe_map_completeness(self) -> None:
        """All 9 Timeframe enum values must have a Binance mapping."""
        for tf in Timeframe:
            assert tf in BinanceFeed.TIMEFRAME_MAP, f"Missing mapping for {tf}"

    def test_timeframe_map_values(self) -> None:
        assert BinanceFeed.TIMEFRAME_MAP[Timeframe.M1] == "1m"
        assert BinanceFeed.TIMEFRAME_MAP[Timeframe.H4] == "4h"
        assert BinanceFeed.TIMEFRAME_MAP[Timeframe.D1] == "1d"
        assert BinanceFeed.TIMEFRAME_MAP[Timeframe.W1] == "1w"
        assert BinanceFeed.TIMEFRAME_MAP[Timeframe.MO1] == "1M"

    def test_normalize_klines(self) -> None:
        """Test Binance kline response normalization."""
        # Binance kline format: [open_time_ms, open, high, low, close, volume, ...]
        raw_klines = [
            [1704067200000, "42000.50", "42500.00", "41800.00", "42300.00", "150.5",
             1704067259999, "6000000", 500, "75.25", "3000000", "0"],
            [1704067260000, "42300.00", "42600.00", "42200.00", "42550.00", "200.0",
             1704067319999, "8000000", 600, "100.0", "4000000", "0"],
        ]
        candles = BinanceFeed._normalize_klines(raw_klines, "BTCUSDT", Timeframe.M1)
        assert len(candles) == 2
        assert candles[0].symbol == "BTCUSDT"
        assert candles[0].timeframe == Timeframe.M1
        assert candles[0].open == 42000.50
        assert candles[0].high == 42500.00
        assert candles[0].volume == 150.5
        # Timestamps should be UTC
        assert candles[0].timestamp.tzinfo is not None

    def test_normalize_empty_klines(self) -> None:
        candles = BinanceFeed._normalize_klines([], "BTCUSDT", Timeframe.M1)
        assert candles == []
