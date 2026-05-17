# Requirements Document

## Introduction

AlgoForge is an institutional-grade algorithmic trading system that has successfully completed 22 phases with 583 passing tests. The system features a sophisticated 5-signal-family architecture with HMM regime detection, risk management, and paper trading capabilities. However, critical gaps exist between the implemented infrastructure and the user's 10 core operational requirements.

This requirements document defines the integration and enhancement work needed to transform AlgoForge from a well-architected foundation into a fully operational trading system that meets all user requirements. The project focuses on seven key integration modules that bridge existing components, activate dormant features, and complete missing functionality.

**Project Scope:** System integration, strategy activation, ML/RL enablement, dynamic position management, P&L enhancement, and frontend completion.

**Success Criteria:** All 10 user requirements fully operational with end-to-end workflow validation from fundamental analysis through execution and monitoring.

## Glossary

- **AlgoForge_System**: The complete algorithmic trading platform including all modules and components
- **Signal_Family**: One of five decorrelated signal generation systems (Momentum, Mean Reversion, Breakout, Structural, Microstructure)
- **Legacy_Strategy**: One of 31 pre-existing strategy implementations in the `strategies/` folder not yet integrated into the signal framework
- **Combination_Engine**: The signal aggregation system that combines multiple signal families with decorrelation and Sharpe-based weighting
- **HMM_Regime_Detector**: Hidden Markov Model-based market regime classifier producing probability distributions
- **FinGPT**: Financial domain-specific large language model for price predictions and market analysis
- **RL_Agent**: Reinforcement Learning agent that adjusts system thresholds based on trade outcomes
- **Trendline_Builder**: Existing module for detecting trendlines that is not currently integrated
- **Dynamic_SL_TP**: Stop-loss and take-profit levels that adjust in real-time based on market conditions
- **R_Multiple**: Risk-reward ratio metric (profit/loss divided by initial risk)
- **Conviction_Score**: Confidence metric (0-1) used to determine position sizing
- **Alpha_Decay_Monitor**: System that tracks signal family performance degradation over time
- **Fundamental_Pipeline**: LangGraph-based 4-agent system for fundamental analysis
- **Paper_Trading_Engine**: Realistic execution simulator with slippage, commission, and latency modeling
- **Risk_Manager**: Module with absolute veto power over all trades enforcing position and portfolio limits
- **Orchestrator**: Main trading pipeline coordinating all modules from data through execution
- **Frontend_Dashboard**: Next.js web interface for monitoring and control
- **Candlestick_Pattern**: Price action patterns (engulfing, hammer, doji, etc.) used for signal confirmation
- **S_R_Level**: Support and Resistance price levels derived from structural analysis
- **ML_Pipeline**: Machine learning enhancement layer with XGBoost, LSTM, and ensemble models
- **Pairs_Trading**: Market-neutral strategy trading cointegrated instrument spreads
- **OMS**: Order Management System tracking order lifecycle and state transitions
- **Circuit_Breaker**: Safety mechanism that halts trading during extreme market moves

## Requirements

### Requirement 1: Legacy Strategy Integration Framework

**User Story:** As a trader, I want all 31 legacy strategies integrated into the signal framework, so that proven strategies contribute to trading decisions through the combination engine.

#### Acceptance Criteria

1. THE Strategy_Adapter SHALL convert each Legacy_Strategy output into a standardized SignalResult with score normalized to [-1, 1]
2. WHEN a Legacy_Strategy generates a signal, THE Strategy_Adapter SHALL include strategy name, timeframe, and confidence metadata
3. THE Integration_Registry SHALL maintain a mapping of all 31 Legacy_Strategy instances to their corresponding Signal_Family categories
4. FOR ALL Legacy_Strategy outputs, THE Strategy_Adapter SHALL preserve original strategy logic while conforming to the SignalResult interface
5. THE Orchestrator SHALL route adapted strategy signals through the Combination_Engine alongside existing signal families
6. WHEN multiple Legacy_Strategy instances target the same Signal_Family, THE Combination_Engine SHALL aggregate them using existing decorrelation logic
7. THE System SHALL validate that adapted strategies produce scores within [-1, 1] bounds (round-trip property)

### Requirement 2: Trendline Detection Integration

**User Story:** As a trader, I want trendline detection integrated into the trading loop, so that trendline breaks and pullbacks generate actionable signals.

