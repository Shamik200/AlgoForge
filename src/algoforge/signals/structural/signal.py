"""Structural Confluence Signal class combining Phase 4 snapshots with micro-structure rejection."""

import numpy as np

from algoforge.core.models import OHLCVSeries
from algoforge.regime.models import RegimeProbabilities
from algoforge.signals.models import SignalDirection, SignalResult
from algoforge.signals.structural.microstructure import detect_rejection
from algoforge.signals.structural.proximity import check_htf_overlap, find_tested_levels
from algoforge.structural.pattern_recognizer import PatternRecognizer, PatternDirection
from algoforge.technical.indicator_base import atr_calc, sma_calc
from algoforge.technical.structural.engine import StructuralSnapshot


class StructuralConfluenceSignal:
    """Generates signals based on structural support/resistance rejections.
    
    Requires a Phase 4 `StructuralSnapshot` to determine the key levels.
    """

    def __init__(self, atr_period: int = 14, vol_sma_period: int = 20) -> None:
        """Initialize Structural Confluence Signal.
        
        Args:
            atr_period: Period for ATR calculation used in proximity bands.
            vol_sma_period: Period for Volume SMA used in climax detection.
        """
        self.atr_period = atr_period
        self.vol_sma_period = vol_sma_period

    def evaluate(
        self,
        series: OHLCVSeries,
        snapshot: StructuralSnapshot,
        htf_snapshots: list[StructuralSnapshot] | None = None,
        regime_probs: RegimeProbabilities | None = None,
        indicators: dict | None = None
    ) -> SignalResult:
        """Evaluate structural confluence and microstructure rejection.
        
        Args:
            series: OHLCV data.
            snapshot: Phase 4 StructuralSnapshot containing SRLevels for the current timeframe.
            htf_snapshots: Optional list of HTF snapshots for MTF overlap boost.
            regime_probs: Optional regime predictions for regime-aware multipliers.
            
        Returns:
            SignalResult bounded [-1.0, 1.0].
        """
        n = len(series.candles)
        if n < max(self.atr_period, self.vol_sma_period):
            return SignalResult(
                family_name="structural", score=0.0, direction=SignalDirection.NEUTRAL,
                is_valid=False, metadata={"filter_failed": "insufficient_data"}
            )
            
        if not snapshot:
            return SignalResult(
                family_name="structural", score=0.0, direction=SignalDirection.NEUTRAL,
                is_valid=False, metadata={"filter_failed": "no_snapshot"}
            )
            
        highs = np.array(series.highs, dtype=np.float64)
        lows = np.array(series.lows, dtype=np.float64)
        closes = np.array(series.closes, dtype=np.float64)
        volumes = np.array(series.volumes, dtype=np.float64)
        
        atr_arr = atr_calc(highs, lows, closes, self.atr_period)
        atr_val = atr_arr[-1]
        
        vol_sma_arr = sma_calc(volumes, self.vol_sma_period)
        vol_sma_val = vol_sma_arr[-1]
        
        latest_bar = series.candles[-1]
        
        # 1. Check for Level Proximity
        best_support, best_resistance = find_tested_levels(
            latest_bar.high, latest_bar.low, atr_val, snapshot
        )
        
        # 2. Check for Trendline Proximity (Requirement 2.3) and Pullback (Requirement 2.5)
        trendline_signal = self._check_trendline_proximity(
            latest_bar, snapshot, atr_val, n - 1, indicators
        )
        
        # If no S/R level and no trendline signal, return neutral
        if not best_support and not best_resistance and not trendline_signal:
            return SignalResult(
                family_name="structural", score=0.0, direction=SignalDirection.NEUTRAL,
                is_valid=False, metadata={"filter_failed": "no_level_or_trendline_tested"}
            )
        
        # 3. Check for Microstructure Rejection
        bull_reject = False
        bear_reject = False
        
        if best_support:
            bull_reject = detect_rejection(
                open_p=latest_bar.open,
                high_p=latest_bar.high,
                low_p=latest_bar.low,
                close_p=latest_bar.close,
                volume=latest_bar.volume,
                vol_sma=vol_sma_val,
                is_support=True
            )
            
        if best_resistance:
            bear_reject = detect_rejection(
                open_p=latest_bar.open,
                high_p=latest_bar.high,
                low_p=latest_bar.low,
                close_p=latest_bar.close,
                volume=latest_bar.volume,
                vol_sma=vol_sma_val,
                is_support=False
            )
        
        # If we have a trendline signal but no microstructure rejection, use trendline signal
        if trendline_signal and not bull_reject and not bear_reject:
            return trendline_signal
            
        if not bull_reject and not bear_reject:
            return SignalResult(
                family_name="structural", score=0.0, direction=SignalDirection.NEUTRAL,
                is_valid=False, metadata={"filter_failed": "no_microstructure_rejection"}
            )
            
        # 4. Calculate Base Conviction
        score = 0.0
        direction = SignalDirection.NEUTRAL
        tested_level = None
        
        if bull_reject and not bear_reject:
            # Assumes max strength score is roughly 5.0
            score = min(1.0, best_support.strength / 5.0)
            direction = SignalDirection.LONG
            tested_level = best_support
        elif bear_reject and not bull_reject:
            score = min(1.0, best_resistance.strength / 5.0)
            direction = SignalDirection.SHORT
            tested_level = best_resistance
        else:
            # Conflicting rejections on the same bar (extremely rare, e.g. giant doji)
            # Pick the higher strength score
            if best_support.strength >= best_resistance.strength:
                score = min(1.0, best_support.strength / 5.0)
                direction = SignalDirection.LONG
                tested_level = best_support
            else:
                score = min(1.0, best_resistance.strength / 5.0)
                direction = SignalDirection.SHORT
                tested_level = best_resistance
                
        metadata = {
            "level_price": tested_level.price,
            "confluence_score": tested_level.strength
        }
        
        # 5. Boost score if trendline also confirms the direction
        if trendline_signal and trendline_signal.direction == direction:
            score *= 1.2
            metadata["trendline_confluence"] = True
                
        # 6. Multi-Timeframe (MTF) Alignment
        if htf_snapshots:
            has_htf_overlap = check_htf_overlap(tested_level, atr_val, htf_snapshots)
            if has_htf_overlap:
                score *= 1.5
                metadata["mtf_overlap"] = True
                
        # 7. Regime Modifiers
        if regime_probs:
            # Boost if mean-reverting (price bounces off structures)
            if regime_probs.mean_revert > 0.5:
                score *= 1.3
                metadata["regime_mod"] = "mean_revert_boost"
                
            # Dampen if strong counter-trend
            # (If trend is strong UP, and we are SHORTING a resistance)
            if direction == SignalDirection.SHORT and regime_probs.trend_up > 0.5:
                score *= 0.3
                metadata["regime_mod"] = "trend_up_dampen"
            # (If trend is strong DOWN, and we are LONGING a support)
            elif direction == SignalDirection.LONG and regime_probs.trend_down > 0.5:
                score *= 0.3
                metadata["regime_mod"] = "trend_down_dampen"
                
        # 8. Final normalization
        score = min(1.0, score)
        if direction == SignalDirection.SHORT:
            score = -score
            
        return SignalResult(
            family_name="structural",
            score=score,
            direction=direction,
            is_valid=True,
            metadata=metadata
        )
    
    def _check_trendline_proximity(
        self,
        latest_bar,
        snapshot: StructuralSnapshot,
        atr_val: float,
        current_index: int,
        indicators: dict | None = None,
        proximity_threshold: float = 0.5
    ) -> SignalResult | None:
        """Check if price is approaching a trendline within 0.5 ATR proximity.
        
        Implements Requirement 2.3 (trendline proximity signals) and Requirement 2.5
        (trendline pullback detection with EMA/RSI/ADX confirmation).
        
        Args:
            latest_bar: Latest OHLCV bar
            snapshot: Structural snapshot containing trendlines
            atr_val: Current ATR value
            current_index: Current bar index
            indicators: Optional indicator values for EMA/RSI/ADX confirmation
            proximity_threshold: ATR multiplier for proximity (default 0.5)
            
        Returns:
            SignalResult if price is near a trendline, None otherwise
        """
        if not snapshot.trendlines:
            return None
            
        # Check active trendlines only
        active_trendlines = [t for t in snapshot.trendlines if not t.broken and not t.invalidated]
        
        if not active_trendlines:
            return None
            
        # Find the strongest trendline near current price
        best_support_trendline = None
        best_resistance_trendline = None
        min_support_distance = float('inf')
        min_resistance_distance = float('inf')
        
        for trendline in active_trendlines:
            line_price = trendline.price_at(current_index)
            
            # Calculate distance from price to trendline
            if trendline.direction == "support":
                # For support, check distance from low
                distance = abs(latest_bar.low - line_price)
                if distance <= atr_val * proximity_threshold and distance < min_support_distance:
                    min_support_distance = distance
                    best_support_trendline = trendline
            else:  # resistance
                # For resistance, check distance from high
                distance = abs(latest_bar.high - line_price)
                if distance <= atr_val * proximity_threshold and distance < min_resistance_distance:
                    min_resistance_distance = distance
                    best_resistance_trendline = trendline
        
        # Determine which trendline to use
        selected_trendline = None
        is_support = False
        distance_atr = 0.0
        
        if best_support_trendline and (not best_resistance_trendline or min_support_distance < min_resistance_distance):
            selected_trendline = best_support_trendline
            is_support = True
            distance_atr = min_support_distance / atr_val
        elif best_resistance_trendline:
            selected_trendline = best_resistance_trendline
            is_support = False
            distance_atr = min_resistance_distance / atr_val
        
        if not selected_trendline:
            return None
        
        # Base signal score from trendline strength
        base_score = min(1.0, selected_trendline.strength / 5.0)
        
        # Requirement 2.5: Check for EMA/RSI/ADX confirmation for pullback signals
        # If indicators are provided, apply confirmation logic
        confirmation_passed = False
        confirmation_metadata = {}
        
        if indicators:
            confirmation_passed, confirmation_metadata = self._check_pullback_confirmation(
                latest_bar, is_support, indicators, snapshot
            )
            
            # If confirmation checks are available but failed, reduce conviction
            if not confirmation_passed:
                base_score *= 0.5  # Reduce score by 50% if confirmation fails
                confirmation_metadata["confirmation_status"] = "failed"
            else:
                base_score *= 1.3  # Boost score by 30% if confirmation passes
                confirmation_metadata["confirmation_status"] = "passed"
        
        # Cap score at 1.0
        base_score = min(1.0, base_score)
        
        # Generate signal based on trendline direction
        if is_support:
            # Price approaching support trendline - potential long signal
            return SignalResult(
                family_name="structural",
                score=base_score,
                direction=SignalDirection.LONG,
                is_valid=True,
                metadata={
                    "signal_type": "trendline_proximity" if not confirmation_passed else "trendline_pullback",
                    "trendline_id": selected_trendline.id,
                    "trendline_direction": "support",
                    "trendline_price": selected_trendline.price_at(current_index),
                    "trendline_strength": selected_trendline.strength,
                    "distance_atr": distance_atr,
                    **confirmation_metadata,
                }
            )
        else:
            # Price approaching resistance trendline - potential short signal
            return SignalResult(
                family_name="structural",
                score=-base_score,  # Negative for short
                direction=SignalDirection.SHORT,
                is_valid=True,
                metadata={
                    "signal_type": "trendline_proximity" if not confirmation_passed else "trendline_pullback",
                    "trendline_id": selected_trendline.id,
                    "trendline_direction": "resistance",
                    "trendline_price": selected_trendline.price_at(current_index),
                    "trendline_strength": selected_trendline.strength,
                    "distance_atr": distance_atr,
                    **confirmation_metadata,
                }
            )
    
    def _check_pullback_confirmation(
        self,
        latest_bar,
        is_support: bool,
        indicators: dict,
        snapshot: StructuralSnapshot
    ) -> tuple[bool, dict]:
        """Check EMA/RSI/ADX confirmation for trendline pullback signals.
        
        Implements Requirement 2.5: Trendline pullback strategy with EMA/RSI/ADX confirmation.
        
        Confirmation criteria:
        - EMA alignment: 5 EMA > 9 EMA > 21 EMA for bullish (reverse for bearish)
        - RSI: Between 40-60 (momentum pause, not oversold/overbought)
        - ADX: > 25 (confirming trend strength)
        
        Args:
            latest_bar: Latest OHLCV bar
            is_support: True if checking support trendline (bullish), False for resistance (bearish)
            indicators: Dictionary of indicator values
            snapshot: Structural snapshot for trend direction
            
        Returns:
            Tuple of (confirmation_passed: bool, metadata: dict)
        """
        metadata = {}
        
        # Extract indicator values
        ema_result = indicators.get("ema")
        rsi_result = indicators.get("rsi")
        adx_result = indicators.get("adx")
        
        if not ema_result or not rsi_result or not adx_result:
            return False, {"confirmation_error": "missing_indicators"}
        
        # Get latest values
        ema_5 = self._get_latest_value(ema_result.values.get("ema_5", []))
        ema_9 = self._get_latest_value(ema_result.values.get("ema_9", []))
        ema_21 = self._get_latest_value(ema_result.values.get("ema_21", []))
        rsi = self._get_latest_value(rsi_result.values.get("rsi", []))
        adx = self._get_latest_value(adx_result.values.get("adx", []))
        
        if ema_5 is None or ema_9 is None or ema_21 is None or rsi is None or adx is None:
            return False, {"confirmation_error": "invalid_indicator_values"}
        
        metadata["ema_5"] = round(ema_5, 4)
        metadata["ema_9"] = round(ema_9, 4)
        metadata["ema_21"] = round(ema_21, 4)
        metadata["rsi"] = round(rsi, 2)
        metadata["adx"] = round(adx, 2)
        
        # Check ADX > 25 (trend strength)
        if adx < 25:
            metadata["adx_check"] = "failed"
            return False, metadata
        metadata["adx_check"] = "passed"
        
        # Check RSI between 40-60 (momentum pause)
        if rsi < 40 or rsi > 60:
            metadata["rsi_check"] = "failed"
            return False, metadata
        metadata["rsi_check"] = "passed"
        
        # Check EMA alignment
        if is_support:
            # Bullish setup: 5 EMA > 9 EMA > 21 EMA
            ema_aligned = ema_5 > ema_9 > ema_21
            metadata["ema_alignment"] = "bullish" if ema_aligned else "not_bullish"
        else:
            # Bearish setup: 5 EMA < 9 EMA < 21 EMA
            ema_aligned = ema_5 < ema_9 < ema_21
            metadata["ema_alignment"] = "bearish" if ema_aligned else "not_bearish"
        
        if not ema_aligned:
            metadata["ema_check"] = "failed"
            return False, metadata
        metadata["ema_check"] = "passed"
        
        # All confirmations passed
        return True, metadata
    
    def _get_latest_value(self, values: list[float]) -> float | None:
        """Get the latest non-NaN value from a list."""
        if not values:
            return None
        for v in reversed(values):
            if not np.isnan(v):
                return float(v)
        return None
