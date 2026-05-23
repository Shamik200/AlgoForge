"""Live Tick Handler — Processes WebSocket market data through the full pipeline.

Extracted from server.py handle_live_tick(). Processes each closed kline
through: Indicators → Structure → Regime → Signal Families → ML Features
→ Strategy Evaluation → Order Execution.

This is the hot path — every 1-minute kline close runs through here.

Phase 6 upgrade: All 5 signal families are now computed and fed through the
CombinationEngine for composite conviction scoring.
"""

from __future__ import annotations

from typing import Callable, Awaitable

import numpy as np
import structlog

from algoforge.core.constants import Timeframe
from algoforge.core.models import OHLCV, OHLCVSeries
from algoforge.core.error_recovery import ErrorRecoveryManager
from algoforge.core.pairs_coordinator import PairTradingCoordinator
from algoforge.core.timeframe_coordinator import TimeframeCoordinator
from algoforge.engine.state import SystemState, log_msg
from algoforge.regime.models import RegimeProbabilities
from algoforge.signals.models import SignalResult
from algoforge.signals.momentum.signal import MomentumSignal
from algoforge.signals.reversion.signal import MeanReversionSignal
from algoforge.signals.breakout.signal_volatility import VolatilityBreakoutSignal
from algoforge.signals.structural.signal import StructuralConfluenceSignal
from algoforge.signals.microstructure.family import MicrostructureFamily

logger = structlog.get_logger(__name__)

# ── Signal Family Singletons (stateful — maintain rolling buffers) ────────
_momentum_signal = MomentumSignal(tsmom_lookback=60, tsmom_skip=5)  # Adapted for 1m bars
_mean_reversion_signal = MeanReversionSignal(vwap_period=20)
_breakout_signal = VolatilityBreakoutSignal(period=20, min_squeeze_duration=3)
_structural_signal = StructuralConfluenceSignal(atr_period=14, vol_sma_period=20)
_microstructure_family = MicrostructureFamily(timeframe="1m", deviation_threshold=1.5)
_timeframe_coordinator = TimeframeCoordinator()
_pairs_coordinator = PairTradingCoordinator()
_error_recovery = ErrorRecoveryManager()


