"""Logic for splitting a trade into independent exit tranches."""

import uuid

from algoforge.risk.models import ActivePosition, TradeDirection


def split_into_tranches(
    symbol: str,
    direction: TradeDirection,
    sector: str,
    entry_price: float,
    initial_stop_loss: float,
    total_position_size_value: float,
    current_price: float
) -> list[ActivePosition]:
    """Split an approved trade into three independent tranches.
    
    Tranche 1: 50% volume. Take Profit = 1.5R.
    Tranche 2: 30% volume. Take Profit = 2.5R.
    Tranche 3: 20% volume. Runner (No hard TP, uses trailing stop).
    
    Args:
        symbol: The asset ticker.
        direction: LONG or SHORT.
        sector: The sector of the asset.
        entry_price: The exact entry price.
        initial_stop_loss: The ATR-anchored stop loss.
        total_position_size_value: The total dollar risk/value approved by the Risk Engine.
        current_price: The current market price.
        
    Returns:
        A list of three ActivePosition objects representing the tranches.
    """
    parent_id = str(uuid.uuid4())
    risk_distance = abs(entry_price - initial_stop_loss)
    
    if risk_distance == 0:
        # Fallback if SL == Entry
        risk_distance = entry_price * 0.01
        
    # Calculate R-multiple take profits
    if direction == TradeDirection.LONG:
        tp1 = entry_price + (1.5 * risk_distance)
        tp2 = entry_price + (2.5 * risk_distance)
    else:
        tp1 = entry_price - (1.5 * risk_distance)
        tp2 = entry_price - (2.5 * risk_distance)
        
    # Base configuration shared across all tranches
    base_kwargs = {
        "symbol": symbol,
        "direction": direction,
        "sector": sector,
        "entry_price": entry_price,
        "current_price": current_price,
        "parent_trade_id": parent_id,
        "stop_loss_price": initial_stop_loss,
        "elapsed_candles": 0,
        "is_breakeven": False
    }
    
    # Tranche 1 (50%)
    t1 = ActivePosition(
        tranche_id=1,
        position_size_value=total_position_size_value * 0.50,
        take_profit_price=tp1,
        **base_kwargs
    )
    
    # Tranche 2 (30%)
    t2 = ActivePosition(
        tranche_id=2,
        position_size_value=total_position_size_value * 0.30,
        take_profit_price=tp2,
        **base_kwargs
    )
    
    # Tranche 3 (20%, Runner)
    t3 = ActivePosition(
        tranche_id=3,
        position_size_value=total_position_size_value * 0.20,
        take_profit_price=None, # No hard TP
        trailing_step=None,     # Set dynamically by the manager later based on ATR
        **base_kwargs
    )
    
    return [t1, t2, t3]