#### Acceptance Criteria

1. THE Orchestrator SHALL invoke Trendline_Builder on each bar for all active instruments
2. WHEN Trendline_Builder detects a valid trendline, THE System SHALL store trendline parameters (slope, touches, strength) in the structural snapshot
3. THE Structural_Signal_Family SHALL generate signals when price approaches a trendline within 0.5 ATR proximity
4. WHEN price breaks a trendline with volume confirmation, THE Breakout_Signal_Family SHALL generate a breakout signal
5. THE Trendline_Pullback_Strategy SHALL activate when price pulls back to a trendline after a breakout with EMA/RSI/ADX confirmation
6. THE System SHALL track trendline validity and invalidate trendlines after N candles without touches or after decisive breaks
7. FOR ALL detected trendlines, THE System SHALL expose trendline data to the Frontend_Dashboard for visualization

### Requirement 3: Candlestick Pattern Recognition

**User Story:** As a trader, I want candlestick pattern recognition integrated, so that price action patterns confirm or reject signals from other families.

#### Acceptance Criteria

1. THE Pattern_Recognizer SHALL detect at least 10 major candlestick patterns (engulfing, hammer, shooting star, doji, morning/evening star, three white soldiers, three black crows, harami, piercing, dark cloud)
2. WHEN a candlestick pattern forms at a high-confluence S_R_Level, THE Structural_Signal_Family SHALL boost signal conviction by 20%
3. THE Pattern_Recognizer SHALL classify patterns by bullish/bearish direction and strength (weak/moderate/strong)
4. WHEN a reversal pattern forms against the current signal direction, THE Combination_Engine SHALL reduce composite conviction by 30%
5. THE System SHALL use pattern recognition as a confirmation filter, not a standalone signal generator
6. THE Pattern_Recognizer SHALL operate on all timeframes and provide multi-timeframe pattern agreement scoring
7. FOR ALL recognized patterns, THE System SHALL log pattern type, strength, and impact on signal conviction

### Requirement 4: FinGPT Integration for Price Predictions

**User Story:** As a trader, I want FinGPT integrated for price predictions, so that domain-specific AI forecasts enhance signal quality and position sizing.

#### Acceptance Criteria

1. THE FinGPT_Client SHALL generate price predictions for the next 1/5/10 bars with confidence intervals
2. WHEN FinGPT prediction direction aligns with Combination_Engine composite signal, THE System SHALL increase Conviction_Score by 15%
3. WHEN FinGPT prediction direction conflicts with composite signal, THE System SHALL reduce Conviction_Score by 25%
4. THE ML_Pipeline SHALL aggregate FinGPT predictions with XGBoost and LSTM forecasts using ensemble stacking
5. THE System SHALL use FinGPT confidence intervals to adjust position sizing (wider intervals = smaller positions)
6. THE FinGPT_Client SHALL implement caching to avoid redundant API calls for the same bar and instrument
7. WHEN FinGPT API fails or times out, THE System SHALL gracefully degrade to algorithmic signals without blocking execution
8. FOR ALL FinGPT predictions, THE System SHALL track prediction accuracy and adjust weighting based on rolling performance

### Requirement 5: ML Pipeline Activation and Integration

**User Story:** As a trader, I want the ML pipeline enabled by default and integrated into signal generation, so that machine learning enhances trading decisions.

#### Acceptance Criteria

1. THE System SHALL set `enable_ml=True` by default in the Orchestrator configuration
2. WHEN ML_Pipeline is enabled, THE System SHALL compute all 44 engineered features on every bar
3. THE XGBoost_Classifier SHALL predict trade direction and output probability scores integrated into the Combination_Engine
4. THE LSTM_Forecaster SHALL generate multi-step price forecasts used for Dynamic_SL_TP adjustment
5. THE ML_Pipeline SHALL use the ensemble meta-model to combine XGBoost, LSTM, and FinGPT predictions
6. THE System SHALL apply ML prediction scores as a multiplier to composite signal conviction (ML_score × composite_score)
7. WHEN ML model confidence is below 0.5, THE System SHALL reduce position size by 50%
8. THE ML_Pipeline SHALL retrain models weekly using walk-forward validation without data leakage
9. FOR ALL ML predictions, THE System SHALL log feature importance and model confidence for monitoring

### Requirement 6: RL Threshold Adjustment Feedback Loop

