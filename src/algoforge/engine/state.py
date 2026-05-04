"""Engine State — Centralized system state and configuration models.

Extracted from server.py monolith. Holds all mutable system state in a
single, inspectable object. All other engine modules read/write this state.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog
from pydantic import BaseModel, Field

from algoforge.core.constants import Timeframe
from algoforge.core.models import OHLCV
from algoforge.core.orchestrator import Orchestrator
from algoforge.engine.persistence import PersistenceStore
from algoforge.risk.manager import RiskConfig
from algoforge.technical.engine import IndicatorEngine
from algoforge.technical.structural.engine import StructuralEngine
from algoforge.technical.regime import RegimeClassifier
from algoforge.strategies.trendline_pullback import TrendlinePullback
from algoforge.strategies.secondary_trending_range import EMACrossover, MeanReversion, EMABounce
from algoforge.strategies.secondary_breakout_reversal import BreakoutStrategy, ReversalStrategy, LiquidityTrapStrategy

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------
# INTELLIGENCE MODELS
# ---------------------------------------------------------
class AssetMemory(BaseModel):
    """Tracks per-asset selection persistence and performance."""
    symbol: str
    cycles_selected: int = 0
    last_score: float = 0.0
    score_trend: str = "FLAT"
    historical_win_rate: float = 0.5
    total_trades: int = 0


class DiscoveryConfig(BaseModel):
    """Configuration for dynamic asset universe discovery."""
    market: str = "crypto"
    universe_size: int = 75
    dynamic_threshold: float = 45.0
    min_liquidity: float = 500_000.0
    max_active_assets: int = 10  # max concurrent WebSocket streams


# ---------------------------------------------------------
# SYSTEM STATE — Single source of truth
# ---------------------------------------------------------
class SystemState:
    """Centralized mutable system state.

    All engine modules (universe, live_handler, trading_loop) share
    this state object. Consolidates what was scattered across
    server.py global variables.
    """

    def __init__(self) -> None:
        self.is_running = False
        self.discovery_config = DiscoveryConfig()
        self.active_broker = "binance"

        # IMPORTANT: All pct fields use FRACTIONAL notation (0.015 = 1.5%, 0.15 = 15%)
        self.risk_config = RiskConfig(
            max_risk_per_trade_pct=0.015,        # 1.5% risk per trade
            max_drawdown_pct=0.15,               # 15% max drawdown kill switch
            max_daily_loss_pct=0.05,             # 5% daily loss limit
            max_weekly_loss_pct=0.10,            # 10% weekly loss limit
            max_correlation=0.85,                # crypto pairs are highly correlated
            min_risk_reward=1.2,                 # aligned with strategy min_rr=1.2
            max_open_positions=10,
            max_consecutive_losses=8,            # less aggressive cooldown trigger
            cooldown_bars=15,                    # 15 bars (~15min) not 1 hour
            max_directional_exposure_pct=0.85,   # crypto trends — allow directional bias
        )
        self.indicator_engine = IndicatorEngine()
        self.structural_engine = StructuralEngine()
        self.regime_classifier = RegimeClassifier()

        self.orchestrator = Orchestrator(
            strategies=[
                TrendlinePullback(),
                EMACrossover(min_rr=1.2),
                EMABounce(atr_proximity=2.5, min_rr=1.2),
                MeanReversion(rsi_oversold=35.0, rsi_overbought=65.0, min_rr=1.2),
                BreakoutStrategy(volume_mult=1.5, min_rr=1.2),
                ReversalStrategy(rsi_extreme=30.0, min_rr=1.2),
                LiquidityTrapStrategy(min_rr=1.2)
            ],
            capital=100_000.0,
            risk_config=self.risk_config,
            enable_fundamentals=True,
            enable_ml=True,
            enable_combination=True,
            enable_dual_tf=True,
        )
        self._ml_trained = False

        self.latest_logs: list[str] = []
        self.equity_history: list[dict] = []

        self.asset_memory: dict[str, AssetMemory] = {}
        self.scored_assets: list[dict] = []
        self.selected_assets: list[str] = []

        # Live Data Buffers
        self.live_books: dict[str, dict] = {}
        self.kline_buffers: dict[str, list[OHLCV]] = {}
        self.connector: Any = None

        # Live regime tracking per asset
        self.asset_regimes: dict[str, str] = {}
        self.asset_confidence: dict[str, float] = {}

        # Strategy signal counters
        self.strategy_signals: dict[str, int] = {}

        # Phase 4: Data Persistence
        self.persistence = PersistenceStore()
        self._checkpoint_counter = 0

    def save_checkpoint(self) -> None:
        """Save periodic state checkpoint (call every 60 bars ~ 1 hour at 1m)."""
        self._checkpoint_counter += 1
        if self._checkpoint_counter % 60 != 0:
            return

        try:
            engine = self.orchestrator._paper
            snap = engine.snapshot()
            positions = [p.model_dump(mode='json') for p in engine.open_positions]
            self.persistence.save_full_state(
                equity=snap.equity,
                cash=snap.cash,
                positions=positions,
                selected_assets=self.selected_assets,
                ml_trained=self._ml_trained,
            )
        except Exception as e:
            logger.warning(f"State checkpoint failed: {e}")

    def restore_checkpoint(self) -> None:
        """Restore state from the last checkpoint."""
        try:
            state = self.persistence.load_full_state()
            if not state:
                return

            if "selected_assets" in state:
                self.selected_assets = state["selected_assets"]
            if "ml_trained" in state:
                self._ml_trained = state["ml_trained"]

            engine = self.orchestrator._paper
            if engine:
                engine.load_state(state)
            
            logger.info("system_state_restored")
        except Exception as e:
            logger.warning(f"State restore failed: {e}")

    def persist_trade(self, trade) -> None:
        """Persist a completed trade to SQLite."""
        try:
            self.persistence.save_trade({
                "id": trade.id,
                "symbol": trade.symbol,
                "direction": trade.direction.value,
                "strategy": trade.strategy,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "quantity": trade.quantity,
                "entry_time": trade.entry_time.isoformat(),
                "exit_time": trade.exit_time.isoformat(),
                "pnl": trade.pnl,
                "commission": trade.commission,
                "slippage": trade.slippage,
                "bars_held": trade.bars_held,
            })
        except Exception as e:
            logger.warning(f"Trade persistence failed: {e}")

    def persist_klines(self, symbol: str) -> None:
        """Persist kline buffer for a symbol to SQLite cache."""
        if symbol not in self.kline_buffers:
            return
        try:
            candles = [
                {
                    "timestamp": c.timestamp.isoformat(),
                    "open": c.open, "high": c.high,
                    "low": c.low, "close": c.close,
                    "volume": c.volume,
                }
                for c in self.kline_buffers[symbol][-300:]
            ]
            self.persistence.save_klines(symbol, "1m", candles)
        except Exception as e:
            logger.warning(f"Kline persistence failed for {symbol}: {e}")


def log_msg(state: SystemState, msg: str) -> None:
    """Append a timestamped log message to state and emit structlog."""
    logger.info(msg)
    ts = datetime.now().strftime("%H:%M:%S")
    state.latest_logs.insert(0, f"[{ts}] {msg}")
    if len(state.latest_logs) > 50:
        state.latest_logs.pop()
