"""Tests for the enhanced PnL tracker and dashboard backend."""

from datetime import datetime, timezone

from algoforge.backtest.models import TradePnL
from algoforge.core.constants import Direction, MarketRegime, Timeframe
from algoforge.core.models import Signal
from algoforge.dashboard.backend import DashboardBackend
from algoforge.execution.paper import PaperTradingEngine
from algoforge.monitoring.pnl_tracker import EnhancedPnLTracker


def _signal() -> Signal:
    return Signal(
        symbol="TEST",
        direction=Direction.LONG,
        strategy="test",
        confidence=0.8,
        entry_price=100,
        stop_loss=95,
        take_profit=110,
        timeframe=Timeframe.D1,
        regime=MarketRegime.TRENDING,
        metadata={"signal_family": "momentum"},
    )


def test_enhanced_pnl_tracker_summary() -> None:
    tracker = EnhancedPnLTracker(initial_capital=100_000)
    tracker.record_trade(
        TradePnL(
            trade_id="1",
            symbol="TEST",
            direction="long",
            entry_price=100,
            exit_price=110,
            quantity=10,
            pnl_amount=100,
            pnl_pct=0.01,
            opened_at=datetime.now(timezone.utc),
            closed_at=datetime.now(timezone.utc),
            friction_cost=1.0,
        )
    )
    tracker.record_trade(
        TradePnL(
            trade_id="2",
            symbol="TEST",
            direction="long",
            entry_price=100,
            exit_price=95,
            quantity=10,
            pnl_amount=-50,
            pnl_pct=-0.005,
            opened_at=datetime.now(timezone.utc),
            closed_at=datetime.now(timezone.utc),
            friction_cost=1.0,
        )
    )

    summary = tracker.summary()
    assert summary.total_trades == 2
    assert summary.total_pnl == 50
    assert 0.4 <= summary.win_rate <= 0.6
    assert summary.max_drawdown_pct >= 0.0


def test_dashboard_backend_consumes_trade_history() -> None:
    engine = PaperTradingEngine(initial_capital=100_000)
    fill = engine.submit_signal(_signal())
    assert fill.filled is True

    engine.update_prices({"TEST": 111.0})
    closed = engine.check_exits(current_bar=1)
    assert len(closed) == 1

    backend = DashboardBackend(paper_engine=engine)
    snapshot = backend.snapshot()
    state = backend.dashboard_state()
    export = backend.export_summary()

    assert snapshot.risk_stats["tracker_total_pnl"] > 0
    assert state.system.total_trades == 1
    assert export["summary"]["total_trades"] == 1