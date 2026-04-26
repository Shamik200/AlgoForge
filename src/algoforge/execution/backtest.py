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


# ---------------------------------------------------------------------------
# Walk-Forward Validation (BACK-02)
# ---------------------------------------------------------------------------


class WalkForwardResult(BaseModel):
    """Result of a single walk-forward window."""

    window_index: int = 0
    train_start: int = 0
    train_end: int = 0
    test_start: int = 0
    test_end: int = 0
    train_metrics: BacktestMetrics | None = None
    test_metrics: BacktestMetrics | None = None


class WalkForwardReport(BaseModel):
    """Aggregate walk-forward validation report."""

    windows: list[WalkForwardResult] = Field(default_factory=list)
    aggregate_metrics: BacktestMetrics | None = None
    avg_oos_sharpe: float = 0.0
    avg_oos_return_pct: float = 0.0
    avg_oos_max_dd: float = 0.0
    degradation_pct: float = 0.0  # avg IS Sharpe vs avg OOS Sharpe
    total_oos_trades: int = 0


class WalkForwardEngine:
    """Walk-forward validation engine (BACK-02).

    Splits candle data into rolling train/test windows. For each window:
    1. Train (optimize/fit) on the training set
    2. Test on the out-of-sample set
    3. Aggregate results to measure true out-of-sample performance

    This prevents overfitting — the most common backtest pitfall.

    Usage:
        wf = WalkForwardEngine(
            initial_capital=100_000,
            train_pct=0.70,
            n_windows=5,
        )
        for strategy_fn in strategies:
            wf.add_strategy(strategy_fn)
        report = wf.run(candles)
    """

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        market: Market = Market.STOCKS_US,
        slippage_pct: float = 0.0005,
        risk_config: RiskConfig | None = None,
        train_pct: float = 0.70,
        n_windows: int = 5,
        expanding: bool = False,
    ) -> None:
        self._initial_capital = initial_capital
        self._market = market
        self._slippage_pct = slippage_pct
        self._risk_config = risk_config
        self._strategies: list[Any] = []
        self._train_pct = train_pct
        self._n_windows = n_windows
        self._expanding = expanding

    def add_strategy(self, strategy_fn: Any) -> None:
        """Add a strategy function (same interface as BacktestEngine)."""
        self._strategies.append(strategy_fn)

    def run(self, candles: list[OHLCV]) -> WalkForwardReport:
        """Run walk-forward validation across N windows.

        For rolling windows:
          Window size = len(candles) / n_windows
          Train = first train_pct of window
          Test = remaining (1 - train_pct)

        For expanding windows:
          Train grows each iteration, test stays fixed.
        """
        n = len(candles)
        if n < 100:
            logger.warning("walk_forward.insufficient_data", bars=n)
            return WalkForwardReport()

        results: list[WalkForwardResult] = []
        step_size = n // self._n_windows

        for i in range(self._n_windows):
            if self._expanding:
                train_start = 0
                train_end = step_size * (i + 1)
            else:
                train_start = step_size * i
                train_end = train_start + int(step_size * self._train_pct)

            test_start = train_end
            test_end = min(train_start + step_size, n) if not self._expanding else min(train_end + step_size, n)

            if test_start >= test_end or train_start >= train_end:
                continue

            train_candles = candles[train_start:train_end]
            test_candles = candles[test_start:test_end]

            # Run backtest on training set
            train_engine = BacktestEngine(
                initial_capital=self._initial_capital,
                market=self._market,
                slippage_pct=self._slippage_pct,
                risk_config=self._risk_config,
            )
            for fn in self._strategies:
                train_engine.add_strategy(fn)
            train_metrics = train_engine.run(train_candles)

            # Run backtest on test (out-of-sample) set
            test_engine = BacktestEngine(
                initial_capital=self._initial_capital,
                market=self._market,
                slippage_pct=self._slippage_pct,
                risk_config=self._risk_config,
            )
            for fn in self._strategies:
                test_engine.add_strategy(fn)
            test_metrics = test_engine.run(test_candles)

            results.append(WalkForwardResult(
                window_index=i,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                train_metrics=train_metrics,
                test_metrics=test_metrics,
            ))

            logger.info(
                "walk_forward.window",
                window=i,
                train_bars=len(train_candles),
                test_bars=len(test_candles),
                is_sharpe=train_metrics.sharpe_ratio,
                oos_sharpe=test_metrics.sharpe_ratio,
            )

        # Aggregate OOS results
        oos_sharpes = [r.test_metrics.sharpe_ratio for r in results if r.test_metrics]
        is_sharpes = [r.train_metrics.sharpe_ratio for r in results if r.train_metrics]
        oos_returns = [r.test_metrics.total_return_pct for r in results if r.test_metrics]
        oos_dds = [r.test_metrics.max_drawdown_pct for r in results if r.test_metrics]
        oos_trades = sum(r.test_metrics.total_trades for r in results if r.test_metrics)

        avg_is = float(np.mean(is_sharpes)) if is_sharpes else 0.0
        avg_oos = float(np.mean(oos_sharpes)) if oos_sharpes else 0.0
        degradation = ((avg_is - avg_oos) / avg_is * 100) if avg_is > 0 else 0.0

        report = WalkForwardReport(
            windows=results,
            avg_oos_sharpe=round(avg_oos, 2),
            avg_oos_return_pct=round(float(np.mean(oos_returns)), 2) if oos_returns else 0.0,
            avg_oos_max_dd=round(float(np.mean(oos_dds)), 4) if oos_dds else 0.0,
            degradation_pct=round(degradation, 1),
            total_oos_trades=oos_trades,
        )

        logger.info(
            "walk_forward.complete",
            windows=len(results),
            avg_oos_sharpe=report.avg_oos_sharpe,
            degradation_pct=report.degradation_pct,
            total_oos_trades=report.total_oos_trades,
        )

        return report


