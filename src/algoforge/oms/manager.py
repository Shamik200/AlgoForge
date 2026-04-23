"""OMS Manager — orchestrates order submission, idempotency, and candle expiry."""

import logging

from algoforge.oms.models import Order, OrderStatus, OrderType
from algoforge.oms.state_machine import transition, InvalidTransitionError
from algoforge.oms.store import OrderStore

logger = logging.getLogger(__name__)


class OrderManager:
    """Central manager for the Order Management System.

    Handles idempotent order submission, state transitions,
    candle-based limit order expiry, and SQLite persistence.
    """

    def __init__(self, store: OrderStore) -> None:
        """Initialize the OMS Manager.

        Args:
            store: The SQLite-backed OrderStore for persistence.
        """
        self.store = store
        # In-memory index of active correlation IDs for fast idempotency checks
        self._active_ids: set[str] = set()
        self._load_active_orders()

    def _load_active_orders(self) -> None:
        """Restore in-memory state from SQLite on startup."""
        active = self.store.get_active_orders()
        for order in active:
            self._active_ids.add(order.correlation_id)
        logger.info("OMS recovered %d active orders from store.", len(active))

    def submit_order(self, order: Order) -> Order | None:
        """Submit a new order with idempotency enforcement.

        If a non-terminal order with the same correlation_id already exists,
        the submission is silently dropped.

        Args:
            order: The Order to submit.

        Returns:
            The submitted Order, or None if it was a duplicate.
        """
        # Idempotency guard
        if order.correlation_id in self._active_ids:
            logger.warning(
                "Duplicate order dropped: correlation_id=%s symbol=%s",
                order.correlation_id, order.symbol,
            )
            return None

        existing = self.store.get_order_by_correlation_id(order.correlation_id)
        if existing is not None:
            logger.warning(
                "Duplicate order dropped (from store): correlation_id=%s",
                order.correlation_id,
            )
            return None

        # Transition to SUBMITTED
        order = transition(order, OrderStatus.SUBMITTED)

        # Persist and track
        self.store.save_order(order)
        self._active_ids.add(order.correlation_id)

        logger.info(
            "Order submitted: %s %s %s @ %.4f qty=%.4f",
            order.correlation_id, order.symbol, order.order_type.value,
            order.price, order.quantity,
        )
        return order

    def fill_order(self, correlation_id: str) -> Order | None:
        """Mark an order as fully filled.

        Args:
            correlation_id: The correlation ID of the order to fill.

        Returns:
            The filled Order, or None if not found.
        """
        order = self.store.get_order_by_correlation_id(correlation_id)
        if order is None:
            logger.error("fill_order: no order found for %s", correlation_id)
            return None

        order = transition(order, OrderStatus.FILLED)
        self.store.update_order(order)
        self._active_ids.discard(correlation_id)

        logger.info("Order filled: %s", correlation_id)
        return order

    def cancel_order(self, correlation_id: str) -> Order | None:
        """Cancel an active order.

        Args:
            correlation_id: The correlation ID of the order to cancel.

        Returns:
            The cancelled Order, or None if not found.
        """
        order = self.store.get_order_by_correlation_id(correlation_id)
        if order is None:
            logger.error("cancel_order: no order found for %s", correlation_id)
            return None

        try:
            order = transition(order, OrderStatus.CANCELLED)
        except InvalidTransitionError:
            logger.warning("Cannot cancel order %s in state %s", correlation_id, order.status.value)
            return None

        self.store.update_order(order)
        self._active_ids.discard(correlation_id)

        logger.info("Order cancelled: %s", correlation_id)
        return order

    def check_expiry(self) -> list[Order]:
        """Increment elapsed candles and cancel expired limit orders.

        Should be called once per candle close.

        Returns:
            List of orders that were cancelled due to expiry.
        """
        active_orders = self.store.get_active_orders()
        expired: list[Order] = []

        for order in active_orders:
            order.elapsed_candles += 1

            # Only expire unfilled LIMIT orders
            if (
                order.order_type == OrderType.LIMIT
                and order.status in (OrderStatus.SUBMITTED, OrderStatus.PARTIAL_FILL)
                and order.elapsed_candles >= order.max_candles
            ):
                try:
                    order = transition(order, OrderStatus.CANCELLED)
                    self.store.update_order(order)
                    self._active_ids.discard(order.correlation_id)
                    expired.append(order)
                    logger.info(
                        "Order expired and cancelled: %s after %d candles",
                        order.correlation_id, order.elapsed_candles,
                    )
                except InvalidTransitionError:
                    pass
            else:
                # Just persist the incremented candle count
                self.store.update_order(order)

        return expired
