"""OBV — On Balance Volume.

Cumulative volume indicator for volume-price divergence detection.
Volume is added on up days and subtracted on down days.

Requirements: INDI-13
"""

from __future__ import annotations

import numpy as np

from algoforge.technical.indicator_base import Indicator, IndicatorResult


class OBV(Indicator):
    """On Balance Volume.

    Usage:
        obv = OBV()
        result = obv.compute(closes, volumes=volumes)
        # result.values = {"obv": [...]}
    """

    @property
    def name(self) -> str:
        return "obv"

    @property
    def lookback_period(self) -> int:
        return 2  # Need at least 2 candles to compare

    def compute(
        self,
        closes: np.ndarray,
        highs: np.ndarray | None = None,
        lows: np.ndarray | None = None,
        volumes: np.ndarray | None = None,
        opens: np.ndarray | None = None,
    ) -> IndicatorResult:
        """Compute OBV."""
        if volumes is None:
            msg = "OBV requires volumes array"
            raise ValueError(msg)

        self._validate_input(closes)
        n = len(closes)

        obv = np.zeros(n)
        obv[0] = volumes[0]

        for i in range(1, n):
            if closes[i] > closes[i - 1]:
                obv[i] = obv[i - 1] + volumes[i]
            elif closes[i] < closes[i - 1]:
                obv[i] = obv[i - 1] - volumes[i]
            else:
                obv[i] = obv[i - 1]

        return IndicatorResult(
            name=self.name,
            values={"obv": obv.tolist()},
            params={},
        )
