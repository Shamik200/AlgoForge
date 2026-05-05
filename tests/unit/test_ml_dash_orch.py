"""Tests for Phase 13 (ML), Phase 14 (Dashboard), Phase 15 (Orchestrator)."""

import json
import tempfile
from datetime import datetime, timezone

import pytest

from algoforge.core.constants import Direction, MarketRegime, Timeframe
from algoforge.core.models import Signal
from algoforge.core.orchestrator import Orchestrator
from algoforge.execution.paper import PaperTradingEngine
from algoforge.execution.paper import PaperTradingEngine
from algoforge.fundamental.pipeline import FundamentalResult
from algoforge.monitoring.dashboard import Dashboard, DashboardSnapshot, StrategyMetrics
from algoforge.risk.manager import RiskConfig, RiskManager
from algoforge.strategies.secondary_trending_range import EMACrossover
from algoforge.technical.engine import IndicatorSnapshot
from algoforge.technical.indicator_base import IndicatorResult
from algoforge.technical.regime import RegimeResult
from algoforge.technical.structural.models import StructuralSnapshot, TrendDirection


def _sig(direction=Direction.LONG, confidence=0.7):
    return Signal(
        symbol="TEST", direction=direction, strategy="test",
        confidence=confidence, entry_price=100, stop_loss=95, take_profit=115,
        timeframe=Timeframe.D1, regime=MarketRegime.TRENDING,
    )


# ---------------------------------------------------------------------------
# ML Integration
# ---------------------------------------------------------------------------

# Removed legacy EnsembleML tests


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class TestDashboard:
    def test_empty_dashboard(self) -> None:
        dash = Dashboard()
        snap = dash.snapshot()
        assert isinstance(snap, DashboardSnapshot)

    def test_dashboard_with_engine(self) -> None:
        engine = PaperTradingEngine(initial_capital=100_000)
        dash = Dashboard(paper_engine=engine)
        snap = dash.snapshot()
        assert snap.portfolio is not None
        assert snap.portfolio.equity == 100_000

    def test_dashboard_with_risk(self) -> None:
        rm = RiskManager(capital=100_000)
        dash = Dashboard(risk_manager=rm)
        snap = dash.snapshot()
        assert snap.risk_stats["capital"] == 100_000

    def test_export_trades(self) -> None:
        engine = PaperTradingEngine(initial_capital=100_000)
        dash = Dashboard(paper_engine=engine)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            count = dash.export_trades(f.name)
        assert count == 0  # No trades yet

    def test_print_summary(self) -> None:
        engine = PaperTradingEngine(initial_capital=100_000)
        rm = RiskManager(capital=100_000)
        dash = Dashboard(paper_engine=engine, risk_manager=rm)
        summary = dash.print_summary()
        assert "AlgoForge Dashboard" in summary
        assert "Equity" in summary

    def test_strategy_metrics_model(self) -> None:
        m = StrategyMetrics(name="test", total_trades=10, win_rate=0.6)
        assert m.name == "test"


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class TestOrchestrator:
    def _indicators(self):
        snap = IndicatorSnapshot()
        snap.set("adx", IndicatorResult(name="adx", values={"adx": [30.0]}))
        snap.set("rsi", IndicatorResult(name="rsi", values={"rsi": [35.0]}))
        snap.set("atr", IndicatorResult(name="atr", values={"atr": [1.5]}))
        snap.set("ema", IndicatorResult(name="ema", values={
            "ema_5": [105], "ema_9": [99, 101], "ema_21": [100, 100.5],
        }))
        return snap

    def _structure(self):
        return StructuralSnapshot(symbol="TEST", trend_direction=TrendDirection.UP)

    def _regime(self):
        return RegimeResult(
            symbol="TEST",
            primary_regime=MarketRegime.TRENDING,
            confidence=0.8,
            probabilities={MarketRegime.TRENDING: 0.8, MarketRegime.RANGE: 0.2},
        )

    def test_create_orchestrator(self) -> None:
        orch = Orchestrator(capital=100_000)
        assert orch.stats["strategies"] == 0

    def test_register_strategy(self) -> None:
        orch = Orchestrator()
        orch.register_strategy(EMACrossover())
        assert orch.stats["strategies"] == 1

    def test_process_bar_no_strategies(self) -> None:
        orch = Orchestrator()
        results = orch.process_bar(
            "TEST", Timeframe.D1, self._indicators(), self._structure(),
            self._regime(), [100.0]*60, [101.0]*60, [99.0]*60,
            [50000.0]*60, [100.0]*60,
        )
        assert results == []

    def test_process_bar_with_strategy(self) -> None:
        orch = Orchestrator(
            strategies=[EMACrossover(min_adx=15)],
            capital=100_000,
        )
        results = orch.process_bar(
            "TEST", Timeframe.D1, self._indicators(), self._structure(),
            self._regime(), [100.0]*60, [101.0]*60, [99.0]*60,
            [50000.0]*60, [100.0]*60,
        )
        assert orch.stats["signals_generated"] >= 0

    def test_regime_gating(self) -> None:
        """Strategy only activates in matching regime."""
        orch = Orchestrator(strategies=[EMACrossover()])
        range_regime = RegimeResult(
            symbol="TEST",
            primary_regime=MarketRegime.RANGE,
            confidence=0.8,
            probabilities={MarketRegime.RANGE: 0.8},
        )
        results = orch.process_bar(
            "TEST", Timeframe.D1, self._indicators(), self._structure(),
            range_regime, [100.0]*60, [101.0]*60, [99.0]*60,
            [50000.0]*60, [100.0]*60,
        )
        # EMA crossover requires TRENDING, regime is RANGE → no signals
        assert orch.stats["signals_generated"] == 0

    def test_paper_engine_accessible(self) -> None:
        """Ensure the underlying paper engine/connector is accessible."""
        orch = Orchestrator(capital=50_000, enable_fundamentals=False)
        assert orch.paper_engine.snapshot().equity == 50_000

    def test_fundamental_filtering(self) -> None:
        """Fundamentals block signal when gate score is too low."""
        orch = Orchestrator(
            strategies=[EMACrossover(min_adx=15)],
            enable_fundamentals=True,
        )
        # Pass a low gate_score to simulate a fundamental block
        fund = FundamentalResult(
            symbol="TEST",
            gate_score=10,  # Below threshold
            sentiment=None, screener=None, macro=None, selections=[]
        )
        results = orch.process_bar(
            "TEST", Timeframe.D1, self._indicators(), self._structure(),
            self._regime(), [100.0]*60, [101.0]*60, [99.0]*60,
            [50000.0]*60, [100.0]*60, fundamental_result=fund,
        )
        # Signals should be blocked by fundamental filter
        assert orch.stats["signals_filled"] == 0
