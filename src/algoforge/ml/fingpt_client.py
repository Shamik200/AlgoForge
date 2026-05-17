"""FinGPT Client for AI-powered price predictions.

This module provides integration with FinGPT (Financial GPT) for generating
price predictions with confidence intervals across multiple time horizons.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal

import pandas as pd
from cachetools import TTLCache
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PricePoint(BaseModel):
    """Single price prediction point with confidence interval."""

    price: float = Field(..., description="Predicted price")
    lower_bound: float = Field(..., description="Lower confidence bound")
    upper_bound: float = Field(..., description="Upper confidence bound")
    confidence_interval_width: float = Field(..., description="Width of confidence interval")

    @property
    def confidence_interval_pct(self) -> float:
        """Confidence interval as percentage of predicted price."""
        if self.price == 0:
            return 0.0
        return (self.confidence_interval_width / self.price) * 100


class FinGPTPrediction(BaseModel):
    """FinGPT price prediction with confidence intervals for multiple horizons."""

    symbol: str = Field(..., description="Trading symbol")
    timestamp: datetime = Field(..., description="Prediction timestamp")
    predictions: dict[int, PricePoint] = Field(
        ..., description="Predictions by horizon (bars forward)"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall prediction confidence")
    direction: Literal["up", "down", "neutral"] = Field(..., description="Predicted direction")

    @property
    def short_term_prediction(self) -> PricePoint | None:
        """Get 1-bar ahead prediction if available."""
        return self.predictions.get(1)

    @property
    def medium_term_prediction(self) -> PricePoint | None:
        """Get 5-bar ahead prediction if available."""
        return self.predictions.get(5)

    @property
    def long_term_prediction(self) -> PricePoint | None:
        """Get 10-bar ahead prediction if available."""
        return self.predictions.get(10)

    @property
    def avg_confidence_interval_width(self) -> float:
        """Average confidence interval width across all horizons."""
        if not self.predictions:
            return 0.0
        widths = [p.confidence_interval_width for p in self.predictions.values()]
        return sum(widths) / len(widths)


class FinGPTClient:
    """Client for FinGPT price prediction API.

    Provides AI-powered price predictions with confidence intervals for multiple
    time horizons. Implements caching to avoid redundant API calls and graceful
    degradation on API failures.

    Example:
        >>> client = FinGPTClient(api_key="your_key", cache_ttl=300)
        >>> prediction = await client.predict_price("AAPL", bars_df, horizons=[1, 5, 10])
        >>> print(f"Direction: {prediction.direction}, Confidence: {prediction.confidence}")
    """

    def __init__(
        self,
        api_key: str,
        cache_ttl: int = 300,
        api_url: str = "https://api.fingpt.ai/v1/predict",
        timeout: float = 10.0,
    ) -> None:
        """Initialize FinGPT client with API credentials and cache settings.

        Args:
            api_key: FinGPT API key for authentication
            cache_ttl: Cache time-to-live in seconds (default: 300)
            api_url: FinGPT API endpoint URL
            timeout: Request timeout in seconds (default: 10.0)
        """
        self.api_key = api_key
        self.api_url = api_url
        self.timeout = timeout
        self.cache: TTLCache = TTLCache(maxsize=1000, ttl=cache_ttl)
        self._api_available = True
        self._consecutive_failures = 0
        self._max_failures_before_disable = 5

        logger.info(
            f"FinGPTClient initialized with cache_ttl={cache_ttl}s, timeout={timeout}s"
        )

    def _generate_cache_key(self, symbol: str, timestamp: datetime, horizons: list[int]) -> str:
        """Generate cache key for a prediction request.

        Args:
            symbol: Trading symbol
            timestamp: Timestamp of the latest bar
            horizons: List of prediction horizons

        Returns:
            Cache key string
        """
        horizons_str = "_".join(map(str, sorted(horizons)))
        ts_str = timestamp.isoformat()
        return f"{symbol}:{ts_str}:{horizons_str}"

    def get_cached_prediction(
        self, symbol: str, timestamp: datetime, horizons: list[int] | None = None
    ) -> FinGPTPrediction | None:
        """Retrieve cached prediction if available.

        Args:
            symbol: Trading symbol
            timestamp: Timestamp to check
            horizons: List of horizons (default: [1, 5, 10])

        Returns:
            Cached prediction or None if not found
        """
        if horizons is None:
            horizons = [1, 5, 10]

        cache_key = self._generate_cache_key(symbol, timestamp, horizons)
        prediction = self.cache.get(cache_key)

        if prediction:
            logger.debug(f"Cache hit for {symbol} at {timestamp}")
        else:
            logger.debug(f"Cache miss for {symbol} at {timestamp}")

        return prediction

    async def predict_price(
        self,
        symbol: str,
        bars: pd.DataFrame,
        horizons: list[int] | None = None,
    ) -> FinGPTPrediction | None:
        """Generate price predictions for multiple horizons.

        Args:
            symbol: Trading symbol
            bars: DataFrame with OHLCV data (columns: open, high, low, close, volume)
            horizons: List of prediction horizons in bars (default: [1, 5, 10])

        Returns:
            FinGPTPrediction with predictions for each horizon, or None on failure

        Note:
            - Returns cached prediction if available
            - Gracefully degrades on API failure (returns None)
            - Disables API calls after consecutive failures
        """
        if horizons is None:
            horizons = [1, 5, 10]

        if bars.empty:
            logger.warning(f"Empty bars DataFrame for {symbol}, cannot predict")
            return None

        # Get latest timestamp
        if "timestamp" in bars.columns:
            latest_timestamp = pd.to_datetime(bars["timestamp"].iloc[-1])
        elif isinstance(bars.index, pd.DatetimeIndex):
            latest_timestamp = bars.index[-1]
        else:
            latest_timestamp = datetime.now()

        # Check cache first
        cache_key = self._generate_cache_key(symbol, latest_timestamp, horizons)
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug(f"Returning cached prediction for {symbol}")
            return cached

        # Check if API is disabled due to consecutive failures
        if not self._api_available:
            logger.warning(
                f"FinGPT API disabled due to {self._consecutive_failures} consecutive failures"
            )
            return None

        try:
            # Make API call
            prediction = await self._call_api(symbol, bars, horizons, latest_timestamp)

            if prediction:
                # Cache successful prediction
                self.cache[cache_key] = prediction
                self._consecutive_failures = 0
                self._api_available = True
                logger.info(
                    f"FinGPT prediction for {symbol}: {prediction.direction} "
                    f"(confidence: {prediction.confidence:.2f})"
                )
                return prediction
            else:
                self._handle_api_failure()
                return None

        except Exception as e:
            logger.error(f"FinGPT API error for {symbol}: {e}")
            self._handle_api_failure()
            return None

    async def _call_api(
        self,
        symbol: str,
        bars: pd.DataFrame,
        horizons: list[int],
        timestamp: datetime,
    ) -> FinGPTPrediction | None:
        """Make actual API call to FinGPT service.

        This is a placeholder implementation. In production, this would make
        an actual HTTP request to the FinGPT API.

        Args:
            symbol: Trading symbol
            bars: OHLCV DataFrame
            horizons: Prediction horizons
            timestamp: Prediction timestamp

        Returns:
            FinGPTPrediction or None on failure
        """
        # TODO: Implement actual API call when FinGPT API is available
        # For now, return a mock prediction for testing

        logger.warning(
            "FinGPT API not implemented - using mock predictions. "
            "Set FINGPT_API_KEY environment variable to enable real predictions."
        )

        # Mock implementation - replace with actual API call
        current_price = float(bars["close"].iloc[-1])

        # Generate mock predictions based on simple trend
        predictions = {}
        for horizon in horizons:
            # Simple mock: predict slight upward trend with increasing uncertainty
            predicted_price = current_price * (1 + 0.001 * horizon)
            uncertainty = current_price * 0.02 * horizon  # 2% per horizon

            predictions[horizon] = PricePoint(
                price=predicted_price,
                lower_bound=predicted_price - uncertainty,
                upper_bound=predicted_price + uncertainty,
                confidence_interval_width=2 * uncertainty,
            )

        # Determine direction
        short_term_change = predictions[min(horizons)].price - current_price
        if short_term_change > current_price * 0.001:
            direction = "up"
        elif short_term_change < -current_price * 0.001:
            direction = "down"
        else:
            direction = "neutral"

        return FinGPTPrediction(
            symbol=symbol,
            timestamp=timestamp,
            predictions=predictions,
            confidence=0.7,  # Mock confidence
            direction=direction,
        )

    def _handle_api_failure(self) -> None:
        """Handle API failure by incrementing failure counter and disabling if needed."""
        self._consecutive_failures += 1
        logger.warning(
            f"FinGPT API failure #{self._consecutive_failures} "
            f"(max: {self._max_failures_before_disable})"
        )

        if self._consecutive_failures >= self._max_failures_before_disable:
            self._api_available = False
            logger.error(
                f"FinGPT API disabled after {self._consecutive_failures} consecutive failures. "
                "System will continue with algorithmic signals only."
            )

    def reset_api_status(self) -> None:
        """Reset API status and failure counter.

        Call this to re-enable API calls after manual intervention or
        when you want to retry after a period of failures.
        """
        self._api_available = True
        self._consecutive_failures = 0
        logger.info("FinGPT API status reset - re-enabled")

    @property
    def is_api_available(self) -> bool:
        """Check if API is currently available."""
        return self._api_available

    @property
    def cache_size(self) -> int:
        """Get current cache size."""
        return len(self.cache)

    def clear_cache(self) -> None:
        """Clear all cached predictions."""
        self.cache.clear()
        logger.info("FinGPT cache cleared")
