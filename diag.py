"""Direct diagnostic — checks what the system is doing right now."""
import requests
import json
import sys
import asyncio
import websockets
import time

API = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000/ws/telemetry"

def check():
    # Health
    r = requests.get(f"{API}/api/health", timeout=5)
    print("HEALTH:", r.json())
    
    # Start if not running
    if not r.json().get("system_running"):
        print("Starting system...")
        r = requests.post(f"{API}/api/system/start", timeout=10)
        print("START:", r.json())
        time.sleep(2)  # Give it time to start
    
    # WebSocket telemetry
    async def ws_check():
        try:
            async with websockets.connect(WS, open_timeout=5) as ws:
                await ws.send("ping")
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(msg)
                print(f"\nSTATUS: {data.get('status')}")
                print(f"EQUITY: {data.get('equity')}")
                print(f"ACTIVE: {data.get('active_assets')}")
                print(f"SCORED: {len(data.get('scored_assets', []))}")
                print(f"POSITIONS: {len(data.get('open_positions', []))}")
                print(f"TRADES: {data.get('total_trades')}")
                print(f"SIGNALS: gen={data.get('signals_generated')} fill={data.get('signals_filled')}")
                print(f"PNL: {data.get('total_pnl')}")
                print(f"\nLOGS ({len(data.get('logs',[]))}):")
                for log in data.get('logs', [])[:25]:
                    print(f"  {log}")
                    
                # Also check scored assets
                scored = data.get('scored_assets', [])
                if scored:
                    print(f"\nSCORED ASSETS ({len(scored)}):")
                    for s in scored[:10]:
                        print(f"  {s.get('symbol')}: score={s.get('score', 0):.1f} regime={s.get('regime', '?')}")
                        
        except Exception as e:
            print(f"WS ERROR: {e}")
    
    asyncio.run(ws_check())
    sys.stdout.flush()

if __name__ == "__main__":
    check()
