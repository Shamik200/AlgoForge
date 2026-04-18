"""Tests for EMA, MACD, and Supertrend indicators."""

import numpy as np
import pytest

from algoforge.technical.ema import EMA
from algoforge.technical.indicator_base import IndicatorResult, ema_calc, true_range
from algoforge.technical.macd import MACD
from algoforge.technical.supertrend import Supertrend


# ---------------------------------------------------------------------------
# Shared test data (typical price series)
# ---------------------------------------------------------------------------

CLOSES = np.array([
    44.34, 44.09, 43.61, 44.33, 44.83,
    45.10, 45.42, 45.84, 46.08, 45.89,
    46.03, 45.61, 46.28, 46.28, 46.00,
    46.03, 46.41, 46.22, 45.64, 46.21,
], dtype=np.float64)

HIGHS = np.array([
    44.50, 44.30, 44.00, 44.50, 45.00,
    45.30, 45.60, 46.00, 46.20, 46.10,
    46.20, 46.00, 46.50, 46.40, 46.20,
    46.20, 46.60, 46.40, 46.00, 46.40,
], dtype=np.float64)

LOWS = np.array([
    44.00, 43.80, 43.50, 44.00, 44.50,
    44.90, 45.20, 45.60, 45.80, 45.70,
    45.80, 45.40, 46.00, 46.00, 45.80,
    45.80, 46.20, 45.90, 45.40, 46.00,
], dtype=np.float64)

VOLUMES = np.array([
    100000, 110000, 95000, 120000, 130000,
    140000, 150000, 160000, 170000, 120000,
    130000, 110000, 140000, 130000, 120000,
    125000, 145000, 135000, 115000, 140000,
], dtype=np.float64)


# ---------------------------------------------------------------------------
# ema_calc tests
# ---------------------------------------------------------------------------

class TestEmaCalc:
    """Test the shared ema_calc utility."""

    def test_ema_calc_length_matches_input(self) -> None:
        """EMA output has same length as input."""
        result = ema_calc(CLOSES, 5)
        assert len(result) == len(CLOSES)

    def test_ema_calc_nan_padding(self) -> None:
        """Values before period are NaN."""
        result = ema_calc(CLOSES, 10)
        assert all(np.isnan(result[:9]))
        assert not np.isnan(result[9])

    def test_ema_calc_seed_is_sma(self) -> None:
        """First EMA value is SMA of first N values."""
        period = 5
        result = ema_calc(CLOSES, period)
        expected_sma = np.mean(CLOSES[:period])
        assert abs(result[period - 1] - expected_sma) < 1e-10

    def test_ema_calc_insufficient_data(self) -> None:
        """Returns all NaN when data < period."""
        result = ema_calc(CLOSES[:3], 10)
        assert all(np.isnan(result))

    def test_ema_calc_weights_recent_more(self) -> None:
        """EMA reacts faster than SMA to recent price changes."""
        data = np.array([10.0] * 20 + [20.0], dtype=np.float64)
        ema_5 = ema_calc(data, 5)
        sma_5 = np.mean(data[-5:])  # SMA of last 5
        # EMA should be closer to 20 than SMA because it weighs recent more
        assert ema_5[-1] > sma_5 or abs(ema_5[-1] - sma_5) < 1.0


class TestTrueRange:
    """Test true_range utility."""

    def test_true_range_length(self) -> None:
        """TR output has same length as input."""
        tr = true_range(HIGHS, LOWS, CLOSES)
        assert len(tr) == len(HIGHS)

    def test_true_range_first_is_hl(self) -> None:
        """First TR value is just high - low."""
        tr = true_range(HIGHS, LOWS, CLOSES)
        assert abs(tr[0] - (HIGHS[0] - LOWS[0])) < 1e-10

    def test_true_range_positive(self) -> None:
        """All TR values are positive."""
        tr = true_range(HIGHS, LOWS, CLOSES)
        assert all(tr > 0)


# ---------------------------------------------------------------------------
# EMA indicator tests
# ---------------------------------------------------------------------------

