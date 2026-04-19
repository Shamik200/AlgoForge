"""Tests for Event Bus v2 — Pydantic events, correlation IDs, hybrid transport, worker pool."""

import asyncio

import pytest

from algoforge.core.event_bus import (
    Event,
    EventBus,
    FillEvent,
    MarketDataEvent,
    OrderEvent,
    RedisStreamWriter,
    RiskEvent,
    SignalEvent,
    SystemEvent,
    WorkerPool,
)


# ---------------------------------------------------------------------------
# Event Schema Tests (Pydantic migration)
# ---------------------------------------------------------------------------


class TestPydanticEvents:
    """All event types are Pydantic BaseModel with hierarchical IDs."""

    def test_event_has_uuid(self) -> None:
        event = Event()
        assert event.event_id is not None
        assert len(event.event_id) == 36  # UUID format

    def test_event_auto_correlation_id(self) -> None:
        """Root events have correlation_id == event_id."""
        event = Event()
        assert event.correlation_id == event.event_id

    def test_event_parent_id_default_none(self) -> None:
        event = Event()
        assert event.parent_id is None

    def test_event_timestamp_utc(self) -> None:
        event = Event()
        assert event.timestamp.tzinfo is not None

    def test_market_data_event_fields(self) -> None:
        event = MarketDataEvent(symbol="AAPL", timeframe="1m")
        assert event.symbol == "AAPL"
        assert event.timeframe == "1m"
        assert event.event_type == "market_data"

    def test_system_event_fields(self) -> None:
        event = SystemEvent(action="startup", message="hello", severity="info")
        assert event.action == "startup"
        assert event.event_type == "system"

    def test_signal_event_type(self) -> None:
        event = SignalEvent()
        assert event.event_type == "signal"

    def test_order_event_type(self) -> None:
        event = OrderEvent(order_id="ord-1", action="placed")
        assert event.event_type == "order"

    def test_fill_event_type(self) -> None:
        event = FillEvent(order_id="ord-1", fill_price=150.0, fill_quantity=10.0)
        assert event.event_type == "fill"
        assert event.fill_price == 150.0

    def test_risk_event_type(self) -> None:
        event = RiskEvent(action="veto", reason="max drawdown")
        assert event.event_type == "risk"

    def test_event_json_serialization(self) -> None:
        """All events serialize to JSON via Pydantic."""
        event = MarketDataEvent(symbol="BTC", timeframe="5m")
        json_str = event.model_dump_json()
        assert "BTC" in json_str
        assert "event_id" in json_str
        assert "correlation_id" in json_str

    def test_event_json_roundtrip(self) -> None:
        """Serialize → deserialize produces equivalent event."""
        original = MarketDataEvent(symbol="ETH", timeframe="1h")
        json_str = original.model_dump_json()
        restored = MarketDataEvent.model_validate_json(json_str)
        assert restored.symbol == original.symbol
        assert restored.event_id == original.event_id
        assert restored.correlation_id == original.correlation_id


# ---------------------------------------------------------------------------
# Hierarchical Correlation ID Tests
# ---------------------------------------------------------------------------


class TestCorrelationIDs:
    """Hierarchical parent_id / correlation_id propagation."""

    def test_spawn_child_sets_parent_id(self) -> None:
        parent = MarketDataEvent(symbol="AAPL", timeframe="1m")
        child = parent.spawn_child(SignalEvent)
        assert child.parent_id == parent.event_id

    def test_spawn_child_inherits_correlation_id(self) -> None:
        root = MarketDataEvent(symbol="AAPL", timeframe="1m")
        child = root.spawn_child(SignalEvent)
        assert child.correlation_id == root.correlation_id

    def test_grandchild_preserves_root_correlation(self) -> None:
        root = MarketDataEvent(symbol="AAPL", timeframe="1m")
        signal = root.spawn_child(SignalEvent)
        order = signal.spawn_child(OrderEvent, order_id="ord-1", action="placed")
        assert order.correlation_id == root.event_id
        assert order.parent_id == signal.event_id

    def test_spawn_child_gets_own_event_id(self) -> None:
        parent = MarketDataEvent(symbol="AAPL", timeframe="1m")
        child = parent.spawn_child(SignalEvent)
        assert child.event_id != parent.event_id

    def test_spawn_child_with_kwargs(self) -> None:
        parent = MarketDataEvent(symbol="AAPL", timeframe="1m")
        child = parent.spawn_child(OrderEvent, order_id="ord-99", action="placed")
        assert child.order_id == "ord-99"
        assert child.action == "placed"

    def test_multiple_children_same_parent(self) -> None:
        """One candle can trigger multiple signals."""
        root = MarketDataEvent(symbol="AAPL", timeframe="1m")
        sig1 = root.spawn_child(SignalEvent)
        sig2 = root.spawn_child(SignalEvent)
        assert sig1.parent_id == sig2.parent_id == root.event_id
        assert sig1.event_id != sig2.event_id
        assert sig1.correlation_id == sig2.correlation_id == root.event_id


