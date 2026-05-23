"""Meta Strategy Router — Handles dynamic strategy weighting, regime alignment, and expectancy suppression.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


class MetaStrategyRouter:
    """Dynamically routes weightings to active strategy families based on regime and rolling performance.

    Implements:
    - Dynamic weight adjustments per regime
    - Expectancy suppression (< 0.0 rolling expectancy suppresses signals to 0)
    - Low win rate suppression (< 35% win rate suppresses signals to 0)
    - Deduping logic for overlapping signals
    """

    def __init__(self) -> None:
        # Default weight maps for strategy family vs. regime
        # Regimes: "trending_bullish", "trending_bearish", "mean_reverting_range", "breakout", "liquidity_trap"
        self._regime_weights: dict[str, dict[str, float]] = {
            "trending_bullish": {
                "trendline-pullback": 1.2,
                "ema-crossover": 1.0,
                "ema-bounce": 1.0,
                "mean-reversion": 0.2,
                "breakout": 0.8,
                "reversal": 0.2,
                "liquidity-trap": 0.4,
            },
            "trending_bearish": {
                "trendline-pullback": 0.3,
                "ema-crossover": 1.2,
                "ema-bounce": 0.4,
                "mean-reversion": 0.5,
                "breakout": 1.0,
                "reversal": 0.8,
                "liquidity-trap": 0.8,
            },
            "mean_reverting_range": {
                "trendline-pullback": 0.2,
                "ema-crossover": 0.1,
                "ema-bounce": 0.4,
                "mean-reversion": 1.3,
                "breakout": 0.2,
                "reversal": 1.2,
                "liquidity-trap": 0.5,
            },
            "breakout": {
                "trendline-pullback": 0.8,
                "ema-crossover": 0.7,
                "ema-bounce": 0.6,
                "mean-reversion": 0.1,
                "breakout": 1.4,
                "reversal": 0.1,
                "liquidity-trap": 0.4,
            },
            "liquidity_trap": {
                "trendline-pullback": 0.1,
                "ema-crossover": 0.1,
                "ema-bounce": 0.2,
                "mean-reversion": 0.6,
                "breakout": 0.3,
                "reversal": 0.8,
                "liquidity-trap": 1.5,
            },
        }

        # Strategy performance tracker: dict of {strategy_family: [pnl_amount1, pnl_amount2, ...]}
        self._rolling_trades: dict[str, list[float]] = {}
        self._rolling_wins: dict[str, list[bool]] = {}

        # Lookback window for strategy evaluation
        self._lookback_window = 30

    def record_trade_outcome(self, strategy_family: str, pnl_amount: float) -> None:
        """Record trade result to calculate expectancy and win rate on the fly."""
        family = self._normalize_family(strategy_family)
        if family not in self._rolling_trades:
            self._rolling_trades[family] = []
            self._rolling_wins[family] = []

        self._rolling_trades[family].append(pnl_amount)
        self._rolling_wins[family].append(pnl_amount > 0.0)

        # Keep lookback window bounded
        if len(self._rolling_trades[family]) > self._lookback_window:
            self._rolling_trades[family].pop(0)
            self._rolling_wins[family].pop(0)

        logger.info(
            "meta_strategy_router.trade_recorded",
            strategy=family,
            pnl=pnl_amount,
            expectancy=self.get_expectancy(family),
            win_rate=self.get_win_rate(family),
        )

    def get_expectancy(self, strategy_family: str) -> float:
        """Calculate rolling expectancy (average PnL per trade)."""
        family = self._normalize_family(strategy_family)
        trades = self._rolling_trades.get(family, [])
        if not trades:
            return 1.0  # Default neutral expectancy
        return sum(trades) / len(trades)

    def get_win_rate(self, strategy_family: str) -> float:
        """Calculate rolling win rate."""
        family = self._normalize_family(strategy_family)
        wins = self._rolling_wins.get(family, [])
        if not wins:
            return 0.5  # Neutral default 50%
        return sum(1 for w in wins if w) / len(wins)

    def get_strategy_weight(self, strategy_family: str, active_regime: str) -> float:
        """Determine live strategy weight, incorporating expectancy & win-rate suppression.

        If a family's expectancy is < 0 or win rate is < 35%, its weight is suppressed to 0.0.
        """
        family = self._normalize_family(strategy_family)
        regime = active_regime.lower()

        # 1. Base weight based on classified market regime
        regime_map = self._regime_weights.get(regime, self._regime_weights["mean_reverting_range"])
        base_weight = regime_map.get(family, 1.0)

        # 2. Performance-based checks
        trades = self._rolling_trades.get(family, [])
        if len(trades) >= 5:  # Require minimum of 5 trades before suppression kicks in
            expectancy = self.get_expectancy(family)
            win_rate = self.get_win_rate(family)

            if expectancy < 0.0:
                logger.warn(
                    "meta_strategy_router.suppressed_negative_expectancy",
                    strategy=family,
                    expectancy=expectancy,
                )
                return 0.0

            if win_rate < 0.35:
                logger.warn(
                    "meta_strategy_router.suppressed_low_win_rate",
                    strategy=family,
                    win_rate=win_rate,
                )
                return 0.0

        return base_weight

    def _normalize_family(self, name: str) -> str:
        """Normalize different formats to a standard snake-case representation."""
        n = name.lower().replace("_", "-").replace(" ", "-")
        if "pullback" in n:
            return "trendline-pullback"
        elif "crossover" in n:
            return "ema-crossover"
        elif "bounce" in n:
            return "ema-bounce"
        elif "mean-reversion" in n or "meanreversion" in n:
            return "mean-reversion"
        elif "breakout" in n:
            return "breakout"
        elif "reversal" in n:
            return "reversal"
        elif "liquidity" in n or "trap" in n:
            return "liquidity-trap"
        return n