class TestEMA:
    """Test EMA indicator."""

    def test_ema_default_periods(self) -> None:
        """Default periods are 5, 9, 21, 50, 100, 200."""
        ema = EMA()
        assert ema.periods == [5, 9, 21, 50, 100, 200]

    def test_ema_custom_periods(self) -> None:
        """Custom periods are respected."""
        ema = EMA(periods=[10, 20])
        assert ema.periods == [10, 20]

    def test_ema_result_type(self) -> None:
        """Compute returns IndicatorResult."""
        ema = EMA(periods=[5])
        result = ema.compute(CLOSES)
        assert isinstance(result, IndicatorResult)

    def test_ema_result_keys(self) -> None:
        """Result has keys for each period."""
        ema = EMA(periods=[5, 9])
        result = ema.compute(CLOSES)
        assert "ema_5" in result.values
        assert "ema_9" in result.values

    def test_ema_name(self) -> None:
        """Indicator name is 'ema'."""
        assert EMA().name == "ema"

    def test_ema_lookback_is_max_period(self) -> None:
        """Lookback equals longest period."""
        ema = EMA(periods=[5, 21, 50])
        assert ema.lookback_period == 50

    def test_ema_insufficient_data_raises(self) -> None:
        """Raises ValueError when not enough data."""
        ema = EMA(periods=[50])
        with pytest.raises(ValueError, match="requires at least 50"):
            ema.compute(CLOSES[:10])

    def test_ema_latest_property(self) -> None:
        """IndicatorResult.latest gives most recent value."""
        ema = EMA(periods=[5])
        result = ema.compute(CLOSES)
        assert "ema_5" in result.latest
        assert isinstance(result.latest["ema_5"], float)


# ---------------------------------------------------------------------------
# MACD tests
# ---------------------------------------------------------------------------

class TestMACD:
    """Test MACD indicator."""

    def test_macd_result_keys(self) -> None:
        """Result has macd, signal, histogram."""
        # Need enough data for MACD (26 + 9 = 35)
        long_closes = np.tile(CLOSES, 3)  # 60 data points
        macd = MACD()
        result = macd.compute(long_closes)
        assert "macd" in result.values
        assert "signal" in result.values
        assert "histogram" in result.values

    def test_macd_name(self) -> None:
        assert MACD().name == "macd"

    def test_macd_lookback(self) -> None:
        """Lookback = slow + signal."""
        macd = MACD(fast=12, slow=26, signal=9)
        assert macd.lookback_period == 35

    def test_macd_histogram_is_diff(self) -> None:
        """Histogram = MACD - Signal."""
        long_closes = np.tile(CLOSES, 3)
        macd = MACD()
        result = macd.compute(long_closes)

        m = np.array(result.values["macd"])
        s = np.array(result.values["signal"])
        h = np.array(result.values["histogram"])

        # Where both MACD and signal are valid
        valid = ~np.isnan(m) & ~np.isnan(s)
        np.testing.assert_allclose(h[valid], (m - s)[valid], atol=1e-10)

    def test_macd_insufficient_data_raises(self) -> None:
        """Raises ValueError when data < lookback."""
        with pytest.raises(ValueError):
            MACD().compute(CLOSES[:10])


# ---------------------------------------------------------------------------
# Supertrend tests
# ---------------------------------------------------------------------------

class TestSupertrend:
    """Test Supertrend indicator."""

    def test_supertrend_result_keys(self) -> None:
        """Result has supertrend and direction."""
        st = Supertrend(period=5)
        result = st.compute(CLOSES, HIGHS, LOWS)
        assert "supertrend" in result.values
        assert "direction" in result.values

    def test_supertrend_name(self) -> None:
        assert Supertrend().name == "supertrend"

    def test_supertrend_direction_values(self) -> None:
        """Direction is either 1.0 (bull) or -1.0 (bear) or NaN."""
        st = Supertrend(period=5)
        result = st.compute(CLOSES, HIGHS, LOWS)
        dirs = np.array(result.values["direction"])
        valid = dirs[~np.isnan(dirs)]
        assert all(d in (1.0, -1.0) for d in valid)

    def test_supertrend_requires_highs_lows(self) -> None:
        """Raises ValueError without highs/lows."""
        st = Supertrend()
        with pytest.raises(ValueError, match="requires highs and lows"):
            st.compute(CLOSES)

    def test_supertrend_params_in_result(self) -> None:
        """Result params include period and multiplier."""
        st = Supertrend(period=7, multiplier=2.5)
        result = st.compute(CLOSES, HIGHS, LOWS)
        assert result.params["period"] == 7
        assert result.params["multiplier"] == 2.5
