"""Strategy Orchestrator — The main trading pipeline.

Connects all modules: Data → Indicators → Structure → Regime →
Fundamental → Strategies → Signal Families → Combination Engine →
Dual TF → ML → Risk → Execution.

This is the "brain" that drives the 3-module pipeline:
Fundamental → Technical → Execution.

AUDIT FIX: Now wires the CombinationEngine, alpha decay health
multipliers, and circuit breaker into the main loop.
"""

from __future__ import annotations

from typing import Any

import structlog

from algoforge.combination.engine import CombinationEngine
from algoforge.core.constants import MarketRegime, Timeframe
from algoforge.core.models import Signal
from algoforge.execution.paper import FillResult, PaperTradingEngine
from algoforge.fundamental.pipeline import FundamentalPipeline, FundamentalResult
from algoforge.ml.pipeline import MLPipeline
from algoforge.risk.manager import RiskConfig
from algoforge.signals.models import SignalResult
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
    5. Signal families pass through CombinationEngine (audit fix)
    6. Circuit breaker is checked every bar (audit fix)
    """

    def __init__(
        self,
        strategies: list[Strategy] | None = None,
        capital: float = 100_000.0,
        risk_config: RiskConfig | None = None,
        enable_ml: bool = False,
        enable_dual_tf: bool = False,
        enable_fundamentals: bool = True,
        enable_combination: bool = True,
    ) -> None:
        self._strategies = strategies or []
        from algoforge.core.constants import Market
        from algoforge.execution.paper import PaperTradingEngine
        from algoforge.connectors.factory import ConnectorFactory
        from algoforge.execution.reconciliation import ReconciliationEngine
        
        paper_engine = PaperTradingEngine(initial_capital=capital, market=Market.CRYPTO, risk_config=risk_config)
        self.connector = ConnectorFactory.create(mode="paper", paper_engine=paper_engine)
        
        self._reconciliation = ReconciliationEngine()
        
        self._fundamental = FundamentalPipeline() if enable_fundamentals else None
        self._dual_tf = DualTimeframeFilter() if enable_dual_tf else None
        self._ml = MLPipeline(train_size=1000, test_size=200, forward_bars=5) if enable_ml else None
        self._combination = CombinationEngine() if enable_combination else None
        self._regime_classifier = RegimeClassifier()
        self._signals_generated = 0
        self._signals_approved = 0
        self._signals_filled = 0
        # Rolling Sharpe ratios per signal family (updated externally)
        self._sharpe_ratios: dict[str, float] = {}
        # Alpha decay health multipliers per family (updated externally)
        self._health_multipliers: dict[str, float] = {}

    def register_strategy(self, strategy: Strategy) -> None:
        """Register a strategy for evaluation."""
        self._strategies.append(strategy)
        logger.info("strategy_registered", name=strategy.name)

    def update_sharpe_ratios(self, ratios: dict[str, float]) -> None:
        """Update rolling Sharpe ratios for signal family weighting."""
        self._sharpe_ratios.update(ratios)

    def update_health_multipliers(self, multipliers: dict[str, float]) -> None:
        """Update alpha decay health multipliers from the decay monitor."""
        self._health_multipliers.update(multipliers)

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
        fundamental_result: FundamentalResult | None = None,
        htf_structure: StructuralSnapshot | None = None,
        htf_regime: MarketRegime | None = None,
        ml_features: dict[str, float] | None = None,
        daily_volume: float | None = None,
        current_bar: int = 0,
        signal_family_results: list[SignalResult] | None = None,
        order_book: dict | None = None,
    ) -> list[FillResult]:
        """Process one bar through the full pipeline.

        Pipeline: Regime → Strategy Evaluate → Fundamental Filter →
                 [CombinationEngine] → Dual TF Filter → ML Enhance →
                 Risk Validate → Execute

        Args:
            signal_family_results: Pre-computed signal family outputs.
                If provided, these go through the CombinationEngine
                for composite scoring and health throttling.
            order_book: Optional live order book data for realistic slippage.
        """
        results: list[FillResult] = []
        active_regime = regime_result.primary_regime

        # Step 0: Check circuit breaker with current prices
        current_prices = {symbol: closes[-1]}
        self.connector.check_circuit_breaker(current_prices)

        # Step 1: Update prices and check exits on existing positions
        self.connector.update_prices(current_prices)
        self.connector.check_exits(current_bar=current_bar)

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

        # Step 2.5: Signal Combination Engine (AUDIT FIX — was dead code)
        composite_conviction = 1.0
        if self._combination and signal_family_results:
            composite = self._combination.combine(
                signals=signal_family_results,
                sharpe_ratios=self._sharpe_ratios,
                health_multipliers=self._health_multipliers or None,
            )
            composite_conviction = abs(composite.score) if composite.is_valid else 0.0

            # Conviction gating: skip if composite too weak
            if composite_conviction < 0.3:
                logger.debug(
                    "conviction_skip",
                    symbol=symbol,
                    conviction=round(composite_conviction, 3),
                )
                return results

        if not raw_signals:
            return results

        # Step 3: Fundamental filter (AUDIT FIX: Uses new Pipeline logic)
        filtered = raw_signals
        if self._fundamental and fundamental_result:
            if not self._fundamental.should_allow_trading(fundamental_result):
                logger.debug("fundamental_skip", symbol=symbol)
                return results  # Trading blocked by fundamental gate

        # Step 4: Dual timeframe filter
        if self._dual_tf and htf_structure and htf_regime:
            filtered = self._dual_tf.filter(filtered, htf_structure, htf_regime)

        # Step 5: ML enhancement
        if self._ml and ml_features:
            filtered = self._ml.enhance_signals(filtered, ml_features)

        self._signals_approved += len(filtered)

        # Step 6: Submit to paper trading (includes risk validation)
        for sig in filtered:
            fill = self.connector.submit_order(
                sig,
                daily_volume=daily_volume,
                conviction=composite_conviction,
                order_book=order_book,
            )
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
                conviction=round(composite_conviction, 3),
            )

        return results

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "strategies": len(self._strategies),
            "signals_generated": self._signals_generated,
            "signals_approved": self._signals_approved,
            "signals_filled": self._signals_filled,
            "portfolio": self.connector.snapshot().model_dump(),
        }

    @property
    def paper_engine(self) -> Any:
        return self.connector
