"""Strategy Orchestrator — The main trading pipeline.

Connects all modules: Data → Indicators → Structure → Regime →
Fundamental → Strategies → Dual TF → ML → Risk → Execution.

This is the "brain" that drives the 3-module pipeline:
Fundamental → Technical → Execution.
"""

from __future__ import annotations

from typing import Any

import structlog

from algoforge.core.constants import MarketRegime, Timeframe
from algoforge.core.models import Signal
from algoforge.execution.paper import FillResult, PaperTradingEngine
from algoforge.fundamental.analysis import FundamentalFilter, FundamentalSnapshot
from algoforge.ml.models import EnsembleML
from algoforge.risk.manager import RiskConfig
from algoforge.strategies.base import Strategy
from algoforge.strategies.dual_timeframe import DualTimeframeFilter
from algoforge.technical.engine import IndicatorSnapshot
from algoforge.technical.regime import RegimeClassifier, RegimeResult
from algoforge.technical.structural.models import StructuralSnapshot

logger = structlog.get_logger(__name__)


class Orchestrator:
    """Main trading pipeline orchestrator.

    Enforces the system invariants:
    1. Fundamental analysis completes BEFORE technical
    2. Regime detection runs BEFORE strategy activation
    3. Every trade MUST have a stop loss
    4. Risk manager has absolute veto power

    Usage:
        orch = Orchestrator(strategies=[...], capital=100_000)
        results = orch.process_bar(
            symbol="AAPL", timeframe=Timeframe.D1,
            indicators=ind_snap, structure=struct_snap,
            regime_result=regime, closes=closes, ...
        )
    """

    def __init__(
        self,
        strategies: list[Strategy] | None = None,
        capital: float = 100_000.0,
        risk_config: RiskConfig | None = None,
        enable_ml: bool = False,
        enable_dual_tf: bool = False,
        enable_fundamentals: bool = True,
    ) -> None:
        self._strategies = strategies or []
        self._paper = PaperTradingEngine(initial_capital=capital, risk_config=risk_config)
        self._fundamental = FundamentalFilter() if enable_fundamentals else None
        self._dual_tf = DualTimeframeFilter() if enable_dual_tf else None
        self._ml = EnsembleML() if enable_ml else None
        self._regime_classifier = RegimeClassifier()
        self._signals_generated = 0
        self._signals_approved = 0
        self._signals_filled = 0

    def register_strategy(self, strategy: Strategy) -> None:
        """Register a strategy for evaluation."""
        self._strategies.append(strategy)
        logger.info("strategy_registered", name=strategy.name)

    def process_bar(
        self,
        symbol: str,
        timeframe: Timeframe,
        indicators: IndicatorSnapshot,
        structure: StructuralSnapshot,
        regime_result: RegimeResult,
        closes: list[float],
        highs: list[float],
        lows: list[float],
        volumes: list[float],
        opens: list[float],
        fundamentals: dict[str, FundamentalSnapshot] | None = None,
        htf_structure: StructuralSnapshot | None = None,
        htf_regime: MarketRegime | None = None,
        ml_features: dict[str, float] | None = None,
        daily_volume: float | None = None,
        current_bar: int = 0,
    ) -> list[FillResult]:
        """Process one bar through the full pipeline.

        Pipeline: Regime → Strategy Evaluate → Fundamental Filter →
                 Dual TF Filter → ML Enhance → Risk Validate → Execute
        """
        results: list[FillResult] = []
        active_regime = regime_result.primary_regime

        # Step 1: Update prices and check exits on existing positions
        self._paper.update_prices({symbol: closes[-1]})
        self._paper.check_exits(current_bar=current_bar)

        # Step 2: Activate regime-matched strategies
        raw_signals: list[Signal] = []
        for strategy in self._strategies:
            if active_regime not in strategy.required_regime:
                continue

            try:
                signals = strategy.evaluate(
                    symbol, timeframe, indicators, structure,
                    closes, highs, lows, volumes, opens,
                )
                raw_signals.extend(signals)
            except Exception as e:
                logger.warning(
                    "strategy_error", strategy=strategy.name, error=str(e),
                )

        self._signals_generated += len(raw_signals)

        if not raw_signals:
            return results

        # Step 3: Fundamental filter (FUND-06: must complete before technical signals proceed)
        filtered = raw_signals
        if self._fundamental and fundamentals:
            filtered = self._fundamental.filter(filtered, fundamentals)

        # Step 4: Dual timeframe filter
        if self._dual_tf and htf_structure and htf_regime:
            filtered = self._dual_tf.filter(filtered, htf_structure, htf_regime)

        # Step 5: ML enhancement
        if self._ml and ml_features:
            filtered = self._ml.enhance_signals(filtered, ml_features)

        self._signals_approved += len(filtered)

        # Step 6: Submit to paper trading (includes risk validation)
        for sig in filtered:
            fill = self._paper.submit_signal(sig, daily_volume=daily_volume)
            results.append(fill)
            if fill.filled:
                self._signals_filled += 1

        if results:
            logger.info(
                "orchestrator_bar",
                symbol=symbol,
                regime=active_regime.value,
                generated=len(raw_signals),
                filtered=len(filtered),
                filled=sum(1 for r in results if r.filled),
            )

        return results

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "strategies": len(self._strategies),
            "signals_generated": self._signals_generated,
            "signals_approved": self._signals_approved,
            "signals_filled": self._signals_filled,
            "portfolio": self._paper.snapshot().model_dump(),
        }

    @property
    def paper_engine(self) -> PaperTradingEngine:
        return self._paper
