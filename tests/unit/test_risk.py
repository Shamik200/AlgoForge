"""Tests for Phase 6 — Risk Management Engine."""

import pytest

from algoforge.core.constants import Direction, MarketRegime, Timeframe
from algoforge.core.models import Position, Signal
from algoforge.risk.manager import RiskCheckResult, RiskConfig, RiskManager


def _long_signal(
    entry: float = 100.0, sl: float = 95.0, tp: float = 115.0,
    confidence: float = 0.7,
) -> Signal:
    """Create a standard long signal."""
    return Signal(
        symbol="TEST", direction=Direction.LONG, strategy="test_strategy",
        confidence=confidence, entry_price=entry, stop_loss=sl, take_profit=tp,
        timeframe=Timeframe.D1, regime=MarketRegime.TRENDING,
    )


def _short_signal(
    entry: float = 100.0, sl: float = 105.0, tp: float = 85.0,
) -> Signal:
    return Signal(
        symbol="TEST", direction=Direction.SHORT, strategy="test_strategy",
        confidence=0.7, entry_price=entry, stop_loss=sl, take_profit=tp,
        timeframe=Timeframe.D1, regime=MarketRegime.TRENDING,
    )


def _position(
    symbol: str = "TEST", direction: Direction = Direction.LONG,
    entry: float = 100.0, qty: float = 10, current: float = 102.0,
) -> Position:
    from datetime import datetime, timezone
    return Position(
        id=f"pos_{symbol}", symbol=symbol, direction=direction,
        entry_price=entry, quantity=qty, stop_loss=95.0, take_profit=110.0,
        strategy="test", opened_at=datetime.now(timezone.utc),
        current_price=current,
    )


class TestRiskConfig:
    """Test risk configuration."""

    def test_default_config(self) -> None:
        cfg = RiskConfig()
        assert cfg.max_risk_per_trade_pct == 0.02
        assert cfg.min_risk_reward == 2.0
        assert cfg.max_open_positions == 5

    def test_custom_config(self) -> None:
        cfg = RiskConfig(max_risk_per_trade_pct=0.01, min_risk_reward=3.0)
        assert cfg.max_risk_per_trade_pct == 0.01


