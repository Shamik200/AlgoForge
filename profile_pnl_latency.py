"""AlgoForge Performance Profiling and Optimization Benchmark.

Synthesizes a realistic trended OHLCV dataset with pullbacks,
runs the complete pipeline (Indicators -> Structural Swings/Trendlines -> Strategy Signals -> Trade Simulation),
and profiles execution times (latency) and PnL metrics.
"""

import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
import structlog

import logging

# Enable structured logging or standard output logging for profiling
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING),
)

from algoforge.core.models import OHLCV, OHLCVSeries
from algoforge.core.constants import Timeframe, Direction, MarketRegime
from algoforge.technical.engine import IndicatorEngine, IndicatorSnapshot
from algoforge.technical.indicator_base import IndicatorResult
from algoforge.technical.structural.engine import StructuralEngine
from algoforge.strategies.trendline_pullback import TrendlinePullback


def generate_synthetic_data(symbol: str, num_bars: int = 1000) -> OHLCVSeries:
    """Generate high-fidelity, realistic trended price data with pullbacks.
    
    Creates a clear upward trend with periodic retracements to create
    clean swing points and support/resistance trendlines.
    """
    np.random.seed(42)  # High reproducibility
    base_price = 100.0
    candles = []
    start_time = datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)
    
    # Drift, cyclical wave, and noise
    t = np.arange(num_bars)
    drift = 0.04 * t  # General uptrend
    wave = 6.0 * np.sin(0.03 * t)  # Pullback cycle
    noise = np.random.normal(0, 0.4, num_bars)
    
    prices = base_price + drift + wave + noise
    
    for i in range(num_bars):
        close_p = float(prices[i])
        open_p = float(prices[i-1]) if i > 0 else close_p
        
        # Pullback simulation candles
        high_p = max(open_p, close_p) + np.random.uniform(0.1, 0.5)
        low_p = min(open_p, close_p) - np.random.uniform(0.1, 0.5)
        volume = float(np.random.randint(1000, 5000))
        
        candles.append(OHLCV(
            symbol=symbol,
            timeframe=Timeframe.M1,
            timestamp=start_time + timedelta(minutes=i),
            open=round(open_p, 4),
            high=round(high_p, 4),
            low=round(low_p, 4),
            close=round(close_p, 4),
            volume=volume
        ))
        
    return OHLCVSeries(symbol=symbol, timeframe=Timeframe.M1, candles=candles)

