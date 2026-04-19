"""Binance data feed adapter for crypto markets.

Fetches OHLCV data via the Binance REST API (python-binance).
Supports historical klines and latest candle polling.
All output normalized to AlgoForge OHLCV models.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import ClassVar

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from algoforge.core.config import get_settings
from algoforge.core.constants import Timeframe
from algoforge.core.models import OHLCV
from algoforge.data.feeds.base_feed import BaseFeed

logger = structlog.get_logger()

# Binance kline interval mapping
_INTERVAL_MAP: dict[str, str] = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
    "1wk": "1w",
    "1mo": "1M",
}

# Binance max klines per request
_MAX_KLINES = 1000

# Period to Binance limit mapping (approximate candle counts)
_PERIOD_TO_LIMIT: dict[str, int] = {
    "1d": 1,
    "5d": 5,
    "1mo": 30,
    "3mo": 90,
    "6mo": 180,
    "1y": 365,
    "2y": 730,
    "max": 1000,
}


class BinanceFeed(BaseFeed):
    """Market data feed adapter for Binance (crypto).

    Uses the Binance REST API via aiohttp for async HTTP requests.
    No API key required for public market data endpoints.
    """

    TIMEFRAME_MAP: ClassVar[dict[Timeframe, str]] = {
        Timeframe.M1: "1m",
        Timeframe.M5: "5m",
        Timeframe.M15: "15m",
        Timeframe.M30: "30m",
        Timeframe.H1: "1h",
        Timeframe.H4: "4h",
        Timeframe.D1: "1d",
        Timeframe.W1: "1w",
        Timeframe.MO1: "1M",
    }

    def __init__(self) -> None:
        self._settings = get_settings()
        self._session = None

    async def connect(self) -> None:
        """Create aiohttp session for Binance API."""
        import aiohttp

        self._session = aiohttp.ClientSession()
        logger.info("binance_feed.connected")

    async def disconnect(self) -> None:
        """Close aiohttp session."""
        if self._session:
            await self._session.close()
            self._session = None
        logger.info("binance_feed.disconnected")

    async def health_check(self) -> bool:
        """Ping Binance API to verify connectivity."""
        if not self._session:
            return False
        try:
            url = f"{self._settings.binance.base_url}/api/v3/ping"
            async with self._session.get(url) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error("binance_feed.health_check_failed", error=str(e))
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
    async def fetch_historical(
        self,
        symbol: str,
        timeframe: Timeframe | None = None,
        period: str | None = None,
    ) -> list[OHLCV]:
        """Fetch historical klines from Binance REST API.

        Args:
            symbol: Binance symbol (e.g., "BTCUSDT").
            timeframe: Target timeframe. Defaults to config base_timeframe.
            period: History period (e.g., "1mo"). Defaults to config.

        Returns:
            List of validated OHLCV candles sorted by timestamp ascending.
        """
        if timeframe is None:
            timeframe = self._settings.data_feed.base_timeframe
        if period is None:
            period = self._settings.data_feed.history_period

        interval = self.TIMEFRAME_MAP[timeframe]
        limit = min(_PERIOD_TO_LIMIT.get(period, 30), _MAX_KLINES)

        logger.info(
            "binance_feed.fetch_historical",
            symbol=symbol,
            interval=interval,
            limit=limit,
        )

        if not self._session:
            await self.connect()

        url = f"{self._settings.binance.base_url}/api/v3/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}

        async with self._session.get(url, params=params) as resp:
            resp.raise_for_status()
            data = await resp.json()

        return self._normalize_klines(data, symbol, timeframe)

    async def fetch_latest(
        self,
        symbol: str,
        timeframe: Timeframe | None = None,
    ) -> OHLCV | None:
        """Fetch the most recent kline from Binance."""
        if timeframe is None:
            timeframe = self._settings.data_feed.base_timeframe

        interval = self.TIMEFRAME_MAP[timeframe]

        if not self._session:
            await self.connect()

        url = f"{self._settings.binance.base_url}/api/v3/klines"
        params = {"symbol": symbol, "interval": interval, "limit": 1}

        try:
            async with self._session.get(url, params=params) as resp:
                resp.raise_for_status()
                data = await resp.json()

            candles = self._normalize_klines(data, symbol, timeframe)
            return candles[-1] if candles else None
        except Exception as e:
            logger.error("binance_feed.fetch_latest_error", symbol=symbol, error=str(e))
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_klines(
        data: list[list],
        symbol: str,
        timeframe: Timeframe,
    ) -> list[OHLCV]:
        """Convert Binance kline response to OHLCV models.

        Binance kline format: [open_time, open, high, low, close, volume,
        close_time, quote_volume, trades, taker_buy_base, taker_buy_quote, ignore]
        """
        candles: list[OHLCV] = []
        for kline in data:
            # kline[0] = open time in milliseconds
            timestamp = datetime.fromtimestamp(kline[0] / 1000, tz=timezone.utc)
            candles.append(
                OHLCV(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=timestamp,
                    open=float(kline[1]),
                    high=float(kline[2]),
                    low=float(kline[3]),
                    close=float(kline[4]),
                    volume=float(kline[5]),
                )
            )
        return candles
