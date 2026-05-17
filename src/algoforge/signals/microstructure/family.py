"""Microstructure Signal Family orchestrator."""

import logging

from algoforge.signals.microstructure.vwap import VWAPTracker
from algoforge.signals.microstructure.volume import calculate_volume_imbalance, detect_obv_divergence
from algoforge.signals.models import SignalResult, SignalDirection

logger = logging.getLogger(__name__)

# Timeframes that are considered "too slow" for microstructure signals
NON_INTRADAY_TIMEFRAMES = {"1d", "1D", "1w", "1W", "1M", "daily", "weekly", "monthly"}


class MicrostructureFamily:
    """Signal Family 5: Microstructure / Order Flow.

    Generates trading signals from VWAP deviation, volume imbalance,
    and OBV divergence. Self-disables on non-intraday timeframes and
    automatically falls back to L1-only indicators when L2 data is unavailable.
    """

    FAMILY_NAME = "microstructure"

    def __init__(
        self,
        timeframe: str = "5m",
        deviation_threshold: float = 1.5,
        imbalance_threshold: float = 0.65,
        obv_window: int = 14,
        has_l2_data: bool = False,
    ) -> None:
        """Initialize the Microstructure signal family.

        Args:
            timeframe: The candle timeframe from the data feed config.
            deviation_threshold: VWAP deviation σ threshold.
            imbalance_threshold: Volume imbalance ratio threshold.
            obv_window: OBV divergence lookback window.
            has_l2_data: Whether Level 2 order book data is available.
        """
        self.timeframe = timeframe
        self.imbalance_threshold = imbalance_threshold
        self.obv_window = obv_window
        self.has_l2_data = has_l2_data

        # Determine if this timeframe is intraday
        self._is_intraday = timeframe not in NON_INTRADAY_TIMEFRAMES

        if not self._is_intraday:
            logger.info(
                "[%s] Self-disabled: timeframe '%s' is not intraday.",
                self.FAMILY_NAME, timeframe
            )

        # Initialize sub-components
        self.vwap_tracker = VWAPTracker(deviation_threshold=deviation_threshold)

        # Price/volume history for OBV
        self._price_history: list[float] = []
        self._volume_history: list[float] = []

        mode = "L2 (full)" if has_l2_data else "L1 (OBV fallback)"
        logger.info("[%s] Initialized in %s mode, timeframe=%s", self.FAMILY_NAME, mode, timeframe)

    def generate(
        self,
        high: float,
        low: float,
        close: float,
        volume: float,
        order_book: dict | None = None,
    ) -> SignalResult:
        """Generate a microstructure signal from the current candle.

        Args:
            high: Candle high price.
            low: Candle low price.
            close: Candle close price.
            volume: Candle volume.

        Returns:
            A SignalResult with the composite microstructure score.
        """
        # Timeframe guard
        if not self._is_intraday:
            return SignalResult(
                family_name=self.FAMILY_NAME,
                score=0.0,
                direction=SignalDirection.NEUTRAL,
                is_valid=False,
                metadata={"reason": f"disabled_on_{self.timeframe}"},
            )

        # 1. Update VWAP
        self.vwap_tracker.update(high, low, close, volume)
        vwap_score = self.vwap_tracker.deviation_score(close)

        # 2. Volume Imbalance
        imbalance = calculate_volume_imbalance(high, low, close)
        # Convert to [-1, 1]: 0.5 (neutral) → 0.0, 1.0 (max buy) → +1.0, 0.0 (max sell) → -1.0
        imbalance_score = (imbalance - 0.5) * 2.0

        # 3. OBV Divergence (L1 fallback or supplement)
        self._price_history.append(close)
        self._volume_history.append(volume)
        obv_score = detect_obv_divergence(
            self._price_history, self._volume_history, self.obv_window
        )

        # 4. Composite Score
        # Weight: VWAP deviation is the primary signal (50%).
        # Volume imbalance confirms direction (30%).
        # OBV divergence is the confirmation layer (20%).
        composite = (vwap_score * 0.50) + (imbalance_score * 0.30) + (obv_score * 0.20)
        metadata: dict[str, str | float | bool] = {
            "vwap_score": round(vwap_score, 4),
            "imbalance_score": round(imbalance_score, 4),
            "obv_score": round(obv_score, 4),
            "current_vwap": round(self.vwap_tracker.current_vwap, 4),
            "mode": "L2" if (self.has_l2_data or order_book) else "L1",
        }

        if order_book and "bid" in order_book and "ask" in order_book and order_book["ask"] > order_book["bid"] > 0:
            bid_qty = float(order_book.get("bid_qty", 0.0))
            ask_qty = float(order_book.get("ask_qty", 0.0))
            book_total = bid_qty + ask_qty
            book_imbalance = (bid_qty - ask_qty) / book_total if book_total > 0 else 0.0
            spread = (float(order_book["ask"]) - float(order_book["bid"])) / float(order_book["ask"])
            l2_score = max(-1.0, min(1.0, book_imbalance - spread))
            composite = (0.65 * composite) + (0.35 * l2_score)
            metadata["book_imbalance"] = round(book_imbalance, 4)
            metadata["bid_ask_spread_pct"] = round(spread, 6)
            metadata["mode"] = "L2"
        composite = max(-1.0, min(1.0, composite))

        # Determine direction
        direction = SignalDirection.NEUTRAL
        if composite > 0.1:
            direction = SignalDirection.LONG
        elif composite < -0.1:
            direction = SignalDirection.SHORT

        return SignalResult(
            family_name=self.FAMILY_NAME,
            score=composite,
            direction=direction,
            is_valid=True,
            metadata=metadata,
        )
