---
phase: 1
plan: 3
title: "Redis Storage & yfinance Data Feed"
wave: 3
depends_on: [1, 2]
files_modified:
  - src/algoforge/data/storage/redis_store.py
  - src/algoforge/data/feeds/base.py
  - src/algoforge/data/feeds/yfinance_feed.py
  - src/algoforge/data/processors/resampler.py
  - tests/unit/test_redis_store.py
  - tests/unit/test_yfinance_feed.py
  - tests/unit/test_resampler.py
requirements: [DATA-01, DATA-02, DATA-03, DATA-04, DATA-05]
autonomous: true
---

# Plan 03: Redis Storage & yfinance Data Feed

<objective>
Implement the Redis storage layer for OHLCV data, the abstract DataFeed interface with yfinance concrete adapter, and the multi-timeframe resampling engine. This plan builds the complete data pipeline: yfinance → normalize → resample → Redis.
</objective>

<task id="03-01">
## Task 1: Create Redis storage layer

<read_first>
- src/algoforge/core/models.py (OHLCV, OHLCVSeries models)
- src/algoforge/core/config.py (RedisConfig)
- .planning/phases/01-foundation-data/01-RESEARCH.md §2 (Redis Data Storage patterns)
</read_first>

<action>
Create `src/algoforge/data/storage/redis_store.py`:

```python
import redis.asyncio as aioredis
import json
from datetime import datetime
from algoforge.core.models import OHLCV, OHLCVSeries
from algoforge.core.config import get_settings
from algoforge.core.constants import Timeframe
import structlog

logger = structlog.get_logger()

class RedisStore:
    """Async Redis storage for OHLCV candle data.
    
    Uses Sorted Sets with timestamp as score for efficient time-range queries.
    Key pattern: ohlcv:{symbol}:{timeframe}
    """
    
    def __init__(self, redis_client: aioredis.Redis | None = None) -> None:
        self._client = redis_client
    
    async def connect(self) -> None:
        """Connect to Redis using settings from config."""
        if self._client is None:
            settings = get_settings()
            self._client = aioredis.Redis(
                host=settings.redis.host,
                port=settings.redis.port,
                db=settings.redis.db,
                password=settings.redis.password,
                decode_responses=True,
            )
        await self._client.ping()
        logger.info("redis.connected", host=settings.redis.host, port=settings.redis.port)
    
    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.aclose()
            logger.info("redis.disconnected")
    
    def _key(self, symbol: str, timeframe: Timeframe) -> str:
        """Generate Redis key for a symbol/timeframe pair."""
        return f"ohlcv:{symbol}:{timeframe.value}"
    
    async def store_candle(self, candle: OHLCV) -> None:
        """Store a single OHLCV candle in Redis."""
        key = self._key(candle.symbol, candle.timeframe)
        score = candle.timestamp.timestamp()
        value = candle.model_dump_json()
        await self._client.zadd(key, {value: score})
    
    async def store_candles(self, candles: list[OHLCV]) -> int:
        """Store multiple candles using Redis pipelining for throughput."""
        if not candles:
            return 0
        pipe = self._client.pipeline()
        for candle in candles:
            key = self._key(candle.symbol, candle.timeframe)
            score = candle.timestamp.timestamp()
            value = candle.model_dump_json()
            pipe.zadd(key, {value: score})
        await pipe.execute()
        logger.info("redis.stored_candles", count=len(candles), symbol=candles[0].symbol)
        return len(candles)
    
    async def get_candles(
        self, symbol: str, timeframe: Timeframe,
        start: datetime | None = None, end: datetime | None = None,
        limit: int = 500,
    ) -> list[OHLCV]:
        """Retrieve candles for a symbol/timeframe within a time range."""
        key = self._key(symbol, timeframe)
        min_score = start.timestamp() if start else "-inf"
        max_score = end.timestamp() if end else "+inf"
        
        results = await self._client.zrangebyscore(
            key, min_score, max_score, start=0, num=limit
        )
        
        candles = []
        for raw in results:
            candle = OHLCV.model_validate_json(raw)
            candles.append(candle)
        return candles
    
    async def get_latest_candle(self, symbol: str, timeframe: Timeframe) -> OHLCV | None:
        """Get the most recent candle for a symbol/timeframe."""
        key = self._key(symbol, timeframe)
        results = await self._client.zrange(key, -1, -1)
        if not results:
            return None
        return OHLCV.model_validate_json(results[0])
    
    async def get_candle_count(self, symbol: str, timeframe: Timeframe) -> int:
        """Get the number of stored candles for a symbol/timeframe."""
        key = self._key(symbol, timeframe)
        return await self._client.zcard(key)
    
    async def health_check(self) -> bool:
        """Check if Redis is reachable."""
        try:
            await self._client.ping()
            return True
        except Exception:
            return False
```
</action>

