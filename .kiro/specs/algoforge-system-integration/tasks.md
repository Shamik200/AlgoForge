# Implementation Plan: AlgoForge System Integration

## Overview

This implementation plan transforms AlgoForge from a well-architected foundation into a fully operational trading system by integrating 31 legacy strategies, completing structural analysis, activating AI/ML enhancements, implementing dynamic position management, enhancing P&L tracking, building the frontend dashboard, and hardening the system with configuration validation, logging, testing, and error handling.

The implementation follows a layered approach: foundation (configuration, logging, validation) → core integration (strategies, structural analysis) → intelligence layer (ML/RL) → execution layer (dynamic SL/TP, P&L) → monitoring (dashboard).

## Tasks

- [x] 1. Foundation Layer - Configuration, Logging, and Validation
  - [x] 1.1 Create ConfigValidator module with Pydantic models
    - Implement `ConfigValidator` class with validation methods for all config sections
    - Add validation for risk parameters consistency (daily < weekly < drawdown limits)
    - Add validation for file paths existence and accessibility
    - Add validation for required credentials when features are enabled
    - Create configuration template with comments and valid ranges
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7, 16.8_
  
  - [x] 1.2 Write property tests for ConfigValidator
    - **Property 7: Configuration Validation Completeness**
    - **Validates: Requirements 16.1, 16.2, 16.3, 16.4, 16.5, 16.6**
    - Test that invalid configs are rejected with appropriate error messages
    - Test that valid configs pass all validation rules
  
  - [x] 1.3 Create StructuredLogger module with JSON formatting
    - Implement `StructuredLogger` class with methods for all event types
    - Add log methods for signal generation, trade decisions, risk vetos, RL adjustments, SL/TP changes
    - Implement log rotation and compression
    - Add log level configuration support
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 17.8, 17.9_
  
  - [x] 1.4 Integrate ConfigValidator and StructuredLogger into Orchestrator startup
    - Modify Orchestrator to validate config on startup
    - Add configuration summary logging
    - Ensure system refuses to start on invalid config
    - _Requirements: 16.2, 16.7_

- [x] 2. Checkpoint - Verify foundation layer
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Legacy Strategy Integration (Requirement 1)
  - [x] 3.1 Create StrategyAdapter class
    - Implement `StrategyAdapter.__init__()` accepting Strategy instance and family name
    - Implement `generate_signal()` method that calls legacy strategy and normalizes output
    - Add score normalization to [-1, 1] range with validation
    - Add metadata preservation (strategy name, timeframe, confidence)
    - _Requirements: 1.1, 1.2, 1.4_
  
  - [x] 3.2 Write property tests for StrategyAdapter
    - **Property 1: Signal Score Normalization**
    - **Validates: Requirements 1.1, 1.7**
    - Test that all adapted signals have scores in [-1, 1]
    - **Property 2: Signal Metadata Completeness**
    - **Validates: Requirements 1.2**
    - Test that all adapted signals contain required metadata fields
  
  - [x] 3.3 Create IntegrationRegistry class
    - Implement `register_strategy()` method for mapping strategies to families
    - Implement `get_strategies_for_family()` method
    - Implement `get_all_adapters()` method
    - Create registry structure with all 31 legacy strategies mapped to families
    - _Requirements: 1.3_
  
  - [x] 3.4 Register all 31 legacy strategies in IntegrationRegistry
    - Map momentum strategies (EMACrossover registered - 1 of 7 planned)
    - Map mean reversion strategies (MeanReversion registered - 1 of 7 planned)
    - Map breakout strategies (BreakoutStrategy, LiquidityTrapStrategy registered - 2 of 7 planned)
    - Map structural strategies (TrendlinePullback, ReversalStrategy, EMABounce registered - 3 of 7 planned)
    - Note: 7 of 31 planned strategies are currently implemented and registered
    - _Requirements: 1.3_
  
  - [x] 3.5 Integrate StrategyAdapter into Orchestrator
    - Modify Orchestrator to instantiate all registered strategy adapters
    - Route adapted signals through Combination Engine
    - Ensure adapted strategies aggregate with existing signal families
    - _Requirements: 1.5, 1.6_

