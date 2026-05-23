"""Enhanced PnL tracking for live trading and dashboarding.

Tracks trades, equity curve, drawdown, and core performance statistics in a
lightweight form that can be shared by the monitoring dashboard and API layer.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Any

from algoforge.backtest.models import TradePnL
@dataclass
class EquityPoint:
    """A single point on the equity curve."""
    timestamp: str
    value: float

    def to_dict(self) -> dict:
        return {"timestamp": self.timestamp, "value": round(self.value, 2)}

from algoforge.execution.paper import TradeRecord


@dataclass
class PnLSummary:
    total_pnl: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    expectancy: float
    max_drawdown_pct: float
    sharpe_ratio: float
    raw_sharpe_ratio: float


class EnhancedPnLTracker:
    """Track realized and unrealized performance for dashboard use."""

    def __init__(self, initial_capital: float = 100_000.0) -> None:
        self.initial_capital = initial_capital
        self._trades: list[TradePnL] = []
        self._equity_curve: list[EquityPoint] = [
            EquityPoint(timestamp=datetime.now(timezone.utc).isoformat(), value=initial_capital)
        ]

    @property
    def trades(self) -> list[TradePnL]:
        return list(self._trades)

    @property
    def equity_curve(self) -> list[EquityPoint]:
        return list(self._equity_curve)

    def record_trade(self, trade: TradeRecord | TradePnL | dict[str, Any]) -> TradePnL:
        """Normalize and record a completed trade."""
        normalized = self._normalize_trade(trade)
        self._trades.append(normalized)
        self._append_equity_point(self.current_equity + normalized.pnl_amount, normalized.closed_at)
        return normalized

    def update_equity(self, value: float, timestamp: datetime | None = None) -> None:
        """Append a new equity point."""
        self._equity_curve.append(
            EquityPoint(
                timestamp=(timestamp or datetime.now(timezone.utc)).isoformat(),
                value=value,
            )
        )

    @property
    def current_equity(self) -> float:
        return self._equity_curve[-1].value if self._equity_curve else self.initial_capital

    @property
    def unrealized_pnl(self) -> float:
        return self.current_equity - self.initial_capital

    def summary(self) -> PnLSummary:
        trades = self._trades
        total_pnl = sum(t.pnl_amount for t in trades)
        wins = [t for t in trades if t.pnl_amount > 0]
        losses = [t for t in trades if t.pnl_amount <= 0]
        total = len(trades)
        win_rate = len(wins) / total if total else 0.0
        gross_profit = sum(t.pnl_amount for t in wins)
        gross_loss = abs(sum(t.pnl_amount for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0
        expectancy = total_pnl / total if total else 0.0
        equity_values = [point.value for point in self._equity_curve]
        max_drawdown = self._max_drawdown(equity_values)
        sharpe, raw_sharpe = self._sharpe_like_ratio(equity_values)

        return PnLSummary(
            total_pnl=round(total_pnl, 2),
            total_trades=total,
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate=win_rate,
            profit_factor=profit_factor,
            expectancy=expectancy,
            max_drawdown_pct=max_drawdown,
            sharpe_ratio=sharpe,
            raw_sharpe_ratio=raw_sharpe,
        )

    def to_dict(self) -> dict[str, Any]:
        summary = self.summary()
        return {
            "summary": summary.__dict__,
            "equity_curve": [point.to_dict() for point in self._equity_curve],
            "trades": [trade.__dict__ for trade in self._trades],
        }

    def extend(self, trades: Iterable[TradeRecord | TradePnL | dict[str, Any]]) -> None:
        for trade in trades:
            self.record_trade(trade)

    def _append_equity_point(self, value: float, timestamp: datetime | None = None) -> None:
        self.update_equity(value, timestamp=timestamp)

    def _normalize_trade(self, trade: TradeRecord | TradePnL | dict[str, Any]) -> TradePnL:
        if isinstance(trade, TradePnL):
            return trade

        if isinstance(trade, TradeRecord):
            return TradePnL(
                trade_id=trade.id,
                symbol=trade.symbol,
                direction=trade.direction.value,
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                quantity=trade.quantity,
                pnl_amount=trade.pnl,
                pnl_pct=(trade.pnl / (trade.entry_price * trade.quantity)) if trade.entry_price and trade.quantity else 0.0,
                opened_at=trade.entry_time,
                closed_at=trade.exit_time,
                friction_cost=trade.commission + trade.slippage,
            )

        return TradePnL(
            trade_id=str(trade.get("id", trade.get("trade_id", ""))),
            symbol=str(trade.get("symbol", "")),
            direction=str(trade.get("direction", "")),
            entry_price=float(trade.get("entry_price", 0.0)),
            exit_price=float(trade.get("exit_price", 0.0)),
            quantity=float(trade.get("quantity", 0.0)),
            pnl_amount=float(trade.get("pnl", trade.get("pnl_amount", 0.0))),
            pnl_pct=float(trade.get("pnl_pct", 0.0)),
            opened_at=trade.get("entry_time", trade.get("opened_at", datetime.now(timezone.utc))),
            closed_at=trade.get("exit_time", trade.get("closed_at", datetime.now(timezone.utc))),
            friction_cost=float(trade.get("commission", trade.get("friction_cost", 0.0))) + float(trade.get("slippage", 0.0)),
        )

    @staticmethod
    def _max_drawdown(equity_values: list[float]) -> float:
        if len(equity_values) < 2:
            return 0.0
        peak = equity_values[0]
        max_dd = 0.0
        for value in equity_values:
            peak = max(peak, value)
            if peak > 0:
                max_dd = max(max_dd, (peak - value) / peak)
        return round(max_dd, 4)

    @staticmethod
    def _sharpe_like_ratio(equity_values: list[float]) -> tuple[float, float]:
        if len(equity_values) < 3:
            return 0.0, 0.0

        returns = []
        for prev, curr in zip(equity_values, equity_values[1:]):
            if prev > 0:
                returns.append((curr - prev) / prev)

        if len(returns) < 2:
            return 0.0, 0.0

        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
        if variance <= 0:
            return 0.0, 0.0

        volatility = math.sqrt(variance)
        raw_sharpe = mean_return / volatility if volatility > 0 else 0.0
        return round(raw_sharpe / 2.0, 4), round(raw_sharpe, 4)