<acceptance_criteria>
- redis_store.py contains `class RedisStore` with methods: connect, disconnect, store_candle, store_candles, get_candles, get_latest_candle
- redis_store.py uses `redis.asyncio` for non-blocking operations
- redis_store.py uses Redis sorted sets (zadd/zrangebyscore) for time-ordered storage
- redis_store.py uses pipelining in `store_candles` for batch writes
- Key pattern is `ohlcv:{symbol}:{timeframe}`
- get_candles supports time range filtering with start/end datetime
</acceptance_criteria>
</task>

<task id="03-02">
## Task 2: Create abstract DataFeed interface and yfinance adapter

<read_first>
- src/algoforge/core/models.py (OHLCV model)
- src/algoforge/core/config.py (DataFeedConfig)
- src/algoforge/core/constants.py (Timeframe, Market enums)
- .planning/phases/01-foundation-data/01-CONTEXT.md §D-03, D-04 (adapter pattern)
- .planning/phases/01-foundation-data/01-RESEARCH.md §1 (yfinance patterns)
</read_first>

<action>
Update `src/algoforge/data/feeds/base.py`:

```python
from abc import ABC, abstractmethod
from datetime import datetime
from algoforge.core.models import OHLCV
from algoforge.core.constants import Timeframe

class DataFeed(ABC):
    """Abstract base class for all market data feeds.
    
    All concrete feeds (yfinance, Binance, Zerodha, CCXT) implement this interface.
    """
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to data source."""
        ...
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to data source."""
        ...
    
    @abstractmethod
    async def fetch_historical(
        self, symbol: str, timeframe: Timeframe,
        start: datetime | None = None, end: datetime | None = None,
        period: str | None = None,
    ) -> list[OHLCV]:
        """Fetch historical OHLCV data."""
        ...
    
    @abstractmethod
    async def fetch_latest(self, symbol: str, timeframe: Timeframe) -> OHLCV | None:
        """Fetch the most recent candle."""
        ...
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if data source is reachable."""
        ...
```

Create `src/algoforge/data/feeds/yfinance_feed.py`:

Implement yfinance adapter:
- Use `asyncio.get_event_loop().run_in_executor()` to wrap synchronous yfinance calls
- Map internal Timeframe enum to yfinance interval strings
- Normalize yfinance DataFrame columns to OHLCV model (open, high, low, close, volume)
- Handle rate limiting with tenacity retry decorator (3 retries, exponential backoff)
- Handle empty responses gracefully (return empty list)
- Support both `period` and `start/end` date ranges
- Add structured logging for all operations

```python
class YFinanceFeed(DataFeed):
    """yfinance data feed adapter — free market data from Yahoo Finance."""
    
    TIMEFRAME_MAP = {
        Timeframe.M1: "1m", Timeframe.M5: "5m", Timeframe.M15: "15m",
        Timeframe.M30: "30m", Timeframe.H1: "1h", Timeframe.H4: "60m",  # yf doesn't have 4h
        Timeframe.D1: "1d", Timeframe.W1: "1wk", Timeframe.MO1: "1mo",
    }
    ...
```
</action>

<acceptance_criteria>
- base.py contains `class DataFeed(ABC)` with abstract methods: connect, disconnect, fetch_historical, fetch_latest, health_check
- yfinance_feed.py contains `class YFinanceFeed(DataFeed)` implementing all abstract methods
- yfinance_feed.py uses `run_in_executor` for async wrapping of synchronous yfinance calls
- yfinance_feed.py has `TIMEFRAME_MAP` dict mapping Timeframe enum to yfinance interval strings
- yfinance_feed.py converts yfinance DataFrame to list[OHLCV] with correct field mapping
- yfinance_feed.py has retry logic (tenacity or manual) for rate limiting
</acceptance_criteria>
</task>

<task id="03-03">
## Task 3: Create multi-timeframe resampler

<read_first>
- src/algoforge/core/models.py (OHLCV model)
- src/algoforge/core/constants.py (Timeframe enum, TIMEFRAME_CONFIG)
- .planning/phases/01-foundation-data/01-RESEARCH.md §4 (Resampling rules)
- .planning/REQUIREMENTS.md §DATA-03 (resampling requirement)
</read_first>

<action>
Create `src/algoforge/data/processors/resampler.py`:

