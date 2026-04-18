"""Tests for Redis storage layer."""

from datetime import datetime, timezone

import pytest

from algoforge.core.constants import Timeframe
from algoforge.core.models import OHLCV
from algoforge.data.storage.redis_store import RedisStore


def _make_candle(minute: int = 30, close: float = 101.0) -> OHLCV:
    """Helper to create a test candle."""
    high = max(102.0, close + 1.0)  # Ensure high >= close
    return OHLCV(
        symbol="TEST",
        timeframe=Timeframe.M1,
        timestamp=datetime(2024, 1, 15, 9, minute, tzinfo=timezone.utc),
        open=100.0,
        high=high,
        low=99.0,
        close=close,
        volume=1000.0,
    )


@pytest.fixture
async def store():
    """Create a RedisStore with fakeredis backend."""
    import fakeredis.aioredis as fake_aioredis

    fake_client = fake_aioredis.FakeRedis(decode_responses=True)
    redis_store = RedisStore(redis_client=fake_client)
    redis_store._connected = True
    yield redis_store
    await fake_client.aclose()


class TestRedisStore:
    """Test Redis OHLCV storage operations."""

    @pytest.mark.asyncio
    async def test_store_and_retrieve_candle(self, store: RedisStore) -> None:
        """Store a candle and retrieve it by time range."""
        candle = _make_candle()
        await store.store_candle(candle)

        result = await store.get_candles("TEST", Timeframe.M1)
        assert len(result) == 1
        assert result[0].symbol == "TEST"
        assert result[0].close == 101.0

    @pytest.mark.asyncio
    async def test_store_candles_batch(self, store: RedisStore) -> None:
        """Store multiple candles via pipelining."""
        candles = [_make_candle(minute=30 + i, close=100.0 + i) for i in range(5)]
        count = await store.store_candles(candles)

        assert count == 5
        result = await store.get_candles("TEST", Timeframe.M1)
        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_get_latest_candle(self, store: RedisStore) -> None:
        """Get the most recent candle."""
        candles = [_make_candle(minute=30 + i, close=100.0 + i) for i in range(3)]
        await store.store_candles(candles)

        latest = await store.get_latest_candle("TEST", Timeframe.M1)
        assert latest is not None
        assert latest.close == 102.0  # Last candle

    @pytest.mark.asyncio
    async def test_get_candle_count(self, store: RedisStore) -> None:
        """Count stored candles."""
        candles = [_make_candle(minute=30 + i) for i in range(4)]
        await store.store_candles(candles)

        count = await store.get_candle_count("TEST", Timeframe.M1)
        assert count == 4

    @pytest.mark.asyncio
    async def test_empty_retrieval(self, store: RedisStore) -> None:
        """No candles returns empty list."""
        result = await store.get_candles("NONEXISTENT", Timeframe.M1)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_latest_empty(self, store: RedisStore) -> None:
        """No candles returns None for latest."""
        latest = await store.get_latest_candle("NONEXISTENT", Timeframe.M1)
        assert latest is None

    @pytest.mark.asyncio
    async def test_store_empty_list(self, store: RedisStore) -> None:
        """Storing empty list returns 0."""
        count = await store.store_candles([])
        assert count == 0

    @pytest.mark.asyncio
    async def test_time_range_filtering(self, store: RedisStore) -> None:
        """Retrieve candles within specific time range."""
        candles = [_make_candle(minute=30 + i, close=100.0 + i) for i in range(10)]
        await store.store_candles(candles)

        start = datetime(2024, 1, 15, 9, 33, tzinfo=timezone.utc)
        end = datetime(2024, 1, 15, 9, 36, tzinfo=timezone.utc)
        result = await store.get_candles("TEST", Timeframe.M1, start=start, end=end)

        assert len(result) == 4  # minutes 33, 34, 35, 36

    @pytest.mark.asyncio
    async def test_delete_candles(self, store: RedisStore) -> None:
        """Delete all candles for a symbol/timeframe."""
        candles = [_make_candle(minute=30 + i) for i in range(3)]
        await store.store_candles(candles)

        deleted = await store.delete_candles("TEST", Timeframe.M1)
        assert deleted == 3

        count = await store.get_candle_count("TEST", Timeframe.M1)
        assert count == 0

    @pytest.mark.asyncio
    async def test_key_format(self, store: RedisStore) -> None:
        """Key format is ohlcv:{symbol}:{timeframe}."""
        key = store._key("AAPL", Timeframe.D1)
        assert key == "ohlcv:AAPL:1d"