**User Story:** As a trader, I want an RL agent that learns from trade outcomes and adjusts system thresholds, so that the system continuously improves based on real performance.

#### Acceptance Criteria

1. THE RL_Agent SHALL observe state tuples (trade_result, market_regime, current_thresholds, signal_scores) after each trade closes
2. WHEN a trade closes, THE RL_Agent SHALL compute reward as R_Multiple adjusted for regime appropriateness and signal quality
3. THE RL_Agent SHALL adjust conviction thresholds (currently 0.3/0.6) based on observed win rates and R_Multiples
4. THE RL_Agent SHALL adjust Risk_Manager position size limits based on recent drawdown and volatility
5. THE RL_Agent SHALL adjust Signal_Family weights in the Combination_Engine based on per-family performance
6. THE RL_Agent SHALL adjust ML_Pipeline model confidence thresholds based on prediction accuracy
7. THE System SHALL persist RL_Agent state and learned parameters across restarts
8. THE RL_Agent SHALL implement exploration (10%) vs exploitation (90%) to avoid local optima
9. WHEN RL_Agent adjustments degrade performance for 20 consecutive trades, THE System SHALL revert to baseline parameters
10. FOR ALL threshold adjustments, THE System SHALL log old values, new values, and the reasoning (which trades triggered the adjustment)

### Requirement 7: Confidence-Based Position Sizing

**User Story:** As a trader, I want position sizes determined by confidence scores from all sources, so that high-conviction trades receive larger allocations and low-conviction trades receive smaller allocations.

#### Acceptance Criteria

1. THE Position_Sizer SHALL compute Conviction_Score as the product of (Combination_Engine_score × ML_confidence × FinGPT_confidence × Regime_alignment)
2. WHEN Conviction_Score is below 0.3, THE System SHALL skip the trade
3. WHEN Conviction_Score is between 0.3 and 0.6, THE Position_Sizer SHALL allocate 50% of the base position size
4. WHEN Conviction_Score is above 0.6, THE Position_Sizer SHALL allocate 100% of the base position size
5. THE Position_Sizer SHALL apply Kelly Criterion fractional sizing with Conviction_Score as the edge parameter
6. THE Risk_Manager SHALL enforce that no position exceeds maximum size limits regardless of Conviction_Score
7. THE System SHALL track realized R_Multiples by Conviction_Score bucket to validate the sizing model
8. FOR ALL position sizing decisions, THE System SHALL log the breakdown of conviction components (signal score, ML confidence, FinGPT confidence, regime alignment)

### Requirement 8: Dynamic Stop-Loss and Take-Profit Adjustment

**User Story:** As a trader, I want stop-loss and take-profit levels to adjust dynamically after trade entry, so that positions adapt to changing market conditions and protect profits.

#### Acceptance Criteria

1. WHEN a position is open, THE Dynamic_SL_TP_Manager SHALL monitor ML_Pipeline and FinGPT predictions every bar
2. WHEN ML prediction confidence increases by 20% in the trade direction, THE Dynamic_SL_TP_Manager SHALL widen TP3 by 0.5 ATR
3. WHEN ML prediction confidence decreases by 20% or reverses direction, THE Dynamic_SL_TP_Manager SHALL tighten stop-loss to breakeven
4. WHEN HMM_Regime_Detector transitions to a conflicting regime, THE Dynamic_SL_TP_Manager SHALL tighten stop-loss by 0.5 ATR
5. WHEN price approaches a newly detected S_R_Level, THE Dynamic_SL_TP_Manager SHALL place stop-loss just beyond the level
6. WHEN a trendline breaks against the trade direction, THE Dynamic_SL_TP_Manager SHALL immediately move stop-loss to breakeven
7. WHEN volatility (ATR) expands by 50%, THE Dynamic_SL_TP_Manager SHALL widen stop-loss proportionally to avoid premature exit
8. WHEN volatility contracts by 30%, THE Dynamic_SL_TP_Manager SHALL tighten stop-loss to lock in profits
9. THE Dynamic_SL_TP_Manager SHALL never widen stop-loss beyond the original entry stop-loss
10. FOR ALL SL/TP adjustments, THE System SHALL log the trigger (regime change, prediction change, volatility change, S/R level) and old/new values

### Requirement 9: Enhanced P&L Tracking and Display

