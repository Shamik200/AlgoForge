"""Pairs trading coordinator with cached family instances."""

from __future__ import annotations

from dataclasses import dataclass

from algoforge.core.models import OHLCV
from algoforge.signals.models import SignalResult
from algoforge.signals.pairs.family import PairsTradingFamily


@dataclass
class PairsSignalContext:
    primary_symbol: str
    partner_symbol: str
    signal: SignalResult


class PairTradingCoordinator:
    """Selects a partner asset and generates a pairs trading signal."""

    def __init__(self) -> None:
        self._families: dict[tuple[str, str], PairsTradingFamily] = {}

    def build_signal(
        self,
        primary_symbol: str,
        selected_assets: list[str],
        kline_buffers: dict[str, list[OHLCV]],
    ) -> PairsSignalContext | None:
        partners = [symbol for symbol in selected_assets if symbol != primary_symbol and symbol in kline_buffers]
        if not partners:
            return None

        partner_symbol = partners[0]
        primary_closes = [c.close for c in kline_buffers.get(primary_symbol, [])]
        partner_closes = [c.close for c in kline_buffers.get(partner_symbol, [])]

        if len(primary_closes) < 50 or len(partner_closes) < 50:
            return None

        key = tuple(sorted((primary_symbol, partner_symbol)))
        family = self._families.setdefault(key, PairsTradingFamily())

        if not family._is_cointegrated:
            family.calibrate(primary_closes, partner_closes)

        signal = family.generate(primary_closes[-1], partner_closes[-1])
        signal.metadata.update({"partner_symbol": partner_symbol})
        return PairsSignalContext(primary_symbol=primary_symbol, partner_symbol=partner_symbol, signal=signal)
