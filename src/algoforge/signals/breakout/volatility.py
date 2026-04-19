"""Volatility analysis, Keltner Channels, and TTM Squeeze mechanics."""

import numpy as np

from algoforge.technical.indicator_base import atr_calc


def calc_ema(series: np.ndarray, period: int) -> np.ndarray:
    """Calculate Exponential Moving Average."""
    n = len(series)
    ema = np.full(n, np.nan)
    if n < period:
        return ema
        
    alpha = 2.0 / (period + 1)
    
    # Simple SMA for the first valid value
    ema[period-1] = np.mean(series[:period])
    
    for i in range(period, n):
        ema[i] = series[i] * alpha + ema[i-1] * (1 - alpha)
        
    return ema


def calc_keltner_channels(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    ema_period: int = 20,
    atr_period: int = 14,
    multiplier: float = 1.5
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Calculate Keltner Channels.
    
    Centerline = EMA(period)
    Upper Band = Centerline + (multiplier * ATR)
    Lower Band = Centerline - (multiplier * ATR)
    
    Returns:
        Tuple of (upper_band, centerline, lower_band). Arrays are same length as inputs.
    """
    centerline = calc_ema(closes, ema_period)
    atr = atr_calc(highs, lows, closes, atr_period)
    
    upper_band = centerline + (multiplier * atr)
    lower_band = centerline - (multiplier * atr)
    
    return upper_band, centerline, lower_band


def detect_squeeze(
    bb_upper: np.ndarray,
    bb_lower: np.ndarray,
    kc_upper: np.ndarray,
    kc_lower: np.ndarray
) -> np.ndarray:
    """Detect TTM-style Volatility Squeeze.
    
    A squeeze is active when Bollinger Bands are completely inside Keltner Channels.
    
    Returns:
        Boolean array where True indicates a squeeze is active.
    """
    # Squeeze is active if BB upper < KC upper AND BB lower > KC lower
    return (bb_upper < kc_upper) & (bb_lower > kc_lower)


def calc_squeeze_duration(squeeze_series: np.ndarray) -> np.ndarray:
    """Calculate consecutive duration of a squeeze.
    
    Returns:
        Integer array of durations. 0 means no squeeze, N means active for N bars.
    """
    duration = np.zeros_like(squeeze_series, dtype=int)
    count = 0
    
    for i in range(len(squeeze_series)):
        if squeeze_series[i]:
            count += 1
            duration[i] = count
        else:
            count = 0
            duration[i] = 0
            
    return duration
