"""Volatility Breakout Signal class combining squeezes and donchian channels."""

import numpy as np
import structlog

from algoforge.core.models import OHLCVSeries
from algoforge.regime.models import RegimeProbabilities, RegimeState
from algoforge.signals.breakout.donchian import (
    calc_donchian_channels,
    detect_breakout,
    detect_failed_breakout,
)
from algoforge.signals.breakout.volatility import (
    calc_keltner_channels,
    calc_squeeze_duration,
    detect_squeeze,
)
from algoforge.signals.models import SignalDirection, SignalResult
from algoforge.technical.indicator_base import atr_calc, sma_calc
from algoforge.technical.structural.models import StructuralSnapshot, Trendline

logger = structlog.get_logger(__name__)


class VolatilityBreakoutSignal:
    """Generates signals based on volatility expansion.
    
    Identifies TTM Squeezes followed by volume-confirmed Donchian breakouts.
    Also handles stateless failed breakout reversal patterns.
    """

    def __init__(self, period: int = 20, min_squeeze_duration: int = 3) -> None:
        """Initialize Volatility Breakout Signal.
        
        Args:
            period: Lookback period for Donchian, Bollinger, and Keltner.
            min_squeeze_duration: Minimum bars of squeeze required for max conviction.
        """
        self.period = period
        self.min_squeeze_duration = min_squeeze_duration

    def evaluate(
        self,
        series: OHLCVSeries,
        bb_upper: np.ndarray,
        bb_lower: np.ndarray,
        regime_probs: RegimeProbabilities | None = None,
        structural_snapshot: StructuralSnapshot | None = None
    ) -> SignalResult:
        """Evaluate volatility breakout.
        
        Args:
            series: OHLCV data.
            bb_upper: Pre-calculated Bollinger Upper Band array.
            bb_lower: Pre-calculated Bollinger Lower Band array.
            regime_probs: Optional regime predictions for activation guard.
            structural_snapshot: Optional structural snapshot containing trendlines.
            
        Returns:
            SignalResult bounded [-1.0, 1.0].
        """
        metadata: dict[str, str | float | bool] = {}
        
        # 1. Regime Guard (Must be trending up or down > 50%)
        if regime_probs is not None:
            trend_prob = regime_probs.trend_up + regime_probs.trend_down
            if trend_prob < 0.50:
                return SignalResult(
                    family_name="breakout",
                    score=0.0,
                    direction=SignalDirection.NEUTRAL,
                    is_valid=False,
                    metadata={"filter_failed": "regime_guard", "trend_prob": trend_prob}
                )
                
        n = len(series.candles)
        if n <= self.period:
            return SignalResult(
                family_name="breakout", score=0.0, direction=SignalDirection.NEUTRAL,
                is_valid=False, metadata={"filter_failed": "insufficient_data"}
            )
            
        highs = np.array(series.highs, dtype=np.float64)
        lows = np.array(series.lows, dtype=np.float64)
        closes = np.array(series.closes, dtype=np.float64)
        volumes = np.array(series.volumes, dtype=np.float64)
        
        # Calculate ATR and Volume SMA
        atr_arr = atr_calc(highs, lows, closes, 14)
        atr_val = atr_arr[-1]
        vol_sma = sma_calc(volumes, self.period)
        latest_vol_ratio = volumes[-1] / vol_sma[-1] if vol_sma[-1] > 0 else 0.0
        
        # Calculate Donchian
        dh, dl = calc_donchian_channels(highs, lows, self.period)
        
        # 2. Check for Reversal Patterns (Highest priority)
        failed_bull, failed_bear = detect_failed_breakout(closes, dh, dl, atr_val)
        if failed_bull == 1:
            # Reversal: Bearish conviction
            return SignalResult(
                family_name="breakout", score=-1.0, direction=SignalDirection.SHORT,
                is_valid=True, metadata={"pattern": "failed_bull_breakout_reversal"}
            )
        if failed_bear == 1:
            # Reversal: Bullish conviction
            return SignalResult(
                family_name="breakout", score=1.0, direction=SignalDirection.LONG,
                is_valid=True, metadata={"pattern": "failed_bear_breakout_reversal"}
            )
        
        # 2.5. Check for Trendline Breaks (High priority)
        if structural_snapshot is not None and structural_snapshot.trendlines:
            trendline_signal = self._detect_trendline_break(
                closes=closes,
                highs=highs,
                lows=lows,
                volumes=volumes,
                atr_val=atr_val,
                trendlines=structural_snapshot.trendlines,
                metadata=metadata
            )
            if trendline_signal is not None:
                return trendline_signal
            
        # Calculate Squeeze Mechanics
        kc_u, kc_c, kc_l = calc_keltner_channels(highs, lows, closes, ema_period=self.period)
        squeeze_active = detect_squeeze(bb_upper, bb_lower, kc_u, kc_l)
        durations = calc_squeeze_duration(squeeze_active)
        latest_duration = durations[-1]
        
        # Note: We check if squeeze WAS active right before the breakout.
        # A true breakout releases the squeeze, so `squeeze_active[-1]` might be False,
        # but `squeeze_active[-2]` would be True.
        squeeze_conviction = min(1.0, max(durations[-2], latest_duration) / self.min_squeeze_duration)
        metadata["squeeze_duration"] = max(durations[-2], latest_duration)
        
        # 3. Check for Standard Breakouts
        bull_break, bear_break = detect_breakout(closes, dh, dl)
        
        # Guard: Volume Confirmation
        has_volume = latest_vol_ratio > 2.0
        metadata["vol_ratio"] = latest_vol_ratio
        
        if not has_volume:
            return SignalResult(
                family_name="breakout", score=0.0, direction=SignalDirection.NEUTRAL,
                is_valid=False, metadata={"filter_failed": "insufficient_volume", **metadata}
            )
            
        score = 0.0
        direction = SignalDirection.NEUTRAL
        
        # Calculate score (base 0.5 + 0.5 * squeeze_conviction)
        base_conviction = 0.5 + (0.5 * squeeze_conviction)
        
        if bull_break == 1:
            score = base_conviction
            direction = SignalDirection.LONG
        elif bear_break == 1:
            score = -base_conviction
            direction = SignalDirection.SHORT
            
        return SignalResult(
            family_name="breakout",
            score=score,
            direction=direction,
            is_valid=score != 0.0,
            metadata=metadata
        )

    def _detect_trendline_break(
        self,
        closes: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        volumes: np.ndarray,
        atr_val: float,
        trendlines: list[Trendline],
        metadata: dict[str, str | float | bool]
    ) -> SignalResult | None:
        """Detect trendline breaks with volume confirmation.
        
        Args:
            closes: Close prices array
            highs: High prices array
            lows: Low prices array
            volumes: Volume array
            atr_val: Current ATR value
            trendlines: List of active trendlines from structural snapshot
            metadata: Metadata dictionary to update
            
        Returns:
            SignalResult if a trendline break is detected, None otherwise
        """
        n = len(closes)
        current_close = closes[-1]
        current_high = highs[-1]
        current_low = lows[-1]
        current_volume = volumes[-1]
        
        # Calculate volume confirmation
        vol_sma = sma_calc(volumes, self.period)
        latest_vol_ratio = current_volume / vol_sma[-1] if vol_sma[-1] > 0 else 0.0
        
        # Volume must be at least 1.5x average for trendline break confirmation
        has_volume_confirmation = latest_vol_ratio > 1.5
        
        if not has_volume_confirmation:
            return None
        
        # Check each active trendline for breaks
        for trendline in trendlines:
            # Skip broken or invalidated trendlines
            if trendline.broken or trendline.invalidated:
                continue
            
            # Calculate trendline price at current index
            current_index = n - 1
            line_price = trendline.price_at(current_index)
            
            # Define break threshold (price must close beyond line + tolerance)
            break_threshold = atr_val * 0.3  # 0.3 ATR beyond the line
            # Define approach threshold for structural family signals (within 0.5 ATR)
            approach_threshold = atr_val * 0.5
            
            # Check for bullish break (breaking above resistance)
            if trendline.is_upper:  # Resistance line
                # Accept a break if the high exceeds the trendline and the close
                # is not significantly below the line (tolerance = 1 ATR * 0.3)
                if current_high > line_price and current_close >= (line_price - break_threshold):
                        logger.info(
                            "trendline_break_detected",
                            direction="bullish",
                            trendline_id=trendline.id,
                            line_price=line_price,
                            close_price=current_close,
                            volume_ratio=latest_vol_ratio,
                        )
                        
                        metadata["pattern"] = "trendline_breakout_bullish"
                        metadata["trendline_id"] = trendline.id
                        metadata["trendline_strength"] = trendline.strength
                        metadata["vol_ratio"] = latest_vol_ratio
                        metadata["line_price"] = line_price
                        
                        # Calculate conviction based on trendline strength and volume
                        # Base conviction 0.7, boosted by trendline strength (normalized)
                        strength_boost = min(0.3, trendline.strength / 10.0)
                        conviction = 0.7 + strength_boost
                        
                        return SignalResult(
                            family_name="breakout",
                            score=conviction,
                            direction=SignalDirection.LONG,
                            is_valid=True,
                            metadata=metadata
                        )
                # If price is approaching the resistance (within approach_threshold)
                if abs(current_close - line_price) <= approach_threshold:
                    # Generate a lower-conviction structural signal (pullback/approach)
                    approach_score = min(0.5, 0.25 + min(0.25, trendline.strength / 10.0))
                    metadata_approach = metadata.copy()
                    metadata_approach["approach"] = True
                    metadata_approach["line_price"] = line_price
                    return SignalResult(
                        family_name="structural",
                        score=approach_score,
                        direction=SignalDirection.LONG,
                        is_valid=True,
                        metadata=metadata_approach
                    )
            
            # Check for bearish break (breaking below support)
            else:  # Support line
                # Accept a break if the low drops below the trendline and the close
                # is not significantly above the line (tolerance = 1 ATR * 0.3)
                if current_low < line_price and current_close <= (line_price + break_threshold):
                        logger.info(
                            "trendline_break_detected",
                            direction="bearish",
                            trendline_id=trendline.id,
                            line_price=line_price,
                            close_price=current_close,
                            volume_ratio=latest_vol_ratio,
                        )
                        
                        metadata["pattern"] = "trendline_breakout_bearish"
                        metadata["trendline_id"] = trendline.id
                        metadata["trendline_strength"] = trendline.strength
                        metadata["vol_ratio"] = latest_vol_ratio
                        metadata["line_price"] = line_price
                        
                        # Calculate conviction based on trendline strength and volume
                        strength_boost = min(0.3, trendline.strength / 10.0)
                        conviction = 0.7 + strength_boost
                        
                        return SignalResult(
                            family_name="breakout",
                            score=-conviction,
                            direction=SignalDirection.SHORT,
                            is_valid=True,
                            metadata=metadata
                        )
                # If price is approaching the support (within approach_threshold)
                if abs(current_close - line_price) <= approach_threshold:
                    approach_score = -min(0.5, 0.25 + min(0.25, trendline.strength / 10.0))
                    metadata_approach = metadata.copy()
                    metadata_approach["approach"] = True
                    metadata_approach["line_price"] = line_price
                    return SignalResult(
                        family_name="structural",
                        score=approach_score,
                        direction=SignalDirection.SHORT,
                        is_valid=True,
                        metadata=metadata_approach
                    )
        
        # No trendline breaks detected
        return None
