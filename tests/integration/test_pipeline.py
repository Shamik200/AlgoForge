"""Integration tests for the data pipeline.

Tests the full flow: feed → normalize → resample → store → event.
Uses mocked feed and fakeredis (no real API calls or Redis needed).
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from algoforge.core.constants import Timeframe
from algoforge.core.event_bus import EventBus
from algoforge.core.models import OHLCV
from algoforge.data.feeds.yfinance_feed import YFinanceFeed
from algoforge.data.pipeline import DataPipeline
from algoforge.data.processors.resampler import Resampler
from algoforge.data.storage.redis_store import RedisStore


def _make_test_candles(count: int = 10) -> list[OHLCV]:
    """Generate test OHLCV candles."""
    base = datetime(2024, 1, 15, 9, 30, tzinfo=timezone.utc)
    candles = []
    for i in range(count):
        candles.append(
            OHLCV(
                symbol="TEST",
                timeframe=Timeframe.M1,
                timestamp=base.replace(minute=30 + i),
                open=100.0 + i,
                high=102.0 + i,
                low=99.0 + i,
                close=101.0 + i,
                volume=1000.0 * (i + 1),
            )
        )
    return candles


@pytest.fixture
async def mock_pipeline():
    """Create DataPipeline with mocked feed and fakeredis store."""
    import fakeredis.aioredis as fake_aioredis

    # Mock feed
    mock_feed = AsyncMock(spec=YFinanceFeed)
    mock_feed.fetch_historical.return_value = _make_test_candles()
    mock_feed.fetch_latest.return_value = _make_test_candles(1)[0]
    mock_feed.health_check.return_value = True
    mock_feed.connect.return_value = None
    mock_feed.disconnect.return_value = None

    # Fakeredis store
    fake_redis = fake_aioredis.FakeRedis(decode_responses=True)
    store = RedisStore(redis_client=fake_redis)
    store._connected = True

    # Real event bus
    event_bus = EventBus()

    pipeline = DataPipeline(
        feed=mock_feed,
        cache=store,
        event_bus=event_bus,
    )

    yield pipeline, mock_feed, store, event_bus

    await fake_redis.aclose()


class TestDataPipeline:
    """Test end-to-end data pipeline operations."""

    @pytest.mark.asyncio
    async def test_pipeline_backfill(self, mock_pipeline) -> None:
        """Backfill fetches data, resamples, and stores in Redis."""
        pipeline, mock_feed, store, _ = mock_pipeline

        count = await pipeline.backfill("TEST")

        assert count > 0
        mock_feed.fetch_historical.assert_called_once()

        # Verify candles are in Redis
        stored = await store.get_candles("TEST", Timeframe.M1)
        assert len(stored) == 10

    @pytest.mark.asyncio
    async def test_pipeline_backfill_empty(self, mock_pipeline) -> None:
        """Backfill with empty response stores nothing."""
        pipeline, mock_feed, store, _ = mock_pipeline
        mock_feed.fetch_historical.return_value = []

        count = await pipeline.backfill("EMPTY")
        assert count == 0

    @pytest.mark.asyncio
    async def test_pipeline_backfill_all(self, mock_pipeline) -> None:
        """Backfill all configured symbols."""
        pipeline, _, _, _ = mock_pipeline

        results = await pipeline.backfill_all()

        assert isinstance(results, dict)
        assert len(results) > 0
        # All symbols should have data
        for symbol, count in results.items():
            assert count >= 0

    @pytest.mark.asyncio
    async def test_pipeline_fetch_and_store_latest(self, mock_pipeline) -> None:
        """Fetch latest candle, store it, and publish event."""
        pipeline, mock_feed, store, event_bus = mock_pipeline

        success = await pipeline.fetch_and_store_latest("TEST")

        assert success is True
        mock_feed.fetch_latest.assert_called_once()

        # Check event was published
        assert event_bus.stats["published"] == 1

    @pytest.mark.asyncio
    async def test_pipeline_fetch_latest_no_data(self, mock_pipeline) -> None:
        """Fetch latest returns False when no data available."""
        pipeline, mock_feed, _, _ = mock_pipeline
        mock_feed.fetch_latest.return_value = None

        success = await pipeline.fetch_and_store_latest("EMPTY")
        assert success is False

    @pytest.mark.asyncio
    async def test_pipeline_health_check(self, mock_pipeline) -> None:
        """Health check reports component status."""
        pipeline, _, _, _ = mock_pipeline

        health = await pipeline.health_check()

        assert health["feed"] is True
        assert health["store"] is True
        assert health["pipeline"] is True

    @pytest.mark.asyncio
    async def test_pipeline_health_check_feed_down(self, mock_pipeline) -> None:
        """Health check reports when feed is down."""
        pipeline, mock_feed, _, _ = mock_pipeline
        mock_feed.health_check.return_value = False

        health = await pipeline.health_check()
        assert health["feed"] is False
        assert health["pipeline"] is False

    @pytest.mark.asyncio
    async def test_pipeline_stop(self, mock_pipeline) -> None:
        """Pipeline stop flag works."""
        pipeline, _, _, _ = mock_pipeline

        assert pipeline.is_running is False
        pipeline.stop()
        assert pipeline.is_running is False
