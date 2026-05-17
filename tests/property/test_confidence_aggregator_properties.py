from __future__ import annotations

from hypothesis import given, strategies as st, settings, assume

from algoforge.ml.confidence_aggregator import ConfidenceAggregator


@st.composite
def valid_confidence_values(draw):
    return draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))


@st.composite
def valid_signal_values(draw):
    return draw(st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False))


@st.composite
def all_confidence_components(draw):
    signal = draw(valid_signal_values())
    ml_conf = draw(valid_confidence_values())
    fingpt_conf = draw(valid_confidence_values())
    regime_align = draw(valid_confidence_values())
    return signal, ml_conf, fingpt_conf, regime_align


class TestConfidenceAggregatorProperties:
    @given(all_confidence_components())
    @settings(max_examples=200)
    def test_conviction_is_product(self, components):
        signal, ml_conf, fingpt_conf, regime_align = components
        agg = ConfidenceAggregator()
        score = agg.compute_conviction(
            composite_signal=signal,
            ml_confidence=ml_conf,
            fingpt_confidence=fingpt_conf,
            regime_alignment=regime_align,
        )
        expected = abs(signal) * ml_conf * fingpt_conf * regime_align
        assert abs(score.total_conviction - expected) < 1e-9

    @given(all_confidence_components())
    @settings(max_examples=200)
    def test_conviction_in_range_and_decision(self, components):
        signal, ml_conf, fingpt_conf, regime_align = components
        agg = ConfidenceAggregator()
        score = agg.compute_conviction(
            composite_signal=signal,
            ml_confidence=ml_conf,
            fingpt_confidence=fingpt_conf,
            regime_alignment=regime_align,
        )
        assert 0.0 <= score.total_conviction <= 1.0
        if score.total_conviction < agg.skip_threshold:
            assert score.decision == "skip"
        elif score.total_conviction < agg.half_position_threshold:
            assert score.decision == "half_position"
        else:
            assert score.decision == "full_position"

    @given(all_confidence_components())
    @settings(max_examples=200)
    def test_signal_direction_independence(self, components):
        signal, ml_conf, fingpt_conf, regime_align = components
        assume(abs(signal) > 0.01)
        agg = ConfidenceAggregator()
        pos = agg.compute_conviction(abs(signal), ml_conf, fingpt_conf, regime_align)
        neg = agg.compute_conviction(-abs(signal), ml_conf, fingpt_conf, regime_align)
        assert abs(pos.total_conviction - neg.total_conviction) < 1e-9
        assert pos.decision == neg.decision

