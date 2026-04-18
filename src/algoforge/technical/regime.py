"""Market Regime Detection.

Classifies each instrument into one of 5 regimes using
multi-factor scoring from indicators and structural analysis.

Requirements: REGM-01 to REGM-04
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import numpy as np
import structlog
from pydantic import BaseModel, Field

from algoforge.core.constants import MarketRegime, Timeframe

logger = structlog.get_logger(__name__)


class RegimeResult(BaseModel):
    """Result of market regime classification.

    Contains probabilities for all 5 regimes, the primary classification,
    confidence level, and contributing factors for transparency.
    """

    symbol: str
    probabilities: dict[str, float] = Field(
        default_factory=dict,
        description="Probability for each regime (sum ≈ 1.0)",
    )
    primary_regime: MarketRegime = Field(default=MarketRegime.RANGE)
    confidence: float = Field(default=0.0, ge=0, le=1.0, description="Gap between top 2 regimes")
    contributing_factors: dict[str, Any] = Field(
        default_factory=dict,
        description="Which indicators contributed to classification",
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_trending(self) -> bool:
        return self.primary_regime == MarketRegime.TRENDING

    @property
    def is_range(self) -> bool:
        return self.primary_regime == MarketRegime.RANGE

    @property
    def is_breakout(self) -> bool:
        return self.primary_regime == MarketRegime.BREAKOUT

    @property
    def is_reversal(self) -> bool:
        return self.primary_regime == MarketRegime.REVERSAL


class RegimeClassifier:
    """Multi-factor market regime classifier.

    Scores each of 5 regimes using weighted indicator signals:
    - ADX for trend strength
    - Bollinger bandwidth + Keltner for squeeze/expansion
    - ATR for volatility state
    - Volume for breakout/reversal confirmation
    - RSI for divergence / reversal signals
    - Structural analysis for liquidity trap detection

    Usage:
        classifier = RegimeClassifier()
        result = classifier.classify(
            symbol="AAPL",
            adx=28.5, plus_di=25.0, minus_di=15.0,
            bb_bandwidth=0.05, bb_pct_b=0.8,
            atr_current=1.5, atr_avg=1.2,
            rsi=65.0,
            volume_ratio=1.8,
            kc_upper=155, kc_lower=145, bb_upper=153, bb_lower=147,
        )
    """

    def __init__(
        self,
        adx_trending_threshold: float = 25.0,
        adx_range_threshold: float = 20.0,
        volume_spike_ratio: float = 2.0,
        atr_expansion_ratio: float = 1.3,
        min_confidence: float = 0.15,
        smoothing_factor: float = 0.3,
    ) -> None:
        self._adx_trending = adx_trending_threshold
        self._adx_range = adx_range_threshold
        self._volume_spike = volume_spike_ratio
        self._atr_expansion = atr_expansion_ratio
        self._min_confidence = min_confidence
        self._smoothing = smoothing_factor
        self._prev_probabilities: dict[str, dict[str, float]] = {}
        self._cache: dict[str, RegimeResult] = {}
        self._total_classifications = 0

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "total_classifications": self._total_classifications,
            "cache_size": len(self._cache),
        }

    def classify(
        self,
        symbol: str,
        adx: float | None = None,
        plus_di: float | None = None,
        minus_di: float | None = None,
        bb_bandwidth: float | None = None,
        bb_pct_b: float | None = None,
        atr_current: float | None = None,
        atr_avg: float | None = None,
        rsi: float | None = None,
        volume_ratio: float | None = None,
        kc_upper: float | None = None,
        kc_lower: float | None = None,
        bb_upper: float | None = None,
        bb_lower: float | None = None,
        price: float | None = None,
        sr_break: bool = False,
        false_breakout: bool = False,
    ) -> RegimeResult:
        """Classify market regime from indicator values.

        All parameters optional — classifier uses what's available.
        More data = more accurate classification.
        """
        scores: dict[str, float] = {
            MarketRegime.TRENDING.value: 0.0,
            MarketRegime.RANGE.value: 0.0,
            MarketRegime.BREAKOUT.value: 0.0,
            MarketRegime.REVERSAL.value: 0.0,
            MarketRegime.LIQUIDITY_TRAP.value: 0.0,
        }
        factors: dict[str, Any] = {}

        # --- ADX scoring (primary trend/range signal) ---
        if adx is not None:
            if adx > self._adx_trending:
                scores[MarketRegime.TRENDING.value] += 3.0
                scores[MarketRegime.RANGE.value] -= 1.0
                factors["adx"] = f"strong_trend ({adx:.1f})"
            elif adx < self._adx_range:
                scores[MarketRegime.RANGE.value] += 3.0
                scores[MarketRegime.TRENDING.value] -= 1.0
                factors["adx"] = f"weak_trend ({adx:.1f})"
            else:
                scores[MarketRegime.TRENDING.value] += 1.0
                scores[MarketRegime.RANGE.value] += 1.0
                factors["adx"] = f"neutral ({adx:.1f})"

            # DI crossover signals trend direction strength
            if plus_di is not None and minus_di is not None:
                di_diff = abs(plus_di - minus_di)
                if di_diff > 10:
                    scores[MarketRegime.TRENDING.value] += 1.0
                    factors["di_spread"] = f"wide ({di_diff:.1f})"

        # --- Bollinger/Keltner squeeze detection ---
        if (
            kc_upper is not None and kc_lower is not None
            and bb_upper is not None and bb_lower is not None
        ):
            bb_inside_kc = bb_upper < kc_upper and bb_lower > kc_lower
            if bb_inside_kc:
                scores[MarketRegime.BREAKOUT.value] += 2.5
                scores[MarketRegime.RANGE.value] += 1.0
                factors["squeeze"] = "active (BB inside KC)"
            else:
                scores[MarketRegime.TRENDING.value] += 0.5
                factors["squeeze"] = "released"

        # --- Bandwidth scoring ---
        if bb_bandwidth is not None:
            if bb_bandwidth < 0.03:
                scores[MarketRegime.BREAKOUT.value] += 1.5
                scores[MarketRegime.RANGE.value] += 1.0
                factors["bandwidth"] = f"tight ({bb_bandwidth:.3f})"
            elif bb_bandwidth > 0.08:
                scores[MarketRegime.TRENDING.value] += 1.0
                factors["bandwidth"] = f"wide ({bb_bandwidth:.3f})"

        # --- ATR expansion/contraction ---
        if atr_current is not None and atr_avg is not None and atr_avg > 0:
            atr_ratio = atr_current / atr_avg
            if atr_ratio > self._atr_expansion:
                scores[MarketRegime.BREAKOUT.value] += 2.0
                scores[MarketRegime.TRENDING.value] += 1.0
                factors["atr"] = f"expanding ({atr_ratio:.2f}x)"
            elif atr_ratio < 0.7:
                scores[MarketRegime.RANGE.value] += 2.0
                factors["atr"] = f"contracting ({atr_ratio:.2f}x)"
            else:
                factors["atr"] = f"normal ({atr_ratio:.2f}x)"

        # --- Volume analysis ---
        if volume_ratio is not None:
            if volume_ratio > self._volume_spike:
                scores[MarketRegime.BREAKOUT.value] += 2.0
                scores[MarketRegime.REVERSAL.value] += 1.0
                factors["volume"] = f"spike ({volume_ratio:.1f}x)"
            elif volume_ratio < 0.5:
                scores[MarketRegime.RANGE.value] += 1.0
                factors["volume"] = f"low ({volume_ratio:.1f}x)"

        # --- RSI divergence/reversal ---
        if rsi is not None:
            if rsi > 75:
                scores[MarketRegime.REVERSAL.value] += 2.0
                factors["rsi"] = f"overbought ({rsi:.1f})"
            elif rsi < 25:
                scores[MarketRegime.REVERSAL.value] += 2.0
                factors["rsi"] = f"oversold ({rsi:.1f})"
            elif 40 < rsi < 60:
                scores[MarketRegime.RANGE.value] += 0.5
                factors["rsi"] = f"neutral ({rsi:.1f})"

        # --- RSI + Volume combo (reversal amplifier) ---
        if rsi is not None and volume_ratio is not None:
            if (rsi > 75 or rsi < 25) and volume_ratio > self._volume_spike:
                scores[MarketRegime.REVERSAL.value] += 2.0
                factors["rsi_vol_combo"] = "extreme_rsi + volume_spike"

        # --- Liquidity trap detection ---
        if false_breakout:
            scores[MarketRegime.LIQUIDITY_TRAP.value] += 4.0
            scores[MarketRegime.BREAKOUT.value] -= 2.0
            factors["liquidity_trap"] = "false_breakout_detected"

        if sr_break and volume_ratio is not None and volume_ratio < 1.0:
            # Break on low volume = potential fake
            scores[MarketRegime.LIQUIDITY_TRAP.value] += 2.0
            factors["liquidity_trap_vol"] = "sr_break_low_volume"

        # --- Normalize scores to probabilities ---
        # Ensure no negative scores
        min_score = min(scores.values())
        if min_score < 0:
            for k in scores:
                scores[k] -= min_score

        total = sum(scores.values())
        if total == 0:
            # Default: equal probability
            n = len(scores)
            probabilities = {k: 1.0 / n for k in scores}
        else:
            probabilities = {k: v / total for k, v in scores.items()}

        # --- Smooth with previous classification ---
        if symbol in self._prev_probabilities:
            prev = self._prev_probabilities[symbol]
            for k in probabilities:
                if k in prev:
                    probabilities[k] = (
                        (1 - self._smoothing) * probabilities[k]
                        + self._smoothing * prev[k]
                    )
            # Re-normalize after smoothing
            total = sum(probabilities.values())
            if total > 0:
                probabilities = {k: v / total for k, v in probabilities.items()}

        self._prev_probabilities[symbol] = probabilities

        # --- Determine primary regime ---
        primary_key = max(probabilities, key=probabilities.get)  # type: ignore
        primary = MarketRegime(primary_key)

        # Confidence = gap between top 2
        sorted_probs = sorted(probabilities.values(), reverse=True)
        confidence = sorted_probs[0] - sorted_probs[1] if len(sorted_probs) > 1 else 1.0

        result = RegimeResult(
            symbol=symbol,
            probabilities=probabilities,
            primary_regime=primary,
            confidence=confidence,
            contributing_factors=factors,
        )

        self._cache[symbol] = result
        self._total_classifications += 1

        logger.info(
            "regime_classified",
            symbol=symbol,
            regime=primary.value,
            confidence=round(confidence, 3),
            probabilities={k: round(v, 3) for k, v in probabilities.items()},
        )

        return result

    def get_cached(self, symbol: str) -> RegimeResult | None:
        """Get cached regime result for a symbol."""
        return self._cache.get(symbol)

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._cache.clear()
        self._prev_probabilities.clear()
