"""Pairs Trading Signal Family."""

import logging
from collections import deque

import numpy as np

from algoforge.signals.models import SignalResult, SignalDirection
from algoforge.signals.pairs.cointegration import engle_granger_test

logger = logging.getLogger(__name__)


class PairsTradingFamily:
    """Signal Family 6: Pairs / Relative Value Trading.

    Identifies cointegrated pairs via Engle-Granger, trades the spread z-score,
    and periodically re-validates cointegration.
    """

    FAMILY_NAME = "pairs"

    def __init__(
        self,
        entry_z: float = 2.0,
        exit_z: float = 0.0,
        spread_window: int = 60,
        revalidation_period: int = 252,
    ) -> None:
        """Initialize the Pairs Trading signal family.

        Args:
            entry_z: Z-score threshold for entry (e.g., ±2.0).
            exit_z: Z-score threshold for exit (e.g., 0.0 = mean).
            spread_window: Rolling window for spread z-score calculation.
            revalidation_period: Number of bars between cointegration re-tests.
        """
        self.entry_z = entry_z
        self.exit_z = exit_z
        self.spread_window = spread_window
        self.revalidation_period = revalidation_period

        # State
        self._prices_a: list[float] = []
        self._prices_b: list[float] = []
        self._hedge_ratio: float = 0.0
        self._intercept: float = 0.0
        self._is_cointegrated: bool = False
        self._bars_since_validation: int = 0
        self._spread_history: deque[float] = deque(maxlen=spread_window)

    def calibrate(self, prices_a: list[float], prices_b: list[float]) -> bool:
        """Calibrate the pair by running the Engle-Granger test.

        Args:
            prices_a: Historical prices for Asset A.
            prices_b: Historical prices for Asset B.

        Returns:
            True if the pair is cointegrated, False otherwise.
        """
        result = engle_granger_test(prices_a, prices_b)
        self._is_cointegrated = result["cointegrated"]
        self._hedge_ratio = result["hedge_ratio"]
        self._bars_since_validation = 0

        if self._is_cointegrated:
            logger.info(
                "[%s] Pair calibrated: hedge_ratio=%.4f, p_value=%.4f",
                self.FAMILY_NAME, self._hedge_ratio, result["p_value"]
            )
            # Seed spread history
            self._spread_history.clear()
            for s in result["spread"][-self.spread_window:]:
                self._spread_history.append(s)
        else:
            logger.warning(
                "[%s] Pair NOT cointegrated (p=%.4f). Signal disabled.",
                self.FAMILY_NAME, result["p_value"]
            )

        # Store prices for re-validation
        self._prices_a = list(prices_a)
        self._prices_b = list(prices_b)

        return self._is_cointegrated

    def generate(self, price_a: float, price_b: float) -> SignalResult:
        """Generate a pairs trading signal from the current prices.

        Args:
            price_a: Current price of Asset A.
            price_b: Current price of Asset B.

        Returns:
            A SignalResult with the spread z-score signal.
        """
        # Track prices for re-validation
        self._prices_a.append(price_a)
        self._prices_b.append(price_b)
        self._bars_since_validation += 1

        # Check if re-validation is needed
        if self._bars_since_validation >= self.revalidation_period:
            self.calibrate(self._prices_a, self._prices_b)

        # If not cointegrated, return invalid
        if not self._is_cointegrated:
            return SignalResult(
                family_name=self.FAMILY_NAME,
                score=0.0,
                direction=SignalDirection.NEUTRAL,
                is_valid=False,
                metadata={"reason": "pair_not_cointegrated"},
            )

        # Calculate current spread
        current_spread = price_a - (self._hedge_ratio * price_b)
        self._spread_history.append(current_spread)

        # Need enough history for z-score
        if len(self._spread_history) < 20:
            return SignalResult(
                family_name=self.FAMILY_NAME,
                score=0.0,
                direction=SignalDirection.NEUTRAL,
                is_valid=False,
                metadata={"reason": "insufficient_spread_history"},
            )

        # Z-score of current spread
        spread_arr = np.array(self._spread_history)
        mean = float(np.mean(spread_arr))
        std = float(np.std(spread_arr))

        if std == 0:
            return SignalResult(
                family_name=self.FAMILY_NAME,
                score=0.0,
                direction=SignalDirection.NEUTRAL,
                is_valid=True,
                metadata={"z_score": "0.0", "spread": str(round(current_spread, 4))},
            )

        z_score = (current_spread - mean) / std

        # Normalize to [-1, 1] using entry_z as the boundary
        normalized_score = max(-1.0, min(1.0, -z_score / self.entry_z))

        # Determine direction
        direction = SignalDirection.NEUTRAL
        if z_score < -self.entry_z:
            direction = SignalDirection.LONG   # Spread too low → buy A, sell B
        elif z_score > self.entry_z:
            direction = SignalDirection.SHORT  # Spread too high → sell A, buy B

        return SignalResult(
            family_name=self.FAMILY_NAME,
            score=normalized_score,
            direction=direction,
            is_valid=True,
            metadata={
                "z_score": str(round(z_score, 4)),
                "spread": str(round(current_spread, 4)),
                "hedge_ratio": str(round(self._hedge_ratio, 4)),
                "spread_mean": str(round(mean, 4)),
                "spread_std": str(round(std, 4)),
            },
        )
