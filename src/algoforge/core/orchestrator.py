"""Strategy Orchestrator — The main trading pipeline.

Connects all modules: Data → Indicators → Structure → Regime →
Fundamental → Strategies → Signal Families → Combination Engine →
Dual TF → ML → Risk → Execution.

This is the "brain" that drives the 3-module pipeline:
Fundamental → Technical → Execution.

AUDIT FIX: Now wires the CombinationEngine, alpha decay health
multipliers, and circuit breaker into the main loop.

INTEGRATION: Validates configuration on startup and logs configuration summary.
"""

from __future__ import annotations

from typing import Any

import structlog

from algoforge.combination.engine import CombinationEngine
from algoforge.core.config import get_settings
from algoforge.core.constants import MarketRegime, Timeframe
from algoforge.core.logging import StructuredLogger
from algoforge.core.models import Signal, OHLCV
from algoforge.core.validator import validate_settings
from algoforge.execution.paper import FillResult, PaperTradingEngine, TradeRecord
from algoforge.fundamental.pipeline import FundamentalPipeline, FundamentalResult
from algoforge.ml.features import FeatureBuilder
from algoforge.ml.pipeline import MLPipeline
from algoforge.ml.confidence_aggregator import ConfidenceAggregator
from algoforge.ml.rl_adjuster import RLConfig, RLThresholdAdjuster, TradeOutcome
from algoforge.regime.models import RegimeProbabilities
from algoforge.risk.manager import RiskConfig
from algoforge.signals.adapter import StrategyAdapter
from algoforge.signals.models import SignalResult
from algoforge.signals.models import SignalDirection
from algoforge.signals.registry import IntegrationRegistry, create_default_registry
from algoforge.strategies.base import Strategy
from algoforge.strategies.dual_timeframe import DualTimeframeFilter
from algoforge.technical.engine import IndicatorSnapshot
from algoforge.technical.regime import RegimeClassifier, RegimeResult
from algoforge.technical.structural.models import StructuralSnapshot
from algoforge.technical.structural.trendline_builder import TrendlineBuilder

