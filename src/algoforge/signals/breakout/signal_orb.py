"""Opening Range Breakout (ORB) Signal class."""

import numpy as np
from datetime import time

from algoforge.core.models import OHLCVSeries
from algoforge.signals.models import SignalDirection, SignalResult
from algoforge.technical.indicator_base import sma_calc


class ORBSignal:
    """Generates intraday Opening Range Breakout signals.
    
    Tracks the high and low of the first N minutes of the trading session.
    A signal is generated when price breaks this range with volume confirmation.
    """

    def __init__(self, open_time: time = time(9, 30), duration_minutes: int = 30) -> None:
        """Initialize ORB Signal.
        
        Args:
            open_time: The start time of the trading session.
            duration_minutes: The length of the opening range window.
        """
        self.open_time = open_time
        self.duration_minutes = duration_minutes

    def evaluate(self, series: OHLCVSeries) -> SignalResult:
        """Evaluate ORB breakout.
        
        Args:
            series: Intraday OHLCV data.
            
        Returns:
            SignalResult bounded [-1.0, 1.0].
        """
        # Timeframe guard: ORB doesn't make sense on Daily or higher
        if series.timeframe.value in ["1d", "1w", "1M"]:
            return SignalResult(
                family_name="orb", score=0.0, direction=SignalDirection.NEUTRAL,
                is_valid=False, metadata={"filter_failed": "invalid_timeframe"}
            )
            
        n = len(series.candles)
        if n < 20:
            return SignalResult(
                family_name="orb", score=0.0, direction=SignalDirection.NEUTRAL,
                is_valid=False, metadata={"filter_failed": "insufficient_data"}
            )
            
        # Find the opening range for the current day
        latest_bar = series.candles[-1]
        latest_date = latest_bar.timestamp.date()
        
        orb_high = -float("inf")
        orb_low = float("inf")
        orb_established = False
        
        # Traverse backwards to find the opening range for today
        for i in range(n - 1, -1, -1):
            bar = series.candles[i]
            if bar.timestamp.date() != latest_date:
                break
                
            bar_time = bar.timestamp.time()
            
            # Simple check: if bar is within the ORB window
            # Convert to minutes since midnight for easy comparison
            bar_mins = bar_time.hour * 60 + bar_time.minute
            open_mins = self.open_time.hour * 60 + self.open_time.minute
            end_mins = open_mins + self.duration_minutes
            
            if open_mins <= bar_mins < end_mins:
                orb_high = max(orb_high, bar.high)
                orb_low = min(orb_low, bar.low)
                orb_established = True
                
        if not orb_established:
            return SignalResult(
                family_name="orb", score=0.0, direction=SignalDirection.NEUTRAL,
                is_valid=False, metadata={"filter_failed": "no_opening_range"}
            )
            
        # Check volume confirmation
        volumes = np.array(series.volumes, dtype=np.float64)
        vol_sma = sma_calc(volumes, 20)
        latest_vol_ratio = volumes[-1] / vol_sma[-1] if vol_sma[-1] > 0 else 0.0
        
        if latest_vol_ratio <= 1.5:
            return SignalResult(
                family_name="orb", score=0.0, direction=SignalDirection.NEUTRAL,
                is_valid=False, metadata={"filter_failed": "insufficient_volume", "vol_ratio": latest_vol_ratio}
            )
            
        # We only consider it a breakout if we are currently PAST the opening range window
        latest_mins = latest_bar.timestamp.time().hour * 60 + latest_bar.timestamp.time().minute
        end_mins = self.open_time.hour * 60 + self.open_time.minute + self.duration_minutes
        
        if latest_mins < end_mins:
            return SignalResult(
                family_name="orb", score=0.0, direction=SignalDirection.NEUTRAL,
                is_valid=False, metadata={"filter_failed": "still_in_orb_window"}
            )
            
        score = 0.0
        direction = SignalDirection.NEUTRAL
        
        if latest_bar.close > orb_high:
            score = 1.0
            direction = SignalDirection.LONG
        elif latest_bar.close < orb_low:
            score = -1.0
            direction = SignalDirection.SHORT
            
        return SignalResult(
            family_name="orb",
            score=score,
            direction=direction,
            is_valid=score != 0.0,
            metadata={"orb_high": orb_high, "orb_low": orb_low, "vol_ratio": latest_vol_ratio}
        )
