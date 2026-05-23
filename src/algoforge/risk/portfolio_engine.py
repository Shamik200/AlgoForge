"""Portfolio Engine — Performs pre-trade portfolio optimization, Pearson correlation filtering, and cluster exposure capping.
"""

from __future__ import annotations

import numpy as np
import structlog
from typing import Any

logger = structlog.get_logger(__name__)


class PortfolioEngine:
    """Pre-trade risk allocator and portfolio manager.

    Checks:
    - Pearson correlation with existing positions
    - Sector / asset clustering exposure caps (max 25% exposure per cluster)
    - Drawdown limits & hard vetos
    """

    def __init__(
        self,
        max_correlation: float = 0.70,
        max_cluster_exposure_pct: float = 0.25,
        max_portfolio_drawdown_pct: float = 0.10,
    ) -> None:
        self.max_correlation = max_correlation
        self.max_cluster_exposure_pct = max_cluster_exposure_pct
        self.max_portfolio_drawdown_pct = max_portfolio_drawdown_pct
        logger.info(
            "portfolio_engine.initialized",
            max_correlation=max_correlation,
            max_cluster_exposure_pct=max_cluster_exposure_pct,
            max_portfolio_drawdown_pct=max_portfolio_drawdown_pct,
        )

    def evaluate_pre_trade(
        self,
        symbol: str,
        open_positions: list[dict[str, Any]],
        historical_returns: dict[str, list[float]],
        portfolio_equity: float,
        proposed_size_usd: float,
        current_drawdown_pct: float,
    ) -> tuple[bool, str]:
        """Evaluates whether to permit or VETO a proposed trade.

        Returns:
            (is_approved: bool, reason: str)
        """
        # 1. Hard Drawdown Veto Check
        if current_drawdown_pct >= self.max_portfolio_drawdown_pct:
            logger.warn(
                "portfolio_engine.veto.drawdown_breach",
                symbol=symbol,
                drawdown=current_drawdown_pct,
                limit=self.max_portfolio_drawdown_pct,
            )
            return False, f"VETO: Portfolio drawdown {current_drawdown_pct:.1%} exceeds limit of {self.max_portfolio_drawdown_pct:.1%}"

        # 2. Sector / Clustering Exposure Cap (e.g. max 25% of equity in correlated assets)
        # Define mock/heuristic asset clusters for common trading universe
        # e.g., Layer 1 tokens (BTC, ETH, SOL, ADA, DOT), DeFi (UNI, AAVE), Memes (DOGE, SHIB)
        cluster_map = {
            "BTC": "l1", "ETH": "l1", "SOL": "l1", "ADA": "l1", "DOT": "l1", "AVAX": "l1",
            "DOGE": "meme", "SHIB": "meme", "PEPE": "meme", "WIF": "meme",
            "UNI": "defi", "AAVE": "defi", "LINK": "defi", "MKR": "defi"
        }
        
        # Determine base coin symbol (e.g. BTC from BTC/USDT or BTCUSDT)
        base_symbol = symbol.split("/")[0].split("USDT")[0].upper()
        proposed_cluster = cluster_map.get(base_symbol, "other")

        # Sum existing exposure in this cluster
        existing_cluster_exposure = 0.0
        for pos in open_positions:
            pos_symbol = pos.get("symbol", "").split("/")[0].split("USDT")[0].upper()
            pos_cluster = cluster_map.get(pos_symbol, "other")
            if pos_cluster == proposed_cluster:
                existing_cluster_exposure += float(pos.get("quantity", 0.0)) * float(pos.get("entry_price", 0.0))

        total_proposed_cluster_exposure = existing_cluster_exposure + proposed_size_usd
        cluster_ratio = total_proposed_cluster_exposure / portfolio_equity

        if proposed_cluster != "other" and cluster_ratio > self.max_cluster_exposure_pct:
            logger.warn(
                "portfolio_engine.veto.cluster_exposure_breach",
                symbol=symbol,
                cluster=proposed_cluster,
                ratio=cluster_ratio,
                limit=self.max_cluster_exposure_pct,
            )
            return False, f"VETO: Correlation cluster '{proposed_cluster}' exposure {cluster_ratio:.1%} exceeds limit of {self.max_cluster_exposure_pct:.1%}"

        # 3. Pearson Correlation Veto Check
        # Check returns correlation against currently open position returns
        if symbol in historical_returns and len(historical_returns[symbol]) >= 10:
            proposed_ret = historical_returns[symbol]
            for pos in open_positions:
                pos_sym = pos.get("symbol", "")
                if pos_sym != symbol and pos_sym in historical_returns:
                    pos_ret = historical_returns[pos_sym]
                    # Align returns array lengths
                    min_len = min(len(proposed_ret), len(pos_ret))
                    if min_len >= 10:
                        corr = np.corrcoef(proposed_ret[-min_len:], pos_ret[-min_len:])[0, 1]
                        if not np.isnan(corr) and corr > self.max_correlation:
                            logger.warn(
                                "portfolio_engine.veto.correlation_too_high",
                                symbol=symbol,
                                versus=pos_sym,
                                correlation=corr,
                                limit=self.max_correlation,
                            )
                            return False, f"VETO: High Pearson correlation ({corr:.2f}) with open position {pos_sym}"

        logger.info("portfolio_engine.approved", symbol=symbol, proposed_size=proposed_size_usd)
        return True, "Approved"
