"""Breakout and Volatility Expansion Signal Family module."""

from algoforge.signals.breakout.donchian import (
    calc_donchian_channels,
    detect_breakout,
    detect_failed_breakout,
)
from algoforge.signals.breakout.signal_orb import ORBSignal
from algoforge.signals.breakout.signal_volatility import VolatilityBreakoutSignal
from algoforge.signals.breakout.volatility import (
    calc_keltner_channels,
    calc_squeeze_duration,
    detect_squeeze,
)

__all__ = [
    "VolatilityBreakoutSignal",
    "ORBSignal",
    "calc_keltner_channels",
    "detect_squeeze",
    "calc_squeeze_duration",
    "calc_donchian_channels",
    "detect_breakout",
    "detect_failed_breakout",
]
