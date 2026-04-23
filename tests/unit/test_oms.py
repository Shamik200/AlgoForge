"""Unit tests for the Order Management System."""

import pytest

from algoforge.oms.models import Order, OrderStatus, OrderType
from algoforge.oms.state_machine import transition, InvalidTransitionError
from algoforge.oms.store import OrderStore
from algoforge.oms.manager import OrderManager


# --- State Machine Tests ---

def test_valid_transition_new_to_submitted():
    """Test NEW -> SUBMITTED is allowed."""
    order = Order(correlation_id="test-1", symbol="AAPL", direction="long",
                  order_type=OrderType.LIMIT, price=150.0, quantity=10)
    result = transition(order, OrderStatus.SUBMITTED)
    assert result.status == OrderStatus.SUBMITTED


def test_valid_transition_submitted_to_filled():
    """Test SUBMITTED -> FILLED is allowed."""
    order = Order(correlation_id="test-2", symbol="AAPL", direction="long",
                  order_type=OrderType.LIMIT, price=150.0, quantity=10,
                  status=OrderStatus.SUBMITTED)
    result = transition(order, OrderStatus.FILLED)
    assert result.status == OrderStatus.FILLED


def test_invalid_transition_filled_to_cancelled():
    """Test FILLED (terminal) -> CANCELLED is blocked."""
    order = Order(correlation_id="test-3", symbol="AAPL", direction="long",
                  order_type=OrderType.LIMIT, price=150.0, quantity=10,
                  status=OrderStatus.FILLED)
    with pytest.raises(InvalidTransitionError):
        transition(order, OrderStatus.CANCELLED)


def test_invalid_transition_new_to_filled():
    """Test NEW -> FILLED (skipping SUBMITTED) is blocked."""
    order = Order(correlation_id="test-4", symbol="AAPL", direction="long",
                  order_type=OrderType.LIMIT, price=150.0, quantity=10)
    with pytest.raises(InvalidTransitionError):
        transition(order, OrderStatus.FILLED)


# --- SQLite Store Tests ---

def test_store_round_trip():
    """Test saving and loading an order from SQLite."""
    store = OrderStore(db_path=":memory:")
    order = Order(correlation_id="rt-1", symbol="TSLA", direction="short",
                  order_type=OrderType.MARKET, price=200.0, quantity=5,
                  status=OrderStatus.SUBMITTED)
    store.save_order(order)

    loaded = store.get_order_by_correlation_id("rt-1")
    assert loaded is not None
    assert loaded.symbol == "TSLA"
    assert loaded.status == OrderStatus.SUBMITTED
    store.close()


def test_store_get_active_orders():
    """Test that only non-terminal orders are returned."""
    store = OrderStore(db_path=":memory:")

    active_order = Order(correlation_id="active-1", symbol="AAPL", direction="long",
                         order_type=OrderType.LIMIT, price=150.0, quantity=10,
                         status=OrderStatus.SUBMITTED)
    filled_order = Order(correlation_id="filled-1", symbol="GOOG", direction="long",
                         order_type=OrderType.LIMIT, price=2800.0, quantity=2,
                         status=OrderStatus.FILLED)
    store.save_order(active_order)
    store.save_order(filled_order)

    active = store.get_active_orders()
    assert len(active) == 1
    assert active[0].correlation_id == "active-1"
    store.close()


# --- OMS Manager Tests ---

def test_idempotent_submission():
    """Test that duplicate correlation IDs are silently dropped."""
    store = OrderStore(db_path=":memory:")
    mgr = OrderManager(store)

    order1 = Order(correlation_id="idem-1", symbol="AAPL", direction="long",
                   order_type=OrderType.LIMIT, price=150.0, quantity=10)
    order2 = Order(correlation_id="idem-1", symbol="AAPL", direction="long",
                   order_type=OrderType.LIMIT, price=150.0, quantity=10)

    result1 = mgr.submit_order(order1)
    result2 = mgr.submit_order(order2)

    assert result1 is not None
    assert result2 is None  # Dropped as duplicate
    store.close()


def test_candle_expiry():
    """Test that limit orders are cancelled after max_candles."""
    store = OrderStore(db_path=":memory:")
    mgr = OrderManager(store)

    order = Order(correlation_id="exp-1", symbol="AAPL", direction="long",
                  order_type=OrderType.LIMIT, price=150.0, quantity=10,
                  max_candles=3)
    mgr.submit_order(order)

    # Tick 1 and 2: no expiry
    expired = mgr.check_expiry()
    assert len(expired) == 0
    expired = mgr.check_expiry()
    assert len(expired) == 0

    # Tick 3: expiry triggers
    expired = mgr.check_expiry()
    assert len(expired) == 1
    assert expired[0].status == OrderStatus.CANCELLED
    store.close()


def test_fill_order():
    """Test filling a submitted order."""
    store = OrderStore(db_path=":memory:")
    mgr = OrderManager(store)

    order = Order(correlation_id="fill-1", symbol="AAPL", direction="long",
                  order_type=OrderType.LIMIT, price=150.0, quantity=10)
    mgr.submit_order(order)

    filled = mgr.fill_order("fill-1")
    assert filled is not None
    assert filled.status == OrderStatus.FILLED

    # Verify it's no longer in active IDs
    assert "fill-1" not in mgr._active_ids
    store.close()


def test_market_order_not_expired():
    """Test that MARKET orders are never expired by candle expiry."""
    store = OrderStore(db_path=":memory:")
    mgr = OrderManager(store)

    order = Order(correlation_id="mkt-1", symbol="AAPL", direction="long",
                  order_type=OrderType.MARKET, price=150.0, quantity=10,
                  max_candles=1)
    mgr.submit_order(order)

    # Even after exceeding max_candles, market orders should NOT be expired
    expired = mgr.check_expiry()
    assert len(expired) == 0
    store.close()
