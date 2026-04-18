"""Tests for the async event bus."""

import asyncio

import pytest

from algoforge.core.event_bus import EventBus, MarketDataEvent, SystemEvent


class TestEventBus:
    """Test event bus pub/sub functionality."""

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self) -> None:
        """Handler receives published event."""
        bus = EventBus()
        received: list = []

        async def handler(event: MarketDataEvent) -> None:
            received.append(event)

        bus.subscribe("market_data", handler)
        await bus.publish(MarketDataEvent(symbol="AAPL", timeframe="1m"))

        # Manually dispatch (not using start loop for unit test)
        event = await asyncio.wait_for(bus._queue.get(), timeout=1.0)
        await bus._dispatch(event)

        assert len(received) == 1
        assert received[0].symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self) -> None:
        """All subscribers receive the event."""
        bus = EventBus()
        received_a: list = []
        received_b: list = []

        async def handler_a(event: MarketDataEvent) -> None:
            received_a.append(event)

        async def handler_b(event: MarketDataEvent) -> None:
            received_b.append(event)

        bus.subscribe("market_data", handler_a)
        bus.subscribe("market_data", handler_b)

        event = MarketDataEvent(symbol="MSFT", timeframe="5m")
        await bus.publish(event)
        queued = await asyncio.wait_for(bus._queue.get(), timeout=1.0)
        await bus._dispatch(queued)

        assert len(received_a) == 1
        assert len(received_b) == 1

    @pytest.mark.asyncio
    async def test_handler_error_doesnt_crash(self) -> None:
        """Exception in one handler doesn't affect others."""
        bus = EventBus()
        received: list = []

        async def failing_handler(event: MarketDataEvent) -> None:
            raise RuntimeError("boom")

        async def good_handler(event: MarketDataEvent) -> None:
            received.append(event)

        bus.subscribe("market_data", failing_handler)
        bus.subscribe("market_data", good_handler)

        event = MarketDataEvent(symbol="GOOGL", timeframe="1m")
        await bus.publish(event)
        queued = await asyncio.wait_for(bus._queue.get(), timeout=1.0)
        await bus._dispatch(queued)

        # Good handler still received the event despite the other one crashing
        assert len(received) == 1
        assert bus.stats["errors"] == 1

    @pytest.mark.asyncio
    async def test_event_type_routing(self) -> None:
        """Events only go to matching subscribers."""
        bus = EventBus()
        market_received: list = []
        system_received: list = []

        async def market_handler(event: MarketDataEvent) -> None:
            market_received.append(event)

        async def system_handler(event: SystemEvent) -> None:
            system_received.append(event)

        bus.subscribe("market_data", market_handler)
        bus.subscribe("system", system_handler)

        # Publish market data event
        await bus.publish(MarketDataEvent(symbol="TSLA", timeframe="1m"))
        event = await asyncio.wait_for(bus._queue.get(), timeout=1.0)
        await bus._dispatch(event)

        assert len(market_received) == 1
        assert len(system_received) == 0

    @pytest.mark.asyncio
    async def test_unsubscribe(self) -> None:
        """Unsubscribed handler no longer receives events."""
        bus = EventBus()
        received: list = []

        async def handler(event: MarketDataEvent) -> None:
            received.append(event)

        bus.subscribe("market_data", handler)
        assert bus.subscriber_count == 1

        removed = bus.unsubscribe("market_data", handler)
        assert removed is True
        assert bus.subscriber_count == 0

    @pytest.mark.asyncio
    async def test_publish_nowait_full_queue(self) -> None:
        """publish_nowait returns False when queue is full."""
        bus = EventBus(max_queue_size=1)
        event = SystemEvent(action="test", message="test")

        # First should succeed
        assert bus.publish_nowait(event) is True
        # Second should fail (queue size 1)
        assert bus.publish_nowait(event) is False

    @pytest.mark.asyncio
    async def test_stop_drains_queue(self) -> None:
        """Stopping the bus drains remaining events."""
        bus = EventBus()
        received: list = []

        async def handler(event: SystemEvent) -> None:
            received.append(event)

        bus.subscribe("system", handler)
        await bus.publish(SystemEvent(action="test", message="drain-me"))

        await bus.stop()
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_stats_tracking(self) -> None:
        """Event bus tracks publish/dispatch/error counts."""
        bus = EventBus()

        async def noop(event: MarketDataEvent) -> None:
            pass

        bus.subscribe("market_data", noop)
        await bus.publish(MarketDataEvent(symbol="X", timeframe="1m"))

        event = await asyncio.wait_for(bus._queue.get(), timeout=1.0)
        await bus._dispatch(event)

        assert bus.stats["published"] == 1
        assert bus.stats["dispatched"] == 1
        assert bus.stats["errors"] == 0
