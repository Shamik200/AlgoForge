"""Tests for Alpha Vantage feed adapter."""

from datetime import datetime, timezone

from algoforge.core.constants import Timeframe
from algoforge.data.feeds.alphavantage_feed import AlphaVantageFeed


class TestAlphaVantageFeed:
    """Alpha Vantage feed adapter tests — no live API calls."""

    def test_instantiation(self) -> None:
        feed = AlphaVantageFeed()
        assert feed._session is None

    def test_timeframe_map_completeness(self) -> None:
        """All 9 Timeframe enum values must have an AV mapping."""
        for tf in Timeframe:
            assert tf in AlphaVantageFeed.TIMEFRAME_MAP, f"Missing mapping for {tf}"

    def test_split_pair_standard(self) -> None:
        """EURUSD → ('EUR', 'USD')."""
        from_curr, to_curr = AlphaVantageFeed._split_pair("EURUSD")
        assert from_curr == "EUR"
        assert to_curr == "USD"

    def test_split_pair_with_slash(self) -> None:
        """EUR/USD → ('EUR', 'USD')."""
        from_curr, to_curr = AlphaVantageFeed._split_pair("EUR/USD")
        assert from_curr == "EUR"
        assert to_curr == "USD"

    def test_split_pair_with_suffix(self) -> None:
        """EURUSD=X → ('EUR', 'USD')."""
        from_curr, to_curr = AlphaVantageFeed._split_pair("EURUSD=X")
        assert from_curr == "EUR"
        assert to_curr == "USD"

    def test_normalize_response_daily(self) -> None:
        """Test Alpha Vantage daily response normalization."""
        data = {
            "Meta Data": {"1. Information": "Forex Daily"},
            "Time Series FX (Daily)": {
                "2024-01-15": {
                    "1. open": "1.0950",
                    "2. high": "1.0980",
                    "3. low": "1.0920",
                    "4. close": "1.0960",
                },
                "2024-01-14": {
                    "1. open": "1.0900",
                    "2. high": "1.0960",
                    "3. low": "1.0880",
                    "4. close": "1.0950",
                },
            },
        }
        candles = AlphaVantageFeed._normalize_response(data, "EURUSD", Timeframe.D1)
        assert len(candles) == 2
        # Should be sorted ascending
        assert candles[0].timestamp < candles[1].timestamp
        assert candles[0].symbol == "EURUSD"
        assert candles[0].volume == 0.0  # Forex has no volume
        assert candles[1].close == 1.0960

    def test_normalize_empty_response(self) -> None:
        """Missing time series key returns empty list."""
        candles = AlphaVantageFeed._normalize_response(
            {"Error": "API limit reached"}, "EURUSD", Timeframe.D1
        )
        assert candles == []
