"""Structural Confluence Signal class combining Phase 4 snapshots with micro-structure rejection."""

import numpy as np

from algoforge.core.models import OHLCVSeries
from algoforge.regime.models import RegimeProbabilities
from algoforge.signals.models import SignalDirection, SignalResult
from algoforge.signals.structural.microstructure import detect_rejection
from algoforge.signals.structural.proximity import check_htf_overlap, find_tested_levels
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
        regime_probs: RegimeProbabilities | None = None
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
        
        if not best_support and not best_resistance:
            return SignalResult(
                family_name="structural", score=0.0, direction=SignalDirection.NEUTRAL,
                is_valid=False, metadata={"filter_failed": "no_level_tested"}
            )
            
        # 2. Check for Microstructure Rejection
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
            
        if not bull_reject and not bear_reject:
            return SignalResult(
                family_name="structural", score=0.0, direction=SignalDirection.NEUTRAL,
                is_valid=False, metadata={"filter_failed": "no_microstructure_rejection"}
            )
            
        # 3. Calculate Base Conviction
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
                
        # 4. Multi-Timeframe (MTF) Alignment
        if htf_snapshots:
            has_htf_overlap = check_htf_overlap(tested_level, atr_val, htf_snapshots)
            if has_htf_overlap:
                score *= 1.5
                metadata["mtf_overlap"] = True
                
        # 5. Regime Modifiers
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
                
        # 6. Final normalization
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