**User Story:** As a trader, I want detailed P&L metrics including percentage returns and R-multiples, so that I can evaluate trade quality beyond absolute dollar amounts.

#### Acceptance Criteria

1. THE P&L_Tracker SHALL compute percentage P&L as (exit_price - entry_price) / entry_price × 100 for each position
2. THE P&L_Tracker SHALL compute R_Multiple as (profit_or_loss) / (initial_risk) for each closed trade
3. THE P&L_Tracker SHALL track capital allocated per instrument including margin requirements
4. THE P&L_Tracker SHALL compute portfolio-level metrics (total P&L %, Sharpe ratio, Sortino ratio, max drawdown %)
5. THE Frontend_Dashboard SHALL display per-position metrics (entry price, current price, P&L $, P&L %, R-multiple, time in trade)
6. THE Frontend_Dashboard SHALL display portfolio-level metrics (total capital, allocated capital, available capital, total P&L $, total P&L %, current drawdown %)
7. THE P&L_Tracker SHALL categorize trades by Signal_Family and display per-family P&L contribution
8. THE P&L_Tracker SHALL track cumulative R-multiples and display R-multiple distribution histogram
9. FOR ALL closed trades, THE System SHALL persist P&L metrics to the database for historical analysis

### Requirement 10: Complete Frontend Dashboard

**User Story:** As a trader, I want a comprehensive dashboard showing all system state and metrics, so that I can monitor performance, diagnose issues, and control the system.

#### Acceptance Criteria

1. THE Frontend_Dashboard SHALL display Signal_Family health panel showing per-family Sharpe ratios, hit rates, and Alpha_Decay_Monitor status (green/yellow/red)
2. THE Frontend_Dashboard SHALL display HMM_Regime_Detector probability distribution as a stacked bar chart updated every bar
3. THE Frontend_Dashboard SHALL display ML_Pipeline metrics panel showing model accuracy, feature importance top-10, and prediction confidence
4. THE Frontend_Dashboard SHALL display backtest results viewer with equity curve, drawdown chart, and Monte Carlo confidence bands
5. THE Frontend_Dashboard SHALL display Risk_Manager metrics panel showing current exposure, VaR, position limits, and circuit breaker status
6. THE Frontend_Dashboard SHALL display per-position P&L table with all metrics from Requirement 9
7. THE Frontend_Dashboard SHALL display price charts with trendlines, S_R_Levels, candlestick patterns, and entry/exit markers
8. THE Frontend_Dashboard SHALL support multi-timeframe chart view (1m/5m/15m/1H/4H/1D) with synchronized crosshairs
9. THE Frontend_Dashboard SHALL display order book depth (L2 data) when available for the selected instrument
10. THE Frontend_Dashboard SHALL provide a kill switch button that flattens all positions and halts trading within 2 seconds
11. THE Frontend_Dashboard SHALL use WebSocket for real-time updates with sub-second latency
12. THE Frontend_Dashboard SHALL be responsive and functional on desktop browsers (1920×1080 minimum resolution)

### Requirement 11: System Flow Verification and Dead Code Removal

**User Story:** As a developer, I want verification that all modules are properly connected and unused code removed, so that the system is maintainable and all components serve a purpose.

#### Acceptance Criteria

1. THE System SHALL execute the complete flow: Fundamental_Pipeline → Technical_Analysis → ML_Pipeline → RL_Agent → Risk_Manager → Execution on every trading opportunity
2. THE System SHALL verify that Fundamental_Pipeline gate scores block trades when fundamental conditions are unfavorable
3. THE System SHALL verify that all 5 Signal_Family instances contribute signals to the Combination_Engine
4. THE System SHALL verify that Combination_Engine output feeds into ML_Pipeline for enhancement
5. THE System SHALL verify that ML_Pipeline predictions influence both signal conviction and Dynamic_SL_TP adjustments
6. THE System SHALL verify that RL_Agent receives trade outcomes and adjusts thresholds
7. THE System SHALL verify that Risk_Manager evaluates every signal and can veto trades
8. THE System SHALL verify that Alpha_Decay_Monitor tracks all Signal_Family performance and adjusts weights
9. THE System SHALL identify and remove code files that are not imported or called by any active module
10. THE System SHALL preserve all 31 Legacy_Strategy files as they will be integrated per Requirement 1
11. THE System SHALL generate a module dependency graph showing all active connections
12. FOR ALL modules, THE System SHALL verify that configuration parameters are used and not overridden by hardcoded values

