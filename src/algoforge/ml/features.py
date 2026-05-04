"""Feature engineering for the ML pipeline.

This is where the real alpha lives. Features matter more than model choice.
Inspired by the feature engineering approaches used at Two Sigma, Citadel,
and documented in Marcos López de Prado's 'Advances in Financial Machine Learning'.
"""

import math

import numpy as np


class FeatureBuilder:
    """Builds a flat feature vector from the current trading system state.

    Produces ~50 features across 7 categories:
    1. Signal family scores + rolling statistics
    2. Lagged signal features
    3. Regime/HMM features
    4. Microstructure features
    5. Price action features
    6. Cross-asset features
    7. Cyclical time features
    """

    FEATURE_NAMES: list[str] = []  # Populated on first build

    @staticmethod
    def build(
        signal_scores: dict[str, float],
        signal_history: dict[str, list[float]] | None = None,
        regime_probs: dict[str, float] | None = None,
        bars_since_regime_change: int = 0,
        vwap_deviation: float = 0.0,
        volume_imbalance: float = 0.0,
        obv_score: float = 0.0,
        volume_ratio: float = 1.0,
        returns_1: float = 0.0,
        returns_5: float = 0.0,
        returns_10: float = 0.0,
        returns_20: float = 0.0,
        volatility_5: float = 0.0,
        volatility_20: float = 0.0,
        atr_ratio: float = 1.0,
        momentum: float = 0.0,
        benchmark_corr: float = 0.0,
        relative_strength: float = 0.0,
        spread_z: float = 0.0,
        sector_momentum: float = 0.0,
        hour: int = 12,
        day_of_week: int = 2,
        month: int = 6,
    ) -> np.ndarray:
        """Build a flat feature vector from the current system state.

        Args:
            signal_scores: Current scores from all signal families.
            signal_history: Rolling history of signal scores (for std calculation).
            regime_probs: HMM state probabilities {bull, bear, sideways}.
            bars_since_regime_change: How many bars since the last regime transition.
            vwap_deviation: Current VWAP deviation score.
            volume_imbalance: Current volume imbalance ratio.
            obv_score: Current OBV divergence score.
            volume_ratio: Current volume / 20-bar average volume.
            returns_*: Returns over various lookback periods.
            volatility_*: Volatility over various lookback periods.
            atr_ratio: ATR(5) / ATR(20) — expansion/contraction indicator.
            momentum: Close - EMA(20).
            benchmark_corr: Rolling correlation with benchmark.
            relative_strength: Relative strength vs sector.
            spread_z: Pairs spread z-score (if applicable).
            sector_momentum: Sector-level momentum.
            hour, day_of_week, month: Time features.

        Returns:
            Numpy array of ~50 features.
        """
        features = []
        names = []

        # --- Category 1: Signal Scores (6 features) ---
        family_order = ["momentum", "mean_reversion", "breakout", "regime", "microstructure", "pairs"]
        for family in family_order:
            features.append(signal_scores.get(family, 0.0))
            names.append(f"sig_{family}")

        # --- Category 2: Rolling Signal Statistics (12 features) ---
        if signal_history:
            for family in family_order:
                history = signal_history.get(family, [])
                if len(history) >= 20:
                    recent = history[-20:]
                    features.append(float(np.std(recent)))
                    features.append(float(np.mean(recent[-5:]) - np.mean(recent)))
                else:
                    features.extend([0.0, 0.0])
                names.append(f"sig_{family}_std20")
                names.append(f"sig_{family}_momentum")
        else:
            features.extend([0.0] * 12)
            for family in family_order:
                names.append(f"sig_{family}_std20")
                names.append(f"sig_{family}_momentum")

        # --- Category 3: Regime Features (4 features) ---
        probs = regime_probs or {"bull": 0.33, "bear": 0.33, "sideways": 0.34}
        features.append(probs.get("bull", 0.33))
        features.append(probs.get("bear", 0.33))
        features.append(probs.get("sideways", 0.34))
        features.append(min(bars_since_regime_change / 100.0, 1.0))  # Normalize
        names.extend(["regime_bull", "regime_bear", "regime_sideways", "regime_recency"])

        # --- Category 4: Microstructure Features (4 features) ---
        features.append(vwap_deviation)
        features.append(volume_imbalance)
        features.append(obv_score)
        features.append(np.log1p(volume_ratio))  # Log-transform to reduce skew
        names.extend(["micro_vwap_dev", "micro_vol_imbalance", "micro_obv", "micro_vol_ratio"])

        # --- Category 5: Price Action Features (8 features) ---
        features.append(returns_1)
        features.append(returns_5)
        features.append(returns_10)
        features.append(returns_20)
        features.append(volatility_5)
        features.append(volatility_20)
        features.append(atr_ratio)
        features.append(momentum)
        names.extend(["ret_1", "ret_5", "ret_10", "ret_20",
                       "vol_5", "vol_20", "atr_ratio", "momentum"])

        # --- Category 6: Cross-Asset Features (4 features) ---
        features.append(benchmark_corr)
        features.append(relative_strength)
        features.append(spread_z)
        features.append(sector_momentum)
        names.extend(["cross_bench_corr", "cross_rel_strength", "cross_spread_z", "cross_sector_mom"])

        # --- Category 7: Alpha158-style Technical Factors (16 features) ---
        # Note: Added for Phase 11. In production, these should be passed from live_handler.py
        # Here we mock them with 0.0 if not provided to avoid breaking the signature
        features.extend([0.0] * 16)
        names.extend([
            "alpha_macd", "alpha_macd_signal", "alpha_macd_hist", "alpha_rsi_14", 
            "alpha_cci_20", "alpha_bollinger_w", "alpha_stoch_k", "alpha_stoch_d",
            "alpha_roc_10", "alpha_williams_r", "alpha_adx_14", "alpha_mfi_14",
            "alpha_trix", "alpha_ult_osc", "alpha_cmf", "alpha_keltner_w"
        ])

        # --- Category 8: Cyclical Time Features (6 features) ---
        # Encode cyclical features as sin/cos to preserve periodicity
        features.append(math.sin(2 * math.pi * hour / 24))
        features.append(math.cos(2 * math.pi * hour / 24))
        features.append(math.sin(2 * math.pi * day_of_week / 5))
        features.append(math.cos(2 * math.pi * day_of_week / 5))
        features.append(math.sin(2 * math.pi * month / 12))
        features.append(math.cos(2 * math.pi * month / 12))
        names.extend(["time_hour_sin", "time_hour_cos", "time_dow_sin",
                       "time_dow_cos", "time_month_sin", "time_month_cos"])

        FeatureBuilder.FEATURE_NAMES = names
        return np.array(features, dtype=np.float64)
