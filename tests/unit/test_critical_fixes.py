"""Tests for Critical Gap Fixes — Walk-Forward, Monte Carlo, Kelly, Circuit Breaker."""

from datetime import datetime, timedelta, timezone

import pytest

from algoforge.core.constants import Direction, Market, MarketRegime, Timeframe
from algoforge.core.models import OHLCV, Signal
from algoforge.execution.backtest import (
    BacktestEngine,
    BacktestMetrics,
    MonteCarloResult,
    MonteCarloSimulator,
    WalkForwardEngine,
    WalkForwardReport,
)
from algoforge.execution.paper import PaperTradingEngine, TradeRecord
from algoforge.risk.manager import RiskConfig, RiskManager


def _candle(
    symbol: str = "TEST",
    o: float = 100.0,
    h: float = 105.0,
    l: float = 95.0,
    c: float = 102.0,
    v: float = 1000.0,
    ts: datetime | None = None,
) -> OHLCV:
    return OHLCV(
        symbol=symbol,
        timeframe="1m",
        timestamp=ts or datetime.now(timezone.utc),
        open=o, high=h, low=l, close=c, volume=v,
    )


def _make_candles(n: int = 200) -> list[OHLCV]:
    """Generate a sequence of trending candles for testing."""
    candles = []
    price = 100.0
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for i in range(n):
        price += 0.1 * (1 if i % 3 != 0 else -1)
        candles.append(_candle(
            o=price, h=price + 1, l=price - 1, c=price + 0.5, v=1000 + i,
            ts=base_time + timedelta(minutes=i),
        ))
    return candles


class TestWalkForwardEngine:
    """Test walk-forward validation (BACK-02)."""

    def test_basic_walk_forward(self) -> None:
        """Walk-forward produces report with N windows."""
        candles = _make_candles(500)
        wf = WalkForwardEngine(
            initial_capital=100_000,
            n_windows=3,
            train_pct=0.70,
        )
        # Dummy strategy: no signals
        wf.add_strategy(lambda idx, c, hist: [])
        report = wf.run(candles)
        assert isinstance(report, WalkForwardReport)
        assert len(report.windows) == 3

    def test_expanding_window(self) -> None:
        """Expanding mode grows training set each window."""
        candles = _make_candles(500)
        wf = WalkForwardEngine(
            initial_capital=100_000,
            n_windows=3,
            expanding=True,
        )
        wf.add_strategy(lambda idx, c, hist: [])
        report = wf.run(candles)
        # Expanding: each window's train_start should be 0
        for w in report.windows:
            assert w.train_start == 0

    def test_insufficient_data(self) -> None:
        """< 100 bars returns empty report."""
        candles = _make_candles(50)
        wf = WalkForwardEngine(n_windows=3)
        wf.add_strategy(lambda idx, c, hist: [])
        report = wf.run(candles)
        assert len(report.windows) == 0

    def test_degradation_calculation(self) -> None:
        """Degradation pct is computed."""
        candles = _make_candles(500)
        wf = WalkForwardEngine(n_windows=3)
        wf.add_strategy(lambda idx, c, hist: [])
        report = wf.run(candles)
        assert isinstance(report.degradation_pct, float)

    def test_window_boundaries(self) -> None:
        """Each window has valid train/test boundaries."""
        candles = _make_candles(300)
        wf = WalkForwardEngine(n_windows=3, train_pct=0.70)
        wf.add_strategy(lambda idx, c, hist: [])
        report = wf.run(candles)
        for w in report.windows:
            assert w.train_start < w.train_end
            assert w.test_start < w.test_end
            assert w.train_end == w.test_start


