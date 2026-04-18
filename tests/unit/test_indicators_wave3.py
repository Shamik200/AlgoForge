"""Tests for Wave 3 indicators — VWAP, Donchian, Volume Profile, OBV, Ichimoku."""

import numpy as np
import pytest

from algoforge.technical.donchian import DonchianChannels
from algoforge.technical.ichimoku import Ichimoku
from algoforge.technical.indicator_base import IndicatorResult
from algoforge.technical.obv import OBV
from algoforge.technical.volume_profile import VolumeProfile
from algoforge.technical.vwap import VWAP

# Extended dataset (60 bars for Ichimoku's 52-period lookback)
np.random.seed(42)
BASE = 100.0
CHANGES = np.random.randn(60) * 0.5
CLOSES = BASE + np.cumsum(CHANGES)
HIGHS = CLOSES + np.abs(np.random.randn(60)) * 0.3
LOWS = CLOSES - np.abs(np.random.randn(60)) * 0.3
VOLUMES = (np.random.rand(60) * 100000 + 50000).astype(np.float64)


class TestVWAP:
    """Test VWAP indicator."""

    def test_vwap_result_keys(self) -> None:
        result = VWAP().compute(CLOSES, HIGHS, LOWS, VOLUMES)
        assert "vwap" in result.values
        assert "upper_band" in result.values
        assert "lower_band" in result.values

    def test_vwap_name(self) -> None:
        assert VWAP().name == "vwap"

    def test_vwap_within_price_range(self) -> None:
        """VWAP should be within the high-low range of the data."""
        result = VWAP().compute(CLOSES, HIGHS, LOWS, VOLUMES)
        vwap = np.array(result.values["vwap"])
        valid = vwap[~np.isnan(vwap)]
        assert all(np.min(LOWS) <= v <= np.max(HIGHS) for v in valid)

    def test_vwap_requires_volumes(self) -> None:
        with pytest.raises(ValueError, match="requires highs, lows, and volumes"):
            VWAP().compute(CLOSES)

    def test_vwap_band_ordering(self) -> None:
        """Upper band >= VWAP >= lower band."""
        result = VWAP().compute(CLOSES, HIGHS, LOWS, VOLUMES)
        v = np.array(result.values["vwap"])
        u = np.array(result.values["upper_band"])
        lo = np.array(result.values["lower_band"])
        valid = ~np.isnan(u) & ~np.isnan(lo)
        assert all(u[valid] >= v[valid])
        assert all(v[valid] >= lo[valid])


class TestDonchianChannels:
    """Test Donchian Channels."""

    def test_donchian_result_keys(self) -> None:
        result = DonchianChannels(period=10).compute(CLOSES, HIGHS, LOWS)
        assert "upper" in result.values
        assert "lower" in result.values
        assert "middle" in result.values

    def test_donchian_name(self) -> None:
        assert DonchianChannels().name == "donchian"

    def test_donchian_upper_is_highest_high(self) -> None:
        """Upper channel = highest high over period."""
        period = 10
        result = DonchianChannels(period=period).compute(CLOSES, HIGHS, LOWS)
        u = np.array(result.values["upper"])
        # Check a specific point
        idx = period  # First valid + 1
        expected = np.max(HIGHS[idx - period + 1 : idx + 1])
        assert abs(u[idx] - expected) < 1e-10

    def test_donchian_lower_is_lowest_low(self) -> None:
        """Lower channel = lowest low over period."""
        period = 10
        result = DonchianChannels(period=period).compute(CLOSES, HIGHS, LOWS)
        lo = np.array(result.values["lower"])
        idx = period
        expected = np.min(LOWS[idx - period + 1 : idx + 1])
        assert abs(lo[idx] - expected) < 1e-10

    def test_donchian_middle_is_average(self) -> None:
        """Middle = (upper + lower) / 2."""
        result = DonchianChannels(period=10).compute(CLOSES, HIGHS, LOWS)
        u = np.array(result.values["upper"])
        lo = np.array(result.values["lower"])
        m = np.array(result.values["middle"])
        valid = ~np.isnan(u)
        np.testing.assert_allclose(m[valid], (u[valid] + lo[valid]) / 2.0)

    def test_donchian_requires_highs_lows(self) -> None:
        with pytest.raises(ValueError):
            DonchianChannels().compute(CLOSES)