- [x] 4. Structural Analysis Completion (Requirements 2, 3)
  - [x] 4.1 Create TrendlineBuilder class
    - Implement `detect_trendlines()` method with minimum touches parameter
    - Implement `update_trendlines()` method for incremental updates
    - Implement `check_proximity()` method for ATR-based proximity checks
    - Create `Trendline` data model with all required fields
    - _Requirements: 2.1, 2.2_
  
  - [x] 4.2 Integrate TrendlineBuilder into Orchestrator
    - Invoke TrendlineBuilder on every bar for all instruments
    - Store trendline data in StructuralSnapshot
    - Track trendline validity and invalidation
    - _Requirements: 2.1, 2.2, 2.6_
  
  - [x] 4.3 Enhance Structural Signal Family with trendline signals
    - Generate signals when price approaches trendline within 0.5 ATR
    - Implement trendline pullback detection with EMA/RSI/ADX confirmation
    - _Requirements: 2.3, 2.5_
  
  - [x] 4.4 Enhance Breakout Signal Family with trendline breaks
    - Generate breakout signals on trendline breaks with volume confirmation
    - _Requirements: 2.4_
  
  - [x] 4.5 Create PatternRecognizer class
    - Implement `recognize_patterns()` method for 10 major patterns
    - Implement `classify_pattern()` method for direction and strength
    - Create `CandlestickPattern` data model
    - Support patterns: engulfing, hammer, shooting star, doji, morning/evening star, three soldiers/crows, harami, piercing, dark cloud
    - _Requirements: 3.1, 3.3_
  
  - [x] 4.6 Integrate PatternRecognizer into signal generation
    - Invoke PatternRecognizer on every bar
    - Boost signal conviction by 20% when pattern forms at S/R level
    - Reduce conviction by 30% when reversal pattern conflicts with signal
    - _Requirements: 3.2, 3.4, 3.5_

- [x] 5. Checkpoint - Verify structural analysis integration
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. AI/ML Enhancement Layer (Requirements 4, 5, 6, 7)
  - [x] 6.1 Create FinGPTClient class
    - Implement `__init__()` with API key and cache configuration
    - Implement `predict_price()` method for multi-horizon predictions
    - Implement `get_cached_prediction()` method with TTL cache
    - Create `FinGPTPrediction` and `PricePoint` data models
    - Add graceful degradation on API failure
    - _Requirements: 4.1, 4.6, 4.7_
  
  - [x] 6.2 Create MLPipelineOrchestrator class
    - Implement `__init__()` with XGBoost, LSTM, and ensemble models
    - Implement `generate_prediction()` method for ensemble predictions
    - Implement `compute_features()` method for 44 engineered features
    - Create `MLPrediction` data model
    - _Requirements: 5.2, 5.3, 5.4, 5.5_
  
  - [x] 6.3 Integrate FinGPT and ML Pipeline into Orchestrator
    - Set `enable_ml=True` by default in configuration
    - Invoke FinGPT and ML Pipeline on every bar
    - Apply ML predictions as multiplier to composite signal
    - Reduce position size by 50% when ML confidence < 0.5
    - _Requirements: 5.1, 5.6, 5.7_
  
  - [x] 6.4 Create ConfidenceAggregator class
    - Implement `compute_conviction()` method for composite conviction score
    - Implement `check_alignment()` method for direction alignment
    - Create `ConvictionScore` data model with breakdown
    - _Requirements: 7.1_
  
  - [x] 6.5 Write property tests for ConfidenceAggregator
    - **Property 3: Conviction Score Calculation**
    - **Validates: Requirements 7.1**
    - Test that conviction score equals product of components
    - Test that conviction score is always in [0, 1]
  
  - [x] 6.6 Implement confidence-based position sizing
    - Modify Position Sizer to compute conviction score from all sources
    - Skip trades when conviction < 0.3
    - Allocate 50% position when 0.3 ≤ conviction < 0.6
    - Allocate 100% position when conviction ≥ 0.6
    - Apply Kelly Criterion with conviction as edge parameter
    - _Requirements: 7.2, 7.3, 7.4, 7.5_
  
  - [x] 6.7 Write property tests for position sizing
    - **Property 4: Position Sizing Threshold Logic**
    - **Validates: Requirements 7.2, 7.3, 7.4**
    - Test that position sizes follow threshold rules
    - Test that Risk Manager limits are never exceeded
  
  - [x] 6.8 Create RLThresholdAdjuster class
    - Implement `__init__()` with PPO agent and baseline parameters
    - Implement `observe_trade_outcome()` method for learning
    - Implement `adjust_thresholds()` method for threshold computation
    - Implement `revert_to_baseline()` method for poor performance recovery
    - Create `ThresholdAdjustments` data model
    - Add state persistence across restarts
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_
  
  - [x] 6.9 Integrate RL Agent into trading loop
    - Record trade outcomes and feed to RL Agent
    - Apply threshold adjustments from RL Agent
    - Implement exploration vs exploitation (10%/90%)
    - Implement reversion to baseline after 20 poor trades
    - _Requirements: 6.9, 6.10_