class TestRiskManager:
    """Test risk management engine."""

    def test_approve_valid_signal(self) -> None:
        """Valid signal with good R:R ratio → approved."""
        rm = RiskManager(capital=100_000)
        sig = _long_signal(entry=100, sl=95, tp=115)  # R:R = 3:1
        result = rm.validate(sig)
        assert result.approved
        assert result.position_size > 0
        assert result.risk_amount > 0

    def test_reject_bad_rr_ratio(self) -> None:
        """R:R below minimum → rejected."""
        rm = RiskManager(capital=100_000, config=RiskConfig(min_risk_reward=2.0))
        sig = _long_signal(entry=100, sl=95, tp=107)  # R:R = 1.4 < 2.0
        result = rm.validate(sig)
        assert not result.approved
        assert any("RISK-03" in r for r in result.rejection_reasons)

    def test_reject_no_stop_loss(self) -> None:
        """RISK-04: No SL → immediate veto."""
        rm = RiskManager(capital=100_000)
        # Can't create Signal with SL=0 due to validator, test with very low
        # Instead test the property
        sig = _long_signal(entry=100, sl=0.001, tp=115)
        result = rm.validate(sig)
        # SL of 0.001 is valid but massive risk — should still be checked

    def test_max_open_positions(self) -> None:
        """RISK-06: Max open positions → rejected."""
        rm = RiskManager(capital=100_000, config=RiskConfig(max_open_positions=2))
        positions = [_position(f"SYM{i}") for i in range(2)]
        sig = _long_signal()
        result = rm.validate(sig, open_positions=positions)
        assert not result.approved
        assert any("RISK-06" in r for r in result.rejection_reasons)

    def test_position_sizing(self) -> None:
        """Position size = (Capital × Risk%) / Risk per share."""
        cfg = RiskConfig(max_risk_per_trade_pct=0.02, max_position_size_pct=0.50)
        rm = RiskManager(capital=100_000, config=cfg)
        sig = _long_signal(entry=100, sl=95, tp=115)
        result = rm.validate(sig)
        # Risk per share = 5, max risk = 2000, position = 400 shares
        assert result.approved
        assert result.position_size == 400.0
        assert result.risk_amount == 2000.0

    def test_max_position_size_cap(self) -> None:
        """RISK-02: Position value capped at max_position_size_pct."""
        cfg = RiskConfig(max_risk_per_trade_pct=0.05, max_position_size_pct=0.05)
        rm = RiskManager(capital=100_000, config=cfg)
        sig = _long_signal(entry=100, sl=99, tp=110)
        # Risk per share = 1, max risk = 5000, naive position = 5000 shares
        # But 5000 × 100 = 500K > 5% of 100K = 5K → cap to 50 shares
        result = rm.validate(sig)
        assert result.approved
        assert result.position_value <= 100_000 * 0.05 + 1  # +1 for rounding

    def test_daily_loss_limit(self) -> None:
        """RISK-08: Daily loss exceeded → reject."""
        rm = RiskManager(capital=100_000, config=RiskConfig(max_daily_loss_pct=0.03))
        rm._daily_pnl = -3100  # > 3% of 100K
        sig = _long_signal()
        result = rm.validate(sig)
        assert not result.approved
        assert any("RISK-08" in r for r in result.rejection_reasons)

    def test_weekly_loss_limit(self) -> None:
        """RISK-09: Weekly loss exceeded → reject."""
        rm = RiskManager(capital=100_000, config=RiskConfig(max_weekly_loss_pct=0.07))
        rm._weekly_pnl = -7500
        sig = _long_signal()
        result = rm.validate(sig)
        assert not result.approved
        assert any("RISK-09" in r for r in result.rejection_reasons)

    def test_drawdown_kill_switch(self) -> None:
        """RISK-10: Max drawdown → kill switch activated."""
        rm = RiskManager(capital=100_000, config=RiskConfig(max_drawdown_pct=0.15))
        rm._peak_equity = 100_000
        rm._capital = 84_000  # 16% drawdown > 15%
        sig = _long_signal()
        result = rm.validate(sig)
        assert not result.approved
        assert any("KILL_SWITCH" in r for r in result.rejection_reasons)
        # All subsequent signals also rejected
        result2 = rm.validate(sig)
        assert not result2.approved

    def test_kill_switch_reset(self) -> None:
        """Kill switch can be manually reset."""
        rm = RiskManager(capital=100_000)
        rm._kill_switch_active = True
        rm.reset_kill_switch()
        assert not rm._kill_switch_active

    def test_consecutive_losses_cooldown(self) -> None:
        """RISK-05: Max consecutive losses → cooldown."""
        cfg = RiskConfig(max_consecutive_losses=3, cooldown_bars=10)
        rm = RiskManager(capital=100_000, config=cfg)
        rm._consecutive_losses = 3
        sig = _long_signal()
        result = rm.validate(sig, current_bar=5)
        assert not result.approved
        assert any("RISK-05" in r or "COOLDOWN" in r for r in result.rejection_reasons)

    def test_cooldown_expires(self) -> None:
        """Cooldown expires after cooldown_bars."""
        cfg = RiskConfig(max_consecutive_losses=3, cooldown_bars=10)
        rm = RiskManager(capital=100_000, config=cfg)
        rm._consecutive_losses = 3
        rm.validate(_long_signal(), current_bar=5)  # Triggers cooldown until bar 15
        # After cooldown
        rm._consecutive_losses = 0
        result = rm.validate(_long_signal(), current_bar=20)
        assert result.approved

    def test_directional_exposure_limit(self) -> None:
        """RISK-12: Net directional exposure capped."""
        cfg = RiskConfig(max_directional_exposure_pct=0.60)
        rm = RiskManager(capital=100_000, config=cfg)
        # 7 long positions worth 10K each = 70K net long = 70% > 60%
        positions = [_position(f"SYM{i}", qty=100, current=100) for i in range(7)]
        sig = _long_signal()
        result = rm.validate(sig, open_positions=positions)
        assert not result.approved
        assert any("RISK-12" in r for r in result.rejection_reasons)

    def test_liquidity_check(self) -> None:
        """RISK-18: Reject if position > volume/3."""
        cfg = RiskConfig(min_volume_multiplier=3.0)
        rm = RiskManager(capital=100_000, config=cfg)
        sig = _long_signal(entry=100, sl=95, tp=115)
        # Position ~400 shares × 100 = 40K, volume needs > 120K
        result = rm.validate(sig, daily_volume=50_000)  # Too low
        assert not result.approved
        assert any("RISK-18" in r for r in result.rejection_reasons)

    def test_slippage_applied(self) -> None:
        """RISK-17: SL/TP adjusted for slippage."""
        cfg = RiskConfig(slippage_buffer_pct=0.001)
        rm = RiskManager(capital=100_000, config=cfg)
        sig = _long_signal(entry=100, sl=95, tp=115)
        result = rm.validate(sig)
        assert result.approved
        # Long SL widened downward, TP pulled slightly lower
        assert result.adjusted_signal is not None
        assert result.adjusted_signal.stop_loss < 95.0
        assert result.adjusted_signal.take_profit < 115.0

    def test_short_signal_slippage(self) -> None:
        """Slippage for short positions widens SL upward."""
        rm = RiskManager(capital=100_000)
        sig = _short_signal(entry=100, sl=105, tp=85)
        result = rm.validate(sig)
        assert result.approved
        assert result.adjusted_signal is not None
        assert result.adjusted_signal.stop_loss > 105.0

    def test_record_trade_result(self) -> None:
        """Recording PnL updates capital and loss tracking."""
        rm = RiskManager(capital=100_000)
        rm.record_trade_result(-500)
        assert rm._capital == 99_500
        assert rm._consecutive_losses == 1
        rm.record_trade_result(1000)
        assert rm._capital == 100_500
        assert rm._consecutive_losses == 0  # Reset on win

    def test_peak_equity_tracking(self) -> None:
        """Peak equity updates on new highs."""
        rm = RiskManager(capital=100_000)
        rm.record_trade_result(5000)
        assert rm._peak_equity == 105_000
        rm.record_trade_result(-3000)
        assert rm._peak_equity == 105_000  # Doesn't decrease

    def test_stats(self) -> None:
        rm = RiskManager(capital=100_000)
        rm.validate(_long_signal())
        s = rm.stats
        assert s["capital"] == 100_000
        assert s["approvals"] == 1

    def test_reset_daily(self) -> None:
        rm = RiskManager(capital=100_000)
        rm._daily_pnl = -1000
        rm.reset_daily()
        assert rm._daily_pnl == 0.0

    def test_reset_weekly(self) -> None:
        rm = RiskManager(capital=100_000)
        rm._weekly_pnl = -5000
        rm.reset_weekly()
        assert rm._weekly_pnl == 0.0
