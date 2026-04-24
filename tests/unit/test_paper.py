"""Unit tests for the Paper Trading Engine."""

import pytest

from algoforge.oms.manager import OrderManager
from algoforge.oms.models import Order, OrderType, OrderStatus
from algoforge.oms.store import OrderStore
from algoforge.paper.config import AssetClass, PaperTradingConfig
from algoforge.paper.engine import PaperTradingEngine
from algoforge.paper.friction import (
    calculate_commissions,
    simulate_slippage,
    simulate_latency_drift,
    calculate_market_impact
)


def test_commissions():
    """Test commission models for different asset classes."""
    # US Stocks
    us_comm = calculate_commissions(AssetClass.US_STOCKS, 100, 150.0, False)
    assert us_comm == 1.0  # max(1.00, 100 * 0.005)
    
    us_comm_large = calculate_commissions(AssetClass.US_STOCKS, 1000, 150.0, False)
    assert us_comm_large == 5.0  # 1000 * 0.005
    
    # Crypto (Maker/Taker)
    crypto_comm = calculate_commissions(AssetClass.CRYPTO, 2.0, 50000.0, False)
    assert crypto_comm == 100.0  # 100,000 * 0.001
    
    # Indian Stocks (Buy - No STT)
    in_comm_buy = calculate_commissions(AssetClass.INDIAN_STOCKS, 100, 1000.0, False)
    # notional = 100k. Brokerage = 30. GST = 5.4. STT = 0.
    assert in_comm_buy == 35.4
    
    # Indian Stocks (Sell - With STT)
    in_comm_sell = calculate_commissions(AssetClass.INDIAN_STOCKS, 100, 1000.0, True)
    # notional = 100k. Brokerage = 30. GST = 5.4. STT = 100.
    assert in_comm_sell == 135.4


def test_slippage():
    """Test slippage application."""
    config = PaperTradingConfig(slippage_pct=0.01) # 1% slip for easy math
    
    # Limit orders do not slip
    slip_limit_price, cost = simulate_slippage(config, 100.0, True, OrderType.LIMIT)
    assert slip_limit_price == 100.0
    assert cost == 0.0
    
    # Market BUY slips UP (adverse)
    slip_market_buy, cost_buy = simulate_slippage(config, 100.0, True, OrderType.MARKET)
    assert slip_market_buy == 101.0
    assert cost_buy == 1.0
    
    # Market SELL slips DOWN (adverse)
    slip_market_sell, cost_sell = simulate_slippage(config, 100.0, False, OrderType.MARKET)
    assert slip_market_sell == 99.0
    assert cost_sell == 1.0


def test_market_impact():
    """Test market impact function."""
    config = PaperTradingConfig(avg_daily_volume=10000.0, impact_coefficient=0.1)
    
    # Small order ratio (1 / 10k = 0.0001 < 0.001) -> No impact
    price, cost = calculate_market_impact(config, 1.0, 100.0, True)
    assert price == 100.0
    assert cost == 0.0
    
    # Large order (1000 / 10000 = 0.1). sqrt(0.1) = ~0.316. 
    # Impact pct = 0.1 * 0.316 = 0.0316 = 3.16%
    price_lg, cost_lg = calculate_market_impact(config, 1000.0, 100.0, True)
    assert price_lg > 103.0
    assert cost_lg > 3.0


def test_paper_engine_execution():
    """Test end-to-end execution of an order in the engine."""
    store = OrderStore(":memory:")
    oms = OrderManager(store)
    config = PaperTradingConfig(
        asset_class=AssetClass.US_STOCKS, 
        latency_min_ms=0, latency_max_ms=0, # Turn off jitter for deterministic tests
        adverse_drift_pct=0.0
    )
    engine = PaperTradingEngine(config, oms)
    
    # Submit LIMIT BUY order at 100
    order = Order(correlation_id="p-1", symbol="AAPL", direction="long", 
                  order_type=OrderType.LIMIT, price=100.0, quantity=10)
    oms.submit_order(order)
    
    # Tick: High 105, Low 101, Close 102. Low > 100, so NO fill.
    fills = engine.process_tick(102.0, 105.0, 101.0)
    assert len(fills) == 0
    assert oms.store.get_order_by_correlation_id("p-1").status == OrderStatus.SUBMITTED
    
    # Tick: High 105, Low 99, Close 102. Low < 100, so FILL!
    fills = engine.process_tick(102.0, 105.0, 99.0)
    assert len(fills) == 1
    
    fill_res = fills[0]
    assert fill_res.filled is True
    # LIMIT fills at Limit Price (or better). 
    assert fill_res.fill_price == 100.0 
    assert fill_res.slippage_cost == 0.0 # Limit doesn't slip
    
    # Check status updated
    assert oms.store.get_order_by_correlation_id("p-1").status == OrderStatus.FILLED
    store.close()
