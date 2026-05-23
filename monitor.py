"""Stay-connected diagnostic: listens on the WebSocket for live updates."""
import asyncio
import json
import websockets
import time
import sys
import requests

API = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000/ws/telemetry"

async def monitor(duration=180):
    # Make sure system is started
    r = requests.get(f"{API}/api/health", timeout=5)
    h = r.json()
    print(f"Health: {h}", flush=True)
    
    if not h.get("system_running"):
        print("Applying Config...", flush=True)
        r = requests.post(f"{API}/api/config/apply", timeout=10)
        print(f"Config: {r.json()}", flush=True)
        
        print("Starting system...", flush=True)
        r = requests.post(f"{API}/api/system/start", timeout=10)
        print(f"Start: {r.json()}", flush=True)
        await asyncio.sleep(1)
    
    t0 = time.time()
    print(f"\nConnecting to WebSocket...", flush=True)
    
    async with websockets.connect(WS, open_timeout=10) as ws:
        print("Connected! Listening for updates...\n", flush=True)
        
        while time.time() - t0 < duration:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(msg)
                
                elapsed = round(time.time() - t0, 1)
                status = data.get("status", "?")
                equity = data.get("equity", 0)
                assets = data.get("active_assets", [])
                scored = len(data.get("scored_assets", []))
                positions = len(data.get("open_positions", []))
                trades = data.get("total_trades", 0)
                sig_gen = data.get("signals_generated", 0)
                sig_fill = data.get("signals_filled", 0)
                pnl = data.get("total_pnl", 0)
                logs = data.get("logs", [])
                
                print(f"[T+{elapsed}s] {status} | eq=${equity:,.2f} | assets={len(assets)} scored={scored} | pos={positions} trades={trades} | sig={sig_gen}/{sig_fill} | pnl=${pnl:,.2f}", flush=True)
                print(f"  Active: {assets[:5]}", flush=True)
                
                # Show new logs
                for log in logs[:10]:
                    print(f"  LOG: {log}", flush=True)
                    
                print("", flush=True)
                
            except asyncio.TimeoutError:
                print(f"[T+{round(time.time()-t0,1)}s] Waiting for update...", flush=True)
            except websockets.ConnectionClosed:
                print("WebSocket closed!", flush=True)
                break

asyncio.run(monitor(120))
