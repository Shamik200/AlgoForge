---
phase: 1
plan: 4
title: "Data Pipeline Integration & Application Entry Point"
wave: 4
depends_on: [1, 2, 3]
files_modified:
  - src/algoforge/data/pipeline.py
  - src/algoforge/__main__.py
  - tests/integration/__init__.py
  - tests/integration/test_pipeline.py
requirements: [DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, CONF-01, CONF-02, CONF-03, CONF-04, CONF-05]
autonomous: true
---

# Plan 04: Data Pipeline Integration & Application Entry Point

<objective>
Wire everything together into the DataPipeline orchestrator that ingests data from yfinance, resamples to multiple timeframes, stores in Redis, and publishes events. Create the application entry point (__main__.py) that loads config, connects services, and starts the pipeline.
</objective>

<task id="04-01">
## Task 1: Create DataPipeline orchestrator

<read_first>
- src/algoforge/data/feeds/yfinance_feed.py (data feed)
- src/algoforge/data/storage/redis_store.py (storage)
- src/algoforge/data/processors/resampler.py (resampler)
- src/algoforge/core/event_bus.py (event publishing)
- src/algoforge/core/config.py (settings)
- .planning/phases/01-foundation-data/01-CONTEXT.md §D-15 (timeframe strategy)
</read_first>

<action>
Create `src/algoforge/data/pipeline.py`:

```python
import asyncio
from datetime import datetime
from algoforge.core.config import get_settings
from algoforge.core.event_bus import EventBus, MarketDataEvent
from algoforge.core.constants import Timeframe, TimeframeMode, TIMEFRAME_CONFIG
from algoforge.data.feeds.base import DataFeed
from algoforge.data.storage.redis_store import RedisStore
from algoforge.data.processors.resampler import Resampler
import structlog

logger = structlog.get_logger()

class DataPipeline:
    """Orchestrates data flow: Feed → Normalize → Resample → Store → Publish.
    
    This is the heartbeat of the system. It:
    1. Fetches OHLCV data from the configured feed
    2. Stores base timeframe candles in Redis
    3. Resamples to all required higher timeframes
    4. Stores resampled candles in Redis
    5. Publishes MarketDataEvents for each new candle
    """
    
    def __init__(
        self,
        feed: DataFeed,
        store: RedisStore,
        event_bus: EventBus,
        resampler: Resampler | None = None,
    ) -> None:
        self._feed = feed
        self._store = store
        self._event_bus = event_bus
        self._resampler = resampler or Resampler()
        self._running = False
        self._settings = get_settings()
    
    async def initialize(self) -> None:
        """Connect to data feed and storage."""
        await self._feed.connect()
        await self._store.connect()
        logger.info("pipeline.initialized")
    
    async def shutdown(self) -> None:
        """Gracefully disconnect all services."""
        self._running = False
        await self._feed.disconnect()
        await self._store.disconnect()
        logger.info("pipeline.shutdown")
    
    async def backfill(self, symbol: str) -> int:
        """Backfill historical data for a symbol from the configured feed."""
        settings = self._settings
        base_tf = settings.data_feed.base_timeframe
        period = settings.data_feed.history_period
        
        candles = await self._feed.fetch_historical(
            symbol=symbol, timeframe=base_tf, period=period
        )
        
        if not candles:
            logger.warning("pipeline.backfill.empty", symbol=symbol)
            return 0
        
        # Store base timeframe
        stored = await self._store.store_candles(candles)
        
        # Resample and store higher timeframes
        mode = settings.market.timeframe_mode
        tf_config = TIMEFRAME_CONFIG[mode]
        target_tfs = set(tf_config["sr_timeframes"] + tf_config["trendline_timeframes"])
        
        resampled = self._resampler.resample_to_all(candles, list(target_tfs))
        for tf, tf_candles in resampled.items():
            await self._store.store_candles(tf_candles)
            stored += len(tf_candles)
        
        logger.info("pipeline.backfill.complete", symbol=symbol, 
                    candles_stored=stored, timeframes=len(resampled) + 1)
        return stored
    
    async def backfill_all(self) -> dict[str, int]:
        """Backfill historical data for all configured symbols."""
        symbols = self._settings.data_feed.symbols
        results = {}
        for symbol in symbols:
            try:
                count = await self.backfill(symbol)
                results[symbol] = count
            except Exception as e:
                logger.error("pipeline.backfill.error", symbol=symbol, error=str(e))
                results[symbol] = 0
        return results
    
    async def fetch_and_store_latest(self, symbol: str) -> bool:
        """Fetch the latest candle and store it. Returns True if new data received."""
        base_tf = self._settings.data_feed.base_timeframe
        candle = await self._feed.fetch_latest(symbol, base_tf)
        
        if candle is None:
            return False
        
        await self._store.store_candle(candle)
        
        # Publish market data event
        event = MarketDataEvent(
            symbol=symbol,
            timeframe=base_tf.value,
            candle=candle,
        )
        await self._event_bus.publish(event)
        
        return True
    
    async def run_polling_loop(self, interval_seconds: int = 60) -> None:
        """Continuously poll for new data at the configured interval."""
        self._running = True
        symbols = self._settings.data_feed.symbols
        
        logger.info("pipeline.polling.started", 
                    symbols=symbols, interval=interval_seconds)
        
        while self._running:
            for symbol in symbols:
                try:
                    await self.fetch_and_store_latest(symbol)
                except Exception as e:
                    logger.error("pipeline.poll.error", symbol=symbol, error=str(e))
            
            await asyncio.sleep(interval_seconds)
    
    async def health_check(self) -> dict[str, bool]:
        """Check health of all pipeline components."""
        return {
            "feed": await self._feed.health_check(),
            "store": await self._store.health_check(),
        }
```
</action>

