"""Volume Profile.

Price-volume distribution analysis. Identifies where the most
trading occurred (POC), and the value area (VAH/VAL).

Requirements: INDI-12
"""

from __future__ import annotations

import numpy as np

from algoforge.technical.indicator_base import Indicator, IndicatorResult


class VolumeProfile(Indicator):
    """Volume Profile with POC, VAH, VAL.

    Bins price data by volume to find:
    - POC (Point of Control) — price level with highest volume
    - VAH (Value Area High) — upper bound of 70% volume area
    - VAL (Value Area Low) — lower bound of 70% volume area

    Usage:
        vp = VolumeProfile(num_bins=50, value_area_pct=0.7)
        result = vp.compute(closes, highs, lows, volumes)
        # result.values = {"poc": [...], "vah": [...], "val": [...]}
        # result.metadata = {"profile": {...}}
    """

    def __init__(self, num_bins: int = 50, value_area_pct: float = 0.7) -> None:
        self._num_bins = num_bins
        self._value_area_pct = value_area_pct

    @property
    def name(self) -> str:
        return "volume_profile"

    @property
    def lookback_period(self) -> int:
        return 10  # Need at least 10 bars for meaningful profile

    def compute(
        self,
        closes: np.ndarray,
        highs: np.ndarray | None = None,
        lows: np.ndarray | None = None,
        volumes: np.ndarray | None = None,
        opens: np.ndarray | None = None,
    ) -> IndicatorResult:
        """Compute Volume Profile."""
        if highs is None or lows is None or volumes is None:
            msg = "Volume Profile requires highs, lows, and volumes arrays"
            raise ValueError(msg)

        self._validate_input(closes)
        n = len(closes)

        # Build volume profile from all data
        price_min = float(np.min(lows))
        price_max = float(np.max(highs))

        if price_max == price_min:
            # Flat market — return simple values
            return IndicatorResult(
                name=self.name,
                values={
                    "poc": [price_min] * n,
                    "vah": [price_max] * n,
                    "val": [price_min] * n,
                },
                params={"num_bins": self._num_bins, "value_area_pct": self._value_area_pct},
            )

        # Create price bins
        bin_edges = np.linspace(price_min, price_max, self._num_bins + 1)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
        bin_volumes = np.zeros(self._num_bins)

        # Distribute volume across bins using typical price
        typical = (highs + lows + closes) / 3.0
        for i in range(n):
            bin_idx = int((typical[i] - price_min) / (price_max - price_min) * (self._num_bins - 1))
            bin_idx = min(max(bin_idx, 0), self._num_bins - 1)
            bin_volumes[bin_idx] += volumes[i]

        # POC = bin with highest volume
        poc_idx = int(np.argmax(bin_volumes))
        poc_price = float(bin_centers[poc_idx])

        # Value Area — 70% of total volume centered on POC
        total_vol = np.sum(bin_volumes)
        target_vol = total_vol * self._value_area_pct

        va_vol = bin_volumes[poc_idx]
        low_idx = poc_idx
        high_idx = poc_idx

        while va_vol < target_vol and (low_idx > 0 or high_idx < self._num_bins - 1):
            # Expand whichever side adds more volume
            vol_below = bin_volumes[low_idx - 1] if low_idx > 0 else 0
            vol_above = bin_volumes[high_idx + 1] if high_idx < self._num_bins - 1 else 0

            if vol_below >= vol_above and low_idx > 0:
                low_idx -= 1
                va_vol += bin_volumes[low_idx]
            elif high_idx < self._num_bins - 1:
                high_idx += 1
                va_vol += bin_volumes[high_idx]
            else:
                low_idx -= 1
                va_vol += bin_volumes[low_idx]

        vah_price = float(bin_centers[high_idx])
        val_price = float(bin_centers[low_idx])

        # Return constant POC/VAH/VAL for entire series (profile is over all data)
        return IndicatorResult(
            name=self.name,
            values={
                "poc": [poc_price] * n,
                "vah": [vah_price] * n,
                "val": [val_price] * n,
            },
            params={"num_bins": self._num_bins, "value_area_pct": self._value_area_pct},
            metadata={
                "bin_centers": bin_centers.tolist(),
                "bin_volumes": bin_volumes.tolist(),
            },
        )
