"""Data pipeline — orchestrates feed → normalize → resample → store → event.

The DataPipeline is the central data management component. It coordinates:
1. Historical backfill from the data feed
2. Continuous polling for latest candles
3. Multi-timeframe resampling (1m through 1M)
4. Dual storage: Redis (cache) + TimescaleDB (persistent)
5. Event publication for downstream consumers
"""

from __future__ import annotations

import asyncio

import structlog

from algoforge.core.config import get_settings
from algoforge.core.constants import Timeframe
from algoforge.core.event_bus import EventBus, MarketDataEvent
from algoforge.data.feeds.base_feed import BaseFeed
from algoforge.data.processors.resampler import Resampler
from algoforge.data.storage.redis_store import RedisStore

logger = structlog.get_logger()


class DataPipeline:
    """Orchestrates the full data flow: feed → store → event bus.

    Supports dual storage (Redis cache + TimescaleDB persistent) and
    any feed adapter implementing BaseFeed.

    Args:
        feed: Market data feed adapter (YFinance, Binance, AlphaVantage).
        cache: Redis store for real-time caching.
        store: Optional TimescaleDB store for persistent historical data.
        event_bus: Event bus for publishing data events.
    """

    def __init__(
        self,
        feed: BaseFeed,
        cache: RedisStore,
        store: object | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._feed = feed
        self._cache = cache
        self._store = store  # TimescaleStore (optional for backward compat)
        self._event_bus = event_bus
        self._resampler = Resampler()
        self._settings = get_settings()
        self._running = False

    @property
    def is_running(self) -> bool:
        """True if the polling loop is active."""
        return self._running

    async def initialize(self) -> None:
        """Connect to feed and all stores."""
        await self._feed.connect()
        await self._cache.connect()
        if self._store is not None:
            await self._store.connect()
        logger.info("pipeline.initialized", has_persistent_store=self._store is not None)

    async def shutdown(self) -> None:
        """Disconnect from feed and all stores."""
        await self._feed.disconnect()
        await self._cache.disconnect()
        if self._store is not None:
            await self._store.disconnect()
        logger.info("pipeline.shutdown")

    async def health_check(self) -> dict[str, bool]:
        """Check health of all pipeline components.

        Returns a dict with component status and overall pipeline health.
        """
        feed_ok = await self._feed.health_check()
        cache_ok = await self._cache.health_check()
        store_ok = True
        if self._store is not None:
            store_ok = await self._store.health_check()
        return {
            "feed": feed_ok,
            "cache": cache_ok,
            "store": store_ok,
            "pipeline": feed_ok and cache_ok and store_ok,
        }

    # ------------------------------------------------------------------
    # Backfill
    # ------------------------------------------------------------------

    async def backfill(self, symbol: str) -> int:
        """Backfill historical data for a single symbol.

        Fetches base-timeframe candles, stores them in both cache and
        persistent store, then resamples to higher timeframes.

        Returns the number of base candles stored.
        """
        candles = await self._feed.fetch_historical(symbol)
        if not candles:
            logger.warning("pipeline.backfill.no_data", symbol=symbol)
            return 0

        # Store base timeframe candles in cache (Redis)
        count = await self._cache.store_candles(candles)
        logger.info("pipeline.backfill.cached", symbol=symbol, candles=count)

        # Store in persistent store (TimescaleDB) if available
        if self._store is not None:
            await self._store.store_candles(candles)
            logger.info("pipeline.backfill.persisted", symbol=symbol, candles=count)

        # Resample to higher timeframes and store
        targets = [Timeframe.M5, Timeframe.M15, Timeframe.H1, Timeframe.H4, Timeframe.D1]
        resampled = self._resampler.resample_to_all(candles, targets)
        for tf, tf_candles in resampled.items():
            if tf_candles:
                await self._cache.store_candles(tf_candles)
                if self._store is not None:
                    await self._store.store_candles(tf_candles)
                logger.info(
                    "pipeline.backfill.resampled",
                    symbol=symbol,
                    timeframe=tf.value,
                    candles=len(tf_candles),
                )

        return count

    async def backfill_all(self) -> dict[str, int]:
        """Backfill all configured symbols.

        Returns a dict of {symbol: candle_count}.
        """
        symbols = self._settings.data_feed.symbols
        results: dict[str, int] = {}

        for symbol in symbols:
            try:
                count = await self.backfill(symbol)
                results[symbol] = count
            except Exception as e:
                logger.error(
                    "pipeline.backfill.error",
                    symbol=symbol,
                    error=str(e),
                )
                results[symbol] = 0

        return results

    # ------------------------------------------------------------------
    # Polling loop
    # ------------------------------------------------------------------

    async def fetch_and_store_latest(self, symbol: str) -> bool:
        """Fetch the latest candle, store it in both stores, and publish event.

        Returns True if a candle was fetched and stored.
        """
        candle = await self._feed.fetch_latest(symbol)
        if candle is None:
            return False

        # Write to cache (Redis)
        await self._cache.store_candle(candle)

        # Write to persistent store (TimescaleDB) if available
        if self._store is not None:
            await self._store.store_candle(candle)

        # Publish event for downstream consumers
        if self._event_bus is not None:
            event = MarketDataEvent(
                symbol=candle.symbol,
                timeframe=candle.timeframe.value,
                candle=candle,
            )
            await self._event_bus.publish(event)

        return True

    async def run_polling_loop(self) -> None:
        """Continuously poll for latest candles at the configured interval.

        Runs until stop() is called.
        """
        self._running = True
        interval = self._settings.data_feed.poll_interval_seconds
        symbols = self._settings.data_feed.symbols

        logger.info(
            "pipeline.polling.started",
            symbols=symbols,
            interval_seconds=interval,
        )

        while self._running:
            for symbol in symbols:
                try:
                    await self.fetch_and_store_latest(symbol)
                except Exception as e:
                    logger.error(
                        "pipeline.polling.error",
                        symbol=symbol,
                        error=str(e),
                    )
            await asyncio.sleep(interval)

        logger.info("pipeline.polling.stopped")

    def stop(self) -> None:
        """Signal the polling loop to stop."""
        self._running = False
