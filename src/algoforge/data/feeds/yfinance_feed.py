"""YFinance data feed adapter.

Fetches OHLCV data via the yfinance library. Supports historical backfill
and latest-candle polling. All output normalized to AlgoForge OHLCV models.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import ClassVar

import pandas as pd
import structlog
import yfinance as yf
from tenacity import retry, stop_after_attempt, wait_exponential

from algoforge.core.config import get_settings
from algoforge.core.constants import Timeframe
from algoforge.core.models import OHLCV
from algoforge.data.feeds.base_feed import BaseFeed

logger = structlog.get_logger()

# yfinance period ordering for clamping
_PERIOD_ORDER = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"]


class YFinanceFeed(BaseFeed):
    """Market data feed adapter for yfinance.

    Maps AlgoForge Timeframe enums to yfinance interval strings and normalizes
    the returned DataFrames into validated OHLCV models.
    """

    # Map every Timeframe enum to the yfinance interval string
    TIMEFRAME_MAP: ClassVar[dict[Timeframe, str]] = {
        Timeframe.M1: "1m",
        Timeframe.M5: "5m",
        Timeframe.M15: "15m",
        Timeframe.M30: "30m",
        Timeframe.H1: "1h",
        Timeframe.H4: "1h",  # yfinance has no 4h; we resample from 1h
        Timeframe.D1: "1d",
        Timeframe.W1: "1wk",
        Timeframe.MO1: "1mo",
    }

    # yfinance maximum history periods per interval
    _MAX_PERIOD: ClassVar[dict[str, str]] = {
        "1m": "5d",
        "5m": "60d",
        "15m": "60d",
        "30m": "60d",
        "1h": "730d",
        "1d": "max",
        "1wk": "max",
        "1mo": "max",
    }

    def __init__(self) -> None:
        self._settings = get_settings()

    async def connect(self) -> None:
        """No persistent connection needed for yfinance."""
        logger.info("yfinance_feed.connected")

    async def disconnect(self) -> None:
        """No cleanup needed for yfinance."""
        logger.info("yfinance_feed.disconnected")

    async def health_check(self) -> bool:
        """Verify yfinance is working by fetching a tiny sample."""
        try:
            ticker = yf.Ticker("AAPL")
            hist = ticker.history(period="1d", interval="1d")
            return not hist.empty
        except Exception as e:
            logger.error("yfinance_feed.health_check_failed", error=str(e))
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
    async def fetch_historical(
        self,
        symbol: str,
        timeframe: Timeframe | None = None,
        period: str | None = None,
    ) -> list[OHLCV]:
        """Fetch historical OHLCV data for a symbol.

        Args:
            symbol: Ticker symbol (e.g., "AAPL", "BTC-USD").
            timeframe: Target timeframe. Defaults to config base_timeframe.
            period: History period (e.g., "1mo", "1y"). Defaults to config.

        Returns:
            List of validated OHLCV candles sorted by timestamp ascending.
        """
        if timeframe is None:
            timeframe = self._settings.data_feed.base_timeframe
        if period is None:
            period = self._settings.data_feed.history_period

        yf_interval = self.TIMEFRAME_MAP[timeframe]
        max_period = self._MAX_PERIOD.get(yf_interval, "max")
        clamped_period = self._clamp_period(period, max_period)

        logger.info(
            "yfinance_feed.fetch_historical",
            symbol=symbol,
            interval=yf_interval,
            period=clamped_period,
        )

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=clamped_period, interval=yf_interval)
            return self._normalize_dataframe(df, symbol, timeframe)
        except Exception as e:
            logger.error(
                "yfinance_feed.fetch_historical_error",
                symbol=symbol,
                error=str(e),
            )
            raise

    async def fetch_latest(
        self,
        symbol: str,
        timeframe: Timeframe | None = None,
    ) -> OHLCV | None:
        """Fetch the most recent candle for a symbol.

        Returns None if no data is available.
        """
        if timeframe is None:
            timeframe = self._settings.data_feed.base_timeframe

        yf_interval = self.TIMEFRAME_MAP[timeframe]

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="1d", interval=yf_interval)
            candles = self._normalize_dataframe(df, symbol, timeframe)
            return candles[-1] if candles else None
        except Exception as e:
            logger.error(
                "yfinance_feed.fetch_latest_error",
                symbol=symbol,
                error=str(e),
            )
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_dataframe(
        df: pd.DataFrame,
        symbol: str,
        timeframe: Timeframe,
    ) -> list[OHLCV]:
        """Convert a yfinance DataFrame to a list of validated OHLCV models.

        Handles:
        - Empty DataFrames
        - MultiIndex columns (single-ticker yfinance quirk)
        - NaN rows (skipped)
        """
        if df.empty:
            return []

        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        candles: list[OHLCV] = []
        for ts, row in df.iterrows():
            # Skip rows with NaN
            if any(
                isinstance(v, float) and math.isnan(v)
                for v in [row["Open"], row["High"], row["Low"], row["Close"], row["Volume"]]
            ):
                continue

            # Ensure timestamp is timezone-aware UTC
            if isinstance(ts, pd.Timestamp):
                if ts.tzinfo is None:
                    ts = ts.tz_localize("UTC")
                dt = ts.to_pydatetime()
            else:
                dt = datetime.fromtimestamp(ts.timestamp(), tz=timezone.utc)

            candles.append(
                OHLCV(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=dt,
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(row["Volume"]),
                )
            )

        return candles

    @staticmethod
    def _clamp_period(requested: str, maximum: str) -> str:
        """Clamp a requested period to the maximum allowed by yfinance.

        If the requested period exceeds the maximum, return the maximum.
        """
        if requested not in _PERIOD_ORDER or maximum not in _PERIOD_ORDER:
            return requested

        req_idx = _PERIOD_ORDER.index(requested)
        max_idx = _PERIOD_ORDER.index(maximum)

        return requested if req_idx <= max_idx else maximum
