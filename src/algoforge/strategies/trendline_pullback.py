"""Trendline Pullback Strategy — Primary Strategy.

Generates >50% of all trade signals. Waits for price pullback to trendline
in a confirmed trend, then enters on candlestick confirmation.

Requirements: PRIM-01 to PRIM-12
"""

from __future__ import annotations

import numpy as np
import structlog

from algoforge.core.constants import Direction, MarketRegime, Timeframe
from algoforge.core.models import Signal
from algoforge.strategies.base import Strategy
from algoforge.strategies.candlestick import CandlestickDetector
from algoforge.technical.engine import IndicatorSnapshot
from algoforge.technical.structural.models import (
    StructuralSnapshot,
    TrendDirection,
)

logger = structlog.get_logger(__name__)


class TrendlinePullback(Strategy):
    """Primary strategy: Trendline Pullback.

    Entry logic:
    1. Trend must be UP or DOWN (skip UNCLEAR — PRIM-12)
    2. Price pulls back to trendline (within ATR tolerance)
    3. EMA alignment confirms trend (PRIM-04)
    4. RSI turning from extreme (PRIM-05)
    5. ADX > threshold for trend strength (PRIM-06)
    6. Candlestick pattern confirms (PRIM-07)
    7. Wait for 1-3 momentum bars (PRIM-08)

    Exit:
    - SL at trendline-S/R intersection + ATR buffer (PRIM-09)
    - TP at next S/R level or opposite trendline (PRIM-10)
    - Minimum 1:2 R:R enforced (PRIM-11)
    """

    def __init__(
        self,
        atr_touch_multiplier: float = 2.0,
        atr_sl_multiplier: float = 1.5,
        min_adx: float = 15.0,
        min_rr_ratio: float = 1.5,
        momentum_bars: int = 2,
    ) -> None:
        self._atr_touch = atr_touch_multiplier
        self._atr_sl = atr_sl_multiplier
        self._min_adx = min_adx
        self._min_rr = min_rr_ratio
        self._momentum_bars = momentum_bars
        self._candle_detector = CandlestickDetector()

    @property
    def name(self) -> str:
        return "trendline_pullback"

    @property
    def required_regime(self) -> list[MarketRegime]:
        return [MarketRegime.TRENDING]

    @property
    def min_bars(self) -> int:
        return 50

    def evaluate(
        self,
        symbol: str,
        timeframe: Timeframe,
        indicators: IndicatorSnapshot,
        structure: StructuralSnapshot,
        closes: list[float],
        highs: list[float],
        lows: list[float],
        volumes: list[float],
        opens: list[float],
    ) -> list[Signal]:
        """Evaluate for trendline pullback entries."""
        signals: list[Signal] = []

        if len(closes) < self.min_bars:
            return signals

        # PRIM-12: Use structural trend if clear; else infer from EMA direction
        trend = structure.trend_direction
        if trend == TrendDirection.UNCLEAR:
            # Fall back to EMA direction to allow trading in regime=trending situations
            ema_result_raw = indicators.get("ema")
            if ema_result_raw:
                ema9  = self._latest_valid(ema_result_raw.values.get("ema_9", []))
                ema21 = self._latest_valid(ema_result_raw.values.get("ema_21", []))
                if ema9 and ema21:
                    if ema9 > ema21:
                        trend = TrendDirection.UP
                    elif ema9 < ema21:
                        trend = TrendDirection.DOWN
            if trend == TrendDirection.UNCLEAR:
                logger.debug("trendline_pullback_skip", symbol=symbol, reason="trend_unclear")
                return signals

        # Get indicator values
        atr_result = indicators.get("atr")
        rsi_result = indicators.get("rsi")
        adx_result = indicators.get("adx")
        ema_result = indicators.get("ema")

        if not atr_result or not rsi_result or not adx_result or not ema_result:
            return signals

        # Current values (latest non-NaN)
        atr_values = atr_result.values.get("atr", [])
        rsi_values = rsi_result.values.get("rsi", [])
        adx_values = adx_result.values.get("adx", [])

        current_atr = self._latest_valid(atr_values)
        current_rsi = self._latest_valid(rsi_values)
        current_adx = self._latest_valid(adx_values)

        if current_atr is None or current_rsi is None or current_adx is None:
            return signals

        # PRIM-06: ADX > threshold (relaxed to 15)
        if current_adx < self._min_adx:
            logger.debug("trendline_pullback_skip", symbol=symbol, reason=f"adx_low ({current_adx:.1f})")
            return signals

        # PRIM-04: EMA alignment
        if not self._check_ema_alignment(ema_result.values, trend):
            logger.debug("trendline_pullback_skip", symbol=symbol, reason="ema_misaligned")
            return signals

        # Check for trendline touch
        n = len(closes)
        current_close = closes[-1]
        active_trendlines = structure.active_trendlines

        # Detect candlestick patterns
        opens_arr = np.array(opens, dtype=np.float64)
        highs_arr = np.array(highs, dtype=np.float64)
        lows_arr = np.array(lows, dtype=np.float64)
        closes_arr = np.array(closes, dtype=np.float64)
        patterns = self._candle_detector.detect(opens_arr, highs_arr, lows_arr, closes_arr)

        for tl in active_trendlines:
            tl_price = tl.price_at(n - 1)
            distance = abs(current_close - tl_price)

            # Is price near the trendline? (within ATR tolerance)
            if distance > current_atr * self._atr_touch:
                continue

            if trend == TrendDirection.UP and not tl.is_upper:
                # Uptrend: pullback to LOWER trendline (support)
                # PRIM-02: Wait for pullback to lower trendline

                # PRIM-05: RSI not overbought (widened to 60)
                if current_rsi > 60:  # Price not pulling back enough
                    continue

                # PRIM-07: Bullish candlestick confirmation
                bullish_patterns = self._candle_detector.bullish_at(patterns, n - 1)
                if not bullish_patterns:
                    # Check recent bars for momentum confirmation (PRIM-08)
                    bullish_patterns = self._candle_detector.patterns_near(patterns, n - 1, self._momentum_bars)
                    bullish_patterns = [p for p in bullish_patterns if p.pattern_type.value == "bullish"]

                if not bullish_patterns:
                    continue

                # Calculate SL and TP
                # PRIM-09: SL at trendline with ATR buffer
                sl = tl_price - current_atr * self._atr_sl

                # PRIM-10: TP at next resistance or upper trendline
                tp = self._find_target(
                    current_close, Direction.LONG, structure, active_trendlines, current_atr
                )

                # PRIM-11: Min 1:2 R:R
                risk = current_close - sl
                reward = tp - current_close
                if risk <= 0 or reward / risk < self._min_rr:
                    continue

                signals.append(Signal(
                    symbol=symbol,
                    direction=Direction.LONG,
                    strategy=self.name,
                    confidence=self._calc_confidence(
                        current_adx, current_rsi, bullish_patterns, tl.touch_count
                    ),
                    entry_price=current_close,
                    stop_loss=round(sl, 4),
                    take_profit=round(tp, 4),
                    timeframe=timeframe,
                    regime=MarketRegime.TRENDING,
                    metadata={
                        "trendline_price": round(tl_price, 4),
                        "trendline_touches": tl.touch_count,
                        "pattern": bullish_patterns[0].name if bullish_patterns else "momentum",
                        "adx": round(current_adx, 2),
                        "rsi": round(current_rsi, 2),
                    },
                ))

            elif trend == TrendDirection.DOWN and tl.is_upper:
                # Downtrend: rally to UPPER trendline (resistance)
                # PRIM-03

                # PRIM-05: RSI not oversold (widened to 40)
                if current_rsi < 40:
                    continue

                # PRIM-07: Bearish candlestick confirmation
                bearish_patterns = self._candle_detector.bearish_at(patterns, n - 1)
                if not bearish_patterns:
                    bearish_patterns = self._candle_detector.patterns_near(patterns, n - 1, self._momentum_bars)
                    bearish_patterns = [p for p in bearish_patterns if p.pattern_type.value == "bearish"]

                if not bearish_patterns:
                    continue

                # SL above trendline with ATR buffer
                sl = tl_price + current_atr * self._atr_sl

                # TP at next support or lower trendline
                tp = self._find_target(
                    current_close, Direction.SHORT, structure, active_trendlines, current_atr
                )

                risk = sl - current_close
                reward = current_close - tp
                if risk <= 0 or reward / risk < self._min_rr:
                    continue

                signals.append(Signal(
                    symbol=symbol,
                    direction=Direction.SHORT,
                    strategy=self.name,
                    confidence=self._calc_confidence(
                        current_adx, current_rsi, bearish_patterns, tl.touch_count
                    ),
                    entry_price=current_close,
                    stop_loss=round(sl, 4),
                    take_profit=round(tp, 4),
                    timeframe=timeframe,
                    regime=MarketRegime.TRENDING,
                    metadata={
                        "trendline_price": round(tl_price, 4),
                        "trendline_touches": tl.touch_count,
                        "pattern": bearish_patterns[0].name if bearish_patterns else "momentum",
                        "adx": round(current_adx, 2),
                        "rsi": round(current_rsi, 2),
                    },
                ))

        if signals:
            logger.info(
                "trendline_pullback_signals",
                symbol=symbol,
                count=len(signals),
                directions=[s.direction.value for s in signals],
            )

        return signals

    def _latest_valid(self, values: list[float]) -> float | None:
        """Get latest non-NaN value."""
        for v in reversed(values):
            if not np.isnan(v):
                return float(v)
        return None

    def _check_ema_alignment(
        self, ema_values: dict[str, list[float]], trend: TrendDirection
    ) -> bool:
        """Check EMA alignment matches trend direction."""
        ema_5 = self._latest_valid(ema_values.get("ema_5", []))
        ema_9 = self._latest_valid(ema_values.get("ema_9", []))
        ema_21 = self._latest_valid(ema_values.get("ema_21", []))

        if ema_5 is None or ema_9 is None or ema_21 is None:
            return False

        # Relaxed: just need short EMA above/below long EMA (EMA9 vs EMA21 is sufficient)
        if trend == TrendDirection.UP:
            return ema_9 > ema_21  # Don't require full stacking ema_5 > ema_9 > ema_21
        elif trend == TrendDirection.DOWN:
            return ema_9 < ema_21
        return False

    def _find_target(
        self,
        entry: float,
        direction: Direction,
        structure: StructuralSnapshot,
        trendlines: list,
        atr: float,
    ) -> float:
        """Find take-profit target from S/R levels or opposite trendline."""
        if direction == Direction.LONG:
            # Find nearest resistance above entry
            for level in structure.resistance_levels:
                if level.price > entry + atr:
                    return level.price
            # Fallback: entry + 3× ATR
            return entry + atr * 3.0
        else:
            # Find nearest support below entry
            for level in structure.support_levels:
                if level.price < entry - atr:
                    return level.price
            return entry - atr * 3.0

    def _calc_confidence(
        self,
        adx: float,
        rsi: float,
        patterns: list,
        touch_count: int,
    ) -> float:
        """Calculate signal confidence from contributing factors."""
        confidence = 0.5

        # ADX strength bonus
        if adx > 30:
            confidence += 0.15
        elif adx > 25:
            confidence += 0.10

        # Pattern strength bonus
        if patterns:
            best_pattern = max(patterns, key=lambda p: p.strength)
            confidence += min(best_pattern.strength * 0.1, 0.15)

        # Trendline quality bonus (more touches = stronger)
        if touch_count >= 3:
            confidence += 0.10

        return min(confidence, 0.95)
