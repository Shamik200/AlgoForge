"""AlgoForge structured logging setup.

Configures structlog for JSON or console output. All components use
`structlog.get_logger()` — this module configures the shared pipeline.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import structlog

from algoforge.core.config import get_settings


def setup_logging() -> None:
    """Configure structured logging for the entire application.

    Call once at startup before any other modules log.
    Reads logging config from settings.yaml.
    """
    settings = get_settings()
    cfg = settings.logging

    # Determine log level
    log_level = getattr(logging, cfg.level.upper(), logging.INFO)

    # Choose renderer based on format setting
    if cfg.format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Create log directory if file logging is enabled
    if cfg.log_file:
        log_path = Path(cfg.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

    # Configure stdlib logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    structlog.get_logger().info(
        "logging.configured",
        level=cfg.level,
        format=cfg.format,
        log_file=cfg.log_file,
    )
