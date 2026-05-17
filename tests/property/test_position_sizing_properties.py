from __future__ import annotations

from hypothesis import given, strategies as st, settings

from algoforge.risk.models import AccountState
from algoforge.risk.sizing import calculate_position_size


@given(
    equity=st.floats(min_value=100.0, max_value=1_000_000.0),
    peak=st.floats(min_value=100.0, max_value=1_000_000.0),
    risk_pct_small=st.floats(min_value=0.0001, max_value=0.02),
    risk_pct_large=st.floats(min_value=0.0201, max_value=0.2),
    entry=st.floats(min_value=1.0, max_value=5000.0),
    sl_offset=st.floats(min_value=0.001, max_value=0.5),
)
@settings(max_examples=200)
def test_position_sizing_monotonicity_and_cap(equity, peak, risk_pct_small, risk_pct_large, entry, sl_offset):
    peak = max(peak, equity)
    acct = AccountState(current_equity=equity, peak_equity=peak)

    stop_loss_far = entry - entry * sl_offset
    stop_loss_close = entry - entry * (sl_offset * 0.5)

    pos_small = calculate_position_size(acct, risk_pct_small, entry, stop_loss_far, max_position_pct=0.10)
    pos_large = calculate_position_size(acct, risk_pct_large, entry, stop_loss_far, max_position_pct=0.10)

    assert pos_small >= 0.0 and pos_large >= 0.0
    assert pos_large >= pos_small - 1e-9

    pos_close = calculate_position_size(acct, risk_pct_small, entry, stop_loss_close, max_position_pct=0.10)
    max_cap = acct.current_equity * 0.10
    assert pos_close <= max_cap + 1e-9
    assert pos_small <= max_cap + 1e-9
