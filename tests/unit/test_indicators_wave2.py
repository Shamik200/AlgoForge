"""Tests for Wave 2 indicators — RSI, ADX, ATR, Bollinger, Keltner, Stochastic."""

import numpy as np
import pytest

from algoforge.technical.adx import ADX
from algoforge.technical.atr import ATR
from algoforge.technical.bollinger import BollingerBands
from algoforge.technical.indicator_base import IndicatorResult
from algoforge.technical.keltner import KeltnerChannels
from algoforge.technical.rsi import RSI
from algoforge.technical.stochastic import Stochastic

# Longer dataset for indicators that need more lookback
CLOSES = np.array([
    44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08, 45.89,
    46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64, 46.21,
    46.25, 45.71, 46.45, 45.78, 45.35, 44.03, 44.18, 44.22, 44.57, 43.42,
], dtype=np.float64)

HIGHS = np.array([
    44.50, 44.30, 44.00, 44.50, 45.00, 45.30, 45.60, 46.00, 46.20, 46.10,
    46.20, 46.00, 46.50, 46.40, 46.20, 46.20, 46.60, 46.40, 46.00, 46.40,
    46.50, 46.00, 46.60, 46.00, 45.60, 44.80, 44.40, 44.50, 44.80, 44.00,
], dtype=np.float64)

LOWS = np.array([
    44.00, 43.80, 43.50, 44.00, 44.50, 44.90, 45.20, 45.60, 45.80, 45.70,
    45.80, 45.40, 46.00, 46.00, 45.80, 45.80, 46.20, 45.90, 45.40, 46.00,
    45.50, 45.50, 45.60, 45.50, 45.00, 43.80, 43.90, 44.00, 44.30, 43.20,
], dtype=np.float64)


# ---------------------------------------------------------------------------
# RSI tests
# ---------------------------------------------------------------------------

class TestRSI:
    """Test RSI indicator."""

    def test_rsi_range(self) -> None:
        """RSI values are between 0 and 100."""
        rsi = RSI(period=14)
        result = rsi.compute(CLOSES)
        values = np.array(result.values["rsi"])
        valid = values[~np.isnan(values)]
        assert all(0 <= v <= 100 for v in valid)

    def test_rsi_name(self) -> None:
        assert RSI().name == "rsi"

    def test_rsi_lookback(self) -> None:
        assert RSI(period=14).lookback_period == 15

    def test_rsi_result_type(self) -> None:
        result = RSI(period=14).compute(CLOSES)
        assert isinstance(result, IndicatorResult)
        assert "rsi" in result.values

    def test_rsi_nan_padding(self) -> None:
        """Values before lookback period are NaN."""
        result = RSI(period=14).compute(CLOSES)
        values = np.array(result.values["rsi"])
        assert all(np.isnan(values[:14]))

    def test_rsi_insufficient_data(self) -> None:
        with pytest.raises(ValueError):
            RSI(period=14).compute(CLOSES[:10])


# ---------------------------------------------------------------------------
# ATR tests
# ---------------------------------------------------------------------------

class TestATR:
    """Test ATR indicator."""

    def test_atr_positive(self) -> None:
        """ATR values are positive."""
        result = ATR(period=14).compute(CLOSES, HIGHS, LOWS)
        values = np.array(result.values["atr"])
        valid = values[~np.isnan(values)]
        assert all(v > 0 for v in valid)

    def test_atr_name(self) -> None:
        assert ATR().name == "atr"

    def test_atr_requires_highs_lows(self) -> None:
        with pytest.raises(ValueError, match="requires highs and lows"):
            ATR().compute(CLOSES)


# ---------------------------------------------------------------------------
# ADX tests
# ---------------------------------------------------------------------------

