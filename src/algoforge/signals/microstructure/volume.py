"""Volume-based indicators for microstructure analysis."""

from collections import deque


def calculate_volume_imbalance(high: float, low: float, close: float) -> float:
    """Calculate buying pressure using the Chaikin-style money flow proxy.

    When only OHLCV data is available (no L2 order book), we approximate
    buy/sell pressure using the position of the close relative to the
    high-low range.

    Formula: (Close - Low) / (High - Low)
    - Values near 1.0 indicate strong buying pressure (close near high)
    - Values near 0.0 indicate strong selling pressure (close near low)
    - Values near 0.5 indicate neutral/balanced flow

    Args:
        high: Candle high price.
        low: Candle low price.
        close: Candle close price.

    Returns:
        Buying pressure ratio in [0.0, 1.0].
    """
    price_range = high - low
    if price_range <= 0:
        return 0.5  # Doji or zero-range candle → neutral

    return (close - low) / price_range


def detect_obv_divergence(
    prices: list[float],
    volumes: list[float],
    window: int = 14
) -> float:
    """Detect On-Balance Volume (OBV) divergence as a proxy for informed flow.

    OBV accumulates volume on up-closes and subtracts on down-closes.
    Divergence occurs when price makes a new extreme but OBV does not:
    - Price new high + OBV not new high = bearish divergence (return negative)
    - Price new low + OBV not new low = bullish divergence (return positive)

    Args:
        prices: List of close prices (chronological).
        volumes: List of corresponding volumes.
        window: Lookback window for detecting extremes.

    Returns:
        Divergence score in [-1.0, 1.0]. 0.0 = no divergence.
    """
    if len(prices) < window + 1 or len(volumes) < window + 1:
        return 0.0

    # Calculate OBV series
    obv = [0.0]
    for i in range(1, len(prices)):
        if prices[i] > prices[i - 1]:
            obv.append(obv[-1] + volumes[i])
        elif prices[i] < prices[i - 1]:
            obv.append(obv[-1] - volumes[i])
        else:
            obv.append(obv[-1])

    # Check recent window
    recent_prices = prices[-window:]
    recent_obv = obv[-window:]

    current_price = prices[-1]
    current_obv = obv[-1]

    price_high = max(recent_prices)
    price_low = min(recent_prices)
    obv_high = max(recent_obv)
    obv_low = min(recent_obv)

    # Bearish divergence: price at high but OBV is not
    if current_price >= price_high and current_obv < obv_high * 0.95:
        # Strength based on how far OBV is from its high
        if obv_high > 0:
            strength = 1.0 - (current_obv / obv_high)
            return max(-1.0, min(-0.1, -strength))

    # Bullish divergence: price at low but OBV is not
    if current_price <= price_low and obv_low < 0 and current_obv > obv_low * 0.95:
        if obv_low < 0:
            strength = 1.0 - (current_obv / obv_low)
            return min(1.0, max(0.1, strength))

    return 0.0