### Requirement 12: Pairs Trading Completion

**User Story:** As a trader, I want the pairs trading implementation completed, so that market-neutral strategies contribute to the Mean_Reversion_Signal_Family.

#### Acceptance Criteria

1. THE Pairs_Detector SHALL scan the instrument universe and identify cointegrated pairs using Engle-Granger test with p-value < 0.05
2. WHEN a valid pair is detected, THE Pairs_Detector SHALL compute the spread as (price_A - hedge_ratio × price_B)
3. THE Pairs_Trader SHALL compute spread z-score using rolling 60-period mean and standard deviation
4. WHEN spread z-score exceeds +2.0, THE Pairs_Trader SHALL generate a mean-reversion signal (short spread: short A, long B)
5. WHEN spread z-score falls below -2.0, THE Pairs_Trader SHALL generate a mean-reversion signal (long spread: long A, short B)
6. THE Pairs_Trader SHALL size positions to be dollar-neutral (position_A_value + position_B_value = 0)
7. THE Pairs_Trader SHALL re-validate cointegration every 20 trading days and invalidate pairs when p-value > 0.10
8. WHEN a pair is invalidated, THE System SHALL close any open positions in that pair within 5 bars
9. THE Pairs_Trader SHALL integrate with the Mean_Reversion_Signal_Family and contribute to the Combination_Engine
10. FOR ALL pairs trades, THE System SHALL track spread P&L separately from directional P&L

### Requirement 13: User-Specific Strategy Implementation

**User Story:** As a trader, I want my specific trendline pullback strategy (5/9/21 EMA + RSI + ADX + ATR confirmation) fully operational, so that my preferred trading approach is available in the system.

#### Acceptance Criteria

1. THE Trendline_Pullback_Strategy SHALL detect valid trendlines using Trendline_Builder with minimum 3 touches
2. WHEN price breaks above a trendline and then pulls back to within 0.3 ATR, THE Strategy SHALL check for entry conditions
3. THE Strategy SHALL require 5 EMA > 9 EMA > 21 EMA for bullish setup (reverse for bearish)
4. THE Strategy SHALL require RSI between 40-60 (not oversold/overbought, showing momentum pause)
5. THE Strategy SHALL require ADX > 25 (confirming trend strength)
6. THE Strategy SHALL require current ATR within 20th-80th percentile (avoiding extreme volatility)
7. WHEN all conditions are met, THE Strategy SHALL generate a signal with conviction = 0.7
8. THE Strategy SHALL set initial stop-loss at 1.5 ATR below the trendline (bullish) or above (bearish)
9. THE Strategy SHALL set TP1/TP2/TP3 using the standard multi-target exit system from Requirement 8
10. THE Strategy SHALL integrate into the Structural_Signal_Family and route through the Combination_Engine

### Requirement 14: Multi-Timeframe Coordination

**User Story:** As a trader, I want signals coordinated across multiple timeframes, so that trades align with both short-term and long-term market structure.

#### Acceptance Criteria

1. THE System SHALL compute structural analysis (S_R_Levels, trendlines, patterns) on at least 3 timeframes (primary, 3× primary, 9× primary)
2. WHEN a signal is generated on the primary timeframe, THE System SHALL check for alignment with higher timeframe trend direction
3. WHEN higher timeframe trend conflicts with primary timeframe signal, THE System SHALL reduce Conviction_Score by 40%
4. WHEN higher timeframe trend aligns with primary timeframe signal, THE System SHALL increase Conviction_Score by 20%
5. THE System SHALL use higher timeframe S_R_Levels as stronger confluence zones than primary timeframe levels
6. THE System SHALL detect higher timeframe regime transitions and propagate regime changes to lower timeframes
7. THE Frontend_Dashboard SHALL display multi-timeframe alignment indicator (aligned/neutral/conflicted) for each instrument

### Requirement 15: Order Book Integration

**User Story:** As a trader, I want order book depth (L2 data) integrated into execution logic, so that slippage estimates and liquidity checks are more accurate.

#### Acceptance Criteria

