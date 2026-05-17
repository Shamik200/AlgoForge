"""Dashboard backend facade.

Coordinates the paper engine, risk manager, and enhanced PnL tracker so the
monitoring dashboard can read a single coherent performance view.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from algoforge.dashboard.models import DashboardState, SystemState, SystemStatus
from algoforge.dashboard.server import DashboardServer
from algoforge.execution.paper import PaperTradingEngine
from algoforge.monitoring.dashboard import Dashboard, DashboardSnapshot
from algoforge.monitoring.pnl_tracker import EnhancedPnLTracker
from algoforge.risk.manager import RiskManager


class DashboardBackend:
    """High-level dashboard aggregation backend."""

    def __init__(
        self,
        paper_engine: PaperTradingEngine | None = None,
        risk_manager: RiskManager | None = None,
        dashboard_server: DashboardServer | None = None,
        tracker: EnhancedPnLTracker | None = None,
    ) -> None:
        self.paper_engine = paper_engine
        self.risk_manager = risk_manager
        self.dashboard = Dashboard(paper_engine=paper_engine, risk_manager=risk_manager)
        self.dashboard_server = dashboard_server
        self.tracker = tracker or EnhancedPnLTracker(
            initial_capital=paper_engine.snapshot().equity if paper_engine else 100_000.0
        )
        self._seen_trade_ids: set[str] = set()
        self._start_time = datetime.now(timezone.utc)

    def sync(self) -> None:
        """Pull the latest trade/equity state from the engine."""
        if self.paper_engine:
            snapshot = self.paper_engine.snapshot()

            for trade in self.paper_engine.trade_history:
                if trade.id in self._seen_trade_ids:
                    continue
                self.tracker.record_trade(trade)
                self._seen_trade_ids.add(trade.id)

            if snapshot.equity != self.tracker.current_equity:
                self.tracker.update_equity(snapshot.equity)

        if self.dashboard_server:
            pnl = self.tracker.summary()
            self.dashboard_server.update_system_metrics(
                total_pnl=pnl.total_pnl,
                total_trades=pnl.total_trades,
                win_rate=pnl.win_rate,
                sharpe=pnl.sharpe_ratio,
            )
            self.dashboard_server.add_equity_point(self.tracker.current_equity)

    def snapshot(self) -> DashboardSnapshot:
        """Return the monitoring dashboard snapshot."""
        self.sync()
        snap = self.dashboard.snapshot()
        pnl = self.tracker.summary()
        snap.risk_stats.update(
            {
                "tracker_total_pnl": pnl.total_pnl,
                "tracker_win_rate": round(pnl.win_rate, 4),
                "tracker_profit_factor": pnl.profit_factor,
                "tracker_expectancy": pnl.expectancy,
                "tracker_max_drawdown_pct": pnl.max_drawdown_pct,
                "tracker_sharpe_ratio": pnl.sharpe_ratio,
            }
        )
        return snap

    def dashboard_state(self) -> DashboardState:
        """Return the websocket-ready dashboard state."""
        self.sync()
        if self.dashboard_server:
            return self.dashboard_server.generate_snapshot()

        pnl = self.tracker.summary()
        system = SystemStatus(
            state=SystemState.RUNNING if self.paper_engine else SystemState.STARTING,
            uptime_seconds=int((datetime.now(timezone.utc) - self._start_time).total_seconds()),
            total_pnl=pnl.total_pnl,
            total_pnl_pct=(pnl.total_pnl / self.tracker.initial_capital) if self.tracker.initial_capital > 0 else 0.0,
            total_trades=pnl.total_trades,
            win_rate=pnl.win_rate,
            sharpe_ratio=pnl.sharpe_ratio,
        )
        return DashboardState(
            timestamp=datetime.now(timezone.utc).isoformat(),
            system=system,
            equity_curve=self.tracker.equity_curve,
        )

    def export_summary(self) -> dict[str, Any]:
        """Return a JSON-friendly summary for APIs or UI dashboards."""
        pnl = self.tracker.summary()
        return {
            "dashboard": self.snapshot().model_dump(mode="json"),
            "pnl_tracker": self.tracker.to_dict(),
            "summary": pnl.__dict__,
        }