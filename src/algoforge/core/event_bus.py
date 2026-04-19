"""AlgoForge async event bus v2.

Hybrid event transport: asyncio.Queue for hot dispatch (<1ms) +
Redis Streams for durable persistence/replay. Pydantic event schema
with hierarchical correlation IDs for full DAG traceability.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()

# Type alias for async event handlers
EventHandler = Callable[["Event"], Coroutine[Any, Any, None]]


# ---------------------------------------------------------------------------
# Pydantic Event Types (v2 — migrated from dataclass)
# ---------------------------------------------------------------------------


class Event(BaseModel):
    """Base event class — all events inherit from this.

    Hierarchical correlation:
      - event_id: unique ID for THIS event
      - parent_id: ID of the event that caused this one (None for root events)
      - correlation_id: root event_id of the entire chain (for lifecycle filtering)
    """

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: str | None = Field(default=None, description="ID of the causing event")
    correlation_id: str | None = Field(default=None, description="Root event ID of the chain")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str = ""

    def model_post_init(self, __context: Any) -> None:
        """Auto-set correlation_id to event_id if this is a root event."""
        if self.correlation_id is None:
            self.correlation_id = self.event_id

    def spawn_child(self, child_cls: type["Event"], **kwargs: Any) -> "Event":
        """Create a child event inheriting correlation context.

        The child's parent_id = this event's event_id.
        The child's correlation_id = this event's correlation_id (root).
        """
        return child_cls(
            parent_id=self.event_id,
            correlation_id=self.correlation_id,
            **kwargs,
        )


class MarketDataEvent(Event):
    """Published when new OHLCV data arrives from a feed."""

    symbol: str = ""
    timeframe: str = ""
    candle: Any = None  # OHLCV model instance
    event_type: str = "market_data"


class SystemEvent(Event):
    """System lifecycle events — startup, shutdown, errors, config changes."""

    action: str = ""  # startup, shutdown, error, config_reload, health_check
    message: str = ""
    severity: str = "info"  # info, warning, error, critical
    event_type: str = "system"


class SignalEvent(Event):
    """Published when a strategy generates a trading signal."""

    signal: Any = None  # Signal model instance
    event_type: str = "signal"


class OrderEvent(Event):
    """Published when an order is placed/filled/cancelled."""

    order_id: str = ""
    action: str = ""  # placed, filled, cancelled, rejected
    details: dict = Field(default_factory=dict)
    event_type: str = "order"


class FillEvent(Event):
    """Published when an order is filled (partial or complete)."""

    order_id: str = ""
    fill_price: float = 0.0
    fill_quantity: float = 0.0
    commission: float = 0.0
    event_type: str = "fill"


class RiskEvent(Event):
    """Published when risk management takes action."""

    action: str = ""  # veto, alert, margin_call, position_close
    reason: str = ""
    details: dict = Field(default_factory=dict)
    event_type: str = "risk"


# ---------------------------------------------------------------------------
# Redis Streams Persistence Layer
# ---------------------------------------------------------------------------


class RedisStreamWriter:
    """Async writer that persists events to Redis Streams.

    Events are written asynchronously — does not block the hot dispatch path.
    Streams are keyed by event_type: 'events:{event_type}'.
    """

    STREAM_PREFIX = "events"
    MAX_STREAM_LEN = 100_000  # Max entries per stream (MAXLEN ~)

    def __init__(self, redis_client: Any | None = None) -> None:
        self._client = redis_client
        self._connected = redis_client is not None
        self._buffer: list[Event] = []
        self._buffer_size = 50  # Flush after N events
        self._stats = {"written": 0, "errors": 0}

    async def connect(self, redis_client: Any) -> None:
        """Set the Redis client for Streams writes."""
        self._client = redis_client
        self._connected = True
        logger.info("redis_stream_writer.connected")

    async def write_event(self, event: Event) -> None:
        """Write a single event to the appropriate Redis Stream."""
        if not self._connected or self._client is None:
            return

        stream_key = f"{self.STREAM_PREFIX}:{event.event_type}"
        try:
            data = {
                "event_id": event.event_id,
                "parent_id": event.parent_id or "",
                "correlation_id": event.correlation_id or "",
                "timestamp": event.timestamp.isoformat(),
                "payload": event.model_dump_json(),
            }
            await self._client.xadd(
                stream_key,
                data,
                maxlen=self.MAX_STREAM_LEN,
                approximate=True,
            )
            self._stats["written"] += 1
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(
                "redis_stream_writer.write_error",
                stream=stream_key,
                error=str(e),
            )

    async def write_batch(self, events: list[Event]) -> None:
        """Write multiple events using Redis pipeline."""
        if not self._connected or self._client is None or not events:
            return

        try:
            pipe = self._client.pipeline()
            for event in events:
                stream_key = f"{self.STREAM_PREFIX}:{event.event_type}"
                data = {
                    "event_id": event.event_id,
                    "parent_id": event.parent_id or "",
                    "correlation_id": event.correlation_id or "",
                    "timestamp": event.timestamp.isoformat(),
                    "payload": event.model_dump_json(),
                }
                pipe.xadd(stream_key, data, maxlen=self.MAX_STREAM_LEN, approximate=True)
            await pipe.execute()
            self._stats["written"] += len(events)
        except Exception as e:
            self._stats["errors"] += 1
            logger.error("redis_stream_writer.batch_error", count=len(events), error=str(e))

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._stats)


# ---------------------------------------------------------------------------
# Instrument Worker Pool
# ---------------------------------------------------------------------------


class WorkerPool:
    """Configurable async worker pool for concurrent instrument processing.

    Workers pull tasks from a shared queue. Queue depth serves as a
    natural backpressure signal and health metric.
    """

    def __init__(
        self,
        pool_size: int = 20,
        max_queue_size: int = 10000,
        backpressure_threshold: int = 5000,
    ) -> None:
        self._pool_size = pool_size
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._backpressure_threshold = backpressure_threshold
        self._workers: list[asyncio.Task] = []
        self._running = False
        self._stats = {"processed": 0, "errors": 0, "backpressure_events": 0}

    @property
    def queue_depth(self) -> int:
        """Current number of items waiting in the work queue."""
        return self._queue.qsize()

    @property
    def is_backpressured(self) -> bool:
        """True if queue depth exceeds threshold."""
        return self.queue_depth > self._backpressure_threshold

    @property
    def stats(self) -> dict[str, Any]:
        return {
            **self._stats,
            "pool_size": self._pool_size,
            "queue_depth": self.queue_depth,
            "backpressured": self.is_backpressured,
        }

    async def submit(self, coro_func: Callable, *args: Any) -> None:
        """Submit a coroutine function + args to the worker queue."""
        await self._queue.put((coro_func, args))
        if self.is_backpressured:
            self._stats["backpressure_events"] += 1
            logger.warning(
                "worker_pool.backpressure",
                queue_depth=self.queue_depth,
                threshold=self._backpressure_threshold,
            )

    async def start(self) -> None:
        """Start N worker tasks."""
        self._running = True
        for i in range(self._pool_size):
            task = asyncio.create_task(self._worker_loop(i))
            self._workers.append(task)
        logger.info("worker_pool.started", pool_size=self._pool_size)

    async def stop(self) -> None:
        """Stop all workers and drain remaining tasks."""
        self._running = False
        # Cancel all workers
        for worker in self._workers:
            worker.cancel()
        # Wait for graceful shutdown
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info(
            "worker_pool.stopped",
            processed=self._stats["processed"],
            errors=self._stats["errors"],
        )

    async def _worker_loop(self, worker_id: int) -> None:
        """Single worker loop — pulls tasks and executes them."""
        while self._running:
            try:
                coro_func, args = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                try:
                    await coro_func(*args)
                    self._stats["processed"] += 1
                except Exception as e:
                    self._stats["errors"] += 1
                    logger.error(
                        "worker_pool.task_error",
                        worker=worker_id,
                        error=str(e),
                    )
                finally:
                    self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break


# ---------------------------------------------------------------------------
# Event Bus v2 (Hybrid Transport)
# ---------------------------------------------------------------------------


class EventBus:
    """Async event bus with hybrid transport.

    Hot path: asyncio.Queue → immediate handler dispatch (<1ms).
    Durable path: async write to Redis Streams for audit/replay.

    Components subscribe to event types and receive events asynchronously.
    Error in one handler does not affect others — the bus is fault-tolerant.

    Usage:
        bus = EventBus()

        async def on_market_data(event: MarketDataEvent):
            print(f"New candle: {event.symbol}")

        bus.subscribe("market_data", on_market_data)
        await bus.publish(MarketDataEvent(symbol="AAPL", timeframe="1m"))
    """

    def __init__(
        self,
        max_queue_size: int = 10000,
        redis_client: Any | None = None,
        enable_streams: bool = True,
    ) -> None:
        self._subscribers: dict[str, list[EventHandler]] = {}
        self._queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=max_queue_size)
        self._running = False
        self._enable_streams = enable_streams
        self._stream_writer = RedisStreamWriter(redis_client=redis_client)
        self._stats: dict[str, int] = {
            "published": 0,
            "dispatched": 0,
            "errors": 0,
        }

    @property
    def subscriber_count(self) -> int:
        """Total number of registered handlers across all event types."""
        return sum(len(handlers) for handlers in self._subscribers.values())

    @property
    def stats(self) -> dict[str, int]:
        """Event bus statistics."""
        return dict(self._stats)

    @property
    def stream_stats(self) -> dict[str, int]:
        """Redis Streams writer statistics."""
        return self._stream_writer.stats

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe a handler to an event type.

        Args:
            event_type: Type of event to subscribe to (e.g., "market_data")
            handler: Async function that receives the event
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        logger.info(
            "event_bus.subscribe",
            event_type=event_type,
            handler=handler.__qualname__,
            total_subscribers=self.subscriber_count,
        )

    def unsubscribe(self, event_type: str, handler: EventHandler) -> bool:
        """Remove a handler from an event type.

        Returns True if the handler was found and removed.
        """
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
                logger.info("event_bus.unsubscribe", event_type=event_type)
                return True
            except ValueError:
                return False
        return False

    async def publish(self, event: Event) -> None:
        """Publish an event to the queue for async dispatch.

        Also writes to Redis Streams if enabled (async, non-blocking).
        """
        await self._queue.put(event)
        self._stats["published"] += 1

        # Async write to Redis Streams (fire-and-forget)
        if self._enable_streams and self._stream_writer._connected:
            asyncio.create_task(self._stream_writer.write_event(event))

    def publish_nowait(self, event: Event) -> bool:
        """Publish without waiting — returns False if queue is full."""
        try:
            self._queue.put_nowait(event)
            self._stats["published"] += 1

            if self._enable_streams and self._stream_writer._connected:
                asyncio.create_task(self._stream_writer.write_event(event))

            return True
        except asyncio.QueueFull:
            logger.warning("event_bus.queue_full", event_type=event.event_type)
            return False

    async def _dispatch(self, event: Event) -> None:
        """Dispatch event to all matching subscribers."""
        handlers = self._subscribers.get(event.event_type, [])
        if not handlers:
            return

        for handler in handlers:
            try:
                await handler(event)
                self._stats["dispatched"] += 1
            except Exception as e:
                self._stats["errors"] += 1
                logger.error(
                    "event_bus.handler_error",
                    event_type=event.event_type,
                    handler=handler.__qualname__,
                    event_id=event.event_id,
                    correlation_id=event.correlation_id,
                    error=str(e),
                    exc_info=True,
                )

    async def start(self) -> None:
        """Start processing events from the queue.

        Runs until stop() is called. Drains remaining events on shutdown.
        """
        self._running = True
        logger.info("event_bus.started", queue_size=self._queue.maxsize)

        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._dispatch(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error("event_bus.loop_error", error=str(e))

    async def stop(self) -> None:
        """Stop the event bus and drain remaining events."""
        self._running = False

        # Drain remaining events
        drained = 0
        while not self._queue.empty():
            try:
                event = self._queue.get_nowait()
                await self._dispatch(event)
                drained += 1
            except asyncio.QueueEmpty:
                break

        logger.info(
            "event_bus.stopped",
            drained=drained,
            total_published=self._stats["published"],
            total_dispatched=self._stats["dispatched"],
            total_errors=self._stats["errors"],
        )

    @property
    def is_running(self) -> bool:
        """True if the event bus is currently processing events."""
        return self._running
