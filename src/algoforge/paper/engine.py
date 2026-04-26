"""The core Paper Trading Simulator."""

import logging

from algoforge.oms.models import Order, OrderStatus, OrderType
from algoforge.oms.state_machine import transition, InvalidTransitionError
from algoforge.oms.manager import OrderManager
from algoforge.paper.config import PaperTradingConfig, FillResult
from algoforge.paper.friction import (
    calculate_commissions,
    simulate_latency_drift,
    simulate_slippage,
    calculate_market_impact
)

logger = logging.getLogger(__name__)


class PaperTradingEngine:
    """Simulates real-world execution of OMS orders."""

    def __init__(self, config: PaperTradingConfig, oms: OrderManager) -> None:
        """Initialize the simulator.

        Args:
            config: PaperTradingConfig containing capital and friction params.
            oms: The OrderManager instance to interface with.
        """
        self.config = config
        self.oms = oms
        self.current_capital = config.starting_capital

    def process_tick(self, current_price: float, high: float, low: float, volume: float = 0.0) -> list[FillResult]:
        """Process a market tick (or candle close) against all active orders.

        Args:
            current_price: The closing/current price of the asset.
            high: The high of the candle (used for checking limit triggers).
            low: The low of the candle (used for checking limit triggers).
            volume: The volume of the candle (for market impact).

        Returns:
            A list of FillResults for any orders that executed.
        """
        fills = []
        
        # Expire stale limits before checking for fills
        self.oms.check_expiry()
        
        active_orders = self.oms.store.get_active_orders()

        for order in active_orders:
            # Only process SUBMITTED or PARTIAL_FILL
            if order.status not in (OrderStatus.SUBMITTED, OrderStatus.PARTIAL_FILL):
                continue

            fill_res = self._evaluate_order(order, current_price, high, low, volume)
            
            if fill_res.filled:
                try:
                    # Deduct the total cost/friction from capital
                    notional = order.quantity * fill_res.fill_price
                    total_cost = notional + fill_res.total_friction
                    
                    # (In a real system, you'd only deduct for entries, add for exits. 
                    # For paper trading simulation we assume P&L tracking handles that, 
                    # and we just log friction costs).
                    
                    # Update OMS state
                    self.oms.fill_order(order.correlation_id)
                    fills.append(fill_res)
                    
                    logger.info(
                        "Paper Trade Filled: %s at %.2f (Friction: %.2f)", 
                        order.correlation_id, fill_res.fill_price, fill_res.total_friction
                    )
                except InvalidTransitionError as e:
                    logger.error("Failed to fill order %s: %s", order.correlation_id, str(e))

        return fills

    def _evaluate_order(self, order: Order, current_price: float, high: float, low: float, volume: float) -> FillResult:
        """Determine if an order fills and calculate its execution price with friction."""
        
        is_buy = (order.direction.lower() == "long")
        is_sell = not is_buy
        
        # 1. Check Trigger
        triggered = False
        base_price = current_price
        
        if order.order_type == OrderType.MARKET:
            triggered = True
            base_price = current_price
        elif order.order_type == OrderType.LIMIT:
            if is_buy and low <= order.price:
                triggered = True
                base_price = min(current_price, order.price)
            elif is_sell and high >= order.price:
                triggered = True
                base_price = max(current_price, order.price)
                
        if not triggered:
            return FillResult(filled=False)

        # 2. Apply Friction Models
        
        # Latency
        price_after_latency, latency_cost = simulate_latency_drift(
            self.config, base_price, is_buy
        )
        
        # Slippage (Only applied to Market orders)
        # Assuming orders that close a position are exits
        is_exit = ("stop" in order.correlation_id.lower() or "tp" in order.correlation_id.lower())
        price_after_slip, slippage_cost = simulate_slippage(
            self.config, price_after_latency, is_buy, order.order_type, is_exit
        )
        
        # Market Impact
        final_price, impact_cost = calculate_market_impact(
            self.config, order.quantity, price_after_slip, is_buy, volume
        )
        
        # Commissions
        commission_cost = calculate_commissions(
            self.config.asset_class, order.quantity, final_price, is_sell
        )
        
        # Scale per-share friction costs by quantity
        total_slippage = slippage_cost * order.quantity
        total_latency = latency_cost * order.quantity
        total_impact = impact_cost * order.quantity
        
        total_friction = total_slippage + total_latency + total_impact + commission_cost

        return FillResult(
            filled=True,
            fill_price=final_price,
            slippage_cost=total_slippage,
            commission_cost=commission_cost,
            latency_cost=total_latency,
            impact_cost=total_impact,
            total_friction=total_friction,
            details={"correlation_id": order.correlation_id}
        )
