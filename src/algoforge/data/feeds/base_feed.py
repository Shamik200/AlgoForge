"""Abstract base class for all market data feed adapters.

All feed adapters must implement these methods to be usable
by the DataPipeline. The interface is intentionally minimal —
connect, disconnect, health check, fetch historical, fetch latest.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from algoforge.core.constants import Timeframe
from algoforge.core.models import OHLCV


class BaseFeed(ABC):
    """Abstract base for market data feed adapters.

    Subclasses:
        - YFinanceFeed (stocks, general purpose)
        - BinanceFeed (crypto, real-time WebSocket)
        - AlphaVantageFeed (forex, REST API)
    """

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the data source."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Clean up connection resources."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Verify the data source is reachable and working."""

    @abstractmethod
    async def fetch_historical(
        self,
        symbol: str,
        timeframe: Timeframe | None = None,
        period: str | None = None,
    ) -> list[OHLCV]:
        """Fetch historical OHLCV data for a symbol.

        Args:
            symbol: Ticker symbol.
            timeframe: Target timeframe. Defaults to config base_timeframe.
            period: History period (e.g., "1mo"). Defaults to config.

        Returns:
            List of validated OHLCV candles sorted by timestamp ascending.
        """

    @abstractmethod
    async def fetch_latest(
        self,
        symbol: str,
        timeframe: Timeframe | None = None,
    ) -> OHLCV | None:
        """Fetch the most recent candle for a symbol.

        Returns None if no data is available.
        """
