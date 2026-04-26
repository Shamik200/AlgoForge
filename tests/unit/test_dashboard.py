"""Unit tests for the Dashboard & Monitoring module."""

import asyncio
import json

import pytest

from algoforge.dashboard.models import (
    DashboardState,
    EquityPoint,
    HealthStatus,
    PositionView,
    RegimeView,
    SignalHealthView,
    SystemState,
    SystemStatus,
)
from algoforge.dashboard.server import DashboardServer


def test_position_view_serialization():
    """Test PositionView serializes to camelCase JSON dict."""
    pos = PositionView(
        symbol="AAPL", side="LONG", quantity=100,
        entry_price=150.0, current_price=155.0,
        unrealized_pnl=500.0, unrealized_pnl_pct=0.0333,
    )
    d = pos.to_dict()

    assert d["symbol"] == "AAPL"
    assert d["side"] == "LONG"
    assert d["entryPrice"] == 150.0
    assert d["currentPrice"] == 155.0
    assert d["unrealizedPnl"] == 500.0


def test_signal_health_view_serialization():
    """Test SignalHealthView serializes correctly."""
    sig = SignalHealthView(
        family_name="momentum", current_score=0.75,
        health_multiplier=1.0, status=HealthStatus.HEALTHY,
        conviction_weight=0.25,
    )
    d = sig.to_dict()

    assert d["familyName"] == "momentum"
    assert d["status"] == "healthy"
    assert d["healthMultiplier"] == 1.0


def test_regime_view_serialization():
    """Test RegimeView serializes correctly."""
    regime = RegimeView(
        bull_prob=0.7, bear_prob=0.1, sideways_prob=0.2,
        current_regime="bull", bars_in_regime=42,
    )
    d = regime.to_dict()

    assert d["bullProb"] == 0.7
    assert d["currentRegime"] == "bull"
    assert d["barsInRegime"] == 42


def test_dashboard_state_full_snapshot():
    """Test full DashboardState serialization."""
    system = SystemStatus(
        state=SystemState.RUNNING, uptime_seconds=3600,
        total_pnl=1500.0, total_pnl_pct=0.015,
        total_trades=25, win_rate=0.56, sharpe_ratio=1.8,
    )
    state = DashboardState(
        timestamp="2026-04-26T12:00:00",
        system=system,
        positions=[PositionView("AAPL", "LONG", 100, 150, 155, 500, 0.033)],
        signals=[SignalHealthView("momentum", 0.5, 1.0, HealthStatus.HEALTHY, 0.25)],
        regime=RegimeView(0.7, 0.1, 0.2, "bull", 42),
        equity_curve=[EquityPoint("2026-04-26T11:00:00", 100500.0)],
    )
    d = state.to_dict()

    assert d["system"]["state"] == "running"
    assert len(d["positions"]) == 1
    assert len(d["signals"]) == 1
    assert d["regime"]["currentRegime"] == "bull"
    assert len(d["equityCurve"]) == 1

    # Must be JSON serializable
    json_str = json.dumps(d)
    assert len(json_str) > 0


def test_server_snapshot_generation():
    """Test server generates valid snapshots."""
    server = DashboardServer()
    server.set_system_state(SystemState.RUNNING)
    server.update_positions([
        PositionView("AAPL", "LONG", 100, 150, 155, 500, 0.033),
    ])
    server.update_signals([
        SignalHealthView("momentum", 0.5, 1.0, HealthStatus.HEALTHY, 0.25),
    ])
    server.update_regime(RegimeView(0.7, 0.1, 0.2, "bull", 42))
    server.update_system_metrics(1500.0, 25, 0.56, 1.8)
    server.add_equity_point(101500.0)

    snapshot = server.generate_snapshot()

    assert snapshot.system.state == SystemState.RUNNING
    assert len(snapshot.positions) == 1
    assert len(snapshot.signals) == 1
    assert snapshot.regime is not None
    assert len(snapshot.equity_curve) == 1

    # Serialize to JSON
    d = snapshot.to_dict()
    assert json.dumps(d)


@pytest.mark.asyncio
async def test_server_kill_switch():
    """Test kill switch changes system state."""
    server = DashboardServer()
    server.set_system_state(SystemState.RUNNING)

    result = await server.handle_kill_switch()

    assert result["status"] == "executed"
    assert server._system_state == SystemState.KILLED


@pytest.mark.asyncio
async def test_server_message_handling():
    """Test WebSocket message routing."""
    server = DashboardServer()
    server.set_system_state(SystemState.RUNNING)

    # Test PAUSE command
    result = await server.handle_message(json.dumps({"command": "PAUSE"}))
    assert result["status"] == "paused"
    assert server._system_state == SystemState.PAUSED

    # Test RESUME command
    result = await server.handle_message(json.dumps({"command": "RESUME"}))
    assert result["status"] == "running"
    assert server._system_state == SystemState.RUNNING

    # Test unknown command
    result = await server.handle_message(json.dumps({"command": "INVALID"}))
    assert "error" in result


@pytest.mark.asyncio
async def test_server_kill_switch_with_callback():
    """Test kill switch invokes the registered callback."""
    callback_invoked = False

    async def mock_flatten():
        nonlocal callback_invoked
        callback_invoked = True

    server = DashboardServer()
    server.set_kill_switch_callback(mock_flatten)
    server.set_system_state(SystemState.RUNNING)

    result = await server.handle_message(json.dumps({"command": "FLATTEN_ALL"}))

    assert result["status"] == "executed"
    assert callback_invoked is True
    assert server._system_state == SystemState.KILLED


def test_equity_curve_capping():
    """Test equity curve is capped at 500 points."""
    server = DashboardServer()

    for i in range(600):
        server.add_equity_point(100_000 + i * 10)

    snapshot = server.generate_snapshot()
    assert len(snapshot.equity_curve) == 500
