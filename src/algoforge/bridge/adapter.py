"""Abstract Broker Adapter interface.

All broker integrations (Alpaca, Binance, Zerodha, etc.) implement this ABC.
The engine talks to this interface, never to broker APIs directly.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class OrderResult:
    """Result of an order submission."""
    order_id: str
    status: OrderStatus
    filled_quantity: float
    filled_price: float
    commission: float = 0.0
    message: str = ""


@dataclass
class BrokerPosition:
    """A position as reported by the broker."""
    symbol: str
    quantity: float
    avg_entry_price: float
    current_price: float
    unrealized_pnl: float
    side: str  # "long" or "short"


@dataclass
class AccountInfo:
    """Broker account summary."""
    equity: float
    cash: float
    buying_power: float
    portfolio_value: float
    currency: str = "USD"


class BrokerAdapter(ABC):
    """Abstract base class for all broker integrations.

    Subclass this to add support for a new broker. The engine only
    interacts with this interface, making broker changes a single-file swap.
    """

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the broker API.

        Returns:
            True if connected successfully.
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the broker API."""
        ...

    @abstractmethod
    async def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: float | None = None,
        stop_price: float | None = None,
    ) -> OrderResult:
        """Submit an order to the broker.

        Args:
            symbol: Instrument symbol.
            side: Buy or sell.
            quantity: Number of shares/contracts.
            order_type: Market, limit, stop, or stop-limit.
            limit_price: Limit price (for limit/stop-limit orders).
            stop_price: Stop trigger price (for stop/stop-limit orders).

        Returns:
            OrderResult with fill details.
        """
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order.

        Args:
            order_id: The broker-assigned order ID.

        Returns:
            True if cancellation was successful.
        """
        ...

    @abstractmethod
    async def get_positions(self) -> list[BrokerPosition]:
        """Get all current positions.

        Returns:
            List of BrokerPosition objects.
        """
        ...

    @abstractmethod
    async def get_account(self) -> AccountInfo:
        """Get account summary.

        Returns:
            AccountInfo with equity, cash, buying power.
        """
        ...
