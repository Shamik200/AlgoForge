"""AlgoForge entry point — python -m algoforge."""

from algoforge.core.config import get_settings


def main() -> None:
    """Bootstrap and display system info."""
    settings = get_settings()
    print(
        f"AlgoForge v{settings.version} | "
        f"Market: {settings.market.selected_market.value} | "
        f"Mode: {settings.market.timeframe_mode.value} | "
        f"Capital: {settings.market.currency} {settings.market.paper_trading_capital:,.0f}"
    )


if __name__ == "__main__":
    main()