async def handle_live_tick(
    state: SystemState,
    data: dict,
    broadcast_fn: Callable[[], Awaitable[None]],
) -> None:
    """Process a single live tick (book update or kline close).

    Args:
        state: Shared system state.
        data: Tick data from exchange adapter.
        broadcast_fn: Async function to broadcast telemetry after state changes.
    """
    sym = data["symbol"]

    # 1. ORDER BOOK UPDATE (Bid/Ask)
    if data["type"] == "book":
        state.live_books[sym] = {
            "bid": data["bid"],
            "ask": data["ask"],
            "bid_qty": data.get("bid_qty", float("inf")),
            "ask_qty": data.get("ask_qty", float("inf"))
        }
        if state.connector:
            state.connector.update_prices({sym: data["bid"]})
            state.connector.check_circuit_breaker({sym: data["bid"]})
            closed_trades = state.connector.check_exits()
            for trade in closed_trades:
                log_msg(state, f"POSITION CLOSED: {trade.symbol} at ${trade.exit_price:.2f} | PnL: ${trade.pnl:.2f}")
                # Phase 4: Persist closed trade to SQLite
                state.persist_trade(trade)
                await broadcast_fn()

    # 2. KLINE CLOSE — full pipeline
    elif data["type"] == "kline" and data["is_closed"]:
        if sym not in state.kline_buffers:
            return

        candle = OHLCV(
            symbol=sym, timeframe=Timeframe.M1, timestamp=data["timestamp"],
            open=data["open"], high=data["high"], low=data["low"],
            close=data["price"], volume=data["volume"]
        )
        state.kline_buffers[sym].append(candle)
        if len(state.kline_buffers[sym]) > 300:
            state.kline_buffers[sym].pop(0)

        try:
            series = OHLCVSeries(
                symbol=sym, timeframe=Timeframe.M1,
                candles=state.kline_buffers[sym]
            )

            # ── STEP 1: INDICATORS ──────────────────────────────────
            indicators = state.indicator_engine.compute(series)

            # ── STEP 2: STRUCTURAL ANALYSIS ─────────────────────────
            ema_res = indicators.get("ema")
            ema_vals = ema_res.values if ema_res else None
            atr_res = indicators.get("atr")
            atr_vals = atr_res.values.get("atr", []) if atr_res else None
            structure = state.structural_engine.analyze(
                series, ema_values=ema_vals, atr_values=atr_vals
            )

            # ── STEP 3: REGIME CLASSIFICATION ───────────────────────
            adx_res = indicators.get("adx")
            bb_res = indicators.get("bollinger")
            adx_vals = adx_res.values.get("adx", []) if adx_res else []
            adx_pdi = adx_res.values.get("plus_di", []) if adx_res else []
            adx_mdi = adx_res.values.get("minus_di", []) if adx_res else []
            bb_w = bb_res.values.get("bandwidth", []) if bb_res else []

            regime_result = state.regime_classifier.classify(
                symbol=sym,
                adx=adx_vals[-1] if adx_vals else None,
                plus_di=adx_pdi[-1] if adx_pdi else None,
                minus_di=adx_mdi[-1] if adx_mdi else None,
                bb_bandwidth=bb_w[-1] if bb_w else None,
                atr_current=atr_vals[-1] if atr_vals else None,
                volume_ratio=(
                    series.volumes[-1] / np.mean(series.volumes[-20:])
                ) if series.count > 20 else 1.0,
                price=series.closes[-1] if series.count > 0 else None,
            )
            regime_name = regime_result.primary_regime.value
            state.asset_regimes[sym] = regime_name
            state.asset_confidence[sym] = round(regime_result.confidence, 3)
            log_msg(state, f"[{sym}] REGIME: {regime_name} (conf={regime_result.confidence:.2f})")

            # ── STEP 4: SIGNAL FAMILIES (Phase 6 — was dead code!) ─────
            signal_family_results = _compute_signal_families(
                series, indicators, structure, regime_result,
                order_book=state.live_books.get(sym),
            )

            # ── STEP 4.5: MULTI-TIMEFRAME + PAIRS COORDINATION ────────
            htf_context = _timeframe_coordinator.build_context(
                sym,
                series,
                state.indicator_engine,
                state.structural_engine,
                state.regime_classifier,
            )

            if htf_context:
                state.asset_confidence[sym] = round(
                    max(state.asset_confidence.get(sym, 0.0), htf_context.htf_regime.confidence),
                    3,
                )

            pairs_context = _pairs_coordinator.build_signal(
                sym,
                state.selected_assets,
                state.kline_buffers,
            )
            if pairs_context is not None:
                signal_family_results.append(pairs_context.signal)

            # Log signal family activity
            active_families = [s.family_name for s in signal_family_results if s.is_valid]
            all_scores = ", ".join(
                f"{s.family_name}={s.score:+.3f}" for s in signal_family_results
            )
            if active_families:
                log_msg(state, f"[{sym}] SIGNALS | {all_scores}")
            else:
                log_msg(state, f"[{sym}] SCANNING | No active signals | scores: {all_scores}")

            # ── STEP 5: BUILD ML FEATURES ───────────────────────────
            ml_features = _build_ml_features(
                series, indicators, regime_name, regime_result, data
            )

            # ── STEP 6: AUTO-TRAIN ML ON FIRST SYMBOL (once) ───────
            _try_train_ml(state, series, sym)

            # ── STEP 7: DECISION LOG ────────────────────────────────
            _log_decision(state, sym, series, indicators, structure, regime_result)

            # ── STEP 8: ORCHESTRATOR — evaluate strategies & execute ─
            rsi_res = indicators.get("rsi")
            
            # Compute score_weight from universe scoring (0.0-1.0)
            # Higher-quality assets get proportionally larger positions
            asset_score = 50.0  # default neutral
            for scored in state.scored_assets:
                if scored.get("symbol") == sym:
                    asset_score = scored.get("score", 50.0)
                    break
            # Normalize to 0.0-1.0 range (scores are 0-100)
            score_weight = min(1.0, max(0.0, asset_score / 100.0))
            
            # Component 1: Duplicate position prevention
            open_symbols = {p.symbol for p in state.orchestrator.connector.open_positions}
            if sym in open_symbols:
                log_msg(state, f"[{sym}] SKIP | already in position (duplicate prevention)")
                fills = []
            else:
                fills = state.orchestrator.process_bar(
                    symbol=sym,
                    timeframe=Timeframe.M1,
                    indicators=indicators,
                    structure=structure,
                    regime_result=regime_result,
                    closes=series.closes,
                    highs=series.highs,
                    lows=series.lows,
                    volumes=series.volumes,
                    opens=[c.open for c in series.candles],
                    current_bar=series.count,
                    ml_features=ml_features if state._ml_trained else None,
                    signal_family_results=signal_family_results,
                    htf_structure=htf_context.htf_structure if htf_context else None,
                    htf_regime=htf_context.htf_regime.primary_regime if htf_context else None,
                    order_book=state.live_books.get(sym),
                    score_weight=score_weight,
                )

                # Log fills
                await _log_fills(state, sym, fills, broadcast_fn)

        except Exception as e:
            decision = _error_recovery.handle_exception(
                e,
                stage="live_tick_pipeline",
                context={"symbol": sym},
            )
            logger.error(
                "Pipeline error for %s: %s | recovery=%s",
                sym,
                e,
                decision.fallback_message,
            )
            import traceback
            logger.debug(traceback.format_exc())

        await broadcast_fn()

        # Phase 4: Periodic state checkpoint + kline cache persistence
        state.save_checkpoint()
        if state._checkpoint_counter % 30 == 0:  # Every 30 bars persist klines
            state.persist_klines(sym)


