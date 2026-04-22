"""Initial Stop Loss logic anchored to ATR and HMM regimes."""

from algoforge.risk.models import TradeDirection


def calculate_initial_stop(
    entry_price: float,
    direction: TradeDirection,
    atr: float,
    regime_state: str = "trending"
) -> float:
    """Calculate the ATR-anchored initial stop loss.
    
    Args:
        entry_price: The exact entry price of the trade.
        direction: LONG or SHORT.
        atr: The current Average True Range (e.g. ATR(14)).
        regime_state: The current HMM regime ("trending" or "ranging").
        
    Returns:
        The exact price level for the initial stop loss.
    """
    if atr <= 0:
        # Fallback if ATR is invalid, use 1% stop
        distance = entry_price * 0.01
    else:
        multiplier = 1.5 if regime_state.lower() == "trending" else 1.0
        distance = atr * multiplier
        
    if direction == TradeDirection.LONG:
        return entry_price - distance
    else:
        return entry_price + distance
