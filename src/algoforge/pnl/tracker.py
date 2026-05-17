"""Enhanced P&L Tracker for comprehensive performance tracking.

Tracks detailed P&L metrics including percentage returns, R-multiples,
portfolio-level metrics, and per-signal-family performance.

Requirements: Requirement 9 (Enhanced P&L Tracking and Display)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from pydantic import BaseModel, Field

from algoforge.core.constants import Direction

logger = structlog.get_logger(__name__)


class TradeMetrics(BaseModel):
    """Comprehensive trade-level metrics."""

    trade_id: str
    symbol: str
    signal_family: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl_dollars: float
    pnl_percent: float
    r_multiple: float
    initial_risk: float
    time_in_trade: timedelta
    exit_reason: str
    conviction_score: float = 0.0
    direction: Direction
    entry_time: datetime
    exit_time: datetime
    commission: float = 0.0
    slippage: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class PortfolioMetrics(BaseModel):
    """Portfolio-level performance metrics."""

    total_capital: float
    allocated_capital: float
    available_capital: float
    total_pnl_dollars: float
    total_pnl_percent: float
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown_percent: float = 0.0
    current_drawdown_percent: float = 0.0
    cumulative_r_multiples: float = 0.0
    win_rate: float = 0.0
    avg_r_multiple: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FamilyMetrics(BaseModel):
    """Signal family performance metrics."""

    family_name: str
    total_trades: int = 0
    win_rate: float = 0.0
    avg_r_multiple: float = 0.0
    total_pnl_dollars: float = 0.0
    sharpe_ratio: float = 0.0
    contribution_percent: float = 0.0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_pnl_percent: float = 0.0


class EnhancedPnLTracker:
    """Tracks comprehensive P&L metrics.

    Features:
    - Percentage P&L calculation (Requirement 9.1)
    - R-multiple tracking (Requirement 9.2)
    - Capital allocation tracking (Requirement 9.3)
    - Portfolio-level metrics (Requirement 9.4)
    - Per-signal-family metrics (Requirement 9.7)
    - Cumulative R-multiple tracking (Requirement 9.8)

    Usage:
        tracker = EnhancedPnLTracker(initial_capital=100_000)
        tracker.record_trade_open(position, entry_price, stop_loss, capital)
        metrics = tracker.record_trade_close(position, exit_price, "TP")
        portfolio = tracker.get_portfolio_metrics()
        family = tracker.get_family_metrics("momentum")
    """

    def __init__(self, initial_capital: float = 100_000.0) -> None:
        """Initialize P&L tracker.

        Args:
            initial_capital: Starting capital for the portfolio
        """
        self._initial_capital = initial_capital
        self._total_capital = initial_capital
        self._allocated_capital = 0.0
        self._peak_capital = initial_capital

        # Track open positions
        self._open_positions: dict[str, dict[str, Any]] = {}

        # Track closed trades
        self._trade_history: list[TradeMetrics] = []

        # Track per-family metrics
        self._family_trades: dict[str, list[TradeMetrics]] = {}

        logger.info(
            "pnl_tracker_initialized",
            initial_capital=initial_capital,
        )

    def record_trade_open(
        self,
        position_id: str,
        symbol: str,
        direction: Direction,
        entry_price: float,
        stop_loss: float,
        quantity: float,
        signal_family: str = "unknown",
        conviction_score: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record trade opening for P&L tracking.

        Args:
            position_id: Unique position identifier
            symbol: Trading symbol
            direction: Trade direction (LONG/SHORT)
            entry_price: Entry price
            stop_loss: Stop loss price
            quantity: Position size
            signal_family: Signal family that generated the trade
            conviction_score: Conviction score (0-1)
            metadata: Additional metadata
        """
        # Calculate initial risk (Requirement 9.2)
        if direction == Direction.LONG:
            initial_risk = abs(entry_price - stop_loss) * quantity
        else:
            initial_risk = abs(stop_loss - entry_price) * quantity

        # Calculate capital allocated (Requirement 9.3)
        capital_allocated = entry_price * quantity

        self._open_positions[position_id] = {
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "quantity": quantity,
            "signal_family": signal_family,
            "conviction_score": conviction_score,
            "initial_risk": initial_risk,
            "capital_allocated": capital_allocated,
            "entry_time": datetime.now(timezone.utc),
            "metadata": metadata or {},
        }

        self._allocated_capital += capital_allocated

        logger.info(
            "trade_opened",
            position_id=position_id,
            symbol=symbol,
            direction=direction.value,
            entry_price=entry_price,
            initial_risk=round(initial_risk, 2),
            capital_allocated=round(capital_allocated, 2),
            signal_family=signal_family,
        )

    def record_trade_close(
        self,
        position_id: str,
        exit_price: float,
        exit_reason: str,
        commission: float = 0.0,
        slippage: float = 0.0,
    ) -> TradeMetrics:
        """Record trade closing and compute comprehensive metrics.

        Args:
            position_id: Position identifier
            exit_price: Exit price
            exit_reason: Reason for exit (TP, SL, manual, etc.)
            commission: Total commission paid
            slippage: Total slippage cost

        Returns:
            TradeMetrics with all computed metrics

        Raises:
            KeyError: If position_id not found in open positions
        """
        if position_id not in self._open_positions:
            raise KeyError(f"Position {position_id} not found in open positions")

        pos = self._open_positions[position_id]
        exit_time = datetime.now(timezone.utc)

        # Calculate P&L in dollars
        if pos["direction"] == Direction.LONG:
            pnl_dollars = (exit_price - pos["entry_price"]) * pos["quantity"]
        else:
            pnl_dollars = (pos["entry_price"] - exit_price) * pos["quantity"]

        # Subtract costs
        pnl_dollars -= (commission + slippage)

        # Calculate P&L percentage (Requirement 9.1)
        pnl_percent = ((exit_price - pos["entry_price"]) / pos["entry_price"]) * 100
        if pos["direction"] == Direction.SHORT:
            pnl_percent = -pnl_percent

        # Calculate R-multiple (Requirement 9.2)
        r_multiple = pnl_dollars / pos["initial_risk"] if pos["initial_risk"] > 0 else 0.0

        # Calculate time in trade
        time_in_trade = exit_time - pos["entry_time"]

        # Create trade metrics
        metrics = TradeMetrics(
            trade_id=position_id,
            symbol=pos["symbol"],
            signal_family=pos["signal_family"],
            entry_price=pos["entry_price"],
            exit_price=exit_price,
            quantity=pos["quantity"],
            pnl_dollars=round(pnl_dollars, 2),
            pnl_percent=round(pnl_percent, 4),
            r_multiple=round(r_multiple, 4),
            initial_risk=pos["initial_risk"],
            time_in_trade=time_in_trade,
            exit_reason=exit_reason,
            conviction_score=pos["conviction_score"],
            direction=pos["direction"],
            entry_time=pos["entry_time"],
            exit_time=exit_time,
            commission=commission,
            slippage=slippage,
            metadata=pos["metadata"],
        )

        # Update tracking
        self._trade_history.append(metrics)
        self._allocated_capital -= pos["capital_allocated"]
        self._total_capital += pnl_dollars

        # Track peak capital for drawdown calculation
        if self._total_capital > self._peak_capital:
            self._peak_capital = self._total_capital

        # Track per-family metrics (Requirement 9.7)
        family = pos["signal_family"]
        if family not in self._family_trades:
            self._family_trades[family] = []
        self._family_trades[family].append(metrics)

        # Remove from open positions
        del self._open_positions[position_id]

        logger.info(
            "trade_closed",
            position_id=position_id,
            symbol=pos["symbol"],
            exit_reason=exit_reason,
            pnl_dollars=round(pnl_dollars, 2),
            pnl_percent=round(pnl_percent, 4),
            r_multiple=round(r_multiple, 4),
            time_in_trade_seconds=time_in_trade.total_seconds(),
        )

        return metrics

    def get_portfolio_metrics(self) -> PortfolioMetrics:
        """Compute portfolio-level metrics (Requirement 9.4).

        Returns:
            PortfolioMetrics with all portfolio-level statistics
        """
        # Calculate basic metrics
        total_pnl_dollars = sum(t.pnl_dollars for t in self._trade_history)
        total_pnl_percent = (
            (self._total_capital - self._initial_capital) / self._initial_capital * 100
        )

        # Calculate win rate
        winning_trades = sum(1 for t in self._trade_history if t.pnl_dollars > 0)
        losing_trades = sum(1 for t in self._trade_history if t.pnl_dollars <= 0)
        total_trades = len(self._trade_history)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

        # Calculate cumulative R-multiples (Requirement 9.8)
        cumulative_r_multiples = sum(t.r_multiple for t in self._trade_history)
        avg_r_multiple = (
            cumulative_r_multiples / total_trades if total_trades > 0 else 0.0
        )

        # Calculate Sharpe ratio (Requirement 9.4)
        sharpe_ratio = self._calculate_sharpe_ratio()

        # Calculate Sortino ratio (Requirement 9.4)
        sortino_ratio = self._calculate_sortino_ratio()

        # Calculate drawdown (Requirement 9.4)
        max_drawdown_percent = (
            (self._peak_capital - self._total_capital) / self._peak_capital * 100
            if self._peak_capital > 0
            else 0.0
        )
        current_drawdown_percent = max_drawdown_percent  # Same as max for current

        return PortfolioMetrics(
            total_capital=round(self._total_capital, 2),
            allocated_capital=round(self._allocated_capital, 2),
            available_capital=round(self._total_capital - self._allocated_capital, 2),
            total_pnl_dollars=round(total_pnl_dollars, 2),
            total_pnl_percent=round(total_pnl_percent, 4),
            sharpe_ratio=round(sharpe_ratio, 4),
            sortino_ratio=round(sortino_ratio, 4),
            max_drawdown_percent=round(max_drawdown_percent, 4),
            current_drawdown_percent=round(current_drawdown_percent, 4),
            cumulative_r_multiples=round(cumulative_r_multiples, 4),
            win_rate=round(win_rate, 2),
            avg_r_multiple=round(avg_r_multiple, 4),
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
        )

    def get_family_metrics(self, family_name: str) -> FamilyMetrics:
        """Get metrics for a specific signal family (Requirement 9.7).

        Args:
            family_name: Name of the signal family

        Returns:
            FamilyMetrics for the specified family
        """
        trades = self._family_trades.get(family_name, [])

        if not trades:
            return FamilyMetrics(family_name=family_name)

        # Calculate basic metrics
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.pnl_dollars > 0)
        losing_trades = sum(1 for t in trades if t.pnl_dollars <= 0)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

        # Calculate P&L metrics
        total_pnl_dollars = sum(t.pnl_dollars for t in trades)
        avg_pnl_percent = (
            sum(t.pnl_percent for t in trades) / total_trades if total_trades > 0 else 0.0
        )

        # Calculate R-multiple metrics
        total_r_multiples = sum(t.r_multiple for t in trades)
        avg_r_multiple = total_r_multiples / total_trades if total_trades > 0 else 0.0

        # Calculate Sharpe ratio for this family
        sharpe_ratio = self._calculate_family_sharpe_ratio(trades)

        # Calculate contribution to total portfolio P&L
        total_portfolio_pnl = sum(t.pnl_dollars for t in self._trade_history)
        contribution_percent = (
            (total_pnl_dollars / total_portfolio_pnl * 100)
            if total_portfolio_pnl != 0
            else 0.0
        )

        return FamilyMetrics(
            family_name=family_name,
            total_trades=total_trades,
            win_rate=round(win_rate, 2),
            avg_r_multiple=round(avg_r_multiple, 4),
            total_pnl_dollars=round(total_pnl_dollars, 2),
            sharpe_ratio=round(sharpe_ratio, 4),
            contribution_percent=round(contribution_percent, 2),
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            avg_pnl_percent=round(avg_pnl_percent, 4),
        )

    def get_all_family_metrics(self) -> dict[str, FamilyMetrics]:
        """Get metrics for all signal families.

        Returns:
            Dictionary mapping family names to their metrics
        """
        return {
            family: self.get_family_metrics(family) for family in self._family_trades.keys()
        }

    def get_trade_history(self) -> list[TradeMetrics]:
        """Get all closed trade metrics.

        Returns:
            List of all TradeMetrics
        """
        return self._trade_history.copy()

    def get_open_positions_count(self) -> int:
        """Get count of currently open positions.

        Returns:
            Number of open positions
        """
        return len(self._open_positions)

    def _calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio for the portfolio.

        Returns:
            Sharpe ratio (annualized)
        """
        if len(self._trade_history) < 2:
            return 0.0

        # Calculate returns
        returns = [t.pnl_percent for t in self._trade_history]

        # Calculate mean and std
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_return = variance**0.5

        if std_return == 0:
            return 0.0

        # Annualize (assuming ~252 trading days, adjust based on avg trade duration)
        avg_trade_days = sum(
            t.time_in_trade.total_seconds() / 86400 for t in self._trade_history
        ) / len(self._trade_history)
        trades_per_year = 252 / max(avg_trade_days, 1)

        sharpe = (mean_return / std_return) * (trades_per_year**0.5)
        return sharpe

    def _calculate_sortino_ratio(self) -> float:
        """Calculate Sortino ratio for the portfolio.

        Returns:
            Sortino ratio (annualized)
        """
        if len(self._trade_history) < 2:
            return 0.0

        # Calculate returns
        returns = [t.pnl_percent for t in self._trade_history]
        mean_return = sum(returns) / len(returns)

        # Calculate downside deviation (only negative returns)
        downside_returns = [r for r in returns if r < 0]
        if not downside_returns:
            return 0.0

        downside_variance = sum(r**2 for r in downside_returns) / len(downside_returns)
        downside_std = downside_variance**0.5

        if downside_std == 0:
            return 0.0

        # Annualize
        avg_trade_days = sum(
            t.time_in_trade.total_seconds() / 86400 for t in self._trade_history
        ) / len(self._trade_history)
        trades_per_year = 252 / max(avg_trade_days, 1)

        sortino = (mean_return / downside_std) * (trades_per_year**0.5)
        return sortino

    def _calculate_family_sharpe_ratio(self, trades: list[TradeMetrics]) -> float:
        """Calculate Sharpe ratio for a specific family.

        Args:
            trades: List of trades for the family

        Returns:
            Sharpe ratio for the family
        """
        if len(trades) < 2:
            return 0.0

        returns = [t.pnl_percent for t in trades]
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_return = variance**0.5

        if std_return == 0:
            return 0.0

        avg_trade_days = sum(t.time_in_trade.total_seconds() / 86400 for t in trades) / len(
            trades
        )
        trades_per_year = 252 / max(avg_trade_days, 1)

        sharpe = (mean_return / std_return) * (trades_per_year**0.5)
        return sharpe

    def reset(self) -> None:
        """Reset tracker to initial state."""
        self._total_capital = self._initial_capital
        self._allocated_capital = 0.0
        self._peak_capital = self._initial_capital
        self._open_positions.clear()
        self._trade_history.clear()
        self._family_trades.clear()

        logger.info("pnl_tracker_reset")