def _compute_signal_families(
    series: OHLCVSeries,
    indicators: dict,
    structure,
    regime_result,
    order_book: dict | None = None,
) -> list[SignalResult]:
    """Compute all 5 signal family outputs for the CombinationEngine.

    This was dead code before Phase 6 — the signal families existed but
    were never evaluated in the live pipeline. Now they feed through
    the CombinationEngine for composite conviction scoring.

    Families:
        1. Momentum — time-series momentum + VWAP deviation
        2. Mean Reversion — VWAP z-score + Bollinger divergence
        3. Breakout — volatility squeeze + Donchian breakout
        4. Structural — S/R level rejection + microstructure
        5. Microstructure — VWAP deviation + volume imbalance + OBV
        
    Pattern Recognition Integration (Requirement 3.2, 3.4, 3.5):
        - Detects candlestick patterns on every bar
        - Boosts conviction by 20% when pattern forms at S/R level
        - Reduces conviction by 30% when reversal pattern conflicts with signal
    """
    results: list[SignalResult] = []

    # Extract common indicator values
    atr_res = indicators.get("atr")
    atr_vals = np.array(atr_res.values.get("atr", []), dtype=np.float64) if atr_res else np.array([])
    ema_res = indicators.get("ema")
    kama_val = float(ema_res.values.get("ema_21", [0.0])[-1]) if ema_res and ema_res.values.get("ema_21") else np.nan
    rsi_res = indicators.get("rsi")
    rsi_vals = np.array(rsi_res.values.get("rsi", []), dtype=np.float64) if rsi_res else np.array([])
    bb_res = indicators.get("bollinger")
    bb_upper_arr = np.array(bb_res.values.get("upper", []), dtype=np.float64) if bb_res else np.array([])
    bb_lower_arr = np.array(bb_res.values.get("lower", []), dtype=np.float64) if bb_res else np.array([])
    bb_upper_val = float(bb_upper_arr[-1]) if len(bb_upper_arr) > 0 else 0.0
    bb_lower_val = float(bb_lower_arr[-1]) if len(bb_lower_arr) > 0 else 0.0

    # Build RegimeProbabilities for signal family consumption
    regime_probs = _build_regime_probs(regime_result)
    
    # ── PATTERN RECOGNITION (Requirement 3.2, 3.4, 3.5) ──────────────────
    # Invoke PatternRecognizer on every bar to detect candlestick patterns
    detected_patterns = []
    try:
        from algoforge.structural.pattern_recognizer import PatternRecognizer
        
        pattern_recognizer = PatternRecognizer()
        
        # Extract OHLC arrays for pattern recognition
        opens = np.array([c.open for c in series.candles], dtype=np.float64)
        highs = np.array([c.high for c in series.candles], dtype=np.float64)
        lows = np.array([c.low for c in series.candles], dtype=np.float64)
        closes = np.array([c.close for c in series.candles], dtype=np.float64)
        
        # Recognize patterns in recent bars
        detected_patterns = pattern_recognizer.recognize_patterns(
            opens=opens,
            highs=highs,
            lows=lows,
            closes=closes,
            lookback=5,
        )
        
        # Check if patterns are at S/R levels (high-confluence zones)
        if detected_patterns and structure and hasattr(structure, 'support_resistance_levels'):
            current_price = closes[-1]
            sr_levels = structure.support_resistance_levels
            
            # Check proximity to S/R levels (within 0.5% tolerance)
            for pattern in detected_patterns:
                for level in sr_levels:
                    level_price = level.price if hasattr(level, 'price') else level
                    if abs(current_price - level_price) / level_price < 0.005:
                        pattern.at_sr_level = True
                        pattern.confluence_boost = 0.2  # 20% boost
                        break
        
        if detected_patterns:
            logger.debug(
                "patterns_detected",
                count=len(detected_patterns),
                patterns=[p.pattern_type for p in detected_patterns],
            )
    except Exception as e:
        logger.warning("pattern_recognition_error", error=str(e))

    # 1. MOMENTUM SIGNAL
    try:
        mom_result = _momentum_signal.evaluate(
            series=series,
            kama=kama_val,
            atr_series=atr_vals,
            regime_probs=regime_probs,
        )
        results.append(mom_result)
    except Exception as e:
        logger.debug(f"Momentum signal error: {e}")
        results.append(SignalResult(
            family_name="momentum", score=0.0,
            direction="neutral", is_valid=False,
            metadata={"error": str(e)}
        ))

    # 2. MEAN REVERSION SIGNAL
    try:
        mom_score = results[0].score if results else 0.0
        rev_result = _mean_reversion_signal.evaluate(
            series=series,
            rsi_series=rsi_vals,
            bb_upper=bb_upper_val,
            bb_lower=bb_lower_val,
            regime_probs=regime_probs,
            momentum_score=mom_score,
        )
        results.append(rev_result)
    except Exception as e:
        logger.debug(f"Mean reversion signal error: {e}")
        results.append(SignalResult(
            family_name="mean_reversion", score=0.0,
            direction="neutral", is_valid=False,
            metadata={"error": str(e)}
        ))

    # 3. BREAKOUT SIGNAL
    try:
        brk_result = _breakout_signal.evaluate(
            series=series,
            bb_upper=bb_upper_arr,
            bb_lower=bb_lower_arr,
            regime_probs=regime_probs,
            structural_snapshot=structure,
        )
        results.append(brk_result)
    except Exception as e:
        logger.debug(f"Breakout signal error: {e}")
        results.append(SignalResult(
            family_name="breakout", score=0.0,
            direction="neutral", is_valid=False,
            metadata={"error": str(e)}
        ))

    # 4. STRUCTURAL SIGNAL
    try:
        struct_result = _structural_signal.evaluate(
            series=series,
            snapshot=structure,
            regime_probs=regime_probs,
            indicators=indicators,
        )
        results.append(struct_result)
    except Exception as e:
        logger.debug(f"Structural signal error: {e}")
        results.append(SignalResult(
            family_name="structural", score=0.0,
            direction="neutral", is_valid=False,
            metadata={"error": str(e)}
        ))

    # 5. MICROSTRUCTURE SIGNAL
    try:
        latest = series.candles[-1]
        micro_result = _microstructure_family.generate(
            high=latest.high,
            low=latest.low,
            close=latest.close,
            volume=latest.volume,
            order_book=order_book,
        )
        results.append(micro_result)
    except Exception as e:
        logger.debug(f"Microstructure signal error: {e}")
        results.append(SignalResult(
            family_name="microstructure", score=0.0,
            direction="neutral", is_valid=False,
            metadata={"error": str(e)}
        ))
    
    # ── PATTERN-BASED CONVICTION ADJUSTMENTS (Requirement 3.2, 3.4, 3.5) ──
    # Apply pattern recognition as a confirmation filter
    if detected_patterns:
        for signal in results:
            if not signal.is_valid:
                continue
            
            # Determine signal direction for pattern matching
            signal_direction = signal.direction
            if isinstance(signal_direction, str):
                signal_direction_str = signal_direction
            else:
                signal_direction_str = signal_direction.value if hasattr(signal_direction, 'value') else str(signal_direction)
            
            original_score = signal.score
            adjustment_applied = False
            adjustment_reason = []
            
            for pattern in detected_patterns:
                pattern_dir = pattern.direction.value if hasattr(pattern.direction, 'value') else pattern.direction
                
                # Requirement 3.2: Boost conviction by 20% when pattern forms at S/R level
                if pattern.at_sr_level and pattern_dir != "neutral":
                    # Check if pattern direction aligns with signal
                    if (signal_direction_str == "long" and pattern_dir == "bullish") or \
                       (signal_direction_str == "short" and pattern_dir == "bearish"):
                        signal.score = signal.score * 1.20  # 20% boost
                        adjustment_applied = True
                        adjustment_reason.append(f"pattern_at_sr_boost:{pattern.pattern_type}")
                        logger.debug(
                            "pattern_conviction_boost",
                            family=signal.family_name,
                            pattern=pattern.pattern_type,
                            original_score=round(original_score, 3),
                            adjusted_score=round(signal.score, 3),
                        )
                
                # Requirement 3.4: Reduce conviction by 30% when reversal pattern conflicts
                # Reversal patterns: engulfing, hammer, shooting_star, morning_star, evening_star
                reversal_patterns = ["engulfing", "hammer", "shooting_star", "morning_star", "evening_star", "piercing", "dark_cloud"]
                if pattern.pattern_type in reversal_patterns:
                    # Check if pattern direction conflicts with signal
                    if (signal_direction_str == "long" and pattern_dir == "bearish") or \
                       (signal_direction_str == "short" and pattern_dir == "bullish"):
                        signal.score = signal.score * 0.70  # 30% reduction
                        adjustment_applied = True
                        adjustment_reason.append(f"reversal_conflict:{pattern.pattern_type}")
                        logger.debug(
                            "pattern_conviction_reduction",
                            family=signal.family_name,
                            pattern=pattern.pattern_type,
                            original_score=round(original_score, 3),
                            adjusted_score=round(signal.score, 3),
                        )
            
            # Add pattern adjustment metadata to signal
            if adjustment_applied:
                if not hasattr(signal, 'metadata') or signal.metadata is None:
                    signal.metadata = {}
                signal.metadata['pattern_adjustments'] = adjustment_reason
                signal.metadata['original_score'] = original_score

    return results


