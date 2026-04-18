"""Secondary Strategies — Breakout, Reversal, Liquidity Trap.

Breakout: S/R level breakout with volume confirmation.
Reversal: Multi-signal reversal at structural levels.
Liquidity Trap: False breakout detection and fade.

Requirements: SEC-BREAK, SEC-REV, SEC-TRAP
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
    SRLevel,
    SRType,
    StructuralSnapshot,
    TrendDirection,
)

logger = structlog.get_logger(__name__)


class BreakoutStrategy(Strategy):
    """S/R breakout strategy for breakout regimes.

    Entry: Price breaks through significant S/R with volume surge.
    Confirmation: Volume > 1.5× average.
    """

    def __init__(
        self,
        volume_mult: float = 1.5,
        atr_buffer: float = 0.5,
        atr_sl_mult: float = 1.5,
        atr_tp_mult: float = 3.0,
        min_rr: float = 2.0,
    ) -> None:
        self._vol_mult = volume_mult
        self._atr_buf = atr_buffer
        self._atr_sl = atr_sl_mult
        self._atr_tp = atr_tp_mult
        self._min_rr = min_rr

    @property
    def name(self) -> str:
        return "breakout"

    @property
    def required_regime(self) -> list[MarketRegime]:
        return [MarketRegime.BREAKOUT]

    def evaluate(
        self, symbol: str, timeframe: Timeframe,
        indicators: IndicatorSnapshot, structure: StructuralSnapshot,
        closes: list[float], highs: list[float], lows: list[float],
        volumes: list[float], opens: list[float],
    ) -> list[Signal]:
        if len(closes) < self.min_bars:
            return []

        atr_r = indicators.get("atr")
        if not atr_r:
            return []
        atr = self._lv(atr_r.values.get("atr", []))
        if atr is None:
            return []

        price = closes[-1]
        prev_price = closes[-2] if len(closes) > 1 else price
        avg_vol = np.mean(volumes[-20:]) if len(volumes) >= 20 else np.mean(volumes)
        curr_vol = volumes[-1]

        signals: list[Signal] = []

        for level in structure.resistance_levels:
            # Breakout above resistance with volume
            if prev_price < level.price and price > level.price + atr * self._atr_buf:
                if curr_vol > avg_vol * self._vol_mult:
                    sl = level.price - atr * self._atr_sl
                    tp = price + atr * self._atr_tp
                    risk = price - sl
                    reward = tp - price
                    if risk > 0 and reward / risk >= self._min_rr:
                        signals.append(Signal(
                            symbol=symbol, direction=Direction.LONG, strategy=self.name,
                            confidence=0.65, entry_price=price,
                            stop_loss=round(sl, 4), take_profit=round(tp, 4),
                            timeframe=timeframe, regime=MarketRegime.BREAKOUT,
                            metadata={"level": level.price, "volume_ratio": curr_vol / avg_vol},
                        ))

        for level in structure.support_levels:
            # Breakdown below support with volume
            if prev_price > level.price and price < level.price - atr * self._atr_buf:
                if curr_vol > avg_vol * self._vol_mult:
                    sl = level.price + atr * self._atr_sl
                    tp = price - atr * self._atr_tp
                    risk = sl - price
                    reward = price - tp
                    if risk > 0 and reward / risk >= self._min_rr:
                        signals.append(Signal(
                            symbol=symbol, direction=Direction.SHORT, strategy=self.name,
                            confidence=0.65, entry_price=price,
                            stop_loss=round(sl, 4), take_profit=round(tp, 4),
                            timeframe=timeframe, regime=MarketRegime.BREAKOUT,
                            metadata={"level": level.price, "volume_ratio": curr_vol / avg_vol},
                        ))

        return signals

    def _lv(self, vals: list[float]) -> float | None:
        for v in reversed(vals):
            if not np.isnan(v):
                return float(v)
        return None


class ReversalStrategy(Strategy):
    """Reversal strategy at structural levels.

    Entry: Price at key S/R + RSI extreme + candlestick confirmation.
    """

    def __init__(
        self,
        rsi_extreme: float = 25.0,
        atr_proximity: float = 1.0,
        min_rr: float = 2.0,
        atr_sl_mult: float = 1.5,
    ) -> None:
        self._rsi_ext = rsi_extreme
        self._atr_prox = atr_proximity
        self._min_rr = min_rr
        self._atr_sl = atr_sl_mult
        self._candle = CandlestickDetector()

    @property
    def name(self) -> str:
        return "reversal"

    @property
    def required_regime(self) -> list[MarketRegime]:
        return [MarketRegime.REVERSAL]

    def evaluate(
        self, symbol: str, timeframe: Timeframe,
        indicators: IndicatorSnapshot, structure: StructuralSnapshot,
        closes: list[float], highs: list[float], lows: list[float],
        volumes: list[float], opens: list[float],
    ) -> list[Signal]:
        if len(closes) < self.min_bars:
            return []

        rsi_r = indicators.get("rsi")
        atr_r = indicators.get("atr")
        if not rsi_r or not atr_r:
            return []

        rsi = self._lv(rsi_r.values.get("rsi", []))
        atr = self._lv(atr_r.values.get("atr", []))
        if rsi is None or atr is None:
            return []

        price = closes[-1]
        n = len(closes)
        patterns = self._candle.detect(
            np.array(opens), np.array(highs), np.array(lows), np.array(closes),
        )

        signals: list[Signal] = []

        # Bullish reversal at support with RSI oversold
        if rsi <= self._rsi_ext:
            for level in structure.support_levels:
                if abs(price - level.price) <= atr * self._atr_prox:
                    bullish = self._candle.bullish_at(patterns, n - 1)
                    if bullish:
                        sl = level.price - atr * self._atr_sl
                        tp = price + atr * 3.0  # Target 3× ATR
                        risk = price - sl
                        reward = tp - price
                        if risk > 0 and reward / risk >= self._min_rr:
                            signals.append(Signal(
                                symbol=symbol, direction=Direction.LONG, strategy=self.name,
                                confidence=0.6, entry_price=price,
                                stop_loss=round(sl, 4), take_profit=round(tp, 4),
                                timeframe=timeframe, regime=MarketRegime.REVERSAL,
                                metadata={"rsi": rsi, "pattern": bullish[0].name},
                            ))
                        break

        # Bearish reversal at resistance with RSI overbought
        if rsi >= 100 - self._rsi_ext:
            for level in structure.resistance_levels:
                if abs(price - level.price) <= atr * self._atr_prox:
                    bearish = self._candle.bearish_at(patterns, n - 1)
                    if bearish:
                        sl = level.price + atr * self._atr_sl
                        tp = price - atr * 3.0
                        risk = sl - price
                        reward = price - tp
                        if risk > 0 and reward / risk >= self._min_rr:
                            signals.append(Signal(
                                symbol=symbol, direction=Direction.SHORT, strategy=self.name,
                                confidence=0.6, entry_price=price,
                                stop_loss=round(sl, 4), take_profit=round(tp, 4),
                                timeframe=timeframe, regime=MarketRegime.REVERSAL,
                                metadata={"rsi": rsi, "pattern": bearish[0].name},
                            ))
                        break

        return signals

    def _lv(self, vals: list[float]) -> float | None:
        for v in reversed(vals):
            if not np.isnan(v):
                return float(v)
        return None


class LiquidityTrapStrategy(Strategy):
    """Liquidity trap / false breakout fade strategy.

    Entry: Detects false breakout (brief S/R breach then reversal back).
    Fades the false move.
    """

    def __init__(
        self,
        atr_breach: float = 0.3,
        atr_sl_mult: float = 2.0,
        min_rr: float = 2.0,
    ) -> None:
        self._atr_breach = atr_breach
        self._atr_sl = atr_sl_mult
        self._min_rr = min_rr

    @property
    def name(self) -> str:
        return "liquidity_trap"

    @property
    def required_regime(self) -> list[MarketRegime]:
        return [MarketRegime.LIQUIDITY_TRAP]

    def evaluate(
        self, symbol: str, timeframe: Timeframe,
        indicators: IndicatorSnapshot, structure: StructuralSnapshot,
        closes: list[float], highs: list[float], lows: list[float],
        volumes: list[float], opens: list[float],
    ) -> list[Signal]:
        if len(closes) < self.min_bars or len(highs) < 3:
            return []

        atr_r = indicators.get("atr")
        if not atr_r:
            return []
        atr = self._lv(atr_r.values.get("atr", []))
        if atr is None:
            return []

        price = closes[-1]
        signals: list[Signal] = []

        # False breakout above resistance: wick above, close below
        for level in structure.resistance_levels:
            # Bar pierced above level but closed below it
            if (
                highs[-1] > level.price + atr * self._atr_breach
                and closes[-1] < level.price
                and closes[-2] < level.price  # Prior bar also below
            ):
                sl = highs[-1] + atr * self._atr_sl
                tp = price - atr * 3.0
                risk = sl - price
                reward = price - tp
                if risk > 0 and reward / risk >= self._min_rr:
                    signals.append(Signal(
                        symbol=symbol, direction=Direction.SHORT, strategy=self.name,
                        confidence=0.55, entry_price=price,
                        stop_loss=round(sl, 4), take_profit=round(tp, 4),
                        timeframe=timeframe, regime=MarketRegime.LIQUIDITY_TRAP,
                        metadata={"trap_type": "bull_trap", "level": level.price},
                    ))
                break

        # False breakdown below support: wick below, close above
        for level in structure.support_levels:
            if (
                lows[-1] < level.price - atr * self._atr_breach
                and closes[-1] > level.price
                and closes[-2] > level.price
            ):
                sl = lows[-1] - atr * self._atr_sl
                tp = price + atr * 3.0
                risk = price - sl
                reward = tp - price
                if risk > 0 and reward / risk >= self._min_rr:
                    signals.append(Signal(
                        symbol=symbol, direction=Direction.LONG, strategy=self.name,
                        confidence=0.55, entry_price=price,
                        stop_loss=round(sl, 4), take_profit=round(tp, 4),
                        timeframe=timeframe, regime=MarketRegime.LIQUIDITY_TRAP,
                        metadata={"trap_type": "bear_trap", "level": level.price},
                    ))
                break

        return signals

    def _lv(self, vals: list[float]) -> float | None:
        for v in reversed(vals):
            if not np.isnan(v):
                return float(v)
        return None