<acceptance_criteria>
- pipeline.py contains `class DataPipeline` with methods: initialize, shutdown, backfill, backfill_all, fetch_and_store_latest, run_polling_loop, health_check
- DataPipeline accepts DataFeed, RedisStore, EventBus via constructor (dependency injection)
- backfill method fetches historical + resamples to timeframe mode + stores all
- fetch_and_store_latest publishes MarketDataEvent after storing candle
- run_polling_loop polls at configurable interval with error handling per symbol
- health_check returns status dict for feed and store
</acceptance_criteria>
</task>

<task id="04-02">
## Task 2: Create application entry point

<read_first>
- src/algoforge/data/pipeline.py (pipeline orchestrator)
- src/algoforge/core/config.py (settings)
- src/algoforge/core/logging.py (setup_logging)
- src/algoforge/core/event_bus.py (EventBus)
</read_first>

<action>
Update `src/algoforge/__main__.py`:

```python
"""AlgoForge — Institutional-Grade Algorithmic Trading System.

Entry point: python -m algoforge
"""
import asyncio
import signal
import sys
from algoforge.core.config import get_settings
from algoforge.core.logging import setup_logging
from algoforge.core.event_bus import EventBus, SystemEvent
from algoforge.data.feeds.yfinance_feed import YFinanceFeed
from algoforge.data.storage.redis_store import RedisStore
from algoforge.data.pipeline import DataPipeline
import structlog

logger = structlog.get_logger()

async def main() -> None:
    """Main application entry point."""
    setup_logging()
    settings = get_settings()
    
    logger.info("algoforge.starting", 
                version=settings.version,
                market=settings.market.selected_market.value,
                mode=settings.market.timeframe_mode.value,
                symbols=settings.data_feed.symbols,
                capital=settings.market.paper_trading_capital,
                currency=settings.market.currency)
    
    # Initialize components
    event_bus = EventBus()
    feed = YFinanceFeed()
    store = RedisStore()
    pipeline = DataPipeline(feed=feed, store=store, event_bus=event_bus)
    
    # Setup graceful shutdown
    shutdown_event = asyncio.Event()
    
    def handle_signal(sig, frame):
        logger.info("algoforge.shutdown_signal", signal=sig)
        shutdown_event.set()
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    try:
        # Connect and initialize
        await pipeline.initialize()
        
        # Publish startup event
        await event_bus.publish(SystemEvent(
            action="startup",
            message=f"AlgoForge v{settings.version} started — {settings.market.selected_market.value}"
        ))
        
        # Health check
        health = await pipeline.health_check()
        logger.info("algoforge.health", **health)
        
        # Backfill historical data
        logger.info("algoforge.backfill.starting")
        results = await pipeline.backfill_all()
        for symbol, count in results.items():
            logger.info("algoforge.backfill.result", symbol=symbol, candles=count)
        
        # Start event bus and polling loop concurrently
        event_bus_task = asyncio.create_task(event_bus.start())
        polling_task = asyncio.create_task(pipeline.run_polling_loop())
        
        # Wait for shutdown signal
        await shutdown_event.wait()
        
    except Exception as e:
        logger.error("algoforge.error", error=str(e), exc_info=True)
    finally:
        await pipeline.shutdown()
        await event_bus.stop()
        logger.info("algoforge.stopped")

if __name__ == "__main__":
    asyncio.run(main())
```
</action>