# ---------------------------------------------------------------------------
# EventBus v2 Tests (backward compat + new features)
# ---------------------------------------------------------------------------


class TestEventBusV2:
    """EventBus v2 with Pydantic events — backward compatible API."""

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self) -> None:
        bus = EventBus(enable_streams=False)
        received: list = []

        async def handler(event: MarketDataEvent) -> None:
            received.append(event)

        bus.subscribe("market_data", handler)
        await bus.publish(MarketDataEvent(symbol="AAPL", timeframe="1m"))

        event = await asyncio.wait_for(bus._queue.get(), timeout=1.0)
        await bus._dispatch(event)

        assert len(received) == 1
        assert received[0].symbol == "AAPL"
        assert received[0].event_id is not None

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self) -> None:
        bus = EventBus(enable_streams=False)
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
        bus = EventBus(enable_streams=False)
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

        assert len(received) == 1
        assert bus.stats["errors"] == 1

    @pytest.mark.asyncio
    async def test_event_type_routing(self) -> None:
        bus = EventBus(enable_streams=False)
        market_received: list = []
        system_received: list = []

        async def market_handler(event: MarketDataEvent) -> None:
            market_received.append(event)

        async def system_handler(event: SystemEvent) -> None:
            system_received.append(event)

        bus.subscribe("market_data", market_handler)
        bus.subscribe("system", system_handler)

        await bus.publish(MarketDataEvent(symbol="TSLA", timeframe="1m"))
        event = await asyncio.wait_for(bus._queue.get(), timeout=1.0)
        await bus._dispatch(event)

        assert len(market_received) == 1
        assert len(system_received) == 0

    @pytest.mark.asyncio
    async def test_unsubscribe(self) -> None:
        bus = EventBus(enable_streams=False)
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
        bus = EventBus(max_queue_size=1, enable_streams=False)
        event = SystemEvent(action="test", message="test")
        assert bus.publish_nowait(event) is True
        assert bus.publish_nowait(event) is False

    @pytest.mark.asyncio
    async def test_stop_drains_queue(self) -> None:
        bus = EventBus(enable_streams=False)
        received: list = []

        async def handler(event: SystemEvent) -> None:
            received.append(event)

        bus.subscribe("system", handler)
        await bus.publish(SystemEvent(action="test", message="drain-me"))
        await bus.stop()
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_stats_tracking(self) -> None:
        bus = EventBus(enable_streams=False)

        async def noop(event: MarketDataEvent) -> None:
            pass

        bus.subscribe("market_data", noop)
        await bus.publish(MarketDataEvent(symbol="X", timeframe="1m"))

        event = await asyncio.wait_for(bus._queue.get(), timeout=1.0)
        await bus._dispatch(event)

        assert bus.stats["published"] == 1
        assert bus.stats["dispatched"] == 1
        assert bus.stats["errors"] == 0

    @pytest.mark.asyncio
    async def test_dispatch_logs_correlation_id_on_error(self) -> None:
        """Error logging includes event_id and correlation_id."""
        bus = EventBus(enable_streams=False)

        async def bad(event: Event) -> None:
            raise ValueError("fail")

        bus.subscribe("market_data", bad)
        event = MarketDataEvent(symbol="X", timeframe="1m")
        await bus._dispatch(event)
        assert bus.stats["errors"] == 1

    def test_stream_stats_available(self) -> None:
        bus = EventBus(enable_streams=False)
        stats = bus.stream_stats
        assert "written" in stats
        assert "errors" in stats


