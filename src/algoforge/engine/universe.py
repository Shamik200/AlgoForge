"""Universe Engine — Dynamic asset discovery and scoring.

Extracted from server.py. Implements multi-factor scoring with
persistence bonuses, dynamic threshold selection, and historical
kline pre-fetching.

Inspired by:
- Freqtrade pairlist plugin architecture
- LEAN Universe Selection framework
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import asyncio

import requests
import structlog

from algoforge.core.constants import Timeframe
from algoforge.core.models import OHLCV
from algoforge.engine.state import AssetMemory, SystemState, log_msg

logger = structlog.get_logger(__name__)

# Stablecoins to exclude from universe
STABLECOIN_FRAGMENTS = frozenset(
    ["USDC", "FDUSD", "TUSD", "USD1", "USDD", "BUSD", "DAI", "USDE"]
)


def score_universe(state: SystemState, universe: list[dict]) -> list[dict]:
    """Score all assets using multi-factor model with persistence bonus.

    Factors:
        - Liquidity (30%): 24h volume in millions, capped at 100
        - Volatility (20%): inverted high-low range (prefer moderate)
        - Trend strength (50%): 24h price change percentage

    Persistence modifier: +2 points per consecutive selection cycle (max +10).
    """
    scores = []

    for asset in universe:
        sym = asset["symbol"]

        # Exclude stablecoins
        if any(stable in sym for stable in STABLECOIN_FRAGMENTS):
            continue

        # Real Factors
        liquidity = asset["volume"] / 1_000_000  # in millions
        vol_proxy = (asset["high"] - asset["low"]) / asset["last_price"] * 100
        trend_strength = asset["price_change_pct"]

        base_score = (
            (0.30 * min(liquidity, 100)) +
            (0.20 * (100 - min(vol_proxy * 10, 100))) +
            (0.50 * (trend_strength + 50))
        )

        # Persistence Modifier
        if sym not in state.asset_memory:
            state.asset_memory[sym] = AssetMemory(symbol=sym)
        mem = state.asset_memory[sym]

        final_score = round(base_score + min(mem.cycles_selected * 2.0, 10.0), 2)
        trend_str = (
            "UP" if final_score > mem.last_score + 1
            else "DOWN" if final_score < mem.last_score - 1
            else "FLAT"
        )
        mem.score_trend = trend_str
        mem.last_score = final_score

        scores.append({
            "symbol": sym,
            "score": final_score,
            "trend": trend_str,
            "persistence": f"{mem.cycles_selected} cycles",
            "status": "EVALUATING"
        })

    return scores


def select_top_assets(state: SystemState, scores: list[dict]) -> list[dict]:
    """Select top-K assets above dynamic threshold.

    Updates asset memory persistence counters.
    """
    scores.sort(key=lambda x: x["score"], reverse=True)

    above_threshold = [
        s for s in scores
        if s["score"] >= state.discovery_config.dynamic_threshold
    ]
    selected = above_threshold[:state.discovery_config.max_active_assets]

    for s in scores:
        mem = state.asset_memory[s["symbol"]]
        if s in selected:
            mem.cycles_selected += 1
            s["status"] = "ACTIVE"
        else:
            mem.cycles_selected = max(0, mem.cycles_selected - 1)

    return selected


def fetch_historical_klines(symbol: str) -> list[OHLCV]:
    """Fetch 250 historical 1m klines from Binance REST API."""
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=250"
        resp = requests.get(url, timeout=8)
        data = resp.json()
        return [OHLCV(
            symbol=symbol,
            timeframe=Timeframe.M1,
            timestamp=datetime.fromtimestamp(r[0] / 1000, tz=timezone.utc),
            open=float(r[1]),
            high=float(r[2]),
            low=float(r[3]),
            close=float(r[4]),
            volume=float(r[5])
        ) for r in data]
    except Exception as e:
        logger.error(f"Failed to fetch historical klines for {symbol}: {e}")
        return []


async def prefetch_klines(state: SystemState) -> None:
    """Pre-fetch historical klines in parallel for newly selected assets."""
    symbols_to_fetch = [
        sym for sym in state.selected_assets
        if sym not in state.kline_buffers
    ]
    if not symbols_to_fetch:
        return

    log_msg(state, f"Pre-fetching {len(symbols_to_fetch)} kline histories in parallel...")
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=len(symbols_to_fetch)) as pool:
        results = await loop.run_in_executor(
            None,
            lambda: {sym: fetch_historical_klines(sym) for sym in symbols_to_fetch}
        )
    for sym, candles in results.items():
        state.kline_buffers[sym] = candles
    log_msg(
        state,
        f"Kline pre-fetch complete: {sum(len(v) for v in results.values())} candles loaded."
    )
