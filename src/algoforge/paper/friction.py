"""Friction modeling for realistic execution simulation."""

import math
import random

from algoforge.paper.config import AssetClass, COMMISSION_SCHEDULES, PaperTradingConfig
from algoforge.oms.models import OrderType


def calculate_commissions(
    asset_class: AssetClass,
    shares: float,
    price: float,
    is_sell: bool = False
) -> float:
    """Calculate realistic commission and tax fees based on asset class.

    Args:
        asset_class: The asset class from config.
        shares: Number of shares/contracts traded.
        price: Price per share.
        is_sell: Whether this is a sell order (some taxes like STT only apply on sell).

    Returns:
        The total commission cost in fiat.
    """
    schedule = COMMISSION_SCHEDULES.get(asset_class)
    if not schedule:
        return 0.0

    notional = shares * price
    model = schedule.get("model")

    if model == "per_share":
        rate = schedule.get("rate", 0.0)
        min_fee = schedule.get("minimum", 0.0)
        return max(min_fee, shares * rate)

    elif model == "percentage":
        if asset_class == AssetClass.INDIAN_STOCKS:
            brokerage = notional * schedule.get("brokerage_pct", 0.0)
            gst = brokerage * schedule.get("gst_pct", 0.0)
            stt = (notional * schedule.get("stt_pct", 0.0)) if is_sell else 0.0
            return brokerage + gst + stt
        
        elif asset_class == AssetClass.CRYPTO:
            # Assume taker fee for simplicity in simulation
            taker = schedule.get("taker_pct", 0.0)
            return notional * taker

    return 0.0


def simulate_latency_drift(config: PaperTradingConfig, base_price: float, is_buy: bool) -> tuple[float, float]:
    """Simulate random network latency and adverse price drift.

    Args:
        config: PaperTradingConfig with latency parameters.
        base_price: The market price at the moment the signal fired.
        is_buy: Whether the order is a BUY.

    Returns:
        Tuple of (new_price_after_drift, latency_cost_fiat).
    """
    # Simulate jitter
    latency_ms = random.randint(config.latency_min_ms, config.latency_max_ms)
    
    # We assume a tiny bit of adverse drift proportional to the latency
    # This models high-frequency traders picking off the order
    drift_factor = (latency_ms / 1000.0) * config.adverse_drift_pct
    
    if is_buy:
        drifted_price = base_price * (1.0 + drift_factor)
    else:
        drifted_price = base_price * (1.0 - drift_factor)
        
    return drifted_price, abs(drifted_price - base_price)


def simulate_slippage(config: PaperTradingConfig, price: float, is_buy: bool, order_type: OrderType) -> tuple[float, float]:
    """Simulate order slippage (adverse execution).

    LIMIT orders do not experience traditional market slippage, only MARKET orders do.

    Args:
        config: PaperTradingConfig.
        price: Price before slippage.
        is_buy: Whether order is BUY.
        order_type: LIMIT or MARKET.

    Returns:
        Tuple of (slipped_price, slippage_cost_fiat).
    """
    if order_type == OrderType.LIMIT:
        return price, 0.0

    slip = price * config.slippage_pct
    
    if is_buy:
        slipped_price = price + slip
    else:
        slipped_price = price - slip
        
    return slipped_price, slip


def calculate_market_impact(config: PaperTradingConfig, shares: float, price: float, is_buy: bool) -> tuple[float, float]:
    """Simulate temporary market impact for large orders using square root model.

    Impact = coeff * sigma * sqrt(OrderSize / ADV)
    We simplify sigma (volatility) into the coefficient for simulation.

    Args:
        config: PaperTradingConfig.
        shares: Number of shares to trade.
        price: Current price.
        is_buy: Whether order is BUY.

    Returns:
        Tuple of (impacted_price, impact_cost_fiat).
    """
    ratio = shares / max(1.0, config.avg_daily_volume)
    
    if ratio < 0.001:
        # Negligible impact for very small orders
        return price, 0.0
        
    impact_pct = config.impact_coefficient * math.sqrt(ratio)
    impact_amount = price * impact_pct
    
    if is_buy:
        impacted_price = price + impact_amount
    else:
        impacted_price = price - impact_amount
        
    return impacted_price, impact_amount
