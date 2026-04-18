"""VWAP — Volume Weighted Average Price.

Session-based institutional fair value indicator.
Resets at market open each day.

Requirements: INDI-08
"""

from __future__ import annotations

import numpy as np

from algoforge.technical.indicator_base import Indicator, IndicatorResult


class VWAP(Indicator):
    """Volume Weighted Average Price.

    VWAP = cumsum(typical_price × volume) / cumsum(volume)
    where typical_price = (high + low + close) / 3

    Usage:
        vwap = VWAP()
        result = vwap.compute(closes, highs, lows, volumes)
        # result.values = {"vwap": [...], "upper_band": [...], "lower_band": [...]}
    """

    def __init__(self, std_dev_bands: float = 2.0) -> None:
        self._std_dev_bands = std_dev_bands

    @property
    def name(self) -> str:
        return "vwap"

    @property
    def lookback_period(self) -> int:
        return 1  # VWAP can compute from first candle of session

    def compute(
        self,
        closes: np.ndarray,
        highs: np.ndarray | None = None,
        lows: np.ndarray | None = None,
        volumes: np.ndarray | None = None,
        opens: np.ndarray | None = None,
    ) -> IndicatorResult:
        """Compute VWAP with optional standard deviation bands."""
        if highs is None or lows is None or volumes is None:
            msg = "VWAP requires highs, lows, and volumes arrays"
            raise ValueError(msg)

        n = len(closes)

        # Typical price
        typical = (highs + lows + closes) / 3.0

        # Cumulative VWAP
        cum_tp_vol = np.cumsum(typical * volumes)
        cum_vol = np.cumsum(volumes)

        vwap = np.where(cum_vol > 0, cum_tp_vol / cum_vol, np.nan)

        # VWAP standard deviation bands
        upper_band = np.full(n, np.nan)
        lower_band = np.full(n, np.nan)

        for i in range(1, n):
            if cum_vol[i] > 0:
                # Running variance of typical price vs VWAP
                tp_slice = typical[:i + 1]
                vwap_val = vwap[i]
                vol_slice = volumes[:i + 1]

                weighted_sq_diff = vol_slice * (tp_slice - vwap_val) ** 2
                variance = np.sum(weighted_sq_diff) / np.sum(vol_slice)
                std = np.sqrt(variance)

                upper_band[i] = vwap[i] + self._std_dev_bands * std
                lower_band[i] = vwap[i] - self._std_dev_bands * std

        return IndicatorResult(
            name=self.name,
            values={
                "vwap": vwap.tolist(),
                "upper_band": upper_band.tolist(),
                "lower_band": lower_band.tolist(),
            },
            params={"std_dev_bands": self._std_dev_bands},
        )
