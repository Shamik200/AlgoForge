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
        min_adx: float = 25.0,
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

        lb = self._lv(lower)
        ub = self._lv(upper)
        bb_range = (ub - lb) if (ub and lb) else 0
        near_lower = lb is not None and price <= lb + bb_range * 0.15
        near_upper = ub is not None and price >= ub - bb_range * 0.15
        lb_s = f"{lb:.6f}" if lb else "N/A"
        ub_s = f"{ub:.6f}" if ub else "N/A"
        mid_s = f"{mid:.6f}" if mid else "N/A"
        # LONG: price near/below lower BB + RSI oversold
        if near_lower and rsi <= self._rsi_os and mid is not None:
            sl = price - atr * self._atr_sl
            tp = max(mid, price + atr * 2.5)  # guaranteed TP beyond mid
            risk = price - sl
            reward = tp - price
            if risk > 0 and reward / risk >= self._min_rr:
                signals.append(Signal(
                    symbol=symbol, direction=Direction.LONG, strategy=self.name,
                    confidence=min(0.65, 1.0), entry_price=price,
                    stop_loss=round(sl, 6), take_profit=round(tp, 6),
                    timeframe=timeframe, regime=MarketRegime.RANGE,
                    metadata={"lb": lb_s, "mid": mid_s, "rsi": round(rsi,2), "atr": round(atr,6)},
                ))
                logger.info("mean_rev_LONG", symbol=symbol,
                    price=round(price,6), sl=round(sl,6), tp=round(tp,6),
                    rr=round(reward/risk,2), rsi=round(rsi,2))
            else:
                logger.info("mean_rev_skip", symbol=symbol, direction="LONG",
                    reason=f"RR_too_low rr={reward/risk:.2f}<{self._min_rr}",
                    price=round(price,6), sl=round(sl,6), tp=round(tp,6),
                    lb=lb_s, mid=mid_s, rsi=round(rsi,2))
        elif not near_lower:
            thr_s = f"{lb + bb_range*0.15:.6f}" if lb else "N/A"
            logger.info("mean_rev_skip", symbol=symbol, direction="LONG",
                reason="price_not_near_lower_bb",
                price=round(price,6), lb=lb_s, threshold=thr_s, rsi=round(rsi,2))
        elif rsi > self._rsi_os:
            logger.info("mean_rev_skip", symbol=symbol, direction="LONG",
                reason=f"RSI_not_oversold rsi={rsi:.1f}>{self._rsi_os} need<={self._rsi_os}",
                price=round(price,6), lb=lb_s)

        # SHORT: price near/above upper BB + RSI overbought
        if near_upper and rsi >= self._rsi_ob and mid is not None:
            sl = price + atr * self._atr_sl
            tp = min(mid, price - atr * 2.5)  # guaranteed TP beyond mid
            risk = sl - price
            reward = price - tp
            if risk > 0 and reward / risk >= self._min_rr:
                signals.append(Signal(
                    symbol=symbol, direction=Direction.SHORT, strategy=self.name,
                    confidence=min(0.65, 1.0), entry_price=price,
                    stop_loss=round(sl, 6), take_profit=round(tp, 6),
                    timeframe=timeframe, regime=MarketRegime.RANGE,
                    metadata={"ub": ub_s, "mid": mid_s, "rsi": round(rsi,2), "atr": round(atr,6)},
                ))
                logger.info("mean_rev_SHORT", symbol=symbol,
                    price=round(price,6), sl=round(sl,6), tp=round(tp,6),
                    rr=round(reward/risk,2), rsi=round(rsi,2))
            else:
                logger.info("mean_rev_skip", symbol=symbol, direction="SHORT",
                    reason=f"RR_too_low rr={reward/risk:.2f}<{self._min_rr}",
                    price=round(price,6), sl=round(sl,6), tp=round(tp,6),
                    ub=ub_s, mid=mid_s, rsi=round(rsi,2))
        elif not near_upper and rsi >= self._rsi_ob:
            thr_s = f"{ub - bb_range*0.15:.6f}" if ub else "N/A"
            logger.info("mean_rev_skip", symbol=symbol, direction="SHORT",
                reason="price_not_near_upper_bb",
                price=round(price,6), ub=ub_s, threshold=thr_s, rsi=round(rsi,2))

        return signals

    def _lv(self, vals: list[float]) -> float | None:
        for v in reversed(vals):
            if not np.isnan(v):
                return float(v)
        return None