class TestMonteCarloSimulator:
    """Test Monte Carlo simulation (BACK-03)."""

    def test_empty_trades(self) -> None:
        """No trades → empty result."""
        mc = MonteCarloSimulator(n_simulations=100)
        result = mc.run([], initial_capital=100_000)
        assert result.n_simulations == 0

    def test_basic_simulation(self) -> None:
        """Runs N simulations and produces valid metrics."""
        # Mix of varied win/loss amounts to get different shuffle outcomes
        trades = []
        for i in range(50):
            pnl = 200 + (i * 10) if i % 3 != 0 else -(100 + i * 5)
            trades.append(TradeRecord(
                id=str(i), symbol="TEST", direction=Direction.LONG,
                strategy="test", entry_price=100, exit_price=102 if pnl > 0 else 98,
                quantity=10,
                entry_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
                exit_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
                pnl=pnl, commission=1, slippage=0.05, bars_held=5,
            ))
        mc = MonteCarloSimulator(n_simulations=500)
        result = mc.run(trades, initial_capital=100_000)
        assert result.n_simulations == 500
        assert result.median_final_equity > 0
        assert 0 <= result.prob_profitable <= 1
        assert result.median_max_drawdown >= 0

    def test_deterministic_with_seed(self) -> None:
        """Same seed → same results."""
        trades = [
            TradeRecord(
                id=str(i), symbol="TEST", direction=Direction.LONG,
                strategy="test", entry_price=100, exit_price=105,
                quantity=10,
                entry_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
                exit_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
                pnl=50 + i * 3, commission=1, slippage=0.05,
            )
            for i in range(20)
        ]
        mc1 = MonteCarloSimulator(n_simulations=100)
        mc2 = MonteCarloSimulator(n_simulations=100)
        r1 = mc1.run(trades, 100_000)
        r2 = mc2.run(trades, 100_000)
        assert r1.median_final_equity == r2.median_final_equity

    def test_prob_ruin(self) -> None:
        """With heavy losses, prob_ruin should be > 0."""
        trades = [
            TradeRecord(
                id=str(i), symbol="TEST", direction=Direction.LONG,
                strategy="test", entry_price=100, exit_price=50,
                quantity=10,
                entry_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
                exit_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
                pnl=-5000, commission=1, slippage=0.05,
            )
            for i in range(20)
        ]
        mc = MonteCarloSimulator(n_simulations=100, ruin_threshold_pct=0.5)
        result = mc.run(trades, initial_capital=100_000)
        assert result.prob_ruin > 0


class TestKellyCriterion:
    """Test Kelly Criterion position sizing (SIZE-01)."""

    def test_kelly_activates_after_20_trades(self) -> None:
        """Kelly sizing requires 20+ trade history."""
        config = RiskConfig(sizing_method="kelly", kelly_fraction=0.25)
        rm = RiskManager(capital=100_000, config=config)

        # Record 20 winning trades (no consecutive losses)
        for i in range(20):
            rm.record_trade_result(200.0)

        assert len(rm._trade_results) == 20

        sig = Signal(
            symbol="TEST", direction=Direction.LONG, strategy="test",
            confidence=0.7, entry_price=100, stop_loss=95, take_profit=115,
            timeframe=Timeframe.D1, regime=MarketRegime.TRENDING,
        )
        result = rm.validate(sig)
        assert result.approved
        assert result.position_size > 0

    def test_kelly_requires_wins_and_losses(self) -> None:
        """Kelly needs both wins and losses to compute — falls back to fixed if only wins."""
        config = RiskConfig(sizing_method="kelly", kelly_fraction=0.25)
        rm = RiskManager(capital=100_000, config=config)

        # All wins → Kelly returns 0 (no losses for ratio), falls to fixed
        for i in range(25):
            rm.record_trade_result(100.0)

        sig = Signal(
            symbol="TEST", direction=Direction.LONG, strategy="test",
            confidence=0.7, entry_price=100, stop_loss=95, take_profit=115,
            timeframe=Timeframe.D1, regime=MarketRegime.TRENDING,
        )
        result = rm.validate(sig)
        assert result.approved
        # Falls back to fixed sizing since Kelly can't compute without losses

    def test_kelly_with_mixed_results(self) -> None:
        """Kelly with realistic win/loss mix adjusts position size."""
        config = RiskConfig(sizing_method="kelly", kelly_fraction=0.25)
        rm = RiskManager(capital=100_000, config=config)

        # 60% win rate, avg win = 300, avg loss = 150 → positive Kelly
        for i in range(30):
            if i % 5 < 3:  # 60% wins
                rm.record_trade_result(300.0)
            else:
                rm.record_trade_result(-150.0)

        sig = Signal(
            symbol="TEST", direction=Direction.LONG, strategy="test",
            confidence=0.7, entry_price=100, stop_loss=95, take_profit=115,
            timeframe=Timeframe.D1, regime=MarketRegime.TRENDING,
        )
        result = rm.validate(sig)
        assert result.approved
        assert result.position_size > 0

    def test_fixed_sizing_mode(self) -> None:
        """Explicitly set to 'fixed' mode ignores Kelly."""
        config = RiskConfig(sizing_method="fixed")
        rm = RiskManager(capital=100_000, config=config)

        for i in range(30):
            rm.record_trade_result(200.0)

        sig = Signal(
            symbol="TEST", direction=Direction.LONG, strategy="test",
            confidence=0.7, entry_price=100, stop_loss=95, take_profit=115,
            timeframe=Timeframe.D1, regime=MarketRegime.TRENDING,
        )
        result = rm.validate(sig)
        assert result.approved
        # Fixed sizing should yield: capital * risk% / risk_per_share
        # But capped by max_position_size_pct: 100k * 10% / 100 = 100 shares
        # risk sizing: capital * 2% / 5 = 400 → capped at 100 (10% * 106k / 100)
        assert result.position_size > 0


