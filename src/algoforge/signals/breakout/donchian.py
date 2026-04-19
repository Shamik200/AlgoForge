"""Donchian Channel calculations and Breakout/Failure pattern recognition."""

import numpy as np


def calc_donchian_channels(highs: np.ndarray, lows: np.ndarray, period: int = 20) -> tuple[np.ndarray, np.ndarray]:
    """Calculate N-period Donchian Channels (rolling high / rolling low).
    
    The current bar's channel uses the rolling high/low of the PREVIOUS N bars,
    so that a breakout on the current bar can be detected by comparing close > channel.
    
    Returns:
        Tuple of (Donchian High, Donchian Low).
    """
    n = len(highs)
    dh = np.full(n, np.nan)
    dl = np.full(n, np.nan)
    
    if n <= period:
        return dh, dl
        
    for i in range(period, n):
        # Look back over previous `period` bars (exclusive of current bar i)
        dh[i] = np.max(highs[i-period:i])
        dl[i] = np.min(lows[i-period:i])
        
    return dh, dl


def detect_breakout(
    closes: np.ndarray,
    donchian_highs: np.ndarray,
    donchian_lows: np.ndarray
) -> tuple[int, int]:
    """Detect simple Donchian breakouts on the most recent bar.
    
    Returns:
        Tuple of (bull_breakout, bear_breakout) as 1/0 integers.
        (1, 0) means bull breakout.
        (0, 1) means bear breakout.
    """
    if len(closes) < 2 or np.isnan(donchian_highs[-1]):
        return 0, 0
        
    bull_breakout = 1 if closes[-1] > donchian_highs[-1] else 0
    bear_breakout = 1 if closes[-1] < donchian_lows[-1] else 0
    
    return bull_breakout, bear_breakout


def detect_failed_breakout(
    closes: np.ndarray,
    donchian_highs: np.ndarray,
    donchian_lows: np.ndarray,
    atr_val: float
) -> tuple[int, int]:
    """Detect stateless failed breakout reversals.
    
    A failed Bull Breakout occurs if the previous close was ABOVE the Donchian High,
    but the current close is back INSIDE the channel by at least 0.5 ATR.
    
    Returns:
        Tuple of (failed_bull, failed_bear) as 1/0 integers.
        If failed_bull == 1, that is a BEARISH reversal signal.
        If failed_bear == 1, that is a BULLISH reversal signal.
    """
    if len(closes) < 2 or np.isnan(donchian_highs[-1]) or atr_val <= 0.0:
        return 0, 0
        
    prev_close = closes[-2]
    curr_close = closes[-1]
    
    dh = donchian_highs[-1]
    dl = donchian_lows[-1]
    
    failed_bull = 0
    failed_bear = 0
    
    # Check failed bull breakout
    if prev_close > donchian_highs[-2] and curr_close < (dh - 0.5 * atr_val):
        failed_bull = 1
        
    # Check failed bear breakout
    if prev_close < donchian_lows[-2] and curr_close > (dl + 0.5 * atr_val):
        failed_bear = 1
        
    return failed_bull, failed_bear