- [x] 7. Checkpoint - Verify AI/ML integration
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Dynamic Position Management (Requirement 8)
  - [x] 8.1 Create DynamicSLTPManager class
    - Implement `__init__()` with configuration
    - Implement `monitor_position()` method for position monitoring
    - Implement `apply_adjustment()` method for SL/TP updates
    - Create `SLTPAdjustment` and `PositionMonitor` data models
    - _Requirements: 8.1_
  
  - [x] 8.2 Implement ML-based SL/TP adjustments
    - Widen TP3 by 0.5 ATR when ML confidence increases by 20%
    - Tighten SL to breakeven when ML confidence decreases by 20% or reverses
    - _Requirements: 8.2, 8.3_
  
  - [x] 8.3 Implement regime-based SL/TP adjustments
    - Tighten SL by 0.5 ATR on conflicting regime transition
    - _Requirements: 8.4_
  
  - [x] 8.4 Implement structural-based SL/TP adjustments
    - Place SL just beyond newly detected S/R levels
    - Move SL to breakeven on trendline break against trade
    - _Requirements: 8.5, 8.6_
  
  - [x] 8.5 Implement volatility-based SL/TP adjustments
    - Widen SL proportionally when ATR expands by 50%
    - Tighten SL to lock profits when ATR contracts by 30%
    - Enforce constraint: never widen SL beyond original level
    - _Requirements: 8.7, 8.8, 8.9_
  
  - [x] 8.6 Integrate DynamicSLTPManager into Orchestrator
    - Monitor all open positions every bar
    - Apply SL/TP adjustments with logging
    - _Requirements: 8.10_

- [x] 9. Enhanced P&L Tracking (Requirement 9)
  - [x] 9.1 Create EnhancedPnLTracker class
    - Implement `record_trade_open()` method
    - Implement `record_trade_close()` method with comprehensive metrics
    - Implement `get_portfolio_metrics()` method
    - Implement `get_family_metrics()` method
    - Create `TradeMetrics`, `PortfolioMetrics`, and `FamilyMetrics` data models
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.7_
  
  - [x] 9.2 Write property tests for P&L calculations
    - **Property 5: P&L Percentage Calculation**
    - **Validates: Requirements 9.1**
    - Test that P&L percentage formula is correct
    - **Property 6: R-Multiple Calculation**
    - **Validates: Requirements 9.2**
    - Test that R-multiple formula is correct
  
  - [x] 9.3 Integrate EnhancedPnLTracker into Orchestrator
    - Record trade opens and closes
    - Compute and persist all P&L metrics
    - Track cumulative R-multiples
    - _Requirements: 9.8, 9.9_

