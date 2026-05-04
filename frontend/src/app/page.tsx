"use client";
import React, { useState, useEffect, useRef } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { Play, Square, ShieldAlert, RefreshCw, Settings, TrendingUp, TrendingDown, Minus, Activity, Zap, DollarSign, BarChart2, AlertCircle } from "lucide-react";

const API = "http://127.0.0.1:8000";
const WS  = "ws://127.0.0.1:8000/ws/telemetry";

const REGIME_COLOR: Record<string, string> = {
  trending:       "text-blue-400",
  range:          "text-yellow-400",
  breakout:       "text-purple-400",
  reversal:       "text-orange-400",
  liquidity_trap: "text-red-400",
};

const REGIME_BG: Record<string, string> = {
  trending:       "bg-blue-500/10 border-blue-500/30",
  range:          "bg-yellow-500/10 border-yellow-500/30",
  breakout:       "bg-purple-500/10 border-purple-500/30",
  reversal:       "bg-orange-500/10 border-orange-500/30",
  liquidity_trap: "bg-red-500/10 border-red-500/30",
};

function StatCard({ label, value, sub, color = "text-white" }: any) {
  return (
    <div className="bg-[#161b22] border border-gray-800 rounded-xl p-4 shadow-lg">
      <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</div>
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      {sub && <div className="text-xs text-gray-600 mt-1">{sub}</div>}
    </div>
  );
}

