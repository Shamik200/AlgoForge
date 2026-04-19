"""Volume-Weighted Average Price (VWAP) calculation with session resets."""

import numpy as np

from algoforge.core.models import OHLCVSeries


def calculate_vwap(series: OHLCVSeries) -> np.ndarray:
    """Calculate the rolling VWAP, resetting at each new trading day.
    
    VWAP = sum(Typical Price * Volume) / sum(Volume)
    Typical Price = (High + Low + Close) / 3
    
    Args:
        series: OHLCV data series. Should ideally be intraday data (e.g., 1m, 5m).
        
    Returns:
        1D numpy array containing the VWAP value for each bar.
    """
    n = len(series.closes)
    if n == 0:
        return np.array([])
        
    vwap = np.zeros(n, dtype=np.float64)
    
    cum_vol_price = 0.0
    cum_vol = 0.0
    current_day = -1
    
    for i, bar in enumerate(series.candles):
        # Extract the day from the timestamp to detect session boundaries
        bar_day = bar.timestamp.timetuple().tm_yday
        
        # Reset accumulations at the start of a new trading day
        if bar_day != current_day:
            cum_vol_price = 0.0
            cum_vol = 0.0
            current_day = bar_day
            
        typical_price = (bar.high + bar.low + bar.close) / 3.0
        
        cum_vol_price += typical_price * bar.volume
        cum_vol += bar.volume
        
        if cum_vol > 0:
            vwap[i] = cum_vol_price / cum_vol
        else:
            vwap[i] = typical_price
            
    return vwap


def vwap_momentum_score(close: float, vwap_value: float) -> float:
    """Calculate a normalized momentum score based on VWAP deviation.
    
    Args:
        close: Current close price.
        vwap_value: Current VWAP value.
        
    Returns:
        A score between -1.0 and 1.0 representing distance from VWAP.
    """
    if vwap_value <= 0:
        return 0.0
        
    # Percentage deviation from VWAP
    deviation = (close - vwap_value) / vwap_value
    
    # Normalize typical deviations (e.g. +/- 2%) to a [-1, 1] scale.
    # We use a soft tanh-like bounding to prevent extreme outliers 
    # from completely breaking the composite score.
    # A 1% deviation translates to ~0.76 score
    score = np.tanh(deviation * 100.0)
    
    return float(score)
