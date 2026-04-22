"""Exit Manager to evaluate dynamic stops at each candle close."""

from algoforge.risk.models import ActivePosition, TradeDirection


class ExitManager:
    """Evaluates time-based and dynamic exits for active tranches."""
    
    def __init__(self, time_limit_candles: int = 45, trailing_atr_multiplier: float = 2.0) -> None:
        """Initialize the Exit Manager.
        
        Args:
            time_limit_candles: Number of candles before breakeven is enforced.
            trailing_atr_multiplier: ATR multiplier for the Tranche 3 trailing stop.
        """
        self.time_limit = time_limit_candles
        self.trail_mult = trailing_atr_multiplier
        
    def evaluate_candle_close(self, positions: list[ActivePosition], current_atr: float) -> list[ActivePosition]:
        """Evaluate open positions at the close of a candle.
        
        This method will:
        1. Increment elapsed_candles.
        2. Move stop-loss to breakeven if time limit exceeded and TP1 hasn't been hit.
        3. Ratchet the trailing stop for Tranche 3 (runner) if it's profitable enough.
        
        Args:
            positions: List of currently open ActivePositions.
            current_atr: The latest ATR value.
            
        Returns:
            The list of mutated ActivePositions.
        """
        # Group active positions by parent_trade_id to check TP1 status
        # If tranche 1 is NOT in the list of active positions, it means it hit its TP and was removed.
        active_parents = {}
        for pos in positions:
            if pos.parent_trade_id not in active_parents:
                active_parents[pos.parent_trade_id] = set()
            active_parents[pos.parent_trade_id].add(pos.tranche_id)
            
        for pos in positions:
            pos.elapsed_candles += 1
            
            # 1. Time-Based Breakeven Logic
            # Only tighten if TP1 is still active (meaning we haven't secured partial profits)
            if not pos.is_breakeven and pos.elapsed_candles >= self.time_limit:
                tp1_still_active = 1 in active_parents.get(pos.parent_trade_id, set())
                
                if tp1_still_active:
                    # Move SL to Entry (breakeven)
                    pos.stop_loss_price = pos.entry_price
                    pos.is_breakeven = True
                    
            # 2. Trailing Stop Logic (Tranche 3 only)
            if pos.tranche_id == 3 and current_atr > 0:
                trail_distance = current_atr * self.trail_mult
                pos.trailing_step = trail_distance
                
                if pos.direction == TradeDirection.LONG:
                    new_sl = pos.current_price - trail_distance
                    # Only ratchet up, never down
                    if pos.stop_loss_price is None or new_sl > pos.stop_loss_price:
                        # Only trail if it locks in profit or beats initial SL
                        if new_sl > pos.entry_price:
                            pos.stop_loss_price = new_sl
                            
                elif pos.direction == TradeDirection.SHORT:
                    new_sl = pos.current_price + trail_distance
                    # Only ratchet down, never up
                    if pos.stop_loss_price is None or new_sl < pos.stop_loss_price:
                        # Only trail if it locks in profit or beats initial SL
                        if new_sl < pos.entry_price:
                            pos.stop_loss_price = new_sl
                            
        return positions