# ---------------------------------------------------------------------------
# Worker Pool Tests
# ---------------------------------------------------------------------------


class TestWorkerPool:
    """Worker pool for concurrent instrument processing."""

    @pytest.mark.asyncio
    async def test_submit_and_process(self) -> None:
        pool = WorkerPool(pool_size=2, max_queue_size=100)
        results: list[str] = []

        async def task(symbol: str) -> None:
            results.append(symbol)

        await pool.start()
        await pool.submit(task, "AAPL")
        await pool.submit(task, "MSFT")
        await asyncio.sleep(0.5)
        await pool.stop()

        assert "AAPL" in results
        assert "MSFT" in results
        assert pool.stats["processed"] == 2

    @pytest.mark.asyncio
    async def test_pool_error_handling(self) -> None:
        pool = WorkerPool(pool_size=1)
        results: list[str] = []

        async def bad_task() -> None:
            raise RuntimeError("boom")

        async def good_task() -> None:
            results.append("ok")

        await pool.start()
        await pool.submit(bad_task)
        await pool.submit(good_task)
        await asyncio.sleep(0.5)
        await pool.stop()

        assert "ok" in results
        assert pool.stats["errors"] == 1

    def test_backpressure_detection(self) -> None:
        pool = WorkerPool(pool_size=1, max_queue_size=100, backpressure_threshold=5)
        assert pool.is_backpressured is False
        assert pool.queue_depth == 0

    @pytest.mark.asyncio
    async def test_stats(self) -> None:
        pool = WorkerPool(pool_size=2)
        stats = pool.stats
        assert stats["pool_size"] == 2
        assert stats["processed"] == 0
        assert stats["queue_depth"] == 0


# ---------------------------------------------------------------------------
# RedisStreamWriter Tests (without Redis)
# ---------------------------------------------------------------------------


class TestRedisStreamWriter:
    """RedisStreamWriter instantiation and interface."""

    def test_instantiation(self) -> None:
        writer = RedisStreamWriter()
        assert writer._connected is False
        assert writer.stats["written"] == 0

    @pytest.mark.asyncio
    async def test_write_skips_when_disconnected(self) -> None:
        writer = RedisStreamWriter()
        event = MarketDataEvent(symbol="X", timeframe="1m")
        await writer.write_event(event)  # Should not raise
        assert writer.stats["written"] == 0

    @pytest.mark.asyncio
    async def test_batch_write_skips_when_disconnected(self) -> None:
        writer = RedisStreamWriter()
        events = [MarketDataEvent(symbol="X", timeframe="1m")]
        await writer.write_batch(events)  # Should not raise
        assert writer.stats["written"] == 0

    def test_stream_prefix(self) -> None:
        assert RedisStreamWriter.STREAM_PREFIX == "events"


# ---------------------------------------------------------------------------
# Config Tests
# ---------------------------------------------------------------------------


class TestPhase2Config:
    """Settings includes event_bus and worker_pool configs."""

    def test_settings_has_event_bus(self) -> None:
        from algoforge.core.config import EventBusConfig, Settings
        settings = Settings()
        assert hasattr(settings, "event_bus")
        assert isinstance(settings.event_bus, EventBusConfig)
        assert settings.event_bus.max_queue_size == 10000

    def test_settings_has_worker_pool(self) -> None:
        from algoforge.core.config import Settings, WorkerPoolConfig
        settings = Settings()
        assert hasattr(settings, "worker_pool")
        assert isinstance(settings.worker_pool, WorkerPoolConfig)
        assert settings.worker_pool.pool_size == 20

    def test_event_bus_config_defaults(self) -> None:
        from algoforge.core.config import EventBusConfig
        cfg = EventBusConfig()
        assert cfg.enable_streams is True
        assert cfg.stream_max_len == 100000

    def test_worker_pool_config_defaults(self) -> None:
        from algoforge.core.config import WorkerPoolConfig
        cfg = WorkerPoolConfig()
        assert cfg.backpressure_threshold == 5000
