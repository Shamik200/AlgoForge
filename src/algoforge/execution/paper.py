"""Paper Trading Engine — Simulated execution environment.

Models realistic execution with slippage, commissions, and latency.
Processes signals through the risk manager, executes fills, tracks
portfolio state and performance metrics.

Requirements: PAPR-01 to PAPR-06
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from pydantic import BaseModel, Field

from algoforge.core.constants import Direction, Market, Timeframe
from algoforge.core.models import Position, Signal
from algoforge.oms.manager import OrderManager
from algoforge.oms.models import Order, OrderType
from algoforge.oms.store import OrderStore
from algoforge.risk.manager import RiskConfig, RiskManager

logger = structlog.get_logger(__name__)


class FillResult(BaseModel):
    """Result of a simulated order fill."""

    filled: bool = False
    position_id: str = ""
    fill_price: float = 0.0
    slippage: float = 0.0
    commission: float = 0.0
    latency_ms: float = 0.0
    rejection_reason: str = ""


class TradeRecord(BaseModel):
    """Completed trade record for performance tracking."""

    id: str
    symbol: str
    direction: Direction
    strategy: str
    entry_price: float
    exit_price: float
    quantity: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    commission: float
    slippage: float
    bars_held: int = 0


class PortfolioSnapshot(BaseModel):
    """Point-in-time portfolio state."""

    equity: float = 0.0
    cash: float = 0.0
    open_positions: int = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    total_commission: float = 0.0
    max_drawdown_pct: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PaperTradingEngine:
    """Simulated trading execution engine.

    Features:
    - Realistic slippage modeling (PAPR-01)
    - Commission/fee modeling (PAPR-02)
    - Latency simulation (PAPR-03)
    - Market-agnostic (PAPR-04)
    - Integrates with RiskManager for all validations
    - Tracks full portfolio state and trade history

    Usage:
        engine = PaperTradingEngine(
            initial_capital=100_000,
            market=Market.STOCKS_US,
        )
        fill = engine.submit_signal(signal)
        engine.update_prices({"AAPL": 155.0})
        engine.check_exits(current_bar=100)
    """

    # Market-specific fee structures (PAPR-02)
    FEE_STRUCTURES: dict[Market, dict[str, float]] = {
        Market.STOCKS_US: {"commission_per_share": 0.005, "min_commission": 1.0, "tax_rate": 0.0},
        Market.STOCKS_INDIA: {"commission_pct": 0.0003, "stt_pct": 0.001, "gst_pct": 0.18, "min_commission": 20.0},
        Market.CRYPTO: {"maker_fee_pct": 0.0002, "taker_fee_pct": 0.0004, "min_commission": 0.0, "tax_rate": 0.0},
        Market.FOREX: {"spread_pips": 1.5, "commission_per_lot": 3.5, "min_commission": 0.0},
    }

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        market: Market = Market.STOCKS_US,
        slippage_pct: float = 0.0000,
        latency_ms: float = 100.0,
        latency_min_ms: float = 50.0,
        latency_max_ms: float = 200.0,
        latency_enabled: bool = True,
        risk_config: RiskConfig | None = None,
        oms_db_path: str = "data/oms_orders.db",
    ) -> None:
        self._initial_capital = initial_capital
        self._cash = initial_capital
        self._market = market
        self._slippage_pct = slippage_pct
        self._latency_ms = latency_ms
        self._latency_min_ms = latency_min_ms
        self._latency_max_ms = latency_max_ms
        self._latency_enabled = latency_enabled
        self._risk_manager = RiskManager(capital=initial_capital, config=risk_config)
        self._positions: dict[str, Position] = {}
        self._trade_history: list[TradeRecord] = []
        self._peak_equity = initial_capital
        self._current_bar = 0
        self._prices: dict[str, float] = {}
        self._rng = random.Random(42)

        # OMS Integration (Phase 3)
        try:
            from pathlib import Path
            Path(oms_db_path).parent.mkdir(parents=True, exist_ok=True)
            self._oms_store = OrderStore(db_path=oms_db_path)
            self._oms = OrderManager(store=self._oms_store)
            logger.info("oms_initialized", db_path=oms_db_path)
        except Exception as e:
            logger.warning(f"OMS initialization failed, running without audit trail: {e}")
            self._oms = None
            self._oms_store = None

    @property
    def equity(self) -> float:
        """Total equity = cash + locked margin + unrealized pnl."""
        margin_locked = sum(p.entry_price * p.quantity for p in self._positions.values())
        unrealized_pnl = sum(p.unrealized_pnl for p in self._positions.values())
        return self._cash + margin_locked + unrealized_pnl

    @property
    def open_positions(self) -> list[Position]:
        return list(self._positions.values())

    @property
    def trade_history(self) -> list[TradeRecord]:
        return self._trade_history

    @property
    def risk_manager(self) -> RiskManager:
        """Public access to the risk manager for circuit breaker / correlation updates."""
        return self._risk_manager

    def submit_signal(
        self,
        signal: Signal,
        daily_volume: float | None = None,
        conviction: float = 1.0,
        order_book: dict | None = None,
    ) -> FillResult:
        """Submit a signal for paper execution.

        Steps:
        1. Run through RiskManager validation
        2. Apply dynamic order book slippage (Phase 8 Realism)
        3. Calculate commissions
        4. Create position if all checks pass
        """
        # Risk validation (with absolute veto power)
        risk_result = self._risk_manager.validate(
            signal,
            open_positions=self.open_positions,
            daily_volume=daily_volume,
            current_bar=self._current_bar,
            conviction=conviction,
        )

        # Generate correlation ID for OMS tracking
        correlation_id = f"{signal.symbol}-{signal.strategy}-{self._current_bar}-{uuid.uuid4().hex[:6]}"

        if not risk_result.approved:
            # Track rejected order in OMS
            if self._oms:
                oms_order = Order(
                    correlation_id=correlation_id,
                    symbol=signal.symbol,
                    direction=signal.direction.value,
                    order_type=OrderType.MARKET,
                    price=signal.entry_price,
                    quantity=risk_result.position_size or 0.0001,
                )
                submitted = self._oms.submit_order(oms_order)
                if submitted:
                    from algoforge.oms.state_machine import transition
                    from algoforge.oms.models import OrderStatus
                    try:
                        rejected = transition(submitted, OrderStatus.REJECTED)
                        self._oms.store.update_order(rejected)
                    except Exception:
                        pass

            return FillResult(
                filled=False,
                rejection_reason="; ".join(risk_result.rejection_reasons),
            )

        # Submit order to OMS before execution
        if self._oms:
            oms_order = Order(
                correlation_id=correlation_id,
                symbol=signal.symbol,
                direction=signal.direction.value,
                order_type=OrderType.MARKET,
                price=signal.entry_price,
                quantity=risk_result.position_size,
            )
            submitted = self._oms.submit_order(oms_order)
            if submitted is None:
                # Idempotency guard — duplicate order
                return FillResult(
                    filled=False,
                    rejection_reason="OMS: Duplicate order (idempotency guard)",
                )

        # Apply slippage (PAPR-01) - Execution Realism (Phase 8)
        import math
        qty = risk_result.position_size
        
        if order_book and "ask" in order_book and "bid" in order_book and order_book["ask"] > 0:
            if signal.direction == Direction.LONG:
                base_price = order_book["ask"]
                available_qty = order_book.get("ask_qty", float("inf"))
            else:
                base_price = order_book["bid"]
                available_qty = order_book.get("bid_qty", float("inf"))

            tif = getattr(signal, 'time_in_force', TimeInForce.GTC)
            if qty > available_qty:
                if tif == TimeInForce.FOK:
                    return FillResult(
                        filled=False,
                        rejection_reason="FOK order killed: Insufficient liquidity",
                    )
                elif tif == TimeInForce.IOC:
                    # Partial fill: only take what's available
                    qty = available_qty
                    risk_result.position_size = qty

            # Volume-weighted slippage: larger orders = more slippage (eat into book depth)
            depth_penalty = math.sqrt(qty / max(available_qty, 0.0001)) * 0.0005 if available_qty < float("inf") else 0
            if signal.direction == Direction.LONG:
                fill_price = base_price * (1 + depth_penalty)
            else:
                fill_price = base_price * (1 - depth_penalty)
        else:
            # Fallback to static percentage if order book is missing
            slippage = signal.entry_price * self._slippage_pct
            if signal.direction == Direction.LONG:
                fill_price = signal.entry_price + slippage  # Worse fill for longs
            else:
                fill_price = signal.entry_price - slippage  # Worse fill for shorts

        # Simulate latency (PAPR-03)
        actual_latency_ms = self._latency_ms
        if self._latency_enabled:
            actual_latency_ms = self._rng.uniform(self._latency_min_ms, self._latency_max_ms)
            # Price moves during latency — add additional drift proportional to delay
            latency_drift_factor = actual_latency_ms / 1000.0  # Convert to seconds
            # Random micro-movement: up to 0.01% per 100ms of latency
            drift_pct = self._rng.gauss(0, 0.0001) * (actual_latency_ms / 100.0)
            latency_impact = fill_price * drift_pct
            if signal.direction == Direction.LONG:
                fill_price += abs(latency_impact)  # Adverse fill for longs
            else:
                fill_price -= abs(latency_impact)  # Adverse fill for shorts

        # Determine Maker/Taker (Phase 8 Execution Realism)
        is_maker = False
        if hasattr(signal, 'order_type') and signal.order_type == OrderType.LIMIT:
            if hasattr(signal, 'time_in_force') and signal.time_in_force == TimeInForce.GTC:
                is_maker = True

        # Calculate commission (PAPR-02)
        commission = self._calculate_commission(
            fill_price, risk_result.position_size, is_maker=is_maker
        )

        # Check cash available
        position_cost = fill_price * risk_result.position_size + commission
        if position_cost > self._cash:
            # Cancel OMS order on insufficient funds
            if self._oms:
                self._oms.cancel_order(correlation_id)
            return FillResult(
                filled=False,
                rejection_reason=f"Insufficient cash: {self._cash:.2f} < {position_cost:.2f}",
            )

        # Create position
        position_id = str(uuid.uuid4())[:8]
        adjusted = risk_result.adjusted_signal or signal

        position = Position(
            id=position_id,
            symbol=signal.symbol,
            direction=signal.direction,
            entry_price=fill_price,
            quantity=risk_result.position_size,
            stop_loss=adjusted.stop_loss,
            take_profit=adjusted.take_profit,
            strategy=signal.strategy,
            opened_at=datetime.now(timezone.utc),
            current_price=fill_price,
        )

        self._positions[position_id] = position
        self._cash -= position_cost

        # Mark OMS order as filled
        if self._oms:
            self._oms.fill_order(correlation_id)

        logger.info(
            "paper_fill",
            position_id=position_id,
            symbol=signal.symbol,
            direction=signal.direction.value,
            fill_price=round(fill_price, 4),
            quantity=risk_result.position_size,
            commission=round(commission, 2),
            slippage=round(slippage, 4),
            oms_id=correlation_id if self._oms else "n/a",
        )

        return FillResult(
            filled=True,
            position_id=position_id,
            fill_price=round(fill_price, 4),
            slippage=round(slippage, 4),
            commission=round(commission, 2),
            latency_ms=round(actual_latency_ms, 1),
        )

    def update_prices(self, prices: dict[str, float]) -> None:
        """Update current prices and position P&L."""
        self._prices.update(prices)
        for pos in self._positions.values():
            if pos.symbol in prices:
                pos.current_price = prices[pos.symbol]
                if pos.direction == Direction.LONG:
                    pos.unrealized_pnl = (pos.current_price - pos.entry_price) * pos.quantity
                else:
                    pos.unrealized_pnl = (pos.entry_price - pos.current_price) * pos.quantity

        # Track peak equity
        if self.equity > self._peak_equity:
            self._peak_equity = self.equity

    def check_exits(self, current_bar: int = 0) -> list[TradeRecord]:
        """Check all positions for SL/TP hits."""
        self._current_bar = current_bar
        closed: list[TradeRecord] = []
        to_close: list[str] = []

        for pid, pos in self._positions.items():
            price = pos.current_price
            hit_sl = False
            hit_tp = False

            if pos.direction == Direction.LONG:
                hit_sl = price <= pos.stop_loss
                hit_tp = price >= pos.take_profit
            else:
                hit_sl = price >= pos.stop_loss
                hit_tp = price <= pos.take_profit

            if hit_sl or hit_tp:
                exit_price = pos.stop_loss if hit_sl else pos.take_profit
                # Apply slippage on exit
                slippage = exit_price * self._slippage_pct
                if pos.direction == Direction.LONG:
                    exit_price -= slippage  # Worse exit for longs
                else:
                    exit_price += slippage

                commission = self._calculate_commission(exit_price, pos.quantity)

                if pos.direction == Direction.LONG:
                    pnl = (exit_price - pos.entry_price) * pos.quantity - commission
                else:
                    pnl = (pos.entry_price - exit_price) * pos.quantity - commission

                trade = TradeRecord(
                    id=pid,
                    symbol=pos.symbol,
                    direction=pos.direction,
                    strategy=pos.strategy,
                    entry_price=pos.entry_price,
                    exit_price=round(exit_price, 4),
                    quantity=pos.quantity,
                    entry_time=pos.opened_at,
                    exit_time=datetime.now(timezone.utc),
                    pnl=round(pnl, 2),
                    commission=round(commission, 2),
                    slippage=round(slippage, 4),
                )

                self._trade_history.append(trade)
                self._cash += (pos.entry_price * pos.quantity) + pnl
                self._risk_manager.record_trade_result(pnl)
                to_close.append(pid)
                closed.append(trade)

                logger.info(
                    "paper_exit",
                    position_id=pid,
                    symbol=pos.symbol,
                    exit_type="SL" if hit_sl else "TP",
                    pnl=round(pnl, 2),
                )

        for pid in to_close:
            del self._positions[pid]

        return closed

    def _calculate_commission(self, price: float, quantity: float, is_maker: bool = False) -> float:
        """Calculate commission based on market fee structure."""
        fees = self.FEE_STRUCTURES.get(self._market, {})

        if "commission_per_share" in fees:
            # US stocks
            comm = max(quantity * fees["commission_per_share"], fees.get("min_commission", 0))
        elif "commission_pct" in fees or "taker_fee_pct" in fees:
            # India/Crypto
            fee_pct = fees.get("maker_fee_pct", 0) if is_maker else fees.get("taker_fee_pct", fees.get("commission_pct", 0))
            comm = max(price * quantity * fee_pct, fees.get("min_commission", 0))
            if "stt_pct" in fees:
                comm += price * quantity * fees["stt_pct"]
        elif "spread_pips" in fees:
            # Forex
            comm = fees.get("commission_per_lot", 0) * (quantity / 100_000)
        else:
            comm = 0.0

        return comm

    def snapshot(self) -> PortfolioSnapshot:
        """Get current portfolio state."""
        wins = sum(1 for t in self._trade_history if t.pnl > 0)
        losses = sum(1 for t in self._trade_history if t.pnl <= 0)
        total_pnl = sum(t.pnl for t in self._trade_history)
        total_comm = sum(t.commission for t in self._trade_history)
        dd = (self._peak_equity - self.equity) / self._peak_equity if self._peak_equity > 0 else 0

        return PortfolioSnapshot(
            equity=round(self.equity, 2),
            cash=round(self._cash, 2),
            open_positions=len(self._positions),
            total_trades=len(self._trade_history),
            winning_trades=wins,
            losing_trades=losses,
            total_pnl=round(total_pnl, 2),
            total_commission=round(total_comm, 2),
            max_drawdown_pct=round(dd, 4),
        )

    def reset(self) -> None:
        """Reset engine to initial state."""
        self._cash = self._initial_capital
        self._positions.clear()
        self._trade_history.clear()
        self._peak_equity = self._initial_capital
        self._current_bar = 0
        self._prices.clear()
        self._rng = random.Random(42)