1. WHEN L2 order book data is available, THE System SHALL use actual bid/ask spreads for slippage estimation instead of fixed percentages
2. THE System SHALL compute available liquidity at each price level within 0.5% of current price
3. WHEN position size exceeds 10% of available liquidity at best bid/ask, THE Risk_Manager SHALL reduce position size or reject the trade
4. THE Paper_Trading_Engine SHALL simulate realistic fills by walking the order book and computing volume-weighted average fill price
5. THE Frontend_Dashboard SHALL display order book depth chart for the selected instrument
6. WHEN L2 data is unavailable, THE System SHALL gracefully degrade to volume-based liquidity estimates
7. THE System SHALL detect order book imbalances (bid volume / ask volume) and use as a microstructure signal input

### Requirement 16: Configuration Management and Validation

**User Story:** As a developer, I want all configuration parameters validated and documented, so that system behavior is predictable and configuration errors are caught early.

#### Acceptance Criteria

1. THE System SHALL use Pydantic models to validate all configuration parameters on startup
2. WHEN an invalid configuration value is detected, THE System SHALL log a detailed error message and refuse to start
3. THE System SHALL provide a configuration template with comments explaining each parameter and valid ranges
4. THE System SHALL validate that all file paths in configuration exist and are accessible
5. THE System SHALL validate that API keys and credentials are present when required features are enabled
6. THE System SHALL validate that risk parameters are internally consistent (e.g., daily loss limit < weekly loss limit < drawdown kill switch)
7. THE System SHALL generate a configuration summary on startup showing all active settings
8. THE System SHALL support environment-specific configurations (development, staging, production) loaded via environment variables

### Requirement 17: Logging and Observability

**User Story:** As a developer, I want comprehensive structured logging and metrics, so that I can diagnose issues, monitor performance, and understand system behavior.

#### Acceptance Criteria

1. THE System SHALL use structured logging (JSON format) for all log messages with consistent field names
2. THE System SHALL log every signal generation with all contributing factors (signal family scores, conviction, regime, ML predictions)
3. THE System SHALL log every trade decision with the full decision tree (why accepted or rejected)
4. THE System SHALL log every Risk_Manager veto with the specific rule that was violated
5. THE System SHALL log every RL_Agent threshold adjustment with before/after values and triggering trades
6. THE System SHALL log every Dynamic_SL_TP adjustment with the trigger and new levels
7. THE System SHALL emit Prometheus metrics for key performance indicators (signal latency, execution latency, fill rate, P&L)
8. THE System SHALL provide log level configuration (DEBUG, INFO, WARNING, ERROR) without code changes
9. THE System SHALL rotate log files daily and compress old logs to manage disk space
10. THE System SHALL provide a log query interface in the Frontend_Dashboard for searching and filtering logs

### Requirement 18: Testing and Validation Framework

**User Story:** As a developer, I want comprehensive tests for all integration points, so that system reliability is maintained as components are connected.

#### Acceptance Criteria

1. THE System SHALL include integration tests that verify the complete flow from data ingestion through execution
2. THE System SHALL include property-based tests for signal normalization (all outputs in [-1, 1] range)
3. THE System SHALL include property-based tests for position sizing (all positions within risk limits)
4. THE System SHALL include property-based tests for P&L calculations (sum of position P&L = portfolio P&L)
5. THE System SHALL include tests that verify Risk_Manager veto power (no trade executes when limits violated)
6. THE System SHALL include tests that verify RL_Agent threshold adjustments stay within valid ranges
7. THE System SHALL include tests that verify Dynamic_SL_TP never widens stop-loss beyond original level
8. THE System SHALL include tests that verify Combination_Engine decorrelation (pairwise correlations < 0.7)
9. THE System SHALL include backtests on historical data that verify system performance meets minimum thresholds (Sharpe > 1.0)
10. THE System SHALL achieve >80% test coverage for all new integration code

### Requirement 19: Performance Optimization

**User Story:** As a developer, I want the system optimized for real-time performance, so that signal generation and execution latency remain below acceptable thresholds.

#### Acceptance Criteria

1. THE System SHALL process a complete bar (all indicators, signals, ML predictions) in under 100ms for a single instrument
2. THE System SHALL handle 50+ concurrent instruments with total processing time under 2 seconds per bar
3. THE System SHALL cache indicator calculations to avoid redundant computation across signal families
4. THE System SHALL use vectorized NumPy operations for all indicator and feature calculations
5. THE System SHALL implement connection pooling for database and Redis connections
6. THE System SHALL use async I/O for all external API calls (FinGPT, data feeds, broker APIs)
7. THE System SHALL profile performance on startup and log any operations taking >50ms
8. THE System SHALL implement circuit breakers for slow external services to prevent blocking the main loop
9. THE System SHALL use incremental updates for indicators rather than full recalculation when possible

