# 🚀 AlgoForge Full Trading Dashboard - Quick Start

## ✅ Your Original Dashboard is COMPLETE!

Good news! Your comprehensive trading dashboard in the `frontend/` directory has **ALL** the features you mentioned:

### Features Already Working:
- ✅ **Market Selection** - Choose Crypto/Forex/Stocks
- ✅ **Broker Selection** - Binance/Bybit
- ✅ **Universe Size** - Configure how many assets to scan
- ✅ **Score Threshold** - Set minimum score for trades
- ✅ **Start/Stop/Reset Controls** - Full engine control
- ✅ **Live Profit Graph** - Real-time equity curve
- ✅ **Confidence Display** - See ML confidence scores
- ✅ **Open Positions** - Live position monitoring
- ✅ **Closed Positions** - Complete trade history
- ✅ **Market Scanner** - Real-time asset scoring
- ✅ **System Logs** - Event tracking
- ✅ **WebSocket Updates** - Sub-second latency

## 🎯 Quick Start (3 Steps):

### Option 1: Automatic Start (Easiest)

**Double-click this file:**
```
START_FULL_DASHBOARD.bat
```

This will:
1. Start the backend API server
2. Start the frontend dashboard
3. Open your browser automatically

### Option 2: Manual Start

**Step 1: Start Backend**
```bash
python -m algoforge.api.server
```
Backend will run on: `http://127.0.0.1:8000`

**Step 2: Start Frontend** (in a new terminal)
```bash
cd frontend
npm run dev
```
Frontend will run on: `http://localhost:3000`

**Step 3: Open Browser**
```
http://localhost:3000
```

## 📊 Dashboard Layout:

```
┌─────────────────────────────────────────────────────────────────┐
│  ⚡ ALGOFORGE TERMINAL                    $100,000  $100,000  ● LIVE │
├──────────────┬──────────────────────────────────────────────────┤
│              │  📊 STATS: Positions | Trades | P&L | Drawdown  │
│  ENGINE      ├──────────────────────────────────────────────────┤
│  CONTROLS    │  📈 LIVE EQUITY CURVE (Real-time graph)         │
│              ├──────────────────────────────────────────────────┤
│  ▶ START     │  🔍 MARKET SCANNER    │  📍 LIVE POSITIONS      │
│  ⏸ PAUSE     │  - Asset scores       │  - Symbol, Side         │
│  🔄 RESET    │  - Regime detection   │  - Entry, Current       │
│  🛑 FLATTEN  │  - Trend indicators   │  - SL/TP levels         │
│              │  - Bid/Ask prices     │  - Unrealized P&L       │
│──────────────┤                       ├─────────────────────────┤
│  ⚙ CONFIG    │                       │  📜 TRADE HISTORY       │
│  Market: ▼   │                       │  - Closed positions     │
│  Broker: ▼   │                       │  - Realized P&L         │
│  Universe: # │                       │  - Strategy used        │
│  Threshold:# │                       │  - Exit prices          │
│  [APPLY]     │                       │                         │
│──────────────┴───────────────────────┴─────────────────────────┤
│  📋 SYSTEM LOGS (Real-time events, color-coded)                │
└─────────────────────────────────────────────────────────────────┘
```

## 🎮 How to Use:

### 1. Configure System (Left Sidebar)

**Market Selection:**
- Crypto (default)
- Forex
- Stocks

**Broker:**
- Binance (default)
- Bybit

**Universe Size:**
- How many assets to scan (e.g., 50)
- Higher = more opportunities, slower

**Score Threshold:**
- Minimum score to trade (e.g., 65)
- Higher = fewer but higher quality trades

**Click "Apply Configuration"** to save

### 2. Start Trading

**Click "START TRADING"** (green button)

The system will:
1. Connect to exchange WebSocket
2. Scan universe for opportunities
3. Calculate scores and regimes
4. Execute trades based on confidence
5. Update dashboard in real-time

### 3. Monitor Performance

**Watch the dashboard update:**
- Equity curve shows profit/loss
- Open positions show active trades
- Market scanner shows opportunities
- System logs show all events

### 4. Control System

**PAUSE** - Stop trading, keep positions
**RESET** - Clear all data, start fresh
**FLATTEN** - Emergency close all positions

## 📈 Understanding the Dashboard:

### Stat Cards (Top Row)

**Open Positions:**
- Number of active trades
- Green when > 0

**Total Trades:**
- All trades executed
- Shows W/L breakdown
- Win rate percentage

**Realized P&L:**
- Total profit/loss
- Green = profit, Red = loss
- Includes commission

**Max Drawdown:**
- Worst peak-to-trough decline
- Red if > 5%

### Live Equity Curve

**Real-time graph showing:**
- Portfolio value over time
- Profit/loss from $100,000 start
- Updates every bar

### Market Scanner

**Shows top assets by score:**
- **Symbol** - Asset name
- **Score** - Composite score (0-100)
- **Trend** - UP ↗ / DOWN ↘ / SIDEWAYS →
- **Regime** - Market state (trending/range/breakout/reversal/liquidity_trap)
- **Bid** - Current bid price
- **Status** - ACTIVE (trading) / EVAL (evaluating)

**Color coding:**
- Green score = Above threshold (will trade)
- Gray score = Below threshold (skip)

### Live Positions

