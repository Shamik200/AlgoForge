# Phase 2: Technical Indicator Engine — Plans

**Phase:** 02-technical-indicators
**Plans:** 4 (in 4 waves)
**Total requirements:** INDI-01 to INDI-14

## Wave 1 — Plan 01: Indicator Base + Trend Indicators (EMA, MACD, Supertrend)
**Files:** `indicator_base.py`, `ema.py`, `macd.py`, `supertrend.py`, `test_ema.py`, `test_macd.py`, `test_supertrend.py`
**Requirements:** INDI-01, INDI-05, INDI-09
**Depends on:** Core models, config

Creates the `Indicator` ABC, `IndicatorResult` model, and implements:
- EMA (6 periods: 5, 9, 21, 50, 100, 200)
- MACD (12, 26, 9)
- Supertrend (10, 3.0)

---

## Wave 2 — Plan 02: Volatility & Momentum Indicators (RSI, ADX, ATR, Bollinger, Keltner, Stochastic)
**Files:** `rsi.py`, `adx.py`, `atr.py`, `bollinger.py`, `keltner.py`, `stochastic.py`, tests
**Requirements:** INDI-02, INDI-03, INDI-04, INDI-06, INDI-07, INDI-10
**Depends on:** Wave 1 (EMA used inside ATR, Keltner, Supertrend)

Implements:
- RSI (14-period)
- ADX/DMI (14-period)
- ATR (14-period)
- Bollinger Bands (20, 2σ)
- Keltner Channels (20, 1.5×ATR)
- Stochastic Oscillator (14, 3, 3)

---

## Wave 3 — Plan 03: Volume & Structure Indicators (VWAP, Donchian, Volume Profile, OBV, Ichimoku)
**Files:** `vwap.py`, `donchian.py`, `volume_profile.py`, `obv.py`, `ichimoku.py`, tests
**Requirements:** INDI-08, INDI-11, INDI-12, INDI-13, INDI-14
**Depends on:** Wave 1

Implements:
- VWAP (session-based)
- Donchian Channels (20-period)
- Volume Profile (POC, VAH, VAL)
- OBV (cumulative)
- Ichimoku Cloud (9, 26, 52)

---

## Wave 4 — Plan 04: IndicatorEngine Orchestrator + Integration Tests
**Files:** `engine.py`, `test_engine.py`, `test_indicator_integration.py`
**Requirements:** All INDI-* (orchestration)
**Depends on:** Waves 1-3

Implements:
- `IndicatorEngine` — subscribes to `MarketDataEvent`, computes all 14 indicators, publishes `IndicatorUpdateEvent`
- Incremental update logic with rolling buffers
- In-memory caching (keyed by symbol:timeframe:indicator)
- Performance test: 100 instruments × 6 timeframes < 1 second
- Integration test: candle → engine → all indicators → event

---

*Created: 2026-04-18*
