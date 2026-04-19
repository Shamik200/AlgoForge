"""Alpha Vantage data feed adapter for forex markets.

Fetches OHLCV data via the Alpha Vantage REST API using aiohttp.
Free tier: 25 requests/minute with API key.
Note: Forex data from Alpha Vantage does not include volume — defaults to 0.0.
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

# Alpha Vantage function mapping by timeframe
_AV_FUNCTIONS: dict[str, tuple[str, str]] = {
    # timeframe_value: (function_name, interval_param_or_None)
    "1m": ("FX_INTRADAY", "1min"),
    "5m": ("FX_INTRADAY", "5min"),
    "15m": ("FX_INTRADAY", "15min"),
    "30m": ("FX_INTRADAY", "30min"),
    "1h": ("FX_INTRADAY", "60min"),
    "4h": ("FX_INTRADAY", "60min"),  # Fetch 1h, resample to 4h
    "1d": ("FX_DAILY", ""),
    "1wk": ("FX_WEEKLY", ""),
    "1mo": ("FX_MONTHLY", ""),
}


class AlphaVantageFeed(BaseFeed):
    """Market data feed adapter for Alpha Vantage (forex).

    Converts forex pair format: config "EURUSD" → API "EUR"/"USD".
    Volume is always 0.0 (forex has no centralized volume data).
    """

    TIMEFRAME_MAP: ClassVar[dict[Timeframe, str]] = {
        Timeframe.M1: "1min",
        Timeframe.M5: "5min",
        Timeframe.M15: "15min",
        Timeframe.M30: "30min",
        Timeframe.H1: "60min",
        Timeframe.H4: "60min",
        Timeframe.D1: "daily",
        Timeframe.W1: "weekly",
        Timeframe.MO1: "monthly",
    }

    def __init__(self) -> None:
        self._settings = get_settings()
        self._session = None
        self._api_key = self._settings.alphavantage.api_key

    async def connect(self) -> None:
        """Create aiohttp session and validate API key."""
        import aiohttp

        if not self._api_key:
            logger.warning("alphavantage_feed.no_api_key", msg="Set ALGOFORGE_ALPHAVANTAGE__API_KEY")
        self._session = aiohttp.ClientSession()
        logger.info("alphavantage_feed.connected")

    async def disconnect(self) -> None:
        """Close aiohttp session."""
        if self._session:
            await self._session.close()
            self._session = None
        logger.info("alphavantage_feed.disconnected")

    async def health_check(self) -> bool:
        """Verify Alpha Vantage API is reachable."""
        if not self._session or not self._api_key:
            return False
        try:
            url = self._settings.alphavantage.base_url
            params = {"function": "CURRENCY_EXCHANGE_RATE", "from_currency": "EUR",
                       "to_currency": "USD", "apikey": self._api_key}
            async with self._session.get(url, params=params) as resp:
                data = await resp.json()
                return "Realtime Currency Exchange Rate" in data
        except Exception as e:
            logger.error("alphavantage_feed.health_check_failed", error=str(e))
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, max=30))
    async def fetch_historical(
        self,
        symbol: str,
        timeframe: Timeframe | None = None,
        period: str | None = None,
    ) -> list[OHLCV]:
        """Fetch historical forex data from Alpha Vantage.

        Args:
            symbol: Forex pair (e.g., "EURUSD" → split to EUR/USD).
            timeframe: Target timeframe. Defaults to config base_timeframe.
            period: Ignored — Alpha Vantage returns full available history.
        """
        if timeframe is None:
            timeframe = self._settings.data_feed.base_timeframe

        from_currency, to_currency = self._split_pair(symbol)
        tf_value = timeframe.value
        av_func, av_interval = _AV_FUNCTIONS.get(tf_value, ("FX_DAILY", ""))

        logger.info(
            "alphavantage_feed.fetch_historical",
            symbol=symbol,
            function=av_func,
            interval=av_interval,
        )

        if not self._session:
            await self.connect()

        params: dict[str, str] = {
            "function": av_func,
            "from_symbol": from_currency,
            "to_symbol": to_currency,
            "apikey": self._api_key,
            "outputsize": "compact",
        }
        if av_interval:
            params["interval"] = av_interval

        url = self._settings.alphavantage.base_url
        async with self._session.get(url, params=params) as resp:
            resp.raise_for_status()
            data = await resp.json()

        return self._normalize_response(data, symbol, timeframe)

    async def fetch_latest(
        self,
        symbol: str,
        timeframe: Timeframe | None = None,
    ) -> OHLCV | None:
        """Fetch the most recent forex candle."""
        try:
            candles = await self.fetch_historical(symbol, timeframe)
            return candles[-1] if candles else None
        except Exception as e:
            logger.error("alphavantage_feed.fetch_latest_error", symbol=symbol, error=str(e))
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _split_pair(symbol: str) -> tuple[str, str]:
        """Split forex pair: 'EURUSD' → ('EUR', 'USD').

        Handles both 'EURUSD' and 'EUR/USD' formats.
        """
        symbol = symbol.replace("/", "").replace("=X", "").upper()
        if len(symbol) == 6:
            return symbol[:3], symbol[3:]
        return symbol, "USD"

    @staticmethod
    def _normalize_response(
        data: dict,
        symbol: str,
        timeframe: Timeframe,
    ) -> list[OHLCV]:
        """Convert Alpha Vantage JSON response to OHLCV models.

        Alpha Vantage returns time series as:
        {"Time Series (...)": {"2024-01-01": {"1. open": "1.1050", ...}}}
        """
        # Find the time series key (varies by function)
        ts_key = None
        for key in data:
            if "Time Series" in key or "Time Series FX" in key:
                ts_key = key
                break

        if ts_key is None:
            logger.warning("alphavantage_feed.no_time_series", keys=list(data.keys()))
            return []

        time_series = data[ts_key]
        candles: list[OHLCV] = []

        for date_str, values in time_series.items():
            try:
                # Parse date — formats: "2024-01-01" or "2024-01-01 09:30:00"
                if " " in date_str:
                    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                else:
                    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)

                candles.append(
                    OHLCV(
                        symbol=symbol,
                        timeframe=timeframe,
                        timestamp=dt,
                        open=float(values.get("1. open", 0)),
                        high=float(values.get("2. high", 0)),
                        low=float(values.get("3. low", 0)),
                        close=float(values.get("4. close", 0)),
                        volume=0.0,  # Forex has no centralized volume
                    )
                )
            except (ValueError, KeyError) as e:
                logger.warning("alphavantage_feed.parse_error", date=date_str, error=str(e))
                continue

        # Sort ascending by timestamp
        candles.sort(key=lambda c: c.timestamp)
        return candles