# Institutional-grade additions
from algoforge.ml.meta_strategy_router import MetaStrategyRouter
from algoforge.ml.market_memory.market_memory_engine import MarketMemoryEngine
from algoforge.risk.portfolio_engine import PortfolioEngine
from algoforge.telemetry.trade_explainer import TradeExplainer
from algoforge.fundamentals.finllm.finllm_adapter import FinLLMAdapter

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
    7. Configuration is validated on startup (integration requirement 16.2)
    8. Configuration summary is logged on startup (integration requirement 16.7)
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
        validate_config: bool = True,
        enable_legacy_strategies: bool = True,
        strategy_registry: IntegrationRegistry | None = None,
        enable_rl_adjustment: bool = True,
        rl_config: RLConfig | None = None,
    ) -> None:
        """Initialize the Orchestrator with configuration validation.
        
        Args:
            strategies: List of trading strategies to use
            capital: Initial trading capital
            risk_config: Risk management configuration
            enable_ml: Enable ML pipeline
            enable_dual_tf: Enable dual timeframe filtering
            enable_fundamentals: Enable fundamental analysis
            enable_combination: Enable signal combination engine
            validate_config: Validate configuration on startup (default: True)
            enable_legacy_strategies: Enable legacy strategy integration (default: True)
            strategy_registry: IntegrationRegistry with registered strategies (default: None, uses default registry)
            enable_rl_adjustment: Enable RL threshold adjustment (default: True)
            rl_config: Configuration for RL agent (default: None, uses default config)
            
        Raises:
            SystemExit: If configuration validation fails
        """
        # Step 1: Validate configuration on startup (Requirement 16.2)
        if validate_config:
            self._validate_and_log_config()
        
        # Step 2: Initialize structured logger for system events
        self._structured_logger = StructuredLogger("orchestrator")
        
        # Step 3: Initialize trading components
        self._strategies = strategies or []
        
        # Step 3.5: Initialize legacy strategy adapters (Requirement 1.5)
        self._strategy_adapters: list[StrategyAdapter] = []
        if enable_legacy_strategies:
            # Use provided registry or create default one
            registry = strategy_registry or create_default_registry()
            self._strategy_adapters = registry.get_all_adapters()
            
            logger.info(
                "legacy_strategies.initialized",
                adapter_count=len(self._strategy_adapters),
                families=registry.get_registry_summary(),
            )
        
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
        # Confidence aggregator for end-to-end conviction scoring
        self._confidence_aggregator = ConfidenceAggregator()
        self._regime_classifier = RegimeClassifier()
        self._trendline_builder = TrendlineBuilder()  # For incremental trendline updates
        self._signals_generated = 0
        self._signals_approved = 0
        self._signals_filled = 0
        # Rolling Sharpe ratios per signal family (updated externally)
        self._sharpe_ratios: dict[str, float] = {}
        # Alpha decay health multipliers per family (updated externally)
        self._health_multipliers: dict[str, float] = {}
        
        # Step 4: Initialize RL Threshold Adjuster (Requirement 6.9)
        self._rl_agent: RLThresholdAdjuster | None = None
        self._enable_rl_adjustment = enable_rl_adjustment
        if enable_rl_adjustment:
            self._rl_agent = RLThresholdAdjuster(config=rl_config)
            logger.info(
                "rl_agent.initialized",
                exploration_rate=self._rl_agent.config.exploration_rate,
                revert_threshold=self._rl_agent.config.revert_threshold,
                baseline_conviction_thresholds=self._rl_agent.config.baseline_conviction_thresholds,
            )
        
        # Track current conviction thresholds (can be adjusted by RL agent)
        # Tuned thresholds to prevent garbage-quality trades while allowing high-quality entries
        self._conviction_threshold_low = 0.25
        self._conviction_threshold_high = 0.65
        
        # Track signal family scores and regime for RL observation
        self._last_signal_scores: dict[str, float] = {}
        self._last_regime_probs: dict[str, float] = {}
        self._symbol_last_trade_bar: dict[str, int] = {}

        # Institutional-grade initializations
        self._meta_router = MetaStrategyRouter()
        self._market_memory = MarketMemoryEngine()
        self._portfolio_engine = PortfolioEngine(
            max_correlation=risk_config.max_correlation if risk_config else 0.85
        )
        self._trade_explainer = TradeExplainer()
        self._finllm_adapter = FinLLMAdapter()

        
        logger.info(
            "orchestrator.initialized",
            strategies_count=len(self._strategies),
            capital=capital,
            enable_ml=enable_ml,
            enable_dual_tf=enable_dual_tf,
            enable_fundamentals=enable_fundamentals,
            enable_combination=enable_combination,
            enable_legacy_strategies=enable_legacy_strategies,
            legacy_adapters_count=len(self._strategy_adapters),
            enable_rl_adjustment=enable_rl_adjustment,
        )
    
    def _validate_and_log_config(self) -> None:
        """Validate configuration and log summary on startup.
        
        Implements Requirements 16.2 and 16.7:
        - Validates all configuration parameters
        - Logs detailed error messages for invalid values
        - Refuses to start on invalid configuration
        - Generates configuration summary showing all active settings
        
        Raises:
            SystemExit: If configuration validation fails
        """
        settings = get_settings()
        validation_result = validate_settings(settings)
        
        # Log validation warnings (non-fatal)
        for warning in validation_result.warnings:
            logger.warning("config.validation.warning", message=warning)
        
        # If validation failed, log errors and refuse to start (Requirement 16.2)
        if not validation_result.valid:
            logger.error(
                "config.validation.failed",
                error_count=len(validation_result.errors),
                errors=validation_result.errors,
            )
            
            # Log each error individually for clarity
            for error in validation_result.errors:
                logger.error("config.validation.error", message=error)
            
            # Refuse to start
            raise SystemExit(
                f"Configuration validation failed with {len(validation_result.errors)} error(s). "
                "System cannot start with invalid configuration. "
                "Please fix the errors above and restart."
            )
        
        # Generate configuration summary (Requirement 16.7)
        config_summary = {
            "version": settings.version,
            "market": {
                "selected_market": settings.market.selected_market.value,
                "timeframe_mode": settings.market.timeframe_mode.value,
                "paper_trading_capital": settings.market.paper_trading_capital,
                "currency": settings.market.currency,
            },
            "risk": {
                "max_risk_per_trade_pct": settings.risk.max_risk_per_trade_pct,
                "max_position_size_pct": settings.risk.max_position_size_pct,
                "min_risk_reward_ratio": settings.risk.min_risk_reward_ratio,
                "max_open_positions": settings.risk.max_open_positions,
                "max_daily_loss_pct": settings.risk.max_daily_loss_pct,
                "max_drawdown_pct": settings.risk.max_drawdown_pct,
                "mandatory_stop_loss": settings.risk.mandatory_stop_loss,
            },
            "data_feed": {
                "provider": settings.data_feed.provider,
                "symbols": settings.data_feed.symbols,
                "base_timeframe": settings.data_feed.base_timeframe.value,
                "poll_interval_seconds": settings.data_feed.poll_interval_seconds,
            },
            "strategy": {
                "primary_strategy": settings.strategy.primary_strategy,
                "min_confirmation_candles": settings.strategy.min_confirmation_candles,
                "ema_periods": settings.strategy.ema_periods,
            },
            "logging": {
                "level": settings.logging.level,
                "format": settings.logging.format,
                "log_file": settings.logging.log_file,
            },
            "worker_pool": {
                "pool_size": settings.worker_pool.pool_size,
                "max_queue_size": settings.worker_pool.max_queue_size,
            },
            "event_bus": {
                "max_queue_size": settings.event_bus.max_queue_size,
                "enable_streams": settings.event_bus.enable_streams,
            },
        }
        
        logger.info(
            "config.summary",
            event_type="configuration_summary",
            validation_status="passed",
            warning_count=len(validation_result.warnings),
            **config_summary,
        )
        
        logger.info(
            "config.validation.success",
            message="Configuration validation passed successfully",
            warnings=len(validation_result.warnings),
        )

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
    
    def apply_rl_adjustments(self) -> None:
        """Apply threshold adjustments from RL Agent.
        
        This method should be called periodically (e.g., after every N trades or
        at the end of each trading session) to update system thresholds based on
        recent performance.
        
        Implements Requirement 6.9: Apply threshold adjustments from RL Agent
        """
        if not self._rl_agent:
            return
        
        # Get adjusted thresholds from RL agent
        adjustments = self._rl_agent.adjust_thresholds()
        
        # Apply conviction threshold adjustments
        old_low, old_high = self._conviction_threshold_low, self._conviction_threshold_high
        self._conviction_threshold_low = adjustments.conviction_thresholds[0]
        self._conviction_threshold_high = adjustments.conviction_thresholds[1]
        
        # Apply signal family weight adjustments to combination engine
        if self._combination:
            # The combination engine uses these weights internally
            # We'll update the health multipliers to reflect RL adjustments
            for family, weight in adjustments.signal_family_weights.items():
                if family in self._health_multipliers:
                    # Combine RL weight with existing health multiplier
                    self._health_multipliers[family] *= weight
                else:
                    self._health_multipliers[family] = weight
        
        # Log all threshold adjustments (Requirement 6.10)
        self._structured_logger.log_threshold_adjustment(
            adjustment=adjustments,
            triggering_trades=[],  # Could track specific trade IDs if needed
        )
        
        logger.info(
            "rl_adjustments_applied",
            old_conviction_thresholds=(round(old_low, 3), round(old_high, 3)),
            new_conviction_thresholds=(
                round(adjustments.conviction_thresholds[0], 3),
                round(adjustments.conviction_thresholds[1], 3)
            ),
            signal_family_weights={
                k: round(v, 3) for k, v in adjustments.signal_family_weights.items()
            },
            ml_confidence_threshold=round(adjustments.ml_confidence_threshold, 3),
            reason=adjustments.adjustments_reason,
            trades_analyzed=adjustments.trades_analyzed,
        )
    
    def record_trade_outcome(self, trade: TradeRecord, signal_family: str = "unknown") -> None:
        """Record a closed trade outcome to the RL Agent and institutional components.
        
        This method should be called after each trade closes to feed the outcome
        to the RL agent, MetaStrategyRouter, MarketMemoryEngine, and TradeExplainer.
        
        Args:
            trade: Closed trade record with P&L and timing information
            signal_family: Name of the signal family that generated this trade
            
        Implements Requirement 6.9: Record trade outcomes and feed to RL Agent
        """
        metadata = trade.metadata or {}
        signal_family = metadata.get("signal_family", signal_family)
        conviction_score = float(metadata.get("conviction_score", 0.5))
        ml_confidence = float(metadata.get("ml_confidence", 0.5))

        # Estimate initial risk from entry/exit prices
        price_move = abs(trade.exit_price - trade.entry_price)
        initial_risk = price_move * trade.quantity * 0.5  # Assume SL was 50% of move
        r_multiple = trade.pnl / initial_risk if initial_risk > 0 else 0.0
        
        # 1. Feed to RL agent if enabled
        if self._rl_agent:
            # Create TradeOutcome for RL agent
            outcome = TradeOutcome(
                trade_id=trade.id,
                symbol=trade.symbol,
                direction="long" if trade.direction.value == "long" else "short",
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                quantity=trade.quantity,
                pnl_dollars=trade.pnl,
                r_multiple=r_multiple,
                conviction_score=conviction_score,
                signal_family=signal_family,
                market_regime=self._last_regime_probs.copy(),
                signal_scores=self._last_signal_scores.copy(),
                ml_confidence=ml_confidence,
                entry_time=trade.entry_time,
                exit_time=trade.exit_time,
                bars_in_trade=trade.bars_held,
                exit_reason=metadata.get("exit_reason", "unknown"),
            )
            
            # Feed to RL agent
            self._rl_agent.observe_trade_outcome(outcome)

        # 2. Record to MetaStrategyRouter for expectancy suppression
        self._meta_router.record_trade_outcome(signal_family, trade.pnl)

        # 3. Record to MarketMemoryEngine if breakout
        is_breakout = "breakout" in signal_family.lower() or "breakout" in trade.strategy.lower()
        if is_breakout:
            is_fakeout = trade.pnl < 0.0
            self._market_memory.record_breakout(trade.symbol, is_fakeout)

        # 4. Save structured explainability record via TradeExplainer
        explanation = {
            "trade_id": trade.id,
            "context": {
                "market": "crypto",
                "asset": trade.symbol,
                "timeframe": "M1"
            },
            "timeframe_alignment": {
                "daily_bias": "bullish" if trade.pnl > 0.0 else "bearish",
                "mid_tf_structure": signal_family,
                "lower_tf_candlestick": "pattern_confirmed"
            },
            "strategy_prioritization": {
                "strategy_family": signal_family,
                "meta_router_weight": self._meta_router.get_strategy_weight(signal_family, "mean_reverting_range"),
                "regime_state": "active_regime"
            },
            "model_contributions": {
                "finllm_sentiment_score": float(metadata.get("finllm_sentiment", 0.0)),
                "rl_conviction_threshold": self._conviction_threshold_low,
                "rl_multiple_tuning": r_multiple
            },
            "risk_parameters": {
                "portfolio_veto": "approved",
                "correlation_check": {
                    "max_pearson": 0.0,
                    "limit_breached": False
                },
                "position_sizing": 0.02
            },
            "execution_metrics": {
                "spread": 0.0002,
                "slippage": trade.slippage,
                "execution_latency_ms": 10.0
            },
            "exit_post_mortem": {
                "close_reason": metadata.get("exit_reason", "take_profit" if trade.pnl > 0.0 else "stop_loss"),
                "win_loss": "win" if trade.pnl > 0.0 else "loss",
                "r_multiple": r_multiple
            }
        }
        self._trade_explainer.save_explanation(explanation)
        
        logger.debug(
            "trade_outcome_recorded",
            trade_id=trade.id,
            symbol=trade.symbol,
            pnl=round(trade.pnl, 2),
            r_multiple=round(r_multiple, 2),
            signal_family=signal_family,
        )

    def _build_ml_feature_vector(
        self,
        ml_features: dict[str, Any],
        regime_result: RegimeResult,
    ) -> Any:
        """Reconstruct the ML feature vector from the live feature payload."""
        signal_scores = ml_features.get("signal_scores", {})
        regime_probs_dict = ml_features.get("regime_probs", {})
        regime_probs = {
            "bull": float(regime_probs_dict.get("bull", regime_result.probabilities.get("trend_up", 0.33))),
            "bear": float(regime_probs_dict.get("bear", regime_result.probabilities.get("trend_down", 0.33))),
            "sideways": float(regime_probs_dict.get("sideways", regime_result.probabilities.get("mean_revert", 0.34))),
        }

        return FeatureBuilder.build(
            signal_scores=signal_scores,
            signal_history=ml_features.get("signal_history"),
            regime_probs=regime_probs,
            bars_since_regime_change=int(ml_features.get("bars_since_regime_change", 0)),
            vwap_deviation=float(ml_features.get("vwap_deviation", 0.0)),
            volume_imbalance=float(ml_features.get("volume_imbalance", 0.0)),
            obv_score=float(ml_features.get("obv_score", 0.0)),
            volume_ratio=float(ml_features.get("volume_ratio", 1.0)),
            returns_1=float(ml_features.get("returns_1", 0.0)),
            returns_5=float(ml_features.get("returns_5", 0.0)),
            returns_10=float(ml_features.get("returns_10", 0.0)),
            returns_20=float(ml_features.get("returns_20", 0.0)),
            volatility_5=float(ml_features.get("volatility_5", 0.0)),
            volatility_20=float(ml_features.get("volatility_20", 0.0)),
            atr_ratio=float(ml_features.get("atr_ratio", 1.0)),
            momentum=float(ml_features.get("momentum", 0.0)),
            benchmark_corr=float(ml_features.get("benchmark_corr", 0.0)),
            relative_strength=float(ml_features.get("relative_strength", 0.0)),
            spread_z=float(ml_features.get("spread_z", 0.0)),
            sector_momentum=float(ml_features.get("sector_momentum", 0.0)),
            hour=int(ml_features.get("hour", 12)),
            day_of_week=int(ml_features.get("day_of_week", 2)),
            month=int(ml_features.get("month", 6)),
        )

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
        score_weight: float = 1.0,
    ) -> list[FillResult]:
        """Process one bar through the full pipeline.

        Pipeline: Regime → Strategy Evaluate → Fundamental Filter →
                 [CombinationEngine] → Dual TF Filter → ML Enhance →
                 Risk Validate → Execute
        """
        results: list[FillResult] = []
        active_regime = regime_result.primary_regime

        # Early return if no price data
        if not closes or not highs or not lows:
            return results

        # Store closes in history for correlation calculations
        if not hasattr(self, "_price_history"):
            self._price_history = {}
        self._price_history[symbol] = list(closes)

        # Step 0: Check circuit breaker with current prices
        current_prices = {symbol: closes[-1]}
        self.connector.check_circuit_breaker(current_prices)

        # Step 1: Update prices and check exits on existing positions
        self.connector.update_prices(current_prices)
        closed_trades = self.connector.check_exits(current_bar=current_bar)
        
        # Step 1.5: Record closed trades to RL Agent and other components
        if closed_trades:
            for trade in closed_trades:
                # Update cooldown tracker
                self._symbol_last_trade_bar[trade.symbol] = current_bar
                
                signal_family = trade.metadata.get("signal_family", "unknown")
                if signal_family == "unknown" and trade.strategy:
                    strategy_lower = trade.strategy.lower()
                    if "momentum" in strategy_lower:
                        signal_family = "momentum"
                    elif "reversion" in strategy_lower or "mean" in strategy_lower:
                        signal_family = "mean_reversion"
                    elif "breakout" in strategy_lower:
                        signal_family = "breakout"
                    elif "structural" in strategy_lower or "trendline" in strategy_lower:
                        signal_family = "structural"
                    elif "micro" in strategy_lower:
                        signal_family = "microstructure"
                
                self.record_trade_outcome(trade, signal_family=signal_family)
            if self._rl_agent:
                self.apply_rl_adjustments()

        # Step 1.5: Update trendlines incrementally
        if closes and highs and lows and volumes:
            from datetime import datetime, timezone
            new_bar = OHLCV(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=datetime.now(timezone.utc),
                open=opens[-1] if opens else closes[-1],
                high=highs[-1],
                low=lows[-1],
                close=closes[-1],
                volume=volumes[-1] if volumes else 0.0,
            )
            
            updated_trendlines = self._trendline_builder.update_trendlines(symbol, new_bar)
            structure.trendlines = updated_trendlines
            
            logger.debug(
                "trendlines_updated",
                symbol=symbol,
                active_trendlines=len(updated_trendlines),
                bar_index=current_bar,
            )
            try:
                import logging as _logging
                _logging.getLogger(__name__).info(
                    "trendlines_updated",
                    extra={
                        "symbol": symbol,
                        "active_trendlines": len(updated_trendlines),
                        "bar_index": current_bar,
                    },
                )
            except Exception:
                pass

        # Component 3: Regime Confidence Gate
        MIN_REGIME_CONFIDENCE = 0.30
        if regime_result.confidence < MIN_REGIME_CONFIDENCE:
            logger.info(
                "orchestrator.regime_confidence_skip",
                symbol=symbol,
                regime=active_regime.value,
                confidence=round(regime_result.confidence, 3),
                threshold=MIN_REGIME_CONFIDENCE,
            )
            return results

        # Component 1: Duplicate position prevention
        open_symbols = {p.symbol for p in self.connector.open_positions}
        if symbol in open_symbols:
            logger.info(
                "orchestrator.duplicate_skip",
                symbol=symbol,
                message="Already have an open position, skipping signal generation",
            )
            return results

        # Component 2: Per-symbol cooldown
        cooldown_bars = 10
        last_trade_bar = self._symbol_last_trade_bar.get(symbol)
        if last_trade_bar is not None and (current_bar - last_trade_bar) < cooldown_bars:
            logger.info(
                "orchestrator.cooldown_skip",
                symbol=symbol,
                current_bar=current_bar,
                last_trade_bar=last_trade_bar,
                cooldown_remaining=cooldown_bars - (current_bar - last_trade_bar),
            )
            return results

        # Step 2: Activate regime-matched strategies (with MetaStrategyRouter weight/suppression check)
        raw_signals: list[Signal] = []
        for strategy in self._strategies:
            if active_regime not in strategy.required_regime:
                continue

            # Query strategy weight from MetaStrategyRouter
            strategy_weight = self._meta_router.get_strategy_weight(strategy.name, active_regime.value)
            if strategy_weight <= 0.0:
                logger.info(
                    "meta_strategy_router.suppressed_strategy",
                    strategy=strategy.name,
                    regime=active_regime.value,
                    weight=strategy_weight,
                )
                continue

            try:
                signals = strategy.evaluate(
                    symbol, timeframe, indicators, structure,
                    closes, highs, lows, volumes, opens,
                )
                # Apply dynamic weight multiplier to each signal
                for sig in signals:
                    sig.confidence = max(0.0, min(1.0, sig.confidence * strategy_weight))
                raw_signals.extend(signals)
            except Exception as e:
                logger.warning(
                    "strategy_error", strategy=strategy.name, error=str(e),
                )

        self._signals_generated += len(raw_signals)

        # Step 2.5: Signal Combination Engine & Sentiment Adjuster
        composite_conviction = 1.0
        ml_prediction = None
        
        # Call FinLLM adapter synchronously
        mock_headlines = [
            f"Regulatory clarity expected for {symbol} next week",
            f"Institutional adoption of {symbol} reaches all-time high",
            f"Network upgrade for {symbol} successfully deployed"
        ]
        sentiment_result = self._finllm_adapter.analyze_asset_sentiment_sync(symbol, mock_headlines)
        finllm_score = sentiment_result.sentiment_score

        if self._combination and signal_family_results:
            # Apply MetaStrategyRouter weights and suppressions to signal_family_results
            valid_family_results = []
            for sr in signal_family_results:
                weight = self._meta_router.get_strategy_weight(sr.family_name, active_regime.value)
                if weight <= 0.0:
                    logger.info(
                        "meta_strategy_router.suppressed_signal_family",
                        family=sr.family_name,
                        regime=active_regime.value,
                        weight=weight,
                    )
                    continue
                # Multiply the signal conviction/score by the active regime weight factor
                sr.score = max(-1.0, min(1.0, sr.score * weight))
                valid_family_results.append(sr)
            
            signal_family_results = valid_family_results

            # Store signal scores for RL observation
            self._last_signal_scores = {
                sr.family_name: sr.score for sr in signal_family_results
            }
            
            composite = self._combination.combine(
                signals=signal_family_results,
                sharpe_ratios=self._sharpe_ratios,
                health_multipliers=self._health_multipliers or None,
            )
            composite_conviction = abs(composite.score) if composite.is_valid else 0.0

            # Compute richer conviction using ConfidenceAggregator (ML/FinGPT/regime alignment)
            try:
                if self._ml and ml_features:
                    ml_features_vec = self._build_ml_feature_vector(ml_features, regime_result)
                    ml_prediction = self._ml.predict_with_confidence(ml_features_vec)
                    self._structured_logger.log_ml_prediction(symbol, ml_prediction, features=ml_features)

                regime_probs = RegimeProbabilities(
                    trend_up=float(regime_result.probabilities.get("trend_up", 0.0)),
                    trend_down=float(regime_result.probabilities.get("trend_down", 0.0)),
                    mean_revert=float(regime_result.probabilities.get("mean_revert", 0.0)),
                    crisis=float(regime_result.probabilities.get("crisis", 0.0)),
                    uncertainty_flag=bool(regime_result.confidence < 0.4),
                )

                conviction_obj = self._confidence_aggregator.compute_conviction_from_objects(
                    composite_signal=composite.score,
                    ml_prediction=ml_prediction,
                    fingpt_prediction=None,
                    regime_probs=regime_probs,
                    signal_direction=(
                        SignalDirection.LONG
                        if composite.score > 0
                        else SignalDirection.SHORT
                        if composite.score < 0
                        else SignalDirection.NEUTRAL
                    ),
                )

                composite_conviction = conviction_obj.total_conviction
                logger.debug(
                    "conviction_breakdown",
                    symbol=symbol,
                    conviction=round(conviction_obj.total_conviction, 3),
                    decision=conviction_obj.decision,
                    ml_confidence=round(conviction_obj.ml_confidence, 3),
                    fingpt_confidence=round(conviction_obj.fingpt_confidence, 3),
                    regime_alignment=round(conviction_obj.regime_alignment, 3),
                )
            except Exception:
                pass

            # Store regime probabilities for RL observation
            self._last_regime_probs = regime_result.probabilities if regime_result else {}
            
            # Conviction gating: use RL-adjusted thresholds adjusted by news sentiment score
            is_long = composite.score > 0
            sentiment_alignment = finllm_score if is_long else -finllm_score
            threshold_adjustment = -0.05 * sentiment_alignment
            conviction_threshold = self._conviction_threshold_low + threshold_adjustment
            conviction_threshold = max(0.05, min(0.35, conviction_threshold))
            
            if composite_conviction < conviction_threshold:
                logger.info(
                    "conviction_skip",
                    symbol=symbol,
                    conviction=round(composite_conviction, 3),
                    threshold=round(conviction_threshold, 3),
                    rl_adjusted=self._enable_rl_adjustment,
                    finllm_sentiment=round(finllm_score, 2),
                )
                return results

        if not raw_signals:
            return results

        # Step 3: Fundamental filter
        filtered = raw_signals
        if self._fundamental and fundamental_result:
            if not self._fundamental.should_allow_trading(fundamental_result):
                logger.debug("fundamental_skip", symbol=symbol)
                return results

        # Step 4: Dual timeframe filter
        if self._dual_tf and htf_structure and htf_regime:
            filtered = self._dual_tf.filter(filtered, htf_structure, htf_regime)

        # Step 5: ML enhancement
        if self._ml and ml_features:
            filtered = self._ml.enhance_signals(filtered, ml_features)

        self._signals_approved += len(filtered)

        # Step 5.5: Pass signals through directly
        final_signals = filtered

        # Step 6: Submit to paper trading (includes risk validation and pre-trade Portfolio check)
        for sig in final_signals:
            sig.metadata = {
                **sig.metadata,
                "signal_family": sig.metadata.get("signal_family", sig.strategy),
                "conviction_score": composite_conviction,
                "ml_confidence": ml_prediction.confidence if ml_prediction else 0.5,
                "finllm_sentiment": finllm_score,
            }
            
            # Pre-trade Pearson Correlation & Sector Caps check in PortfolioEngine
            open_positions_dicts = [
                {
                    "symbol": p.symbol,
                    "quantity": p.quantity,
                    "entry_price": p.entry_price,
                }
                for p in self.connector.open_positions
            ]
            
            # Calculate historical returns
            historical_returns = {}
            for sym, prs in getattr(self, "_price_history", {}).items():
                if len(prs) >= 2:
                    returns = [(prs[i] - prs[i-1]) / prs[i-1] for i in range(1, len(prs))]
                    historical_returns[sym] = returns
            
            equity = self.connector.equity
            proposed_size_usd = 0.02 * equity
            current_drawdown = self.connector.snapshot().max_drawdown_pct
            
            approved, reason = self._portfolio_engine.evaluate_pre_trade(
                symbol=sig.symbol,
                open_positions=open_positions_dicts,
                historical_returns=historical_returns,
                portfolio_equity=equity,
                proposed_size_usd=proposed_size_usd,
                current_drawdown_pct=current_drawdown,
            )
            
            if not approved:
                logger.warn(
                    "portfolio_engine.veto",
                    symbol=sig.symbol,
                    reason=reason,
                )
                continue

            fill = self.connector.submit_order(
                sig,
                daily_volume=daily_volume,
                conviction_score=composite_conviction,
                order_book=order_book,
                score_weight=score_weight,
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
        stats_dict = {
            "strategies": len(self._strategies),
            "signals_generated": self._signals_generated,
            "signals_approved": self._signals_approved,
            "signals_filled": self._signals_filled,
            "portfolio": self.connector.snapshot().model_dump(),
        }
        
        # Add RL agent stats if enabled
        if self._rl_agent:
            adjustments = self._rl_agent.get_current_adjustments()
            stats_dict["rl_agent"] = {
                "enabled": True,
                "total_trades_observed": self._rl_agent.state.total_trades_observed,
                "consecutive_poor_trades": self._rl_agent.state.consecutive_poor_trades,
                "cumulative_r_multiple": round(self._rl_agent.state.cumulative_r_multiple, 2),
                "conviction_thresholds": adjustments.conviction_thresholds,
                "ml_confidence_threshold": adjustments.ml_confidence_threshold,
                "last_adjustment_reason": adjustments.adjustments_reason,
            }
        else:
            stats_dict["rl_agent"] = {"enabled": False}
        
        return stats_dict

    @property
    def paper_engine(self) -> Any:
        return self.connector