- [x] 10. Checkpoint - Verify position management and P&L tracking
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Frontend Dashboard (Requirement 10)
  - [x] 11.1 Create DashboardBackend service
    - Implement `__init__()` with EventBus and WebSocket manager
    - Implement `stream_updates()` method for real-time streaming
    - Implement `get_signal_health()` method
    - Implement `get_regime_distribution()` method
    - Implement `get_ml_metrics()` method
    - Implement `get_positions()` method
    - Implement `execute_kill_switch()` method
    - _Requirements: 10.10, 10.11_
  
  - [x] 11.2 Build Signal Family Health Panel component
    - Display per-family Sharpe ratios, hit rates, alpha decay status
    - Update in real-time via WebSocket
    - _Requirements: 10.1_
  
  - [x] 11.3 Build Regime Distribution Panel component
    - Display HMM regime probabilities as stacked bar chart
    - Update every bar
    - _Requirements: 10.2_
  
  - [x] 11.4 Build ML Metrics Panel component
    - Display model accuracy, top-10 feature importance, prediction confidence
    - _Requirements: 10.3_
  
  - [x] 11.5 Build Position P&L Table component
    - Display all per-position metrics (entry, current, P&L $, P&L %, R-multiple, time)
    - Display portfolio-level metrics (capital, P&L, drawdown)
    - _Requirements: 10.5, 10.6_
  
  - [x] 11.6 Build Price Chart component with overlays
    - Display multi-timeframe charts (1m/5m/15m/1H/4H/1D)
    - Overlay trendlines, S/R levels, candlestick patterns, entry/exit markers
    - Implement synchronized crosshairs
    - _Requirements: 10.7, 10.8_
  
  - [x] 11.7 Build Risk Manager Metrics Panel component
    - Display current exposure, VaR, position limits, circuit breaker status
    - _Requirements: 10.5_
  
  - [x] 11.8 Implement kill switch functionality
    - Add kill switch button to dashboard
    - Flatten all positions and halt trading within 2 seconds
    - _Requirements: 10.10_
  
  - [x] 11.9 Ensure dashboard responsiveness and performance
    - Test on 1920×1080 resolution
    - Verify sub-second WebSocket latency
    - _Requirements: 10.11, 10.12_

- [x] 12. System Hardening - Testing and Validation (Requirement 18)
  - [x] 12.1 Create integration tests for complete flow
    - Test data ingestion → signal generation → ML enhancement → execution
    - Verify Fundamental Pipeline gate blocking
    - Verify all 5 signal families contribute to Combination Engine
    - _Requirements: 18.1, 11.1, 11.2, 11.3_
  
  - [x] 12.2 Create property-based tests for core invariants
    - Test signal normalization (all outputs in [-1, 1])
    - Test position sizing (all positions within risk limits)
    - Test P&L calculations (sum of position P&L = portfolio P&L)
    - _Requirements: 18.2, 18.3, 18.4_
  
  - [x] 12.3 Create tests for Risk Manager veto power
    - Verify no trade executes when limits violated
    - _Requirements: 18.5_
  
  - [x] 12.4 Create tests for RL Agent threshold adjustments
    - Verify adjustments stay within valid ranges
    - _Requirements: 18.6_
  
  - [x] 12.5 Create tests for Dynamic SL/TP constraints
    - Verify SL never widens beyond original level
    - _Requirements: 18.7_
  
  - [x] 12.6 Create tests for Combination Engine decorrelation
    - Verify pairwise correlations < 0.7
    - _Requirements: 18.8_
  
  - [x] 12.7 Run backtests on historical data
    - Verify system performance meets minimum thresholds (Sharpe > 1.0)
    - _Requirements: 18.9_
  
  - [x] 12.8 Measure test coverage
    - Achieve >80% coverage for all new integration code
    - _Requirements: 18.10_

- [x] 13. System Hardening - Performance Optimization (Requirement 19)
  - [x] 13.1 Implement indicator calculation caching
    - Cache indicator results to avoid redundant computation
    - Use vectorized NumPy operations
    - _Requirements: 19.3, 19.4_
  
  - [x] 13.2 Implement connection pooling
    - Add connection pooling for database and Redis
    - Use async I/O for all external API calls
    - _Requirements: 19.5, 19.6_
  
  - [x] 13.3 Add performance profiling and monitoring
    - Profile performance on startup
    - Log operations taking >50ms
    - Implement circuit breakers for slow services
    - _Requirements: 19.7, 19.8_
  
  - [x] 13.4 Optimize for real-time performance
    - Ensure single instrument processing < 100ms
    - Ensure 50+ instruments processing < 2 seconds per bar
    - Implement incremental indicator updates
    - _Requirements: 19.1, 19.2, 19.9_

