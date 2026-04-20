"""Main Risk Engine orchestrator."""

from algoforge.risk.correlation import CorrelationMatrix
from algoforge.risk.limits import (
    check_account_limits,
    check_portfolio_limits,
    check_trade_limits,
)
from algoforge.risk.models import (
    AccountState,
    ActivePosition,
    RiskEvaluation,
    TradeDirection,
    TradeLedger,
)
from algoforge.risk.sizing import calculate_kelly_fraction, calculate_position_size


class RiskEngine:
    """The absolute authority on capital preservation.
    
    Evaluates proposed trades against sizing rules, account limits,
    portfolio concentration, and liquidity constraints.
    """

    def __init__(self, correlation_matrix: CorrelationMatrix | None = None) -> None:
        """Initialize Risk Engine.
        
        Args:
            correlation_matrix: Cached correlation matrix. Will use an empty one if not provided.
        """
        self.correlation_matrix = correlation_matrix or CorrelationMatrix()

    def evaluate_trade(
        self,
        symbol: str,
        sector: str,
        direction: TradeDirection,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        session_open_price: float,
        current_price: float,
        daily_volume: float,
        account: AccountState,
        ledger: TradeLedger,
        active_positions: list[ActivePosition]
    ) -> RiskEvaluation:
        """Evaluate a proposed trade for risk approval and sizing.
        
        Args:
            symbol: Ticker symbol.
            sector: Sector of the asset.
            direction: Trade direction (LONG/SHORT).
            entry_price: Proposed entry price.
            stop_loss: Proposed stop loss.
            take_profit: Proposed take profit.
            session_open_price: Today's open price (for circuit breakers).
            current_price: Current market price.
            daily_volume: Average Daily Volume or recent volume.
            account: Current global account state.
            ledger: Trade ledger for Kelly calculation.
            active_positions: List of currently open positions.
            
        Returns:
            RiskEvaluation detailing approval, size, and rejection reasons.
        """
        # 1. Global Account Limits (Immediate Vetoes)
        acc_veto = check_account_limits(account)
        if acc_veto:
            return RiskEvaluation(is_approved=False, rejection_reason=acc_veto)
            
        # 2. Position Sizing (Determine hypothetical size)
        risk_pct = calculate_kelly_fraction(ledger)
        if risk_pct <= 0.0:
            return RiskEvaluation(is_approved=False, rejection_reason="zero_risk_pct_calculated")
            
        alloc_capital = calculate_position_size(account, risk_pct, entry_price, stop_loss)
        if alloc_capital <= 0.0:
            return RiskEvaluation(is_approved=False, rejection_reason="zero_capital_allocated")
            
        # 3. Portfolio Limits
        port_veto = check_portfolio_limits(
            candidate_symbol=symbol,
            candidate_sector=sector,
            candidate_direction=direction,
            candidate_size=alloc_capital,
            active_positions=active_positions,
            account=account,
            correlation_matrix=self.correlation_matrix
        )
        if port_veto:
            return RiskEvaluation(is_approved=False, rejection_reason=port_veto)
            
        # 4. Trade Micro Limits
        trade_veto = check_trade_limits(
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            session_open_price=session_open_price,
            current_price=current_price,
            daily_volume=daily_volume,
            candidate_size=alloc_capital
        )
        if trade_veto:
            return RiskEvaluation(is_approved=False, rejection_reason=trade_veto)
            
        # All checks passed
        return RiskEvaluation(
            is_approved=True,
            allocated_capital=alloc_capital,
            risk_pct=risk_pct,
            metadata={"source": "kelly" if ledger.total_trades >= 30 else "fixed_fallback"}
        )
