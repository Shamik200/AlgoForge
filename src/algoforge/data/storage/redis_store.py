"""Redis storage layer for OHLCV candles.

Stores candles in Redis Sorted Sets keyed by symbol:timeframe,
scored by timestamp. Supports time-range queries, batch writes
via pipelining, and connection management.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import structlog

from algoforge.core.config import get_settings
from algoforge.core.constants import Timeframe
from algoforge.core.models import OHLCV

logger = structlog.get_logger()


class RedisStore:
    """Async Redis storage for OHLCV time-series data.

    Uses Redis Sorted Sets with timestamp scores for ordered retrieval.
    Accepts an optional pre-built redis client (useful for fakeredis in tests).
    """

    def __init__(self, redis_client: Any | None = None) -> None:
        self._client = redis_client
        self._connected = redis_client is not None
        self._settings = get_settings()

    async def connect(self) -> None:
        """Connect to Redis if not already connected."""
        if self._connected and self._client is not None:
            return

        import redis.asyncio as aioredis

        cfg = self._settings.redis
        self._client = aioredis.Redis(
            host=cfg.host,
            port=cfg.port,
            db=cfg.db,
            password=cfg.password,
            decode_responses=True,
            socket_timeout=cfg.socket_timeout,
            max_connections=cfg.max_connections,
        )
        self._connected = True
        logger.info(
            "redis_store.connected",
            host=cfg.host,
            port=cfg.port,
            db=cfg.db,
        )

    async def disconnect(self) -> None:
        """Close the Redis connection."""
        if self._client is not None:
            await self._client.aclose()
            self._connected = False
            logger.info("redis_store.disconnected")

    async def health_check(self) -> bool:
        """Ping Redis to check connectivity."""
        if self._client is None:
            return False
        try:
            result = await self._client.ping()
            return result is True or result == "PONG" or result == b"PONG"
        except Exception as e:
            logger.error("redis_store.health_check_failed", error=str(e))
            return False

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def store_candle(self, candle: OHLCV) -> None:
        """Store a single OHLCV candle."""
        key = self._key(candle.symbol, candle.timeframe)
        score = candle.to_redis_score()
        value = candle.model_dump_json()
        await self._client.zadd(key, {value: score})

    async def store_candles(self, candles: list[OHLCV]) -> int:
        """Store multiple candles using pipelining for efficiency.

        Returns the number of candles stored.
        """
        if not candles:
            return 0

        pipe = self._client.pipeline()
        for candle in candles:
            key = self._key(candle.symbol, candle.timeframe)
            score = candle.to_redis_score()
            value = candle.model_dump_json()
            pipe.zadd(key, {value: score})

        await pipe.execute()
        return len(candles)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[OHLCV]:
        """Retrieve candles for a symbol/timeframe, optionally filtered by time range.

        Returns candles sorted by timestamp ascending.
        """
        key = self._key(symbol, timeframe)

        if start is not None and end is not None:
            min_score = start.timestamp()
            max_score = end.timestamp()
            raw = await self._client.zrangebyscore(key, min_score, max_score)
        else:
            raw = await self._client.zrangebyscore(key, "-inf", "+inf")

        return [OHLCV.model_validate_json(item) for item in raw]

    async def get_latest_candle(
        self,
        symbol: str,
        timeframe: Timeframe,
    ) -> OHLCV | None:
        """Get the most recent candle (highest timestamp score)."""
        key = self._key(symbol, timeframe)
        # ZREVRANGE returns items from highest to lowest score
        result = await self._client.zrevrange(key, 0, 0)
        if not result:
            return None
        return OHLCV.model_validate_json(result[0])

    async def get_candle_count(
        self,
        symbol: str,
        timeframe: Timeframe,
    ) -> int:
        """Count stored candles for a symbol/timeframe."""
        key = self._key(symbol, timeframe)
        return await self._client.zcard(key)

    # ------------------------------------------------------------------
    # Delete operations
    # ------------------------------------------------------------------

    async def delete_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
    ) -> int:
        """Delete all candles for a symbol/timeframe. Returns count deleted."""
        key = self._key(symbol, timeframe)
        count = await self._client.zcard(key)
        await self._client.delete(key)
        return count

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _key(symbol: str, timeframe: Timeframe) -> str:
        """Generate Redis sorted set key: ohlcv:{symbol}:{timeframe}."""
        return f"ohlcv:{symbol}:{timeframe.value}"
