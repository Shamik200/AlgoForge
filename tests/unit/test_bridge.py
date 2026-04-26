"""Unit tests for the Live Trading Bridge module."""

import pytest
import numpy as np

from algoforge.bridge.adapter import (
    BrokerAdapter, OrderSide, OrderType, OrderStatus,
)
from algoforge.bridge.alpaca import AlpacaAdapter
from algoforge.bridge.deployment import DeploymentConfig, ScalingThreshold
from algoforge.bridge.metrics import TradingMetrics


@pytest.mark.asyncio
async def test_alpaca_adapter_connect():
    """Test Alpaca adapter connects successfully."""
    adapter = AlpacaAdapter(paper=True)
    connected = await adapter.connect()
    assert connected is True
    await adapter.disconnect()


@pytest.mark.asyncio
async def test_alpaca_adapter_submit_order():
    """Test Alpaca adapter simulates order fill."""
    adapter = AlpacaAdapter(paper=True)
    await adapter.connect()

    result = await adapter.submit_order(
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=100,
        order_type=OrderType.MARKET,
    )

    assert result.status == OrderStatus.FILLED
    assert result.filled_quantity == 100
    assert len(result.order_id) > 0
    await adapter.disconnect()


@pytest.mark.asyncio
async def test_alpaca_adapter_account():
    """Test Alpaca adapter returns account info."""
    adapter = AlpacaAdapter(paper=True)
    await adapter.connect()

    account = await adapter.get_account()
    assert account.equity > 0
    assert account.currency == "USD"
    await adapter.disconnect()


def test_deployment_config_initial():
    """Test deployment config starts at initial allocation."""
    config = DeploymentConfig(initial_capital_pct=0.10)
    assert config.get_current_allocation(0.0) == 0.10


def test_deployment_config_scaling():
    """Test deployment config scales up with P&L."""
    config = DeploymentConfig(
        initial_capital_pct=0.10,
        scaling_thresholds=[
            ScalingThreshold(pnl_pct=0.05, new_capital_pct=0.25),
            ScalingThreshold(pnl_pct=0.10, new_capital_pct=0.50),
        ],
    )

    # Below first threshold
    assert config.get_current_allocation(0.03) == 0.10

    # Above first threshold
    assert config.get_current_allocation(0.07) == 0.25

    # Above second threshold
    assert config.get_current_allocation(0.15) == 0.50


def test_deployment_config_max_cap():
    """Test deployment config respects max allocation."""
    config = DeploymentConfig(
        initial_capital_pct=0.10,
        max_capital_pct=0.75,
        scaling_thresholds=[
            ScalingThreshold(pnl_pct=0.05, new_capital_pct=1.0),
        ],
    )
    # Even though threshold says 100%, max is 75%
    assert config.get_current_allocation(0.10) == 0.75


def test_metrics_gauges():
    """Test Prometheus gauge metrics."""
    metrics = TradingMetrics()
    metrics.set_gauge("active_positions", 5)
    metrics.set_gauge("total_pnl", 1500.0)

    summary = metrics.get_summary()
    assert summary["active_positions"] == 5
    assert summary["total_pnl"] == 1500.0


def test_metrics_counters():
    """Test Prometheus counter metrics."""
    metrics = TradingMetrics()
    metrics.increment_counter("orders_filled_total", 3)
    metrics.increment_counter("orders_filled_total", 2)

    summary = metrics.get_summary()
    assert summary["orders_filled_total"] == 5


def test_metrics_histograms():
    """Test Prometheus histogram/latency metrics."""
    metrics = TradingMetrics()
    for i in range(100):
        metrics.observe_latency("signal_latency_ms", float(i))

    summary = metrics.get_summary()
    assert summary["signal_latency_ms_p50"] == 50.0
    assert summary["signal_latency_ms_p95"] == 95.0


def test_metrics_prometheus_format():
    """Test Prometheus exposition format output."""
    metrics = TradingMetrics()
    metrics.set_gauge("active_positions", 3)
    metrics.increment_counter("orders_filled_total", 10)
    metrics.observe_latency("signal_latency_ms", 5.0)

    text = metrics.get_metrics_text()
    assert "algoforge_active_positions 3" in text
    assert "algoforge_orders_filled_total 10" in text
    assert "algoforge_signal_latency_ms" in text
