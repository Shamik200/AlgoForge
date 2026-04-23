"""Core data models for the Order Management System."""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class OrderStatus(str, Enum):
    """Lifecycle states for an order."""
    NEW = "new"
    SUBMITTED = "submitted"
    PARTIAL_FILL = "partial_fill"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class OrderType(str, Enum):
    """Type of order to submit to the exchange."""
    LIMIT = "limit"
    MARKET = "market"


# Terminal states — once an order reaches one of these, it cannot transition further.
TERMINAL_STATES = frozenset({OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED})


class Order(BaseModel):
    """A single order in the OMS lifecycle."""

    correlation_id: str
    symbol: str
    direction: str  # "long" or "short"
    order_type: OrderType
    price: float = 0.0
    quantity: float = Field(..., gt=0)
    status: OrderStatus = OrderStatus.NEW

    # Candle expiry tracking
    max_candles: int = 3
    elapsed_candles: int = 0

    # Audit timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_terminal(self) -> bool:
        """Check if the order has reached a terminal state."""
        return self.status in TERMINAL_STATES