# ---------------------------------------------------------------------------
# Monte Carlo Simulation (BACK-03)
# ---------------------------------------------------------------------------


class MonteCarloResult(BaseModel):
    """Monte Carlo simulation result with confidence intervals."""

    n_simulations: int = 0
    median_final_equity: float = 0.0
    p5_final_equity: float = 0.0
    p95_final_equity: float = 0.0
    median_max_drawdown: float = 0.0
    p95_max_drawdown: float = 0.0
    prob_profitable: float = 0.0
    prob_ruin: float = 0.0  # P(drawdown > ruin_threshold)
    median_sharpe: float = 0.0


class MonteCarloSimulator:
    """Monte Carlo simulation for strategy robustness testing (BACK-03).

    Shuffles the order of historical trades to generate N synthetic
    equity curves. Produces confidence intervals around key metrics.

    Usage:
        trades = backtest_engine.trade_history
        mc = MonteCarloSimulator(n_simulations=1000)
        result = mc.run(trades, initial_capital=100_000)
    """

    def __init__(
        self,
        n_simulations: int = 1000,
        ruin_threshold_pct: float = 0.5,
    ) -> None:
        self._n_sims = n_simulations
        self._ruin_threshold = ruin_threshold_pct

    def run(
        self,
        trades: list[TradeRecord],
        initial_capital: float,
    ) -> MonteCarloResult:
        """Run Monte Carlo simulation by shuffling trade order.

        For each simulation:
        1. Randomly shuffle the trade P&L sequence
        2. Build equity curve from shuffled sequence
        3. Compute metrics (final equity, max drawdown)
        4. Aggregate across all simulations
        """
        if not trades:
            return MonteCarloResult()

        pnls = np.array([t.pnl for t in trades])
        n_trades = len(pnls)

        final_equities: list[float] = []
        max_drawdowns: list[float] = []
        sharpes: list[float] = []

        rng = np.random.default_rng(seed=42)

        for _ in range(self._n_sims):
            # Shuffle trade order
            shuffled = rng.permutation(pnls)

            # Build equity curve
            equity = initial_capital
            peak = initial_capital
            max_dd = 0.0
            returns: list[float] = []

            for pnl in shuffled:
                prev = equity
                equity += pnl
                if equity > peak:
                    peak = equity
                dd = (peak - equity) / peak if peak > 0 else 0
                if dd > max_dd:
                    max_dd = dd
                if prev > 0:
                    returns.append(pnl / prev)

            final_equities.append(equity)
            max_drawdowns.append(max_dd)

            # Sharpe from returns
            if returns:
                avg_r = np.mean(returns)
                std_r = np.std(returns)
                sharpes.append(float((avg_r / std_r) * np.sqrt(252)) if std_r > 0 else 0.0)
            else:
                sharpes.append(0.0)

        fe = np.array(final_equities)
        dd = np.array(max_drawdowns)
        sh = np.array(sharpes)

        result = MonteCarloResult(
            n_simulations=self._n_sims,
            median_final_equity=round(float(np.median(fe)), 2),
            p5_final_equity=round(float(np.percentile(fe, 5)), 2),
            p95_final_equity=round(float(np.percentile(fe, 95)), 2),
            median_max_drawdown=round(float(np.median(dd)), 4),
            p95_max_drawdown=round(float(np.percentile(dd, 95)), 4),
            prob_profitable=round(float(np.mean(fe > initial_capital)), 3),
            prob_ruin=round(float(np.mean(dd > self._ruin_threshold)), 3),
            median_sharpe=round(float(np.median(sh)), 2),
        )

        logger.info(
            "monte_carlo.complete",
            n_simulations=self._n_sims,
            median_equity=result.median_final_equity,
            p95_drawdown=result.p95_max_drawdown,
            prob_profitable=result.prob_profitable,
        )

        return result
