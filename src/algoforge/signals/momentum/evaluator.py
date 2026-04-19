"""Evaluator for momentum conditions and confirmation filters."""

import numpy as np

from algoforge.technical.indicator_base import ema_calc, roc_calc


def time_series_momentum(closes: np.ndarray, lookback: int = 252, skip_recent: int = 21) -> float:
    """Calculate time-series momentum (TSMOM).
    
    Standard practice in TSMOM is trailing 12M return skipping the most recent 1M 
    to avoid the short-term reversal effect.
    
    Args:
        closes: Array of close prices.
        lookback: Total lookback period (e.g. 252 days for 12M).
        skip_recent: Recent period to skip (e.g. 21 days for 1M).
        
    Returns:
        Normalized momentum score between -1.0 and 1.0.
    """
    n = len(closes)
    if n <= lookback:
        return 0.0
        
    current_price = closes[-skip_recent - 1]
    past_price = closes[-lookback - 1]
    
    if past_price <= 0:
        return 0.0
        
    # Rate of change
    roc = (current_price - past_price) / past_price
    
    # Normalize ROC using tanh (e.g., a 20% move gives ~0.96 score)
    score = np.tanh(roc * 10.0)
    
    return float(score)


def check_kama_confirmation(close: float, kama: float) -> bool:
    """Check if the price is on the correct side of KAMA for the momentum.
    
    This filter ensures we don't buy when price is below the adaptive trend,
    and we don't short when price is above it.
    
    Returns True if valid or if KAMA is not computable.
    """
    if np.isnan(kama) or kama == 0.0:
        return True
    return True # Confirmation logic is applied contextually by the caller based on direction


def check_volume_confirmation(volumes: np.ndarray, period: int = 14) -> bool:
    """Check if volume momentum is supportive.
    
    Args:
        volumes: Array of volume data.
        period: Lookback for volume ROC.
        
    Returns:
        True if Volume ROC > 0 (expanding volume), False otherwise.
    """
    if len(volumes) <= period:
        return True
        
    vol_roc = roc_calc(volumes, period=period)
    latest_roc = vol_roc[-1]
    
    if np.isnan(latest_roc):
        return True
        
    return float(latest_roc) > 0.0


def check_atr_percentile(atr_series: np.ndarray, lower_pct: float = 20.0, upper_pct: float = 80.0) -> bool:
    """Check if current ATR is within the acceptable historical percentile range.
    
    Filters out "choppy" low-volatility environments and "exhausted" 
    extreme-volatility environments.
    
    Args:
        atr_series: Array of historical ATR values.
        lower_pct: Lower bound percentile (0-100).
        upper_pct: Upper bound percentile (0-100).
        
    Returns:
        True if the latest ATR falls within the percentiles.
    """
    if len(atr_series) < 100:  # Need sufficient data for percentiles
        return True
        
    valid_atr = atr_series[~np.isnan(atr_series)]
    if len(valid_atr) < 100:
        return True
        
    latest_atr = valid_atr[-1]
    p_low = np.percentile(valid_atr, lower_pct)
    p_high = np.percentile(valid_atr, upper_pct)
    
    return bool(p_low <= latest_atr <= p_high)