def run_profiler(label: str = "BASELINE", atr_touch=0.5, atr_sl=1.5, min_adx=15.0, min_rr=1.5) -> dict:
    """Run the complete pipeline over the synthetic dataset and profile latency & PnL."""
    symbol = "BTC-USD"
    series = generate_synthetic_data(symbol, num_bars=1000)
    
    indicator_engine = IndicatorEngine()
    structural_engine = StructuralEngine()
    
    # Precompute indicators on the full series once to avoid O(N^2) indicator overhead
    full_indicators = indicator_engine.compute(series)
    
    # Initialize strategy with requested parameters
    strategy = TrendlinePullback(
        atr_touch_multiplier=atr_touch,
        atr_sl_multiplier=atr_sl,
        min_adx=min_adx,
        min_rr_ratio=min_rr
    )
    
    # Timers for stages
    t_indicator = 0.0
    t_structural = 0.0
    t_strategy = 0.0
    
    eval_count = 0
    signals_generated = []
    
    # Backtest simulation loop
    start_loop = time.perf_counter()
    
    for i in range(100, len(series.candles)):
        eval_count += 1
        sub_candles = series.candles[:i]
        sub_series = OHLCVSeries(symbol=symbol, timeframe=Timeframe.M1, candles=sub_candles)
        
        # 1. Sliced Indicator Lookup (Zero recalculation cost)
        t0 = time.perf_counter()
        indicators = IndicatorSnapshot()
        for name in full_indicators.indicator_names:
            full_res = full_indicators.get(name)
            if full_res:
                sliced_values = {k: v[:i] for k, v in full_res.values.items()}
                sliced_res = IndicatorResult(
                    name=full_res.name,
                    values=sliced_values,
                    params=full_res.params,
                    timestamp=full_res.timestamp,
                    metadata=full_res.metadata
                )
                indicators.set(name, sliced_res)
        t_indicator += (time.perf_counter() - t0)
        
        # 2. Structural Analysis
        ema_result = indicators.get("ema")
        atr_result = indicators.get("atr")
        ema_values = ema_result.values if ema_result else None
        atr_values = atr_result.values.get("atr", []) if atr_result else None
        
        t0 = time.perf_counter()
        structure = structural_engine.analyze(sub_series, ema_values=ema_values, atr_values=atr_values)
        t_structural += (time.perf_counter() - t0)
        
        # 3. Strategy Evaluation
        closes = sub_series.closes
        highs = sub_series.highs
        lows = sub_series.lows
        volumes = sub_series.volumes
        opens = [c.open for c in sub_candles]
        
        t0 = time.perf_counter()
        signals = strategy.evaluate(
            symbol=symbol,
            timeframe=Timeframe.M1,
            indicators=indicators,
            structure=structure,
            closes=closes,
            highs=highs,
            lows=lows,
            volumes=volumes,
            opens=opens
        )
        t_strategy += (time.perf_counter() - t0)
        
        for sig in signals:
            signals_generated.append((i, sig))
            
    total_time = time.perf_counter() - start_loop
    
    # 4. Simulate Trades & Calculate PnL
    trades = []
    active_position = None
    
    closes_arr = np.array(series.closes)
    highs_arr = np.array(series.highs)
    lows_arr = np.array(series.lows)
    
    signal_by_index = {idx: sig for idx, sig in signals_generated}
    
    for idx in range(100, len(series.candles)):
        close_p = closes_arr[idx]
        high_p = highs_arr[idx]
        low_p = lows_arr[idx]
        
        if active_position:
            entry, sl, tp, direction, entry_idx = active_position
            
            if direction == Direction.LONG:
                if low_p <= sl:
                    pnl = sl - entry
                    pnl_pct = pnl / entry
                    trades.append(pnl_pct)
                    active_position = None
                elif high_p >= tp:
                    pnl = tp - entry
                    pnl_pct = pnl / entry
                    trades.append(pnl_pct)
                    active_position = None
            else:  # SHORT
                if high_p >= sl:
                    pnl = entry - sl
                    pnl_pct = pnl / entry
                    trades.append(pnl_pct)
                    active_position = None
                elif low_p <= tp:
                    pnl = entry - tp
                    pnl_pct = pnl / entry
                    trades.append(pnl_pct)
                    active_position = None
        else:
            if idx in signal_by_index:
                sig = signal_by_index[idx]
                active_position = (sig.entry_price, sig.stop_loss, sig.take_profit, sig.direction, idx)
                
    num_trades = len(trades)
    wins = [t for t in trades if t > 0]
    win_rate = len(wins) / num_trades if num_trades > 0 else 0.0
    total_pnl = sum(trades)
    avg_pnl = np.mean(trades) if num_trades > 0 else 0.0
    
    sharpe = 0.0
    if num_trades > 2:
        std_pnl = np.std(trades)
        if std_pnl > 0:
            sharpe = (avg_pnl / std_pnl) * np.sqrt(252)
            
    print(f"\n==========================================")
    print(f"  AlgoForge Profiler: {label}")
    print(f"  Parameters: ATR_Touch={atr_touch}, ATR_SL={atr_sl}, Min_ADX={min_adx}, Min_RR={min_rr}")
    print(f"==========================================")
    print(f"  Total bars evaluated:  {eval_count}")
    print(f"  Total processing time: {total_time:.2f}s")
    print(f"  Avg Latency per bar:   {(total_time / eval_count)*1000:.2f} ms")
    print(f"  --- Component Latency Breakdown ---")
    print(f"    Indicator Engine:    {t_indicator:.2f}s ({(t_indicator / eval_count)*1000:.2f} ms/bar)")
    print(f"    Structural Engine:   {t_structural:.2f}s ({(t_structural / eval_count)*1000:.2f} ms/bar)")
    print(f"    Strategy Evaluation: {t_strategy:.2f}s ({(t_strategy / eval_count)*1000:.2f} ms/bar)")
    print(f"  --- PnL & Trade Performance ---")
    print(f"    Signals Generated:   {len(signals_generated)}")
    print(f"    Total Trades Closed: {num_trades}")
    print(f"    Win Rate:            {win_rate:.2%}")
    print(f"    Total Simulated PnL: {total_pnl:.2%}")
    print(f"    Sharpe Ratio:        {sharpe:.2f}")
    print(f"==========================================\n")
    
    return {
        "eval_count": eval_count,
        "total_time_ms": total_time * 1000,
        "avg_latency_ms": (total_time / eval_count) * 1000,
        "t_indicator_ms": t_indicator * 1000,
        "t_structural_ms": t_structural * 1000,
        "t_strategy_ms": t_strategy * 1000,
        "signals_count": len(signals_generated),
        "trades_count": num_trades,
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "sharpe": sharpe
    }

def run_optimization_sweep():
    """Run a parametric grid search to optimize PnL and Sharpe Ratio."""
    print("Starting Parametric Optimization Grid Search Sweep...")
    
    # Grid of parameters to test
    atr_touches = [0.4, 0.6]
    atr_sls = [2.0, 2.5]
    min_adxs = [20.0, 25.0]
    min_rrs = [1.8, 2.2]
    
    best_pnl = -999.0
    best_params = {}
    best_result = {}
    
    # Run a subset of the grid for quick search
    for touch in atr_touches:
        for sl in atr_sls:
            for adx in min_adxs:
                for rr in min_rrs:
                    print(f"Testing combination: Touch={touch}, SL={sl}, ADX={adx}, RR={rr}")
                    res = run_profiler(f"SWEEP_Touch_{touch}_SL_{sl}_ADX_{adx}_RR_{rr}", 
                                       atr_touch=touch, atr_sl=sl, min_adx=adx, min_rr=rr)
                    if res["total_pnl"] > best_pnl:
                        best_pnl = res["total_pnl"]
                        best_params = {"atr_touch": touch, "atr_sl": sl, "min_adx": adx, "min_rr": rr}
                        best_result = res
                        
    print("\n" + "="*60)
    print("  OPTIMIZATION SWEEP COMPLETE")
    print("="*60)
    print(f"  Best Parameters Found:")
    print(f"    ATR Touch Multiplier:  {best_params['atr_touch']}")
    print(f"    ATR SL Multiplier:     {best_params['atr_sl']}")
    print(f"    Minimum ADX Limit:     {best_params['min_adx']}")
    print(f"    Minimum Risk-Reward:   {best_params['min_rr']}")
    print(f"  Performance:")
    print(f"    Total PnL:             {best_result['total_pnl']:.2%}")
    print(f"    Sharpe Ratio:          {best_result['sharpe']:.2f}")
    print(f"    Win Rate:              {best_result['win_rate']:.2%}")
    print(f"    Trades Closed:         {best_result['trades_count']}")
    print("="*60 + "\n")

if __name__ == "__main__":
    # 1. Run Baseline
    run_profiler("BASELINE")
    
    # 2. Run Optimization Sweep
    run_optimization_sweep()
