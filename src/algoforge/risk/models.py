"""Core data models for the Risk Management Engine."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TradeDirection(str, Enum):
    """Direction of a trade."""
    LONG = "long"
    SHORT = "short"


class TradeRecord(BaseModel):
    """A record of a closed trade for the Trade Ledger."""
    
    symbol: str
    direction: TradeDirection
    entry_price: float
    exit_price: float
    pnl_amount: float
    pnl_percent: float
    closed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TradeLedger(BaseModel):
    """Ledger tracking historical performance to calculate Kelly criterion."""
    
    records: list[TradeRecord] = Field(default_factory=list)
    
    @property
    def total_trades(self) -> int:
        return len(self.records)
        
    @property
    def win_rate(self) -> float:
        """Percentage of trades that were profitable."""
        if not self.records:
            return 0.0
        winners = sum(1 for r in self.records if r.pnl_amount > 0)
        return winners / len(self.records)
        
    @property
    def payoff_ratio(self) -> float:
        """Ratio of average win to average loss."""
        winners = [r.pnl_amount for r in self.records if r.pnl_amount > 0]
        losers = [abs(r.pnl_amount) for r in self.records if r.pnl_amount < 0]
        
        avg_win = sum(winners) / len(winners) if winners else 0.0
        avg_loss = sum(losers) / len(losers) if losers else 0.0
        
        if avg_loss == 0.0:
            return float('inf') if avg_win > 0 else 0.0
            
        return avg_win / avg_loss


class AccountState(BaseModel):
    """Abstract representation of global account state."""
    
    current_equity: float = Field(..., gt=0)
    peak_equity: float = Field(..., gt=0)
    daily_pnl: float = 0.0
    weekly_pnl: float = 0.0
    consecutive_losses: int = 0
    
    @property
    def drawdown_pct(self) -> float:
        """Current drawdown from peak equity as a positive percentage."""
        if self.peak_equity <= 0:
            return 0.0
        dd = (self.peak_equity - self.current_equity) / self.peak_equity
        return max(0.0, dd)


class ActivePosition(BaseModel):
    """A currently open position."""
    
    symbol: str
    direction: TradeDirection
    sector: str = "unknown"
    entry_price: float
    current_price: float
    position_size_value: float = Field(..., gt=0)
    
    # Phase 12: Multi-Target Exits
    parent_trade_id: str = "legacy"
    tranche_id: int = 1
    elapsed_candles: int = 0
    is_breakeven: bool = False
    trailing_step: float | None = None
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    
    @property
    def pnl_pct(self) -> float:
        if self.direction == TradeDirection.LONG:
            return (self.current_price - self.entry_price) / self.entry_price
        else:
            return (self.entry_price - self.current_price) / self.entry_price


class RiskEvaluation(BaseModel):
    """Result of a risk engine evaluation."""
    
    is_approved: bool
    rejection_reason: str | None = None
    allocated_capital: float = 0.0
    risk_pct: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
