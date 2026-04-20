"""Position sizing models (Kelly Criterion and Fixed Fractional)."""

from algoforge.risk.models import AccountState, TradeLedger


def calculate_kelly_fraction(
    ledger: TradeLedger,
    kelly_multiplier: float = 0.5,
    max_risk_pct: float = 0.02
) -> float:
    """Calculate the Kelly Criterion risk percentage.
    
    Formula: Kelly % = W - ((1 - W) / R)
    where W is win rate, R is payoff ratio.
    
    Args:
        ledger: The TradeLedger with historical performance.
        kelly_multiplier: Multiplier to apply to full Kelly (e.g., 0.5 for Half-Kelly).
        max_risk_pct: Hard cap on the risk percentage allowed.
        
    Returns:
        Risk percentage (e.g. 0.015 for 1.5% risk).
    """
    if ledger.total_trades < 30:
        # Not enough data for a stable Kelly. Fallback to fixed fractional.
        return min(0.01, max_risk_pct)
        
    w = ledger.win_rate
    r = ledger.payoff_ratio
    
    if r <= 0.0 or w <= 0.0:
        return 0.0
        
    full_kelly = w - ((1.0 - w) / r)
    
    # Can't risk negative amounts. If edge is negative, Kelly is negative.
    if full_kelly <= 0.0:
        return 0.0
        
    fractional_kelly = full_kelly * kelly_multiplier
    return min(fractional_kelly, max_risk_pct)


def calculate_position_size(
    account: AccountState,
    risk_pct: float,
    entry_price: float,
    stop_loss_price: float,
    max_position_pct: float = 0.10
) -> float:
    """Calculate the exact capital allocation for a trade.
    
    Risk Amount = Account Equity * risk_pct
    Trade Risk % = abs(Entry - SL) / Entry
    Position Size = Risk Amount / Trade Risk %
    
    Args:
        account: The current AccountState.
        risk_pct: The risk percentage calculated (e.g. from Kelly).
        entry_price: Planned entry price.
        stop_loss_price: Planned stop loss price.
        max_position_pct: Hard cap on the total position size as a % of equity.
        
    Returns:
        Dollar value of the capital to allocate to the trade.
    """
    if risk_pct <= 0.0 or entry_price <= 0.0 or stop_loss_price <= 0.0:
        return 0.0
        
    if entry_price == stop_loss_price:
        return 0.0
        
    risk_amount = account.current_equity * risk_pct
    trade_risk_pct = abs(entry_price - stop_loss_price) / entry_price
    
    if trade_risk_pct <= 0.0:
        return 0.0
        
    ideal_position_size = risk_amount / trade_risk_pct
    
    # Cap position size
    max_position_size = account.current_equity * max_position_pct
    
    return min(ideal_position_size, max_position_size)
