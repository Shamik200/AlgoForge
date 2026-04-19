"""Tests for upgraded DataPipeline v2 — multi-feed + dual storage."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from algoforge.core.constants import Timeframe
from algoforge.core.models import OHLCV
from algoforge.data.feeds.base_feed import BaseFeed
from algoforge.data.pipeline import DataPipeline
from algoforge.data.storage.redis_store import RedisStore


def _make_candle(symbol: str = "TEST", tf: Timeframe = Timeframe.M1) -> OHLCV:
    return OHLCV(
        symbol=symbol,
        timeframe=tf,
        timestamp=datetime(2024, 1, 15, 14, 30, tzinfo=timezone.utc),
        open=100.0,
        high=105.0,
        low=99.0,
        close=103.0,
        volume=5000.0,
    )


class TestPipelineV2Init:
    """DataPipeline accepts BaseFeed and optional TimescaleStore."""

    def test_accepts_base_feed(self) -> None:
        mock_feed = MagicMock(spec=BaseFeed)
        mock_cache = MagicMock(spec=RedisStore)
        pipeline = DataPipeline(feed=mock_feed, cache=mock_cache)
        assert pipeline._feed is mock_feed
        assert pipeline._cache is mock_cache

    def test_store_is_optional(self) -> None:
        mock_feed = MagicMock(spec=BaseFeed)
        mock_cache = MagicMock(spec=RedisStore)
        pipeline = DataPipeline(feed=mock_feed, cache=mock_cache)
        assert pipeline._store is None

    def test_store_accepts_timescale(self) -> None:
        mock_feed = MagicMock(spec=BaseFeed)
        mock_cache = MagicMock(spec=RedisStore)
        mock_store = MagicMock()
        pipeline = DataPipeline(feed=mock_feed, cache=mock_cache, store=mock_store)
        assert pipeline._store is mock_store

    def test_event_bus_is_optional(self) -> None:
        mock_feed = MagicMock(spec=BaseFeed)
        mock_cache = MagicMock(spec=RedisStore)
        pipeline = DataPipeline(feed=mock_feed, cache=mock_cache)
        assert pipeline._event_bus is None


class TestPipelineV2DualStorage:
    """Pipeline writes to both cache and persistent store."""

    @pytest.mark.asyncio
    async def test_fetch_and_store_writes_to_cache(self) -> None:
        candle = _make_candle()
        mock_feed = AsyncMock(spec=BaseFeed)
        mock_feed.fetch_latest = AsyncMock(return_value=candle)
        mock_cache = AsyncMock(spec=RedisStore)
        mock_cache.store_candle = AsyncMock()

        pipeline = DataPipeline(feed=mock_feed, cache=mock_cache)
        result = await pipeline.fetch_and_store_latest("TEST")

        assert result is True
        mock_cache.store_candle.assert_awaited_once_with(candle)

    @pytest.mark.asyncio
    async def test_fetch_and_store_writes_to_persistent_store(self) -> None:
        candle = _make_candle()
        mock_feed = AsyncMock(spec=BaseFeed)
        mock_feed.fetch_latest = AsyncMock(return_value=candle)
        mock_cache = AsyncMock(spec=RedisStore)
        mock_store = AsyncMock()

        pipeline = DataPipeline(feed=mock_feed, cache=mock_cache, store=mock_store)
        result = await pipeline.fetch_and_store_latest("TEST")

        assert result is True
        mock_cache.store_candle.assert_awaited_once()
        mock_store.store_candle.assert_awaited_once_with(candle)

    @pytest.mark.asyncio
    async def test_fetch_returns_false_when_no_candle(self) -> None:
        mock_feed = AsyncMock(spec=BaseFeed)
        mock_feed.fetch_latest = AsyncMock(return_value=None)
        mock_cache = AsyncMock(spec=RedisStore)

        pipeline = DataPipeline(feed=mock_feed, cache=mock_cache)
        result = await pipeline.fetch_and_store_latest("TEST")
        assert result is False

    @pytest.mark.asyncio
    async def test_backfill_no_data(self) -> None:
        mock_feed = AsyncMock(spec=BaseFeed)
        mock_feed.fetch_historical = AsyncMock(return_value=[])
        mock_cache = AsyncMock(spec=RedisStore)

        pipeline = DataPipeline(feed=mock_feed, cache=mock_cache)
        count = await pipeline.backfill("TEST")
        assert count == 0


class TestPipelineV2HealthCheck:
    """Health check covers all components."""

    @pytest.mark.asyncio
    async def test_health_check_without_store(self) -> None:
        mock_feed = AsyncMock(spec=BaseFeed)
        mock_feed.health_check = AsyncMock(return_value=True)
        mock_cache = AsyncMock(spec=RedisStore)
        mock_cache.health_check = AsyncMock(return_value=True)

        pipeline = DataPipeline(feed=mock_feed, cache=mock_cache)
        health = await pipeline.health_check()

        assert health["feed"] is True
        assert health["cache"] is True
        assert health["store"] is True  # Defaults to True when no store
        assert health["pipeline"] is True

    @pytest.mark.asyncio
    async def test_health_check_with_store(self) -> None:
        mock_feed = AsyncMock(spec=BaseFeed)
        mock_feed.health_check = AsyncMock(return_value=True)
        mock_cache = AsyncMock(spec=RedisStore)
        mock_cache.health_check = AsyncMock(return_value=True)
        mock_store = AsyncMock()
        mock_store.health_check = AsyncMock(return_value=False)

        pipeline = DataPipeline(feed=mock_feed, cache=mock_cache, store=mock_store)
        health = await pipeline.health_check()

        assert health["store"] is False
        assert health["pipeline"] is False  # One component down = overall down