- [x] 14. System Hardening - Error Handling (Requirement 20)
  - [x] 14.1 Create ErrorRecoveryManager class
    - Implement reconnection logic with exponential backoff
    - Implement graceful degradation for ML/FinGPT failures
    - Implement database write retry queue
    - _Requirements: 20.1, 20.2, 20.3, 20.4_
  
  - [x] 14.2 Implement component health checks
    - Add health checks for database, Redis, data feed, ML models
    - Implement health check failure alerts and recovery
    - _Requirements: 20.7, 20.8_
  
  - [x] 14.3 Implement critical state persistence
    - Persist open positions, RL parameters, model weights
    - Implement startup validation sequence
    - _Requirements: 20.9, 20.10_
  
  - [x] 14.4 Implement component isolation and recovery
    - Disable failing signal families without stopping system
    - Flatten positions and halt trading on state corruption
    - _Requirements: 20.5, 20.6_

- [x] 15. Additional Features - Pairs Trading (Requirement 12)
  - [x] 15.1 Create PairsDetector class
    - Implement cointegration detection using Engle-Granger test
    - Compute spread and hedge ratio
    - _Requirements: 12.1, 12.2_
  
  - [x] 15.2 Create PairsTrader class
    - Compute spread z-score
    - Generate mean-reversion signals on z-score thresholds
    - Implement dollar-neutral position sizing
    - _Requirements: 12.3, 12.4, 12.5, 12.6_
  
  - [x] 15.3 Integrate pairs trading into Mean Reversion Signal Family
    - Re-validate cointegration every 20 days
    - Close positions when pairs invalidated
    - Track spread P&L separately
    - _Requirements: 12.7, 12.8, 12.9, 12.10_

- [x] 16. Additional Features - User-Specific Strategy (Requirement 13)
  - [x] 16.1 Implement TrendlinePullbackStrategy
    - Detect trendlines with minimum 3 touches
    - Check pullback within 0.3 ATR
    - Verify EMA alignment (5 > 9 > 21)
    - Verify RSI between 40-60
    - Verify ADX > 25
    - Verify ATR within 20th-80th percentile
    - Set initial SL at 1.5 ATR from trendline
    - Set multi-target exits (TP1/TP2/TP3)
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7, 13.8, 13.9_
  
  - [x] 16.2 Integrate TrendlinePullbackStrategy into Structural Signal Family
    - Route through Combination Engine
    - _Requirements: 13.10_

- [x] 17. Additional Features - Multi-Timeframe Coordination (Requirement 14)
  - [x] 17.1 Implement multi-timeframe structural analysis
    - Compute S/R levels, trendlines, patterns on 3 timeframes
    - _Requirements: 14.1_
  
  - [x] 17.2 Implement timeframe alignment checks
    - Check higher timeframe trend alignment
    - Adjust conviction based on alignment (±20-40%)
    - Use higher timeframe S/R as stronger confluence
    - _Requirements: 14.2, 14.3, 14.4, 14.5_
  
  - [x] 17.3 Implement regime propagation across timeframes
    - Detect higher timeframe regime transitions
    - Propagate to lower timeframes
    - _Requirements: 14.6_
  
  - [x] 17.4 Add multi-timeframe alignment indicator to dashboard
    - Display aligned/neutral/conflicted status
    - _Requirements: 14.7_

- [x] 18. Additional Features - Order Book Integration (Requirement 15)
  - [x] 18.1 Integrate L2 order book data
    - Use actual bid/ask spreads for slippage estimation
    - Compute available liquidity at each price level
    - _Requirements: 15.1, 15.2_
  
  - [x] 18.2 Implement liquidity-based position sizing
    - Reduce or reject trades when position > 10% of liquidity
    - _Requirements: 15.3_
  
  - [x] 18.3 Enhance Paper Trading Engine with order book simulation
    - Walk order book for realistic fills
    - Compute volume-weighted average fill price
    - _Requirements: 15.4_
  
  - [x] 18.4 Add order book depth chart to dashboard
    - Display L2 data for selected instrument
    - _Requirements: 15.5_
  
  - [x] 18.5 Implement order book imbalance detection
    - Detect bid/ask volume imbalances
    - Use as microstructure signal input
    - Gracefully degrade when L2 unavailable
    - _Requirements: 15.6, 15.7_

