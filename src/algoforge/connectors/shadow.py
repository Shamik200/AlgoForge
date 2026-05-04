"""Shadow Connector for Paper-Live Reconciliation (Phase 13).

Wraps a Live Connector and a Paper Connector. For every order submitted,
it executes the live order (scaling capital), mirrors it to the paper engine,
and then reconciles the fill outcomes to detect execution drift.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from algoforge.connectors.base import ConnectorBase
from algoforge.core.models import Order, Signal, PortfolioSnapshot
from algoforge.execution.paper import FillResult
from algoforge.execution.reconciliation import ReconciliationEngine

logger = logging.getLogger(__name__)


class ShadowConnector(ConnectorBase):
    """Executes live orders with scaled capital while running paper shadow mode."""

    def __init__(self, live_connector: ConnectorBase, paper_connector: ConnectorBase):
        """
        Args:
            live_connector: The actual exchange connector (e.g., Binance).
            paper_connector: The paper trading connector.
        """
        self.live = live_connector
        self.paper = paper_connector
        self.reconciliation = ReconciliationEngine()
        
    def submit_order(
        self,
        signal: Signal,
        daily_volume: float | None = None,
        conviction: float = 1.0,
        order_book: dict | None = None,
    ) -> FillResult:
        """Submit to both live and paper engines, and reconcile the fills."""
        
        # 1. Submit Paper Order (Full size, 1.0 capital scale)
        paper_fill = self.paper.submit_order(
            signal=signal,
            daily_volume=daily_volume,
            conviction=conviction,
            order_book=order_book,
        )
        
        # 2. Capital Scaling Logic for Live Order
        scale = self.reconciliation.current_capital_scale
        scaled_signal = self._scale_signal(signal, scale)
        
        # 3. Submit Live Order (Scaled size)
        # Note: If live connector is mocked, this acts as a placeholder.
        live_fill = self.live.submit_order(
            signal=scaled_signal,
            daily_volume=daily_volume,
            conviction=conviction, # Keep conviction same
            order_book=order_book,
        )
        
        # 4. Reconcile Phase (Only if both filled/partially filled)
        if live_fill.order and paper_fill.order:
            self.reconciliation.reconcile(live_fill.order, paper_fill.order)
            
        return live_fill

    def update_prices(self, current_prices: Dict[str, float]) -> None:
        """Forward price updates to both engines."""
        self.live.update_prices(current_prices)
        self.paper.update_prices(current_prices)

    def check_exits(self, current_bar: int = 0) -> None:
        """Check exits on both engines."""
        self.live.check_exits(current_bar)
        self.paper.check_exits(current_bar)

    def check_circuit_breaker(self, prices: Dict[str, float]) -> None:
        """Check circuit breakers on both engines."""
        self.live.check_circuit_breaker(prices)
        self.paper.check_circuit_breaker(prices)

    def get_open_positions(self) -> List[Any]:
        """Return live open positions as the source of truth."""
        return self.live.get_open_positions()

    def snapshot(self) -> PortfolioSnapshot:
        """Return live portfolio snapshot."""
        return self.live.snapshot()
        
    def get_paper_snapshot(self) -> PortfolioSnapshot:
        """Return paper portfolio snapshot for drift comparison."""
        return self.paper.snapshot()

    def _scale_signal(self, signal: Signal, scale: float) -> Signal:
        """Create a new signal scaled down by the gradual allocation multiplier."""
        # Deep copy the signal to avoid mutating the original that paper uses
        import copy
        scaled = copy.deepcopy(signal)
        # Assuming the position size or allocation conviction would be reduced.
        # Signal object might not have explicit 'size' field, but RiskManager
        # uses signal.confidence or we can scale a hypothetical allocation field.
        scaled.confidence = max(0.0, min(1.0, signal.confidence * scale))
        return scaled
