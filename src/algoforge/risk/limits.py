"""Hard limits and veto rules for the Risk Management Engine."""

from algoforge.risk.correlation import CorrelationMatrix
from algoforge.risk.models import AccountState, ActivePosition, TradeDirection


def check_account_limits(
    account: AccountState,
    max_daily_loss_pct: float = 0.05,
    max_drawdown_pct: float = 0.20,
    max_consecutive_losses: int = 5
) -> str | None:
    """Check global account killswitches.
    
    Returns:
        Rejection reason string if a limit is breached, otherwise None.
    """
    if account.current_equity <= 0:
        return "account_blown"
        
    # Check Drawdown
    if account.drawdown_pct >= max_drawdown_pct:
        return f"max_drawdown_exceeded_{account.drawdown_pct:.2f}"
        
    # Check Daily Loss
    daily_loss_pct = -account.daily_pnl / account.current_equity if account.daily_pnl < 0 else 0.0
    if daily_loss_pct >= max_daily_loss_pct:
        return f"max_daily_loss_exceeded_{daily_loss_pct:.2f}"
        
    # Check Consecutive Losses (Cooldown)
    if account.consecutive_losses >= max_consecutive_losses:
        return f"cooldown_active_{account.consecutive_losses}_losses"
        
    return None


def check_portfolio_limits(
    candidate_symbol: str,
    candidate_sector: str,
    candidate_direction: TradeDirection,
    candidate_size: float,
    active_positions: list[ActivePosition],
    account: AccountState,
    correlation_matrix: CorrelationMatrix,
    max_open_positions: int = 10,
    max_sector_exposure_pct: float = 0.25,
    max_directional_exposure_pct: float = 0.60,
    max_correlation: float = 0.70
) -> str | None:
    """Check portfolio concentration and correlation limits.
    
    Returns:
        Rejection reason string if a limit is breached, otherwise None.
    """
    if len(active_positions) >= max_open_positions:
        return f"max_open_positions_exceeded_{max_open_positions}"
        
    # Check if already in this symbol
    for pos in active_positions:
        if pos.symbol == candidate_symbol:
            return f"already_in_position_{candidate_symbol}"
            
    # Check Sector Exposure
    sector_exposure = candidate_size
    for pos in active_positions:
        if pos.sector == candidate_sector:
            sector_exposure += pos.position_size_value
            
    if sector_exposure / account.current_equity > max_sector_exposure_pct:
        return f"sector_limit_exceeded_{candidate_sector}"
        
    # Check Directional Exposure (Net)
    net_exposure = candidate_size if candidate_direction == TradeDirection.LONG else -candidate_size
    for pos in active_positions:
        if pos.direction == TradeDirection.LONG:
            net_exposure += pos.position_size_value
        else:
            net_exposure -= pos.position_size_value
            
    if abs(net_exposure) / account.current_equity > max_directional_exposure_pct:
        return f"directional_limit_exceeded"
        
    # Check Correlation
    for pos in active_positions:
        # We only care about high correlation if we are trading in the same direction.
        # If trading opposite directions, highly correlated assets are a hedge, not a risk multiplier.
        # Wait, if correlation is highly negative, taking SAME direction is a hedge. 
        # If correlation is highly positive, taking SAME direction is risk multiplier.
        corr = correlation_matrix.get_correlation(candidate_symbol, pos.symbol)
        
        if candidate_direction == pos.direction:
            if corr > max_correlation:
                return f"correlation_limit_exceeded_with_{pos.symbol}"
        else:
            if corr < -max_correlation:
                return f"negative_correlation_limit_exceeded_with_{pos.symbol}"
                
    return None


def check_trade_limits(
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    session_open_price: float,
    current_price: float,
    daily_volume: float,
    candidate_size: float,
    min_rr_ratio: float = 2.0,
    max_session_drop_pct: float = 0.05,
    max_adv_pct: float = 0.01
) -> str | None:
    """Check micro trade limits like circuit breakers and liquidity.
    
    Returns:
        Rejection reason string if a limit is breached, otherwise None.
    """
    if entry_price <= 0 or stop_loss <= 0 or current_price <= 0:
        return "invalid_prices"
        
    # Circuit Breaker (Symbol specific drop from open)
    if session_open_price > 0:
        session_drop = (current_price - session_open_price) / session_open_price
        if session_drop <= -max_session_drop_pct:
            return "circuit_breaker_halt"
            
    # Reward to Risk Ratio
    risk = abs(entry_price - stop_loss)
    reward = abs(take_profit - entry_price)
    
    if risk == 0:
        return "zero_risk_invalid_sl"
        
    rr_ratio = reward / risk
    if rr_ratio < min_rr_ratio:
        return f"insufficient_rr_{rr_ratio:.2f}"
        
    # Liquidity Check (Position size as % of Average Daily Volume)
    if daily_volume > 0:
        shares = candidate_size / entry_price
        if shares / daily_volume > max_adv_pct:
            return "insufficient_liquidity"
            
    return None
