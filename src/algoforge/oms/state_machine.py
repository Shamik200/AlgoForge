"""Deterministic state machine for order lifecycle transitions."""

from algoforge.oms.models import OrderStatus, Order

# Valid transitions: current_state -> set of allowed next states
VALID_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.NEW: {OrderStatus.SUBMITTED, OrderStatus.REJECTED, OrderStatus.CANCELLED},
    OrderStatus.SUBMITTED: {OrderStatus.PARTIAL_FILL, OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED},
    OrderStatus.PARTIAL_FILL: {OrderStatus.FILLED, OrderStatus.CANCELLED},
}
# Terminal states (FILLED, CANCELLED, REJECTED) have no outgoing transitions.


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


def transition(order: Order, new_status: OrderStatus) -> Order:
    """Transition an order to a new status.

    Args:
        order: The order to transition.
        new_status: The target status.

    Returns:
        The order with its status updated.

    Raises:
        InvalidTransitionError: If the transition is not allowed.
    """
    if order.is_terminal:
        raise InvalidTransitionError(
            f"Order {order.correlation_id} is in terminal state {order.status.value}. "
            f"Cannot transition to {new_status.value}."
        )

    allowed = VALID_TRANSITIONS.get(order.status, set())
    if new_status not in allowed:
        raise InvalidTransitionError(
            f"Invalid transition: {order.status.value} -> {new_status.value} "
            f"for order {order.correlation_id}. "
            f"Allowed: {[s.value for s in allowed]}"
        )

    from datetime import datetime, timezone
    order.status = new_status
    order.updated_at = datetime.now(timezone.utc)
    return order
