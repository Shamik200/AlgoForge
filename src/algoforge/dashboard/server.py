"""FastAPI WebSocket server for the monitoring dashboard.

Streams DashboardState snapshots to connected clients at ~1Hz.
Accepts kill switch commands on the same WebSocket connection.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

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

logger = logging.getLogger(__name__)


class DashboardServer:
    """WebSocket server for real-time dashboard updates.

    In production, this would be run inside a FastAPI app:

        from fastapi import FastAPI, WebSocket
        app = FastAPI()
        server = DashboardServer()

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await server.handle_connection(websocket)

    For the core library, we implement the state management and
    snapshot generation logic. The FastAPI integration is a thin wrapper.
    """

    def __init__(self, broadcast_interval: float = 1.0) -> None:
        """Initialize the dashboard server.

        Args:
            broadcast_interval: Seconds between state broadcasts (default 1Hz).
        """
        self.broadcast_interval = broadcast_interval
        self._system_state = SystemState.STARTING
        self._positions: list[PositionView] = []
        self._signals: list[SignalHealthView] = []
        self._regime: RegimeView | None = None
        self._equity_curve: list[EquityPoint] = []
        self._total_pnl: float = 0.0
        self._total_trades: int = 0
        self._win_rate: float = 0.0
        self._sharpe: float = 0.0
        self._start_time: datetime = datetime.now()
        self._kill_switch_callback: Any = None
        self._connected_clients: list[Any] = []

    def set_kill_switch_callback(self, callback: Any) -> None:
        """Register the callback invoked when the kill switch is triggered.

        Args:
            callback: An async callable that flattens all positions.
        """
        self._kill_switch_callback = callback

    def update_positions(self, positions: list[PositionView]) -> None:
        """Update the current positions snapshot."""
        self._positions = positions

    def update_signals(self, signals: list[SignalHealthView]) -> None:
        """Update the signal family health snapshot."""
        self._signals = signals

    def update_regime(self, regime: RegimeView) -> None:
        """Update the HMM regime state."""
        self._regime = regime

    def update_system_metrics(
        self,
        total_pnl: float,
        total_trades: int,
        win_rate: float,
        sharpe: float,
    ) -> None:
        """Update aggregate system performance metrics."""
        self._total_pnl = total_pnl
        self._total_trades = total_trades
        self._win_rate = win_rate
        self._sharpe = sharpe

    def add_equity_point(self, value: float) -> None:
        """Append a new point to the equity curve."""
        point = EquityPoint(
            timestamp=datetime.now().isoformat(),
            value=value,
        )
        self._equity_curve.append(point)
        # Keep last 500 points for display
        if len(self._equity_curve) > 500:
            self._equity_curve = self._equity_curve[-500:]

    def set_system_state(self, state: SystemState) -> None:
        """Set the overall system state."""
        self._system_state = state

    def generate_snapshot(self) -> DashboardState:
        """Generate a complete dashboard state snapshot.

        Returns:
            DashboardState ready for JSON serialization and WebSocket broadcast.
        """
        uptime = int((datetime.now() - self._start_time).total_seconds())

        # Calculate total P&L percentage (assume 100k starting capital)
        starting_capital = 100_000.0
        pnl_pct = self._total_pnl / starting_capital if starting_capital > 0 else 0.0

        system = SystemStatus(
            state=self._system_state,
            uptime_seconds=uptime,
            total_pnl=self._total_pnl,
            total_pnl_pct=pnl_pct,
            total_trades=self._total_trades,
            win_rate=self._win_rate,
            sharpe_ratio=self._sharpe,
        )

        return DashboardState(
            timestamp=datetime.now().isoformat(),
            system=system,
            positions=list(self._positions),
            signals=list(self._signals),
            regime=self._regime,
            equity_curve=list(self._equity_curve),
        )

    async def handle_kill_switch(self) -> dict:
        """Handle the kill switch command.

        Returns:
            Confirmation dict with execution result.
        """
        logger.warning("[KILL SWITCH] Triggered! Flattening all positions...")
        self._system_state = SystemState.KILLED

        if self._kill_switch_callback:
            try:
                await self._kill_switch_callback()
                return {"status": "executed", "message": "All positions flattened"}
            except Exception as e:
                logger.error("[KILL SWITCH] Error: %s", e)
                return {"status": "error", "message": str(e)}
        else:
            return {"status": "executed", "message": "Kill switch triggered (no callback registered)"}

    async def handle_message(self, message: str) -> dict | None:
        """Process an incoming WebSocket message.

        Args:
            message: JSON string from the client.

        Returns:
            Response dict, or None for state-only messages.
        """
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON"}

        command = data.get("command")

        if command == "FLATTEN_ALL":
            return await self.handle_kill_switch()
        elif command == "PAUSE":
            self._system_state = SystemState.PAUSED
            return {"status": "paused"}
        elif command == "RESUME":
            self._system_state = SystemState.RUNNING
            return {"status": "running"}
        elif command == "GET_SNAPSHOT":
            return self.generate_snapshot().to_dict()
        else:
            return {"error": f"Unknown command: {command}"}