def _build_regime_probs(regime_result) -> RegimeProbabilities | None:
    """Convert RegimeResult to RegimeProbabilities for signal families."""
    try:
        from algoforge.regime.models import RegimeState
        regime_map = {
            "trend_up": "trend_up",
            "trend_down": "trend_down",
            "mean_revert": "mean_revert",
            "ranging": "mean_revert",
            "crisis": "crisis",
            "volatile": "crisis",
        }
        primary = regime_result.primary_regime.value
        conf = regime_result.confidence

        probs = {"trend_up": 0.1, "trend_down": 0.1, "mean_revert": 0.1, "crisis": 0.1}
        mapped = regime_map.get(primary, "mean_revert")
        probs[mapped] = conf
        remaining = 1.0 - conf
        other_keys = [k for k in probs if k != mapped]
        for k in other_keys:
            probs[k] = remaining / len(other_keys)

        return RegimeProbabilities(
            trend_up=probs["trend_up"],
            trend_down=probs["trend_down"],
            mean_revert=probs["mean_revert"],
            crisis=probs["crisis"],
            uncertainty_flag=(conf < 0.4),
        )
    except Exception:
        return None


def _build_ml_features(
    series: OHLCVSeries,
    indicators: dict,
    regime_name: str,
    regime_result,
    data: dict,
) -> dict:
    """Build ML feature dict from current bar data."""
    rsi_res = indicators.get("rsi")
    rsi_vals = rsi_res.values.get("rsi", []) if rsi_res else []
    ema_res = indicators.get("ema")
    ema_vals = ema_res.values if ema_res else None
    atr_res = indicators.get("atr")
    atr_vals = atr_res.values.get("atr", []) if atr_res else []

    closes = series.closes
    n = len(closes)

    ret1 = (closes[-1] / closes[-2] - 1) if n > 1 else 0.0
    ret5 = (closes[-1] / closes[-6] - 1) if n > 5 else 0.0
    ret10 = (closes[-1] / closes[-11] - 1) if n > 10 else 0.0
    ret20 = (closes[-1] / closes[-21] - 1) if n > 20 else 0.0
    vol5 = float(np.std(closes[-5:])) if n > 5 else 0.0
    vol20 = float(np.std(closes[-20:])) if n > 20 else 0.0
    cur_atr = float(atr_vals[-1]) if atr_vals else 1.0
    ema9_v = float(ema_vals.get("ema_9", [closes[-1]])[-1]) if ema_vals else closes[-1]
    ema21_v = float(ema_vals.get("ema_21", [closes[-1]])[-1]) if ema_vals else closes[-1]
    atr5 = float(np.mean([abs(closes[i] - closes[i - 1]) for i in range(-5, 0)])) if n > 5 else cur_atr

    return dict(
        signal_scores={},
        regime_probs={regime_name: regime_result.confidence, "other": 1 - regime_result.confidence},
        bars_since_regime_change=0,
        returns_1=ret1, returns_5=ret5, returns_10=ret10, returns_20=ret20,
        volatility_5=vol5, volatility_20=vol20,
        atr_ratio=atr5 / cur_atr if cur_atr > 0 else 1.0,
        momentum=closes[-1] - ema21_v,
        volume_ratio=(series.volumes[-1] / np.mean(series.volumes[-20:])) if n > 20 else 1.0,
        hour=data["timestamp"].hour,
        day_of_week=data["timestamp"].weekday(),
        month=data["timestamp"].month,
    )


