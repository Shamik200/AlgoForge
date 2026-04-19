"""Rolling VWAP and Z-Score calculation for mean reversion signals."""

import numpy as np

from algoforge.core.models import OHLCVSeries


def calculate_rolling_vwap(series: OHLCVSeries, period: int = 20) -> np.ndarray:
    """Calculate an N-period rolling VWAP.
    
    Rolling VWAP = sum(Typical Price * Volume, N) / sum(Volume, N)
    Typical Price = (High + Low + Close) / 3
    
    Args:
        series: OHLCV data series.
        period: The rolling window size.
        
    Returns:
        1D numpy array containing the rolling VWAP value.
    """
    n = len(series.candles)
    if n == 0:
        return np.array([])
        
    vwap = np.full(n, np.nan, dtype=np.float64)
    
    if n < period:
        return vwap
        
    # Extract arrays
    highs = np.array(series.highs)
    lows = np.array(series.lows)
    closes = np.array(series.closes)
    volumes = np.array(series.volumes)
    
    typical_prices = (highs + lows + closes) / 3.0
    vol_price = typical_prices * volumes
    
    # Calculate rolling sums using convolution for speed
    window = np.ones(period)
    sum_vol_price = np.convolve(vol_price, window, mode='valid')
    sum_vol = np.convolve(volumes, window, mode='valid')
    
    # Prevent division by zero
    valid_mask = sum_vol > 0
    
    rolling_vwap_valid = np.where(
        valid_mask,
        sum_vol_price / np.where(valid_mask, sum_vol, 1.0),
        typical_prices[period-1:]
    )
    
    vwap[period-1:] = rolling_vwap_valid
    return vwap


def vwap_zscore(closes: np.ndarray, vwaps: np.ndarray, period: int = 20) -> float:
    """Calculate the Z-Score of the current price relative to the rolling VWAP.
    
    Z = (Close - VWAP) / StdDev(Close, N)
    
    Args:
        closes: Array of close prices.
        vwaps: Array of rolling VWAP values.
        period: Rolling window size for StdDev.
        
    Returns:
        Normalized z-score. Inverse bounded to [-1.0, 1.0] for mean reversion.
    """
    if len(closes) < period or np.isnan(vwaps[-1]):
        return 0.0
        
    latest_close = closes[-1]
    latest_vwap = vwaps[-1]
    
    recent_closes = closes[-period:]
    std_dev = np.std(recent_closes)
    
    if std_dev == 0.0:
        return 0.0
        
    # Standard Z-Score
    z = (latest_close - latest_vwap) / std_dev
    
    # We invert the z-score because if price is +2 SD above VWAP, 
    # the mean reversion signal should be strongly negative (SHORT).
    # If price is -2 SD below VWAP, signal is positive (LONG).
    # tanh(z/2) maps a z-score of 2 to ~0.76.
    score = np.tanh(-z / 2.0)
    
    return float(score)