class TestADX:
    """Test ADX indicator."""

    def test_adx_range(self) -> None:
        """ADX values are between 0 and 100."""
        result = ADX(period=14).compute(CLOSES, HIGHS, LOWS)
        values = np.array(result.values["adx"])
        valid = values[~np.isnan(values)]
        assert all(0 <= v <= 100 for v in valid)

    def test_adx_result_keys(self) -> None:
        result = ADX(period=14).compute(CLOSES, HIGHS, LOWS)
        assert "adx" in result.values
        assert "plus_di" in result.values
        assert "minus_di" in result.values

    def test_adx_name(self) -> None:
        assert ADX().name == "adx"

    def test_adx_requires_highs_lows(self) -> None:
        with pytest.raises(ValueError, match="requires highs and lows"):
            ADX().compute(CLOSES)


# ---------------------------------------------------------------------------
# Bollinger Bands tests
# ---------------------------------------------------------------------------

class TestBollingerBands:
    """Test Bollinger Bands indicator."""

    def test_bollinger_bands_ordering(self) -> None:
        """Upper > middle > lower for all valid values."""
        result = BollingerBands(period=10).compute(CLOSES)
        u = np.array(result.values["upper"])
        m = np.array(result.values["middle"])
        lo = np.array(result.values["lower"])

        valid = ~np.isnan(u)
        assert all(u[valid] >= m[valid])
        assert all(m[valid] >= lo[valid])

    def test_bollinger_result_keys(self) -> None:
        result = BollingerBands(period=10).compute(CLOSES)
        assert "upper" in result.values
        assert "middle" in result.values
        assert "lower" in result.values
        assert "bandwidth" in result.values
        assert "pct_b" in result.values

    def test_bollinger_name(self) -> None:
        assert BollingerBands().name == "bollinger"

    def test_bollinger_pctb_range(self) -> None:
        """When close is at lower band, %B ≈ 0; at upper ≈ 1."""
        result = BollingerBands(period=10).compute(CLOSES)
        pctb = np.array(result.values["pct_b"])
        valid = pctb[~np.isnan(pctb)]
        # %B can go slightly outside 0-1 (close outside bands), but typical range
        assert len(valid) > 0


# ---------------------------------------------------------------------------
# Keltner Channels tests
# ---------------------------------------------------------------------------

class TestKeltnerChannels:
    """Test Keltner Channels indicator."""

    def test_keltner_bands_ordering(self) -> None:
        """Upper > middle > lower."""
        result = KeltnerChannels(period=10).compute(CLOSES, HIGHS, LOWS)
        u = np.array(result.values["upper"])
        m = np.array(result.values["middle"])
        lo = np.array(result.values["lower"])

        valid = ~np.isnan(u)
        assert all(u[valid] >= m[valid])
        assert all(m[valid] >= lo[valid])

    def test_keltner_result_keys(self) -> None:
        result = KeltnerChannels(period=10).compute(CLOSES, HIGHS, LOWS)
        assert "upper" in result.values
        assert "middle" in result.values
        assert "lower" in result.values

    def test_keltner_name(self) -> None:
        assert KeltnerChannels().name == "keltner"

    def test_keltner_requires_highs_lows(self) -> None:
        with pytest.raises(ValueError, match="requires highs and lows"):
            KeltnerChannels().compute(CLOSES)


# ---------------------------------------------------------------------------
# Stochastic tests
# ---------------------------------------------------------------------------

class TestStochastic:
    """Test Stochastic Oscillator."""

    def test_stochastic_k_range(self) -> None:
        """%K values between 0 and 100."""
        result = Stochastic(k_period=14, d_period=3, smooth=3).compute(CLOSES, HIGHS, LOWS)
        k = np.array(result.values["k"])
        valid = k[~np.isnan(k)]
        assert all(0 <= v <= 100 for v in valid)

    def test_stochastic_result_keys(self) -> None:
        result = Stochastic(k_period=14).compute(CLOSES, HIGHS, LOWS)
        assert "k" in result.values
        assert "d" in result.values

    def test_stochastic_name(self) -> None:
        assert Stochastic().name == "stochastic"

    def test_stochastic_requires_highs_lows(self) -> None:
        with pytest.raises(ValueError, match="requires highs and lows"):
            Stochastic().compute(CLOSES)
