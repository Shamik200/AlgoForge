"""AlgoForge — Institutional-Grade Algorithmic Trading System.

Entry point: python -m algoforge

Initializes config, logging, event bus, data feed, storage, and pipeline.
Runs historical backfill then continuous polling loop.
"""

from __future__ import annotations

import asyncio
import signal
import sys

import structlog

from algoforge.core.config import get_settings
from algoforge.core.event_bus import EventBus, SystemEvent
from algoforge.core.logging import setup_logging
from algoforge.data.feeds.yfinance_feed import YFinanceFeed
from algoforge.data.pipeline import DataPipeline
from algoforge.data.storage.redis_store import RedisStore


async def main() -> None:
    """Main application entry point."""
    # 1. Load config and setup logging
    setup_logging()
    logger = structlog.get_logger()
    settings = get_settings()

    logger.info(
        "algoforge.starting",
        version=settings.version,
        market=settings.market.selected_market.value,
        mode=settings.market.timeframe_mode.value,
        symbols=settings.data_feed.symbols,
        capital=settings.market.paper_trading_capital,
        currency=settings.market.currency,
    )

    # 2. Initialize components
    event_bus = EventBus()
    feed = YFinanceFeed()
    store = RedisStore()
    pipeline = DataPipeline(feed=feed, cache=store, event_bus=event_bus)

    # 3. Setup graceful shutdown
    shutdown_event = asyncio.Event()

    def handle_signal(sig: int, frame: object) -> None:
        logger.info("algoforge.shutdown_signal", signal=sig)
        shutdown_event.set()

    # Register signal handlers (SIGTERM may not be available on Windows)
    signal.signal(signal.SIGINT, handle_signal)
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, handle_signal)

    try:
        # 4. Connect and initialize
        await pipeline.initialize()

        # Publish startup event
        await event_bus.publish(
            SystemEvent(
                action="startup",
                message=f"AlgoForge v{settings.version} — {settings.market.selected_market.value}",
            )
        )

        # 5. Health check
        health = await pipeline.health_check()
        logger.info("algoforge.health", **health)

        if not health["pipeline"]:
            logger.error("algoforge.health_failed", health=health)
            print("\n[WARN] Pipeline health check failed. Check Redis connection.")
            print(f"  Redis: {settings.redis.host}:{settings.redis.port}")
            return

        # 6. Backfill historical data
        logger.info("algoforge.backfill.starting")
        results = await pipeline.backfill_all()
        for sym, count in results.items():
            logger.info("algoforge.backfill.result", symbol=sym, candles=count)

        total = sum(results.values())
        print(f"\n[OK] Backfilled {total:,} candles across {len(results)} symbols")

        # 7. Start event bus and polling loop concurrently
        event_bus_task = asyncio.create_task(event_bus.start())
        polling_task = asyncio.create_task(pipeline.run_polling_loop())

        print(f"[OK] Polling every {settings.data_feed.poll_interval_seconds}s")
        print("  Press Ctrl+C to stop\n")

        # 8. Wait for shutdown signal
        await shutdown_event.wait()

    except KeyboardInterrupt:
        logger.info("algoforge.keyboard_interrupt")
    except Exception as e:
        logger.error("algoforge.error", error=str(e), exc_info=True)
    finally:
        # 9. Graceful shutdown
        pipeline.stop()
        await pipeline.shutdown()
        await event_bus.stop()
        logger.info(
            "algoforge.stopped",
            events_published=event_bus.stats["published"],
            events_dispatched=event_bus.stats["dispatched"],
        )
        print("\n[OK] AlgoForge stopped gracefully")


if __name__ == "__main__":
    asyncio.run(main())