def _try_train_ml(state: SystemState, series: OHLCVSeries, sym: str) -> None:
    """Auto-train ML ensemble on first symbol with enough data.
    
    Hardened for Phase 10:
    - Requires 5000 bars minimum for statistical significance.
    - Uses MLPipeline with purged walk-forward CV to prevent leakage.
    """
    closes = np.array(series.closes, dtype=np.float64)
    n = len(closes)

    # Require minimum 5000 bars (approx 3.5 days of 1m data)
    MIN_TRAIN_BARS = 5000
    if state._ml_trained or not state.orchestrator._ml or n < MIN_TRAIN_BARS:
        return

    try:
        from algoforge.ml.features import FeatureBuilder
        X_rows = []
        for i in range(21, n):
            feat = FeatureBuilder.build(
                signal_scores={},
                returns_1=(closes[i] / closes[i - 1] - 1) if i > 0 else 0,
                returns_5=(closes[i] / closes[i - 5] - 1) if i > 4 else 0,
                returns_10=(closes[i] / closes[i - 10] - 1) if i > 9 else 0,
                returns_20=(closes[i] / closes[i - 20] - 1) if i > 19 else 0,
                volatility_5=float(np.std(closes[max(0, i - 5):i])),
                volatility_20=float(np.std(closes[max(0, i - 20):i])),
                momentum=closes[i] - float(np.mean(closes[max(0, i - 21):i])),
            )
            X_rows.append(feat)
            
        features = np.array(X_rows)
        # Pad initial prices to match features length
        aligned_closes = closes[21:]
        aligned_highs = np.array(series.highs)[21:]
        aligned_lows = np.array(series.lows)[21:]

        log_msg(state, f"Starting ML pipeline training on {len(features)} historical bars from {sym} (Purged Walk-Forward CV)...")
        
        result = state.orchestrator._ml.train(
            features=features,
            closes=aligned_closes,
            highs=aligned_highs,
            lows=aligned_lows,
        )
        
        state._ml_trained = True
        # Phase 10: Model persistence
        state.orchestrator._ml.save("data/ml_model.joblib")
        log_msg(state, f"ML Pipeline trained successfully. Folds: {result.n_folds}, Avg Accuracy: {result.avg_accuracy:.3f}")
    except Exception as ml_e:
        logger.warning(f"ML training failed: {ml_e}")
        import traceback
        logger.debug(traceback.format_exc())
        state._ml_trained = True  # Don't retry continuously on error


