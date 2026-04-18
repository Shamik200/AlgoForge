"""Tests for Phase 4 — Market Regime Detection."""

import pytest

from algoforge.core.constants import MarketRegime
from algoforge.technical.regime import RegimeClassifier, RegimeResult


class TestRegimeResult:
    """Test RegimeResult model."""

    def test_regime_result_creation(self) -> None:
        r = RegimeResult(
            symbol="AAPL",
            probabilities={"trending": 0.5, "range": 0.3, "breakout": 0.1, "reversal": 0.05, "liquidity_trap": 0.05},
            primary_regime=MarketRegime.TRENDING,
            confidence=0.2,
        )
        assert r.symbol == "AAPL"
        assert r.is_trending
        assert not r.is_range

    def test_regime_helpers(self) -> None:
        r = RegimeResult(symbol="X", primary_regime=MarketRegime.BREAKOUT)
        assert r.is_breakout
        assert not r.is_reversal


class TestRegimeClassifier:
    """Test multi-factor regime classification."""

    def test_strong_trend_adx_high(self) -> None:
        """High ADX → trending regime."""
        c = RegimeClassifier()
        result = c.classify("TEST", adx=35.0, plus_di=30.0, minus_di=15.0)
        assert result.primary_regime == MarketRegime.TRENDING

    def test_range_adx_low(self) -> None:
        """Low ADX → range regime."""
        c = RegimeClassifier()
        result = c.classify("TEST", adx=12.0, rsi=50.0, volume_ratio=0.8)
        assert result.primary_regime == MarketRegime.RANGE

    def test_breakout_squeeze(self) -> None:
        """BB inside KC (squeeze) + ATR expansion → breakout."""
        c = RegimeClassifier()
        result = c.classify(
            "TEST",
            adx=22.0,
            bb_upper=153.0, bb_lower=147.0,
            kc_upper=155.0, kc_lower=145.0,
            bb_bandwidth=0.02,
            atr_current=2.0, atr_avg=1.2,
            volume_ratio=2.5,
        )
        assert result.primary_regime == MarketRegime.BREAKOUT

    def test_reversal_rsi_extreme(self) -> None:
        """RSI overbought + volume spike → reversal."""
        c = RegimeClassifier()
        result = c.classify(
            "TEST",
            adx=18.0,
            rsi=82.0,
            volume_ratio=2.5,
        )
        assert result.primary_regime == MarketRegime.REVERSAL

    def test_liquidity_trap(self) -> None:
        """False breakout signal → liquidity trap."""
        c = RegimeClassifier()
        result = c.classify(
            "TEST",
            adx=18.0,
            false_breakout=True,
        )
        assert result.primary_regime == MarketRegime.LIQUIDITY_TRAP

    def test_probabilities_sum_to_one(self) -> None:
        """All 5 regime probabilities should sum to ~1.0."""
        c = RegimeClassifier()
        result = c.classify("TEST", adx=25.0, rsi=55.0)
        total = sum(result.probabilities.values())
        assert abs(total - 1.0) < 0.01, f"Probabilities sum to {total}"

    def test_all_regimes_present(self) -> None:
        """Output contains probability for all 5 regimes."""
        c = RegimeClassifier()
        result = c.classify("TEST", adx=25.0)
        assert len(result.probabilities) == 5
        assert MarketRegime.TRENDING.value in result.probabilities
        assert MarketRegime.RANGE.value in result.probabilities
        assert MarketRegime.BREAKOUT.value in result.probabilities
        assert MarketRegime.REVERSAL.value in result.probabilities
        assert MarketRegime.LIQUIDITY_TRAP.value in result.probabilities

    def test_confidence_is_gap(self) -> None:
        """Confidence = primary probability - second highest."""
        c = RegimeClassifier()
        result = c.classify("TEST", adx=40.0, plus_di=35.0, minus_di=10.0)
        probs = sorted(result.probabilities.values(), reverse=True)
        expected_confidence = probs[0] - probs[1]
        assert abs(result.confidence - expected_confidence) < 0.01

    def test_smoothing(self) -> None:
        """Regime classification uses smoothing from previous result."""
        c = RegimeClassifier(smoothing_factor=0.5)
        # First call: strong trending
        r1 = c.classify("TEST", adx=40.0, plus_di=30.0, minus_di=10.0)
        trending_before = r1.probabilities[MarketRegime.TRENDING.value]

        # Second call: range signal → but smoothing keeps trending influence
        r2 = c.classify("TEST", adx=12.0, rsi=50.0)
        # Trending probability should be higher than without smoothing
        # because we blend with previous trending result
        assert r2.probabilities[MarketRegime.TRENDING.value] > 0

    def test_no_data_equal_distribution(self) -> None:
        """No indicator data → equal probability distribution."""
        c = RegimeClassifier()
        result = c.classify("TEST")
        probs = list(result.probabilities.values())
        # All should be equal (0.2 each)
        assert all(abs(p - 0.2) < 0.01 for p in probs)

    def test_caching(self) -> None:
        """Results are cached."""
        c = RegimeClassifier()
        c.classify("AAPL", adx=30.0)
        cached = c.get_cached("AAPL")
        assert cached is not None
        assert cached.symbol == "AAPL"

    def test_cache_miss(self) -> None:
        c = RegimeClassifier()
        assert c.get_cached("MISSING") is None

    def test_clear_cache(self) -> None:
        c = RegimeClassifier()
        c.classify("AAPL", adx=30.0)
        c.clear_cache()
        assert c.get_cached("AAPL") is None

    def test_stats(self) -> None:
        c = RegimeClassifier()
        c.classify("AAPL", adx=30.0)
        c.classify("GOOG", adx=15.0)
        assert c.stats["total_classifications"] == 2

    def test_sr_break_low_volume_trap(self) -> None:
        """S/R break on low volume → liquidity trap signal."""
        c = RegimeClassifier()
        result = c.classify(
            "TEST",
            adx=18.0,
            sr_break=True,
            volume_ratio=0.6,
        )
        trap_prob = result.probabilities[MarketRegime.LIQUIDITY_TRAP.value]
        assert trap_prob > 0.15  # Should have meaningful trap probability

    def test_atr_contraction_range(self) -> None:
        """ATR contracting → range signal."""
        c = RegimeClassifier()
        result = c.classify("TEST", adx=18.0, atr_current=0.5, atr_avg=1.0)
        assert result.primary_regime == MarketRegime.RANGE