export default function AlgoForge() {
  const [status, setStatus]             = useState("OFFLINE");
  const [equity, setEquity]             = useState(100000);
  const [cash, setCash]                 = useState(100000);
  const [positions, setPositions]       = useState(0);
  const [totalTrades, setTotalTrades]   = useState(0);
  const [wins, setWins]                 = useState(0);
  const [losses, setLosses]             = useState(0);
  const [totalPnl, setTotalPnl]         = useState(0);
  const [totalComm, setTotalComm]       = useState(0);
  const [drawdown, setDrawdown]         = useState(0);
  const [sigGen, setSigGen]             = useState(0);
  const [sigFill, setSigFill]           = useState(0);
  const [equityCurve, setEquityCurve]   = useState<any[]>([]);
  const [logs, setLogs]                 = useState<string[]>([]);
  const [scoredAssets, setScoredAssets] = useState<any[]>([]);
  const [openPos, setOpenPos]           = useState<any[]>([]);
  const [closedPos, setClosedPos]       = useState<any[]>([]);
  const [activeAssets, setActiveAssets] = useState<string[]>([]);

  // Config
  const [market, setMarket]           = useState("crypto");
  const [broker, setBroker]           = useState("binance");
  const [universeSize, setUnivSize]   = useState(50);
  const [threshold, setThreshold]     = useState(65);

  // Auto-scroll logs
  const logsRef = useRef<HTMLDivElement>(null);
  useEffect(() => { logsRef.current?.scrollTo(0, 0); }, [logs]);

  useEffect(() => {
    let ws: WebSocket;
    let mounted = true;
    const connect = () => {
      ws = new WebSocket(WS);
      ws.onmessage = (e) => {
        const d = JSON.parse(e.data);
        setStatus(d.status || "OFFLINE");
        if (d.equity           !== undefined) setEquity(d.equity);
        if (d.cash             !== undefined) setCash(d.cash);
        if (d.positions        !== undefined) setPositions(d.positions);
        if (d.total_trades     !== undefined) setTotalTrades(d.total_trades);
        if (d.winning_trades   !== undefined) setWins(d.winning_trades);
        if (d.losing_trades    !== undefined) setLosses(d.losing_trades);
        if (d.total_pnl        !== undefined) setTotalPnl(d.total_pnl);
        if (d.total_commission !== undefined) setTotalComm(d.total_commission);
        if (d.max_drawdown_pct !== undefined) setDrawdown(d.max_drawdown_pct);
        if (d.signals_generated !== undefined) setSigGen(d.signals_generated);
        if (d.signals_filled    !== undefined) setSigFill(d.signals_filled);
        if (d.equity_curve)     setEquityCurve(d.equity_curve.map((p: any) => ({ ...p, time: p.time?.slice(11, 16) })));
        if (d.logs)             setLogs(d.logs);
        if (d.scored_assets)    setScoredAssets(d.scored_assets);
        if (d.open_positions)   setOpenPos(d.open_positions);
        if (d.closed_positions) setClosedPos(d.closed_positions);
        if (d.active_assets)    setActiveAssets(d.active_assets);
      };
      ws.onclose = () => { if (mounted) setTimeout(connect, 3000); };
    };
    connect();
    return () => { mounted = false; ws?.close(); };
  }, []);

  const cmd = async (action: string) => {
    try { await fetch(`${API}/api/system/${action}`, { method: "POST" }); }
    catch { /* backend logs it */ }
  };

  const applyConfig = async () => {
    try {
      await fetch(`${API}/api/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ market, broker, universe_size: universeSize, selected_assets_count: 5, min_liquidity: 1000000, volatility_filter: 1.5, max_risk_pct: 1.5, max_drawdown_pct: 15.0 }),
      });
    } catch { /* logged server-side */ }
  };

  const running = status === "RUNNING";
  const pnlColor = totalPnl >= 0 ? "text-green-400" : "text-red-400";
  const winRate  = totalTrades > 0 ? ((wins / totalTrades) * 100).toFixed(1) : "—";

  return (
    <div className="min-h-screen bg-[#0d1117] text-gray-300 font-sans">
      {/* HEADER */}
      <header className="border-b border-gray-800 px-6 py-4 flex items-center justify-between sticky top-0 z-50 bg-[#0d1117]/95 backdrop-blur">
        <div className="flex items-center gap-3">
          <Activity className="text-blue-500 w-6 h-6" />
          <span className="text-xl font-bold text-white tracking-widest">ALGOFORGE <span className="text-blue-500 font-light">TERMINAL</span></span>
          <span className="ml-2 text-xs bg-blue-500/10 border border-blue-500/30 text-blue-400 px-2 py-0.5 rounded-full">PAPER TRADING</span>
        </div>
        <div className="flex items-center gap-8">
          <div className="text-right">
            <div className="text-xs text-gray-500 uppercase tracking-widest">Portfolio Equity</div>
            <div className="text-2xl font-bold text-white">${equity.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
          </div>
          <div className="text-right">
            <div className="text-xs text-gray-500 uppercase tracking-widest">Free Cash</div>
            <div className="text-lg font-semibold text-gray-300">${cash.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
          </div>
          <div className="flex items-center gap-2">
            {running
              ? <span className="flex items-center gap-2 text-green-400 font-bold"><span className="animate-pulse w-2 h-2 rounded-full bg-green-400 inline-block" />LIVE</span>
              : <span className="flex items-center gap-2 text-red-500 font-bold"><span className="w-2 h-2 rounded-full bg-red-500 inline-block" />OFFLINE</span>}
          </div>
        </div>
      </header>

      <div className="flex h-[calc(100vh-65px)]">
        {/* LEFT SIDEBAR */}
        <aside className="w-64 border-r border-gray-800 flex flex-col gap-4 p-4 overflow-y-auto flex-shrink-0">
          {/* Controls */}
          <div className="bg-[#161b22] border border-gray-800 rounded-xl p-4">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-2"><Zap className="w-3 h-3" /> Engine Controls</div>
            <div className="flex flex-col gap-2">
              <button onClick={() => cmd("start")} disabled={running}
                className="w-full flex items-center justify-center gap-2 py-2 rounded-lg font-semibold text-sm transition-all bg-green-600 hover:bg-green-500 disabled:opacity-40 disabled:cursor-not-allowed text-white">
                <Play className="w-4 h-4" /> START TRADING
              </button>
              <button onClick={() => cmd("stop")} disabled={!running}
                className="w-full flex items-center justify-center gap-2 py-2 rounded-lg font-semibold text-sm transition-all bg-gray-700 hover:bg-gray-600 disabled:opacity-40 disabled:cursor-not-allowed text-white">
                <Square className="w-4 h-4" /> PAUSE
              </button>
              <button onClick={() => cmd("reset")}
                className="w-full flex items-center justify-center gap-2 py-2 rounded-lg font-semibold text-sm transition-all bg-yellow-700 hover:bg-yellow-600 text-white">
                <RefreshCw className="w-4 h-4" /> RESET ALL DATA
              </button>
              <button onClick={() => cmd("flatten")}
                className="w-full flex items-center justify-center gap-2 py-2 rounded-lg font-semibold text-sm transition-all bg-red-700 hover:bg-red-600 text-white mt-1">
                <ShieldAlert className="w-4 h-4" /> EMERGENCY FLATTEN
              </button>
            </div>
          </div>

          {/* Config */}
          <div className="bg-[#161b22] border border-gray-800 rounded-xl p-4">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-2"><Settings className="w-3 h-3" /> Configuration</div>
            <div className="flex flex-col gap-3">
              <div>
                <label className="text-xs text-gray-600 block mb-1">Market</label>
                <select value={market} onChange={e => setMarket(e.target.value)}
                  className="w-full bg-[#0d1117] border border-gray-700 rounded-md p-1.5 text-xs text-white focus:border-blue-500 outline-none">
                  <option value="crypto">Crypto</option>
                  <option value="forex">Forex</option>
                  <option value="stocks">Stocks</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-600 block mb-1">Broker</label>
                <select value={broker} onChange={e => setBroker(e.target.value)}
                  className="w-full bg-[#0d1117] border border-gray-700 rounded-md p-1.5 text-xs text-white focus:border-blue-500 outline-none">
                  <option value="binance">Binance</option>
                  <option value="bybit">Bybit</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-600 block mb-1">Universe Size</label>
                <input type="number" value={universeSize} onChange={e => setUnivSize(+e.target.value)}
                  className="w-full bg-[#0d1117] border border-gray-700 rounded-md p-1.5 text-xs text-white outline-none" />
              </div>
              <div>
                <label className="text-xs text-gray-600 block mb-1">Score Threshold</label>
                <input type="number" value={threshold} onChange={e => setThreshold(+e.target.value)}
                  className="w-full bg-[#0d1117] border border-gray-700 rounded-md p-1.5 text-xs text-white outline-none" />
              </div>
              <button onClick={applyConfig}
                className="w-full bg-blue-600 hover:bg-blue-500 text-white py-2 rounded-lg text-xs font-semibold transition-all">
                Apply Configuration
              </button>
            </div>
          </div>

          {/* Engine Stats */}
          <div className="bg-[#161b22] border border-gray-800 rounded-xl p-4">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-2"><BarChart2 className="w-3 h-3" /> Engine Stats</div>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between"><span className="text-gray-500">Strategies Active</span><span className="text-white">6</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Signals Generated</span><span className="text-blue-400">{sigGen}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Signals Executed</span><span className="text-green-400">{sigFill}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Active Assets</span><span className="text-white">{activeAssets.length}</span></div>
            </div>
            {activeAssets.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1">
                {activeAssets.map(s => (
                  <span key={s} className="text-xs bg-blue-500/10 border border-blue-500/30 text-blue-400 px-2 py-0.5 rounded-full">{s.replace("USDT","")}</span>
                ))}
              </div>
            )}
          </div>
        </aside>

        {/* MAIN CONTENT */}
        <main className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* STAT CARDS */}
          <div className="grid grid-cols-4 gap-4">
            <StatCard label="Open Positions" value={positions} sub="Paper trades active" color={positions > 0 ? "text-green-400" : "text-white"} />
            <StatCard label="Total Trades" value={totalTrades} sub={`W: ${wins} / L: ${losses}  Win Rate: ${winRate}%`} />
            <StatCard label="Realized P&L" value={`${totalPnl >= 0 ? "+" : ""}$${totalPnl.toFixed(2)}`} sub={`Commission paid: $${totalComm.toFixed(2)}`} color={pnlColor} />
            <StatCard label="Max Drawdown" value={`${(drawdown * 100).toFixed(2)}%`} sub="From peak equity" color={drawdown > 0.05 ? "text-red-400" : "text-gray-300"} />
          </div>

          {/* EQUITY CURVE */}
          <div className="bg-[#161b22] border border-gray-800 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-xs font-semibold text-white uppercase tracking-wider">Live Equity Curve</h2>
              <span className={`text-xs font-bold ${(equity - 100000) >= 0 ? "text-green-400" : "text-red-400"}`}>
                {(equity - 100000) >= 0 ? "+" : ""}${(equity - 100000).toFixed(2)} from start
              </span>
            </div>
            <div className="h-[180px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={equityCurve}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
                  <XAxis dataKey="time" hide />
                  <YAxis domain={["auto","auto"]} stroke="#30363d" tick={{ fontSize: 10, fill: "#8b949e" }} width={75} tickFormatter={v => `$${(v/1000).toFixed(1)}k`} />
                  <Tooltip contentStyle={{ backgroundColor: "#161b22", borderColor: "#30363d", fontSize: 12 }} formatter={(v: any) => [`$${Number(v).toLocaleString()}`, "Equity"]} />
                  <Line type="monotone" dataKey="value" stroke="#58a6ff" strokeWidth={2} dot={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* MARKET SCANNER */}
            <div className="bg-[#161b22] border border-gray-800 rounded-xl p-4 flex flex-col">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-xs font-semibold text-white uppercase tracking-wider">Market Scanner</h2>
                <span className="text-xs text-gray-500">Threshold ≥ {threshold}</span>
              </div>
              <div className="flex-1 overflow-y-auto">
                <table className="w-full text-xs">
                  <thead className="text-gray-500 border-b border-gray-800">
                    <tr>
                      <th className="text-left pb-2">Asset</th>
                      <th className="text-left pb-2">Score</th>
                      <th className="text-left pb-2">Regime</th>
                      <th className="text-left pb-2">Bid</th>
                      <th className="text-left pb-2">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scoredAssets.length === 0 && (
                      <tr><td colSpan={5} className="text-gray-600 py-4 text-center">Waiting for scan...</td></tr>
                    )}
                    {scoredAssets.map((a: any, i) => (
                      <tr key={i} className="border-t border-gray-800/40 hover:bg-white/[0.02]">
                        <td className="py-1.5 font-mono text-white font-bold">{a.symbol.replace("USDT","")}<span className="text-gray-600 font-normal">/USDT</span></td>
                        <td className="py-1.5">
                          <span className={a.score >= threshold ? "text-green-400 font-bold" : "text-gray-500"}>{a.score?.toFixed(1)}</span>
                          <span className="ml-1">{a.trend === "UP" ? <TrendingUp className="inline w-3 h-3 text-green-500" /> : a.trend === "DOWN" ? <TrendingDown className="inline w-3 h-3 text-red-500" /> : <Minus className="inline w-3 h-3 text-gray-600" />}</span>
                        </td>
                        <td className="py-1.5">
                          {a.regime ? (
                            <span className={`px-1.5 py-0.5 rounded border text-xs ${REGIME_BG[a.regime] || "bg-gray-800 border-gray-700"} ${REGIME_COLOR[a.regime] || "text-gray-400"}`}>
                              {a.regime}
                            </span>
                          ) : <span className="text-gray-700">—</span>}
                        </td>
                        <td className="py-1.5 font-mono text-gray-400">{a.bid > 0 ? a.bid.toFixed(4) : "—"}</td>
                        <td className="py-1.5">
                          {a.status === "ACTIVE"
                            ? <span className="bg-green-500/10 border border-green-500/30 text-green-400 px-1.5 py-0.5 rounded text-xs">ACTIVE</span>
                            : <span className="text-gray-700 text-xs">EVAL</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* RIGHT PANEL: POSITIONS + HISTORY */}
            <div className="flex flex-col gap-4">
              {/* OPEN POSITIONS */}
              <div className="bg-[#161b22] border border-gray-800 rounded-xl p-4 flex-1">
                <h2 className="text-xs font-semibold text-white uppercase tracking-wider mb-3 flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${positions > 0 ? "bg-green-400 animate-pulse" : "bg-gray-700"}`} />
                  Live Positions ({positions})
                </h2>
                <div className="space-y-2 overflow-y-auto max-h-[160px]">
                  {openPos.length === 0
                    ? <div className="text-gray-600 text-xs text-center py-4">No active positions. Engine is hunting...</div>
                    : openPos.map((p: any, i) => (
                      <div key={i} className="bg-[#0d1117] border border-gray-800 rounded-lg p-2.5 flex justify-between items-center">
                        <div>
                          <span className="text-white font-bold text-sm">{p.symbol}</span>
                          <span className={`ml-2 text-xs font-semibold ${p.direction === "long" ? "text-green-400" : "text-red-400"}`}>{p.direction.toUpperCase()}</span>
                          <div className="text-gray-600 text-xs mt-0.5">{p.strategy} · Entry: ${p.entry_price?.toFixed(4)}</div>
                          <div className="text-gray-600 text-xs">SL: ${p.stop_loss?.toFixed(4)} · TP: ${p.take_profit?.toFixed(4)}</div>
                        </div>
                        <div className="text-right">
                          <div className={`font-bold text-sm ${p.unrealized_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                            {p.unrealized_pnl >= 0 ? "+" : ""}${p.unrealized_pnl?.toFixed(2)}
                          </div>
                          <div className="text-gray-600 text-xs">{p.current_price?.toFixed(4)}</div>
                        </div>
                      </div>
                    ))}
                </div>
              </div>

              {/* TRADE HISTORY */}
              <div className="bg-[#161b22] border border-gray-800 rounded-xl p-4 flex-1">
                <h2 className="text-xs font-semibold text-white uppercase tracking-wider mb-3">Trade History ({totalTrades})</h2>
                <div className="space-y-2 overflow-y-auto max-h-[160px]">
                  {closedPos.length === 0
                    ? <div className="text-gray-600 text-xs text-center py-4">No closed trades yet.</div>
                    : [...closedPos].reverse().map((p: any, i) => (
                      <div key={i} className="bg-[#0d1117] border border-gray-800 rounded-lg p-2.5 flex justify-between items-center">
                        <div>
                          <span className="text-gray-300 font-bold text-sm">{p.symbol}</span>
                          <span className={`ml-2 text-xs ${p.direction === "long" ? "text-green-500/70" : "text-red-500/70"}`}>{p.direction?.toUpperCase()}</span>
                          <div className="text-gray-600 text-xs mt-0.5">{p.strategy}</div>
                          <div className="text-gray-700 text-xs">Exit: ${p.exit_price?.toFixed(4)}</div>
                        </div>
                        <div className={`font-bold text-sm ${p.pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                          {p.pnl >= 0 ? "+" : ""}${p.pnl?.toFixed(2)}
                        </div>
                      </div>
                    ))}
                </div>
              </div>
            </div>
          </div>

          {/* SYSTEM LOGS */}
          <div className="bg-[#161b22] border border-gray-800 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-xs font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                <AlertCircle className="w-3 h-3 text-yellow-500" /> System Logs
              </h2>
              <span className="text-xs text-gray-600">{logs.length} entries · newest first</span>
            </div>
            <div ref={logsRef} className="h-[140px] overflow-y-auto font-mono text-xs text-gray-400 space-y-0.5 bg-[#0d1117] rounded-lg p-3">
              {logs.length === 0
                ? <div className="text-gray-700">Awaiting system events...</div>
                : logs.map((l, i) => (
                  <div key={i} className={`${l.includes("TRADE") ? "text-green-400" : l.includes("POSITION CLOSED") ? "text-yellow-400" : l.includes("Error") || l.includes("FLATTEN") ? "text-red-400" : l.includes("STARTED") || l.includes("RESET") ? "text-blue-400" : "text-gray-500"}`}>
                    {l}
                  </div>
                ))}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
