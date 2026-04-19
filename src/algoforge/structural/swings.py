"""Swing point detection and clustering algorithms.

Objective detection of local highs and lows, and algorithms to cluster
proximate swing points into robust structural zones of support/resistance.
"""

from __future__ import annotations

import numpy as np

from algoforge.structural.models import LevelType, PriceLevel


def detect_swings(
    highs: np.ndarray,
    lows: np.ndarray,
    left_bars: int = 5,
    right_bars: int = 5,
) -> list[PriceLevel]:
    """Detect local swing highs and lows in price data.
    
    A point is a swing high if it is the highest high within `left_bars` before
    and `right_bars` after it. Similarly for swing lows.

    Args:
        highs: Array of high prices.
        lows: Array of low prices.
        left_bars: Number of bars to the left to check for extrema.
        right_bars: Number of bars to the right to check for extrema.

    Returns:
        List of detected PriceLevel objects (LevelType.SWING_HIGH/LOW).
    """
    if len(highs) != len(lows):
        msg = "Highs and lows arrays must have the same length."
        raise ValueError(msg)

    n = len(highs)
    levels: list[PriceLevel] = []
    
    # Need at least left_bars + right_bars + 1 data points
    if n < left_bars + right_bars + 1:
        return levels

    # Detect Swing Highs
    for i in range(left_bars, n - right_bars):
        is_high = True
        for j in range(i - left_bars, i + right_bars + 1):
            if i != j and highs[j] >= highs[i]:
                is_high = False
                break
        
        if is_high:
            # Strength could be enhanced by volume or magnitude, using 1.0 for now
            age = n - 1 - i
            levels.append(
                PriceLevel(
                    price=float(highs[i]),
                    level_type=LevelType.SWING_HIGH,
                    strength=1.0,
                    age=age
                )
            )

    # Detect Swing Lows
    for i in range(left_bars, n - right_bars):
        is_low = True
        for j in range(i - left_bars, i + right_bars + 1):
            if i != j and lows[j] <= lows[i]:
                is_low = False
                break
        
        if is_low:
            age = n - 1 - i
            levels.append(
                PriceLevel(
                    price=float(lows[i]),
                    level_type=LevelType.SWING_LOW,
                    strength=1.0,
                    age=age
                )
            )

    # Sort by price for downstream processing convenience
    return sorted(levels, key=lambda x: x.price)


def cluster_swings(swings: list[PriceLevel], atr: float) -> list[PriceLevel]:
    """Cluster proximate swing points into stronger merged levels.
    
    Uses a greedy 1D clustering approach. Swings within a certain distance
    (defined by a multiplier of ATR) are grouped together into a single,
    stronger structural level.

    Args:
        swings: List of raw swing PriceLevels.
        atr: The current Average True Range, used to define the clustering threshold.

    Returns:
        List of clustered PriceLevel objects. Strength is aggregated.
    """
    if not swings:
        return []

    # Distance threshold for clustering (e.g., 0.5 * ATR)
    # This means levels within half an ATR are considered the same structural zone.
    threshold = 0.5 * atr

    # Separate highs and lows to cluster them independently
    highs = sorted([s for s in swings if s.level_type == LevelType.SWING_HIGH], key=lambda x: x.price)
    lows = sorted([s for s in swings if s.level_type == LevelType.SWING_LOW], key=lambda x: x.price)

    def _cluster_group(levels: list[PriceLevel], level_type: LevelType) -> list[PriceLevel]:
        if not levels:
            return []

        clusters: list[PriceLevel] = []
        current_cluster = [levels[0]]

        for i in range(1, len(levels)):
            level = levels[i]
            # Average price of current cluster
            cluster_price = np.mean([l.price for l in current_cluster])
            
            if abs(level.price - cluster_price) <= threshold:
                current_cluster.append(level)
            else:
                # Finalize current cluster
                avg_price = float(np.mean([l.price for l in current_cluster]))
                # Aggregated strength: cap at 1.0, or use a decay function based on age.
                # For now, simply sum up to a max of 1.0, or boost it slightly for multi-touches.
                base_strength = sum(l.strength for l in current_cluster)
                # Normalize strength (e.g. 1 touch = 0.5, 2 touches = 0.75, 3 touches = 1.0)
                # Here we use a simple logarithmic scale for touches.
                touches = len(current_cluster)
                agg_strength = min(1.0, 0.5 + (0.15 * touches))
                
                # Minimum age among the clustered touches (most recent touch)
                min_age = min(l.age for l in current_cluster)

                clusters.append(
                    PriceLevel(
                        price=avg_price,
                        level_type=level_type,
                        strength=agg_strength,
                        age=min_age
                    )
                )
                current_cluster = [level]

        # Finalize last cluster
        if current_cluster:
            avg_price = float(np.mean([l.price for l in current_cluster]))
            touches = len(current_cluster)
            agg_strength = min(1.0, 0.5 + (0.15 * touches))
            min_age = min(l.age for l in current_cluster)
            
            clusters.append(
                PriceLevel(
                    price=avg_price,
                    level_type=level_type,
                    strength=agg_strength,
                    age=min_age
                )
            )
            
        return clusters

    clustered_highs = _cluster_group(highs, LevelType.SWING_HIGH)
    clustered_lows = _cluster_group(lows, LevelType.SWING_LOW)

    return sorted(clustered_highs + clustered_lows, key=lambda x: x.price)