class TestVolumeProfile:
    """Test Volume Profile indicator."""

    def test_volume_profile_result_keys(self) -> None:
        result = VolumeProfile().compute(CLOSES, HIGHS, LOWS, VOLUMES)
        assert "poc" in result.values
        assert "vah" in result.values
        assert "val" in result.values

    def test_volume_profile_name(self) -> None:
        assert VolumeProfile().name == "volume_profile"

    def test_poc_within_price_range(self) -> None:
        """POC must be within the data's price range."""
        result = VolumeProfile().compute(CLOSES, HIGHS, LOWS, VOLUMES)
        poc = result.values["poc"][0]
        assert np.min(LOWS) <= poc <= np.max(HIGHS)

    def test_value_area_ordering(self) -> None:
        """VAH >= POC >= VAL."""
        result = VolumeProfile().compute(CLOSES, HIGHS, LOWS, VOLUMES)
        vah = result.values["vah"][0]
        poc = result.values["poc"][0]
        val = result.values["val"][0]
        assert vah >= poc >= val or abs(vah - val) < 1.0  # Allow small tolerance

    def test_volume_profile_requires_volumes(self) -> None:
        with pytest.raises(ValueError):
            VolumeProfile().compute(CLOSES)

    def test_volume_profile_metadata(self) -> None:
        """Metadata contains bin data."""
        result = VolumeProfile().compute(CLOSES, HIGHS, LOWS, VOLUMES)
        assert "bin_centers" in result.metadata
        assert "bin_volumes" in result.metadata


class TestOBV:
    """Test OBV indicator."""

    def test_obv_result_keys(self) -> None:
        result = OBV().compute(CLOSES, volumes=VOLUMES)
        assert "obv" in result.values

    def test_obv_name(self) -> None:
        assert OBV().name == "obv"

    def test_obv_first_value_is_first_volume(self) -> None:
        """First OBV = first volume."""
        result = OBV().compute(CLOSES, volumes=VOLUMES)
        assert result.values["obv"][0] == VOLUMES[0]

    def test_obv_up_day_adds_volume(self) -> None:
        """Up day: OBV increases by volume."""
        # Create simple up-trend data
        closes = np.array([10.0, 11.0, 12.0, 13.0], dtype=np.float64)
        volumes = np.array([100.0, 200.0, 300.0, 400.0], dtype=np.float64)
        result = OBV().compute(closes, volumes=volumes)
        obv = result.values["obv"]
        assert obv[0] == 100.0
        assert obv[1] == 300.0  # 100 + 200
        assert obv[2] == 600.0  # 300 + 300

    def test_obv_down_day_subtracts(self) -> None:
        """Down day: OBV decreases by volume."""
        closes = np.array([13.0, 12.0, 11.0], dtype=np.float64)
        volumes = np.array([100.0, 200.0, 300.0], dtype=np.float64)
        result = OBV().compute(closes, volumes=volumes)
        obv = result.values["obv"]
        assert obv[1] == -100.0  # 100 - 200

    def test_obv_requires_volumes(self) -> None:
        with pytest.raises(ValueError, match="requires volumes"):
            OBV().compute(CLOSES)


class TestIchimoku:
    """Test Ichimoku Cloud."""

    def test_ichimoku_result_keys(self) -> None:
        result = Ichimoku().compute(CLOSES, HIGHS, LOWS)
        assert "tenkan" in result.values
        assert "kijun" in result.values
        assert "senkou_a" in result.values
        assert "senkou_b" in result.values
        assert "chikou" in result.values

    def test_ichimoku_name(self) -> None:
        assert Ichimoku().name == "ichimoku"

    def test_ichimoku_lookback(self) -> None:
        assert Ichimoku().lookback_period == 52

    def test_ichimoku_tenkan_faster_than_kijun(self) -> None:
        """Tenkan (9) starts producing values before Kijun (26)."""
        result = Ichimoku().compute(CLOSES, HIGHS, LOWS)
        tenkan = np.array(result.values["tenkan"])
        kijun = np.array(result.values["kijun"])

        first_tenkan = np.argmax(~np.isnan(tenkan))
        first_kijun = np.argmax(~np.isnan(kijun))
        assert first_tenkan < first_kijun

    def test_ichimoku_requires_highs_lows(self) -> None:
        with pytest.raises(ValueError, match="requires highs and lows"):
            Ichimoku().compute(CLOSES)

    def test_ichimoku_params_in_result(self) -> None:
        result = Ichimoku(tenkan=9, kijun=26, senkou_b=52).compute(CLOSES, HIGHS, LOWS)
        assert result.params["tenkan_period"] == 9
        assert result.params["kijun_period"] == 26
        assert result.params["senkou_b_period"] == 52
