"""Paper Trading Connector.

Wraps BinanceAdapter for live data streaming, but routes all execution
through the local simulated PaperTradingEngine.
"""

from typing import Callable, Awaitable, Any

from algoforge.connectors.base import ConnectorBase
from algoforge.core.models import OHLCV, Signal
from algoforge.execution.paper import FillResult, PaperTradingEngine, TradeRecord, Position
from algoforge.api.binance_stream import BinanceAdapter

class PaperConnector(ConnectorBase):
    """Data from Binance, Execution in Memory."""

    def __init__(self, paper_engine: PaperTradingEngine):
        self._engine = paper_engine
        self._adapter = None

    def _get_adapter(self, callback: Callable[[dict], Awaitable[None]] = None) -> BinanceAdapter:
        if self._adapter is None:
            self._adapter = BinanceAdapter(callback)
        elif callback is not None:
            self._adapter.callback = callback
        return self._adapter

    # ─── DATA STREAMING (Pass-through to Binance) ────────────────────

    def fetch_top_n_universe(self, limit: int = 50) -> list[dict]:
        return self._get_adapter().fetch_top_n_universe(limit)

    def fetch_historical_klines(self, symbol: str) -> list[OHLCV]:
        # Implementation is in engine/universe.py currently, but we can move it or leave it
        pass

    async def start_streams(self, symbols: list[str], callback: Callable[[dict], Awaitable[None]]) -> None:
        await self._get_adapter(callback).start_streams(symbols)

    async def stop(self) -> None:
        if self._adapter:
            await self._adapter.stop()

    # ─── EXECUTION (Pass-through to Paper Engine) ────────────────────

    def submit_order(
        self,
        signal: Signal,
        daily_volume: float | None = None,
        conviction: float = 1.0,
        conviction_score: float | None = None,
        order_book: dict | None = None,
        score_weight: float = 1.0,
    ) -> FillResult:
        return self._engine.submit_signal(
            signal,
            daily_volume=daily_volume,
            conviction=conviction,
            conviction_score=conviction_score,
            order_book=order_book,
            score_weight=score_weight,
        )

    def update_prices(self, prices: dict[str, float]) -> None:
        self._engine.update_prices(prices)

    def check_exits(self, **kwargs) -> list[TradeRecord]:
        return self._engine.check_exits(**kwargs)

    def check_circuit_breaker(self, prices: dict[str, float]) -> None:
        self._engine.risk_manager.check_circuit_breaker(prices)

    @property
    def open_positions(self) -> list[Position]:
        return self._engine.open_positions

    @property
    def trade_history(self) -> list[TradeRecord]:
        return self._engine._trade_history

    def snapshot(self) -> Any:
        return self._engine.snapshot()

    def emergency_flatten(self) -> None:
        from datetime import datetime, timezone
        for pos in self._engine.open_positions:
            self._engine._execute_market_exit(pos, pos.current_price, datetime.now(timezone.utc))

    def reset(self) -> None:
        self._engine.reset()

    def reset_risk_limits(self) -> None:
        rm = self._engine.risk_manager
        rm._consecutive_losses = 0
        rm._cooldown_until = None
        rm._kill_switch_active = False
        rm._circuit_breaker_active = False
