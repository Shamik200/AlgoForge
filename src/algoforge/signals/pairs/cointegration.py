"""Cointegration testing and pair validation."""

import numpy as np


def engle_granger_test(prices_a: list[float], prices_b: list[float]) -> dict:
    """Perform the Engle-Granger two-step cointegration test.

    Step 1: OLS regression of A on B to estimate the hedge ratio.
    Step 2: ADF test on the residuals (spread) to check stationarity.

    Args:
        prices_a: Price series for Asset A.
        prices_b: Price series for Asset B.

    Returns:
        Dict with keys: 'cointegrated' (bool), 'hedge_ratio' (float),
        'p_value' (float), 'spread' (list[float]).
    """
    if len(prices_a) != len(prices_b) or len(prices_a) < 30:
        return {"cointegrated": False, "hedge_ratio": 0.0, "p_value": 1.0, "spread": []}

    a = np.array(prices_a, dtype=float)
    b = np.array(prices_b, dtype=float)

    # Step 1: OLS regression — A = hedge_ratio * B + intercept + residual
    # Using numpy least squares: [B, 1] @ [beta, intercept] = A
    ones = np.ones_like(b)
    X = np.column_stack([b, ones])
    result = np.linalg.lstsq(X, a, rcond=None)
    coeffs = result[0]
    hedge_ratio = float(coeffs[0])
    intercept = float(coeffs[1])

    # Residuals (spread)
    spread = a - (hedge_ratio * b + intercept)

    # Step 2: Simplified ADF test on spread
    # We implement a basic Dickey-Fuller: regress Δspread on spread(t-1)
    # If the t-statistic is sufficiently negative, the spread is stationary.
    delta_spread = np.diff(spread)
    lagged_spread = spread[:-1]

    if len(delta_spread) < 10:
        return {"cointegrated": False, "hedge_ratio": hedge_ratio, "p_value": 1.0,
                "spread": spread.tolist()}

    # OLS: delta_spread = gamma * lagged_spread + error
    X_adf = lagged_spread.reshape(-1, 1)
    gamma_result = np.linalg.lstsq(X_adf, delta_spread, rcond=None)
    gamma = float(gamma_result[0][0])

    # Residual standard error
    residuals_adf = delta_spread - gamma * lagged_spread
    se = np.sqrt(np.sum(residuals_adf ** 2) / (len(residuals_adf) - 1))
    se_gamma = se / np.sqrt(np.sum(lagged_spread ** 2))

    # t-statistic
    t_stat = gamma / se_gamma if se_gamma > 0 else 0.0

    # Approximate p-value using critical values for ADF (n>100)
    # 1%: -3.43, 5%: -2.86, 10%: -2.57
    if t_stat < -3.43:
        p_value = 0.01
    elif t_stat < -2.86:
        p_value = 0.05
    elif t_stat < -2.57:
        p_value = 0.10
    else:
        p_value = 0.50  # Not stationary

    cointegrated = p_value < 0.05

    return {
        "cointegrated": cointegrated,
        "hedge_ratio": hedge_ratio,
        "p_value": p_value,
        "spread": spread.tolist(),
    }
