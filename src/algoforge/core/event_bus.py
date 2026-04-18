"""AlgoForge async event bus.

Topic-based pub/sub using asyncio.Queue. All inter-component communication
flows through the event bus — this is the backbone of the event-driven architecture.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

import structlog

logger = structlog.get_logger()

# Type alias for async event handlers
EventHandler = Callable[["Event"], Coroutine[Any, Any, None]]


# ---------------------------------------------------------------------------
# Event Types
# ---------------------------------------------------------------------------


@dataclass
class Event:
    """Base event class — all events inherit from this."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str = ""


@dataclass
class MarketDataEvent(Event):
    """Published when new OHLCV data arrives from a feed."""

    symbol: str = ""
    timeframe: str = ""
    candle: Any = None  # OHLCV model instance
    event_type: str = "market_data"


@dataclass
class SystemEvent(Event):
    """System lifecycle events — startup, shutdown, errors, config changes."""

    action: str = ""  # startup, shutdown, error, config_reload, health_check
    message: str = ""
    severity: str = "info"  # info, warning, error, critical
    event_type: str = "system"


@dataclass
class SignalEvent(Event):
    """Published when a strategy generates a trading signal (Phase 5+)."""

    signal: Any = None  # Signal model instance
    event_type: str = "signal"


@dataclass
class OrderEvent(Event):
    """Published when an order is placed/filled/cancelled (Phase 7+)."""

    order_id: str = ""
    action: str = ""  # placed, filled, cancelled, rejected
    details: dict = field(default_factory=dict)
    event_type: str = "order"


@dataclass
class RiskEvent(Event):
    """Published when risk management takes action (Phase 6+)."""

    action: str = ""  # veto, alert, margin_call, position_close
    reason: str = ""
    details: dict = field(default_factory=dict)
    event_type: str = "risk"


# ---------------------------------------------------------------------------
# Event Bus
# ---------------------------------------------------------------------------


class EventBus:
    """Async event bus with topic-based pub/sub.

    Components subscribe to event types and receive events asynchronously.
    Error in one handler does not affect others — the bus is fault-tolerant.

    Usage:
        bus = EventBus()

        async def on_market_data(event: MarketDataEvent):
            print(f"New candle: {event.symbol}")

        bus.subscribe("market_data", on_market_data)
        await bus.publish(MarketDataEvent(symbol="AAPL", timeframe="1m"))
    """

    def __init__(self, max_queue_size: int = 10000) -> None:
        self._subscribers: dict[str, list[EventHandler]] = {}
        self._queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=max_queue_size)
        self._running = False
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
        """Publish an event to the queue for async dispatch."""
        await self._queue.put(event)
        self._stats["published"] += 1

    def publish_nowait(self, event: Event) -> bool:
        """Publish without waiting — returns False if queue is full."""
        try:
            self._queue.put_nowait(event)
            self._stats["published"] += 1
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
