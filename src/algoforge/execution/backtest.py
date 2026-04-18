"""Backtesting Engine — Event-driven historical simulation.

Processes one candle at a time (no lookahead bias). Executes signals
on NEXT bar's open. Generates performance metrics.

Requirements: BACK-01 to BACK-07
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import numpy as np
import structlog
from pydantic import BaseModel, Field

from algoforge.core.constants import Direction, Market, Timeframe
from algoforge.core.models import OHLCV, Signal
from algoforge.execution.paper import PaperTradingEngine, TradeRecord
from algoforge.risk.manager import RiskConfig

logger = structlog.get_logger(__name__)


class BacktestMetrics(BaseModel):
    """Comprehensive backtest performance metrics (BACK-05)."""

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    total_commission: float = 0.0
    net_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    avg_bars_held: float = 0.0
    initial_capital: float = 0.0
    final_equity: float = 0.0
    total_return_pct: float = 0.0

    @classmethod
    def from_trades(
        cls,
        trades: list[TradeRecord],
        equity_curve: list[float],
        initial_capital: float,
    ) -> BacktestMetrics:
        """Calculate all metrics from trade history and equity curve."""
        if not trades:
            return cls(initial_capital=initial_capital, final_equity=initial_capital)

        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl <= 0]
        total_pnl = sum(t.pnl for t in trades)
        total_comm = sum(t.commission for t in trades)

        gross_profit = sum(t.pnl for t in wins) if wins else 0
        gross_loss = abs(sum(t.pnl for t in losses)) if losses else 0

        # Max drawdown from equity curve
        peak = initial_capital
        max_dd = 0.0
        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        # Daily returns for Sharpe/Sortino
        returns = []
        for i in range(1, len(equity_curve)):
            if equity_curve[i - 1] > 0:
                returns.append((equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1])

        sharpe = 0.0
        sortino = 0.0
        if returns:
            avg_ret = np.mean(returns)
            std_ret = np.std(returns)
            if std_ret > 0:
                sharpe = (avg_ret / std_ret) * np.sqrt(252)  # Annualized

            downside = [r for r in returns if r < 0]
            if downside:
                downside_std = np.std(downside)
                if downside_std > 0:
                    sortino = (avg_ret / downside_std) * np.sqrt(252)

        final_eq = equity_curve[-1] if equity_curve else initial_capital
        total_return = (final_eq - initial_capital) / initial_capital if initial_capital > 0 else 0
        calmar = total_return / max_dd if max_dd > 0 else 0

        return cls(
            total_trades=len(trades),
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate=len(wins) / len(trades) if trades else 0,
            total_pnl=round(total_pnl, 2),
            total_commission=round(total_comm, 2),
            net_pnl=round(total_pnl, 2),
            avg_win=round(gross_profit / len(wins), 2) if wins else 0,
            avg_loss=round(gross_loss / len(losses), 2) if losses else 0,
            profit_factor=round(gross_profit / gross_loss, 2) if gross_loss > 0 else float("inf"),
            expectancy=round(total_pnl / len(trades), 2) if trades else 0,
            max_drawdown_pct=round(max_dd, 4),
            sharpe_ratio=round(float(sharpe), 2),
            sortino_ratio=round(float(sortino), 2),
            calmar_ratio=round(calmar, 2),
            avg_bars_held=round(np.mean([t.bars_held for t in trades]), 1) if trades else 0,
            initial_capital=initial_capital,
            final_equity=round(final_eq, 2),
            total_return_pct=round(total_return * 100, 2),
        )


class BacktestEngine:
    """Event-driven backtesting engine.

    Processes candles one-at-a-time with no lookahead bias (BACK-01, BACK-07).
    Signals execute on NEXT bar's open price.

    Usage:
        engine = BacktestEngine(initial_capital=100_000)
        for signal_fn in strategies:
            engine.add_strategy(signal_fn)
        metrics = engine.run(candles)
    """

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        market: Market = Market.STOCKS_US,
        slippage_pct: float = 0.0005,
        risk_config: RiskConfig | None = None,
    ) -> None:
        self._initial_capital = initial_capital
        self._market = market
        self._slippage_pct = slippage_pct
        self._risk_config = risk_config
        self._strategies: list[Any] = []
        self._pending_signals: list[Signal] = []
        self._equity_curve: list[float] = []
        self._paper_engine: PaperTradingEngine | None = None

    def add_strategy(self, strategy_fn: Any) -> None:
        """Add a strategy function.

        strategy_fn(bar_index, candle, history) → list[Signal]
        """
        self._strategies.append(strategy_fn)

    def run(self, candles: list[OHLCV]) -> BacktestMetrics:
        """Run backtest on historical candle data.

        BACK-07: Signals generated on bar N execute on bar N+1's open.
        """
        start_time = time.perf_counter()

        self._paper_engine = PaperTradingEngine(
            initial_capital=self._initial_capital,
            market=self._market,
            slippage_pct=self._slippage_pct,
            risk_config=self._risk_config,
        )
        self._equity_curve = [self._initial_capital]
        self._pending_signals = []

        for i, candle in enumerate(candles):
            # BACK-07: Execute pending signals at THIS bar's open (from previous bar)
            if self._pending_signals:
                for sig in self._pending_signals:
                    # Override entry price with current bar's open (no lookahead)
                    adjusted = sig.model_copy(update={"entry_price": candle.open})
                    # Re-validate SL direction after entry price change
                    try:
                        if adjusted.direction == Direction.LONG and adjusted.stop_loss >= adjusted.entry_price:
                            continue
                        if adjusted.direction == Direction.SHORT and adjusted.stop_loss <= adjusted.entry_price:
                            continue
                        self._paper_engine.submit_signal(adjusted)
                    except ValueError:
                        continue  # Invalid signal after adjustment

                self._pending_signals = []

            # Update prices with current candle's close
            self._paper_engine.update_prices({candle.symbol: candle.close})

            # Check exits (SL/TP against high/low, not just close)
            self._check_intrabar_exits(candle, i)

            # Generate new signals for NEXT bar
            history = candles[:i + 1]
            for strategy_fn in self._strategies:
                try:
                    signals = strategy_fn(i, candle, history)
                    if signals:
                        self._pending_signals.extend(signals)
                except Exception as e:
                    logger.warning("strategy_error", bar=i, error=str(e))

            # Record equity
            self._equity_curve.append(self._paper_engine.equity)

        elapsed = time.perf_counter() - start_time

        metrics = BacktestMetrics.from_trades(
            self._paper_engine.trade_history,
            self._equity_curve,
            self._initial_capital,
        )

        logger.info(
            "backtest_complete",
            total_bars=len(candles),
            total_trades=metrics.total_trades,
            net_pnl=metrics.net_pnl,
            sharpe=metrics.sharpe_ratio,
            max_dd=metrics.max_drawdown_pct,
            elapsed_s=round(elapsed, 2),
        )

        return metrics

    def _check_intrabar_exits(self, candle: OHLCV, bar_index: int) -> None:
        """Check SL/TP against intrabar high/low for more accurate exits."""
        if not self._paper_engine:
            return

        for pos in list(self._paper_engine.open_positions):
            if pos.symbol != candle.symbol:
                continue

            # Check if SL/TP was hit during this bar
            if pos.direction == Direction.LONG:
                if candle.low <= pos.stop_loss:
                    self._paper_engine.update_prices({candle.symbol: pos.stop_loss})
                elif candle.high >= pos.take_profit:
                    self._paper_engine.update_prices({candle.symbol: pos.take_profit})
            else:
                if candle.high >= pos.stop_loss:
                    self._paper_engine.update_prices({candle.symbol: pos.stop_loss})
                elif candle.low <= pos.take_profit:
                    self._paper_engine.update_prices({candle.symbol: pos.take_profit})

        self._paper_engine.check_exits(current_bar=bar_index)

    @property
    def equity_curve(self) -> list[float]:
        return self._equity_curve

    @property
    def trade_history(self) -> list[TradeRecord]:
        if self._paper_engine:
            return self._paper_engine.trade_history
        return []
