import asyncio
import json
import websockets
import structlog
import requests
from datetime import datetime, timezone

logger = structlog.get_logger(__name__)

class BinanceAdapter:
    def __init__(self, callback):
        self.callback = callback
        self.running = False
        self._ws = None
        self._stream_task = None  # Track the stream task for cancellation

    def fetch_top_n_universe(self, limit=50) -> list[dict]:
        """Fetch top N symbols by 24h quote volume from Binance."""
        try:
            url = "https://api.binance.com/api/v3/ticker/24hr"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            # Filter USDT pairs, excluding stablecoins and leveraged tokens
            excludes = {"USDCUSDT", "FDUSDUSDT", "TUSDUSDT", "EURUSDT", "BUSDUSDT"}
            usdt_pairs = [
                d for d in data
                if d['symbol'].endswith('USDT')
                and d['symbol'] not in excludes
                and 'UP' not in d['symbol']   # exclude 3x longs
                and 'DOWN' not in d['symbol'] # exclude 3x shorts
                and 'BULL' not in d['symbol']
                and 'BEAR' not in d['symbol']
            ]
            
            # Sort by quote volume
            usdt_pairs.sort(key=lambda x: float(x['quoteVolume']), reverse=True)
            
            universe = []
            for d in usdt_pairs[:limit]:
                universe.append({
                    "symbol": d['symbol'],
                    "volume": float(d['quoteVolume']),
                    "price_change_pct": float(d['priceChangePercent']),
                    "last_price": float(d['lastPrice']),
                    "high": float(d['highPrice']),
                    "low": float(d['lowPrice'])
                })
            return universe
        except Exception as e:
            logger.error("binance_rest_error", error=str(e))
            return []

    async def start_streams(self, symbols: list[str]):
        """Stream klines and orderbook for selected symbols."""
        self.running = True
        
        if not symbols:
            return
            
        streams = []
        for s in symbols:
            sym = s.lower()
            streams.append(f"{sym}@bookTicker")  # Best Bid/Ask
            streams.append(f"{sym}@kline_1m")    # OHLCV
            
        stream_str = "/".join(streams)
        uri = f"wss://stream.binance.com:9443/ws/{stream_str}"
        
        while self.running:
            try:
                async with websockets.connect(uri, ping_interval=20, ping_timeout=10) as ws:
                    self._ws = ws
                    logger.info("binance_ws_connected", num_streams=len(streams))
                    while self.running:
                        try:
                            # Use wait_for so we check self.running every second
                            msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                            data = json.loads(msg)
                            await self.handle_message(data)
                        except asyncio.TimeoutError:
                            continue  # check self.running again
            except asyncio.CancelledError:
                break
            except Exception as e:
                if self.running:  # Only log if not deliberately stopped
                    logger.error("binance_ws_error", error=str(e))
                    await asyncio.sleep(2)  # Reconnect delay
                else:
                    break

    async def handle_message(self, data: dict):
        try:
            # 1. Kline
            if "e" in data and data["e"] == "kline":
                k = data["k"]
                normalized = {
                    "type": "kline",
                    "symbol": data["s"],
                    "price": float(k["c"]),
                    "open": float(k["o"]),
                    "high": float(k["h"]),
                    "low": float(k["l"]),
                    "volume": float(k["v"]),
                    "is_closed": k["x"],
                    "timestamp": datetime.fromtimestamp(data["E"]/1000, tz=timezone.utc)
                }
                await self.callback(normalized)
                
            # 2. BookTicker (Bid/Ask)
            elif "u" in data and "b" in data and "a" in data:
                normalized = {
                    "type": "book",
                    "symbol": data["s"],
                    "bid": float(data["b"]),
                    "ask": float(data["a"]),
                    "bid_qty": float(data["B"]),
                    "ask_qty": float(data["A"]),
                    "timestamp": datetime.now(timezone.utc)
                }
                await self.callback(normalized)
        except Exception:
            pass  # Ignore malformed packets

    async def stop(self):
        """Cleanly stop all streams."""
        self.running = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
