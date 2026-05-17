"""Paper-Live Reconciliation Engine (Phase 13).

Compares live trades against their paper shadow equivalents to detect drift.
Alerts if divergence exceeds safe thresholds, and manages gradual capital scaling.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from algoforge.oms.models import Order

logger = logging.getLogger(__name__)


@dataclass
class DriftReport:
    """Report comparing a live order against its paper shadow."""
    symbol: str
    live_order_id: str
    paper_order_id: str
    
    # Timing Drift
    live_fill_time: datetime
    paper_fill_time: datetime
    timing_drift_ms: int
    
    # Price Drift (Slippage)
    live_avg_price: float
    paper_avg_price: float
    price_drift_pct: float
    
    # Quantity Drift (Partial Fills)
    live_filled_qty: float
    paper_filled_qty: float
    qty_drift_pct: float
    
    # System Alert Flag
    is_divergent: bool
    alert_reasons: List[str]


class ReconciliationEngine:
    """Monitors live execution vs paper shadow mode."""

    def __init__(self, max_price_drift_pct: float = 0.005, max_timing_drift_ms: int = 2000):
        """
        Args:
            max_price_drift_pct: Max allowed price slippage drift vs paper (e.g., 0.005 = 0.5%).
            max_timing_drift_ms: Max allowed execution latency drift vs paper in ms.
        """
        self.max_price_drift_pct = max_price_drift_pct
        self.max_timing_drift_ms = max_timing_drift_ms
        self.reports: List[DriftReport] = []
        
        # Gradual Capital Scaling Configuration
        self.scaling_stages = [0.10, 0.25, 0.50, 1.00]
        self.current_stage_idx = 0
        self.successful_trades_in_stage = 0
        self.trades_needed_to_upgrade = 20  # Require 20 divergence-free trades to scale up

    @property
    def current_capital_scale(self) -> float:
        """Returns the current capital allocation multiplier (10% -> 100%)."""
        return self.scaling_stages[self.current_stage_idx]

    def reconcile(self, live_order: Order, paper_order: Order) -> DriftReport | None:
        """Compare a completed live order to its paper equivalent."""
        if live_order.status not in ["FILLED", "PARTIALLY_FILLED"]:
            return None
            
        if not live_order.filled_at or not paper_order.filled_at:
            return None
            
        timing_drift = int(abs((live_order.filled_at - paper_order.filled_at).total_seconds() * 1000))
        
        # Compare prices
        if paper_order.average_price > 0:
            price_drift = abs(live_order.average_price - paper_order.average_price) / paper_order.average_price
        else:
            price_drift = 0.0
            
        # Compare filled quantities
        if paper_order.filled > 0:
            qty_drift = abs(live_order.filled - paper_order.filled) / paper_order.filled
        else:
            qty_drift = 0.0
            
        alert_reasons = []
        is_divergent = False
        
        if price_drift > self.max_price_drift_pct:
            is_divergent = True
            alert_reasons.append(f"Price drift {price_drift:.3%} exceeds {self.max_price_drift_pct:.3%}")
            
        if timing_drift > self.max_timing_drift_ms:
            is_divergent = True
            alert_reasons.append(f"Timing drift {timing_drift}ms exceeds {self.max_timing_drift_ms}ms")
            
        if qty_drift > 0.05:  # Tolerance for partial fills
            is_divergent = True
            alert_reasons.append(f"Quantity drift {qty_drift:.3%} exceeds 5%")
            
        report = DriftReport(
            symbol=live_order.symbol,
            live_order_id=live_order.id,
            paper_order_id=paper_order.id,
            live_fill_time=live_order.filled_at,
            paper_fill_time=paper_order.filled_at,
            timing_drift_ms=timing_drift,
            live_avg_price=live_order.average_price,
            paper_avg_price=paper_order.average_price,
            price_drift_pct=price_drift,
            live_filled_qty=live_order.filled,
            paper_filled_qty=paper_order.filled,
            qty_drift_pct=qty_drift,
            is_divergent=is_divergent,
            alert_reasons=alert_reasons
        )
        
        self.reports.append(report)
        self._process_scaling(report)
        
        if is_divergent:
            logger.warning(
                f"[DRIFT DETECTED] {live_order.symbol}: " + " | ".join(alert_reasons)
            )
            
        return report

    def _process_scaling(self, report: DriftReport) -> None:
        """Adjust gradual capital scaling based on drift history."""
        if report.is_divergent:
            # Penalize: Reset counter, potentially downgrade stage
            logger.warning("Divergence detected. Resetting capital scale progress.")
            self.successful_trades_in_stage = 0
            # If divergence is extreme, we could decrement current_stage_idx
        else:
            self.successful_trades_in_stage += 1
            if self.successful_trades_in_stage >= self.trades_needed_to_upgrade:
                self._upgrade_scale()

    def _upgrade_scale(self) -> None:
        """Upgrade the capital scaling to the next level."""
        if self.current_stage_idx < len(self.scaling_stages) - 1:
            self.current_stage_idx += 1
            self.successful_trades_in_stage = 0
            new_scale = self.scaling_stages[self.current_stage_idx]
            logger.info(f"🚀 Capital Scaling Upgraded: Now running at {new_scale * 100}% live capital.")
