"""Dual Timeframe Analysis — Multi-timeframe signal confirmation.

Higher timeframe determines trend direction, lower timeframe
provides precision entries. Reduces false signals significantly.

Requirements: DUAL-01 to DUAL-04
"""

from __future__ import annotations

from typing import Any

import structlog

from algoforge.core.constants import MarketRegime, Timeframe
from algoforge.core.models import Signal
from algoforge.strategies.base import Strategy
from algoforge.technical.engine import IndicatorSnapshot
from algoforge.technical.structural.models import StructuralSnapshot, TrendDirection

logger = structlog.get_logger(__name__)

# Timeframe hierarchy: higher TF at index 0
TIMEFRAME_HIERARCHY: dict[Timeframe, Timeframe] = {
    Timeframe.M1: Timeframe.M5,
    Timeframe.M5: Timeframe.M15,
    Timeframe.M15: Timeframe.H1,
    Timeframe.H1: Timeframe.H4,
    Timeframe.H4: Timeframe.D1,
    Timeframe.D1: Timeframe.W1,
}


class DualTimeframeFilter:
    """Filter signals using higher timeframe confirmation.

    DUAL-01: HTF trend must agree with signal direction
    DUAL-02: HTF regime must be compatible
    DUAL-03: HTF S/R levels used for target refinement
    DUAL-04: Configurable timeframe pairs

    Usage:
        dtf = DualTimeframeFilter()
        approved = dtf.filter(
            signals,
            ltf_structure=ltf_snap,
            htf_structure=htf_snap,
            htf_regime=MarketRegime.TRENDING,
        )
    """

    def __init__(
        self,
        require_trend_alignment: bool = True,
        compatible_regimes: dict[MarketRegime, list[MarketRegime]] | None = None,
    ) -> None:
        self._require_trend = require_trend_alignment
        self._compatible = compatible_regimes or {
            MarketRegime.TRENDING: [MarketRegime.TRENDING],
            MarketRegime.RANGE: [MarketRegime.RANGE, MarketRegime.TRENDING],
            MarketRegime.BREAKOUT: [MarketRegime.TRENDING, MarketRegime.BREAKOUT],
            MarketRegime.REVERSAL: [MarketRegime.RANGE, MarketRegime.REVERSAL],
            MarketRegime.LIQUIDITY_TRAP: [MarketRegime.RANGE, MarketRegime.LIQUIDITY_TRAP],
        }

    def filter(
        self,
        signals: list[Signal],
        htf_structure: StructuralSnapshot,
        htf_regime: MarketRegime,
    ) -> list[Signal]:
        """Filter signals against higher timeframe context."""
        approved: list[Signal] = []

        for sig in signals:
            reasons: list[str] = []

            # DUAL-01: Trend alignment
            if self._require_trend:
                if sig.direction.value == "long" and htf_structure.trend_direction == TrendDirection.DOWN:
                    reasons.append("HTF trend DOWN → reject LONG")
                elif sig.direction.value == "short" and htf_structure.trend_direction == TrendDirection.UP:
                    reasons.append("HTF trend UP → reject SHORT")

            # DUAL-02: Regime compatibility
            if sig.regime:
                compatible = self._compatible.get(sig.regime, [])
                if htf_regime not in compatible:
                    reasons.append(f"HTF regime {htf_regime.value} incompatible with {sig.regime.value}")

            if reasons:
                logger.debug(
                    "dtf_rejected", symbol=sig.symbol, strategy=sig.strategy,
                    reasons=reasons,
                )
            else:
                # DUAL-03: Refine targets with HTF S/R
                refined = self._refine_targets(sig, htf_structure)
                approved.append(refined)

        logger.info(
            "dtf_filter",
            input_count=len(signals),
            approved_count=len(approved),
        )
        return approved

    def _refine_targets(self, signal: Signal, htf_structure: StructuralSnapshot) -> Signal:
        """Refine TP using HTF S/R levels (DUAL-03)."""
        if signal.direction.value == "long":
            # Find nearest HTF resistance for TP
            for level in htf_structure.resistance_levels:
                if level.price > signal.entry_price and level.price < signal.take_profit:
                    return signal.model_copy(update={"take_profit": level.price})
        else:
            # Find nearest HTF support for TP
            for level in htf_structure.support_levels:
                if level.price < signal.entry_price and level.price > signal.take_profit:
                    return signal.model_copy(update={"take_profit": level.price})
        return signal

    @staticmethod
    def get_higher_timeframe(tf: Timeframe) -> Timeframe | None:
        """Get the next higher timeframe."""
        return TIMEFRAME_HIERARCHY.get(tf)
