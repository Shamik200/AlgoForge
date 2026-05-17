"""Trading Loop — Main background engine that orchestrates universe discovery and live streams.

Extracted from server.py trading_engine_loop(). Connects universe
selection → kline pre-fetch → WebSocket streaming in a cycle.
"""

from __future__ import annotations

from typing import Callable, Awaitable

import asyncio
import time
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

    try:
        # Use the connector initialized by the Orchestrator
        state.connector = state.orchestrator.connector
        logger.info("trading_loop_started", connector_type=type(state.connector).__name__)
    except Exception as e:
        import traceback
        logger.error("trading_loop_init_failed", error=str(e), traceback=traceback.format_exc())
        log_msg(state, f"❌ Trading loop failed to initialize: {e}")
        return

    while state.is_running:
        try:
            # STEP 1: Universe Construction (REST)
            # CRITICAL: run in thread pool to avoid blocking the event loop
            t0 = time.monotonic()
            log_msg(state, "Fetching Live Universe (Top USDT Pairs)...")
            await broadcast_fn()  # Push log update to frontend immediately
            
            universe = await asyncio.to_thread(
                state.connector.fetch_top_n_universe,
                state.discovery_config.universe_size,
            )
            t1 = time.monotonic()
            log_msg(state, f"Universe fetched: {len(universe)} raw pairs ({t1-t0:.1f}s)")
            await broadcast_fn()

            # STEP 2: Multi-Factor Scoring (CPU-bound, run in thread)
            log_msg(state, f"Running Multi-Factor Scoring on {len(universe)} assets...")
            await broadcast_fn()
            scores = await asyncio.to_thread(score_universe, state, universe)
            t2 = time.monotonic()
            log_msg(state, f"Scoring complete: {len(scores)} scored ({t2-t1:.1f}s)")

            # STEP 3: Dynamic Top-K Selection
            selected = select_top_assets(state, scores)

            state.scored_assets = scores
            state.selected_assets = [s["symbol"] for s in selected]

            above_threshold = len([s for s in scores if s.get("score", 0) >= state.discovery_config.dynamic_threshold])
            log_msg(
                state,
                f"Selection: {len(selected)} assets active "
                f"(threshold={state.discovery_config.dynamic_threshold}, "
                f"above={above_threshold}, max={state.discovery_config.max_active_assets})"
            )
            await broadcast_fn()

            # STEP 4: Pre-fetch Historical Klines in PARALLEL
            log_msg(state, f"Pre-fetching klines for {len(state.selected_assets)} assets...")
            await broadcast_fn()
            await prefetch_klines(state)
            t3 = time.monotonic()
            log_msg(state, f"Klines ready ({t3-t2:.1f}s)")
            await broadcast_fn()

            # STEP 5: Start Async WebSocket Stream
            if state.selected_assets:
                asset_preview = ", ".join(state.selected_assets[:5])
                more = f"... +{len(state.selected_assets)-5}" if len(state.selected_assets) > 5 else ""
                log_msg(
                    state,
                    f"Initiating Live WebSocket Streams for "
                    f"{len(state.selected_assets)} assets: {asset_preview}{more}"
                )
                await broadcast_fn()
                await state.connector.start_streams(state.selected_assets, callback=on_tick)
            else:
                log_msg(state, "No assets passed the dynamic threshold. Waiting 60s for next cycle...")
                await broadcast_fn()
                await asyncio.sleep(60)

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error("trading_loop_error", error=str(e), traceback=tb)
            log_msg(state, f"Critical Engine Error: {str(e)}")
            await broadcast_fn()
            await asyncio.sleep(10)