**Active trades showing:**
- **Symbol** - Asset being traded
- **Side** - LONG (green) / SHORT (red)
- **Strategy** - Which strategy opened it
- **Entry Price** - Price when entered
- **Current Price** - Live price
- **SL** - Stop loss level
- **TP** - Take profit level
- **Unrealized P&L** - Current profit/loss

**Updates in real-time** as prices change

### Trade History

**Closed positions showing:**
- **Symbol** - Asset traded
- **Side** - LONG / SHORT
- **Strategy** - Strategy used
- **Exit Price** - Price when closed
- **Realized P&L** - Final profit/loss

**Shows last 20 trades** (newest first)

### System Logs

**Real-time event log with color coding:**
- 🟢 **Green** - Trade executions
- 🟡 **Yellow** - Position closes
- 🔴 **Red** - Errors, flatten events
- 🔵 **Blue** - System start/reset
- ⚪ **Gray** - General events

**Auto-scrolls** to show newest events

### Engine Stats (Left Sidebar)

**System metrics:**
- **Strategies Active** - Number of strategies running
- **Signals Generated** - Total signals created
- **Signals Executed** - Signals that became trades
- **Active Assets** - Assets currently being traded

**Shows asset badges** for quick reference

## 🧠 Confidence-Based Trading:

The system uses ML confidence to size positions:

**Confidence < 30%:**
- ❌ **SKIP** - Don't trade

**Confidence 30-60%:**
- ⚠️ **HALF** - 50% position size

**Confidence ≥ 60%:**
- ✅ **FULL** - 100% position size

**You can see confidence scores in:**
- Market scanner (regime confidence)
- Position details (when opened)
- Trade history (final confidence)

## 🔧 Advanced Configuration:

### Backend API Configuration

Edit `config/settings.yaml` for:
- Risk parameters
- Position sizing
- Stop loss / take profit
- ML model settings
- Regime detection parameters

### Frontend Customization

Edit `frontend/src/app/page.tsx` for:
- UI colors and themes
- Chart configurations
- Update intervals
- Display preferences

## 🐛 Troubleshooting:

### Backend won't start:
```bash
# Check if port 8000 is in use
netstat -ano | findstr :8000

# Kill process if needed
taskkill /PID <PID> /F

# Restart backend
python -m algoforge.api.server
```

### Frontend won't start:
```bash
# Reinstall dependencies
cd frontend
rm -rf node_modules package-lock.json
npm install

# Start again
npm run dev
```

### WebSocket not connecting:
1. Check backend is running on port 8000
2. Check browser console for errors
3. Verify CORS settings in `src/algoforge/api/server.py`

### No data showing:
1. Click "START TRADING" button
2. Wait 30 seconds for first scan
3. Check system logs for errors
4. Verify exchange API credentials in `.env`

## 📚 API Endpoints:

**Backend runs on:** `http://127.0.0.1:8000`

**REST Endpoints:**
- `GET /api/health` - Health check
- `GET /api/config` - Get configuration
- `POST /api/config` - Update configuration
- `POST /api/system/start` - Start trading
- `POST /api/system/stop` - Pause trading
- `POST /api/system/reset` - Reset all data
- `POST /api/system/flatten` - Emergency flatten
- `GET /api/trades` - Get trade history
- `GET /api/trades/stats` - Strategy statistics
- `GET /api/trades/export` - Export trades JSON

**WebSocket:**
- `WS /ws/telemetry` - Real-time updates

## 🎨 Color Scheme:

**Background:** Dark theme (#0d1117)
**Cards:** Slightly lighter (#161b22)
**Borders:** Gray (#30363d)
**Text:** White/Gray
**Profit:** Green (#3fb950)
**Loss:** Red (#f85149)
**Warning:** Yellow (#d29922)
**Info:** Blue (#58a6ff)

## 🚀 Performance:

**Expected latency:**
- WebSocket updates: < 100ms
- UI refresh: 60 FPS
- Chart updates: Real-time
- API calls: < 50ms

**Recommended specs:**
- CPU: 4+ cores
- RAM: 8GB+
- Network: Stable connection
- Browser: Chrome/Edge (latest)

## 📝 Notes:

1. **Paper Trading Only** - This is a simulation, no real money
2. **Data Persistence** - Trades saved to SQLite database
3. **State Recovery** - System restores state on restart
4. **Risk Management** - Built-in position limits and circuit breakers
5. **Multi-Strategy** - 6 strategies running simultaneously

## 🎯 Next Steps:

1. **Start the dashboard** using the batch file
2. **Configure your preferences** (market, broker, universe, threshold)
3. **Click START TRADING** and watch it work
4. **Monitor performance** and adjust settings
5. **Review trade history** to understand decisions

## 💡 Tips:

- **Start with small universe** (20-30 assets) to learn
- **Use higher threshold** (70+) for quality over quantity
- **Watch the logs** to understand system behavior
- **Check regime detection** - it affects trade decisions
- **Monitor drawdown** - reset if it gets too high
- **Review closed trades** - learn from winners and losers

## 🆘 Need Help?

Check these files:
- `FRONTEND_ENHANCEMENT_PLAN.md` - Detailed feature list
- `README.md` - Project overview
- `docs/` - Additional documentation
- System logs in dashboard - Real-time diagnostics

---

**Your dashboard is ready to go! Just run `START_FULL_DASHBOARD.bat` and start trading!** 🚀
