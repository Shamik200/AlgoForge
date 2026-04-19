"""Dashboard & Monitoring — CLI and data export for monitoring.

Provides real-time portfolio metrics, strategy performance,
and trade logging in structured JSON format.

Requirements: DASH-01 to DASH-05
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import structlog
from pydantic import BaseModel, Field

from algoforge.execution.paper import PaperTradingEngine, PortfolioSnapshot, TradeRecord
from algoforge.risk.manager import RiskManager

logger = structlog.get_logger(__name__)


class StrategyMetrics(BaseModel):
    """Performance metrics for a single strategy."""

    name: str
    total_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    avg_pnl: float = 0.0
    avg_holding_bars: float = 0.0


class DashboardSnapshot(BaseModel):
    """Complete dashboard state for export."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    portfolio: PortfolioSnapshot | None = None
    strategy_metrics: list[StrategyMetrics] = Field(default_factory=list)
    risk_stats: dict[str, Any] = Field(default_factory=dict)
    active_signals: int = 0
    uptime_seconds: float = 0.0


class Dashboard:
    """Real-time monitoring dashboard.

    DASH-01: Portfolio overview (equity, positions, P&L)
    DASH-02: Strategy-level metrics
    DASH-03: Risk status monitoring
    DASH-04: Trade log export
    DASH-05: Structured JSON output

    Usage:
        dash = Dashboard(paper_engine, risk_manager)
        snapshot = dash.snapshot()
        dash.export_trades("trades.json")
    """

    def __init__(
        self,
        paper_engine: PaperTradingEngine | None = None,
        risk_manager: RiskManager | None = None,
    ) -> None:
        self._engine = paper_engine
        self._risk = risk_manager
        self._start_time = datetime.now(timezone.utc)

    def snapshot(self) -> DashboardSnapshot:
        """Get current dashboard state."""
        portfolio = None
        if self._engine:
            portfolio = self._engine.snapshot()

        risk_stats = {}
        if self._risk:
            risk_stats = self._risk.stats

        strategy_metrics = self._compute_strategy_metrics()
        elapsed = (datetime.now(timezone.utc) - self._start_time).total_seconds()

        return DashboardSnapshot(
            portfolio=portfolio,
            strategy_metrics=strategy_metrics,
            risk_stats=risk_stats,
            uptime_seconds=round(elapsed, 1),
        )

    def _compute_strategy_metrics(self) -> list[StrategyMetrics]:
        """Compute per-strategy performance metrics."""
        if not self._engine:
            return []

        by_strategy: dict[str, list[TradeRecord]] = {}
        for trade in self._engine.trade_history:
            by_strategy.setdefault(trade.strategy, []).append(trade)

        metrics = []
        for name, trades in by_strategy.items():
            wins = sum(1 for t in trades if t.pnl > 0)
            total_pnl = sum(t.pnl for t in trades)
            metrics.append(StrategyMetrics(
                name=name,
                total_trades=len(trades),
                win_rate=wins / len(trades) if trades else 0,
                total_pnl=round(total_pnl, 2),
                avg_pnl=round(total_pnl / len(trades), 2) if trades else 0,
                avg_holding_bars=round(
                    sum(t.bars_held for t in trades) / len(trades), 1
                ) if trades else 0,
            ))

        return metrics

    def export_trades(self, filepath: str) -> int:
        """Export trade history to JSON (DASH-04, DASH-05)."""
        if not self._engine:
            return 0

        trades = self._engine.trade_history
        data = [t.model_dump(mode="json") for t in trades]

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)

        logger.info("trades_exported", filepath=filepath, count=len(data))
        return len(data)

    def print_summary(self) -> str:
        """Generate text summary for CLI output."""
        snap = self.snapshot()
        lines = [
            "═" * 50,
            " AlgoForge Dashboard",
            "═" * 50,
        ]

        if snap.portfolio:
            p = snap.portfolio
            lines.extend([
                f"  Equity:     ${p.equity:,.2f}",
                f"  Cash:       ${p.cash:,.2f}",
                f"  Positions:  {p.open_positions}",
                f"  Trades:     {p.total_trades} (W:{p.winning_trades} L:{p.losing_trades})",
                f"  Total P&L:  ${p.total_pnl:,.2f}",
                f"  Max DD:     {p.max_drawdown_pct:.2%}",
            ])

        if snap.strategy_metrics:
            lines.append("\n  Strategy Performance:")
            for m in snap.strategy_metrics:
                lines.append(f"    {m.name}: {m.total_trades} trades, WR:{m.win_rate:.0%}, P&L:${m.total_pnl:,.2f}")

        if snap.risk_stats:
            lines.append(f"\n  Kill Switch: {'🔴 ACTIVE' if snap.risk_stats.get('kill_switch') else '🟢 OK'}")

        lines.append("═" * 50)
        summary = "\n".join(lines)
        return summary
