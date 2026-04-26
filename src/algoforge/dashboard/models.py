"""Dashboard data models for real-time monitoring.

These models define the shape of data sent from the trading engine
to the monitoring dashboard via WebSocket.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SystemState(str, Enum):
    """Overall engine state."""
    RUNNING = "running"
    PAUSED = "paused"
    KILLED = "killed"
    STARTING = "starting"


class HealthStatus(str, Enum):
    """Signal family health status for display."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    PAUSED = "paused"


@dataclass
class PositionView:
    """Simplified position for dashboard display."""
    symbol: str
    side: str  # "LONG" or "SHORT"
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "entryPrice": self.entry_price,
            "currentPrice": self.current_price,
            "unrealizedPnl": round(self.unrealized_pnl, 2),
            "unrealizedPnlPct": round(self.unrealized_pnl_pct, 4),
        }


@dataclass
class SignalHealthView:
    """Per-signal-family health status for the health dashboard."""
    family_name: str
    current_score: float  # [-1, 1]
    health_multiplier: float  # [0, 1]
    status: HealthStatus
    conviction_weight: float  # Post-combination weight

    def to_dict(self) -> dict:
        return {
            "familyName": self.family_name,
            "currentScore": round(self.current_score, 4),
            "healthMultiplier": round(self.health_multiplier, 4),
            "status": self.status.value,
            "convictionWeight": round(self.conviction_weight, 4),
        }


@dataclass
class RegimeView:
    """HMM regime probabilities for visualization."""
    bull_prob: float
    bear_prob: float
    sideways_prob: float
    current_regime: str  # "bull", "bear", "sideways"
    bars_in_regime: int

    def to_dict(self) -> dict:
        return {
            "bullProb": round(self.bull_prob, 4),
            "bearProb": round(self.bear_prob, 4),
            "sidewaysProb": round(self.sideways_prob, 4),
            "currentRegime": self.current_regime,
            "barsInRegime": self.bars_in_regime,
        }


@dataclass
class EquityPoint:
    """A single point on the equity curve."""
    timestamp: str
    value: float

    def to_dict(self) -> dict:
        return {"timestamp": self.timestamp, "value": round(self.value, 2)}


@dataclass
class SystemStatus:
    """Overall system status for the control panel."""
    state: SystemState
    uptime_seconds: int
    total_pnl: float
    total_pnl_pct: float
    total_trades: int
    win_rate: float
    sharpe_ratio: float

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "uptimeSeconds": self.uptime_seconds,
            "totalPnl": round(self.total_pnl, 2),
            "totalPnlPct": round(self.total_pnl_pct, 4),
            "totalTrades": self.total_trades,
            "winRate": round(self.win_rate, 4),
            "sharpeRatio": round(self.sharpe_ratio, 4),
        }


@dataclass
class DashboardState:
    """Complete state snapshot sent to the dashboard via WebSocket.

    This is the single object streamed to the frontend at ~1Hz.
    """
    timestamp: str
    system: SystemStatus
    positions: list[PositionView] = field(default_factory=list)
    signals: list[SignalHealthView] = field(default_factory=list)
    regime: RegimeView | None = None
    equity_curve: list[EquityPoint] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "system": self.system.to_dict(),
            "positions": [p.to_dict() for p in self.positions],
            "signals": [s.to_dict() for s in self.signals],
            "regime": self.regime.to_dict() if self.regime else None,
            "equityCurve": [e.to_dict() for e in self.equity_curve],
        }
