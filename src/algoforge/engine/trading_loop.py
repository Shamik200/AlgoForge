"""Trading Loop — Main background engine that orchestrates universe discovery and live streams.

Extracted from server.py trading_engine_loop(). Connects universe
selection → kline pre-fetch → WebSocket streaming in a cycle.
"""

from __future__ import annotations

from typing import Callable, Awaitable

import asyncio
import structlog

from algoforge.connectors.factory import ConnectorFactory
from algoforge.engine.state import SystemState, log_msg
from algoforge.engine.universe import (
    score_universe,
    select_top_assets,
    prefetch_klines,
)
from algoforge.engine.live_handler import handle_live_tick

logger = structlog.get_logger(__name__)


async def trading_engine_loop(
    state: SystemState,
    broadcast_fn: Callable[[], Awaitable[None]],
) -> None:
    """Main trading engine background loop.

    Cycle:
    1. Fetch universe from exchange REST API
    2. Score and rank assets
    3. Select top-K above dynamic threshold
    4. Pre-fetch historical klines for new assets
    5. Start WebSocket streams for selected assets
    6. Process live ticks until next cycle
    """
    # Create tick handler with bound state and broadcast
    async def on_tick(data: dict) -> None:
        await handle_live_tick(state, data, broadcast_fn)

    # Use the connector initialized by the Orchestrator
    state.connector = state.orchestrator.connector

    while state.is_running:
        try:
            # STEP 1: Universe Construction (REST)
            log_msg(state, "Fetching Live Universe (Top 50 USDT Pairs)...")
            universe = state.connector.fetch_top_n_universe(
                state.discovery_config.universe_size
            )

            # STEP 2: Multi-Factor Scoring
            log_msg(state, f"Running Multi-Factor Scoring on {len(universe)} assets...")
            scores = score_universe(state, universe)

            # STEP 3: Dynamic Top-K Selection
            selected = select_top_assets(state, scores)

            state.scored_assets = scores
            state.selected_assets = [s["symbol"] for s in selected]

            log_msg(
                state,
                f"Selection: {len(selected)} assets active "
                f"(threshold={state.discovery_config.dynamic_threshold}, "
                f"above={len([s for s in scores if s.get('score', 0) >= state.discovery_config.dynamic_threshold])})"
            )

            # STEP 4: Pre-fetch Historical Klines in PARALLEL
            await prefetch_klines(state)

            # STEP 5: Start Async WebSocket Stream
            if state.selected_assets:
                log_msg(
                    state,
                    f"Initiating Live WebSocket Streams for "
                    f"{len(state.selected_assets)} assets..."
                )
                await state.connector.start_streams(state.selected_assets, callback=on_tick)
            else:
                log_msg(state, "No assets passed the dynamic threshold. Waiting for next cycle...")
                await asyncio.sleep(60)

        except Exception as e:
            log_msg(state, f"Critical Engine Error: {str(e)}")
            await asyncio.sleep(10)