### Requirement 20: Error Handling and Recovery

**User Story:** As a trader, I want the system to handle errors gracefully and recover automatically, so that temporary failures don't require manual intervention.

#### Acceptance Criteria

1. WHEN a data feed connection fails, THE System SHALL attempt reconnection with exponential backoff (1s, 2s, 4s, 8s, max 60s)
2. WHEN an ML model prediction fails, THE System SHALL log the error and continue with algorithmic signals only
3. WHEN FinGPT API times out, THE System SHALL use cached predictions if available or skip FinGPT enhancement
4. WHEN a database write fails, THE System SHALL queue the write for retry and continue operation
5. WHEN the Risk_Manager detects corrupted state, THE System SHALL flatten all positions and halt trading
6. WHEN an unhandled exception occurs in a signal family, THE System SHALL disable that family and continue with remaining families
7. THE System SHALL implement health checks for all critical components (database, Redis, data feed, ML models)
8. WHEN a health check fails, THE System SHALL alert via the Frontend_Dashboard and attempt recovery
9. THE System SHALL persist critical state (open positions, RL parameters, model weights) to survive restarts
10. THE System SHALL implement a startup validation sequence that verifies all components before accepting live data

## Dependencies Between Requirements

**Foundation Requirements (Must Complete First):**
- Requirement 11 (System Flow Verification) - Validates current architecture before adding complexity
- Requirement 16 (Configuration Management) - Ensures reliable configuration for all modules
- Requirement 17 (Logging and Observability) - Provides visibility for debugging integration issues

**Core Integration Requirements (Second Priority):**
- Requirement 1 (Legacy Strategy Integration) - Activates existing strategies
- Requirement 2 (Trendline Detection) - Completes structural analysis
- Requirement 3 (Candlestick Patterns) - Adds confirmation layer
- Requirement 13 (User-Specific Strategy) - Implements primary user strategy

**ML/AI Enhancement Requirements (Third Priority):**
- Requirement 4 (FinGPT Integration) - Adds AI predictions
- Requirement 5 (ML Pipeline Activation) - Enables ML enhancement
- Requirement 6 (RL Threshold Adjustment) - Adds adaptive learning

**Position Management Requirements (Fourth Priority):**
- Requirement 7 (Confidence-Based Sizing) - Depends on Requirements 4, 5, 6 for confidence inputs
- Requirement 8 (Dynamic SL/TP) - Depends on Requirements 4, 5 for prediction inputs
- Requirement 9 (Enhanced P&L Tracking) - Depends on Requirements 7, 8 for accurate tracking

**Completion Requirements (Final Priority):**
- Requirement 10 (Frontend Dashboard) - Depends on all other requirements for complete data
- Requirement 12 (Pairs Trading) - Independent, can be done anytime
- Requirement 14 (Multi-Timeframe) - Enhances Requirements 1-3
- Requirement 15 (Order Book) - Enhances execution quality
- Requirement 18 (Testing) - Validates all integrations
- Requirement 19 (Performance) - Optimizes integrated system
- Requirement 20 (Error Handling) - Hardens integrated system

## Success Metrics

**Functional Completeness:**
- All 10 user requirements operational and validated
- All 31 legacy strategies integrated and contributing signals
- ML pipeline enabled and improving Sharpe ratio by ≥0.3
- RL agent adjusting thresholds based on outcomes
- Frontend dashboard displaying all metrics in real-time

**Performance Metrics:**
- Signal generation latency <100ms per instrument
- End-to-end execution latency <200ms
- System handles 50+ instruments concurrently
- Dashboard updates with <1s latency

**Quality Metrics:**
- Test coverage >80% for integration code
- All property-based tests passing
- Zero unhandled exceptions in 24-hour test run
- Backtest Sharpe ratio >1.5 on 2+ years of data

**Operational Metrics:**
- System uptime >99.5% over 30-day period
- Automatic recovery from transient failures >95%
- Risk manager veto rate <5% (most signals pass risk checks)
- Signal family decorrelation maintained (pairwise correlation <0.5)