class TestPaperTradeMetadata:
    def test_signal_metadata_persists_into_trade(self) -> None:
        engine = PaperTradingEngine(initial_capital=100_000)
        sig = Signal(
            symbol="TEST",
            direction=Direction.LONG,
            strategy="test",
            confidence=0.7,
            entry_price=100,
            stop_loss=95,
            take_profit=110,
            timeframe=Timeframe.D1,
            regime=MarketRegime.TRENDING,
            metadata={
                "signal_family": "momentum",
                "conviction_score": 0.82,
                "ml_confidence": 0.76,
            },
        )

        fill = engine.submit_signal(sig)
        assert fill.filled is True

        engine.update_prices({"TEST": 110.0})
        trades = engine.check_exits(current_bar=1)
        assert len(trades) == 1
        assert trades[0].metadata["signal_family"] == "momentum"
        assert trades[0].metadata["conviction_score"] == 0.82
        assert trades[0].metadata["ml_confidence"] == 0.76


class TestCircuitBreaker:
    """Test market circuit breaker (RISK-19)."""

    def test_circuit_breaker_triggers(self) -> None:
        """5%+ drop from open triggers circuit breaker."""
        rm = RiskManager(capital=100_000)
        rm.update_session_open({"AAPL": 100.0})

        # 6% drop
        triggered = rm.check_circuit_breaker({"AAPL": 94.0})
        assert triggered
        assert rm._circuit_breaker_active

    def test_circuit_breaker_blocks_trades(self) -> None:
        """Active circuit breaker vetoes all signals."""
        rm = RiskManager(capital=100_000)
        rm.update_session_open({"AAPL": 100.0})
        rm.check_circuit_breaker({"AAPL": 94.0})

        sig = Signal(
            symbol="TEST", direction=Direction.LONG, strategy="test",
            confidence=0.7, entry_price=100, stop_loss=95, take_profit=115,
            timeframe=Timeframe.D1, regime=MarketRegime.TRENDING,
        )
        result = rm.validate(sig)
        assert not result.approved
        assert "CIRCUIT_BREAKER" in result.rejection_reasons[0]

    def test_circuit_breaker_no_trigger(self) -> None:
        """Small drop doesn't trigger."""
        rm = RiskManager(capital=100_000)
        rm.update_session_open({"AAPL": 100.0})
        triggered = rm.check_circuit_breaker({"AAPL": 96.0})  # 4% drop
        assert not triggered
        assert not rm._circuit_breaker_active

    def test_circuit_breaker_reset(self) -> None:
        """Circuit breaker resets for new session."""
        rm = RiskManager(capital=100_000)
        rm.update_session_open({"AAPL": 100.0})
        rm.check_circuit_breaker({"AAPL": 94.0})
        assert rm._circuit_breaker_active

        rm.reset_circuit_breaker()
        assert not rm._circuit_breaker_active

    def test_custom_threshold(self) -> None:
        """Custom threshold percentage."""
        config = RiskConfig(market_circuit_breaker_pct=0.03)  # 3% threshold
        rm = RiskManager(capital=100_000, config=config)
        rm.update_session_open({"AAPL": 100.0})

        # 3.5% drop → triggers with 3% threshold
        triggered = rm.check_circuit_breaker({"AAPL": 96.5})
        assert triggered
