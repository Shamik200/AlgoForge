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
            # 1. Update Market Prices & Process Fills
            current_price = float(row['Close'])
            high = float(row['High'])
            low = float(row['Low'])
            timestamp = pd.Timestamp(index)

            # Paper engine evaluates active orders against the candle's High/Low
            fills = self.paper_engine.process_tick(current_price, high, low)
            
            # 2. Record Fills / PnL (Simplified tracking for simulation)
            for fill in fills:
                # In a full integration, we'd calculate exact PnL by matching entry and exit fills.
                # For this backtester shell, we assume the `strategy_logic` manages open positions
                # and returns a completed TradePnL when an exit occurs.
                # Here we just deduct the friction from our current running capital.
                current_capital -= fill.total_friction

            # 3. Ask Strategy for new orders / closed trades
            # This is where the strategy evaluates the current candle and active positions
            # It returns a list of new orders to submit, and a list of closed TradePnL objects
            new_orders, closed_trades = strategy_logic(row, self.oms)
            
            for order in new_orders:
                self.oms.submit_order(order)
                
            for trade in closed_trades:
                trade.closed_at = timestamp
                self.executed_trades.append(trade)
                # Add the trade's PnL to our running equity
                current_capital += trade.pnl_amount

            # 4. Record daily equity
            self.equity_values.append(current_capital)
            self.timestamps.append(timestamp)

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
            final_capital=current_capital,
            metrics=metrics,
            monte_carlo=monte_carlo,
            trades=self.executed_trades,
            equity_curve=equity_series
        )
