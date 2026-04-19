"""Feature preprocessing pipeline for the HMM Regime Detector."""

import numpy as np

from algoforge.core.models import OHLCVSeries
from algoforge.technical.indicator_base import ema_calc


def build_features(
    series: OHLCVSeries, 
    cross_asset_features: np.ndarray | None = None
) -> np.ndarray:
    """Build the feature matrix for HMM training and inference.
    
    Extracts returns, realized volatility, volume ratio, and aligns any provided
    cross-asset features.
    
    Args:
        series: Primary asset price series.
        cross_asset_features: Optional array of aligned cross-asset data 
            (e.g., VIX, Yields) with the same length as the series.
            
    Returns:
        A 2D numpy array of shape (n_samples, n_features).
    """
    closes = np.array(series.closes, dtype=np.float64)
    volumes = np.array(series.volumes, dtype=np.float64)
    n = len(closes)
    
    if n < 20:  # Require minimum data for meaningful features
        # Not enough data, return empty array with correct dimensions (e.g. 3 base features + cross asset)
        n_features = 3 + (cross_asset_features.shape[1] if cross_asset_features is not None else 0)
        return np.empty((0, n_features))

    # Feature 1: Log Returns
    # Using log returns instead of simple returns for statistical properties
    returns = np.zeros(n)
    returns[1:] = np.log(closes[1:] / closes[:-1])
    # For index 0, forward fill from index 1 to avoid NaN
    returns[0] = returns[1] if n > 1 else 0.0

    # Feature 2: Realized Volatility (Rolling 20-period std dev of returns)
    realized_vol = np.zeros(n)
    for i in range(n):
        start_idx = max(0, i - 19)
        if i >= 1:
            realized_vol[i] = np.std(returns[start_idx:i+1])
        else:
            realized_vol[i] = 0.0
    
    # Fill early NaNs/zeros with the first valid vol calculation
    if n >= 20:
        realized_vol[:20] = realized_vol[19]

    # Feature 3: Volume Ratio (Volume / 20-period moving average volume)
    vol_ratio = np.ones(n)
    for i in range(n):
        start_idx = max(0, i - 19)
        avg_vol = np.mean(volumes[start_idx:i+1])
        if avg_vol > 0:
            vol_ratio[i] = volumes[i] / avg_vol
            
    # Combine core features
    features_list = [returns.reshape(-1, 1), realized_vol.reshape(-1, 1), vol_ratio.reshape(-1, 1)]
    
    # Append cross-asset features if provided
    if cross_asset_features is not None:
        if len(cross_asset_features) != n:
            msg = f"Cross-asset features length ({len(cross_asset_features)}) does not match series length ({n})"
            raise ValueError(msg)
        features_list.append(cross_asset_features)
        
    return np.hstack(features_list)


def smooth_features(features: np.ndarray, period: int = 5) -> np.ndarray:
    """Apply a fast EMA smoothing to features to prevent regime flip-flopping.
    
    Args:
        features: 2D numpy array of features (n_samples, n_features).
        period: EMA lookback period.
        
    Returns:
        Smoothed 2D numpy array of the same shape.
    """
    if features.shape[0] == 0:
        return features
        
    smoothed = np.empty_like(features)
    for col in range(features.shape[1]):
        # ema_calc handles NaN padding at start, but we want a continuous signal.
        # If we have less data than the period, just return the raw feature.
        col_data = features[:, col]
        if len(col_data) < period:
            smoothed[:, col] = col_data
        else:
            ema_col = ema_calc(col_data, period)
            # Fill the initial NaN values (up to period-1) with the raw data
            nan_mask = np.isnan(ema_col)
            ema_col[nan_mask] = col_data[nan_mask]
            smoothed[:, col] = ema_col
            
    return smoothed


def forward_fill_cross_asset(
    target_timestamps: list[int], 
    cross_asset_timestamps: list[int], 
    cross_asset_values: np.ndarray
) -> np.ndarray:
    """Align cross-asset data using forward-fill to prevent lookahead bias.
    
    Given a list of target timestamps (e.g., 1-minute bars for the primary asset),
    and a sparse/differently-aligned series of cross-asset data (e.g., daily VIX),
    this function aligns them by carrying forward the last known value.
    
    Args:
        target_timestamps: List of epoch timestamps for the primary asset.
        cross_asset_timestamps: List of epoch timestamps for the cross asset.
        cross_asset_values: 2D array of values corresponding to cross_asset_timestamps.
            Shape: (len(cross_asset_timestamps), n_features)
            
    Returns:
        2D array of aligned cross-asset values. Shape: (len(target_timestamps), n_features)
    """
    if not target_timestamps:
        n_features = cross_asset_values.shape[1] if cross_asset_values.ndim > 1 else 1
        return np.empty((0, n_features))
        
    if not cross_asset_timestamps or len(cross_asset_timestamps) == 0:
        msg = "Cross asset timestamps cannot be empty"
        raise ValueError(msg)
        
    if len(cross_asset_timestamps) != len(cross_asset_values):
        msg = "Lengths of cross_asset_timestamps and cross_asset_values must match"
        raise ValueError(msg)
        
    # Ensure 2D
    if cross_asset_values.ndim == 1:
        cross_asset_values = cross_asset_values.reshape(-1, 1)
        
    n_targets = len(target_timestamps)
    n_features = cross_asset_values.shape[1]
    aligned = np.zeros((n_targets, n_features))
    
    # Pointers
    ca_idx = 0
    max_ca_idx = len(cross_asset_timestamps) - 1
    
    # Keep track of the "last known" value
    current_value = cross_asset_values[0].copy()
    
    for i, t_time in enumerate(target_timestamps):
        # Advance the cross-asset pointer until it exceeds the target time.
        # But we must only use data that is <= t_time (no lookahead bias).
        while ca_idx < max_ca_idx and cross_asset_timestamps[ca_idx + 1] <= t_time:
            ca_idx += 1
            current_value = cross_asset_values[ca_idx].copy()
            
        aligned[i] = current_value
        
    return aligned
