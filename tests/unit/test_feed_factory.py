"""Tests for feed factory and feed adapter instantiation."""

import pytest

from algoforge.data.feeds.base_feed import BaseFeed
from algoforge.data.feeds.feed_factory import create_feed


class TestFeedFactory:
    """Feed factory returns correct adapter for each provider."""

    def test_create_yfinance_feed(self) -> None:
        feed = create_feed("yfinance")
        assert isinstance(feed, BaseFeed)
        assert type(feed).__name__ == "YFinanceFeed"

    def test_create_binance_feed(self) -> None:
        feed = create_feed("binance")
        assert isinstance(feed, BaseFeed)
        assert type(feed).__name__ == "BinanceFeed"

    def test_create_alphavantage_feed(self) -> None:
        feed = create_feed("alphavantage")
        assert isinstance(feed, BaseFeed)
        assert type(feed).__name__ == "AlphaVantageFeed"

    def test_invalid_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown feed provider"):
            create_feed("nonexistent")

    def test_default_uses_config(self) -> None:
        """Default provider from config is 'yfinance'."""
        feed = create_feed()
        assert type(feed).__name__ == "YFinanceFeed"


class TestBaseFeedInterface:
    """All feeds implement BaseFeed ABC methods."""

    @pytest.mark.parametrize("provider", ["yfinance", "binance", "alphavantage"])
    def test_feed_has_required_methods(self, provider: str) -> None:
        feed = create_feed(provider)
        assert hasattr(feed, "connect")
        assert hasattr(feed, "disconnect")
        assert hasattr(feed, "health_check")
        assert hasattr(feed, "fetch_historical")
        assert hasattr(feed, "fetch_latest")
