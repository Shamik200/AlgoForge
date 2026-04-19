"""Tests for Phase 7 — Paper Trading Engine."""

import pytest

from algoforge.core.constants import Direction, Market, MarketRegime, Timeframe
from algoforge.core.models import Signal
from algoforge.execution.paper import (
    FillResult,
    PaperTradingEngine,
    PortfolioSnapshot,
    TradeRecord,
)
from algoforge.risk.manager import RiskConfig


def _signal(
    symbol: str = "AAPL", direction: Direction = Direction.LONG,
    entry: float = 100.0, sl: float = 95.0, tp: float = 115.0,
) -> Signal:
    return Signal(
        symbol=symbol, direction=direction, strategy="test",
        confidence=0.7, entry_price=entry, stop_loss=sl, take_profit=tp,
        timeframe=Timeframe.D1, regime=MarketRegime.TRENDING,
    )


class TestPaperTradingEngine:
    """Test paper trading execution."""

    def test_submit_valid_signal(self) -> None:
        """Valid signal → filled with position created."""
        engine = PaperTradingEngine(initial_capital=100_000)
        result = engine.submit_signal(_signal())
        assert result.filled
        assert result.position_id != ""
        assert result.fill_price > 0
        assert result.commission > 0
        assert len(engine.open_positions) == 1

    def test_slippage_applied(self) -> None:
        """PAPR-01: Slippage makes fill price worse."""
        engine = PaperTradingEngine(initial_capital=100_000, slippage_pct=0.001)
        sig = _signal(entry=100.0)
        result = engine.submit_signal(sig)
        assert result.filled
        # Long fill should be above entry (slippage)
        assert result.fill_price > 100.0
        assert result.slippage > 0

    def test_short_slippage(self) -> None:
        """Short fills below entry price."""
        engine = PaperTradingEngine(initial_capital=100_000, slippage_pct=0.001)
        sig = _signal(direction=Direction.SHORT, entry=100, sl=105, tp=85)
        result = engine.submit_signal(sig)
        assert result.filled
        assert result.fill_price < 100.0

    def test_commission_us_stocks(self) -> None:
        """PAPR-02: US stock commission model."""
        engine = PaperTradingEngine(initial_capital=100_000, market=Market.STOCKS_US)
        result = engine.submit_signal(_signal())
        assert result.filled
        assert result.commission >= 1.0  # Min commission for US

    def test_commission_india(self) -> None:
        """PAPR-02: India market includes STT."""
        engine = PaperTradingEngine(initial_capital=10_000_000, market=Market.STOCKS_INDIA)
        result = engine.submit_signal(_signal(entry=1000, sl=950, tp=1150))
        assert result.filled
        assert result.commission > 0

    def test_commission_crypto(self) -> None:
        """PAPR-02: Crypto percentage commission."""
        engine = PaperTradingEngine(initial_capital=100_000, market=Market.CRYPTO)
        result = engine.submit_signal(_signal(entry=50000, sl=48000, tp=55000))
        assert result.filled
        assert result.commission > 0

    def test_latency_simulation(self) -> None:
        """PAPR-03: Latency simulation with random jitter."""
        engine = PaperTradingEngine(
            initial_capital=100_000,
            latency_min_ms=50.0,
            latency_max_ms=200.0,
            latency_enabled=True,
        )
        result = engine.submit_signal(_signal())
        assert result.filled
        assert 50.0 <= result.latency_ms <= 200.0
        # Fill price should differ from entry due to latency drift
        assert result.fill_price != _signal().entry_price

    def test_risk_rejection(self) -> None:
        """Risk manager rejects → not filled."""
        cfg = RiskConfig(min_risk_reward=5.0)  # Very high R:R requirement
        engine = PaperTradingEngine(initial_capital=100_000, risk_config=cfg)
        sig = _signal(entry=100, sl=95, tp=107)  # R:R = 1.4
        result = engine.submit_signal(sig)
        assert not result.filled
        assert result.rejection_reason != ""

    def test_insufficient_cash(self) -> None:
        """Reject when insufficient cash."""
        cfg = RiskConfig(max_risk_per_trade_pct=0.5, max_position_size_pct=0.99)
        engine = PaperTradingEngine(initial_capital=50, risk_config=cfg)  # Very small
        sig = _signal(entry=100, sl=95, tp=115)
        # 50 capital, 50% risk = 25, risk/share = 5, size = 5 shares × 100 = 500 > 50
        result = engine.submit_signal(sig)
        assert not result.filled

    def test_update_prices(self) -> None:
        """Price updates reflect in position P&L."""
        engine = PaperTradingEngine(initial_capital=100_000)
        engine.submit_signal(_signal(symbol="AAPL", entry=100, sl=95, tp=115))
        engine.update_prices({"AAPL": 105.0})
        pos = engine.open_positions[0]
        assert pos.current_price == 105.0
        assert pos.unrealized_pnl > 0

    def test_check_exits_tp_hit(self) -> None:
        """TP hit → position closed with profit."""
        engine = PaperTradingEngine(initial_capital=100_000, slippage_pct=0.0001)
        engine.submit_signal(_signal(entry=100, sl=95, tp=115))
        engine.update_prices({"AAPL": 116.0})  # Above TP
        closed = engine.check_exits()
        assert len(closed) == 1
        assert closed[0].pnl > 0
        assert len(engine.open_positions) == 0

    def test_check_exits_sl_hit(self) -> None:
        """SL hit → position closed with loss."""
        engine = PaperTradingEngine(initial_capital=100_000, slippage_pct=0.0001)
        engine.submit_signal(_signal(entry=100, sl=95, tp=115))
        engine.update_prices({"AAPL": 94.0})  # Below SL
        closed = engine.check_exits()
        assert len(closed) == 1
        assert closed[0].pnl < 0

    def test_trade_history(self) -> None:
        """Closed trades recorded in history."""
        engine = PaperTradingEngine(initial_capital=100_000, slippage_pct=0.0001)
        engine.submit_signal(_signal(entry=100, sl=95, tp=115))
        engine.update_prices({"AAPL": 116.0})
        engine.check_exits()
        assert len(engine.trade_history) == 1
        assert engine.trade_history[0].strategy == "test"

    def test_portfolio_snapshot(self) -> None:
        """Snapshot reflects current portfolio state."""
        engine = PaperTradingEngine(initial_capital=100_000)
        snap = engine.snapshot()
        assert snap.equity == 100_000
        assert snap.open_positions == 0
        assert snap.total_trades == 0

    def test_snapshot_after_trades(self) -> None:
        """Snapshot updates after trades."""
        engine = PaperTradingEngine(initial_capital=100_000, slippage_pct=0.0001)
        engine.submit_signal(_signal(entry=100, sl=95, tp=115))
        engine.update_prices({"AAPL": 116.0})
        engine.check_exits()
        snap = engine.snapshot()
        assert snap.total_trades == 1
        assert snap.winning_trades == 1
        assert snap.total_pnl > 0

    def test_multiple_positions(self) -> None:
        """Multiple simultaneous positions."""
        cfg = RiskConfig(max_open_positions=5)
        engine = PaperTradingEngine(initial_capital=100_000, risk_config=cfg)
        engine.submit_signal(_signal(symbol="AAPL", entry=100, sl=95, tp=115))
        engine.submit_signal(_signal(symbol="GOOG", entry=200, sl=190, tp=230))
        assert len(engine.open_positions) == 2

    def test_equity_calculation(self) -> None:
        """Equity = cash + position values."""
        engine = PaperTradingEngine(initial_capital=100_000)
        initial_equity = engine.equity
        engine.submit_signal(_signal(entry=100, sl=95, tp=115))
        # Equity should still be ~100K (cash decreased, position value added)
        assert abs(engine.equity - initial_equity) < 50  # Small diff from commission

    def test_reset(self) -> None:
        """Reset returns engine to initial state."""
        engine = PaperTradingEngine(initial_capital=100_000)
        engine.submit_signal(_signal())
        engine.reset()
        assert engine.equity == 100_000
        assert len(engine.open_positions) == 0
        assert len(engine.trade_history) == 0

    def test_short_exit_tp(self) -> None:
        """Short TP: price drops below TP → profit."""
        engine = PaperTradingEngine(initial_capital=100_000, slippage_pct=0.0001)
        sig = _signal(direction=Direction.SHORT, entry=100, sl=105, tp=85)
        engine.submit_signal(sig)
        engine.update_prices({"AAPL": 84.0})  # Below TP
        closed = engine.check_exits()
        assert len(closed) == 1
        assert closed[0].pnl > 0

    def test_short_exit_sl(self) -> None:
        """Short SL: price rises above SL → loss."""
        engine = PaperTradingEngine(initial_capital=100_000, slippage_pct=0.0001)
        sig = _signal(direction=Direction.SHORT, entry=100, sl=105, tp=85)
        engine.submit_signal(sig)
        engine.update_prices({"AAPL": 106.0})  # Above SL
        closed = engine.check_exits()
        assert len(closed) == 1
        assert closed[0].pnl < 0