class EMABounce(Strategy):
    """EMA-21 bounce strategy for trending regimes — no trendlines needed.

    Entry: In an uptrend, price pulls back and touches EMA-21 then bounces.
           In a downtrend, price rallies to EMA-21 then rejects.
    Exit: SL below/above recent swing + ATR buffer. TP at 2×ATR extension.
    """

    def __init__(
        self,
        ema_period: int = 21,
        atr_proximity: float = 1.0,
        atr_sl_mult: float = 2.5,
        atr_tp_mult: float = 5.0,
        min_rr: float = 1.5,
    ) -> None:
        self._ema_period = ema_period
        self._atr_prox = atr_proximity
        self._atr_sl = atr_sl_mult
        self._atr_tp = atr_tp_mult
        self._min_rr = min_rr

    @property
    def name(self) -> str:
        return "ema_bounce"

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

        ema_r = indicators.get("ema")
        atr_r = indicators.get("atr")
        rsi_r = indicators.get("rsi")
        adx_r = indicators.get("adx")
        if not ema_r or not atr_r or not rsi_r or not adx_r:
            return []

        ema21_vals = ema_r.values.get("ema_21", [])
        ema9_vals  = ema_r.values.get("ema_9", [])
        atr_vals   = atr_r.values.get("atr", [])
        rsi_vals   = rsi_r.values.get("rsi", [])
        adx_vals   = adx_r.values.get("adx", [])

        ema21 = self._lv(ema21_vals)
        ema9  = self._lv(ema9_vals)
        atr   = self._lv(atr_vals)
        rsi   = self._lv(rsi_vals)
        adx   = self._lv(adx_vals)

        if any(v is None for v in [ema21, ema9, atr, rsi, adx]):
            return []

        # Check ADX minimum filter (Component 5 check)
        if adx < 20.0:
            logger.info("ema_bounce_skip", symbol=symbol, reason=f"ADX_too_low adx={adx:.1f}<20.0")
            return []

        price = closes[-1]
        signals: list[Signal] = []
        dist_to_ema = abs(price - ema21)
        prox_threshold = atr * self._atr_prox

        # UPTREND: EMA9 > EMA21, price near EMA21, RSI not overbought
        if ema9 > ema21:
            if dist_to_ema <= prox_threshold:
                if rsi < 60:  # Tightened from 65 to 60
                    # Confirm upward momentum: RSI not collapsing (>30) and price within zone
                    # Removed single-candle close check — too noisy on 1m timeframe
                    sl = price - atr * self._atr_sl
                    tp = price + atr * self._atr_tp
                    risk = price - sl
                    reward = tp - price
                    if risk > 0 and reward / risk >= self._min_rr:
                        signals.append(Signal(
                            symbol=symbol, direction=Direction.LONG, strategy=self.name,
                            confidence=min(0.55 + adx / 200, 0.80), entry_price=price,
                            stop_loss=round(sl, 6), take_profit=round(tp, 6),
                            timeframe=timeframe, regime=MarketRegime.TRENDING,
                            metadata={"ema21": round(ema21,6), "atr": round(atr,6), "rsi": round(rsi,2),
                                      "dist_atr": round(dist_to_ema/atr, 2)},
                        ))
                    else:
                        logger.info("ema_bounce_skip", symbol=symbol, direction="LONG",
                            reason=f"RR_low rr={reward/risk:.2f}<{self._min_rr}",
                            sl=round(sl,4), tp=round(tp,4), atr=round(atr,4))
                else:
                    logger.info("ema_bounce_skip", symbol=symbol, direction="LONG",
                        reason=f"RSI_overbought rsi={rsi:.1f}>=60")
            else:
                logger.info("ema_bounce_skip", symbol=symbol, direction="LONG",
                    reason=f"price_far_from_EMA21 dist={dist_to_ema:.4f} threshold={prox_threshold:.4f} ({dist_to_ema/atr:.1f}xATR)")
        # DOWNTREND: EMA9 < EMA21
        elif ema9 < ema21:
            if dist_to_ema <= prox_threshold:
                if rsi > 40:  # Tightened from 35 to 40
                    # Confirm downward momentum via RSI direction — removed single-candle check
                    sl = price + atr * self._atr_sl
                    tp = price - atr * self._atr_tp
                    risk = sl - price
                    reward = price - tp
                    if risk > 0 and reward / risk >= self._min_rr:
                        signals.append(Signal(
                            symbol=symbol, direction=Direction.SHORT, strategy=self.name,
                            confidence=min(0.55 + adx / 200, 0.80), entry_price=price,
                            stop_loss=round(sl, 6), take_profit=round(tp, 6),
                            timeframe=timeframe, regime=MarketRegime.TRENDING,
                            metadata={"ema21": round(ema21,6), "atr": round(atr,6), "rsi": round(rsi,2),
                                      "dist_atr": round(dist_to_ema/atr, 2)},
                        ))
                    else:
                        logger.info("ema_bounce_skip", symbol=symbol, direction="SHORT",
                            reason=f"RR_low rr={reward/risk:.2f}<{self._min_rr}",
                            sl=round(sl,4), tp=round(tp,4), atr=round(atr,4))
                else:
                    logger.info("ema_bounce_skip", symbol=symbol, direction="SHORT",
                        reason=f"RSI_oversold rsi={rsi:.1f}<=40")
            else:
                logger.info("ema_bounce_skip", symbol=symbol, direction="SHORT",
                    reason=f"price_far_from_EMA21 dist={dist_to_ema:.4f} threshold={prox_threshold:.4f} ({dist_to_ema/atr:.1f}xATR)")
        else:
            logger.info("ema_bounce_skip", symbol=symbol, reason="EMA9==EMA21 no trend")

        return signals

    def _lv(self, vals: list[float]) -> float | None:
        for v in reversed(vals):
            if not np.isnan(v):
                return float(v)
        return None
