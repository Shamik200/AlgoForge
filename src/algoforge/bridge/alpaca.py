"""Alpaca broker adapter (placeholder implementation).

This is a placeholder that implements the BrokerAdapter interface
with simulated responses. Replace with real Alpaca API calls when
API keys are configured.
"""

import logging
import uuid

from algoforge.bridge.adapter import (
    AccountInfo,
    BrokerAdapter,
    BrokerPosition,
    OrderResult,
    OrderSide,
    OrderStatus,
    OrderType,
)

logger = logging.getLogger(__name__)


class AlpacaAdapter(BrokerAdapter):
    """Placeholder Alpaca broker adapter.

    In production, this would use alpaca-trade-api to connect to
    Alpaca's REST and WebSocket APIs.
    """

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        paper: bool = True,
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.paper = paper
        self._connected = False
        self._positions: dict[str, BrokerPosition] = {}

        base_url = "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets"
        logger.info("[Alpaca] Initialized (%s mode) → %s", "PAPER" if paper else "LIVE", base_url)

    async def connect(self) -> bool:
        """Simulate connection to Alpaca API."""
        logger.info("[Alpaca] Connecting...")
        self._connected = True
        return True

    async def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False
        logger.info("[Alpaca] Disconnected.")

    async def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: float | None = None,
        stop_price: float | None = None,
    ) -> OrderResult:
        """Simulate order submission."""
        order_id = str(uuid.uuid4())[:8]
        logger.info(
            "[Alpaca] Order submitted: %s %s %s x%.1f (id=%s)",
            order_type.value, side.value, symbol, quantity, order_id
        )

        # Simulate immediate fill for market orders
        fill_price = limit_price or 100.0  # Placeholder price
        return OrderResult(
            order_id=order_id,
            status=OrderStatus.FILLED,
            filled_quantity=quantity,
            filled_price=fill_price,
            commission=quantity * 0.001,  # $0.001 per share
            message=f"Simulated {side.value} fill at ${fill_price:.2f}",
        )

    async def cancel_order(self, order_id: str) -> bool:
        """Simulate order cancellation."""
        logger.info("[Alpaca] Order %s cancelled.", order_id)
        return True

    async def get_positions(self) -> list[BrokerPosition]:
        """Return simulated positions."""
        return list(self._positions.values())

    async def get_account(self) -> AccountInfo:
        """Return simulated account info."""
        return AccountInfo(
            equity=100_000.0,
            cash=50_000.0,
            buying_power=100_000.0,
            portfolio_value=100_000.0,
            currency="USD",
        )