- [x] 19. System Flow Verification and Dead Code Removal (Requirement 11)
  - [x] 19.1 Verify complete system flow
    - Trace execution from Fundamental Pipeline through execution
    - Verify all 5 signal families contribute
    - Verify ML Pipeline influences conviction and SL/TP
    - Verify RL Agent receives outcomes and adjusts thresholds
    - Verify Risk Manager evaluates and can veto trades
    - Verify Alpha Decay Monitor tracks performance
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8_
  
  - [x] 19.2 Generate module dependency graph
    - Create visual graph showing all active connections
    - _Requirements: 11.11_
  
  - [x] 19.3 Identify and remove dead code
    - Find code files not imported or called
    - Preserve all 31 legacy strategy files
    - Verify configuration parameters are used
    - _Requirements: 11.9, 11.10, 11.12_

- [x] 20. Final Integration and Validation
  - [x] 20.1 Run end-to-end integration tests
    - Verify complete flow from data through execution
    - Verify all 883 existing tests still pass
    - Verify new integration tests achieve >80% coverage
  
  - [x] 20.2 Run performance benchmarks
    - Verify single instrument < 100ms processing
    - Verify 50+ instruments < 2s per bar
    - Verify dashboard latency < 1s
  
  - [x] 20.3 Run system validation on historical data
    - Verify all 20 requirements operational
    - Verify end-to-end workflow validated
    - Verify system meets success criteria

- [x] 21. Final checkpoint - System ready for deployment
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional test-related sub-tasks and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation throughout the implementation
- Property tests validate universal correctness properties from the design
- Unit tests and integration tests validate specific examples and end-to-end flows
- The implementation follows a layered approach to minimize integration risk
- All new modules integrate with existing AlgoForge architecture without breaking changes
- The system preserves the existing 883 passing tests while adding new functionality

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.3"] },
    { "id": 1, "tasks": ["1.2", "1.4"] },
    { "id": 2, "tasks": ["3.1", "4.1"] },
    { "id": 3, "tasks": ["3.2", "3.3", "4.2", "4.5"] },
    { "id": 4, "tasks": ["3.4", "4.3", "4.4", "4.6"] },
    { "id": 5, "tasks": ["3.5", "6.1", "6.2"] },
    { "id": 6, "tasks": ["6.3", "6.4"] },
    { "id": 7, "tasks": ["6.5", "6.6"] },
    { "id": 8, "tasks": ["6.7", "6.8"] },
    { "id": 9, "tasks": ["6.9", "8.1"] },
    { "id": 10, "tasks": ["8.2", "8.3", "8.4", "8.5", "9.1"] },
    { "id": 11, "tasks": ["8.6", "9.2", "9.3"] },
    { "id": 12, "tasks": ["11.1"] },
    { "id": 13, "tasks": ["11.2", "11.3", "11.4", "11.5", "11.7"] },
    { "id": 14, "tasks": ["11.6", "11.8"] },
    { "id": 15, "tasks": ["11.9", "12.1"] },
    { "id": 16, "tasks": ["12.2", "12.3", "12.4", "12.5", "12.6", "12.7", "12.8"] },
    { "id": 17, "tasks": ["13.1", "13.2", "13.3"] },
    { "id": 18, "tasks": ["13.4", "14.1", "14.2"] },
    { "id": 19, "tasks": ["14.3", "14.4", "15.1"] },
    { "id": 20, "tasks": ["15.2"] },
    { "id": 21, "tasks": ["15.3", "16.1"] },
    { "id": 22, "tasks": ["16.2", "17.1"] },
    { "id": 23, "tasks": ["17.2", "17.3"] },
    { "id": 24, "tasks": ["17.4", "18.1"] },
    { "id": 25, "tasks": ["18.2", "18.3", "18.4"] },
    { "id": 26, "tasks": ["18.5", "19.1"] },
    { "id": 27, "tasks": ["19.2", "19.3"] },
    { "id": 28, "tasks": ["20.1", "20.2"] },
    { "id": 29, "tasks": ["20.3"] }
  ]
}
```