<acceptance_criteria>
- __main__.py contains `async def main()` that initializes all components
- __main__.py loads settings, creates EventBus, YFinanceFeed, RedisStore, DataPipeline
- __main__.py calls pipeline.backfill_all() on startup
- __main__.py starts polling loop and event bus concurrently with asyncio.create_task
- __main__.py handles SIGINT/SIGTERM for graceful shutdown
- __main__.py logs startup info including market, mode, symbols, capital
</acceptance_criteria>
</task>

<task id="04-03">
## Task 3: Create integration test

<read_first>
- src/algoforge/data/pipeline.py (pipeline)
- src/algoforge/data/feeds/yfinance_feed.py (feed)
- src/algoforge/data/storage/redis_store.py (store)
- src/algoforge/core/event_bus.py (event bus)
</read_first>

<action>
Create `tests/integration/test_pipeline.py`:

```python
"""Integration test: end-to-end data pipeline.

Tests the full flow: yfinance → normalize → resample → Redis.
Requires: Redis running on localhost:6379 (skipped if not available).
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from algoforge.data.pipeline import DataPipeline
from algoforge.data.feeds.yfinance_feed import YFinanceFeed
from algoforge.data.storage.redis_store import RedisStore
from algoforge.data.processors.resampler import Resampler
from algoforge.core.event_bus import EventBus
from algoforge.core.models import OHLCV
from algoforge.core.constants import Timeframe
from datetime import datetime

# Test with mock feed (no real yfinance calls)
@pytest.fixture
def mock_candles():
    """Generate test OHLCV candles."""
    base = datetime(2024, 1, 15, 9, 30)
    candles = []
    for i in range(10):
        candles.append(OHLCV(
            symbol="TEST",
            timeframe=Timeframe.M1,
            timestamp=base.replace(minute=30 + i),
            open=100.0 + i,
            high=101.0 + i,
            low=99.0 + i,
            close=100.5 + i,
            volume=1000.0 * (i + 1),
        ))
    return candles

@pytest.mark.asyncio
async def test_pipeline_backfill_with_mock(mock_candles):
    """Test pipeline backfill with mocked feed and Redis."""
    # Mock the feed
    mock_feed = AsyncMock(spec=YFinanceFeed)
    mock_feed.fetch_historical.return_value = mock_candles
    mock_feed.health_check.return_value = True
    
    # Use fakeredis for storage
    import fakeredis.aioredis as fake_aioredis
    fake_redis = fake_aioredis.FakeRedis(decode_responses=True)
    store = RedisStore(redis_client=fake_redis)
    
    event_bus = EventBus()
    pipeline = DataPipeline(feed=mock_feed, store=store, event_bus=event_bus)
    
    # Backfill
    count = await pipeline.backfill("TEST")
    
    assert count > 0
    mock_feed.fetch_historical.assert_called_once()

@pytest.mark.asyncio
async def test_pipeline_health_check():
    """Test health check reports component status."""
    mock_feed = AsyncMock(spec=YFinanceFeed)
    mock_feed.health_check.return_value = True
    
    mock_store = AsyncMock(spec=RedisStore)
    mock_store.health_check.return_value = True
    
    event_bus = EventBus()
    pipeline = DataPipeline(feed=mock_feed, store=mock_store, event_bus=event_bus)
    
    health = await pipeline.health_check()
    assert health["feed"] is True
    assert health["store"] is True
```
</action>

<acceptance_criteria>
- tests/integration/test_pipeline.py contains at least 2 test functions
- Tests use mocked DataFeed (no real yfinance API calls)
- Tests use fakeredis for Redis operations (no real Redis needed for unit)
- test_pipeline_backfill_with_mock verifies backfill stores candles
- test_pipeline_health_check verifies health returns component statuses
- Running `pytest tests/integration/test_pipeline.py` exits 0
</acceptance_criteria>
</task>

<verification>
## Verification Criteria

### must_haves
- [ ] DataPipeline connects feed, store, resampler, and event bus
- [ ] Backfill fetches historical data and stores at multiple timeframes
- [ ] Application starts with `python -m algoforge` and logs startup info
- [ ] Graceful shutdown on SIGINT/SIGTERM
- [ ] All unit and integration tests pass
- [ ] `python -c "from algoforge.core.config import get_settings; print(get_settings().market.selected_market)"` works
</verification>
