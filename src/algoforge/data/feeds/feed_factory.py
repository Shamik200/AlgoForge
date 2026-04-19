"""Factory for creating the appropriate data feed based on config.

Usage:
    from algoforge.data.feeds.feed_factory import create_feed
    feed = create_feed()         # uses config provider
    feed = create_feed("binance")  # explicit provider
"""

from __future__ import annotations

from algoforge.core.config import get_settings
from algoforge.data.feeds.base_feed import BaseFeed


# Lazy imports to avoid requiring all feed dependencies at startup
_FEED_REGISTRY: dict[str, str] = {
    "yfinance": "algoforge.data.feeds.yfinance_feed.YFinanceFeed",
    "binance": "algoforge.data.feeds.binance_feed.BinanceFeed",
    "alphavantage": "algoforge.data.feeds.alphavantage_feed.AlphaVantageFeed",
}


def create_feed(provider: str | None = None) -> BaseFeed:
    """Create the appropriate feed adapter.

    Args:
        provider: Feed provider name. If None, uses config.

    Returns:
        Configured feed adapter instance.

    Raises:
        ValueError: If provider is not supported.
    """
    if provider is None:
        provider = get_settings().data_feed.provider

    class_path = _FEED_REGISTRY.get(provider)
    if class_path is None:
        raise ValueError(
            f"Unknown feed provider: {provider}. "
            f"Supported: {list(_FEED_REGISTRY.keys())}"
        )

    # Lazy import to avoid loading unused feed dependencies
    module_path, class_name = class_path.rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    feed_cls = getattr(module, class_name)
    return feed_cls()
