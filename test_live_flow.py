"""Live flow test script — monitors the trading system end-to-end."""
import asyncio
import json
import time
import requests
import websockets

API = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000/ws/telemetry"


async def poll_telemetry(duration_s=120, interval_s=10):
    """Poll WebSocket telemetry for `duration_s` seconds."""
    results = []
    start = time.time()
    poll_num = 0

    while time.time() - start < duration_s:
        poll_num += 1
        try:
            async with websockets.connect(WS, open_timeout=5) as ws:
                await ws.send("ping")
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(msg)

                snapshot = {
                    "poll": poll_num,
                    "elapsed_s": round(time.time() - start, 1),
                    "status": data.get("status"),
                    "equity": data.get("equity"),
                    "cash": data.get("cash"),
                    "active_assets": data.get("active_assets", []),
                    "scored_assets_count": len(data.get("scored_assets", [])),
                    "open_positions_count": len(data.get("open_positions", [])),
                    "total_trades": data.get("total_trades"),
                    "winning_trades": data.get("winning_trades"),
                    "losing_trades": data.get("losing_trades"),
                    "total_pnl": data.get("total_pnl"),
                    "total_commission": data.get("total_commission"),
                    "max_drawdown_pct": data.get("max_drawdown_pct"),
                    "signals_generated": data.get("signals_generated"),
                    "signals_filled": data.get("signals_filled"),
                    "log_count": len(data.get("logs", [])),
                }
                results.append(snapshot)

                print(f"\n{'='*60}")
                print(f"POLL #{poll_num} | T+{snapshot['elapsed_s']}s")
                print(f"{'='*60}")
                print(f"  Status:          {snapshot['status']}")
                print(f"  Equity:          ${snapshot['equity']:,.2f}")
                print(f"  Cash:            ${snapshot['cash']:,.2f}")
                print(f"  Active Assets:   {len(snapshot['active_assets'])} {snapshot['active_assets'][:5]}")
                print(f"  Scored Assets:   {snapshot['scored_assets_count']}")
                print(f"  Open Positions:  {snapshot['open_positions_count']}")
                print(f"  Total Trades:    {snapshot['total_trades']}")
                print(f"  Signals Gen:     {snapshot['signals_generated']}")
                print(f"  Signals Filled:  {snapshot['signals_filled']}")
                print(f"  Total PnL:       ${snapshot['total_pnl']:,.2f}")
                print(f"  Max Drawdown:    {snapshot['max_drawdown_pct']:.4%}")

                # Print latest logs
                logs = data.get("logs", [])
                print(f"\n  Latest Logs ({len(logs)}):")
                for log in logs[:15]:
                    print(f"    {log}")

                # Print open positions
                positions = data.get("open_positions", [])
                if positions:
                    print(f"\n  Open Positions:")
                    for p in positions:
                        sym = p.get("symbol", "?")
                        direction = p.get("direction", "?")
                        entry = p.get("entry_price", 0)
                        current = p.get("current_price", 0)
                        pnl = p.get("unrealized_pnl", 0)
                        print(f"    {sym} {direction} entry=${entry:.4f} cur=${current:.4f} pnl=${pnl:.2f}")

                # Print scored assets summary
                scored = data.get("scored_assets", [])
                if scored:
                    print(f"\n  Top Scored Assets:")
                    for s in scored[:8]:
                        sym = s.get("symbol", "?")
                        score = s.get("score", 0)
                        regime = s.get("regime", "?")
                        print(f"    {sym}: score={score:.1f} regime={regime}")

        except Exception as e:
            print(f"\n[Poll {poll_num}] WebSocket Error: {e}")

        await asyncio.sleep(interval_s)

    return results


def main():
    print("=" * 60)
    print("  AlgoForge Live Flow Test")
    print("=" * 60)

    # Step 1: Health check
    print("\n[1] Health Check...")
    try:
        r = requests.get(f"{API}/api/health", timeout=5)
        health = r.json()
        print(f"    Status: {health}")
    except Exception as e:
        print(f"    FAILED: {e}")
        print("    Backend not running! Start with: uvicorn algoforge.api.server:app --port 8000")
        return

    # Step 2: Check current config
    print("\n[2] Current Config...")
    r = requests.get(f"{API}/api/config", timeout=5)
    config = r.json()
    print(f"    {json.dumps(config, indent=4)}")

    # Step 3: Check if system is already running
    if health.get("system_running"):
        print("\n[3] System already running, monitoring...")
    else:
        # Apply config and start
        print("\n[3] Starting trading system...")
        r = requests.post(f"{API}/api/system/start", timeout=10)
        print(f"    Start response: {r.json()}")

    # Step 4: Monitor for 2 minutes
    print("\n[4] Monitoring live flow for 2 minutes...")
    results = asyncio.run(poll_telemetry(duration_s=120, interval_s=10))

    # Step 5: Check trade history
    print("\n\n[5] Trade History...")
    try:
        r = requests.get(f"{API}/api/trades", timeout=5)
        trades = r.json()
        print(f"    Total persisted: {trades.get('total_persisted', 0)}")
        print(f"    Strategy stats: {json.dumps(trades.get('strategy_stats', {}), indent=6)}")
    except Exception as e:
        print(f"    Trade history error: {e}")

    # Step 6: Summary
    print("\n" + "=" * 60)
    print("  LIVE FLOW SUMMARY")
    print("=" * 60)
    if results:
        final = results[-1]
        first = results[0]
        print(f"  Duration:        {final['elapsed_s']}s")
        print(f"  Final Equity:    ${final['equity']:,.2f}")
        print(f"  Active Assets:   {len(final['active_assets'])}")
        print(f"  Scored Assets:   {final['scored_assets_count']}")
        print(f"  Total Trades:    {final['total_trades']}")
        print(f"  Signals Gen:     {final['signals_generated']}")
        print(f"  Signals Filled:  {final['signals_filled']}")
        print(f"  Total PnL:       ${final['total_pnl']:,.2f}")
        print(f"  Max Drawdown:    {final['max_drawdown_pct']:.4%}")
        print(f"  Open Positions:  {final['open_positions_count']}")

    # Save results
    with open("data/live_flow_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved to data/live_flow_test_results.json")


if __name__ == "__main__":
    main()
