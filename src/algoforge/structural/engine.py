"""Structural Confluence Engine.

Aggregates data from Volume Profiles, Moving Averages, and Swing Points
to detect objective zones of Support and Resistance and assign a 
Confluence Score (0-5) to each zone.
"""

from __future__ import annotations

import numpy as np

from algoforge.core.models import OHLCVSeries
from algoforge.structural.models import ConfluenceZone, LevelType, PriceLevel
from algoforge.structural.swings import cluster_swings, detect_swings
from algoforge.technical.engine import IndicatorSnapshot
from algoforge.technical.indicator_base import ema_calc


class StructuralConfluenceEngine:
    """Detects and scores zones of structural confluence.
    
    Combines:
      - Swing Points (Highs/Lows)
      - Volume Profile (POC, VAH, VAL)
      - Dynamic Support/Resistance (KAMA, EMA 50/200)
    
    Usage:
        engine = StructuralConfluenceEngine()
        zones = engine.compute(series, indicator_snapshot)
        high_confluence = [z for z in zones if z.is_high_confluence]
    """

    def __init__(self, confluence_bandwidth_atr: float = 0.5) -> None:
        """Initialize the Confluence Engine.
        
        Args:
            confluence_bandwidth_atr: The bandwidth (in ATR multiplier) used to 
                cluster individual price levels into a single ConfluenceZone.
        """
        self._bandwidth_atr = confluence_bandwidth_atr

    def compute(
        self, series: OHLCVSeries, snapshot: IndicatorSnapshot
    ) -> list[ConfluenceZone]:
        """Compute structural confluence zones.
        
        Args:
            series: Raw price and volume data.
            snapshot: Most recent indicator calculations for this series.
            
        Returns:
            List of detected ConfluenceZones sorted by price.
        """
        if series.is_empty:
            return []

        closes = np.array(series.closes, dtype=np.float64)
        highs = np.array(series.highs, dtype=np.float64)
        lows = np.array(series.lows, dtype=np.float64)
        
        # 1. Get ATR for distance thresholds
        atr_result = snapshot.get("atr")
        if atr_result and not atr_result.is_empty:
            current_atr = atr_result.latest.get("atr", 0.0)
        else:
            # Fallback if ATR isn't available
            current_atr = float(np.mean(highs[-14:] - lows[-14:])) if len(highs) >= 14 else 1.0
            
        if current_atr <= 0:
            current_atr = 1.0  # Safe default

        levels: list[PriceLevel] = []

        # 2. Extract Volume Profile levels (POC, VAH, VAL)
        vp_result = snapshot.get("volume_profile")
        if vp_result and not vp_result.is_empty:
            vp_latest = vp_result.latest
            if "poc" in vp_latest:
                levels.append(PriceLevel(price=vp_latest["poc"], level_type=LevelType.POC, strength=1.0))
            if "vah" in vp_latest:
                levels.append(PriceLevel(price=vp_latest["vah"], level_type=LevelType.VAH, strength=0.8))
            if "val" in vp_latest:
                levels.append(PriceLevel(price=vp_latest["val"], level_type=LevelType.VAL, strength=0.8))

        # 3. Extract Dynamic S/R (KAMA and EMAs)
        # KAMA is in the core engine
        kama_result = snapshot.get("kama")
        if kama_result and not kama_result.is_empty:
            kama_price = kama_result.latest.get("kama")
            if kama_price is not None and not np.isnan(kama_price):
                # Determine if it's support or resistance based on current price
                current_price = closes[-1]
                l_type = LevelType.DYNAMIC_SUPPORT if current_price > kama_price else LevelType.DYNAMIC_RESISTANCE
                levels.append(PriceLevel(price=kama_price, level_type=l_type, strength=0.7))

        # Calculate EMAs (50 and 200) locally since they are not in the core v2 engine by default
        if len(closes) >= 50:
            ema50 = ema_calc(closes, 50)[-1]
            if not np.isnan(ema50):
                l_type = LevelType.DYNAMIC_SUPPORT if closes[-1] > ema50 else LevelType.DYNAMIC_RESISTANCE
                levels.append(PriceLevel(price=ema50, level_type=l_type, strength=0.6))
                
        if len(closes) >= 200:
            ema200 = ema_calc(closes, 200)[-1]
            if not np.isnan(ema200):
                l_type = LevelType.DYNAMIC_SUPPORT if closes[-1] > ema200 else LevelType.DYNAMIC_RESISTANCE
                levels.append(PriceLevel(price=ema200, level_type=l_type, strength=0.8))

        # 4. Detect and Cluster Swing Points
        raw_swings = detect_swings(highs, lows, left_bars=5, right_bars=5)
        clustered_swings = cluster_swings(raw_swings, atr=current_atr)
        levels.extend(clustered_swings)

        # 5. Aggregate into Confluence Zones
        zones = self._aggregate_zones(levels, current_atr)
        
        return zones

    def _aggregate_zones(self, levels: list[PriceLevel], atr: float) -> list[ConfluenceZone]:
        """Group individual price levels into Confluence Zones.
        
        Calculates the score based on the converging elements.
        """
        if not levels:
            return []

        # Sort levels by price to facilitate 1D clustering
        sorted_levels = sorted(levels, key=lambda x: x.price)
        threshold = self._bandwidth_atr * atr
        
        zones: list[ConfluenceZone] = []
        current_group = [sorted_levels[0]]

        def _create_zone(group: list[PriceLevel]) -> ConfluenceZone:
            # Weighted average price based on strength
            total_strength = sum(l.strength for l in group)
            if total_strength > 0:
                center_price = sum(l.price * l.strength for l in group) / total_strength
            else:
                center_price = np.mean([l.price for l in group])
                
            upper = max(l.price for l in group) + (0.1 * atr) # Give it a little buffer
            lower = min(l.price for l in group) - (0.1 * atr)
            
            # Score Calculation (max 5)
            # - Each swing point type adds its strength
            # - POC adds 1.0, VAH/VAL adds 0.8
            # - Dynamic adds 0.6 to 0.8
            # We also give a bonus for diversity of level types.
            types_present = {l.level_type for l in group}
            diversity_bonus = 0.5 * len(types_present)
            
            base_score = sum(l.strength for l in group)
            total_score = min(5.0, base_score + diversity_bonus)
            
            return ConfluenceZone(
                center_price=float(center_price),
                upper_bound=float(upper),
                lower_bound=float(lower),
                score=float(total_score),
                contributing_levels=group
            )

        for i in range(1, len(sorted_levels)):
            level = sorted_levels[i]
            group_price = np.mean([l.price for l in current_group])
            
            if abs(level.price - group_price) <= threshold:
                current_group.append(level)
            else:
                zones.append(_create_zone(current_group))
                current_group = [level]

        # Process the last group
        if current_group:
            zones.append(_create_zone(current_group))

        return sorted(zones, key=lambda x: x.center_price)
