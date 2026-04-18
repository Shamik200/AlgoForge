"""Tests for yfinance data feed adapter."""

from datetime import datetime, timezone

import pandas as pd
import pytest

from algoforge.core.constants import Timeframe
from algoforge.core.models import OHLCV
from algoforge.data.feeds.yfinance_feed import YFinanceFeed


class TestYFinanceFeed:
    """Test yfinance feed adapter."""

    def test_timeframe_mapping_complete(self) -> None:
        """All Timeframe enum values have yfinance mappings."""
        for tf in Timeframe:
            assert tf in YFinanceFeed.TIMEFRAME_MAP, f"Missing mapping for {tf.value}"

    def test_normalize_dataframe(self) -> None:
        """yfinance DataFrame converts to list[OHLCV] correctly."""
        # Create a mock yfinance-style DataFrame
        dates = pd.date_range("2024-01-15 09:30", periods=3, freq="1min", tz="UTC")
        df = pd.DataFrame(
            {
                "Open": [100.0, 101.0, 102.0],
                "High": [101.0, 102.0, 103.0],
                "Low": [99.0, 100.0, 101.0],
                "Close": [100.5, 101.5, 102.5],
                "Volume": [1000, 2000, 3000],
            },
            index=dates,
        )

        candles = YFinanceFeed._normalize_dataframe(df, "AAPL", Timeframe.M1)

        assert len(candles) == 3
        assert candles[0].symbol == "AAPL"
        assert candles[0].timeframe == Timeframe.M1
        assert candles[0].open == 100.0
        assert candles[0].close == 100.5
        assert candles[2].volume == 3000.0

    def test_normalize_skips_nan_rows(self) -> None:
        """Rows with NaN values are skipped during normalization."""
        dates = pd.date_range("2024-01-15 09:30", periods=3, freq="1min", tz="UTC")
        df = pd.DataFrame(
            {
                "Open": [100.0, float("nan"), 102.0],
                "High": [101.0, float("nan"), 103.0],
                "Low": [99.0, float("nan"), 101.0],
                "Close": [100.5, float("nan"), 102.5],
                "Volume": [1000, float("nan"), 3000],
            },
            index=dates,
        )

        candles = YFinanceFeed._normalize_dataframe(df, "AAPL", Timeframe.M1)
        assert len(candles) == 2  # Middle row skipped

    def test_empty_response_handling(self) -> None:
        """Empty DataFrame returns empty list."""
        df = pd.DataFrame()
        candles = YFinanceFeed._normalize_dataframe(df, "AAPL", Timeframe.M1)
        assert candles == []

    def test_clamp_period(self) -> None:
        """Period clamping respects yfinance limits."""
        assert YFinanceFeed._clamp_period("1y", "60d") == "60d"
        assert YFinanceFeed._clamp_period("1mo", "60d") == "1mo"
        assert YFinanceFeed._clamp_period("max", "60d") == "60d"

    def test_normalize_multiindex_columns(self) -> None:
        """Handle MultiIndex columns from single-ticker yfinance download."""
        dates = pd.date_range("2024-01-15 09:30", periods=2, freq="1min", tz="UTC")
        arrays = [
            ["Open", "High", "Low", "Close", "Volume"],
            ["AAPL", "AAPL", "AAPL", "AAPL", "AAPL"],
        ]
        tuples = list(zip(*arrays))
        index = pd.MultiIndex.from_tuples(tuples)
        df = pd.DataFrame(
            [[100.0, 101.0, 99.0, 100.5, 1000], [101.0, 102.0, 100.0, 101.5, 2000]],
            columns=index,
            index=dates,
        )

        candles = YFinanceFeed._normalize_dataframe(df, "AAPL", Timeframe.M1)
        assert len(candles) == 2
