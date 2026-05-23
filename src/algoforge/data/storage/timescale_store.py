"""TimescaleDB storage adapter for OHLCV data.

Uses asyncpg for async PostgreSQL access with TimescaleDB extensions.
Schema: hypertable partitioned by timestamp, continuous aggregates for
multi-timeframe resampling.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog

from algoforge.core.config import get_settings
from algoforge.core.constants import Timeframe
from algoforge.core.models import OHLCV

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# SQL Schema Definitions
# ---------------------------------------------------------------------------

CREATE_OHLCV_TABLE = """
CREATE TABLE IF NOT EXISTS ohlcv (
    timestamp   TIMESTAMPTZ NOT NULL,
    symbol      TEXT NOT NULL,
    timeframe   TEXT NOT NULL,
    open        DOUBLE PRECISION NOT NULL,
    high        DOUBLE PRECISION NOT NULL,
    low         DOUBLE PRECISION NOT NULL,
    close       DOUBLE PRECISION NOT NULL,
    volume      DOUBLE PRECISION NOT NULL,
    UNIQUE (timestamp, symbol, timeframe)
);
"""

CREATE_HYPERTABLE = """
SELECT create_hypertable('ohlcv', 'timestamp', if_not_exists => TRUE);
"""

CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_tf
ON ohlcv (symbol, timeframe, timestamp DESC);
"""

# Continuous aggregate for 5-minute candles from 1-minute data
CREATE_AGG_5M = """
CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_5m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', timestamp) AS bucket,
    symbol,
    '5m' AS timeframe,
    first(open, timestamp) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, timestamp) AS close,
    sum(volume) AS volume
FROM ohlcv
WHERE timeframe = '1m'
GROUP BY bucket, symbol
WITH NO DATA;
"""


class TimescaleStore:
    """Async TimescaleDB storage for OHLCV data.

    Follows the same adapter pattern as RedisStore:
    connect → health_check → store_candle(s) → query_candles → disconnect.
    """

    def __init__(self) -> None:
        self._pool: Any = None  # asyncpg.Pool — typed as Any for import safety
        self._settings = get_settings()

    async def connect(self) -> None:
        """Create connection pool and ensure schema exists."""
        import asyncpg

        cfg = self._settings.timescaledb
        dsn = f"postgresql://{cfg.user}:{cfg.password}@{cfg.host}:{cfg.port}/{cfg.database}"
        self._pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=cfg.min_connections,
            max_size=cfg.max_connections,
        )
        await self._ensure_schema()
        logger.info("timescale_store.connected", host=cfg.host, db=cfg.database)

    async def disconnect(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
        logger.info("timescale_store.disconnected")

    async def health_check(self) -> bool:
        """Check TimescaleDB connectivity."""
        if not self._pool:
            return False
        try:
            async with self._pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1
        except Exception as e:
            logger.error("timescale_store.health_check_failed", error=str(e))
            return False

    # ------------------------------------------------------------------
    # Schema management
    # ------------------------------------------------------------------

    async def _ensure_schema(self) -> None:
        """Create tables, hypertables, indexes, and continuous aggregates."""
        async with self._pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
            await conn.execute(CREATE_OHLCV_TABLE)
            await conn.execute(CREATE_HYPERTABLE)
            await conn.execute(CREATE_INDEX)
            try:
                await conn.execute(CREATE_AGG_5M)
            except Exception:
                pass  # Aggregate may already exist
            
            try:
                # Add background refresh policy for 5m continuous aggregate
                await conn.execute("""
                    SELECT add_continuous_aggregate_policy('ohlcv_5m',
                        start_offset => INTERVAL '1 month',
                        end_offset => INTERVAL '1 hour',
                        schedule_interval => INTERVAL '1 hour');
                """)
                logger.info("timescale_store.schema.refresh_policy_created")
            except Exception:
                pass  # Policy may already exist or DB is offline/in-memory


    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def store_candle(self, candle: OHLCV) -> None:
        """Insert or update a single candle (upsert)."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO ohlcv (timestamp, symbol, timeframe, open, high, low, close, volume)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                   ON CONFLICT (timestamp, symbol, timeframe)
                   DO UPDATE SET open=$4, high=$5, low=$6, close=$7, volume=$8""",
                *candle.to_timescale_row(),
            )

    async def store_candles(self, candles: list[OHLCV]) -> int:
        """Batch insert candles using executemany for performance.

        Returns the number of candles processed.
        """
        if not candles:
            return 0
        rows = [c.to_timescale_row() for c in candles]
        async with self._pool.acquire() as conn:
            await conn.executemany(
                """INSERT INTO ohlcv (timestamp, symbol, timeframe, open, high, low, close, volume)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                   ON CONFLICT (timestamp, symbol, timeframe) DO NOTHING""",
                rows,
            )
        return len(candles)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def query_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 1000,
    ) -> list[OHLCV]:
        """Query candles from TimescaleDB with optional time range filter."""
        query = "SELECT * FROM ohlcv WHERE symbol = $1 AND timeframe = $2"
        params: list[Any] = [symbol, timeframe.value]
        idx = 3

        if start:
            query += f" AND timestamp >= ${idx}"
            params.append(start)
            idx += 1
        if end:
            query += f" AND timestamp <= ${idx}"
            params.append(end)
            idx += 1

        query += f" ORDER BY timestamp ASC LIMIT ${idx}"
        params.append(limit)

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [OHLCV.from_timescale_row(dict(r)) for r in rows]

    async def get_latest_candle(
        self,
        symbol: str,
        timeframe: Timeframe,
    ) -> OHLCV | None:
        """Get the most recent candle for a symbol/timeframe."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT * FROM ohlcv
                   WHERE symbol = $1 AND timeframe = $2
                   ORDER BY timestamp DESC LIMIT 1""",
                symbol,
                timeframe.value,
            )
            if row is None:
                return None
            return OHLCV.from_timescale_row(dict(row))

    async def get_candle_count(
        self,
        symbol: str,
        timeframe: Timeframe,
    ) -> int:
        """Count stored candles for a symbol/timeframe."""
        async with self._pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT COUNT(*) FROM ohlcv WHERE symbol = $1 AND timeframe = $2",
                symbol,
                timeframe.value,
            )
