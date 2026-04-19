"""RSI Divergence detection using structural swing points."""

import numpy as np

from algoforge.structural.swings import detect_swings


def detect_rsi_divergence(
    closes: np.ndarray,
    rsi_series: np.ndarray,
    lookback: int = 100,
    swing_bars: int = 3
) -> float:
    """Detect Bullish or Bearish divergence between price and RSI.
    
    Uses strict structural pivot matching. 
    Bullish Divergence: Price makes Lower Low, RSI makes Higher Low. -> Returns 1.0
    Bearish Divergence: Price makes Higher High, RSI makes Lower High. -> Returns -1.0
    No Divergence -> Returns 0.0
    
    Args:
        closes: Array of close prices.
        rsi_series: Array of RSI values.
        lookback: How far back to search for swings.
        swing_bars: Pivot strength (bars to left/right).
        
    Returns:
        Score: 1.0 (Bullish), -1.0 (Bearish), or 0.0
    """
    n = len(closes)
    if n < lookback or len(rsi_series) != n:
        return 0.0
        
    # We only look at the recent window to avoid outdated structural pivots
    recent_closes = closes[-lookback:]
    recent_rsi = rsi_series[-lookback:]
    
    # We treat Close prices as Highs and Lows for simplified structure matching
    price_swings = detect_swings(recent_closes, recent_closes, left_bars=swing_bars, right_bars=swing_bars)
    
    # We treat RSI as Highs and Lows
    rsi_swings = detect_swings(recent_rsi, recent_rsi, left_bars=swing_bars, right_bars=swing_bars)
    
    if len(price_swings) < 2 or len(rsi_swings) < 2:
        return 0.0
        
    # Extract structural points and sort by age (ascending, so index 0 is most recent)
    price_highs = sorted([s for s in price_swings if s.level_type.value == "swing_high"], key=lambda x: x.age)
    price_lows = sorted([s for s in price_swings if s.level_type.value == "swing_low"], key=lambda x: x.age)
    
    rsi_highs = sorted([s for s in rsi_swings if s.level_type.value == "swing_high"], key=lambda x: x.age)
    rsi_lows = sorted([s for s in rsi_swings if s.level_type.value == "swing_low"], key=lambda x: x.age)
    
    # 1. Check for Bullish Divergence (Price Lower Low, RSI Higher Low)
    if len(price_lows) >= 2 and len(rsi_lows) >= 2:
        last_price_low = price_lows[0]  # Most recent
        prev_price_low = price_lows[1]  # Previous
        
        last_rsi_low = rsi_lows[0]
        prev_rsi_low = rsi_lows[1]
        
        # Are the two most recent pivots relatively close in time?
        if abs(last_price_low.age - last_rsi_low.age) <= 2 and abs(prev_price_low.age - prev_rsi_low.age) <= 2:
            if last_price_low.price < prev_price_low.price and last_rsi_low.price > prev_rsi_low.price:
                return 1.0
                
    # 2. Check for Bearish Divergence (Price Higher High, RSI Lower High)
    if len(price_highs) >= 2 and len(rsi_highs) >= 2:
        last_price_high = price_highs[0]
        prev_price_high = price_highs[1]
        
        last_rsi_high = rsi_highs[0]
        prev_rsi_high = rsi_highs[1]
        
        if abs(last_price_high.age - last_rsi_high.age) <= 2 and abs(prev_price_high.age - prev_rsi_high.age) <= 2:
            if last_price_high.price > prev_price_high.price and last_rsi_high.price < prev_rsi_high.price:
                return -1.0
                
    return 0.0


def bollinger_percent_b(close: float, upper_band: float, lower_band: float) -> float:
    """Calculate the %B of the current price relative to Bollinger Bands.
    
    Returns:
        %B value (usually 0.0 to 1.0, but can exceed if price is outside bands).
    """
    band_width = upper_band - lower_band
    if band_width <= 0:
        return 0.5
        
    return (close - lower_band) / band_width


def evaluate_bollinger_divergence(
    close: float,
    upper_band: float,
    lower_band: float,
    divergence_score: float
) -> float:
    """Evaluate if %B is at an extreme AND corroborated by RSI divergence.
    
    Returns:
        Normalized score [-1.0, 1.0].
    """
    pct_b = bollinger_percent_b(close, upper_band, lower_band)
    
    # Bullish: Oversold (< 0.05) + Bullish Divergence (+1.0)
    if pct_b < 0.05 and divergence_score > 0.5:
        return 1.0
        
    # Bearish: Overbought (> 0.95) + Bearish Divergence (-1.0)
    if pct_b > 0.95 and divergence_score < -0.5:
        return -1.0
        
    return 0.0
