"""Secondary Strategies — Trending & Range Regimes.

EMA Crossover (Trending): Fast/slow EMA crossover with trend confirmation.
Mean Reversion (Range): Bollinger Band bounce with RSI confirmation.

Requirements: SEC-TREND, SEC-RANGE
"""

from __future__ import annotations

import numpy as np
import structlog

from algoforge.core.constants import Direction, MarketRegime, Timeframe
from algoforge.core.models import Signal
from algoforge.strategies.base import Strategy
from algoforge.strategies.candlestick import CandlestickDetector
from algoforge.technical.engine import IndicatorSnapshot
from algoforge.technical.structural.models import StructuralSnapshot, TrendDirection

logger = structlog.get_logger(__name__)


class EMACrossover(Strategy):
    """EMA crossover strategy for trending regimes.

    Entry: Fast EMA crosses above/below slow EMA with ADX confirmation.
    Exit: Opposite crossover or SL/TP hit.
    """

    def __init__(
        self,
        min_adx: float = 20.0,
        min_rr: float = 2.0,
        atr_sl_mult: float = 2.0,
        atr_tp_mult: float = 4.0,
    ) -> None:
        self._min_adx = min_adx
        self._min_rr = min_rr
        self._atr_sl = atr_sl_mult
        self._atr_tp = atr_tp_mult

    @property
    def name(self) -> str:
        return "ema_crossover"

    @property
    def required_regime(self) -> list[MarketRegime]:
        return [MarketRegime.TRENDING]

    def evaluate(
        self, symbol: str, timeframe: Timeframe,
        indicators: IndicatorSnapshot, structure: StructuralSnapshot,
        closes: list[float], highs: list[float], lows: list[float],
        volumes: list[float], opens: list[float],
    ) -> list[Signal]:
        if len(closes) < self.min_bars:
            return []

        ema = indicators.get("ema")
        adx_r = indicators.get("adx")
        atr_r = indicators.get("atr")
        if not ema or not adx_r or not atr_r:
            return []

        fast = ema.values.get("ema_9", [])
        slow = ema.values.get("ema_21", [])
        adx_vals = adx_r.values.get("adx", [])
        atr_vals = atr_r.values.get("atr", [])

        if len(fast) < 2 or len(slow) < 2:
            return []

        adx = self._lv(adx_vals)
        atr = self._lv(atr_vals)
        if adx is None or atr is None or adx < self._min_adx:
            return []

        # Crossover detection
        signals: list[Signal] = []
        curr_fast, prev_fast = fast[-1], fast[-2]
        curr_slow, prev_slow = slow[-1], slow[-2]

        if prev_fast <= prev_slow and curr_fast > curr_slow:
            # Bullish crossover
            entry = closes[-1]
            sl = entry - atr * self._atr_sl
            tp = entry + atr * self._atr_tp
            if (tp - entry) / (entry - sl) >= self._min_rr:
                signals.append(Signal(
                    symbol=symbol, direction=Direction.LONG, strategy=self.name,
                    confidence=min(0.5 + adx / 100, 0.85), entry_price=entry,
                    stop_loss=round(sl, 4), take_profit=round(tp, 4),
                    timeframe=timeframe, regime=MarketRegime.TRENDING,
                ))

        if prev_fast >= prev_slow and curr_fast < curr_slow:
            # Bearish crossover
            entry = closes[-1]
            sl = entry + atr * self._atr_sl
            tp = entry - atr * self._atr_tp
            if (entry - tp) / (sl - entry) >= self._min_rr:
                signals.append(Signal(
                    symbol=symbol, direction=Direction.SHORT, strategy=self.name,
                    confidence=min(0.5 + adx / 100, 0.85), entry_price=entry,
                    stop_loss=round(sl, 4), take_profit=round(tp, 4),
                    timeframe=timeframe, regime=MarketRegime.TRENDING,
                ))

        return signals

    def _lv(self, vals: list[float]) -> float | None:
        for v in reversed(vals):
            if not np.isnan(v):
                return float(v)
        return None


class MeanReversion(Strategy):
    """Bollinger Band mean reversion for range-bound regimes.

    Entry: Price touches lower BB (buy) or upper BB (sell) with RSI confirmation.
    Exit: Price returns to middle BB or SL/TP hit.
    """

    def __init__(
        self,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        min_rr: float = 2.0,
        atr_sl_mult: float = 1.5,
    ) -> None:
        self._rsi_os = rsi_oversold
        self._rsi_ob = rsi_overbought
        self._min_rr = min_rr
        self._atr_sl = atr_sl_mult

    @property
    def name(self) -> str:
        return "mean_reversion"

    @property
    def required_regime(self) -> list[MarketRegime]:
        return [MarketRegime.RANGE]

    def evaluate(
        self, symbol: str, timeframe: Timeframe,
        indicators: IndicatorSnapshot, structure: StructuralSnapshot,
        closes: list[float], highs: list[float], lows: list[float],
        volumes: list[float], opens: list[float],
    ) -> list[Signal]:
        if len(closes) < self.min_bars:
            return []

        bb = indicators.get("bollinger")
        rsi_r = indicators.get("rsi")
        atr_r = indicators.get("atr")
        if not bb or not rsi_r or not atr_r:
            return []

        upper = bb.values.get("upper", [])
        lower = bb.values.get("lower", [])
        middle = bb.values.get("middle", [])
        rsi_vals = rsi_r.values.get("rsi", [])
        atr_vals = atr_r.values.get("atr", [])

        if not upper or not lower or not middle:
            return []

        rsi = self._lv(rsi_vals)
        atr = self._lv(atr_vals)
        if rsi is None or atr is None:
            return []

        price = closes[-1]
        mid = self._lv(middle)
        signals: list[Signal] = []

        # Price at lower BB + RSI oversold → buy
        lb = self._lv(lower)
        if lb is not None and price <= lb and rsi <= self._rsi_os and mid is not None:
            sl = price - atr * self._atr_sl
            tp = mid  # Target middle band
            risk = price - sl
            reward = tp - price
            if risk > 0 and reward / risk >= self._min_rr:
                signals.append(Signal(
                    symbol=symbol, direction=Direction.LONG, strategy=self.name,
                    confidence=min(0.6, 1.0), entry_price=price,
                    stop_loss=round(sl, 4), take_profit=round(tp, 4),
                    timeframe=timeframe, regime=MarketRegime.RANGE,
                ))

        # Price at upper BB + RSI overbought → sell
        ub = self._lv(upper)
        if ub is not None and price >= ub and rsi >= self._rsi_ob and mid is not None:
            sl = price + atr * self._atr_sl
            tp = mid
            risk = sl - price
            reward = price - tp
            if risk > 0 and reward / risk >= self._min_rr:
                signals.append(Signal(
                    symbol=symbol, direction=Direction.SHORT, strategy=self.name,
                    confidence=min(0.6, 1.0), entry_price=price,
                    stop_loss=round(sl, 4), take_profit=round(tp, 4),
                    timeframe=timeframe, regime=MarketRegime.RANGE,
                ))

        return signals

    def _lv(self, vals: list[float]) -> float | None:
        for v in reversed(vals):
            if not np.isnan(v):
                return float(v)
        return None