def _log_decision(
    state: SystemState,
    sym: str,
    series: OHLCVSeries,
    indicators: dict,
    structure,
    regime_result,
) -> None:
    """Log why the system is trading or skipping this bar."""
    engine = state.orchestrator.connector
    open_syms = [p.symbol for p in engine.open_positions]
    snap = engine.snapshot()
    regime_name = regime_result.primary_regime.value

    eligible = [
        s.name for s in state.orchestrator._strategies
        if regime_result.primary_regime in s.required_regime
    ]

    rsi_res = indicators.get("rsi")
    rsi_vals = rsi_res.values.get("rsi", []) if rsi_res else []
    adx_res = indicators.get("adx")
    adx_vals = adx_res.values.get("adx", []) if adx_res else []

    rsi_now = float(rsi_vals[-1]) if rsi_vals else None
    adx_now = float(adx_vals[-1]) if adx_vals else None
    trend_d = structure.trend_direction.value if structure else "unknown"

    reasons_skip = []
    if not eligible:
        reasons_skip.append(f"no strategy covers regime={regime_name}")
    if snap.max_drawdown_pct and snap.max_drawdown_pct > 15.0:
        reasons_skip.append(f"drawdown {snap.max_drawdown_pct:.1f}% > limit")
    if len(open_syms) >= state.risk_config.max_open_positions:
        reasons_skip.append(f"max positions ({state.risk_config.max_open_positions}) reached")
    if sym in open_syms:
        reasons_skip.append("already in position")
    if adx_now and adx_now < 12:
        reasons_skip.append(f"ADX={adx_now:.1f} too low (choppy)")

    if reasons_skip:
        log_msg(
            state,
            f"[{sym}] SKIP | regime={regime_name} conf={regime_result.confidence:.2f} | "
            f"{' | '.join(reasons_skip)}"
        )
    else:
        log_msg(
            state,
            f"[{sym}] SCAN | regime={regime_name} conf={regime_result.confidence:.2f} | "
            f"trend={trend_d} | RSI={rsi_now:.1f} adx={adx_now:.1f} | "
            f"strategies={eligible}"
        )