```python
import pandas as pd
from algoforge.core.models import OHLCV
from algoforge.core.constants import Timeframe
import structlog

logger = structlog.get_logger()

# Ordered from smallest to largest
TIMEFRAME_ORDER = [
    Timeframe.M1, Timeframe.M5, Timeframe.M15, Timeframe.M30,
    Timeframe.H1, Timeframe.H4, Timeframe.D1, Timeframe.W1, Timeframe.MO1,
]

# Pandas resample frequency strings
RESAMPLE_FREQ = {
    Timeframe.M5: "5min", Timeframe.M15: "15min", Timeframe.M30: "30min",
    Timeframe.H1: "1h", Timeframe.H4: "4h", Timeframe.D1: "1D",
    Timeframe.W1: "1W", Timeframe.MO1: "1ME",
}

# OHLCV aggregation rules
OHLCV_AGG = {
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last",
    "volume": "sum",
}

class Resampler:
    """Multi-timeframe OHLCV resampler.
    
    Takes candles at a base timeframe and produces higher timeframe candles.
    Rules: Open=first, High=max, Low=min, Close=last, Volume=sum.
    """
    
    def resample(
        self, candles: list[OHLCV], target_timeframe: Timeframe
    ) -> list[OHLCV]:
        """Resample candles from their current timeframe to a higher timeframe."""
        if not candles:
            return []
        
        source_tf = candles[0].timeframe
        symbol = candles[0].symbol
        
        # Validate: target must be higher than source
        source_idx = TIMEFRAME_ORDER.index(source_tf)
        target_idx = TIMEFRAME_ORDER.index(target_timeframe)
        if target_idx <= source_idx:
            raise ValueError(
                f"Cannot resample {source_tf.value} to {target_timeframe.value}: "
                f"target must be higher timeframe"
            )
        
        # Convert to DataFrame
        df = pd.DataFrame([c.model_dump() for c in candles])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp").sort_index()
        
        # Resample
        freq = RESAMPLE_FREQ[target_timeframe]
        resampled = df[["open", "high", "low", "close", "volume"]].resample(freq).agg(OHLCV_AGG)
        resampled = resampled.dropna()
        
        # Convert back to OHLCV models
        result = []
        for ts, row in resampled.iterrows():
            candle = OHLCV(
                symbol=symbol,
                timeframe=target_timeframe,
                timestamp=ts.to_pydatetime(),
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )
            result.append(candle)
        
        logger.info("resampler.complete", symbol=symbol, 
                    source=source_tf.value, target=target_timeframe.value,
                    input_count=len(candles), output_count=len(result))
        return result
    
    def resample_to_all(
        self, candles: list[OHLCV], target_timeframes: list[Timeframe]
    ) -> dict[Timeframe, list[OHLCV]]:
        """Resample to multiple target timeframes at once."""
        results = {}
        for tf in target_timeframes:
            try:
                results[tf] = self.resample(candles, tf)
            except ValueError as e:
                logger.warning("resampler.skip", timeframe=tf.value, error=str(e))
        return results
```
</action>

<acceptance_criteria>
- resampler.py contains `class Resampler` with methods: resample, resample_to_all
- resampler.py uses pandas resample with OHLCV_AGG rules (open=first, high=max, low=min, close=last, volume=sum)
- resampler.py validates target timeframe > source timeframe
- resampler.py raises ValueError if target is lower than source
- RESAMPLE_FREQ dict maps Timeframe enum values to pandas frequency strings
- resample returns list[OHLCV] with correct symbol and target timeframe
</acceptance_criteria>
</task>

<task id="03-04">
## Task 4: Create tests for Redis store, yfinance feed, and resampler

<read_first>
- src/algoforge/data/storage/redis_store.py (Redis store)
- src/algoforge/data/feeds/yfinance_feed.py (yfinance adapter)
- src/algoforge/data/processors/resampler.py (resampler)
</read_first>

<action>
Create `tests/unit/test_redis_store.py`:
1. `test_store_and_retrieve_candle` — store a candle, retrieve it by time range
2. `test_store_candles_batch` — store multiple candles via pipelining
3. `test_get_latest_candle` — get most recent candle
4. `test_get_candle_count` — count stored candles
5. `test_empty_retrieval` — no candles returns empty list

Use `fakeredis.aioredis` for unit tests (no real Redis needed).

Create `tests/unit/test_yfinance_feed.py`:
1. `test_timeframe_mapping` — all Timeframe enum values have yfinance mappings
2. `test_normalize_dataframe` — yfinance DataFrame converts to list[OHLCV]
3. `test_empty_response_handling` — empty yfinance response returns empty list

Create `tests/unit/test_resampler.py`:
1. `test_resample_1m_to_5m` — 5 one-minute candles → 1 five-minute candle with correct OHLCV aggregation
2. `test_resample_preserves_ohlcv_rules` — High = max of all highs, Low = min of all lows
3. `test_resample_lower_timeframe_raises` — resampling to lower timeframe raises ValueError
4. `test_resample_to_all` — multiple target timeframes produce correct output
5. `test_resample_empty_input` — empty candle list returns empty list
</action>

<acceptance_criteria>
- tests/unit/test_redis_store.py contains at least 4 test functions
- tests/unit/test_yfinance_feed.py contains at least 2 test functions
- tests/unit/test_resampler.py contains at least 4 test functions
- test_resampler.py verifies OHLCV aggregation rules (high=max, low=min)
- Running `pytest tests/unit/test_resampler.py` exits 0
</acceptance_criteria>
</task>

<verification>
## Verification Criteria

### must_haves
- [ ] Redis store connects, stores, and retrieves OHLCV candles
- [ ] yfinance feed fetches and normalizes market data to OHLCV format
- [ ] Resampler produces correct multi-timeframe candles from base timeframe
- [ ] Data pipeline: yfinance → OHLCV → Redis → retrieval works end-to-end
- [ ] All unit tests pass
</verification>
