"""Connector Base — Abstract interface for exchange interaction.

Inspired by Hummingbot's ConnectorBase pattern. Standardizes data fetching,
websocket streaming, and order execution across different environments
(Paper vs Live).
"""

import abc
from typing import Callable, Awaitable, Any
from algoforge.core.models import OHLCV, Signal
from algoforge.execution.paper import FillResult, TradeRecord, Position

class ConnectorBase(abc.ABC):
    """Abstract base class for all exchange connectors."""

    # ─── DATA STREAMING ──────────────────────────────────────────────

    @abc.abstractmethod
    def fetch_top_n_universe(self, limit: int = 50) -> list[dict]:
        """Fetch top N symbols by volume."""
        pass

    @abc.abstractmethod
    def fetch_historical_klines(self, symbol: str) -> list[OHLCV]:
        """Fetch historical 1m klines for a symbol."""
        pass

    @abc.abstractmethod
    async def start_streams(self, symbols: list[str], callback: Callable[[dict], Awaitable[None]]) -> None:
        """Start WebSocket streams for selected symbols."""
        pass

    @abc.abstractmethod
    async def stop(self) -> None:
        """Cleanly stop all streams."""
        pass

    # ─── EXECUTION ───────────────────────────────────────────────────

    @abc.abstractmethod
    def submit_order(
        self,
        signal: Signal,
        daily_volume: float | None = None,
        conviction: float = 1.0,
        order_book: dict | None = None,
        score_weight: float = 1.0,
    ) -> FillResult:
        """Submit an order for execution."""
        pass

    @abc.abstractmethod
    def update_prices(self, prices: dict[str, float]) -> None:
        """Update current prices for position management."""
        pass

    @abc.abstractmethod
    def check_exits(self, **kwargs) -> list[TradeRecord]:
        """Check for and execute any stop-loss/take-profit exits."""
        pass

    @abc.abstractmethod
    def check_circuit_breaker(self, prices: dict[str, float]) -> None:
        """Check and update circuit breaker limits."""
        pass

    @property
    @abc.abstractmethod
    def open_positions(self) -> list[Position]:
        """List currently open positions."""
        pass

    @property
    @abc.abstractmethod
    def trade_history(self) -> list[TradeRecord]:
        """List historical trades."""
        pass

    @property
    @abc.abstractmethod
    def equity(self) -> float:
        """Get current total portfolio equity."""
        pass

    @abc.abstractmethod
    def snapshot(self) -> Any:
        """Get current portfolio state snapshot."""
        pass
        
    @abc.abstractmethod
    def emergency_flatten(self) -> None:
        """Immediately exit all open positions at market."""
        pass
        
    @abc.abstractmethod
    def reset(self) -> None:
        """Reset the execution engine state (for /reset endpoints)."""
        pass
        
    @abc.abstractmethod
    def reset_risk_limits(self) -> None:
        """Clear active risk limits/cooldowns."""
        pass