async def _log_fills(
    state: SystemState,
    sym: str,
    fills: list,
    broadcast_fn,
) -> None:
    """Log trade fills and vetoes."""
    engine = state.orchestrator.connector
    regime_name = state.asset_regimes.get(sym, "unknown")

    traded = False
    for fill in fills:
        if fill.filled:
            traded = True
            pos = next((p for p in engine.open_positions if p.id == fill.position_id), None)
            sl_str = f"${pos.stop_loss:.4f}" if pos else "n/a"
            tp_str = f"${pos.take_profit:.4f}" if pos else "n/a"
            dir_str = pos.direction.value.upper() if pos else "?"
            qty_str = f"{pos.quantity:.4f}" if pos else "?"
            value_str = f"${pos.entry_price * pos.quantity:,.2f}" if pos else "$?"
            ml_tag = f" ML={'ON' if state._ml_trained else 'OFF'}"
            log_msg(
                state,
                f"[TRADE] [{sym}] {dir_str} "
                f"@ ${fill.fill_price:.4f} | SL={sl_str} TP={tp_str} "
                f"qty={qty_str} value={value_str} slip=${fill.slippage:.4f}{ml_tag}"
            )
            await broadcast_fn()
        else:
            reason = fill.rejection_reason or "strategy conditions not met"
            log_msg(state, f"[VETO] [{sym}] | {reason}")

    if not fills and sym not in [p.symbol for p in engine.open_positions]:
        log_msg(state, f"[SCAN] [{sym}] | {regime_name} regime -- conditions not met")
