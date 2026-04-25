"""Unit tests for the Pairs & Cointegration Trading signal family."""

import numpy as np
import pytest

from algoforge.signals.pairs.cointegration import engle_granger_test
from algoforge.signals.pairs.family import PairsTradingFamily
from algoforge.signals.models import SignalDirection


def test_engle_granger_cointegrated():
    """Test Engle-Granger detects a cointegrated pair."""
    np.random.seed(42)
    n = 200

    # Create two cointegrated series: B is a random walk, A = 2*B + noise
    b = np.cumsum(np.random.randn(n)) + 100
    noise = np.random.randn(n) * 0.5
    a = 2.0 * b + 50 + noise  # Cointegrated with hedge ratio ~2.0

    result = engle_granger_test(a.tolist(), b.tolist())

    assert result["cointegrated"] is True
    assert pytest.approx(result["hedge_ratio"], abs=0.3) == 2.0
    assert result["p_value"] < 0.05
    assert len(result["spread"]) == n


def test_engle_granger_not_cointegrated():
    """Test Engle-Granger correctly rejects independent random walks."""
    np.random.seed(42)
    n = 200

    # Two independent random walks
    a = np.cumsum(np.random.randn(n)) + 100
    b = np.cumsum(np.random.randn(n)) + 100

    result = engle_granger_test(a.tolist(), b.tolist())

    # Independent random walks should NOT be cointegrated
    assert result["cointegrated"] is False


def test_engle_granger_insufficient_data():
    """Test Engle-Granger returns not cointegrated with too little data."""
    result = engle_granger_test([100, 101], [200, 201])
    assert result["cointegrated"] is False


def test_pairs_family_calibrate():
    """Test pairs family calibration with cointegrated series."""
    np.random.seed(42)
    n = 200

    b = np.cumsum(np.random.randn(n)) + 100
    noise = np.random.randn(n) * 0.5
    a = 2.0 * b + 50 + noise

    family = PairsTradingFamily(entry_z=2.0, spread_window=60)
    is_valid = family.calibrate(a.tolist(), b.tolist())

    assert is_valid is True
    assert family._is_cointegrated is True
    assert pytest.approx(family._hedge_ratio, abs=0.3) == 2.0


def test_pairs_family_signal_generation():
    """Test signal generation after calibration."""
    np.random.seed(42)
    n = 200

    b_prices = np.cumsum(np.random.randn(n)) + 100
    noise = np.random.randn(n) * 0.5
    a_prices = 2.0 * b_prices + 50 + noise

    family = PairsTradingFamily(entry_z=2.0, spread_window=60)
    family.calibrate(a_prices.tolist(), b_prices.tolist())

    # Generate signal with current spread near mean
    result = family.generate(float(a_prices[-1]), float(b_prices[-1]))

    assert result.is_valid is True
    assert result.family_name == "pairs"
    assert -1.0 <= result.score <= 1.0


def test_pairs_family_not_calibrated():
    """Test signal returns invalid when pair is not cointegrated."""
    family = PairsTradingFamily()
    # Don't calibrate

    result = family.generate(100.0, 200.0)
    assert result.is_valid is False


def test_pairs_family_extreme_spread():
    """Test signal fires when spread deviates significantly."""
    np.random.seed(42)
    n = 200

    b_prices = np.cumsum(np.random.randn(n)) + 100
    noise = np.random.randn(n) * 0.5
    a_prices = 2.0 * b_prices + 50 + noise

    family = PairsTradingFamily(entry_z=2.0, spread_window=60)
    family.calibrate(a_prices.tolist(), b_prices.tolist())

    # Artificially create a massive spread deviation
    # A is way too high relative to B → short spread signal
    extreme_a = float(a_prices[-1]) + 50  # Push A way above fair value
    result = family.generate(extreme_a, float(b_prices[-1]))

    assert result.is_valid is True
    # Positive z-score (spread too high) → SHORT direction
    assert result.direction == SignalDirection.SHORT
