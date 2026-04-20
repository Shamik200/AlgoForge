"""Microstructure rejection detection (Candlestick wicks and Volume climax)."""

import numpy as np


def detect_rejection(
    open_p: float,
    high_p: float,
    low_p: float,
    close_p: float,
    volume: float,
    vol_sma: float,
    is_support: bool,
    min_wick_ratio: float = 0.5,
    min_vol_ratio: float = 1.5
) -> bool:
    """Detect if the current bar shows a strong microstructure rejection.
    
    Args:
        open_p: Bar open.
        high_p: Bar high.
        low_p: Bar low.
        close_p: Bar close.
        volume: Bar volume.
        vol_sma: SMA(Volume) at this bar.
        is_support: True if testing support (needs lower wick), False if testing resistance (needs upper wick).
        min_wick_ratio: Minimum ratio of wick to total candle range.
        min_vol_ratio: Minimum ratio of volume to volume SMA.
        
    Returns:
        True if the candlestick shows a valid rejection pattern.
    """
    total_range = high_p - low_p
    
    # A tiny or zero-range bar is not a strong rejection
    if total_range <= 0.0:
        return False
        
    # 1. Volume Climax Check
    vol_ratio = volume / vol_sma if vol_sma > 0 else 0.0
    if vol_ratio < min_vol_ratio:
        return False
        
    # 2. Wick Rejection Check
    if is_support:
        # Lower wick size = min(Open, Close) - Low
        lower_wick = min(open_p, close_p) - low_p
        wick_ratio = lower_wick / total_range
        return wick_ratio >= min_wick_ratio
    else:
        # Upper wick size = High - max(Open, Close)
        upper_wick = high_p - max(open_p, close_p)
        wick_ratio = upper_wick / total_range
        return wick_ratio >= min_wick_ratio
