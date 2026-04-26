"""Fast-path Backtesting Engine loop."""

import logging
from typing import Any

import pandas as pd

from algoforge.backtest.models import BacktestResult, TradePnL
from algoforge.backtest.metrics import calculate_metrics
from algoforge.backtest.monte_carlo import run_monte_carlo_drawdown
from algoforge.oms.manager import OrderManager
from algoforge.oms.store import OrderStore
from algoforge.paper.config import PaperTradingConfig
from algoforge.paper.engine import PaperTradingEngine

logger = logging.getLogger(__name__)


class BacktestEngine:
    """Event-driven simulator for evaluating strategies against historical data."""

    def __init__(self, config: PaperTradingConfig):
        """Initialize the backtester.

        Args:
            config: The paper trading config determining starting capital and friction.
        """
        self.config = config
        self.store = OrderStore(":memory:")  # Use in-memory SQLite for fast testing
        self.oms = OrderManager(self.store)
        self.paper_engine = PaperTradingEngine(config, self.oms)
        
        self.executed_trades: list[TradePnL] = []
        self.equity_values: list[float] = []
        self.timestamps: list[pd.Timestamp] = []

    def run(self, strategy_name: str, dataframe: pd.DataFrame, strategy_logic: Any) -> BacktestResult:
        """Run the backtest loop over historical data.

        Args:
            strategy_name: Name of the strategy being tested.
            dataframe: OHLCV chronological pandas DataFrame.
            strategy_logic: A callable or object that generates orders based on the candle. 
                            (Abstracted for now; in a full integration, this would wrap
                            Signals -> Risk -> Exits and yield `algoforge.oms.models.Order`s).

        Returns:
            BacktestResult with metrics and equity curve.
        """
        logger.info("Starting backtest: %s over %d bars", strategy_name, len(dataframe))

        current_capital = self.config.starting_capital

        for index, row in dataframe.iterrows():
            timestamp = pd.Timestamp(index)
            current_capital = self._process_bar(row, timestamp, current_capital, strategy_logic)

            # 4. Record daily equity
            self.equity_values.append(current_capital)
            self.timestamps.append(timestamp)

        return self._finalize_results(strategy_name, current_capital)

    def run_walk_forward(
        self,
        strategy_name: str,
        dataframe: pd.DataFrame,
        optimizer: Any,
        strategy_factory: Any,
        train_window: int = 1000,
        test_window: int = 250,
    ) -> BacktestResult:
        """Run walk-forward optimization backtest (OOS evaluation).

        Args:
            strategy_name: Name of the strategy.
            dataframe: Full OHLCV DataFrame.
            optimizer: Callable `opt(train_df)` returning optimal parameters.
            strategy_factory: Callable `factory(params)` returning `strategy_logic`.
            train_window: Number of bars for the IS training window.
            test_window: Number of bars for the OOS testing window.
        """
        logger.info("Starting WFO: %s (Train: %d, Test: %d)", strategy_name, train_window, test_window)
        n = len(dataframe)
        current_capital = self.config.starting_capital

        for start_idx in range(0, n - train_window, test_window):
            train_end = start_idx + train_window
            test_end = min(train_end + test_window, n)

            if test_end - train_end < max(1, test_window // 4):
                break  # Skip final stub if too small

            train_df = dataframe.iloc[start_idx:train_end]
            test_df = dataframe.iloc[train_end:test_end]

            # 1. Optimize on In-Sample
            best_params = optimizer(train_df)
            
            # 2. Build logic for Out-of-Sample
            strategy_logic = strategy_factory(best_params)

            # 3. Evaluate Out-of-Sample
            for index, row in test_df.iterrows():
                timestamp = pd.Timestamp(index)
                current_capital = self._process_bar(row, timestamp, current_capital, strategy_logic)

                self.equity_values.append(current_capital)
                self.timestamps.append(timestamp)

        return self._finalize_results(f"{strategy_name}_WFO", current_capital)

    def _process_bar(self, row: pd.Series, timestamp: pd.Timestamp, current_capital: float, strategy_logic: Any) -> float:
        """Process a single bar and return updated capital."""
        current_price = float(row['Close'])
        high = float(row['High'])
        low = float(row['Low'])

        fills = self.paper_engine.process_tick(current_price, high, low)
        for fill in fills:
            current_capital -= fill.total_friction

        new_orders, closed_trades = strategy_logic(row, self.oms)
        
        for order in new_orders:
            self.oms.submit_order(order)
            
        for trade in closed_trades:
            trade.closed_at = timestamp
            self.executed_trades.append(trade)
            current_capital += trade.pnl_amount

        return current_capital

    def _finalize_results(self, strategy_name: str, final_capital: float) -> BacktestResult:
        """Calculate metrics and return the final result object."""
        # Build equity curve series
        equity_series = pd.Series(self.equity_values, index=self.timestamps)
        
        # Calculate Metrics
        metrics = calculate_metrics(
            trades=self.executed_trades,
            equity_curve=equity_series,
            initial_capital=self.config.starting_capital
        )
        
        # Run Monte Carlo if we have enough trades
        monte_carlo = None
        if len(self.executed_trades) >= 10:
            monte_carlo = run_monte_carlo_drawdown(
                self.executed_trades, self.config.starting_capital
            )

        return BacktestResult(
            strategy_name=strategy_name,
            initial_capital=self.config.starting_capital,
            final_capital=final_capital,
            metrics=metrics,
            monte_carlo=monte_carlo,
            trades=self.executed_trades,
            equity_curve=equity_series
        )
