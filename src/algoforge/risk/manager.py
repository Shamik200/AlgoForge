"""Risk Management Engine — Absolute veto power over all trades.

Implements per-trade and portfolio-level risk controls.
Every trade MUST have a stop loss. Risk manager validates all signals
before they can become orders.

Requirements: RISK-01 to RISK-20, SIZE-01 to SIZE-04
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

import structlog
from pydantic import BaseModel, Field

from algoforge.core.constants import Direction
from algoforge.core.models import Position, Signal
from algoforge.risk.correlation import CorrelationMatrix

logger = structlog.get_logger(__name__)


class RiskConfig(BaseModel):
    """Risk management configuration — all limits configurable."""

    # Per-trade limits
    max_risk_per_trade_pct: float = Field(default=0.02, description="Max 1-2% of capital per trade")
    max_position_size_pct: float = Field(default=0.10, description="Max 5-10% of capital per position")
    min_risk_reward: float = Field(default=2.0, description="Minimum R:R ratio")

    # Position sizing
    sizing_method: str = Field(default="kelly", description="'fixed' or 'kelly'")
    kelly_fraction: float = Field(default=0.25, description="Fractional Kelly (0.25 = quarter-Kelly for safety)")

    # Consecutive loss limits
    max_consecutive_losses: int = Field(default=5, description="Max consecutive losses before cooldown")
    cooldown_bars: int = Field(default=60, description="Cooldown period in bars after max losses")

    # Portfolio limits
    max_open_positions: int = Field(default=5, description="Max 5-10 open positions")
    max_daily_loss_pct: float = Field(default=0.05, description="Max 3-5% daily loss")
    max_weekly_loss_pct: float = Field(default=0.10, description="Max 7-10% weekly loss")
    max_drawdown_pct: float = Field(default=0.20, description="Kill switch: 15-20% from peak")
    max_sector_exposure_pct: float = Field(default=0.25, description="Max 25% per sector")
    max_directional_exposure_pct: float = Field(default=0.60, description="Max 60% net direction")
    max_correlation: float = Field(default=0.70, description="Max correlation between positions")

    # Circuit breaker (RISK-19)
    market_circuit_breaker_pct: float = Field(default=0.05, description="Halt if market drops >5% from open")

    # Execution
    slippage_buffer_pct: float = Field(default=0.001, description="0.1% slippage buffer on SL/TP")
    min_volume_multiplier: float = Field(default=3.0, description="Reject if volume < 3x position size")


class RiskCheckResult(BaseModel):
    """Result of a risk validation check."""

    approved: bool = False
    rejection_reasons: list[str] = Field(default_factory=list)
    adjusted_signal: Signal | None = None
    position_size: float = 0.0
    risk_amount: float = 0.0
    position_value: float = 0.0


class RiskManager:
    """Risk management engine with absolute veto power.

    Every signal passes through validate() before becoming an order.
    The risk manager can:
    - Reject signals that violate any risk rule
    - Adjust position sizes based on Kelly/risk-parity
    - Enforce portfolio-level limits
    - Trigger kill switches on excessive drawdown

    Usage:
        rm = RiskManager(capital=100_000, config=RiskConfig())
        result = rm.validate(signal, open_positions)
        if result.approved:
            # Execute trade with result.position_size
    """

    def __init__(
        self,
        capital: float = 100_000.0,
        config: RiskConfig | None = None,
        sector_map: dict[str, str] | None = None,
    ) -> None:
        self._capital = capital
        self._config = config or RiskConfig()
        self._peak_equity = capital
        self._daily_pnl = 0.0
        self._weekly_pnl = 0.0
        self._consecutive_losses = 0
        self._cooldown_until: int | None = None  # Bar index
        self._current_bar: int = 0
        self._vetoes = 0
        self._approvals = 0
        self._kill_switch_active = False
        self._circuit_breaker_active = False
        self._session_open_prices: dict[str, float] = {}  # RISK-19
        self._trade_results: list[float] = []  # For Kelly sizing
        self._correlation_matrix = CorrelationMatrix()
        self._sector_map: dict[str, str] = sector_map or {}  # symbol -> sector

    @property
    def capital(self) -> float:
        return self._capital

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "capital": self._capital,
            "peak_equity": self._peak_equity,
            "drawdown_pct": self.current_drawdown_pct,
            "daily_pnl": self._daily_pnl,
            "weekly_pnl": self._weekly_pnl,
            "consecutive_losses": self._consecutive_losses,
            "vetoes": self._vetoes,
            "approvals": self._approvals,
            "kill_switch": self._kill_switch_active,
            "circuit_breaker": self._circuit_breaker_active,
            "sizing_method": self._config.sizing_method,
        }

    @property
    def current_drawdown_pct(self) -> float:
        """Current drawdown from peak equity."""
        if self._peak_equity == 0:
            return 0.0
        return (self._peak_equity - self._capital) / self._peak_equity

    def validate(
        self,
        signal: Signal,
        open_positions: list[Position] | None = None,
        daily_volume: float | None = None,
        current_bar: int = 0,
        current_prices: dict[str, float] | None = None,
        conviction: float = 1.0,
    ) -> RiskCheckResult:
        """Validate a signal against all risk rules.

        This is the primary entry point. Returns approved=True only if
        ALL checks pass. Any single failure → veto.
        """
        self._current_bar = current_bar
        positions = open_positions or []
        reasons: list[str] = []

        # RISK-19: Auto-check circuit breaker if prices provided
        if current_prices and not self._circuit_breaker_active:
            self.check_circuit_breaker(current_prices)

        # RISK-19: Circuit breaker check
        if self._circuit_breaker_active:
            reasons.append("CIRCUIT_BREAKER: Market dropped >5% from open — trading halted")
            return self._reject(reasons)

        # RISK-14: Kill switch check (absolute veto)
        if self._kill_switch_active:
            reasons.append("KILL_SWITCH: Trading halted — max drawdown exceeded")
            return self._reject(reasons)

        # Check drawdown kill switch
        if self.current_drawdown_pct >= self._config.max_drawdown_pct:
            self._kill_switch_active = True
            reasons.append(
                f"KILL_SWITCH: Drawdown {self.current_drawdown_pct:.1%} >= "
                f"{self._config.max_drawdown_pct:.1%} limit"
            )
            return self._reject(reasons)

        # Cooldown check
        if self._cooldown_until is not None and current_bar < self._cooldown_until:
            reasons.append(
                f"COOLDOWN: {self._consecutive_losses} consecutive losses — "
                f"cooldown until bar {self._cooldown_until}"
            )
            return self._reject(reasons)
        elif self._cooldown_until is not None and current_bar >= self._cooldown_until:
            self._cooldown_until = None  # Cooldown expired

        # RISK-04: Must have stop loss
        if signal.stop_loss <= 0:
            reasons.append("RISK-04: No stop loss — every trade MUST have SL")
            return self._reject(reasons)

        # RISK-03/PRIM-11: Minimum R:R
        rr = signal.risk_reward_ratio
        if rr < self._config.min_risk_reward:
            reasons.append(
                f"RISK-03: R:R ratio {rr:.2f} < minimum {self._config.min_risk_reward:.2f}"
            )

        # RISK-08: Daily loss limit
        if abs(self._daily_pnl) >= self._capital * self._config.max_daily_loss_pct:
            if self._daily_pnl < 0:
                reasons.append(
                    f"RISK-08: Daily loss {self._daily_pnl:.2f} >= "
                    f"{self._config.max_daily_loss_pct:.1%} limit"
                )

        # RISK-09: Weekly loss limit
        if abs(self._weekly_pnl) >= self._capital * self._config.max_weekly_loss_pct:
            if self._weekly_pnl < 0:
                reasons.append(
                    f"RISK-09: Weekly loss {self._weekly_pnl:.2f} >= "
                    f"{self._config.max_weekly_loss_pct:.1%} limit"
                )

        # RISK-06: Max open positions
        if len(positions) >= self._config.max_open_positions:
            reasons.append(
                f"RISK-06: {len(positions)} open positions >= "
                f"{self._config.max_open_positions} limit"
            )

        # RISK-12: Net directional exposure
        net_long = sum(p.market_value for p in positions if p.direction == Direction.LONG)
        net_short = sum(p.market_value for p in positions if p.direction == Direction.SHORT)
        net_exposure_pct = abs(net_long - net_short) / self._capital if self._capital > 0 else 0
        if net_exposure_pct >= self._config.max_directional_exposure_pct:
            reasons.append(
                f"RISK-12: Net directional exposure {net_exposure_pct:.1%} >= "
                f"{self._config.max_directional_exposure_pct:.1%} limit"
            )

        # RISK-07: Sector exposure limit (was config ghost, now enforced)
        if self._sector_map and positions:
            new_sector = self._sector_map.get(signal.symbol, "unknown")
            sector_value = signal.entry_price  # Approx 1 share
            for p in positions:
                if self._sector_map.get(p.symbol, "unknown") == new_sector:
                    sector_value += p.market_value
            sector_pct = sector_value / self._capital if self._capital > 0 else 0
            if sector_pct >= self._config.max_sector_exposure_pct:
                reasons.append(
                    f"RISK-07: Sector '{new_sector}' exposure {sector_pct:.1%} >= "
                    f"{self._config.max_sector_exposure_pct:.1%} limit"
                )

        # RISK-10: Position correlation check (was config ghost, now enforced)
        if not self._correlation_matrix.is_empty() and positions:
            for p in positions:
                corr = self._correlation_matrix.get_correlation(signal.symbol, p.symbol)
                if abs(corr) >= self._config.max_correlation:
                    reasons.append(
                        f"RISK-10: Correlation({signal.symbol}, {p.symbol}) = {corr:.2f} >= "
                        f"{self._config.max_correlation:.2f} limit"
                    )
                    break  # One violation is enough

        # RISK-18: Liquidity check
        if daily_volume is not None:
            position_size = self._calculate_position_size(signal)
            position_value = position_size * signal.entry_price
            if daily_volume > 0 and position_value > daily_volume / self._config.min_volume_multiplier:
                reasons.append(
                    f"RISK-18: Position value {position_value:.0f} > "
                    f"volume/{self._config.min_volume_multiplier:.0f} ({daily_volume/self._config.min_volume_multiplier:.0f})"
                )

        # RISK-05: Consecutive losses cooldown
        if self._consecutive_losses >= self._config.max_consecutive_losses:
            self._cooldown_until = current_bar + self._config.cooldown_bars
            reasons.append(
                f"RISK-05: {self._consecutive_losses} consecutive losses — "
                f"cooldown triggered for {self._config.cooldown_bars} bars"
            )

        if reasons:
            return self._reject(reasons)

        # --- All checks passed — calculate position size ---
        position_size = self._calculate_position_size(signal, conviction)
        risk_amount = self._calculate_risk_amount(signal, position_size)
        position_value = position_size * signal.entry_price

        # RISK-02: Max position size check
        if position_value > self._capital * self._config.max_position_size_pct:
            position_size = (self._capital * self._config.max_position_size_pct) / signal.entry_price
            position_value = position_size * signal.entry_price
            risk_amount = self._calculate_risk_amount(signal, position_size)

        # Apply slippage buffer to SL
        adjusted_sl = self._apply_slippage(signal.stop_loss, signal.direction)
        adjusted_tp = self._apply_slippage_tp(signal.take_profit, signal.direction)

        adjusted = signal.model_copy(update={
            "stop_loss": adjusted_sl,
            "take_profit": adjusted_tp,
        })

        self._approvals += 1

        logger.info(
            "risk_approved",
            symbol=signal.symbol,
            direction=signal.direction.value,
            position_size=round(position_size, 4),
            risk_amount=round(risk_amount, 2),
            rr_ratio=round(rr, 2),
        )

        return RiskCheckResult(
            approved=True,
            adjusted_signal=adjusted,
            position_size=round(position_size, 4),
            risk_amount=round(risk_amount, 2),
            position_value=round(position_value, 2),
        )

    def _calculate_position_size(self, signal: Signal, conviction: float = 1.0) -> float:
        """Calculate position size using configured method.

        Fixed: Position size = (Capital × Max Risk %) / Risk per share
        Kelly: Uses Kelly Criterion with fractional scaling (SIZE-01)

        Dynamic adjustment: reduces size during drawdown (audit fix).
        Conviction scaling: scales size linearly with signal conviction (audit fix).
        """
        risk_per_share = abs(signal.entry_price - signal.stop_loss)
        if risk_per_share == 0:
            return 0.0

        if self._config.sizing_method == "kelly" and len(self._trade_results) >= 20:
            kelly_size = self._kelly_position_size(signal, risk_per_share)
            if kelly_size > 0:
                base_size = self._apply_dynamic_scaling(kelly_size)
                return base_size * conviction

        # Default: fixed risk-per-trade method
        max_risk_amount = self._capital * self._config.max_risk_per_trade_pct
        position_size = max_risk_amount / risk_per_share
        base_size = self._apply_dynamic_scaling(position_size)
        return base_size * conviction

    def _apply_dynamic_scaling(self, base_size: float) -> float:
        """Reduce position size during drawdown (RISK-15: dynamic adjustment).

        Scale factor = 1.0 at 0% drawdown, 0.5 at half max drawdown, 0.25 at max.
        This gradually reduces risk as losses accumulate.
        """
        dd = self.current_drawdown_pct
        max_dd = self._config.max_drawdown_pct
        if dd <= 0 or max_dd <= 0:
            return base_size
        scale = max(0.25, 1.0 - (dd / max_dd))
        return base_size * scale

    def _kelly_position_size(self, signal: Signal, risk_per_share: float) -> float:
        """Kelly Criterion position sizing (SIZE-01).

        Kelly % = W - [(1 - W) / R]
        Where:
          W = historical win rate
          R = average win / average loss ratio

        We use fractional Kelly (default 25%) for safety to account for
        estimation error and non-normal distribution of returns.
        """
        wins = [r for r in self._trade_results if r > 0]
        losses = [r for r in self._trade_results if r <= 0]

        if not wins or not losses:
            return 0.0

        win_rate = len(wins) / len(self._trade_results)
        avg_win = sum(wins) / len(wins)
        avg_loss = abs(sum(losses) / len(losses))

        if avg_loss == 0:
            return 0.0

        win_loss_ratio = avg_win / avg_loss
        kelly_pct = win_rate - ((1 - win_rate) / win_loss_ratio)

        # Fractional Kelly for safety + floor at 0
        kelly_pct = max(0.0, kelly_pct * self._config.kelly_fraction)

        # Cap at max_risk_per_trade_pct to prevent oversize
        kelly_pct = min(kelly_pct, self._config.max_risk_per_trade_pct)

        max_risk_amount = self._capital * kelly_pct
        position_size = max_risk_amount / risk_per_share

        logger.debug(
            "kelly_sizing",
            win_rate=round(win_rate, 3),
            win_loss_ratio=round(win_loss_ratio, 2),
            raw_kelly=round(kelly_pct / self._config.kelly_fraction, 4) if self._config.kelly_fraction > 0 else 0,
            fractional_kelly=round(kelly_pct, 4),
            position_size=round(position_size, 4),
        )

        return position_size

    def _calculate_risk_amount(self, signal: Signal, position_size: float) -> float:
        """Calculate actual risk amount for this position."""
        risk_per_share = abs(signal.entry_price - signal.stop_loss)
        return position_size * risk_per_share

    def _apply_slippage(self, sl: float, direction: Direction) -> float:
        """Apply slippage buffer to stop loss (widen it slightly)."""
        buffer = sl * self._config.slippage_buffer_pct
        if direction == Direction.LONG:
            return round(sl - buffer, 4)  # Widen SL downward for longs
        else:
            return round(sl + buffer, 4)  # Widen SL upward for shorts

    def _apply_slippage_tp(self, tp: float, direction: Direction) -> float:
        """Apply slippage buffer to take profit (conservative)."""
        buffer = tp * self._config.slippage_buffer_pct
        if direction == Direction.LONG:
            return round(tp - buffer, 4)  # Slightly lower TP for longs
        else:
            return round(tp + buffer, 4)  # Slightly higher TP for shorts

    def _reject(self, reasons: list[str]) -> RiskCheckResult:
        """Reject a signal with reasons."""
        self._vetoes += 1
        logger.warning("risk_vetoed", reasons=reasons)
        return RiskCheckResult(approved=False, rejection_reasons=reasons)

    def record_trade_result(self, pnl: float) -> None:
        """Record trade outcome to update loss tracking and Kelly history."""
        self._capital += pnl
        self._daily_pnl += pnl
        self._weekly_pnl += pnl
        self._trade_results.append(pnl)

        if pnl < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

        if self._capital > self._peak_equity:
            self._peak_equity = self._capital

    def update_session_open(self, prices: dict[str, float]) -> None:
        """Record session open prices for circuit breaker (RISK-19).

        Call this once at market open with the opening prices.
        """
        self._session_open_prices.update(prices)
        self._circuit_breaker_active = False  # Reset for new session

    def check_circuit_breaker(self, current_prices: dict[str, float]) -> bool:
        """Check if any tracked symbol has dropped >5% from session open (RISK-19).

        Returns True if circuit breaker triggers.
        """
        if not self._session_open_prices:
            return False

        threshold = self._config.market_circuit_breaker_pct

        for symbol, current in current_prices.items():
            open_price = self._session_open_prices.get(symbol)
            if open_price and open_price > 0:
                drop = (open_price - current) / open_price
                if drop >= threshold:
                    self._circuit_breaker_active = True
                    logger.error(
                        "circuit_breaker_triggered",
                        symbol=symbol,
                        open_price=open_price,
                        current_price=current,
                        drop_pct=round(drop * 100, 2),
                        threshold_pct=round(threshold * 100, 1),
                    )
                    return True

        return False

    def update_correlation_matrix(self, correlation_matrix: CorrelationMatrix) -> None:
        """Update the cached correlation matrix (call daily)."""
        self._correlation_matrix = correlation_matrix

    def update_sector_map(self, sector_map: dict[str, str]) -> None:
        """Update symbol-to-sector mapping."""
        self._sector_map.update(sector_map)

    def reset_daily(self) -> None:
        """Reset daily PnL counter (call at market open)."""
        self._daily_pnl = 0.0

    def reset_weekly(self) -> None:
        """Reset weekly PnL counter."""
        self._weekly_pnl = 0.0
        self._daily_pnl = 0.0

    def reset_kill_switch(self) -> None:
        """Manual kill switch reset (requires human confirmation)."""
        self._kill_switch_active = False
        logger.warning("kill_switch_reset", capital=self._capital)

    def reset_circuit_breaker(self) -> None:
        """Reset circuit breaker for new session."""
        self._circuit_breaker_active = False
        self._session_open_prices.clear()
